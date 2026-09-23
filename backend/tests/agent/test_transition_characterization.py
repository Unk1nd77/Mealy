"""Observed baseline contracts, not approval of unsafe legacy behavior.

Real loop/executor/validators and production use case; fake provider, retrieval and persistence.
Mode/error expectations updated at the production cutover; unresolved safety witnesses remain.
Database atomicity and broker delivery require separate integration tests.
"""

from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core import plan_services
from app.core.agent import runtime as agent
from app.core.agent import use_case
from app.core.rag import retriever
from app.db import session as db
from app.worker import tasks
from tests.agent.test_agentic_loop import fake_llm, final, setup_calls


@pytest.fixture
def runtime_boundaries(monkeypatch, profile):
    sessions = []

    @asynccontextmanager
    async def factory():
        session = AsyncMock()
        sessions.append(session)
        yield session

    for module in (agent, db, plan_services):
        monkeypatch.setattr(module, "async_session", factory)
    context = AsyncMock(return_value={"user": profile, "available_recipes": []})
    saved = AsyncMock(return_value={"plan_id": "saved-plan", "status": "READY"})
    monkeypatch.setattr(use_case, "build_context_payload", context)
    monkeypatch.setattr(use_case, "save_plan_payload", saved)
    return SimpleNamespace(
        sessions=sessions, context=context, saved=saved
    )


def scripted_days(monkeypatch, plan_data, recipes, days):
    replies = []
    pools = []
    for number in range(1, days + 1):
        day = deepcopy(plan_data)
        day["day_number"] = number
        pool = deepcopy(recipes)
        for meal, recipe in zip(day["meals"], pool, strict=True):
            recipe["id"] += f"-day-{number}"
            meal["recipe_id"] = recipe["id"]
        pools.append(pool)
        replies.extend([*setup_calls(day), final(day)])
    search = AsyncMock(side_effect=pools)
    monkeypatch.setattr(retriever, "search_recipes", search)
    snapshots = fake_llm(monkeypatch, replies)
    return search, snapshots


@pytest.mark.parametrize("days", [1, 7, 14])
async def test_day_week_and_max_days_use_real_agentic_loop(
    monkeypatch, plan_data, recipes, runtime_boundaries, days
):
    search, snapshots = scripted_days(monkeypatch, plan_data, recipes, days)
    result = await tasks._generate_agentic("owner", days)
    assert result["status"] == "READY"
    assert result["mode"] == "agentic"
    assert result["quality_status"] == "valid"
    assert search.await_count == days
    assert len(snapshots) == 3 * days
    runtime_boundaries.saved.assert_awaited_once()
    payload = runtime_boundaries.saved.call_args.args[1]
    runtime_boundaries.context.assert_awaited_once_with("owner", include_recipes=False)
    assert payload["total_days"] == days
    assert [day["day_number"] for day in payload["days"]] == list(range(1, days + 1))
    assert len(payload["generation_meta"]["days"]) == days
    for day, meta in zip(payload["days"], payload["generation_meta"]["days"], strict=True):
        assert meta["attempts_used"] == 3
        assert [t["tool"] for t in meta["tool_call_trace"]] == [
            "get_user_profile",
            "search_recipes",
            "validate_day_plan",
        ]
        assert day["total_calories"] == round(sum(m["calories"] for m in day["meals"]))
        assert all(m["ingredients_summary"] for m in day["meals"])


async def test_exhausted_provider_budget_never_saves_ready(
    monkeypatch, profile, runtime_boundaries
):
    monkeypatch.setattr(agent.settings, "AGENT_MAX_LLM_CALLS", 2)
    snapshots = fake_llm(monkeypatch, [httpx.ConnectError("offline")] * 2)
    with pytest.raises(agent.AgentLimitError):
        await tasks._generate_agentic("owner", 7)
    runtime_boundaries.saved.assert_not_awaited()
    assert len(snapshots) == 2


async def test_retry_after_provider_timeout_spends_one_call(
    monkeypatch, profile, plan_data, search_mock
):
    snapshots = fake_llm(
        monkeypatch,
        [httpx.ReadTimeout("offline"), *setup_calls(plan_data), final(plan_data)],
    )
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.attempts_used == 4
    assert len(snapshots) == 4
    assert result.quality_status == "valid"


async def test_executor_state_does_not_leak_between_users(profile, recipes, monkeypatch):
    other = deepcopy(profile)
    profile["user_id"] = "owner-a"
    other["user_id"] = "owner-b"
    other["allergies"] = ["synthetic-allergen-b"]
    first = agent.ToolExecutor(profile, AsyncMock())
    second = agent.ToolExecutor(other, AsyncMock())
    search = AsyncMock(return_value=recipes)
    monkeypatch.setattr(retriever, "search_recipes", search)
    await first.dispatch("get_user_profile", {})
    await first.dispatch("search_recipes", {"query": "food", "user_id": "owner-b"})
    assert first.session_state.profile_fetched
    assert first.collected_recipes
    assert not second.session_state.profile_fetched
    assert second.collected_recipes == {}
    assert second.search_call_count == 0
    result = await second.dispatch("get_user_profile", {})
    assert "user_id" not in result
    await second.dispatch("search_recipes", {"query": "food", "allergies": []})
    assert search.call_args.kwargs["allergies"] == ["synthetic-allergen-b"]
    assert "user_id" not in search.call_args.kwargs


async def test_baseline_id_provenance_does_not_make_nutrients_canonical(
    monkeypatch, profile, plan_data, recipes
):
    """C05: reproduces current vulnerability, not a target acceptance criterion."""
    canonical = deepcopy(recipes)
    for recipe in canonical:
        recipe["calories"] = 1
        recipe["protein"] = 1
    monkeypatch.setattr(retriever, "search_recipes", AsyncMock(return_value=canonical))
    fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.quality_status == "valid"
    assert result.plan.total_calories == 2000
    assert sum(recipe["calories"] for recipe in result.collected_recipes) == 4


async def test_save_failure_is_not_success(
    monkeypatch, plan_data, recipes, runtime_boundaries
):
    scripted_days(monkeypatch, plan_data, recipes, 1)
    runtime_boundaries.saved.side_effect = RuntimeError("synthetic-write-failure")
    with pytest.raises(RuntimeError, match="synthetic-write-failure"):
        await tasks._generate_agentic("owner", 1)
    runtime_boundaries.saved.assert_awaited_once()

