"""
Seed predefined rules into the rules table.

Correlations and executions reference rules.id with a foreign key, so every
rule that can be executed must exist as a row.
"""
import logging

from sqlalchemy.orm import Session

from engine.predefined_rules import get_predefined_rules
from engine.rule_files import PredefinedRule
from .rule import Rule, RuleStatus

logger = logging.getLogger(__name__)


def _definition(rule: PredefinedRule) -> dict:
    """Serialize the rule columns that make up its definition."""
    return {
        "natural_language": rule.natural_language,
        "trigger": rule.trigger.model_dump(),
        "joins": [j.model_dump(mode="json") for j in rule.joins],
        "window_seconds": rule.window_seconds,
        "emit": rule.emit.model_dump(),
    }


def seed_predefined_rules(db: Session) -> None:
    """Insert or update the predefined rules (idempotent).

    A missing rule is inserted with the status of its file.
    An existing rule gets its definition refreshed and its version bumped when
    it changed; its status is kept so an operator's choice survives a restart.

    Args:
        db: Open session. The caller owns the session; this function commits.
    """
    for rule in get_predefined_rules():
        definition = _definition(rule)
        existing = db.get(Rule, rule.id)

        if existing is None:
            db.add(Rule(
                id=rule.id, version=1, status=RuleStatus[rule.status], **definition
            ))
            continue

        if any(getattr(existing, column) != value for column, value in definition.items()):
            for column, value in definition.items():
                setattr(existing, column, value)
            existing.version += 1

    db.commit()
    logger.info("Predefined rules seeded")
