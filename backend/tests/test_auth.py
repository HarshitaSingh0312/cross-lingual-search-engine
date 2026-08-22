import uuid

from sqlalchemy import delete, update

from app.db.base import async_session
from app.db.models import User, UserRole


async def _cleanup_user(email: str):
    async with async_session() as session:
        await session.execute(delete(User).where(User.email == email))
        await session.commit()


async def test_signup_creates_user_and_returns_tokens(client):
    email = f"signup_{uuid.uuid4().hex}@example.com"
    try:
        resp = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
    finally:
        await _cleanup_user(email)


async def test_signup_rejects_duplicate_email(client):
    email = f"dup_{uuid.uuid4().hex}@example.com"
    try:
        await client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"})
        resp = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        assert resp.status_code == 409
    finally:
        await _cleanup_user(email)


async def test_signup_rejects_short_password(client):
    email = f"short_{uuid.uuid4().hex}@example.com"
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": "short"})
    assert resp.status_code == 422


async def test_login_with_correct_credentials_returns_tokens(client):
    email = f"login_{uuid.uuid4().hex}@example.com"
    try:
        await client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"})
        resp = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": "correcthorse123"}
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
    finally:
        await _cleanup_user(email)


async def test_login_with_wrong_password_is_rejected(client):
    email = f"wrongpw_{uuid.uuid4().hex}@example.com"
    try:
        await client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"})
        resp = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": "wrongpassword"}
        )
        assert resp.status_code == 401
    finally:
        await _cleanup_user(email)


async def test_me_requires_a_valid_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user_with_valid_token(client):
    email = f"me_{uuid.uuid4().hex}@example.com"
    try:
        signup = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        access_token = signup.json()["access_token"]
        resp = await client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == email
        assert resp.json()["role"] == "user"
    finally:
        await _cleanup_user(email)


async def test_refresh_issues_a_new_access_token(client):
    email = f"refresh_{uuid.uuid4().hex}@example.com"
    try:
        signup = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        refresh_token = signup.json()["refresh_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        assert "access_token" in resp.json()
    finally:
        await _cleanup_user(email)


async def test_refresh_rejects_an_access_token(client):
    email = f"refreshbad_{uuid.uuid4().hex}@example.com"
    try:
        signup = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        access_token = signup.json()["access_token"]
        resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401
    finally:
        await _cleanup_user(email)


async def test_admin_route_rejects_regular_user(client):
    email = f"regular_{uuid.uuid4().hex}@example.com"
    try:
        signup = await client.post(
            "/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"}
        )
        access_token = signup.json()["access_token"]
        resp = await client.get(
            "/api/v1/admin/users", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert resp.status_code == 403
    finally:
        await _cleanup_user(email)


async def test_admin_route_allows_admin_user(client):
    email = f"admin_{uuid.uuid4().hex}@example.com"
    try:
        await client.post("/api/v1/auth/signup", json={"email": email, "password": "correcthorse123"})

        # Promote directly in the DB, mirroring scripts/promote_admin.py's real path.
        async with async_session() as session:
            await session.execute(update(User).where(User.email == email).values(role=UserRole.admin))
            await session.commit()

        login = await client.post(
            "/api/v1/auth/login", data={"username": email, "password": "correcthorse123"}
        )
        admin_access_token = login.json()["access_token"]

        resp = await client.get(
            "/api/v1/admin/users", headers={"Authorization": f"Bearer {admin_access_token}"}
        )
        assert resp.status_code == 200
        assert any(u["email"] == email for u in resp.json())
    finally:
        await _cleanup_user(email)
