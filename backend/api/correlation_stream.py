"""
Live correlation feed (Server-Sent Events): GET /api/v1/correlations/stream

Authentication is the usual `Authorization: Bearer` header. The browser's
`EventSource` cannot send that header, so clients read the stream with
`fetch` (no signed stream token is needed, and no token ever travels in a URL).

The stream polls the database, so it works across workers and processes:

- `event: ready`: the stream is open
- `event: correlation` (`id:` is the correlation id): a correlation stored since
  the last event, in the CorrelationResponse format
- `event: execution`: rules were executed since the last event; clients that
  show a list refresh it, because executions also remove correlations
- `event: end`: the server closed the stream after STREAM_MAX_SECONDS; reconnect
  with the `Last-Event-ID` header to resume without a gap

A comment line (`: keep-alive`) keeps idle connections open. Without
`Last-Event-ID` the stream starts from now: only later correlations arrive.
"""
import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

import anyio
from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from api.correlations import to_response
from api.errors import STREAM_LIMIT_REACHED, api_error
from models.base import SessionLocal
from models.rule import Correlation, RuleExecution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/correlations", tags=["correlations"])

STREAM_POLL_SECONDS = 2.0
STREAM_HEARTBEAT_SECONDS = 15.0
STREAM_MAX_SECONDS = 300.0
MAX_CONCURRENT_STREAMS = 20
MAX_EVENTS_PER_POLL = 200
RETRY_MILLISECONDS = 3000

_open_streams = 0


def _frame(data: Any, event: str, event_id: Optional[int] = None) -> str:
    """One SSE frame. JSON never holds a raw newline, so one `data:` line is enough."""
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}")
    return "\n".join(lines) + "\n\n"


def _current_cursors() -> Tuple[int, int]:
    """Highest correlation id and execution id stored now (0 when empty)."""
    with SessionLocal() as db:
        correlation_id = db.query(func.max(Correlation.id)).scalar() or 0
        execution_id = db.query(func.max(RuleExecution.id)).scalar() or 0
    return correlation_id, execution_id


def _poll(after_correlation: int, after_execution: int) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]], int]:
    """Read what was stored after the cursors.

    Returns:
        (new correlations as API dicts, a summary of the executions or None,
        the new execution cursor)
    """
    with SessionLocal() as db:
        rows = (
            db.query(Correlation)
            .filter(Correlation.id > after_correlation)
            .order_by(Correlation.id)
            .limit(MAX_EVENTS_PER_POLL)
            .all()
        )
        correlations = [to_response(row).model_dump() for row in rows]
        executions = db.query(RuleExecution).filter(RuleExecution.id > after_execution).all()
        summary = None
        if executions:
            summary = {
                "rules": len(executions),
                "failed": sum(1 for e in executions if e.error),
                "executed_at": max(e.executed_at for e in executions).isoformat(),
            }
        return correlations, summary, max((e.id for e in executions), default=after_execution)


async def _events(
    request: Request, after_correlation: int, after_execution: int
) -> AsyncIterator[str]:
    """Frames of the stream, until the client leaves or STREAM_MAX_SECONDS pass."""
    global _open_streams
    _open_streams += 1
    try:
        yield f"retry: {RETRY_MILLISECONDS}\n\n" + _frame({}, "ready")
        started = last_sent = time.monotonic()
        while time.monotonic() - started < STREAM_MAX_SECONDS:
            if await request.is_disconnected():
                return
            correlations, executions, after_execution = await anyio.to_thread.run_sync(
                _poll, after_correlation, after_execution
            )
            frames = []
            for correlation in correlations:
                after_correlation = max(after_correlation, correlation["id"])
                frames.append(_frame(correlation, "correlation", correlation["id"]))
            if executions is not None:
                frames.append(_frame(executions, "execution"))
            if frames:
                last_sent = time.monotonic()
                yield "".join(frames)
            elif time.monotonic() - last_sent >= STREAM_HEARTBEAT_SECONDS:
                last_sent = time.monotonic()
                yield ": keep-alive\n\n"
            await asyncio.sleep(STREAM_POLL_SECONDS)
        yield _frame({}, "end")
    finally:
        _open_streams -= 1


def _parse_event_id(value: Optional[str]) -> Optional[int]:
    """Last-Event-ID as a correlation id, None when absent or not a non-negative integer."""
    if value is None or not value.isascii() or not value.isdigit():
        return None
    return int(value)


@router.get("/stream")
async def stream_correlations(
    request: Request,
    last_event_id: Optional[str] = Header(default=None, max_length=20),
):
    """
    Stream new correlations and execution notices (Server-Sent Events)

    Read it with `fetch` and the Bearer header. Send `Last-Event-ID` to resume
    after a reconnection. At most MAX_CONCURRENT_STREAMS streams are open at once.
    """
    if _open_streams >= MAX_CONCURRENT_STREAMS:
        raise api_error(429, STREAM_LIMIT_REACHED, "Too many open streams")

    resume_from = _parse_event_id(last_event_id)
    after_correlation, after_execution = await anyio.to_thread.run_sync(_current_cursors)
    if resume_from is not None:
        after_correlation = resume_from

    return StreamingResponse(
        _events(request, after_correlation, after_execution),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
