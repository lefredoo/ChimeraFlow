"""
API tests: explanation, stable correlations, `since`, alert e-mail, normalization
sandbox, live stream and demo reset.
"""
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

import config
from api import correlation_stream
from engine import alerts
from models.base import SessionLocal
from models.rule import Correlation, Rule, RuleExecution, RuleStatus
from tests.cooldown_store import MemoryCooldownStore
from tests.factories import make_access_record, make_excel_record, make_whatsapp_record

EXECUTE_URL = "/api/v1/correlations/execute"
CORRELATIONS_URL = "/api/v1/correlations"
STREAM_URL = "/api/v1/correlations/stream"
NORMALIZE_URL = "/api/v1/normalize"
RESET_URL = "/api/v1/demo/reset"
RULES_URL = "/api/v1/rules"


@pytest.fixture
def fake_sources(monkeypatch):
    """In-memory records standing in for the file connectors (external boundary)."""
    records = {
        "whatsapp": [make_whatsapp_record()],
        "access": [make_access_record(qty_stock=5)],
        "excel": [make_excel_record(7500)],
    }

    async def fetch_all_records():
        return records

    monkeypatch.setattr("api.correlations._fetch_all_records", fetch_all_records)
    return records


class Resend:
    """Scripted Resend provider on a mock transport."""

    def __init__(self, status=200):
        self.status = status
        self.bodies = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        return httpx.Response(self.status, json={})


@pytest.fixture
def resend(monkeypatch) -> Resend:
    provider = Resend()
    monkeypatch.setattr(alerts, "_TRANSPORT", httpx.MockTransport(provider.handler))
    monkeypatch.setattr(alerts, "RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(config, "ALERT_EMAIL_FROM", "alerts@example.test")
    monkeypatch.setattr(config, "ALERT_EMAIL_TO", ("ops@example.test",))
    monkeypatch.setattr(config, "ALERT_EMAIL_COOLDOWN_SECONDS", 300)
    monkeypatch.setattr(alerts, "get_cooldown_store", lambda: MemoryCooldownStore())
    return provider


def _execute(client, **params):
    return client.post(EXECUTE_URL, params=params)


# --- explanation -----------------------------------------------------------------------------


def test_should_return_the_explanation_when_listing_correlations(api_client, fake_sources):
    _execute(api_client, rule_ids="r_low_stock")

    explanation = api_client.get(CORRELATIONS_URL).json()[0]["explanation"]

    assert explanation["trigger"]["entity"] == {"raw": "ciment 50kg", "norm": "ciment 50 kg"}
    assert [(j["source"], j["method"]) for j in explanation["joins"]] == [("access", "exact"), ("excel", "exact")]
    assert explanation["joins"][0]["where"][0]["actual"] == 5


def test_should_return_a_null_explanation_when_the_row_predates_the_column(api_client, fake_sources):
    _execute(api_client, rule_ids="r_low_stock")
    with SessionLocal() as db:
        db.query(Correlation).update({Correlation.explanation: None})
        db.commit()

    assert api_client.get(CORRELATIONS_URL).json()[0]["explanation"] is None


# --- stable correlations and `since` ---------------------------------------------------------


def test_should_keep_ids_and_detection_time_when_executing_twice(api_client, fake_sources):
    _execute(api_client)
    first = {c["id"]: c["detected_at"] for c in api_client.get(CORRELATIONS_URL).json()}

    _execute(api_client)

    assert {c["id"]: c["detected_at"] for c in api_client.get(CORRELATIONS_URL).json()} == first


def test_should_report_no_new_correlation_when_executing_twice(api_client, fake_sources):
    first = _execute(api_client).json()
    second = _execute(api_client).json()

    assert (first["new_correlations"] > 0, second["new_correlations"]) == (True, 0)


def test_should_delete_a_correlation_when_it_is_no_longer_found(api_client, fake_sources):
    _execute(api_client, rule_ids="r_low_stock")
    fake_sources["access"][:] = [make_access_record(qty_stock=50)]

    _execute(api_client, rule_ids="r_low_stock")

    assert api_client.get(CORRELATIONS_URL, params={"rule_id": "r_low_stock"}).json() == []


def test_should_filter_by_detection_time_when_since_is_given(api_client, fake_sources):
    _execute(api_client)
    detected = datetime.fromisoformat(api_client.get(CORRELATIONS_URL).json()[0]["detected_at"])
    before = (detected - timedelta(seconds=1)).replace(tzinfo=timezone.utc)
    after = (detected + timedelta(seconds=1)).replace(tzinfo=timezone.utc)

    newer = api_client.get(CORRELATIONS_URL, params={"since": before.isoformat()}).json()
    none = api_client.get(CORRELATIONS_URL, params={"since": after.isoformat()}).json()

    assert (len(newer) > 0, none) == (True, [])


def test_should_reject_since_when_it_is_not_a_date(api_client):
    assert api_client.get(CORRELATIONS_URL, params={"since": "yesterday"}).status_code == 422


# --- alert e-mail -----------------------------------------------------------------------------


def test_should_send_one_digest_when_an_execution_finds_new_warnings(api_client, fake_sources, resend):
    _execute(api_client)

    assert len(resend.bodies) == 1
    assert "Stock bas" in resend.bodies[0]["text"]


def test_should_not_send_again_when_the_next_execution_finds_nothing_new(api_client, fake_sources, resend):
    _execute(api_client)
    _execute(api_client)

    assert len(resend.bodies) == 1


def test_should_not_send_when_only_info_correlations_are_found(api_client, fake_sources, resend):
    fake_sources["excel"][:] = [make_excel_record(20000)]

    found = _execute(api_client, rule_ids="r_high_value_order").json()["correlations_found"]

    assert (found, resend.bodies) == (1, [])


def test_should_not_send_when_the_feature_is_not_configured(api_client, fake_sources, monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", None)
    calls = []
    monkeypatch.setattr(alerts, "_TRANSPORT", httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200)))

    _execute(api_client)

    assert calls == []


def test_should_answer_the_request_when_the_provider_fails(api_client, fake_sources, resend):
    resend.status = 500

    response = _execute(api_client)

    assert response.status_code == 200
    assert response.json()["status"] == "success"


# --- normalization sandbox -----------------------------------------------------------------------


def test_should_require_a_token_when_calling_the_sandbox(anonymous_client):
    assert anonymous_client.post(NORMALIZE_URL, json={"text": "ciment"}).status_code == 401


def test_should_return_forms_and_scores_when_comparing_names(api_client):
    body = api_client.post(
        NORMALIZE_URL,
        json={"text": "Ciment50kg", "compare_with": ["ciment 50 kg", "Ciment-colle 25 kg", "tuyau PVC"]},
    ).json()

    assert (body["norm"], body["tokens"], body["numbers"]) == ("ciment 50 kg", ["cement", "50", "kg"], ["50"])
    assert [(c["matched"], c["method"]) for c in body["comparisons"]] == [
        (True, "exact"),
        (False, None),
        (False, None),
    ]


def test_should_report_a_token_match_when_a_name_is_partial(api_client):
    body = api_client.post(
        NORMALIZE_URL, json={"text": "tuyau PVC", "compare_with": ["Tuyau PVC Ø 32mm (barre 6m)"]}
    ).json()

    assert (body["comparisons"][0]["matched"], body["comparisons"][0]["method"]) == (True, "token")


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": "x" * 201},
        {"text": "ciment", "compare_with": ["x"] * 21},
        {"text": "ciment", "compare_with": ["x" * 201]},
    ],
)
def test_should_reject_the_request_when_the_sandbox_input_is_out_of_bounds(api_client, body):
    assert api_client.post(NORMALIZE_URL, json=body).status_code == 422


# --- live stream ------------------------------------------------------------------------------


@pytest.fixture
def short_stream(monkeypatch):
    monkeypatch.setattr(correlation_stream, "STREAM_MAX_SECONDS", 0.3)
    monkeypatch.setattr(correlation_stream, "STREAM_POLL_SECONDS", 0.05)


def _read_stream(client, **headers) -> str:
    with client.stream("GET", STREAM_URL, headers=headers) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        return "".join(response.iter_text())


def test_should_require_a_token_when_opening_the_stream(anonymous_client):
    assert anonymous_client.get(STREAM_URL).status_code == 401


def test_should_open_with_ready_and_close_with_end_when_nothing_happens(api_client, short_stream):
    body = _read_stream(api_client)

    assert body.startswith("retry: 3000\n\nevent: ready\n")
    assert body.rstrip().endswith("event: end\ndata: {}")


def test_should_replay_stored_correlations_when_last_event_id_is_given(api_client, fake_sources, short_stream):
    _execute(api_client, rule_ids="r_low_stock")

    body = _read_stream(api_client, **{"Last-Event-ID": "0"})

    assert "event: correlation" in body
    assert "Stock bas" in body


def test_should_send_only_later_correlations_when_resuming_after_the_last_one(api_client, fake_sources, short_stream):
    _execute(api_client, rule_ids="r_low_stock")
    last_id = api_client.get(CORRELATIONS_URL).json()[0]["id"]

    body = _read_stream(api_client, **{"Last-Event-ID": str(last_id)})

    assert "event: correlation" not in body


def test_should_start_from_now_when_there_is_no_last_event_id(api_client, fake_sources, short_stream):
    _execute(api_client, rule_ids="r_low_stock")

    assert "event: correlation" not in _read_stream(api_client)


def test_should_ignore_last_event_id_when_it_is_not_a_number(api_client, fake_sources, short_stream):
    _execute(api_client, rule_ids="r_low_stock")

    assert "event: correlation" not in _read_stream(api_client, **{"Last-Event-ID": "abc; drop"})


def test_should_refuse_when_too_many_streams_are_open(api_client, monkeypatch):
    monkeypatch.setattr(correlation_stream, "MAX_CONCURRENT_STREAMS", 0)

    response = api_client.get(STREAM_URL)

    assert (response.status_code, response.json()["detail"]["code"]) == (429, "stream_limit_reached")


# --- demo reset -------------------------------------------------------------------------------


def test_should_require_a_token_when_resetting_the_demo(anonymous_client):
    assert anonymous_client.post(RESET_URL).status_code == 401


def test_should_delete_correlations_and_executions_when_resetting_the_demo(api_client, fake_sources):
    _execute(api_client)

    body = api_client.post(RESET_URL).json()

    with SessionLocal() as db:
        remaining = (db.query(Correlation).count(), db.query(RuleExecution).count())
    assert body["correlations_deleted"] > 0 and body["executions_deleted"] > 0
    assert remaining == (0, 0)


def test_should_restore_predefined_rules_when_resetting_the_demo(api_client):
    with SessionLocal() as db:
        db.get(Rule, "r_low_stock").status = RuleStatus.inactive
        db.delete(db.get(Rule, "r_stock_replenish"))
        db.commit()

    api_client.post(RESET_URL)

    statuses = {r["id"]: r["status"] for r in api_client.get(f"{RULES_URL}/predefined").json()}
    assert statuses["r_low_stock"] == "active"
    assert statuses["r_stock_replenish"] == "active"


def test_should_keep_custom_rules_when_resetting_the_demo(api_client):
    custom = api_client.get(f"{RULES_URL}/r_low_stock").json()
    custom.update(id="r_custom", natural_language="Règle personnalisée de démonstration.")
    api_client.post(RULES_URL, json=custom)

    api_client.post(RESET_URL)

    assert api_client.get(f"{RULES_URL}/r_custom").status_code == 200
