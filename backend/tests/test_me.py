import uuid

from sqlalchemy import delete

from app.db.base import async_session
from app.db.models import User


async def _signup(client) -> tuple[str, dict]:
    email = f"me_{uuid.uuid4().hex}@example.com"
    signup = await client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"})
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    return email, headers


async def _cleanup_user(email: str):
    async with async_session() as session:
        await session.execute(delete(User).where(User.email == email))
        await session.commit()


async def test_history_requires_login(client):
    resp = await client.get("/api/v1/me/history")
    assert resp.status_code == 401


async def test_history_returns_only_this_users_searches(client):
    email, headers = await _signup(client)
    try:
        await client.get("/api/v1/search", params={"q": "renewable energy"}, headers=headers)
        resp = await client.get("/api/v1/me/history", headers=headers)
        assert resp.status_code == 200
        queries = [item["query_text"] for item in resp.json()]
        assert "renewable energy" in queries
    finally:
        await _cleanup_user(email)


async def test_bookmark_requires_an_existing_document(client):
    email, headers = await _signup(client)
    try:
        resp = await client.post(
            "/api/v1/me/bookmarks", json={"document_id": "does_not_exist"}, headers=headers
        )
        assert resp.status_code == 404
    finally:
        await _cleanup_user(email)


async def test_bookmark_create_list_and_idempotency(client):
    email, headers = await _signup(client)
    try:
        search = await client.get("/api/v1/search", params={"q": "climate change", "top_k": 1}, headers=headers)
        doc_id = search.json()["results"][0]["doc_id"]

        first = await client.post("/api/v1/me/bookmarks", json={"document_id": doc_id}, headers=headers)
        second = await client.post("/api/v1/me/bookmarks", json={"document_id": doc_id}, headers=headers)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]  # bookmarking twice is a no-op

        listed = await client.get("/api/v1/me/bookmarks", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]["document"]["id"] == doc_id
    finally:
        await _cleanup_user(email)
