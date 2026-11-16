"""
MCP server exposing one ChimeraFlow data source (stdio transport).

One process serves one source (`--source excel|access|whatsapp|momo`), so Kiro
lists four servers. Tools are read-only and mirror the connector contract of
.kiro/specs/connectors-spec.md (R1): `fetch_records(limit)` and `health_check()`.

The launcher (backend/mcp_main.py) configures logging on stderr: stdout carries the protocol.
"""
import asyncio
import importlib
import json
import logging
import time
from typing import Annotated, Any, Awaitable, Callable, Dict, List, Optional, TypeVar

import anyio
import anyio.to_thread
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from .access_connector import AccessConnector
from .base import CONNECTOR_ERRORS, BaseConnector
from .excel_connector import ExcelConnector
from .mcp_settings import McpSettings
from .momo_connector import MobileMoneyConnector
from .whatsapp_connector import WhatsAppConnector

logger = logging.getLogger("chimeraflow.mcp")

# connectors.md: 5 s max per fetch, 2 attempts with exponential backoff, limit 1..1000
OPERATION_TIMEOUT_SECONDS = 5.0
MAX_ATTEMPTS = 2
BACKOFF_BASE_SECONDS = 0.2
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

_T = TypeVar("_T")

_READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)


class HealthCheckResult(BaseModel):
    """Connector health (connectors-spec.md R1); a connector may add fields such as `tables`."""

    model_config = ConfigDict(extra="allow")

    status: str = Field(description="ok, degraded or error")
    source: str
    message: Optional[str] = None
    last_fetch: Optional[str] = None


class FetchRecordsResult(BaseModel):
    """Records of one fetch, in the unified record schema (AGENTS.md §19)."""

    source: str
    count: int
    parse_errors: int = Field(description="Rows skipped as malformed during this call")
    records: List[Dict[str, Any]]


def build_connector(settings: McpSettings) -> BaseConnector:
    """Create the connector of the configured source.

    Args:
        settings: Validated server settings.

    Returns:
        Connector reading the source file under DATA_DIR.
    """
    path = str(settings.file_path)
    name = settings.source.name
    if name == "excel":
        # Imported at startup, not on the first call: pandas loads it lazily and
        # that cold import would eat the 5 s timeout of the first fetch
        importlib.import_module("openpyxl")
        return ExcelConnector(path)
    if name == "access":
        if settings.access_reader == "access-parser":
            importlib.import_module("access_parser")  # same reason as openpyxl above
        return AccessConnector(path, reader=settings.access_reader)
    if name == "whatsapp":
        return WhatsAppConnector(path)
    return MobileMoneyConnector(path)


def _log_operation(
    connector: str, operation: str, records_count: int, errors_count: int, started: float, status: str
) -> None:
    """Emit one structured log line (connectors.md). Record content is never logged."""
    logger.info(
        json.dumps(
            {
                "connector": connector,
                "operation": operation,
                "records_count": records_count,
                "errors_count": errors_count,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "status": status,
            }
        )
    )


async def _run_bounded(call: Callable[[], Awaitable[_T]]) -> _T:
    """Run a connector call off the event loop, with a timeout and one retry.

    Connectors do blocking I/O inside coroutines, so the call runs in a worker
    thread: the 5 s timeout then holds even when a read hangs.

    Raises:
        TimeoutError: If an attempt exceeds OPERATION_TIMEOUT_SECONDS (not retried).
        CONNECTOR_ERRORS: The last failure, after MAX_ATTEMPTS attempts.
    """

    def in_worker() -> _T:
        return asyncio.run(call())

    for attempt in range(MAX_ATTEMPTS):
        try:
            with anyio.fail_after(OPERATION_TIMEOUT_SECONDS):
                return await anyio.to_thread.run_sync(in_worker, abandon_on_cancel=True)
        except TimeoutError:
            # Listed first: TimeoutError is an OSError, which CONNECTOR_ERRORS retries
            raise
        except CONNECTOR_ERRORS:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            await anyio.sleep(BACKOFF_BASE_SECONDS * 2**attempt)
    raise RuntimeError("unreachable")  # pragma: no cover


def create_server(settings: McpSettings, connector: Optional[BaseConnector] = None) -> MCPServer:
    """Build the MCP server of one source.

    Args:
        settings: Validated server settings.
        connector: Connector to serve (built from the settings when omitted).

    Returns:
        Server with the tools `fetch_records` and `health_check` and one
        metadata resource.
    """
    source = settings.source
    served = build_connector(settings) if connector is None else connector
    # One connector call at a time: its parse-error counter is shared state, and
    # pandas/openpyxl are not safe to import for the first time from two threads
    serialized = anyio.Lock()
    server = MCPServer(
        name=f"chimeraflow-{source.name}",
        instructions=(
            f"Read-only access to the ChimeraFlow '{source.name}' source ({source.description}). "
            "Call health_check first, then fetch_records."
        ),
    )

    @server.tool(annotations=_READ_ONLY)
    async def fetch_records(
        limit: Annotated[
            int, Field(ge=1, le=MAX_LIMIT, description=f"Maximum number of records (1 to {MAX_LIMIT})")
        ] = DEFAULT_LIMIT,
    ) -> FetchRecordsResult:
        """Fetch records of this source in the unified record schema."""
        started = time.monotonic()
        try:
            async with serialized:
                errors_before = getattr(served, "parse_errors", 0)
                records = await _run_bounded(lambda: served.fetch_records(limit))
                errors_count = getattr(served, "parse_errors", 0) - errors_before
        except TimeoutError as exc:
            _log_operation(source.name, "fetch_records", 0, 0, started, "timeout")
            raise ToolError(f"Source '{source.name}' did not answer within {OPERATION_TIMEOUT_SECONDS:g} s") from exc
        except CONNECTOR_ERRORS as exc:
            logger.error("fetch_records failed for %s: %s", source.name, exc)
            _log_operation(source.name, "fetch_records", 0, 0, started, "error")
            raise ToolError(f"Source '{source.name}' could not be read ({type(exc).__name__})") from exc
        _log_operation(source.name, "fetch_records", len(records), errors_count, started, "ok")
        return FetchRecordsResult(
            source=source.name,
            count=len(records),
            parse_errors=errors_count,
            records=[record.to_dict() for record in records],
        )

    @server.tool(annotations=_READ_ONLY)
    async def health_check() -> HealthCheckResult:
        """Report whether the source file is readable (status ok, degraded or error)."""
        started = time.monotonic()
        try:
            async with serialized:
                health = await _run_bounded(served.health_check)
        except (TimeoutError, *CONNECTOR_ERRORS) as exc:
            _log_operation(source.name, "health_check", 0, 0, started, "error")
            raise ToolError(f"Health check of '{source.name}' failed ({type(exc).__name__})") from exc
        _log_operation(source.name, "health_check", 0, 0, started, str(health.get("status")))
        return HealthCheckResult(**health)

    @server.resource(f"chimeraflow://source/{source.name}", mime_type="application/json")
    def source_metadata() -> str:
        """Static description of this source and of its tools."""
        return json.dumps(
            {
                "source": source.name,
                "description": source.description,
                "file": source.file_name,
                "format": source.file_format,
                "read_only": True,
                "limit": {"default": DEFAULT_LIMIT, "max": MAX_LIMIT},
                "tools": ["fetch_records", "health_check"],
            }
        )

    return server
