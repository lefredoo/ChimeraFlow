"""
Tests for the rule interpreter using in-memory unified records
"""
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
