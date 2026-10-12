from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class TokenBucket:
    capacity: float
    refill_per_sec: float
    tokens: float
    updated_at: float

    def allow(self, now: float, cost: float = 1.0) -> tuple[bool, float]:
        elapsed = max(0.0, now - self.updated_at)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        self.updated_at = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True, 0.0
        if self.refill_per_sec <= 0:
            return False, float("inf")
        return False, (cost - self.tokens) / self.refill_per_sec


class RateLimiter:
    def __init__(self, per_minute: int, burst: int) -> None:
        self._capacity = float(max(1, burst))
        self._refill = max(0.0, per_minute / 60.0)
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, identity: str, now: float) -> tuple[bool, int]:
        bucket = self._buckets.get(identity)
        if bucket is None:
            bucket = TokenBucket(self._capacity, self._refill, self._capacity, now)
            self._buckets[identity] = bucket
        allowed, retry = bucket.allow(now)
        if allowed:
            return True, 0
        return False, max(1, math.ceil(retry))
