import asyncio
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import async_session, engine
from app.main import app
from app.services.cache_service import cache_service
from app.services.hybrid_search import hybrid_search_service
from app.services.rag_service import rag_service
from app.services.retrieval_service import retrieval_service

if sys.platform == "win32":
    # asyncpg's SSL connections are unreliable on Windows' default ProactorEventLoop
    # (connections intermittently die between requests); the selector loop doesn't have this issue.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def _load_model():
    retrieval_service.load()


@pytest.fixture(autouse=True)
async def _load_hybrid_index():
    # hybrid_search_service.load() is idempotent (no-ops once self.bm25 is set), so this only
    # ever does real work - and opens a DB connection - on the first test that needs it. That
    # connection belongs to that test's own event loop, same loop-affinity constraint as below.
    if hybrid_search_service.bm25 is None:
        async with async_session() as db:
            await hybrid_search_service.load(db)


@pytest.fixture(autouse=True)
async def _dispose_engine_pool():
    # The engine's connection pool binds its connections to whichever event loop is
    # running when they're first opened. pytest-asyncio gives each test its own loop,
    # so the pool must be torn down after every test or the next test's loop reuses
    # connections tied to a now-dead one ("attached to a different loop").
    yield
    await engine.dispose()
    # Same loop-affinity issue applies to the Redis client - close it and let cache_service
    # lazily reconnect on the next test's (fresh) event loop.
    await cache_service.close()
    cache_service._client = None
    await rag_service.close()
    rag_service._client = None


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
