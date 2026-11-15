"""
Correlation execution API endpoints
POST /correlations/execute, GET /correlations
(the live stream, GET /correlations/stream, is in api/correlation_stream.py)
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional, Tuple
import anyio
import logging
from datetime import datetime, timezone

from api.errors import INVALID_SEVERITY, api_error
from api.rate_limit import limiter, mutation_limit
from engine.alerts import AlertItem, dispatch_alerts, select_alert_items
from models.base import get_db
from models.rule import Rule, Correlation, CorrelationSeverity, RuleExecution, RuleStatus
from schemas.rule import CorrelationResponse, RuleCreate
from engine.interpreter import RuleInterpreter
from mcp_servers.base import CONNECTOR_ERRORS
from mcp_servers.excel_connector import ExcelConnector
from mcp_servers.access_connector import AccessConnector
from mcp_servers.whatsapp_connector import WhatsAppConnector
from mcp_servers.momo_connector import MobileMoneyConnector
from config import DATA_DIR
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/correlations", tags=["correlations"])

MAX_RULE_IDS = 20

# Stored in RuleExecution.error; details go to the logs only
GENERIC_EXECUTION_ERROR = "Rule execution failed"

CorrelationKey = Tuple[str, Tuple[str, ...]]


def _to_schema(rule: Rule) -> RuleCreate:
    """Convert a stored rule to the schema the interpreter executes.

    Raises:
        ValidationError: If the stored JSON no longer matches the schema.
    """
    return RuleCreate(
        id=rule.id,
        natural_language=rule.natural_language,
        trigger=rule.trigger,
        joins=rule.joins,
        window_seconds=rule.window_seconds,
        emit=rule.emit
    )


def _correlation_key(message: str, provenance: List[Dict[str, Any]]) -> CorrelationKey:
    """Identity of a correlation: what it says and which records it joins.

    A correlation found again by the next execution keeps its row (and its
    detection time), so clients see only the genuinely new ones.
    """
    return (message, tuple(str(item["record_id"]) for item in provenance))


def _store_correlations(
    db: Session, rule_id: str, correlations: List[Dict[str, Any]], detected_at: datetime
) -> List[Dict[str, Any]]:
    """Make the stored correlations of a rule equal to the ones just found.

    Rows no longer found are deleted, rows found again are refreshed (their
    detection time is kept), new ones are inserted.

    Returns:
        The correlations that were not stored before, in order.
    """
    stored: Dict[CorrelationKey, Correlation] = {}
    for row in db.query(Correlation).filter(Correlation.rule_id == rule_id).order_by(Correlation.id):
        key = _correlation_key(row.message, row.provenance)
        if key in stored:
            db.delete(row)  # a duplicate row never survives
        else:
            stored[key] = row
    found: Dict[CorrelationKey, Dict[str, Any]] = {}
    for corr in correlations:
        found.setdefault(_correlation_key(corr["message"], corr["provenance"]), corr)

    for key, row in stored.items():
        if key not in found:
            db.delete(row)

    created = []
    for key, corr in found.items():
        window = {
            "window_start": datetime.fromisoformat(corr["window_start"]),
            "window_end": datetime.fromisoformat(corr["window_end"]),
        }
        row = stored.get(key)
        if row is not None:
            row.severity = CorrelationSeverity(corr["severity"])
            row.explanation = corr["explanation"]
            row.window_start = window["window_start"]
            row.window_end = window["window_end"]
            continue
        db.add(Correlation(
            rule_id=corr["rule_id"],
            detected_at=detected_at,
            severity=CorrelationSeverity(corr["severity"]),
            message=corr["message"],
            provenance=corr["provenance"],
            explanation=corr["explanation"],
            **window,
        ))
        created.append(corr)
    return created


def _load_active_rules(db: Session, rule_ids: Optional[List[str]]) -> List[Rule]:
    """Active rules to execute, sorted by id (all of them, or the requested ones)."""
    query = db.query(Rule).filter(Rule.status == RuleStatus.active)
    if rule_ids:
        query = query.filter(Rule.id.in_(rule_ids))
    return query.order_by(Rule.id).all()


def _run_rules(
    db: Session, rules_db: List[Rule], all_records: Dict[str, list]
) -> Tuple[Dict[str, int], List[AlertItem]]:
    """Execute rules and store their correlations (blocking: run it in a worker thread).

    Returns:
        (counters of the run, alert items for the new warning and error correlations)
    """
    interpreter = RuleInterpreter()
    total_correlations = 0
    new_correlations: List[Dict[str, Any]] = []
    rules_executed = 0
    rules_failed = 0

    for rule_db in rules_db:
        rule_start = datetime.now(timezone.utc)

        try:
            rule = _to_schema(rule_db)
            trigger_records = all_records.get(rule.trigger.source, [])

            # Savepoint: a failing rule must not leave partial correlations,
            # and its previous correlations stay untouched
            with db.begin_nested():
                correlations = interpreter.execute(rule, trigger_records, all_records)
                new_correlations.extend(_store_correlations(db, rule.id, correlations, rule_start))

                duration_ms = int((datetime.now(timezone.utc) - rule_start).total_seconds() * 1000)
                db.add(RuleExecution(
                    rule_id=rule.id,
                    duration_ms=duration_ms,
                    correlations_found=len(correlations),
                    records_scanned=len(trigger_records)
                ))

            total_correlations += len(correlations)
            rules_executed += 1
            logger.info(f"Rule {rule.id}: {len(correlations)} correlations in {duration_ms}ms")

        except Exception:
            # One failing rule must not stop the others; record it outside the savepoint
            logger.exception(f"Error executing rule {rule_db.id}")
            rules_failed += 1
            db.add(RuleExecution(
                rule_id=rule_db.id,
                duration_ms=0,
                correlations_found=0,
                records_scanned=0,
                error=GENERIC_EXECUTION_ERROR
            ))

    db.commit()
    counters = {
        "rules_executed": rules_executed,
        "rules_failed": rules_failed,
        "correlations_found": total_correlations,
        "new_correlations": len(new_correlations),
    }
    return counters, select_alert_items(new_correlations)


@router.post("/execute")
@limiter.limit(mutation_limit)
async def execute_correlations(
    request: Request,
    background_tasks: BackgroundTasks,
    rule_ids: Optional[List[str]] = Query(None, max_length=MAX_RULE_IDS),
    db: Session = Depends(get_db)
):
    """
    Execute active correlation rules against current data (rate limited per IP)

    Inactive and draft rules are never executed. A correlation found again by
    a later execution keeps its row, so running twice gives the same result and
    only new correlations are new. New warning and error correlations are
    e-mailed in one digest after the response when the alert e-mail is configured.

    Query params:
    - rule_ids: List of specific rule IDs to execute (max 20, default: all active)

    Returns:
        Summary of execution (rules executed and failed, correlations found,
        new correlations, records scanned)
    """
    start_time = datetime.now(timezone.utc)

    rules_db = await run_in_threadpool(_load_active_rules, db, rule_ids)

    if not rules_db:
        return {
            "status": "no_rules",
            "message": "No active rules to execute",
            "rules_executed": 0,
            "rules_failed": 0,
            "correlations_found": 0
        }

    # Fetch all records from sources
    logger.info("Fetching records from all sources...")
    all_records = await _fetch_all_records()

    total_records = sum(len(records) for records in all_records.values())
    logger.info(f"Fetched {total_records} total records from {len(all_records)} sources")

    counters, alerts = await run_in_threadpool(_run_rules, db, rules_db, all_records)
    if alerts:
        background_tasks.add_task(dispatch_alerts, alerts)

    total_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "status": "success",
        **counters,
        "records_scanned": total_records,
        "duration_ms": total_duration_ms
    }


def to_response(c: Correlation) -> CorrelationResponse:
    """API representation of a stored correlation (single conversion point)."""
    return CorrelationResponse(
        id=c.id,
        rule_id=c.rule_id,
        detected_at=c.detected_at.isoformat(),
        severity=c.severity.value,
        message=c.message,
        provenance=c.provenance,
        explanation=c.explanation
    )


@router.get("", response_model=List[CorrelationResponse])
def list_correlations(
    rule_id: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[datetime] = Query(
        default=None,
        description="Only correlations first detected after this instant (ISO 8601; no offset means UTC)",
    ),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    List correlations
    
    Query params:
    - rule_id: Filter by rule ID
    - severity: Filter by severity (info, warning, error)
    - since: Only correlations detected after this instant (polling fallback of the stream)
    - limit: Max results (default 100, 1 to 1000)
    """
    query = db.query(Correlation).order_by(Correlation.detected_at.desc(), Correlation.id)
    
    if rule_id:
        query = query.filter(Correlation.rule_id == rule_id)
    
    if severity:
        try:
            severity_enum = CorrelationSeverity(severity)
        except ValueError:
            raise api_error(400, INVALID_SEVERITY, "Invalid severity filter")
        query = query.filter(Correlation.severity == severity_enum)

    if since is not None:
        # Stored instants are UTC; SQLite drops the offset, so compare in UTC
        utc_since = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since.astimezone(timezone.utc)
        query = query.filter(Correlation.detected_at > utc_since)
    
    return [to_response(c) for c in query.limit(limit).all()]


def _read_source(connector_class, path: Path) -> list:
    """Read a source in a worker thread (connector I/O is blocking: pandas, mdb-export)."""
    return asyncio.run(connector_class(str(path)).fetch_records(limit=1000))


async def _fetch_all_records():
    """Fetch records from all sources (a failing source yields no records)"""
    data_dir = Path(DATA_DIR)

    connectors = {
        "excel": (data_dir / "tarifs_fournisseurs.xlsx", ExcelConnector),
        "access": (data_dir / "STOCK_ZOBO.mdb", AccessConnector),
        "whatsapp": (data_dir / "commandes_clients.txt", WhatsAppConnector),
        "momo": (data_dir / "momo_transactions.csv", MobileMoneyConnector),
    }

    all_records = {}
    for name, (path, connector_class) in connectors.items():
        if not path.exists():
            continue
        try:
            all_records[name] = await anyio.to_thread.run_sync(_read_source, connector_class, path)
        except CONNECTOR_ERRORS as e:
            logger.warning(f"Failed to fetch {name} records: {e}")
            all_records[name] = []

    return all_records
