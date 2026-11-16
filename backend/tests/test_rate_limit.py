"""
Per-IP rate limiting of the mutation endpoints.

The limiter uses memory storage here because BACKEND_NODE_ENV=test (explicit
test configuration, see config.RATE_LIMIT_STORAGE_URI). The limit values are
lowered per test through the configuration the limit callables read.
"""
import os
import subprocess
import sys
from ipaddress import ip_network
from pathlib import Path

import pytest
from limits.errors import StorageError
from starlette.requests import Request

import config
from api.rate_limit import UNKNOWN_CLIENT, client_ip, limiter
from engine.predefined_rules import get_predefined_rule

RULES_URL = "/api/v1/rules"
EXECUTE_URL = "/api/v1/correlations/execute"
FROM_TEXT_URL = "/api/v1/rules/from-text"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _rule_body(rule_id: str) -> dict:
    body = get_predefined_rule("r_low_stock").model_dump(mode="json")
    body["id"] = rule_id
    return body


def _request(peer, forwarded=None) -> Request:
    """Request from a peer; `forwarded` is one X-Forwarded-For value, or a list of header lines."""
    lines = [] if forwarded is None else [forwarded] if isinstance(forwarded, str) else forwarded
    headers = [(b"x-forwarded-for", line.encode()) for line in lines]
    scope = {"type": "http", "headers": headers, "client": None if peer is None else (peer, 5000)}
    return Request(scope)


@pytest.fixture
def limit_of_two(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMIT_PER_IP", 2)
    monkeypatch.setattr(config, "RATE_LIMIT_NL_PER_IP", 1)


@pytest.fixture
def trusted_proxy(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXIES", (ip_network("10.0.0.0/8"),))


class TestMutationLimits:
    def test_should_return_429_when_rule_creation_exceeds_the_limit(self, api_client, limit_of_two):
        statuses = [api_client.post(RULES_URL, json=_rule_body(f"r_rate_{i}")).status_code for i in range(3)]

        assert statuses == [201, 201, 429]

    def test_should_send_retry_after_when_limit_is_exceeded(self, api_client, limit_of_two):
        for i in range(2):
            api_client.post(RULES_URL, json=_rule_body(f"r_rate_{i}"))

        response = api_client.post(RULES_URL, json=_rule_body("r_rate_2"))

        assert 1 <= int(response.headers["Retry-After"]) <= config.RATE_LIMIT_WINDOW_SECONDS

    def test_should_return_stable_code_when_limit_is_exceeded(self, api_client, limit_of_two):
        for i in range(2):
            api_client.post(RULES_URL, json=_rule_body(f"r_rate_{i}"))

        response = api_client.post(RULES_URL, json=_rule_body("r_rate_2"))

        assert response.json() == {"detail": {"code": "rate_limit_exceeded", "message": "Too many requests"}}

    def test_should_not_store_the_rule_when_limit_is_exceeded(self, api_client, limit_of_two):
        for i in range(3):
            api_client.post(RULES_URL, json=_rule_body(f"r_rate_{i}"))

        assert api_client.get(f"{RULES_URL}/r_rate_2").status_code == 404

    def test_should_limit_deletions_with_one_counter_when_ids_differ(self, api_client, limit_of_two):
        statuses = [api_client.delete(f"{RULES_URL}/r_absent_{i}").status_code for i in range(3)]

        assert statuses == [404, 404, 429]

    def test_should_return_429_when_correlation_execution_exceeds_the_limit(self, api_client, limit_of_two):
        statuses = [
            api_client.post(EXECUTE_URL, params={"rule_ids": "r_absent"}).status_code for _ in range(3)
        ]

        assert statuses == [200, 200, 429]

    def test_should_keep_separate_counters_when_endpoints_differ(self, api_client, limit_of_two):
        for i in range(2):
            api_client.post(RULES_URL, json=_rule_body(f"r_rate_{i}"))

        response = api_client.post(EXECUTE_URL, params={"rule_ids": "r_absent"})

        assert response.status_code == 200

    def test_should_not_limit_read_endpoints_when_limit_is_reached(self, api_client, limit_of_two):
        statuses = [api_client.get(RULES_URL).status_code for _ in range(5)]

        assert statuses == [200] * 5

    def test_should_apply_a_stricter_limit_when_converting_text(self, api_client, limit_of_two):
        body = {"text": "Alerte-moi quand le stock de ciment est bas.", "language": "fr"}

        statuses = [api_client.post(FROM_TEXT_URL, json=body).status_code for _ in range(2)]

        assert statuses == [503, 429]

    def test_should_derive_the_text_limit_from_the_general_limit_when_not_configured(self):
        assert config.RATE_LIMIT_NL_PER_IP == 200  # 1000 (RATE_LIMIT_PER_IP of conftest.py) // 5

    def test_should_refuse_the_request_when_the_limiter_storage_fails(self, api_client, monkeypatch):
        def fail(*_args, **_kwargs):
            raise StorageError(ConnectionError("down"))

        monkeypatch.setattr(limiter.limiter, "hit", fail)

        response = api_client.post(RULES_URL, json=_rule_body("r_rate_x"))

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "rate_limit_unavailable"


class TestClientIp:
    def test_should_use_the_peer_when_no_proxy_is_trusted(self):
        assert client_ip(_request("10.0.0.1", forwarded="203.0.113.7")) == "10.0.0.1"

    def test_should_use_forwarded_address_when_peer_is_a_trusted_proxy(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1", forwarded="203.0.113.7")) == "203.0.113.7"

    def test_should_ignore_forwarded_header_when_peer_is_not_a_trusted_proxy(self, trusted_proxy):
        assert client_ip(_request("198.51.100.9", forwarded="203.0.113.7")) == "198.51.100.9"

    def test_should_not_trust_an_entry_written_by_the_client_when_proxy_appends_the_real_one(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1", forwarded="1.1.1.1, 203.0.113.7")) == "203.0.113.7"

    def test_should_skip_trusted_proxies_when_reading_the_chain_from_the_right(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1", forwarded="203.0.113.7, 10.0.0.2")) == "203.0.113.7"

    def test_should_use_the_peer_when_trusted_proxy_sends_no_header(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1")) == "10.0.0.1"

    def test_should_use_the_peer_when_forwarded_entry_is_not_an_ip_address(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1", forwarded="not-an-ip")) == "10.0.0.1"

    def test_should_use_the_peer_when_chain_holds_only_trusted_proxies(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1", forwarded="10.0.0.2, 10.0.0.3")) == "10.0.0.1"

    def test_should_read_the_last_header_line_first_when_forwarded_for_is_split_in_lines(self, trusted_proxy):
        request = _request("10.0.0.1", forwarded=["1.1.1.1", "203.0.113.7"])

        assert client_ip(request) == "203.0.113.7"

    def test_should_skip_trusted_proxies_of_the_last_line_when_forwarded_for_is_split_in_lines(self, trusted_proxy):
        request = _request("10.0.0.1", forwarded=["203.0.113.7", "10.0.0.2"])

        assert client_ip(request) == "203.0.113.7"

    def test_should_key_an_ipv6_client_by_its_64_prefix_when_the_peer_is_ipv6(self):
        assert client_ip(_request("2001:db8:1:2:aaaa:bbbb:cccc:dddd")) == "2001:db8:1:2::/64"

    def test_should_give_one_key_to_two_addresses_of_the_same_64_prefix(self):
        first = client_ip(_request("2001:db8:1:2::1"))
        second = client_ip(_request("2001:db8:1:2:ffff:ffff:ffff:ffff"))

        assert first == second

    def test_should_give_different_keys_to_two_64_prefixes(self):
        assert client_ip(_request("2001:db8:1:2::1")) != client_ip(_request("2001:db8:1:3::1"))

    def test_should_key_an_ipv6_client_by_its_64_prefix_when_forwarded_for_holds_an_ipv6_address(self, trusted_proxy):
        request = _request("10.0.0.1", forwarded="2001:db8:1:2:aaaa:bbbb:cccc:dddd")

        assert client_ip(request) == "2001:db8:1:2::/64"

    def test_should_read_an_ipv4_mapped_peer_as_ipv4_when_building_the_key(self):
        assert client_ip(_request("::ffff:203.0.113.7")) == "203.0.113.7"

    def test_should_read_an_ipv4_mapped_forwarded_entry_as_ipv4_when_building_the_key(self, trusted_proxy):
        assert client_ip(_request("10.0.0.1", forwarded="::ffff:203.0.113.7")) == "203.0.113.7"

    def test_should_trust_an_ipv4_mapped_peer_when_its_ipv4_address_is_a_trusted_proxy(self, trusted_proxy):
        assert client_ip(_request("::ffff:10.0.0.1", forwarded="203.0.113.7")) == "203.0.113.7"

    def test_should_return_a_placeholder_when_the_connection_has_no_client(self):
        assert client_ip(_request(None)) == UNKNOWN_CLIENT

    def test_should_return_the_raw_peer_when_it_is_not_an_ip_address(self, trusted_proxy):
        assert client_ip(_request("testclient", forwarded="203.0.113.7")) == "testclient"


class TestConfiguration:
    @staticmethod
    def _import_config(**changes):
        env = {**os.environ}
        for name, value in changes.items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        return subprocess.run(
            [sys.executable, "-c", "import config"],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
        )

    def test_should_fail_fast_when_rate_limit_per_ip_is_missing(self):
        result = self._import_config(RATE_LIMIT_PER_IP=None)

        assert result.returncode != 0
        assert "RATE_LIMIT_PER_IP" in result.stderr

    def test_should_fail_fast_when_rate_limit_window_is_missing(self):
        result = self._import_config(RATE_LIMIT_WINDOW_SECONDS=None)

        assert result.returncode != 0
        assert "RATE_LIMIT_WINDOW_SECONDS" in result.stderr

    def test_should_fail_fast_when_rate_limit_is_not_positive(self):
        result = self._import_config(RATE_LIMIT_PER_IP="0")

        assert result.returncode != 0
        assert "at least 1" in result.stderr

    def test_should_fail_fast_when_trusted_proxies_entry_is_invalid(self):
        result = self._import_config(TRUSTED_PROXIES="10.0.0.1, bogus")

        assert result.returncode != 0
        assert "TRUSTED_PROXIES" in result.stderr

    @pytest.mark.parametrize("budget", ["nan", "inf", "-inf", "0", "-1", "abc"])
    def test_should_fail_fast_when_the_llm_budget_is_not_a_finite_positive_number(self, budget):
        result = self._import_config(LITELLM_BUDGET_USD=budget)

        assert result.returncode != 0
        assert "LITELLM_BUDGET_USD" in result.stderr

    def test_should_accept_the_llm_budget_when_it_is_a_finite_positive_number(self):
        result = self._import_config(LITELLM_BUDGET_USD="5.0")

        assert result.returncode == 0

    def test_should_accept_trusted_proxies_when_entries_are_addresses_and_networks(self):
        result = self._import_config(TRUSTED_PROXIES="10.0.0.1, 172.16.0.0/12")

        assert result.returncode == 0

    def test_should_disable_nl_conversion_when_litellm_api_key_is_empty(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from engine.nl_to_rule import nl_settings_from_config; "
                "print(nl_settings_from_config() is None)",
            ],
            cwd=BACKEND_DIR,
            env={
                **os.environ,
                "LITELLM_API_KEY": "",
                "LITELLM_BASE_URL": "http://litellm.test",
                "LITELLM_MODEL": "test-model",
                "LITELLM_BUDGET_USD": "5",
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True"
