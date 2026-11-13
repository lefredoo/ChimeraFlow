"""
Correlation execution API endpoints
POST /correlations/execute, GET /correlations
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime, timezone

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


@router.post("/execute")
async def execute_correlations(
    rule_ids: Optional[List[str]] = Query(None, max_length=MAX_RULE_IDS),
    db: Session = Depends(get_db)
):
    """
    Execute active correlation rules against current data

    Inactive and draft rules are never executed. Each execution replaces the
    previous correlations of the rules it runs, so running twice gives the
    same result.

    Query params:
    - rule_ids: List of specific rule IDs to execute (max 20, default: all active)

    Returns:
        Summary of execution (rules executed and failed, correlations found, records scanned)
    """
    start_time = datetime.now(timezone.utc)

    query = db.query(Rule).filter(Rule.status == RuleStatus.active)
    if rule_ids:
        query = query.filter(Rule.id.in_(rule_ids))
    rules_db = query.order_by(Rule.id).all()

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

    # Execute each rule
    interpreter = RuleInterpreter()
    total_correlations = 0
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

                db.query(Correlation).filter(Correlation.rule_id == rule.id).delete(
                    synchronize_session=False
                )
                for corr in correlations:
                    db.add(Correlation(
                        rule_id=corr["rule_id"],
                        detected_at=rule_start,
                        severity=CorrelationSeverity(corr["severity"]),
                        message=corr["message"],
                        provenance=corr["provenance"],
                        window_start=datetime.fromisoformat(corr["window_start"]),
                        window_end=datetime.fromisoformat(corr["window_end"])
                    ))

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

    total_duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

    return {
        "status": "success",
        "rules_executed": rules_executed,
        "rules_failed": rules_failed,
        "correlations_found": total_correlations,
        "records_scanned": total_records,
        "duration_ms": total_duration_ms
    }

@router.get("", response_model=List[CorrelationResponse])
async def list_correlations(
    rule_id: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    List correlations
    
    Query params:
    - rule_id: Filter by rule ID
    - severity: Filter by severity (info, warning, error)
    - limit: Max results (default 100, 1 to 1000)
    """
    query = db.query(Correlation).order_by(Correlation.detected_at.desc(), Correlation.id)
    
    if rule_id:
        query = query.filter(Correlation.rule_id == rule_id)
    
    if severity:
        try:
            severity_enum = CorrelationSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
        query = query.filter(Correlation.severity == severity_enum)
    
    correlations = query.limit(limit).all()
    
    return [
        CorrelationResponse(
            id=c.id,
            rule_id=c.rule_id,
            detected_at=c.detected_at.isoformat(),
            severity=c.severity.value,
            message=c.message,
            provenance=c.provenance
        )
        for c in correlations
    ]


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
            all_records[name] = await connector_class(str(path)).fetch_records(limit=1000)
        except CONNECTOR_ERRORS as e:
            logger.warning(f"Failed to fetch {name} records: {e}")
            all_records[name] = []

    return all_records
