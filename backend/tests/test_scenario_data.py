"""
Integration test on the shipped synthetic files (data/): every predefined rule
must find something, so that the demo shows each of them at work.
"""
from collections import Counter

import pytest

from engine.predefined_rules import get_predefined_rules

EXECUTE_URL = "/api/v1/correlations/execute"
CORRELATIONS_URL = "/api/v1/correlations"

ACTIVE_RULE_IDS = sorted(rule.id for rule in get_predefined_rules() if rule.status == "active")


@pytest.fixture
def executed(api_client):
    """Execute every active rule on the real data files and return the stored correlations."""
    summary = api_client.post(EXECUTE_URL).json()
    correlations = api_client.get(CORRELATIONS_URL, params={"limit": 1000}).json()
    return summary, correlations


def test_should_execute_the_five_predefined_rules_without_failure_when_running_on_the_shipped_data(executed):
    summary, _ = executed

    assert (summary["rules_executed"], summary["rules_failed"]) == (5, 0)
    assert ACTIVE_RULE_IDS == [
        "r_high_value_order", "r_low_stock", "r_payment_received", "r_price_comparison", "r_stock_replenish",
    ]


@pytest.mark.parametrize("rule_id", ACTIVE_RULE_IDS)
def test_should_find_at_least_one_correlation_when_executing_a_rule_on_the_shipped_data(executed, rule_id):
    _, correlations = executed

    assert Counter(c["rule_id"] for c in correlations)[rule_id] >= 1


def _messages(correlations, rule_id):
    return [c["message"] for c in correlations if c["rule_id"] == rule_id]


def test_should_correlate_the_four_spellings_of_ciment_when_stock_is_low(executed):
    _, correlations = executed

    products = {
        c["explanation"]["trigger"]["entity"]["norm"]
        for c in correlations
        if c["rule_id"] == "r_low_stock" and "ciment" in c["explanation"]["trigger"]["entity"]["norm"]
    }

    assert products == {"ciment 50 kg"}


def test_should_correlate_a_partial_name_when_the_message_is_shorter_than_the_catalog_name(executed):
    _, correlations = executed

    methods = {
        (c["explanation"]["trigger"]["entity"]["raw"], j["method"])
        for c in correlations
        for j in c["explanation"]["joins"]
        if c["rule_id"] == "r_high_value_order"
    }

    assert ("perceuse 500W", "token") in methods


def test_should_flag_a_price_gap_above_ten_percent_when_comparing_stock_and_supplier_prices(executed):
    _, correlations = executed

    gaps = [
        condition["gap_pct"]
        for c in correlations
        if c["rule_id"] == "r_price_comparison"
        for condition in c["explanation"]["joins"][0]["where"]
    ]

    assert gaps and all(gap > 10 for gap in gaps)


def test_should_correlate_the_successful_payment_but_not_the_pending_one_when_the_same_order_is_paid_twice(executed):
    _, correlations = executed

    amounts = [m for m in _messages(correlations, "r_payment_received") if "Ciment 50 kg" in m]

    assert any("15000.0 XAF" in m for m in amounts)
    assert not any("7500.0 XAF" in m for m in amounts)


def test_should_recommend_replenishment_only_for_products_below_15_in_stock(executed):
    _, correlations = executed

    stocks = [
        condition["actual"]
        for c in correlations
        if c["rule_id"] == "r_stock_replenish"
        for condition in c["explanation"]["trigger"]["where"]
    ]

    assert stocks and all(stock < 15 for stock in stocks)


def test_should_correlate_both_products_when_a_message_asks_for_two(executed):
    _, correlations = executed

    asked = {
        c["explanation"]["trigger"]["entity"]["raw"]
        for c in correlations
        if c["rule_id"] == "r_low_stock" and "wa-10" in {p["record_id"] for p in c["provenance"]}
    }

    assert asked == {"ciment 50 kg", "perceuse 500W"}
