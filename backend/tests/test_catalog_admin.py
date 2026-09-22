"""Authorization checks for catalog administration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes.auth import get_admin_user
from app.config import settings


@pytest.mark.asyncio
async def test_get_admin_user_accepts_configured_email(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com, owner@example.com")
    user = SimpleNamespace(email="Owner@Example.com")

    assert await get_admin_user(user) is user


@pytest.mark.asyncio
async def test_get_admin_user_rejects_regular_user(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "admin@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user(SimpleNamespace(email="user@example.com"))

    assert exc_info.value.status_code == 403
