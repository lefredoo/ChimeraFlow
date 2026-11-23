"""
Integration tests against a real Redis: rate limiter storage, LLM budget counter, alert cooldown.

They run only when REDIS_TEST_URL is set (CI sets it; locally:
`docker run --rm -p 6390:6379 redis:7-alpine`, then
`REDIS_TEST_URL=redis://localhost:6390/15`). Without it they are skipped, see
tests/conftest.py. The URL must name a dedicated database index other than 0:
that database is flushed before and after every test, and nothing else is.
"""
import asyncio
import json
import os
import time
from typing import Iterator, List, Optional
from urllib.parse import urlparse

import pytest
from redis import Redis as SyncRedis
from redis.asyncio import Redis as AsyncRedis

import config
from api.rate_limit import client_ip, limiter
from engine.alerts import COOLDOWN_KEY, RedisCooldownStore
from engine.llm_client import LlmReply, estimate_reservation_usd
from engine.nl_budget import MICROUSD_PER_USD, SPEND_KEY, RedisSpendStore
from engine.nl_to_rule import NLBudgetExceeded, NLRuleService, NLSettings, build_messages
from slowapi import Limiter
from tests.test_nl_to_rule import TEXT, VALID_DRAFT

pytestmark = pytest.mark.redis

RULES_URL = "/api/v1/rules"
CONCURRENT_CALLS = 20
ADMITTED_CALLS = 5


@pytest.fixture
def redis_url() -> Iterator[str]:
    """URL of the dedicated test database, flushed before and after the test."""
    url = os.environ["REDIS_TEST_URL"]
    database = urlparse(url).path.lstrip("/")
    if not database.isdigit() or int(database) == 0:
        pytest.fail("REDIS_TEST_URL must name a dedicated database index other than 0 (e.g. redis://host:6379/15)")
    client = SyncRedis.from_url(url)
    client.flushdb()
    yield url
    client.flushdb()
    client.close()


@pytest.fixture
def sync_redis(redis_url: str) -> Iterator[SyncRedis]:
    client = SyncRedis.from_url(redis_url)
    yield client
    client.close()


def _use_redis_limiter(monkeypatch: pytest.MonkeyPatch, redis_url: str) -> None:
    """Point the application limiter at Redis, built the way production builds it (storage_uri)."""
    fresh = Limiter(key_func=client_ip, storage_uri=redis_url, key_style="endpoint")
    monkeypatch.setattr(limiter, "_storage", fresh._storage)
    monkeypatch.setattr(limiter, "_limiter", fresh._limiter)


def _rule_body(rule_id: str) -> dict:
    from engine.predefined_rules import get_predefined_rule

    body = get_predefined_rule("r_low_stock").model_dump(mode="json")
    body["id"] = rule_id
    return body


class TestRateLimiterOnRedis:
    def test_should_return_429_when_the_limit_is_exceeded_on_redis(self, api_client, redis_url, monkeypatch):
        monkeypatch.setattr(config, "RATE_LIMIT_PER_IP", 2)
        _use_redis_limiter(monkeypatch, redis_url)

        responses = [api_client.post(RULES_URL, json=_rule_body(f"r_redis_{i}")) for i in range(3)]

        assert [response.status_code for response in responses] == [201, 201, 429]
        assert 1 <= int(responses[2].headers["Retry-After"]) <= config.RATE_LIMIT_WINDOW_SECONDS

    def test_should_keep_counters_in_redis_with_an_expiry(self, api_client, redis_url, sync_redis, monkeypatch):
        monkeypatch.setattr(config, "RATE_LIMIT_PER_IP", 2)
        _use_redis_limiter(monkeypatch, redis_url)

        api_client.post(RULES_URL, json=_rule_body("r_redis_ttl"))

        keys = sync_redis.keys("*")
        assert len(keys) == 1
        assert 0 < sync_redis.ttl(keys[0]) <= config.RATE_LIMIT_WINDOW_SECONDS

    def test_should_share_the_counter_between_two_limiter_instances_when_both_use_redis(
        self, api_client, redis_url, monkeypatch
    ):
        monkeypatch.setattr(config, "RATE_LIMIT_PER_IP", 2)
        _use_redis_limiter(monkeypatch, redis_url)
        first = [api_client.post(RULES_URL, json=_rule_body(f"r_redis_a{i}")).status_code for i in range(2)]

        # A second worker has its own limiter object and connection, but the same Redis
        _use_redis_limiter(monkeypatch, redis_url)
        second = api_client.post(RULES_URL, json=_rule_body("r_redis_b")).status_code

        assert (first, second) == ([201, 201], 429)

class GatedLlm:
    """LLM stand-in that holds every call until released, so that reservations overlap."""

    def __init__(self, cost_usd: float) -> None:
        self.cost_usd = cost_usd
        self.gate = asyncio.Event()
        self.entered = 0

    async def complete(self, messages, *, model: Optional[str] = None, timeout: Optional[float] = None) -> LlmReply:
        self.entered += 1
        await self.gate.wait()
        return LlmReply(content=json.dumps(VALID_DRAFT), cost_usd=self.cost_usd)


def _micro(amount_usd: float) -> int:
    return round(amount_usd * MICROUSD_PER_USD)


async def _spent_micro_usd(client: AsyncRedis) -> int:
    raw = await client.get(SPEND_KEY)
    return 0 if raw is None else int(raw)


class TestSpendBudgetOnRedis:
    async def test_should_replace_the_reservation_by_the_real_cost_when_a_conversion_succeeds(self, redis_url):
        client = AsyncRedis.from_url(redis_url)
        try:
            reservation = estimate_reservation_usd(build_messages(TEXT, "fr"))
            real_cost = reservation / 4
            llm = GatedLlm(cost_usd=real_cost)
            llm.gate.set()
            settings = NLSettings(api_key="k", base_url="http://litellm.test", model="m", budget_usd=5.0)
            service = NLRuleService(settings, llm, RedisSpendStore(client))

            await service.convert(TEXT, "fr")

            assert await _spent_micro_usd(client) == _micro(real_cost)
            assert await client.ttl(SPEND_KEY) == -1  # no expiry: the budget survives a restart
        finally:
            await client.aclose()

    async def test_should_not_exceed_the_cap_when_reservations_are_concurrent(self, redis_url):
        client = AsyncRedis.from_url(redis_url)
        try:
            reservation = estimate_reservation_usd(build_messages(TEXT, "fr"))
            # spent_before < cap admits a call: 0, r, 2r, 3r, 4r are below 4.5r, 5r is not
            budget_usd = reservation * (ADMITTED_CALLS - 0.5)
            llm = GatedLlm(cost_usd=reservation)
            settings = NLSettings(api_key="k", base_url="http://litellm.test", model="m", budget_usd=budget_usd)
            service = NLRuleService(settings, llm, RedisSpendStore(client))

            tasks: List[asyncio.Task] = [
                asyncio.create_task(service.convert(TEXT, "fr")) for _ in range(CONCURRENT_CALLS)
            ]
            # Release the admitted calls only once every other call has been refused,
            # so that all the reservations are held at the same time
            deadline = time.monotonic() + 10
            while sum(task.done() for task in tasks) < CONCURRENT_CALLS - ADMITTED_CALLS:
                assert time.monotonic() < deadline, "the refused calls did not finish"
                await asyncio.sleep(0.01)
            held_micro = await _spent_micro_usd(client)
            llm.gate.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)

            refused = [result for result in results if isinstance(result, NLBudgetExceeded)]
            assert (llm.entered, len(refused)) == (ADMITTED_CALLS, CONCURRENT_CALLS - ADMITTED_CALLS)
            # Refused calls gave their reservation back: only the admitted ones are counted
            assert held_micro == ADMITTED_CALLS * _micro(reservation)
            assert await _spent_micro_usd(client) == ADMITTED_CALLS * _micro(reservation)
        finally:
            await client.aclose()

    async def test_should_add_atomically_when_many_increments_run_at_once(self, redis_url):
        client = AsyncRedis.from_url(redis_url)
        try:
            store = RedisSpendStore(client)

            totals = await asyncio.gather(*(store.add_spent_usd(0.01) for _ in range(50)))

            assert sorted(round(total * 100) for total in totals) == list(range(1, 51))
            assert await store.get_spent_usd() == pytest.approx(0.5)
        finally:
            await client.aclose()


class TestAlertCooldownOnRedis:
    async def test_should_grant_the_first_acquire_only_when_within_the_cooldown(self, redis_url):
        client = AsyncRedis.from_url(redis_url)
        try:
            store = RedisCooldownStore(client)

            first = await store.acquire(60)
            second = await store.acquire(60)

            assert (first, second) == (True, False)
            assert 0 < await client.ttl(COOLDOWN_KEY) <= 60
        finally:
            await client.aclose()

    async def test_should_grant_a_single_acquire_when_workers_race(self, redis_url):
        client = AsyncRedis.from_url(redis_url)
        try:
            store = RedisCooldownStore(client)

            granted = await asyncio.gather(*(store.acquire(60) for _ in range(20)))

            assert granted.count(True) == 1
        finally:
            await client.aclose()

    async def test_should_grant_again_when_the_cooldown_has_expired(self, redis_url):
        client = AsyncRedis.from_url(redis_url)
        try:
            store = RedisCooldownStore(client)
            assert await store.acquire(1) is True

            await asyncio.sleep(1.2)

            assert await store.acquire(1) is True
        finally:
            await client.aclose()
