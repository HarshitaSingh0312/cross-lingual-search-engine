# Load Test Results — Phase 12

**Tooling:** `backend/loadtest/locustfile.py` (Locust, weighted realistic query mix across
en/es/fr, mixed anonymous/logged-in traffic) against the local `docker compose` stack.
Percentiles are read back from Prometheus (`backend/loadtest/collect_metrics.py`), the same
histogram Grafana's dashboard uses — not Locust's own client-side timings — so the numbers
below are the real server-side measurement, not a client-side approximation.

**Environment:** local Docker Desktop, 12 CPUs allocated, CPU-only inference (no GPU) — not
yet the Render free-tier instance (Phase 15 isn't done). These numbers should be re-measured
once deployed; the *bottleneck analysis* below will still hold, but the actual millisecond
figures will very likely be worse on a smaller/shared production CPU, not better.

## What broke, in order

### 1. Baseline (before any fix): synchronous CPU-bound calls block the event loop

`retrieval_service.encode_query` (the embedding model), `HybridSearchService`'s cross-encoder
`.predict()`, and `hash_password`/`verify_password` (bcrypt) were all plain synchronous calls
made directly inside `async def` route handlers — nothing offloaded them off the single
FastAPI event loop.

| Concurrency | `/search` p50 / p95 / p99 | `/search/hybrid` p50 / p95 / p99 | cache hit rate |
|---|---|---|---|
| 1 user | 195ms / 888ms / 977ms | 7500ms / 9750ms / 9950ms* | 7% |
| 10 users | 167ms / 5175ms / 7435ms | 328ms / 8812ms / 10000ms* | 79% |
| 20 users | 42ms / 4133ms / 9175ms | 48ms / 8208ms / 9642ms | 95% |

\* saturated against the histogram's bucket ceiling at the time (see "Also fixed" below) —
the true value was higher than shown.

**Reading this:** median latency actually *drops* as concurrency rises — not because the
system got faster, but because the query mix is Zipfian (a few popular queries repeat across
more simulated users as the run progresses), so the cache absorbs more of the traffic. Tail
latency tells the real story: p95/p99 stay pinned at multi-second regardless of concurrency,
because a single slow request (an uncached search, a hybrid rerank) fully blocks the one
event loop, so every other concurrent request queues up behind it — this is the actual,
concrete "what breaks under load" finding this phase existed to produce.

### 2. First fix attempt: naive `asyncio.to_thread` — crashed the host

Wrapping the three blocking calls in bare `asyncio.to_thread(...)` (no thread-count limits)
looked like the obvious fix — get CPU-bound work off the event loop. Re-running the
concurrency=10 test instead produced **worse** tail latency (`/search/hybrid` p50 jumped to
37s) plus `RemoteDisconnected` errors, and within about a minute the entire Docker Desktop
engine stopped responding (`docker ps` returning 500s from its own API). All five compose
containers were later found exited (code 255) simultaneously — consistent with the whole
WSL2 VM restarting, not one container being individually OOM-killed.

**Root cause:** PyTorch's default behavior is to use *every available core* for a single
call's own intra-op matmuls. `to_thread` only controls how many Python-level threads run
concurrently — it does nothing to stop each of those threads from independently trying to
claim all 12 cores for its own inference call. Ten concurrent requests meant ten threads each
fighting for the same 12 cores, badly enough to destabilize the host. Backend logs from right
before the crash confirmed it directly: individual encode calls that normally take ~300ms had
slowed to 6-6.4 **seconds** each, from pure thread contention, immediately before the process
was killed.

### 3. Second attempt: pin `torch.set_num_threads(1)` — safe, but slower per call

Stopped the oversubscription, but went too far the other way: pinning every call to a single
thread strips out the intra-op parallelism a cross-encoder batch call actually benefits from.
A single, otherwise-uncontended hybrid search request went from ~4.6s (original, unrestricted
threads) to **19s** — safe from crashing, but a regression on the one number that matters most
for a single user.

### 4. Final fix: bound both dimensions to fit the real core budget

`torch.set_num_threads(4)` (each call gets some real parallelism) plus a shared
`asyncio.Semaphore` (`backend/app/services/retrieval_service.py::run_inference`) capping
concurrent inference calls to `cpu_count // 4` (3, on this 12-core machine) — so the two
numbers' product roughly matches the host's actual cores, instead of maximizing one while
zeroing the other. `HybridSearchService`'s cross-encoder call goes through the same
`run_inference` helper, so a burst of hybrid searches shares the same budget as plain
searches rather than each fanning out independently.

Result: a single hybrid request settled at ~8.1s (worse than the original 4.6s baseline, but
nowhere near the 19s single-thread regression), and — the actual point — **concurrency=10
survived without crashing Docker.** Under that same load, `/search` and `/search/hybrid` p95
climbed into the 10-35s range (Locust's own client-side numbers, since the Prometheus bucket
ceiling saturated at this load level — see below): real queueing, since only 3 inference slots
exist, but a safe, honest degradation curve instead of a host crash.

**The tradeoff, stated plainly:** this trades single-request latency and best-case throughput
for a hard ceiling on how much concurrent CPU load this app will ever put on its own host — a
deliberate circuit-breaker-style choice. The actual way to raise the ceiling isn't tuning these
two numbers further, it's one of: horizontal scaling (multiple backend processes/replicas —
out of reach on Render's single free-tier instance), a smaller/faster model, batching multiple
concurrent encode requests into one call, or GPU inference. Worth naming all four as the real
next steps in an interview, not just the two numbers that were tuned this week.

## Also fixed: Prometheus's per-handler histogram was miscalibrated

`prometheus-fastapi-instrumentator`'s default per-handler latency histogram (the one Grafana's
dashboard and `collect_metrics.py` group `by (handler)`) only had buckets at `(0.1, 0.5, 1)`
seconds — fine for fast endpoints, but it silently clipped anything slower (uncached hybrid
search, ~5-8s) to ~1s in every `histogram_quantile()` query. Widened to
`(0.05, 0.1, 0.25, 0.5, 0.75, 1, 2, 3, 5, 7.5, 10)` in `backend/app/main.py`. This still
saturates at the heaviest throttled-concurrency runs (observed values up to 35s) — a known,
stated limit of this fix, not chased further this phase; Locust's own client-side percentiles
are cited above wherever that happened.

## Known issue surfaced this phase, and how it's worked around

Bare-metal `pytest` crashes on this Windows dev machine with a `Windows fatal exception:
access violation` inside `transformers/core_model_loading.py`'s internal multi-threaded model
weight loading — reproduced both before and after every change in this phase, confirming it's
pre-existing and unrelated to this work. Likely a Windows-specific bug in a newer
`transformers` release's parallel checkpoint-loading path.

**Workaround (verified working):** run the suite inside the backend's own Docker image instead
of bare-metal — it's Linux (`python:3.11-slim`), so it never touches the Windows-specific bug.
The Dockerfile uses `CMD`, not `ENTRYPOINT`, so a one-off container can fully override the
default "run migrations then start uvicorn" behavior:

```
docker compose up -d db redis
docker compose run --rm backend python -m pytest -q
```

`--rm` cleans up the one-off container afterward. Confirmed: all 42 tests pass this way,
including after every code change made in this phase (`auth.py`, `retrieval_service.py`,
`hybrid_search.py`, `main.py`) — no regressions. GitHub Actions' Linux CI runners (Phase 13)
should never hit the Windows bug either way, but this is now also the reliable way to run the
suite locally on this machine going forward, not just a one-off diagnostic.
