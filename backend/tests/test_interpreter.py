"""
Tests for the rule interpreter using in-memory unified records
"""
import pytest

from schemas.rule import RuleCreate
from engine.interpreter import RuleInterpreter, render_template
from engine.predefined_rules import get_predefined_rule
from mcp_servers.base import UnifiedRecord
from tests.factories import make_access_record, make_excel_record, make_whatsapp_record


def _whatsapp_record() -> UnifiedRecord:
    return UnifiedRecord(
        id="wa-5",
        source="whatsapp",
        source_ref="commandes_clients.txt#L5",
        timestamp="2026-11-02T11:08:00",
        lang="fr",
        entities=[{"type": "product", "raw": "ciment 50kg", "norm": "ciment 50 kg"}],
        payload={"author": "Client A", "text": "Bsr. Quel est le prix du ciment 50kg svp?"},
    )


def _access_record(qty_stock, date_modif="2026-11-01T00:00:00") -> UnifiedRecord:
    return UnifiedRecord(
        id="access-16",
        source="access",
        source_ref="STOCK_ZOBO.mdb#Articles#16",
        timestamp=date_modif,
        lang="fr",
        entities=[{"type": "product", "raw": "Ciment 50 kg", "norm": "ciment 50 kg"}],
        payload={"id": "16", "designation": "Ciment 50 kg", "qty_stock": qty_stock, "date_modif": date_modif},
    )


def _excel_record() -> UnifiedRecord:
    return UnifiedRecord(
        id="excel-15",
        source="excel",
        source_ref="tarifs_fournisseurs.xlsx#row17",
        timestamp="2026-10-31T00:00:00",
        lang="fr",
        entities=[{"type": "product", "raw": "Ciment 50 kg", "norm": "ciment 50 kg"}],
        payload={"Produit": "Ciment 50 kg", "Prix_Unitaire": 7500, "Date_MAJ": "2026-10-31T00:00:00"},
    )


def _run_low_stock(access_record: UnifiedRecord):
    rule = get_predefined_rule("r_low_stock")
    whatsapp = [_whatsapp_record()]
    all_records = {"whatsapp": whatsapp, "access": [access_record], "excel": [_excel_record()]}

    return RuleInterpreter().execute(rule, whatsapp, all_records)


def test_should_emit_correlation_when_stock_is_below_threshold():
    correlations = _run_low_stock(_access_record(qty_stock=5))

    assert len(correlations) == 1
    assert correlations[0]["rule_id"] == "r_low_stock"
    assert "stock: 5" in correlations[0]["message"]
    assert "prix: 7500" in correlations[0]["message"]


def test_should_list_every_contributing_record_when_correlation_is_emitted():
    correlation = _run_low_stock(_access_record(qty_stock=5))[0]

    assert [p["record_id"] for p in correlation["provenance"]] == ["wa-5", "access-16", "excel-15"]


def test_should_not_emit_correlation_when_stock_is_above_threshold():
    assert _run_low_stock(_access_record(qty_stock=50)) == []


def test_should_not_raise_when_where_compares_incompatible_types():
    assert _run_low_stock(_access_record(qty_stock="n/a")) == []


def test_should_not_emit_correlation_when_joined_record_is_outside_window():
    assert _run_low_stock(_access_record(qty_stock=5, date_modif="2026-09-01T00:00:00")) == []


def test_should_return_identical_messages_when_executed_twice():
    first = _run_low_stock(_access_record(qty_stock=5))
    second = _run_low_stock(_access_record(qty_stock=5))

    assert [c["message"] for c in first] == [c["message"] for c in second]


def _run_low_stock_with_prices(excel_records):
    rule = get_predefined_rule("r_low_stock")
    whatsapp = [make_whatsapp_record()]
    all_records = {
        "whatsapp": whatsapp,
        "access": [make_access_record(qty_stock=5)],
        "excel": excel_records,
    }

    return RuleInterpreter().execute(rule, whatsapp, all_records)


def test_should_pick_latest_price_at_or_before_trigger_when_duplicates_exist():
    # File order is deliberately not chronological: the future price comes first
    prices = [
        make_excel_record(9000, date_maj="2026-11-05T00:00:00", row=3),
        make_excel_record(7000, date_maj="2026-10-28T00:00:00", row=4),
        make_excel_record(7500, date_maj="2026-10-31T00:00:00", row=5),
    ]

    correlation = _run_low_stock_with_prices(prices)[0]

    assert "prix: 7500" in correlation["message"]
    assert correlation["provenance"][-1]["record_id"] == "excel-5"


def test_should_pick_closest_future_price_when_no_price_exists_before_trigger():
    prices = [
        make_excel_record(9000, date_maj="2026-11-06T00:00:00", row=3),
        make_excel_record(8000, date_maj="2026-11-03T00:00:00", row=4),
    ]

    correlation = _run_low_stock_with_prices(prices)[0]

    assert "prix: 8000" in correlation["message"]


def test_should_prefer_best_score_when_a_more_recent_record_matches_less_closely():
    prices = [
        make_excel_record(7500, date_maj="2026-10-30T00:00:00", row=3),
        make_excel_record(7800, date_maj="2026-11-01T00:00:00", produit="Ciment 50 kg sac", row=4),
    ]

    correlation = _run_low_stock_with_prices(prices)[0]

    assert "prix: 7500" in correlation["message"]


def test_should_keep_source_order_when_candidates_are_identical_in_score_and_time():
    prices = [
        make_excel_record(7500, row=3),
        make_excel_record(7600, row=4),
    ]

    correlation = _run_low_stock_with_prices(prices)[0]

    assert correlation["provenance"][-1]["record_id"] == "excel-3"


def test_should_not_match_when_product_size_differs():
    prices = [make_excel_record(6500, produit="Ciment 40 kg")]

    assert _run_low_stock_with_prices(prices) == []


def test_should_return_identical_correlations_when_executed_twice_with_same_inputs():
    prices = [make_excel_record(7500)]

    assert _run_low_stock_with_prices(prices) == _run_low_stock_with_prices(prices)


def test_should_not_set_detection_time_when_engine_emits_a_correlation():
    correlation = _run_low_stock_with_prices([make_excel_record(7500)])[0]

    assert "detected_at" not in correlation


def test_should_not_expand_braces_when_source_text_contains_a_placeholder():
    values = {"product": "{access.qty_stock}", "access": {"qty_stock": 5}}

    assert render_template("{product} / {access.qty_stock}", values) == "{access.qty_stock} / 5"


def test_should_not_expand_braces_when_payload_value_contains_a_placeholder():
    values = {"access": {"designation": "{access.qty_stock}", "qty_stock": 5}}

    assert render_template("{access.designation}", values) == "{access.qty_stock}"


def test_should_render_empty_text_when_placeholder_field_is_missing():
    assert render_template("stock [{access.qty_stock}]", {"access": {}}) == "stock []"


def test_should_render_empty_text_when_placeholder_source_is_missing():
    assert render_template("prix [{excel.Prix_Unitaire}]", {"product": "x"}) == "prix []"


# --- DSL extension: trigger conditions, computed gaps, entity joins, multi-entity, explanation ---

def _record(source, record_id, timestamp, payload, entities=()):
    return UnifiedRecord(
        id=record_id,
        source=source,
        source_ref=f"{source}#{record_id}",
        timestamp=timestamp,
        lang="fr",
        entities=[{"type": "product", "raw": raw, "norm": raw.lower()} for raw in entities],
        payload=payload,
    )


def _momo(status, record_id="momo-1", reference="Ciment 50 kg"):
    return _record(
        "momo", record_id, "2026-11-03T10:00:00",
        {"status": status, "amount": 7500, "currency": "XAF", "reference": reference},
        entities=[reference],
    )


def _whatsapp(*products, record_id="wa-1", timestamp="2026-11-03T08:00:00"):
    return _record("whatsapp", record_id, timestamp, {"author": "Client A", "text": "x"}, entities=products)


def _run(rule_id, triggers, **sources):
    rule = get_predefined_rule(rule_id)
    all_records = {rec.source: [] for rec in triggers}
    for name, records in sources.items():
        all_records[name] = records
    all_records.setdefault(rule.trigger.source, []).extend(triggers)
    return RuleInterpreter().execute(rule, triggers, all_records)


def test_should_correlate_only_successful_payments_when_trigger_has_a_status_condition():
    triggers = [_momo("SUCCESS", "momo-1"), _momo("PENDING", "momo-2")]

    correlations = _run("r_payment_received", triggers, whatsapp=[_whatsapp("ciment 50kg")])

    assert [c["provenance"][0]["record_id"] for c in correlations] == ["momo-1"]


def test_should_report_trigger_condition_values_when_a_payment_is_correlated():
    correlation = _run("r_payment_received", [_momo("SUCCESS")], whatsapp=[_whatsapp("ciment 50kg")])[0]

    where = correlation["explanation"]["trigger"]["where"]
    assert where == [
        {"field": "status", "op": "eq", "expected": "SUCCESS", "actual": "SUCCESS", "passed": True}
    ]


def test_should_match_the_entities_of_a_message_when_join_field_is_entities():
    correlation = _run("r_payment_received", [_momo("SUCCESS")], whatsapp=[_whatsapp("perceuse 500W", "ciment 50kg")])[0]

    join = correlation["explanation"]["joins"][0]
    assert (join["candidate"]["raw"], join["method"]) == ("ciment 50kg", "exact")


def _access(prix_achat, qty_stock=40, designation="Perceuse électrique 500W"):
    return _record(
        "access", "access-1", "2026-11-05T00:00:00",
        {"designation": designation, "qty_stock": qty_stock, "prix_achat": prix_achat},
        entities=[designation],
    )


def _excel(price, produit="Perceuse électrique 500W", record_id="excel-1"):
    return _record(
        "excel", record_id, "2026-11-04T00:00:00",
        {"Produit": produit, "Prix_Unitaire": price}, entities=[produit],
    )


@pytest.mark.parametrize(
    ("supplier_price", "expected"),
    [(46000, 0), (49500, 0), (49501, 1), (40500, 0), (40499, 1), (60000, 1)],
)
def test_should_flag_price_gap_only_when_it_exceeds_ten_percent(supplier_price, expected):
    correlations = _run(
        "r_price_comparison", [_access(45000)], excel=[_excel(supplier_price)]
    )

    assert len(correlations) == expected


def test_should_report_the_gap_when_price_comparison_matches():
    correlation = _run("r_price_comparison", [_access(45000)], excel=[_excel(60000)])[0]

    condition = correlation["explanation"]["joins"][0]["where"][0]
    assert (condition["gap_pct"], condition["expected"], condition["actual"]) == (33.333333, 45000, 60000)


def test_should_not_flag_a_gap_when_the_reference_price_is_zero():
    assert _run("r_price_comparison", [_access(0)], excel=[_excel(60000)]) == []


def test_should_not_flag_a_gap_when_the_reference_price_is_missing():
    assert _run("r_price_comparison", [_access(None)], excel=[_excel(60000)]) == []


def test_should_skip_a_candidate_whose_gap_is_small_when_another_one_exceeds_it():
    excel = [_excel(45500, record_id="excel-1"), _excel(60000, record_id="excel-2")]

    correlations = _run("r_price_comparison", [_access(45000)], excel=excel)

    assert [p["record_id"] for p in correlations[0]["provenance"]] == ["access-1", "excel-2"]


def test_should_recommend_replenishment_only_when_trigger_stock_is_below_threshold():
    kwargs = {"whatsapp": [_whatsapp("perceuse 500W", timestamp="2026-11-04T08:00:00")], "excel": [_excel(45000)]}

    low = _run("r_stock_replenish", [_access(45000, qty_stock=14)], **kwargs)
    enough = _run("r_stock_replenish", [_access(45000, qty_stock=15)], **kwargs)

    assert (len(low), len(enough)) == (1, 0)


def test_should_render_trigger_payload_fields_when_template_names_the_trigger_source():
    kwargs = {"whatsapp": [_whatsapp("perceuse 500W", timestamp="2026-11-04T08:00:00")], "excel": [_excel(45000)]}

    message = _run("r_stock_replenish", [_access(45000, qty_stock=8)], **kwargs)[0]["message"]

    assert message == "Réappro recommandé : Perceuse électrique 500W - stock actuel: 8, prix fournisseur: 45000 FCFA"


def test_should_correlate_every_product_of_a_message_when_it_carries_several():
    rule = get_predefined_rule("r_high_value_order")
    message = _whatsapp("perceuse 500W", "ciment 50 kg", "marteau")
    excel = [_excel(45000), _excel(7500, "Ciment 50 kg", "excel-2"), _excel(15000, "Marteau rivoir 500g", "excel-3")]

    correlations = RuleInterpreter().execute(rule, [message], {"whatsapp": [message], "excel": excel})

    assert [c["explanation"]["trigger"]["entity"]["raw"] for c in correlations] == ["perceuse 500W", "marteau"]


def test_should_correlate_a_product_once_when_a_message_repeats_it_in_other_words():
    message = _whatsapp("ciment 50kg", "Ciment 50 kg")

    correlations = _run("r_high_value_order", [message], excel=[_excel(20000, "Ciment 50 kg")])

    assert len(correlations) == 1


def test_should_explain_each_join_when_a_correlation_is_emitted():
    correlation = _run_low_stock(_access_record(qty_stock=5))[0]

    explanation = correlation["explanation"]
    assert explanation["trigger"]["entity"] == {"raw": "ciment 50kg", "norm": "ciment 50 kg"}
    assert [(j["source"], j["method"], j["score"]) for j in explanation["joins"]] == [
        ("access", "exact", 1.0),
        ("excel", "exact", 1.0),
    ]
    assert explanation["joins"][0]["where"] == [
        {"field": "qty_stock", "op": "lt", "expected": 10, "actual": 5, "passed": True}
    ]


def test_should_report_the_partial_method_when_a_name_is_contained_in_a_longer_one():
    kwargs = {"excel": [_excel(45000)]}

    correlation = _run("r_high_value_order", [_whatsapp("perceuse 500W")], **kwargs)[0]

    join = correlation["explanation"]["joins"][0]
    assert (join["method"], join["candidate"]["raw"]) == ("token", "Perceuse électrique 500W")
    assert 0.85 <= join["score"] < 1.0


def test_should_reject_a_reference_to_a_source_that_is_not_matched_yet():
    broken = get_predefined_rule("r_price_comparison").model_dump(mode="json", exclude={"status"})
    broken["joins"][0]["where"][0]["ref"] = "whatsapp.text"

    with pytest.raises(ValueError, match="neither the trigger nor an earlier join"):
        RuleCreate.model_validate(broken)
