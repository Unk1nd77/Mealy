"""API tests for JWT auth endpoints using a fake async session."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import bcrypt as _bcrypt
import pytest
from fastapi.testclient import TestClient

from app.api.routes import auth
from app.api.routes import users
from app.db.models import ActivityLevel, Gender, Goal, User
from app.main import app

os.environ["DEBUG"] = "true"


class FakeResult:
    def __init__(self, value: User | None):
        self._value = value

    def scalar_one_or_none(self) -> User | None:
        return self._value


class FakeAsyncSession:
    def __init__(self) -> None:
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[uuid.UUID, User] = {}

    async def execute(self, statement: Any) -> FakeResult:
        params = statement.compile().params
        if "email_1" in params:
            return FakeResult(self.users_by_email.get(params["email_1"]))
        if "id_1" in params:
            return FakeResult(self.users_by_id.get(params["id_1"]))
        return FakeResult(None)

    def add(self, user: User) -> None:
        if user.id is None:
            user.id = uuid.uuid4()
        if user.created_at is None:
            user.created_at = datetime.now(UTC).replace(tzinfo=None)
        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user

    async def commit(self) -> None:
        return None

    async def refresh(self, user: User) -> None:
        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user


def _hashed_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _make_user(email: str, password: str) -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=_hashed_password(password),
        age=30,
        weight_kg=70.0,
        height_cm=175.0,
        gender=Gender.male,
        activity_level=ActivityLevel.moderate,
        goal=Goal.maintain,
        target_calories=2400,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    user.allergies = []
    user.preferences = ["high protein"]
    user.disliked_ingredients = []
    user.diseases = []
    user.meal_schedule = None
    return user


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[tuple[TestClient, FakeAsyncSession]]:
    fake_session = FakeAsyncSession()
    monkeypatch.setattr(auth.cache, "set_json", AsyncMock())
    monkeypatch.setattr(auth.cache, "delete", AsyncMock())

    async def override_get_db() -> AsyncIterator[FakeAsyncSession]:
        yield fake_session

    app.dependency_overrides[auth.get_db] = override_get_db
    app.dependency_overrides[users.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, fake_session
    app.dependency_overrides.clear()


def _register_payload(email: str = "user@example.com") -> dict[str, Any]:
    return {
        "email": email,
        "password": "strong-pass",
        "age": 28,
        "weight_kg": 72,
        "height_cm": 178,
        "gender": "male",
        "activity_level": "moderate",
        "goal": "maintain",
        "allergies": ["nuts"],
        "preferences": ["mediterranean"],
        "disliked_ingredients": ["liver"],
        "diseases": [],
    }


def test_register_returns_token_and_user(client: tuple[TestClient, FakeAsyncSession]) -> None:
    test_client, fake_session = client

    response = test_client.post("/api/auth/register", json=_register_payload())

    assert response.status_code == 201
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["expires_in"] > 0
    assert payload["user"]["email"] == "user@example.com"
    assert "user@example.com" in fake_session.users_by_email


def test_duplicate_email_is_rejected(client: tuple[TestClient, FakeAsyncSession]) -> None:
    test_client, fake_session = client
    existing_user = _make_user("user@example.com", "strong-pass")
    fake_session.add(existing_user)

    response = test_client.post("/api/auth/register", json=_register_payload())

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


def test_login_returns_token_for_existing_user(client: tuple[TestClient, FakeAsyncSession]) -> None:
    test_client, fake_session = client
    fake_session.add(_make_user("login@example.com", password="super-secret"))

    response = test_client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "super-secret"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == "login@example.com"


def test_invalid_token_is_rejected_on_protected_endpoint(
    client: tuple[TestClient, FakeAsyncSession],
) -> None:
    test_client, _ = client

    response = test_client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer definitely-not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


def test_me_returns_current_user_from_token(client: tuple[TestClient, FakeAsyncSession]) -> None:
    test_client, fake_session = client
    user = _make_user("me@example.com", "strong-pass")
    fake_session.add(user)
    access_token, _ = auth._create_access_token(user.id)

    response = test_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["email"] == "me@example.com"
    assert payload["preferences"] == ["high protein"]


def test_update_me_updates_profile_and_recalculates_target(
    client: tuple[TestClient, FakeAsyncSession],
) -> None:
    test_client, fake_session = client
    user = _make_user("update@example.com", "strong-pass")
    fake_session.add(user)
    access_token, _ = auth._create_access_token(user.id)

    response = test_client.put(
        "/api/auth/me",
        json={
            "weight_kg": 82,
            "goal": "gain",
            "preferences": ["high protein", "simple dinners"],
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["weight_kg"] == 82
    assert payload["goal"] == "gain"
    assert payload["preferences"] == ["high protein", "simple dinners"]
    assert fake_session.users_by_email["update@example.com"].target_calories is not None


def test_update_user_requires_matching_authenticated_user(
    client: tuple[TestClient, FakeAsyncSession],
) -> None:
    test_client, fake_session = client
    user = _make_user("linked-profile@example.com", "strong-pass")
    other_user = _make_user("other-profile@example.com", "strong-pass")
    fake_session.add(user)
    fake_session.add(other_user)
    access_token, _ = auth._create_access_token(user.id)

    unauthenticated = test_client.put(
        f"/api/users/{user.id}",
        json={"goal": "gain"},
    )
    forbidden = test_client.put(
        f"/api/users/{other_user.id}",
        json={"goal": "gain"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response = test_client.put(
        f"/api/users/{user.id}",
        json={
            "goal": "gain",
            "preferences": ["high protein", "simple dinners"],
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(user.id)
    assert payload["goal"] == "gain"
    assert payload["preferences"] == ["high protein", "simple dinners"]
