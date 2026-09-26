from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.agent import tools as agent
from tests.agent.sample_data import _user_profile


@given(st.integers(1, 10000), st.lists(st.text(), max_size=5))
async def test_profile_projection(calories, values):
    profile = dict(_user_profile(), target_calories=calories, allergies=values, user_id="secret")
    executor = agent.ToolExecutor(profile, AsyncMock())
    result = await executor.dispatch("get_user_profile", {})
    assert set(result) == {
        "target_calories",
        "meal_schedule",
        "allergies",
        "disliked_ingredients",
        "diseases",
        "preferences",
        "goal",
    }
    assert result["target_calories"] == calories
    assert result["allergies"] == values
    assert executor.session_state.profile_fetched
    executor.db_session.execute.assert_not_called()
    profile["allergies"].append("changed")
    assert executor.user_profile["allergies"] != profile["allergies"]


async def test_profile_unavailable():
    executor = agent.ToolExecutor(None, AsyncMock())
    result = await executor.dispatch("get_user_profile", {})
    assert result["error"]["code"] == "PROFILE_UNAVAILABLE"
    assert not executor.session_state.profile_fetched
    result = await executor.dispatch("search_recipes", {"query": "food"})
    assert result["error"]["code"] == "PROFILE_UNAVAILABLE"


@given(st.text(alphabet=" \t\r\n", max_size=30))
async def test_whitespace_query_does_not_spend_budget(query):
    executor = agent.ToolExecutor(_user_profile(), AsyncMock())
    with patch.object(agent.retriever, "search_recipes", new_callable=AsyncMock) as search:
        result = await executor.dispatch("search_recipes", {"query": query})
    assert result["error"]["code"] == "INVALID_QUERY"
    assert executor.search_call_count == 0
    search.assert_not_awaited()


@pytest.mark.parametrize(
    "args,code",
    [
        ({"query": "food", "meal_type": "invalid"}, "INVALID_MEAL_TYPE"),
        ({"query": "food", "meal_type": []}, "INVALID_MEAL_TYPE"),
        *[
            ({"query": "food", "limit": value}, "INVALID_LIMIT")
            for value in [0, -1, 1.5, True, "10", None]
        ],
    ],
)
async def test_invalid_arguments(executor, search_mock, args, code):
    result = await executor.dispatch("search_recipes", args)
    assert result["error"]["code"] == code
    assert executor.search_call_count == 0
    search_mock.assert_not_awaited()


@given(st.lists(st.text(min_size=1), max_size=5))
async def test_search_filters_cannot_be_overridden(values):
    profile = dict(_user_profile(), allergies=values, disliked_ingredients=values, diseases=values)
    executor = agent.ToolExecutor(profile, AsyncMock())
    with patch.object(
        agent.retriever, "search_recipes", new_callable=AsyncMock, return_value=[]
    ) as search:
        await executor.dispatch(
            "search_recipes",
            {"query": "food", "allergies": [], "dislikes": [], "diseases": [], "user_id": "other"},
        )
    assert search.call_args.kwargs["allergies"] == values
    assert search.call_args.kwargs["dislikes"] == values
    assert search.call_args.kwargs["diseases"] == values
    assert "user_id" not in search.call_args.kwargs


async def test_search_meal_filter_and_provenance(executor, search_mock, recipes):
    search_mock.return_value = [*recipes, dict(recipes[1], id="both", meal_type="lunch/dinner")]
    result = await executor.dispatch("search_recipes", {"query": "lunch", "meal_type": "lunch"})
    assert {r["id"] for r in result["recipes"]} == {"recipe-2", "both"}
    assert set(executor.collected_recipes) == {"recipe-2", "both"}
    assert executor.session_state.recipes_fetched
    assert executor.collected_recipes["recipe-2"]["ingredients"]
    assert "ingredients" not in result["recipes"][0]


@given(st.integers(min_value=21, max_value=10000))
async def test_search_clamps_limit(limit):
    executor = agent.ToolExecutor(_user_profile(), AsyncMock())
    with patch.object(
        agent.retriever, "search_recipes", new_callable=AsyncMock, return_value=[]
    ) as search:
        result = await executor.dispatch("search_recipes", {"query": "food", "limit": limit})
    assert search.call_args.kwargs["limit"] == 20
    assert len(result["recipes"]) <= 20
    assert result["message"] == "limit clamped to 20"


async def test_empty_search_does_not_complete_step(executor, search_mock):
    search_mock.return_value = []
    result = await executor.dispatch("search_recipes", {"query": "food"})
    assert result == {
        "recipes": [],
        "message": "No recipes found matching the given criteria and safety filters",
    }
    assert not executor.session_state.recipes_fetched
    assert executor.search_call_count == 1


@pytest.mark.parametrize("failed", [False, True])
async def test_search_budget_includes_failures(executor, search_mock, failed):
    if failed:
        search_mock.side_effect = RuntimeError("private-db-secret")
    for _ in range(agent.settings.AGENT_MAX_SEARCH_CALLS):
        result = await executor.dispatch("search_recipes", {"query": "food"})
        assert "private-db-secret" not in str(result)
        if failed:
            assert result["error"]["code"] == "SEARCH_UNAVAILABLE"
    result = await executor.dispatch("search_recipes", {"query": "food"})
    assert result["error"]["code"] == "SEARCH_LIMIT_REACHED"
    assert search_mock.await_count == agent.settings.AGENT_MAX_SEARCH_CALLS


async def test_validation_hash_and_all_errors(executor, plan_data):
    original = deepcopy(plan_data)
    result = await executor.dispatch("validate_day_plan", {"plan": plan_data})
    assert result["is_valid"] and result["errors"] == []
    assert executor.session_state.last_validated_hash == agent._compute_plan_hash(plan_data)
    assert plan_data == original
    plan_data["total_calories"] = 100
    plan_data["meals"].pop()
    result = await executor.dispatch("validate_day_plan", {"plan": plan_data})
    assert not result["is_valid"] and len(result["errors"]) == 3
    assert executor.session_state.last_validated_hash is None


@pytest.mark.parametrize("plan", [None, "bad", [], {}, {"day_number": 0}])
async def test_invalid_schema_resets_hash(executor, plan):
    executor.session_state.last_validated_hash = "stale"
    result = await executor.dispatch("validate_day_plan", {"plan": plan})
    assert result["is_valid"] == (result["errors"] == []) is False
    assert result["message"] is None
    assert executor.session_state.last_validated_hash is None


async def test_validator_exception(executor, plan_data, monkeypatch):
    executor.session_state.last_validated_hash = "stale"

    def fail(*args, **kwargs):
        raise RuntimeError("validation failed")

    monkeypatch.setattr(agent.validator, "validate_day_plan", fail)
    result = await executor.dispatch("validate_day_plan", {"plan": plan_data})
    assert result["errors"] == ["Internal validation error: validation failed"]
    assert not result["is_valid"] and executor.session_state.last_validated_hash is None


async def test_dispatch_unknown_and_exception(executor, monkeypatch):
    assert (await executor.dispatch("unknown", {}))["error"]["code"] == "UNKNOWN_TOOL"
    assert (await executor.dispatch("get_user_profile", []))["error"]["code"] == "INVALID_ARGUMENTS"

    def fail():
        raise RuntimeError("private-secret")

    monkeypatch.setattr(executor, "_execute_get_user_profile", fail)
    result = await executor.dispatch("get_user_profile", {})
    assert result["error"]["code"] == "TOOL_EXECUTION_ERROR"
    assert "private-secret" not in str(result)
