"""
Rule management API endpoints
POST /rules, GET /rules, DELETE /rules/{id}
"""
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from api.errors import (
    INVALID_STATUS,
    RULE_ALREADY_EXISTS,
    RULE_NOT_FOUND,
    api_error,
)
from api.nl_dependencies import get_nl_service
from api.rate_limit import limiter, mutation_limit, nl_limit
from models.base import get_db
from models.rule import Rule, RuleStatus
from schemas.rule import (
    NaturalLanguageToRuleRequest,
    NaturalLanguageToRuleResponse,
    RuleCreate,
    RuleResponse,
)
from engine.nl_to_rule import NLError, NLFeatureDisabled, NLRuleService
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


def _predefined_responses(db: Session) -> List[RuleResponse]:
    """Stored predefined rules (status and timestamps as seeded), sorted by id."""
    predefined_ids = [rule.id for rule in get_predefined_rules()]
    rules = db.query(Rule).filter(Rule.id.in_(predefined_ids)).order_by(Rule.id).all()
    return [_to_response(r) for r in rules]


@router.get("/predefined", response_model=List[RuleResponse])
def list_predefined_rules(db: Session = Depends(get_db)):
    """
    Get list of predefined rules

    These are built-in rules that don't need LLM conversion. They are loaded from
    data/rules/*.json and seeded into the rules table at startup, so status and
    timestamps are the stored ones.
    """
    return _predefined_responses(db)


@router.post("/from-text", response_model=NaturalLanguageToRuleResponse)
@limiter.limit(nl_limit)
async def create_rule_from_text(
    payload: NaturalLanguageToRuleRequest,
    request: Request,
    db: Session = Depends(get_db),
    service: Optional[NLRuleService] = Depends(get_nl_service),
):
    """
    Convert a natural language description into a draft rule (not stored)

    The client reviews the draft, then sends it to POST /rules to store it.

    Security:
    - Rate limited per IP, stricter than the other mutations (each call can spend LLM budget)
    - The text is passed to the model as data, never as instructions
    - The answer is validated against the rule schema; nothing is executed

    Errors carry a stable `code` and `fallback_rules`: the predefined rules,
    to offer when the conversion is unavailable.
    """
    try:
        if service is None:
            raise NLFeatureDisabled()
        conversion = await service.convert(payload.text, payload.language)
    except NLError as error:
        predefined = await run_in_threadpool(_predefined_responses, db)
        fallback = [rule.model_dump(mode="json") for rule in predefined]
        raise api_error(
            error.status_code,
            error.code,
            error.message,
            fallback_rules=fallback,
            provider_retries=error.provider_retries,
        ) from error

    return NaturalLanguageToRuleResponse(
        rule=conversion.rule, retries=conversion.retries, provider_retries=conversion.provider_retries
    )


@router.post("", response_model=RuleResponse, status_code=201)
@limiter.limit(mutation_limit)
def create_rule(
    rule: RuleCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new correlation rule

    Security:
    - Rate limited per IP (slowapi, Redis)
    - Strict schema validation (Pydantic)
    - No code execution (only whitelisted operators)
    """
    # Check if rule already exists (predefined ids stay reserved even if the row was deleted)
    existing = db.query(Rule).filter(Rule.id == rule.id).first()
    if existing or get_predefined_rule(rule.id):
        raise api_error(409, RULE_ALREADY_EXISTS, "Rule already exists")

    # Create rule model (the client IP is personal data: it is not stored)
    db_rule = Rule(
        id=rule.id,
        version=1,
        status=RuleStatus.active,
        natural_language=rule.natural_language,
        trigger=rule.trigger.model_dump(),
        joins=[j.model_dump(mode="json") for j in rule.joins],
        window_seconds=rule.window_seconds,
        emit=rule.emit.model_dump()
    )

    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)

    logger.info(f"Created rule {rule.id}")

    return _to_response(db_rule)


@router.get("", response_model=List[RuleResponse])
def list_rules(
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
            raise api_error(400, INVALID_STATUS, "Invalid status filter")
        query = query.filter(Rule.status == status_enum)

    return [_to_response(r) for r in query.order_by(Rule.id).all()]


@router.get("/{rule_id}", response_model=RuleResponse)
def get_rule(rule_id: str, db: Session = Depends(get_db)):
    """Get a specific rule by ID"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if rule:
        return _to_response(rule)

    raise api_error(404, RULE_NOT_FOUND, "Rule not found")


@router.delete("/{rule_id}", status_code=204)
@limiter.limit(mutation_limit)
def delete_rule(rule_id: str, request: Request, db: Session = Depends(get_db)):
    """Delete a rule (rate limited per IP)"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()

    if not rule:
        raise api_error(404, RULE_NOT_FOUND, "Rule not found")

    db.delete(rule)
    db.commit()

    logger.info(f"Deleted rule {rule_id}")

    return None