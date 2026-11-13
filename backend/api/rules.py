"""
Rule management API endpoints
POST /rules, GET /rules, DELETE /rules/{id}
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from models.base import get_db
from models.rule import Rule, RuleStatus
from schemas.rule import RuleCreate, RuleResponse
from engine.predefined_rules import get_predefined_rules, get_predefined_rule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rules", tags=["rules"])

def _to_response(rule: Rule) -> RuleResponse:
    """Convert a stored Rule to its API response (single conversion point).

    Args:
        rule: Rule row loaded from the database.

    Returns:
        RuleResponse with JSON columns validated into schema models.
    """
    return RuleResponse(
        id=rule.id,
        version=rule.version,
        status=rule.status.value,
        natural_language=rule.natural_language,
        trigger=rule.trigger,
        joins=rule.joins,
        window_seconds=rule.window_seconds,
        emit=rule.emit,
        created_at=rule.created_at.isoformat(),
        updated_at=rule.updated_at.isoformat()
    )


@router.get("/predefined", response_model=List[RuleResponse])
async def list_predefined_rules(db: Session = Depends(get_db)):
    """
    Get list of predefined rules

    These are built-in rules that don't need LLM conversion. They are seeded
    into the rules table at startup, so status and timestamps are the stored ones.
    """
    predefined_ids = [rule.id for rule in get_predefined_rules()]
    rules = db.query(Rule).filter(Rule.id.in_(predefined_ids)).order_by(Rule.id).all()
    return [_to_response(r) for r in rules]


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    rule: RuleCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new correlation rule

    Security:
    - Rate limited per IP (handled by middleware)
    - Strict schema validation (Pydantic)
    - No code execution (only whitelisted operators)
    """
    # Check if rule already exists (predefined ids stay reserved even if the row was deleted)
    existing = db.query(Rule).filter(Rule.id == rule.id).first()
    if existing or get_predefined_rule(rule.id):
        raise HTTPException(status_code=409, detail=f"Rule '{rule.id}' already exists")

    # Get client IP for tracking (None behind some proxies/test clients)
    client_ip = request.client.host if request.client else None

    # Create rule model
    db_rule = Rule(
        id=rule.id,
        version=1,
        status=RuleStatus.active,
        natural_language=rule.natural_language,
        trigger=rule.trigger.model_dump(),
        joins=[j.model_dump(mode="json") for j in rule.joins],
        window_seconds=rule.window_seconds,
        emit=rule.emit.model_dump(),
        created_by=client_ip
    )

    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)

    logger.info(f"Created rule {rule.id}")

    return _to_response(db_rule)


@router.get("", response_model=List[RuleResponse])
async def list_rules(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all rules

    Query params:
    - status: Filter by status (active, inactive, draft)
    """
    query = db.query(Rule)

    if status:
        try:
            status_enum = RuleStatus[status]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query = query.filter(Rule.status == status_enum)

    return [_to_response(r) for r in query.order_by(Rule.id).all()]


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: str, db: Session = Depends(get_db)):
    """Get a specific rule by ID"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if rule:
        return _to_response(rule)

    raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """Delete a rule"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found")

    db.delete(rule)
    db.commit()

    logger.info(f"Deleted rule {rule_id}")

    return None