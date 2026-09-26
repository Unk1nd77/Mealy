from contextlib import asynccontextmanager
from inspect import signature
from unittest.mock import AsyncMock

import pytest

from app.core import plan_services
from app.core.agent import runtime as agent
from app.core.agent import use_case
from app.db import session as db
from app.worker import tasks
from tests.agent.test_agentic_loop import fake_llm, final, setup_calls


@pytest.fixture
def sessions(monkeypatch):
    @asynccontextmanager
    async def factory():
        yield AsyncMock()

    monkeypatch.setattr(agent, "async_session", factory)
    monkeypatch.setattr(db, "async_session", factory)
    monkeypatch.setattr(plan_services, "async_session", factory)


async def test_profile_only_context(monkeypatch, profile, sessions):
    monkeypatch.setattr(plan_services, "load_user_profile", AsyncMock(return_value=profile))
    result = await plan_services.build_context_payload("user", include_recipes=False)
    assert result["user"] == profile and result["available_recipes"] == []
    with pytest.raises(ValueError, match="Eager recipe context"):
        await plan_services.build_context_payload("user", include_recipes=True)


async def test_worker_uses_tools_and_persists_trace(
    monkeypatch, profile, plan_data, search_mock, sessions
):
    context = AsyncMock(return_value={"user": profile, "available_recipes": []})
    coverage = AsyncMock(return_value={"feasible": True, "missing_slots": []})
    saved = AsyncMock(return_value={"plan_id": "plan-1"})
    monkeypatch.setattr(use_case, "build_context_payload", context)
    monkeypatch.setattr(use_case, "assess_catalog_coverage", coverage)
    monkeypatch.setattr(use_case, "save_plan_payload", saved)
    assert tasks.generate_meal_plan.name == "generate_meal_plan"
    parameters = signature(tasks.generate_meal_plan.run).parameters
    assert list(parameters) == ["user_id", "days", "mode"]
    assert parameters["days"].default == 7
    assert parameters["mode"].default == "agentic"
    fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    result = await tasks._generate_agentic("user", days=1)
    assert result["status"] == "READY" and result["quality_status"] == "valid"
    assert result["mode"] == "agentic"
    coverage.assert_awaited_once_with(profile, days=1)
    payload = saved.call_args.args[1]
    assert len(payload["generation_meta"]["days"][0]["tool_call_trace"]) == 3
