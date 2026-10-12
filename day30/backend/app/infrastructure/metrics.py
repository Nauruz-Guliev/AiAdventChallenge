from __future__ import annotations

from collections import deque


class Metrics:
    def __init__(self, max_samples: int = 2000) -> None:
        self._counters: dict[str, int] = {}
        self._latencies: deque[float] = deque(maxlen=max_samples)

    def inc(self, name: str, amount: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + amount

    def observe(self, ms: float) -> None:
        self._latencies.append(ms)

    def percentile(self, p: float) -> float:
        if not self._latencies:
            return 0.0
        data = sorted(self._latencies)
        index = max(0, min(len(data) - 1, int((p / 100.0) * (len(data) - 1))))
        return data[index]

    def snapshot(self, extra: dict | None = None) -> dict:
        out: dict = dict(self._counters)
        out["latency_ms_p50"] = round(self.percentile(50), 2)
        out["latency_ms_p95"] = round(self.percentile(95), 2)
        out["samples"] = len(self._latencies)
        if extra:
            out.update(extra)
        return out
