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


def _where_of_join(*conditions):
    join = copy.deepcopy(VALID_RULE["joins"][0])
    join["where"] = list(conditions)
    return _rule_with(joins=[join])


def test_should_accept_condition_on_trigger_record_when_value_is_literal():
    trigger = {
        "source": "access",
        "entity": "product",
        "where": [{"field": "qty_stock", "op": "lt", "value": 15}],
    }
    join = {"source": "whatsapp", "on": {"entity": "product", "field": "entities"}}

    rule = RuleCreate.model_validate(_rule_with(trigger=trigger, joins=[join]))

    assert rule.trigger.where[0].field == "qty_stock"


def test_should_accept_computed_comparison_when_ref_points_to_the_trigger():
    trigger = {"source": "access", "entity": "product"}
    join = {
        "source": "excel",
        "sheet": "Tarifs",
        "on": {"entity": "product", "field": "Produit"},
        "where": [{"field": "Prix_Unitaire", "op": "gt", "ref": "access.prix_achat", "tolerance_pct": 10}],
    }

    rule = RuleCreate.model_validate(_rule_with(trigger=trigger, joins=[join], emit={
        "severity": "warning", "template": "{product}: {access.prix_achat} / {excel.Prix_Unitaire}",
    }))

    assert rule.joins[0].where[0].tolerance_pct == 10


@pytest.mark.parametrize(
    "condition",
    [
        {"field": "qty_stock", "op": "lt"},
        {"field": "qty_stock", "op": "lt", "value": 10, "ref": "whatsapp.text"},
        {"field": "qty_stock", "op": "lt", "value": 10, "tolerance_pct": 10},
        {"field": "qty_stock", "op": "eq", "ref": "whatsapp.text", "tolerance_pct": 10},
        {"field": "qty_stock", "op": "in", "ref": "whatsapp.text"},
        {"field": "qty_stock", "op": "gt", "ref": "whatsapp.text", "tolerance_pct": -1},
        {"field": "qty_stock", "op": "gt", "ref": "whatsapp.text", "tolerance_pct": 1001},
        {"field": "qty_stock", "op": "gt", "ref": "whatsapp.text", "tolerance_pct": float("nan")},
        {"field": "qty_stock", "op": "gt", "ref": "text"},
        {"field": "qty_stock", "op": "gt", "ref": "whatsapp.text; drop"},
        {"field": "qty_stock", "op": "lt", "value": {"nested": 1}},
        {"field": "qty_stock", "op": "in", "value": 5},
        {"field": "qty_stock", "op": "lt", "value": "x" * 201},
        {"field": "qty_stock", "op": "in", "value": list(range(51))},
        {"field": "qty_stock", "op": "lt", "value": 10, "free_expression": "qty*2"},
        {"field": "", "op": "lt", "value": 10},
    ],
)
def test_should_reject_condition_when_it_is_malformed(condition):
    with pytest.raises(ValidationError):
        RuleCreate.model_validate(_where_of_join(condition))


def test_should_reject_reference_when_source_is_not_the_trigger_nor_an_earlier_join():
    condition = {"field": "qty_stock", "op": "gt", "ref": "excel.Prix_Unitaire"}

    with pytest.raises(ValidationError, match="neither the trigger nor an earlier join"):
        RuleCreate.model_validate(_where_of_join(condition))


def test_should_reject_reference_when_it_is_on_the_trigger():
    trigger = {
        "source": "whatsapp",
        "entity": "product",
        "where": [{"field": "text", "op": "eq", "ref": "whatsapp.author"}],
    }

    with pytest.raises(ValidationError, match="not allowed on the trigger"):
        RuleCreate.model_validate(_rule_with(trigger=trigger))


def test_should_reject_rule_when_a_column_is_unknown_to_its_source():
    condition = {"field": "invented", "op": "lt", "value": 1}

    with pytest.raises(ValidationError, match="unknown column 'invented'"):
        RuleCreate.model_validate(_where_of_join(condition))


def test_should_reject_rule_when_join_field_is_missing():
    join = copy.deepcopy(VALID_RULE["joins"][0])
    join["on"] = {"entity": "product"}

    with pytest.raises(ValidationError):
        RuleCreate.model_validate(_rule_with(joins=[join]))


@pytest.mark.parametrize(
    "template",
    [
        "{momo.phone}",
        "{momo.customer_name} a payé",
        "{access.invented}",
        "{excel.Prix_Unitaire}",
        "{unknown}",
    ],
)
def test_should_reject_template_when_placeholder_is_not_allowed(template):
    trigger = {"source": "momo", "entity": "product"}
    join = {"source": "whatsapp", "on": {"entity": "product", "field": "entities"}}

    with pytest.raises(ValidationError):
        RuleCreate.model_validate(
            _rule_with(trigger=trigger, joins=[join], emit={"severity": "info", "template": template})
        )


def test_should_reject_rule_when_template_is_longer_than_500_characters():
    with pytest.raises(ValidationError):
        RuleCreate.model_validate(_rule_with(emit={"severity": "info", "template": "x" * 501}))


def test_should_reject_rule_when_a_join_has_more_than_10_conditions():
    conditions = [{"field": "qty_stock", "op": "lt", "value": n} for n in range(11)]

    with pytest.raises(ValidationError):
        RuleCreate.model_validate(_where_of_join(*conditions))
