import logging

from app.db.base import async_session
from app.services.cache_service import cache_service
from app.services.retrieval_service import retrieval_service

logger = logging.getLogger(__name__)


async def warm_cache(queries: list[str], top_k: int = 10) -> None:
    """Runs after the triggering request has already returned a response - FastAPI's
    BackgroundTasks runs this in-process once the response is sent, no separate worker (see
    PROJECT_PLAN.md Section 2 on why there's no Celery here). Needs its own DB session since
    the request's session is already closed by the time this runs.
    """
    async with async_session() as db:
        for query in queries:
            try:
                results = await retrieval_service.search(db, query, top_k=top_k)
                await cache_service.set(cache_service.make_key(query, top_k), results)
            except Exception:
                logger.warning("failed to warm cache for query=%r", query, exc_info=True)
