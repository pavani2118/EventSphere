
import uuid

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)

pytestmark = pytest.mark.integration


def create_test_user():
    if not __import__("os").getenv("EVENTSPHERE_TEST_DATABASE"):
        pytest.skip("Set EVENTSPHERE_TEST_DATABASE=1 only for an isolated test database.")
    email = f"test_{uuid.uuid4().hex[:10]}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test User",
            "email": email,
            "password": "TestPass123!"
        }
    )

    assert response.status_code == 201

    return email


def test_user_registration():
    email = create_test_user()

    with __import__("app.database", fromlist=["get_db_connection"]).get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT role FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()

    assert user["role"] == "ATTENDEE"


def test_duplicate_registration():
    email = create_test_user()

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test User",
            "email": email,
            "password": "TestPass123!"
        }
    )

    assert response.status_code == 409


def test_login_and_profile():
    email = create_test_user()

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "TestPass123!"
        }
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    profile = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert profile.status_code == 200
    assert profile.json()["email"] == email


def test_wrong_password():
    email = create_test_user()

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123!"
        }
    )

    assert response.status_code == 401


def test_attendee_cannot_access_admin():
    email = create_test_user()

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "TestPass123!"
        }
    )

    token = login.json()["access_token"]

    response = client.get(
        "/auth/admin-check",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_logout():
    email = create_test_user()

    login = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "TestPass123!"
        }
    )

    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200

    profile = client.get("/auth/me", headers=headers)
    assert profile.status_code == 401
