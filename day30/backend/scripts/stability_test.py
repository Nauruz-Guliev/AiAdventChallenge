"""Нагрузочная проверка: N параллельных запросов, отчёт по успеху/429/503 и латентностям."""

from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx


def one_request(base_url: str, key: str, timeout: float) -> tuple[int, float]:
    started = time.perf_counter()
    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            headers={"X-API-Key": key},
            json={
                "messages": [{"role": "user", "content": "Назови столицу Франции одним словом."}],
                "max_tokens": 24,
            },
            timeout=timeout,
        )
        status = response.status_code
    except httpx.HTTPError:
        status = 0
    return status, (time.perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--key", default="change-me-local-key")
    parser.add_argument("--requests", type=int, default=24)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(
            pool.map(lambda _: one_request(args.url, args.key, args.timeout), range(args.requests))
        )

    statuses: dict[int, int] = {}
    latencies = []
    for status, latency in results:
        statuses[status] = statuses.get(status, 0) + 1
        latencies.append(latency)

    latencies.sort()
    total = len(results)
    print(f"Всего запросов: {total}")
    for status, count in sorted(statuses.items()):
        label = "сеть/таймаут" if status == 0 else str(status)
        print(f"  {label}: {count} ({count / total:.0%})")
    print(f"  латентность p50: {statistics.median(latencies):.0f} ms")
    p95 = latencies[min(total - 1, int(total * 0.95))]
    print(f"  латентность p95: {p95:.0f} ms")
    print(f"  ok: {statuses.get(200, 0)}/{total}")


if __name__ == "__main__":
    main()
