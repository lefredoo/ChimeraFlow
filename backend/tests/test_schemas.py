"""
Tests for the declarative rule schema (strict validation, no code execution)
"""
import copy

import pytest
from pydantic import ValidationError

from schemas.rule import RuleCreate

VALID_RULE = {
    "id": "r_test",
    "natural_language": "Alerte quand le stock Access est bas pour un produit demandé.",
    "trigger": {"source": "whatsapp", "entity": "product"},
    "joins": [
        {
            "source": "access",
            "table": "Articles",
            "on": {"entity": "product", "field": "designation"},
            "where": [{"field": "qty_stock", "op": "lt", "value": 10}],
        }
    ],
    "window_seconds": 604800,
    "emit": {"severity": "warning", "template": "{product}: stock {access.qty_stock}"},
}


def _rule_with(**overrides):
    rule = copy.deepcopy(VALID_RULE)
    rule.update(overrides)
    return rule


def test_should_accept_rule_when_definition_is_valid():
    rule = RuleCreate.model_validate(VALID_RULE)

    assert rule.id == "r_test"


def test_should_reject_rule_when_joins_are_empty():
    with pytest.raises(ValidationError):
        RuleCreate.model_validate(_rule_with(joins=[]))


def test_should_reject_rule_when_excel_join_has_no_sheet():
    excel_join = {"source": "excel", "on": {"entity": "product", "field": "Produit"}}

    with pytest.raises(ValidationError, match="sheet"):
        RuleCreate.model_validate(_rule_with(joins=[excel_join]))


def test_should_reject_rule_when_access_join_has_no_table():
    access_join = {"source": "access", "on": {"entity": "product", "field": "designation"}}

    with pytest.raises(ValidationError, match="table"):
        RuleCreate.model_validate(_rule_with(joins=[access_join]))


def test_should_reject_rule_when_operator_is_unknown():
    join = copy.deepcopy(VALID_RULE["joins"][0])
    join["where"] = [{"field": "qty_stock", "op": "regex", "value": ".*"}]

    with pytest.raises(ValidationError):
        RuleCreate.model_validate(_rule_with(joins=[join]))
