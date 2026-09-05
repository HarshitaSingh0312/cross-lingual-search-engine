import json
import logging

import redis.asyncio as redis
from prometheus_client import Counter

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Labeled by method (dense/hybrid, parsed from the cache key) so Grafana can graph hit rate
# per search method, not just in aggregate - dense and hybrid have very different cost-of-miss.
cache_requests_total = Counter("cache_requests_total", "Search cache lookups", ["method", "result"])


class CacheService:
    """Thin wrapper around an async Redis client for caching search results.

    Every method fails open: if Redis is unreachable (a real possibility on Upstash's free
    tier, or a container that isn't up yet), search must keep working without the cache,
    not 500 the whole request over a caching layer. Failures are logged, not swallowed
    silently - a search that's mysteriously never cached is a much harder bug to find than
    a warning in the logs pointing straight at it.
    """

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    @staticmethod
    def make_key(query: str, top_k: int, method: str = settings.embedding_model_name) -> str:
        # Case/whitespace-insensitive on purpose: "AI" and "ai" get the same cached results,
        # trading a little cache precision for a meaningfully higher hit rate.
        # `method` namespaces the key so /search and /search/hybrid never collide, since a
        # dense-only result set isn't a valid cached answer for a hybrid request or vice versa.
        normalized = query.strip().lower()
        return f"search:{method}:{top_k}:{normalized}"

    @staticmethod
    def _method_label(key: str) -> str:
        # Keys look like "search:<method>:<top_k>:<query>" (see make_key) - the label is
        # parsed rather than threaded through every get()/set() call as an extra argument.
        parts = key.split(":", 2)
        return parts[1] if len(parts) > 1 else "unknown"

    async def get(self, key: str) -> list[dict] | None:
        try:
            raw = await self._get_client().get(key)
        except Exception:
            logger.warning("cache read failed, falling back to a live search", exc_info=True)
            return None
        cache_requests_total.labels(method=self._method_label(key), result="hit" if raw is not None else "miss").inc()
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: list[dict], ttl: int | None = None) -> None:
        try:
            await self._get_client().set(key, json.dumps(value), ex=ttl or settings.cache_ttl_seconds)
        except Exception:
            logger.warning("cache write failed, results just won't be cached this time", exc_info=True)

    async def ping(self) -> bool:
        try:
            return await self._get_client().ping()
        except Exception:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


cache_service = CacheService()
