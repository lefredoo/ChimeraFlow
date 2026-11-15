"""
API tests: predefined rules seeded in the database, correlation execution,
foreign keys enforced (SQLite behaves like PostgreSQL), idempotent executions.
"""
import pytest

from engine.interpreter import RuleInterpreter
from engine.predefined_rules import INACTIVE_PREDEFINED_IDS, get_predefined_rule, get_predefined_rules
from models.base import SessionLocal, engine
from models.rule import Correlation, Rule, RuleExecution, RuleStatus
from models.seed import seed_predefined_rules
from tests.factories import make_access_record, make_excel_record, make_whatsapp_record

EXECUTE_URL = "/api/v1/correlations/execute"
CORRELATIONS_URL = "/api/v1/correlations"
RULES_URL = "/api/v1/rules"


@pytest.fixture
def fake_sources(monkeypatch):
    """Replace the file connectors (external boundary) by in-memory records."""
    records = {
        "whatsapp": [make_whatsapp_record()],
        "access": [make_access_record(qty_stock=5)],
        "excel": [make_excel_record(7500)],
    }

    async def fetch_all_records():
        return records

    monkeypatch.setattr("api.correlations._fetch_all_records", fetch_all_records)


def _count(model) -> int:
    with SessionLocal() as db:
        return db.query(model).count()


def test_should_enforce_foreign_keys_when_database_is_sqlite():
    with engine.connect() as connection:
        enabled = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()

    assert enabled == 1


def test_should_seed_every_predefined_rule_when_application_starts(api_client):
    ids = [rule["id"] for rule in api_client.get(f"{RULES_URL}/predefined").json()]

    assert ids == sorted(rule.id for rule in get_predefined_rules())


def test_should_seed_rules_with_the_status_of_their_file_when_application_starts(api_client):
    statuses = {rule["id"]: rule["status"] for rule in api_client.get(f"{RULES_URL}/predefined").json()}

    inactive = {rule_id for rule_id, status in statuses.items() if status == "inactive"}
    assert inactive == INACTIVE_PREDEFINED_IDS


def test_should_not_duplicate_rules_when_seeding_twice(api_client):
    with SessionLocal() as db:
        seed_predefined_rules(db)

    assert _count(Rule) == len(get_predefined_rules())


def test_should_keep_status_when_seeding_an_existing_rule(api_client):
    with SessionLocal() as db:
        db.get(Rule, "r_payment_received").status = RuleStatus.inactive
        db.commit()
        seed_predefined_rules(db)

    assert api_client.get(f"{RULES_URL}/r_payment_received").json()["status"] == "inactive"


def test_should_persist_correlations_when_executing_a_predefined_rule(api_client, fake_sources):
    response = api_client.post(EXECUTE_URL, params={"rule_ids": "r_low_stock"})

    assert response.status_code == 200
    assert response.json()["correlations_found"] == 1
    stored = api_client.get(CORRELATIONS_URL).json()
    assert [c["rule_id"] for c in stored] == ["r_low_stock"]
    assert "stock: 5" in stored[0]["message"]


def test_should_return_same_correlation_count_when_executing_twice(api_client, fake_sources):
    api_client.post(EXECUTE_URL)
    first = len(api_client.get(CORRELATIONS_URL).json())
    api_client.post(EXECUTE_URL)

    assert len(api_client.get(CORRELATIONS_URL).json()) == first > 0


def test_should_execute_only_active_rules_when_no_rule_ids_given(api_client, fake_sources):
    body = api_client.post(EXECUTE_URL).json()

    assert body["rules_executed"] == len(get_predefined_rules()) - len(INACTIVE_PREDEFINED_IDS)
    assert body["rules_failed"] == 0


def test_should_report_no_rules_when_requested_rule_is_inactive(api_client, fake_sources):
    with SessionLocal() as db:
        db.get(Rule, "r_payment_received").status = RuleStatus.inactive
        db.commit()

    body = api_client.post(EXECUTE_URL, params={"rule_ids": "r_payment_received"}).json()

    assert body["status"] == "no_rules"
    assert _count(Correlation) == 0


def test_should_reject_request_when_more_than_20_rule_ids_given(api_client):
    response = api_client.post(EXECUTE_URL, params={"rule_ids": [f"r_{i}" for i in range(21)]})

    assert response.status_code == 422


@pytest.mark.parametrize("limit", ["0", "-1", "1001"])
def test_should_reject_request_when_limit_is_out_of_bounds(api_client, limit):
    assert api_client.get(CORRELATIONS_URL, params={"limit": limit}).status_code == 422


def test_should_reject_rule_creation_when_id_matches_a_predefined_rule(api_client):
    body = get_predefined_rule("r_low_stock").model_dump(mode="json")

    assert api_client.post(RULES_URL, json=body).status_code == 409


def test_should_delete_correlations_when_their_rule_is_deleted(api_client, fake_sources):
    body = get_predefined_rule("r_low_stock").model_dump(mode="json")
    body["id"] = "r_custom_stock"
    api_client.post(RULES_URL, json=body)
    api_client.post(EXECUTE_URL, params={"rule_ids": "r_custom_stock"})

    deleted = api_client.delete(f"{RULES_URL}/r_custom_stock")

    assert deleted.status_code == 204
    assert api_client.get(CORRELATIONS_URL, params={"rule_id": "r_custom_stock"}).json() == []


def test_should_store_generic_error_when_a_rule_fails(api_client, fake_sources, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("secret detail from a source")

    monkeypatch.setattr(RuleInterpreter, "execute", fail)

    body = api_client.post(EXECUTE_URL, params={"rule_ids": "r_low_stock"}).json()

    with SessionLocal() as db:
        error = db.query(RuleExecution).one().error
    assert body["rules_failed"] == 1
    assert error == "Rule execution failed"


def test_should_keep_previous_correlations_when_a_rule_fails(api_client, fake_sources, monkeypatch):
    api_client.post(EXECUTE_URL, params={"rule_ids": "r_low_stock"})

    def fail(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(RuleInterpreter, "execute", fail)
    api_client.post(EXECUTE_URL, params={"rule_ids": "r_low_stock"})

    assert _count(Correlation) == 1
