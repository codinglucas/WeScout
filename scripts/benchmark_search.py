"""Time representative searches against the API (the "after" number in docs/benchmarks.md).

    uv run python scripts/benchmark_search.py                       # in-process (app + SQL)
    uv run python scripts/benchmark_search.py --url http://localhost:5000   # real HTTP

Same three searches as the legacy baseline. Each is run --warmup times (discarded) and then
--runs times; we report median and p95 in milliseconds.
"""

from __future__ import annotations

import argparse
import statistics
import time
from typing import Any

import httpx

SEARCHES: dict[str, dict[str, Any]] = {
    "LB, age<=23, value<=EUR15M": {"position": "lb", "max_age": 23, "max_value": 15_000_000},
    "CB, age<=21, value<=EUR10M": {"position": "cb", "max_age": 21, "max_value": 10_000_000},
    "ST, age<=25, value<=EUR30M": {"position": "st", "max_age": 25, "max_value": 30_000_000},
}


def _client(url: str | None) -> Any:
    if url:
        return httpx.Client(base_url=url, timeout=30)
    from fastapi.testclient import TestClient

    from wescout.api.main import app

    return TestClient(app)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=None)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    args = parser.parse_args()

    with _client(args.url) as client:
        print(f"mode={'http ' + args.url if args.url else 'in-process'} runs={args.runs}")
        print("| Search | Results | Median (ms) | p95 (ms) |")
        print("|---|---|---|---|")
        for label, params in SEARCHES.items():
            for _ in range(args.warmup):
                client.get("/api/players/search", params=params)
            times = []
            count = 0
            for _ in range(args.runs):
                t0 = time.perf_counter()
                r = client.get("/api/players/search", params=params)
                times.append((time.perf_counter() - t0) * 1000)
                count = r.json()["count"]
            times.sort()
            p95 = times[int(len(times) * 0.95) - 1]
            print(f"| {label} | {count} | {statistics.median(times):.1f} | {p95:.1f} |")


if __name__ == "__main__":
    main()
