"""
Demo reset: POST /api/v1/demo/reset

Puts the shared demo back in its shipped state: every correlation and
execution is deleted and the predefined rules get their shipped definition and
status again (a deleted predefined rule comes back). Rules created through the
API are kept. Rate limited per IP like the other mutations.
"""
import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from api.rate_limit import limiter, mutation_limit
from models.base import get_db
from models.rule import Correlation, RuleExecution
from models.seed import seed_predefined_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/reset")
@limiter.limit(mutation_limit)
def reset_demo(request: Request, db: Session = Depends(get_db)):
    """Delete correlations and executions and restore the predefined rules.

    Returns:
        Number of correlations and executions deleted.
    """
    correlations = db.query(Correlation).delete(synchronize_session=False)
    executions = db.query(RuleExecution).delete(synchronize_session=False)
    # Commits, so the deletions and the restored rules are one transaction
    seed_predefined_rules(db, restore_status=True)
    logger.info("Demo reset: %d correlations, %d executions deleted", correlations, executions)
    return {"correlations_deleted": correlations, "executions_deleted": executions}
