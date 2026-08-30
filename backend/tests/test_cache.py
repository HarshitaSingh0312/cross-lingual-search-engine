import uuid

from sqlalchemy import delete, update

from app.db.base import async_session
from app.db.models import User, UserRole
from app.services.cache_service import cache_service


async def test_search_populates_the_cache(client):
    query = "artificial intelligence"
    resp = await client.get("/api/v1/search", params={"q": query, "top_k": 3})
    assert resp.status_code == 200

    cached = await cache_service.get(cache_service.make_key(query, 3))
    assert cached is not None
    assert len(cached) == 3


async def test_repeated_search_returns_the_same_documents(client):
    params = {"q": "renewable energy", "top_k": 5}
    first = await client.get("/api/v1/search", params=params)
    second = await client.get("/api/v1/search", params=params)

    first_ids = [r["doc_id"] for r in first.json()["results"]]
    second_ids = [r["doc_id"] for r in second.json()["results"]]
    assert first_ids == second_ids
    # Each call is still logged as its own search event, so it gets its own result ids.
    first_result_ids = [r["search_result_id"] for r in first.json()["results"]]
    second_result_ids = [r["search_result_id"] for r in second.json()["results"]]
    assert first_result_ids != second_result_ids


def test_cache_key_is_case_and_whitespace_insensitive():
    assert cache_service.make_key("Climate Change", 5) == cache_service.make_key("  climate change  ", 5)


async def test_warm_popular_cache_requires_admin(client):
    resp = await client.post("/api/v1/admin/cache/warm-popular")
    assert resp.status_code == 401


async def test_admin_can_trigger_cache_warming(client):
    email = f"warm_{uuid.uuid4().hex}@example.com"
    try:
        await client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"})
        async with async_session() as session:
            await session.execute(update(User).where(User.email == email).values(role=UserRole.admin))
            await session.commit()
        login = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": "correcthorse123"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        resp = await client.post(
            "/api/v1/admin/cache/warm-popular", params={"limit": 3}, headers=headers
        )
        assert resp.status_code == 202
        queries = resp.json()["warming"]
        assert isinstance(queries, list)

        # BackgroundTasks run before the ASGI test transport hands control back, so by now
        # the warmed queries should already be sitting in the cache.
        for query in queries:
            assert await cache_service.get(cache_service.make_key(query, 10)) is not None
    finally:
        async with async_session() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
