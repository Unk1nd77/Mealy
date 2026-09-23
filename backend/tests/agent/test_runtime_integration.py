from contextlib import asynccontextmanager
from inspect import signature
from unittest.mock import AsyncMock

import pytest

from app.core import agent_cli_runtime, cli_contract
from app.core.agent import runtime as agent
from app.core.agent import use_case, validation
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
    monkeypatch.setattr(cli_contract, "async_session", factory)


async def test_cli_profile_only_context(monkeypatch, profile, sessions):
    monkeypatch.setattr(cli_contract, "load_user_profile", AsyncMock(return_value=profile))
    search = AsyncMock(side_effect=AssertionError("Eager retrieval is forbidden"))
    monkeypatch.setattr(cli_contract, "load_candidate_recipes", search)
    result = await cli_contract.build_context_payload("user", include_recipes=False)
    assert result["user"] == profile and result["available_recipes"] == []
    search.assert_not_awaited()


async def test_cli_uses_search_results_and_saves_trace(
    monkeypatch, profile, plan_data, search_mock, sessions
):
    context = AsyncMock(return_value={"user": profile, "available_recipes": []})
    saved = AsyncMock(return_value={"plan_id": "plan-1", "status": "READY", "days": 1})
    monkeypatch.setattr(agent_cli_runtime, "build_context_payload", context)
    monkeypatch.setattr(agent_cli_runtime, "save_plan_payload", saved)
    monkeypatch.setattr(
        validation,
        "repair_day_plan",
        lambda **kwargs: pytest.fail("Valid searched recipes must not trigger repair"),
    )
    # Universal recipes are valid in the new tool mode, including breakfast.
    for recipe in search_mock.return_value:
        recipe["meal_type"] = "universal"
    fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    result = await agent_cli_runtime.run_agent_cli_pipeline(user_id="user", days=1)
    assert result["status"] == "READY" and result["quality_status"] == "valid"
    assert all(call.kwargs["include_recipes"] is False for call in context.call_args_list)
    payload = saved.call_args.args[1]
    assert len(payload["generation_meta"]["days"][0]["tool_call_trace"]) == 3
    assert payload["days"][0]["meals"][0]["ingredients_summary"][0]["name"] == "Oats"


async def test_worker_uses_tools_and_persists_trace(
    monkeypatch, profile, plan_data, search_mock, sessions
):
    context = AsyncMock(return_value={"user": profile, "available_recipes": []})
    saved = AsyncMock(return_value={"plan_id": "plan-1"})
    monkeypatch.setattr(use_case, "build_context_payload", context)
    monkeypatch.setattr(use_case, "save_plan_payload", saved)
    assert tasks.generate_meal_plan.name == "generate_meal_plan"
    parameters = signature(tasks.generate_meal_plan.run).parameters
    assert list(parameters) == ["user_id", "days", "mode"]
    assert parameters["days"].default == 7
    assert parameters["mode"].default == "agentic"
    fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    result = await tasks._generate_by_mode("user", days=1, mode="llm_direct")
    assert result["status"] == "READY" and result["quality_status"] == "valid"
    assert result["mode"] == "agentic"
    payload = saved.call_args.args[1]
    assert len(payload["generation_meta"]["days"][0]["tool_call_trace"]) == 3
