from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.api.routes import plans
from app.core.agent.orchestrator import build_plan_observability
from app.db.models import MealPlanStatus


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _DummyDb:
    def __init__(self, value):
        self._value = value

    async def execute(self, *_args, **_kwargs):
        return _ScalarResult(self._value)


def _ready_plan(plan_id: uuid.UUID, user_id: uuid.UUID, plan_data: dict):
    return SimpleNamespace(
        id=plan_id,
        user_id=user_id,
        status=MealPlanStatus.ready,
        start_date=date(2026, 4, 23),
        end_date=date(2026, 4, 29),
        plan_data=plan_data,
    )


def test_build_plan_observability_sanitizes_persisted_trace():
    plan_data = {
        "daily_target_calories": 2000,
        "days": [
            {
                "day_number": 1,
                "total_calories": 1980,
            }
        ],
        "generation_trace": [
            {
                "key": "reflection",
                "status": "LIMITED",
                "message": "Validation rerun after calorie mismatch.",
                "prompt": "secret prompt",
                "raw_response": "secret response",
            }
        ],
    }

    payload = build_plan_observability(plan_data)

    assert payload["source"] == "stored_plan"
    assert payload["has_persisted_trace"] is True
    assert payload["steps"] == [
        {
            "key": "reflection",
            "status": "limited",
            "message": "Validation rerun after calorie mismatch.",
        }
    ]
    assert payload["day_checks"][0]["within_target"] is True


@pytest.mark.asyncio
async def test_get_plan_observability_returns_safe_day_checks():
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan_data = {
        "daily_target_calories": 2100,
        "days": [
            {
                "day_number": 1,
                "total_calories": 2310,
            },
            {
                "day_number": 2,
                "total_calories": 2080,
            },
        ],
    }
    db = _DummyDb(_ready_plan(plan_id, user_id, plan_data))

    response = await plans.get_plan_observability(plan_id, db=db)

    assert response.source == "derived_plan"
    assert response.has_persisted_trace is False
    assert response.day_checks[0].day_number == 1
    assert response.day_checks[0].deviation_kcal == 210.0
    assert response.day_checks[0].deviation_pct == 10.0
    assert response.day_checks[0].within_target is False
    assert response.day_checks[1].within_target is True
    assert "Worst deviation: 10.0%" in response.summary
