import uuid


async def _get_a_search_result_id(client):
    resp = await client.get("/api/v1/search", params={"q": "climate change", "top_k": 1})
    return resp.json()["results"][0]["search_result_id"]


async def test_search_response_includes_search_result_id(client):
    resp = await client.get("/api/v1/search", params={"q": "climate change", "top_k": 3})
    for result in resp.json()["results"]:
        assert "search_result_id" in result


async def test_feedback_requires_an_existing_search_result(client):
    resp = await client.post(
        "/api/v1/feedback", json={"search_result_id": str(uuid.uuid4()), "is_relevant": True}
    )
    assert resp.status_code == 404


async def test_anonymous_feedback_is_accepted(client):
    search_result_id = await _get_a_search_result_id(client)
    resp = await client.post(
        "/api/v1/feedback", json={"search_result_id": search_result_id, "is_relevant": True}
    )
    assert resp.status_code == 201
    assert resp.json()["is_relevant"] is True


async def test_logged_in_feedback_updates_instead_of_duplicating(client):
    from sqlalchemy import delete, select

    from app.db.base import async_session
    from app.db.models import Feedback, User

    email = f"feedback_{uuid.uuid4().hex}@example.com"
    try:
        signup = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
        search_result_id = await _get_a_search_result_id(client)

        first = await client.post(
            "/api/v1/feedback",
            json={"search_result_id": search_result_id, "is_relevant": True},
            headers=headers,
        )
        second = await client.post(
            "/api/v1/feedback",
            json={"search_result_id": search_result_id, "is_relevant": False},
            headers=headers,
        )
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]  # same row, updated in place
        assert second.json()["is_relevant"] is False

        async with async_session() as session:
            count = len(
                (
                    await session.scalars(
                        select(Feedback).where(Feedback.search_result_id == search_result_id)
                    )
                ).all()
            )
            assert count == 1
    finally:
        async with async_session() as session:
            await session.execute(delete(User).where(User.email == email))
            await session.commit()
