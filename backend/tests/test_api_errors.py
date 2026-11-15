"""
Error bodies: a stable code and a short English message, no interpolated user text.
"""
from tests.test_api_correlations import CORRELATIONS_URL, RULES_URL


def _detail(response) -> dict:
    return response.json()["detail"]


def test_should_return_code_when_rule_is_not_found(api_client):
    response = api_client.get(f"{RULES_URL}/r_absent")

    assert response.status_code == 404
    assert _detail(response)["code"] == "rule_not_found"


def test_should_not_echo_the_rule_id_when_rule_is_not_found(api_client):
    response = api_client.get(f"{RULES_URL}/r_secret_id")

    assert "r_secret_id" not in response.text


def test_should_return_code_when_deleting_an_unknown_rule(api_client):
    response = api_client.delete(f"{RULES_URL}/r_absent")

    assert response.status_code == 404
    assert _detail(response)["code"] == "rule_not_found"


def test_should_return_code_when_rule_already_exists(api_client):
    body = api_client.get(f"{RULES_URL}/r_low_stock").json()

    response = api_client.post(RULES_URL, json=body)

    assert response.status_code == 409
    assert _detail(response)["code"] == "rule_already_exists"


def test_should_return_code_when_status_filter_is_invalid(api_client):
    response = api_client.get(RULES_URL, params={"status": "bogus"})

    assert response.status_code == 400
    assert _detail(response)["code"] == "invalid_status"


def test_should_return_code_when_severity_filter_is_invalid(api_client):
    response = api_client.get(CORRELATIONS_URL, params={"severity": "bogus"})

    assert response.status_code == 400
    assert _detail(response)["code"] == "invalid_severity"


def test_should_return_code_when_source_is_unknown(api_client):
    response = api_client.get("/api/v1/sources/bogus/health")

    assert response.status_code == 404
    assert _detail(response)["code"] == "source_not_found"
