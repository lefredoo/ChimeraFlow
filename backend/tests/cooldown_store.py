"""In-memory stand-in for the Redis alert cooldown (external boundary of the e-mail alert)."""
from typing import List

from engine.alerts import CooldownStoreError


class MemoryCooldownStore:
    """Grants the first `acquire` and refuses the following ones, like SET NX EX within the window."""

    def __init__(self, failing: bool = False) -> None:
        self.failing = failing
        self.granted = False
        self.windows: List[int] = []

    async def acquire(self, seconds: int) -> bool:
        if self.failing:
            raise CooldownStoreError("down")
        self.windows.append(seconds)
        if self.granted:
            return False
        self.granted = True
        return True
