import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import admin, auth, feedback, health, me, search
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import async_session
from app.services.cache_service import cache_service
from app.services.hybrid_search import hybrid_search_service
from app.services.rag_service import rag_service
from app.services.retrieval_service import retrieval_service

settings = get_settings()
configure_logging(settings.log_level)
access_logger = structlog.get_logger("access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    retrieval_service.load()  # load the embedding model once, not per-request
    async with async_session() as db:
        await hybrid_search_service.load(db)  # builds the BM25 index, loads the cross-encoder
    yield
    await cache_service.close()
    await rag_service.close()


app = FastAPI(title="Cross-Lingual Search Engine", lifespan=lifespan)

# Auto-instruments every route with request-count/latency histograms and exposes them at
# /metrics (outside the /api/v1 prefix - Prometheus scrapes it directly, it's not an API call).
# latency_lowr_buckets is the per-handler histogram (the one Grafana's dashboard and
# load-test percentile queries group `by (handler)`) - its default (0.1, 0.5, 1) tops out at
# 1s, so anything slower (e.g. uncached hybrid search, ~4-5s) silently clips to ~1s in every
# histogram_quantile() query instead of reporting its real latency. Widened to actually cover
# this app's slowest known endpoint. The library keeps this histogram's bucket count small on
# purpose (it's multiplied by every handler+method combo, unlike the unlabeled high-r one) -
# matching the fewest buckets that still cover the real range, not maximizing resolution.
Instrumentator().instrument(
    app, latency_lowr_buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1, 2, 3, 5, 7.5, 10)
).expose(app, endpoint="/metrics", include_in_schema=False)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    # Binds a request_id to every structlog call made anywhere during this request (services,
    # routes, error handlers) via contextvars, so grepping logs by request_id reconstructs the
    # full story of one request even though the work spans multiple modules/loggers.
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    access_logger.info(
        "request_handled",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
