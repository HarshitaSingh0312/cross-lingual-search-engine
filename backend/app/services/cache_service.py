import json
import logging

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


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

    async def get(self, key: str) -> list[dict] | None:
        try:
            raw = await self._get_client().get(key)
        except Exception:
            logger.warning("cache read failed, falling back to a live search", exc_info=True)
            return None
        return json.loads(raw) if raw is not None else None

    async def set(self, key: str, value: list[dict], ttl: int | None = None) -> None:
        try:
            await self._get_client().set(key, json.dumps(value), ex=ttl or settings.cache_ttl_seconds)
        except Exception:
            logger.warning("cache write failed, results just won't be cached this time", exc_info=True)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


cache_service = CacheService()
