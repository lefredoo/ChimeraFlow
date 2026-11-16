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


def seed_predefined_rules(db: Session, restore_status: bool = False) -> None:
    """Insert or update the predefined rules (idempotent).

    A missing rule is inserted with the status of its file.
    An existing rule whose shipped definition changed gets the new definition,
    a bumped version and the status of its file: that is how a release
    reactivates a rule it fixed. An unchanged rule keeps its stored status, so
    an operator's choice survives a restart.

    Args:
        db: Open session. The caller owns the session; this function commits.
        restore_status: Also put every rule back to the status of its file
            (demo reset), whether or not its definition changed.
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
            existing.status = RuleStatus[rule.status]
        elif restore_status:
            existing.status = RuleStatus[rule.status]

    db.commit()
    logger.info("Predefined rules seeded")
