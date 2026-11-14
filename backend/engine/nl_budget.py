"""
LLM spend tracking for the NL->rule conversion.

The hard budget cap (LITELLM_BUDGET_USD) is global: every conversion adds its
cost to one counter kept in Redis, so that all workers share it and a restart
does not reset it. The counter has no expiry; deleting the key resets the budget.
"""
import math
from typing import Any, Protocol

from redis.exceptions import RedisError

SPEND_KEY = "chimeraflow:nl:spent_microusd"
MICROUSD_PER_USD = 1_000_000


class SpendStoreError(Exception):
    """The spend counter could not be read or updated."""


class SpendStore(Protocol):
    """Where the cumulative LLM spend is kept."""

    async def get_spent_usd(self) -> float:
        """Return the total spent so far, in USD."""

    async def add_spent_usd(self, amount_usd: float) -> None:
        """Add an amount to the total spent, in USD."""


class RedisSpendStore:
    """Spend counter in Redis, stored as an integer number of micro-dollars.

    An integer counter (INCRBY) is atomic and has no floating-point drift.
    """

    def __init__(self, client: Any) -> None:
        """Create the store.

        Args:
            client: A `redis.asyncio.Redis` client (anything with async `get` and `incrby`).
        """
        self._client = client

    async def get_spent_usd(self) -> float:
        """Return the total spent so far, in USD.

        Raises:
            SpendStoreError: If Redis fails or holds an invalid value.
        """
        try:
            raw = await self._client.get(SPEND_KEY)
            return 0.0 if raw is None else int(raw) / MICROUSD_PER_USD
        except (RedisError, ValueError) as exc:
            raise SpendStoreError("Cannot read the LLM spend counter") from exc

    async def add_spent_usd(self, amount_usd: float) -> None:
        """Add an amount to the total spent (rounded up to a micro-dollar).

        Raises:
            SpendStoreError: If Redis fails.
        """
        try:
            await self._client.incrby(SPEND_KEY, math.ceil(amount_usd * MICROUSD_PER_USD))
        except RedisError as exc:
            raise SpendStoreError("Cannot update the LLM spend counter") from exc
