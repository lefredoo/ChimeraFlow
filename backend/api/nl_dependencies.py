"""
FastAPI dependencies of the NL->rule endpoint.

Settings and spend store are separate dependencies so tests can replace each
external boundary (environment, Redis) on its own.
"""
from functools import lru_cache
from typing import Optional

from fastapi import Depends

import config
from engine.llm_client import LiteLLMClient
from engine.nl_budget import RedisSpendStore, SpendStore
from engine.nl_to_rule import NLRuleService, NLSettings, nl_settings_from_config

REDIS_TIMEOUT_SECONDS = 2


@lru_cache
def _redis_spend_store() -> Optional[RedisSpendStore]:
    """Create the Redis spend store once (None when REDIS_URL is not set, i.e. in tests)."""
    if config.REDIS_URL is None:
        return None
    from redis.asyncio import Redis

    client = Redis.from_url(
        config.REDIS_URL,
        socket_timeout=REDIS_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
    )
    return RedisSpendStore(client)


def get_nl_settings() -> Optional[NLSettings]:
    """Feature settings, None when the feature is not fully configured."""
    return nl_settings_from_config()


def get_spend_store() -> Optional[SpendStore]:
    """Cumulative LLM spend counter."""
    return _redis_spend_store()


def get_nl_service(
    settings: Optional[NLSettings] = Depends(get_nl_settings),
    spend_store: Optional[SpendStore] = Depends(get_spend_store),
) -> Optional[NLRuleService]:
    """The conversion service, or None when the feature is disabled."""
    if settings is None:
        return None
    return NLRuleService(settings, LiteLLMClient(settings.llm), spend_store)
