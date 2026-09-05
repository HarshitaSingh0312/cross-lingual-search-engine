"""Pulls real p50/p95/p99 latency, error rate, and cache hit rate for a load-test run
straight out of Prometheus (the same instance Grafana's dashboard reads from), instead of
relying on Locust's own client-side summary - this way the recorded numbers are the exact
histogram the running system produced, not a hand-copied or re-typed figure.

Usage: after a locust run finishes, run this with the same --run-time window:

    python collect_metrics.py --minutes 3 --handler /api/v1/search /api/v1/search/hybrid
"""

import argparse

import requests

PROMETHEUS_URL = "http://localhost:9090"


def query(promql: str) -> list[dict]:
    resp = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": promql}, timeout=10)
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    return result


def percentile(handler: str, quantile: float, window: str) -> float | None:
    promql = (
        f'histogram_quantile({quantile}, '
        f'sum(rate(http_request_duration_seconds_bucket{{handler="{handler}"}}[{window}])) by (le))'
    )
    result = query(promql)
    if not result:
        return None
    value = result[0]["value"][1]
    return None if value == "NaN" else float(value)


def error_rate(handler: str, window: str) -> float | None:
    promql = (
        f'sum(rate(http_requests_total{{handler="{handler}", status=~"5.."}}[{window}])) '
        f'/ sum(rate(http_requests_total{{handler="{handler}"}}[{window}]))'
    )
    result = query(promql)
    if not result:
        return None
    value = result[0]["value"][1]
    return None if value == "NaN" else float(value)


def cache_hit_rate(window: str) -> float | None:
    promql = (
        f'sum(rate(cache_requests_total{{result="hit"}}[{window}])) '
        f'/ sum(rate(cache_requests_total[{window}]))'
    )
    result = query(promql)
    if not result:
        return None
    value = result[0]["value"][1]
    return None if value == "NaN" else float(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, required=True, help="Length of the just-finished run")
    parser.add_argument("--handler", nargs="+", required=True, help="Route(s) to report, e.g. /api/v1/search")
    args = parser.parse_args()
    window = f"{max(1, round(args.minutes * 60))}s"

    for handler in args.handler:
        p50 = percentile(handler, 0.50, window)
        p95 = percentile(handler, 0.95, window)
        p99 = percentile(handler, 0.99, window)
        err = error_rate(handler, window)
        print(f"{handler}")
        print(f"  p50={p50*1000:.0f}ms  p95={p95*1000:.0f}ms  p99={p99*1000:.0f}ms" if p50 is not None else "  no data")
        print(f"  error_rate={err:.4f}" if err is not None else "  error_rate: no data")

    hit_rate = cache_hit_rate(window)
    print(f"cache_hit_rate={hit_rate:.4f}" if hit_rate is not None else "cache_hit_rate: no data")


if __name__ == "__main__":
    main()
