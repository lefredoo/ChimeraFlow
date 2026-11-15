"""
Predefined rules, loaded from `<DATA_DIR>/rules/*.json` (one file per rule).

The files are validated when this module is first imported (application
startup), so an invalid file stops the server instead of failing later.
Their `natural_language` and `emit.template` texts are business data, not
interface text.
"""
from pathlib import Path
from typing import List, Optional

from config import DATA_DIR
from engine.rule_files import PredefinedRule, load_rule_files

RULES_DIR = Path(DATA_DIR) / "rules"

PREDEFINED_RULES: List[PredefinedRule] = load_rule_files(RULES_DIR)

# Rules whose file says `"status": "inactive"`: seeded but never executed. Empty
# when every shipped rule is expressible in the DSL.
INACTIVE_PREDEFINED_IDS = frozenset(
    rule.id for rule in PREDEFINED_RULES if rule.status == "inactive"
)


def get_predefined_rules() -> List[PredefinedRule]:
    """Get the predefined rules, sorted by id."""
    return PREDEFINED_RULES


def get_predefined_rule(rule_id: str) -> Optional[PredefinedRule]:
    """Get a predefined rule by id, or None when there is none."""
    for rule in PREDEFINED_RULES:
        if rule.id == rule_id:
            return rule
    return None
