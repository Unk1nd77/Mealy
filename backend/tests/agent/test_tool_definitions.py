import json
from itertools import product
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.config import Settings
from app.core.agent import orchestrator as agent


def test_definitions_and_partial_registration(monkeypatch):
    tools = agent._build_tool_definitions()
    assert {t["function"]["name"] for t in tools} == {
        "get_user_profile",
        "search_recipes",
        "validate_day_plan",
    }
    assert "user_id" not in json.dumps(tools)
    for tool in tools:
        fn = tool["function"]
        assert fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert "properties" in fn["parameters"]
    params = tools[2]["function"]["parameters"]
    assert "MealItem" in params["$defs"]
    monkeypatch.setattr(agent.ToolExecutor, "_execute_search_recipes", None)
    assert len(agent._build_tool_definitions()) == 2
    monkeypatch.setattr(agent.ToolExecutor, "_execute_get_user_profile", None)
    monkeypatch.setattr(agent.ToolExecutor, "_execute_validate_day_plan", None)
    with pytest.raises(agent.AgentConfigurationError):
        agent._build_tool_definitions()


@given(st.uuids())
def test_prompt_never_renders_profile(marker):
    with patch.object(agent.ToolExecutor, "_execute_get_user_profile", side_effect=AssertionError):
        prompt = agent._build_agentic_system_prompt()
    assert str(marker) not in prompt
    assert all(
        name in prompt for name in ("get_user_profile", "search_recipes", "validate_day_plan")
    )
    assert "{{" not in prompt


@pytest.mark.parametrize("expect_final", [False, True])
async def test_llm_request_contract(expect_final):
    response = MagicMock()
    response.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]
    }
    client = AsyncMock()
    client.post.return_value = response
    with patch.object(agent.httpx, "AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        tools = agent._build_tool_definitions()
        result = await agent._call_llm_with_tools([], tools, expect_final=expect_final)
    payload = client.post.call_args.kwargs["json"]
    assert payload["tools"] == tools
    assert payload["tool_choice"] == "auto"
    assert ("response_format" in payload) == expect_final
    if expect_final:
        assert payload["response_format"] == {"type": "json_object"}
    assert result["finish_reason"] == "stop"
    response.raise_for_status.assert_called_once()


@pytest.mark.parametrize("profile,recipes,validated", product([False, True], repeat=3))
def test_session_state(profile, recipes, validated):
    state = agent.AgentSessionState(profile, recipes, "hash" if validated else None)
    assert state.ready_for_final() == (profile and recipes and validated)
    assert state.missing_steps() == [
        name
        for name, done in zip(
            ["get_user_profile", "search_recipes", "validate_day_plan"],
            [profile, recipes, validated],
            strict=True,
        )
        if not done
    ]


def test_limits_and_config():
    exc = agent.AgentLimitError(10, ["pending-1"])
    assert exc.llm_calls == 10 and exc.pending_tool_call_ids == ["pending-1"]
    assert "10" in str(exc) and "pending-1" in str(exc)
    assert Settings.model_fields["AGENT_TOOL_USE_ENABLED"].default is False
    for value in [0, 21]:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, AGENT_MAX_SEARCH_CALLS=value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, AGENT_MAX_LLM_CALLS=0)


def test_recursive_trace_redaction():
    summary = agent._build_args_summary(
        {
            "user_id": "secret-user",
            "plan": {"allergies": ["secret-nut"]},
            "nested": [{"goal": "secret-goal", "query": "x" * 400}],
        }
    )
    assert len(summary) <= 200 and "secret" not in summary
