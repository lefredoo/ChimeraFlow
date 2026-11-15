"""
Tests of the alert e-mail digest. The HTTP client is the only boundary: it
runs on an httpx MockTransport, so nothing reaches the network.
"""
import asyncio
import json
import logging

import httpx
import pytest

from redis.exceptions import ConnectionError as RedisConnectionError

import config
from engine import alerts
from engine.alerts import AlertItem, AlertSettings, CooldownStoreError, RedisCooldownStore
from tests.cooldown_store import MemoryCooldownStore

SETTINGS = AlertSettings(
    api_key="re_test_key",
    sender="alerts@example.test",
    recipients=("ops@example.test",),
    cooldown_seconds=300,
)
ITEMS = [
    AlertItem("r_low_stock", "warning", "Stock bas : Ciment 50 kg"),
    AlertItem("r_price_comparison", "error", "Écart de prix : Perceuse"),
]


class Provider:
    """Scripted Resend: answers with the given statuses in order, records the requests."""

    def __init__(self, *statuses):
        self.statuses = list(statuses)
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.statuses.pop(0), json={"id": "x"})


@pytest.fixture
def provider(monkeypatch) -> Provider:
    scripted = Provider(200)
    monkeypatch.setattr(alerts, "_TRANSPORT", httpx.MockTransport(scripted.handler))
    monkeypatch.setattr(alerts, "RETRY_DELAY_SECONDS", 0)
    return scripted


def _enable(monkeypatch):
    monkeypatch.setattr(config, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(config, "ALERT_EMAIL_FROM", "alerts@example.test")
    monkeypatch.setattr(config, "ALERT_EMAIL_TO", ("ops@example.test",))
    monkeypatch.setattr(config, "ALERT_EMAIL_COOLDOWN_SECONDS", 300)


def _use_cooldown(monkeypatch, store):
    monkeypatch.setattr(alerts, "get_cooldown_store", lambda: store)


class FakeRedis:
    """Records the SET calls; answers like Redis (True when set, None when the key exists)."""

    def __init__(self, existing=False, failing=False):
        self.existing = existing
        self.failing = failing
        self.calls = []

    async def set(self, key, value, nx=False, ex=None):
        if self.failing:
            raise RedisConnectionError("down")
        self.calls.append((key, nx, ex))
        return None if self.existing else True


def test_should_post_one_digest_to_resend_when_items_are_given(provider):
    sent = asyncio.run(alerts.send_digest(SETTINGS, ITEMS))

    body = json.loads(provider.requests[0].content)
    assert sent is True
    assert len(provider.requests) == 1
    assert provider.requests[0].headers["Authorization"] == "Bearer re_test_key"
    assert (body["from"], body["to"]) == ("alerts@example.test", ["ops@example.test"])
    assert body["subject"] == "ChimeraFlow : 2 nouvelles alertes"


def test_should_send_nothing_when_there_are_no_items(provider):
    sent = asyncio.run(alerts.send_digest(SETTINGS, []))

    assert (sent, provider.requests) == (False, [])


def test_should_escape_html_and_strip_control_characters_when_a_message_comes_from_a_source():
    hostile = AlertItem("r_x", "warning", "<script>alert(1)</script>\r\nBcc: evil@example.test\x00")

    _, text, html_body = alerts.build_digest([hostile])

    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body
    assert "\r" not in text and "\x00" not in text
    assert "\nBcc:" not in text


def test_should_truncate_a_long_message_when_building_the_digest():
    _, text, _ = alerts.build_digest([AlertItem("r_x", "info", "x" * 5000)])

    assert len(text) < 600


def test_should_list_at_most_50_items_when_the_digest_is_large():
    items = [AlertItem("r_x", "warning", f"message {n}") for n in range(60)]

    subject, text, _ = alerts.build_digest(items)

    assert text.count("[Avertissement]") == 50
    assert "10 autre(s)" in text
    assert "60" in subject


def test_should_use_the_singular_subject_when_there_is_one_item():
    subject, _, _ = alerts.build_digest(ITEMS[:1], "en")

    assert subject == "ChimeraFlow: 1 new alert"


def test_should_retry_once_when_the_provider_answers_a_server_error(provider):
    provider.statuses = [503, 200]

    sent = asyncio.run(alerts.send_digest(SETTINGS, ITEMS))

    assert (sent, len(provider.requests)) == (True, 2)


def test_should_not_retry_when_the_provider_rejects_the_request(provider):
    provider.statuses = [422]

    sent = asyncio.run(alerts.send_digest(SETTINGS, ITEMS))

    assert (sent, len(provider.requests)) == (False, 1)


def test_should_return_false_when_the_network_fails(monkeypatch):
    def refuse(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    monkeypatch.setattr(alerts, "_TRANSPORT", httpx.MockTransport(refuse))
    monkeypatch.setattr(alerts, "RETRY_DELAY_SECONDS", 0)

    assert asyncio.run(alerts.send_digest(SETTINGS, ITEMS)) is False


def test_should_not_log_recipients_or_content_when_sending(provider, caplog):
    caplog.set_level(logging.DEBUG)

    asyncio.run(alerts.send_digest(SETTINGS, ITEMS))

    assert "ops@example.test" not in caplog.text
    assert "re_test_key" not in caplog.text
    assert "Stock bas" not in caplog.text


def test_should_be_disabled_when_one_setting_is_missing(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(config, "ALERT_EMAIL_TO", ())

    assert alerts.alert_settings_from_config() is None


def test_should_read_the_settings_when_all_three_are_set(monkeypatch):
    _enable(monkeypatch)

    assert alerts.alert_settings_from_config() == SETTINGS


def test_should_not_expose_the_secrets_when_settings_are_printed():
    assert "re_test_key" not in repr(SETTINGS)
    assert "ops@example.test" not in repr(SETTINGS)


def test_should_send_nothing_when_dispatching_without_settings(provider):
    asyncio.run(alerts.dispatch_alerts(ITEMS))

    assert provider.requests == []


def test_should_be_disabled_when_the_cooldown_is_missing(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(config, "ALERT_EMAIL_COOLDOWN_SECONDS", None)

    assert alerts.alert_settings_from_config() is None


def test_should_send_one_digest_when_dispatching_twice_within_the_cooldown(provider, monkeypatch):
    _enable(monkeypatch)
    store = MemoryCooldownStore()
    _use_cooldown(monkeypatch, store)
    provider.statuses = [200, 200]

    asyncio.run(alerts.dispatch_alerts(ITEMS))
    asyncio.run(alerts.dispatch_alerts(ITEMS))

    assert (len(provider.requests), store.windows) == (1, [300, 300])


def test_should_send_nothing_when_there_is_no_cooldown_store(provider, monkeypatch):
    _enable(monkeypatch)
    _use_cooldown(monkeypatch, None)

    asyncio.run(alerts.dispatch_alerts(ITEMS))

    assert provider.requests == []


def test_should_send_nothing_when_the_cooldown_store_fails(provider, monkeypatch):
    _enable(monkeypatch)
    _use_cooldown(monkeypatch, MemoryCooldownStore(failing=True))

    asyncio.run(alerts.dispatch_alerts(ITEMS))

    assert provider.requests == []


def test_should_set_the_key_with_nx_and_expiry_when_acquiring_the_cooldown():
    client = FakeRedis()

    granted = asyncio.run(RedisCooldownStore(client).acquire(300))

    assert (granted, client.calls) == (True, [(alerts.COOLDOWN_KEY, True, 300)])


def test_should_refuse_when_the_cooldown_key_already_exists():
    assert asyncio.run(RedisCooldownStore(FakeRedis(existing=True)).acquire(300)) is False


def test_should_raise_a_store_error_when_redis_is_down_on_acquire():
    with pytest.raises(CooldownStoreError):
        asyncio.run(RedisCooldownStore(FakeRedis(failing=True)).acquire(300))


def test_should_require_the_cooldown_when_the_alert_is_enabled(monkeypatch):
    monkeypatch.delenv("ALERT_EMAIL_COOLDOWN_SECONDS", raising=False)

    with pytest.raises(ValueError, match="ALERT_EMAIL_COOLDOWN_SECONDS"):
        config._alert_cooldown(True)


def test_should_leave_the_cooldown_unset_when_the_alert_is_disabled(monkeypatch):
    monkeypatch.delenv("ALERT_EMAIL_COOLDOWN_SECONDS", raising=False)

    assert config._alert_cooldown(False) is None


@pytest.mark.parametrize("raw", ["59", "0", "-5", "abc", "1.5"])
def test_should_reject_an_invalid_cooldown_when_reading_the_setting(monkeypatch, raw):
    monkeypatch.setenv("ALERT_EMAIL_COOLDOWN_SECONDS", raw)

    with pytest.raises(ValueError, match="ALERT_EMAIL_COOLDOWN_SECONDS"):
        config._alert_cooldown(True)


def test_should_read_the_cooldown_when_it_is_at_least_60_seconds(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_COOLDOWN_SECONDS", "60")

    assert config._alert_cooldown(True) == 60


def test_should_only_keep_warning_and_error_when_selecting_items():
    correlations = [
        {"rule_id": "r_a", "severity": "info", "message": "a"},
        {"rule_id": "r_b", "severity": "warning", "message": "b"},
        {"rule_id": "r_c", "severity": "error", "message": "c"},
    ]

    assert [item.rule_id for item in alerts.select_alert_items(correlations)] == ["r_b", "r_c"]


@pytest.mark.parametrize("raw", ["not-an-address", "a@b.test,broken", "a@b.test\nBcc: x@y.test"])
def test_should_reject_malformed_recipients_when_parsing_the_setting(raw):
    with pytest.raises(ValueError, match="ALERT_EMAIL_TO"):
        config._parse_alert_recipients(raw)


def test_should_reject_more_than_5_recipients_when_parsing_the_setting():
    with pytest.raises(ValueError, match="at most 5"):
        config._parse_alert_recipients(",".join(f"u{n}@example.test" for n in range(6)))
