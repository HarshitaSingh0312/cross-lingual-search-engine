import asyncio
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import engine
from app.main import app
from app.services.retrieval_service import retrieval_service

if sys.platform == "win32":
    # asyncpg's SSL connections are unreliable on Windows' default ProactorEventLoop
    # (connections intermittently die between requests); the selector loop doesn't have this issue.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session", autouse=True)
def _load_model():
    retrieval_service.load()


@pytest.fixture(autouse=True)
async def _dispose_engine_pool():
    # The engine's connection pool binds its connections to whichever event loop is
    # running when they're first opened. pytest-asyncio gives each test its own loop,
    # so the pool must be torn down after every test or the next test's loop reuses
    # connections tied to a now-dead one ("attached to a different loop").
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
