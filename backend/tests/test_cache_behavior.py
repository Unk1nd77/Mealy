from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routes import plans
from app.core import cache
from app.db.models import MealPlanStatus


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DummyDb:
    def __init__(self, value):
        self._value = value
        self.calls = 0

    async def execute(self, *_args, **_kwargs):
        self.calls += 1
        return _ScalarResult(self._value)


class _FakeRedis:
    def __init__(self, value: str | None):
        self.value = value
        self.deleted_keys: list[str] = []

    async def get(self, _key: str):
        return self.value

    async def delete(self, key: str):
        self.deleted_keys.append(key)


def _ready_plan(plan_id: uuid.UUID, user_id: uuid.UUID, plan_data: dict):
    return SimpleNamespace(
        id=plan_id,
        user_id=user_id,
        status=MealPlanStatus.ready,
        start_date=date(2026, 4, 23),
        end_date=date(2026, 4, 29),
        plan_data=plan_data,
    )


@pytest.mark.asyncio
async def test_cache_get_json_deletes_invalid_json(monkeypatch):
    fake_redis = _FakeRedis("{broken")
    monkeypatch.setattr(cache, "get_redis", AsyncMock(return_value=fake_redis))

    payload = await cache.get_json("plans:response:v1:test")

    assert payload is None
    assert fake_redis.deleted_keys == [f"{cache.PREFIX}plans:response:v1:test"]


@pytest.mark.asyncio
async def test_get_plan_uses_cached_response_without_db(monkeypatch):
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    cached_payload = {
        "id": str(plan_id),
        "user_id": str(user_id),
        "status": "READY",
        "start_date": "2026-04-23",
        "end_date": "2026-04-29",
        "plan_data": {
            "total_days": 7,
            "daily_target_calories": 2100,
            "days": [],
        },
    }
    monkeypatch.setattr(plans.cache, "get_json", AsyncMock(return_value=cached_payload))

    db = _DummyDb(None)
    response = await plans.get_plan(plan_id, db=db)

    assert response.id == plan_id
    assert response.user_id == user_id
    assert response.status == "READY"
    assert db.calls == 0


@pytest.mark.asyncio
async def test_get_plan_warms_cache_on_miss(monkeypatch):
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_data = {
        "total_days": 7,
        "daily_target_calories": 2100,
        "days": [{"day_number": 1, "meals": []}],
    }
    plan = _ready_plan(plan_id, user_id, plan_data)
    db = _DummyDb(plan)

    get_json = AsyncMock(return_value=None)
    set_json = AsyncMock()
    monkeypatch.setattr(plans.cache, "get_json", get_json)
    monkeypatch.setattr(plans.cache, "set_json", set_json)

    response = await plans.get_plan(plan_id, db=db)

    assert response.id == plan_id
    assert db.calls == 1
    set_json.assert_awaited_once_with(
        plans._plan_response_cache_key(plan_id),
        {
            "id": str(plan_id),
            "user_id": str(user_id),
            "status": "READY",
            "start_date": "2026-04-23",
            "end_date": "2026-04-29",
            "plan_data": plan_data,
        },
        ttl=plans.PLAN_RESPONSE_CACHE_TTL,
    )


@pytest.mark.asyncio
async def test_get_shopping_list_warms_cache_on_miss(monkeypatch):
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_data = {
        "days": [
            {
                "meals": [
                    {
                        "ingredients_summary": [
                            {"name": "Rice", "amount": 100, "unit": "g"},
                            {"name": "Chicken", "amount": 200, "unit": "g"},
                        ]
                    }
                ]
            }
        ]
    }
    plan = _ready_plan(plan_id, user_id, plan_data)
    db = _DummyDb(plan)

    get_json = AsyncMock(return_value=None)
    set_json = AsyncMock()
    monkeypatch.setattr(plans.cache, "get_json", get_json)
    monkeypatch.setattr(plans.cache, "set_json", set_json)

    response = await plans.get_shopping_list(plan_id, db=db)

    assert response == {
        "plan_id": str(plan_id),
        "items": [
            {"name": "Chicken", "amount": 200.0, "unit": "g"},
            {"name": "Rice", "amount": 100.0, "unit": "g"},
        ],
    }
    assert db.calls == 1
    set_json.assert_awaited_once_with(
        plans._shopping_list_cache_key(plan_id),
        response,
        ttl=plans.SHOPPING_LIST_CACHE_TTL,
    )
