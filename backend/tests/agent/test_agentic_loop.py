import json
from contextlib import asynccontextmanager
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.agent import runtime as agent
from app.core.rag import retriever
from tests.agent.sample_data import _user_profile


def call(name, args=None, call_id=None):
    return {
        "id": call_id or name,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args or {})},
    }


def batch(*calls):
    return {"message": {"role": "assistant", "content": None, "tool_calls": list(calls)}}


def final(plan, **changes):
    return {
        "message": {"content": json.dumps({"daily_target_calories": 2000, "day": plan, **changes})}
    }


def setup_calls(plan):
    return [
        batch(call("get_user_profile"), call("search_recipes", {"query": "food"})),
        batch(call("validate_day_plan", {"plan": plan})),
    ]


def fake_llm(monkeypatch, responses):
    snapshots = []
    replies = iter(responses)

    async def invoke(messages, tools, *, expect_final):
        snapshots.append((deepcopy(messages), expect_final))
        value = next(replies)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(agent, "_call_llm_with_tools", invoke)
    return snapshots


async def test_happy_path(monkeypatch, profile, plan_data, search_mock):
    snapshots = fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.quality_status == "valid" and result.attempts_used == 3
    assert result.plan.meals[0].ingredients_summary[0].name == "Oats"
    assert result.plan.total_protein == sum(m.protein for m in result.plan.meals)
    assert len(result.tool_call_trace) == 3 and result.collected_recipes
    assert [expected for _, expected in snapshots] == [False, False, True]
    history = snapshots[1][0]
    assert [m["role"] for m in history] == ["system", "user", "assistant", "tool", "tool"]
    assert [m["tool_call_id"] for m in history if m["role"] == "tool"] == [
        "get_user_profile",
        "search_recipes",
    ]
    assert "2000" not in snapshots[0][0][0]["content"]


async def test_early_final_feedback(monkeypatch, profile, plan_data, search_mock):
    snapshots = fake_llm(monkeypatch, [final(plan_data), *setup_calls(plan_data), final(plan_data)])
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.attempts_used == 4
    assert all(
        name in snapshots[1][0][-1]["content"]
        for name in ["get_user_profile", "search_recipes", "validate_day_plan"]
    )


async def test_hash_mismatch(monkeypatch, profile, plan_data, search_mock):
    changed = deepcopy(plan_data)
    changed["meals"][0]["title"] = "Changed"
    snapshots = fake_llm(
        monkeypatch,
        [
            *setup_calls(plan_data),
            final(changed),
            batch(call("validate_day_plan", {"plan": changed})),
            final(changed),
        ],
    )
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.attempts_used == 5
    assert snapshots[3][1] is False
    assert "differs from the last validated" in snapshots[3][0][-1]["content"]


async def test_provenance_before_backend_validation(monkeypatch, profile, plan_data, search_mock):
    unknown = deepcopy(plan_data)
    unknown["meals"][0]["recipe_id"] = "invented"
    snapshots = fake_llm(
        monkeypatch,
        [
            *setup_calls(unknown),
            final(unknown),
            batch(call("validate_day_plan", {"plan": plan_data})),
            final(plan_data),
        ],
    )
    with patch.object(
        agent.validator, "validate_day_plan", wraps=agent.validator.validate_day_plan
    ) as validate:
        result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.attempts_used == 5
    assert "not returned by search_recipes" in snapshots[3][0][-1]["content"]
    assert validate.call_count == 3


@pytest.mark.parametrize(
    "bad_content,expected",
    [("{", "Invalid JSON"), ("[]", "Schema error"), ('{"day": {}}', "Schema error")],
)
async def test_parse_feedback(monkeypatch, profile, plan_data, search_mock, bad_content, expected):
    snapshots = fake_llm(
        monkeypatch,
        [*setup_calls(plan_data), {"message": {"content": bad_content}}, final(plan_data)],
    )
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.attempts_used == 4
    assert expected in snapshots[3][0][-1]["content"]


async def test_backend_is_quality_authority(monkeypatch, profile, plan_data, search_mock):
    fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    with patch.object(
        agent.validator,
        "validate_day_plan",
        side_effect=[(True, None), (False, "backend rejected")],
    ):
        result = await agent._run_agentic_loop(profile, AsyncMock())
    assert (
        result.quality_status == "partially_valid" and result.validation_error == "backend rejected"
    )


@pytest.mark.parametrize("transport_failure", [False, True])
async def test_call_limit(monkeypatch, profile, transport_failure):
    monkeypatch.setattr(agent.settings, "AGENT_MAX_LLM_CALLS", 2)
    reply = httpx.ConnectError("offline") if transport_failure else {"message": {"content": "{}"}}
    snapshots = fake_llm(monkeypatch, [reply, reply])
    with pytest.raises(agent.AgentLimitError) as error:
        await agent._run_agentic_loop(profile, AsyncMock())
    assert error.value.llm_calls == 2 and error.value.pending_tool_call_ids == []
    assert len(snapshots) == 2


async def test_last_batch_fully_executed(monkeypatch, profile):
    monkeypatch.setattr(agent.settings, "AGENT_MAX_LLM_CALLS", 1)
    fake_llm(monkeypatch, [batch(call("get_user_profile"), call("unknown"))])
    with (
        patch.object(
            agent.ToolExecutor, "dispatch", new_callable=AsyncMock, return_value={}
        ) as dispatch,
        pytest.raises(agent.AgentLimitError) as error,
    ):
        await agent._run_agentic_loop(profile, AsyncMock())
    assert dispatch.await_count == 2
    assert error.value.pending_tool_call_ids == []


async def test_malformed_args_and_dispatch_failure(monkeypatch, profile, plan_data, search_mock):
    broken = call("validate_day_plan")
    broken["function"]["arguments"] = "{"
    snapshots = fake_llm(
        monkeypatch, [batch(broken, call("unknown")), *setup_calls(plan_data), final(plan_data)]
    )
    original = agent.ToolExecutor.dispatch

    async def dispatch(self, name, args):
        if name == "unknown":
            raise RuntimeError("secret")
        return await original(self, name, args)

    monkeypatch.setattr(agent.ToolExecutor, "dispatch", dispatch)
    result = await agent._run_agentic_loop(profile, AsyncMock())
    errors = [
        json.loads(m["content"])["error"]["code"] for m in snapshots[1][0] if m["role"] == "tool"
    ]
    assert errors == ["INVALID_ARGUMENTS", "TOOL_EXECUTION_ERROR"]
    assert len(result.tool_call_trace) == 5


@given(st.integers(1, 10))
async def test_batch_order(count):
    calls = [call("unknown", {"query": "x", "user_id": "private"}, str(i)) for i in range(count)]
    seen = []

    async def llm(messages, tools, *, expect_final):
        seen.append(deepcopy(messages))
        return batch(*calls) if len(seen) == 1 else {"message": {"content": "{}"}}

    with (
        patch.object(agent, "_call_llm_with_tools", llm),
        patch.object(agent.settings, "AGENT_MAX_LLM_CALLS", 2),
        pytest.raises(agent.AgentLimitError),
    ):
        await agent._run_agentic_loop(_user_profile(), AsyncMock())
    assert seen[1][2]["role"] == "assistant"
    assert [m["tool_call_id"] for m in seen[1][3:]] == [str(i) for i in range(count)]


async def test_empty_registry_with_legacy_flag_disabled(monkeypatch, profile):
    llm = AsyncMock()
    monkeypatch.setattr(agent, "_call_llm_with_tools", llm)
    monkeypatch.setattr(agent, "_build_tool_definitions", list)
    with pytest.raises(agent.AgentConfigurationError):
        await agent._run_agentic_loop(profile, AsyncMock())
    llm.assert_not_awaited()


async def test_public_entry_closes_session(monkeypatch, profile, plan_data, search_mock):
    sessions = []

    @asynccontextmanager
    async def session_factory():
        sessions.append("open")
        try:
            yield AsyncMock()
        finally:
            sessions.append("closed")

    monkeypatch.setattr(agent, "async_session", session_factory)
    fake_llm(monkeypatch, [*setup_calls(plan_data), final(plan_data)])
    result = await agent.generate_day_plan(profile)
    assert result.quality_status == "valid" and sessions == ["open", "closed"]


async def test_requested_day_is_preserved(monkeypatch, profile, plan_data, search_mock):
    wrong_day = dict(plan_data, day_number=2)
    snapshots = fake_llm(
        monkeypatch,
        [
            *setup_calls(wrong_day),
            final(wrong_day),
            batch(call("validate_day_plan", {"plan": plan_data})),
            final(plan_data),
        ],
    )
    result = await agent._run_agentic_loop(profile, AsyncMock())
    assert result.plan.day_number == 1
    assert "requested day_number" in snapshots[3][0][-1]["content"]


@given(st.lists(st.sampled_from(["get_user_profile", "unknown"]), min_size=1, max_size=10))
async def test_trace_covers_every_call(names):
    from tests.agent.sample_data import _recipes, _valid_llm_json

    plan = json.loads(_valid_llm_json())["day"]
    responses = [
        batch(
            *[
                call(name, {"query": "x" * 300, "user_id": "private"}, str(i))
                for i, name in enumerate(names)
            ]
        ),
        *setup_calls(plan),
        final(plan),
    ]
    with (
        patch.object(agent, "_call_llm_with_tools", new_callable=AsyncMock, side_effect=responses),
        patch.object(retriever, "search_recipes", new_callable=AsyncMock, return_value=_recipes()),
    ):
        result = await agent._run_agentic_loop(_user_profile(), AsyncMock())
    assert len(result.tool_call_trace) == len(names) + 3
    assert [entry["tool"] for entry in result.tool_call_trace[: len(names)]] == names
    for entry in result.tool_call_trace:
        assert isinstance(entry["llm_call"], int) and entry["llm_call"] >= 1
        assert len(entry["args_summary"]) <= 200
        assert "private" not in entry["args_summary"]


async def test_summary_logs(monkeypatch, profile):
    logs = []
    sink = agent.logger.add(lambda message: logs.append(str(message)), level="INFO")
    try:
        monkeypatch.setattr(agent.settings, "AGENT_MAX_LLM_CALLS", 1)
        fake_llm(monkeypatch, [{"message": {"content": "{}"}}])
        with pytest.raises(agent.AgentLimitError):
            await agent._run_agentic_loop(profile, AsyncMock())
        summary = next(line for line in logs if "[agentic]" in line)
        assert "llm_calls=1" in summary and "outcome=AgentLimitError" in summary
        assert all(
            f"'{name}': 0" in summary
            for name in ("get_user_profile", "search_recipes", "validate_day_plan")
        )
    finally:
        agent.logger.remove(sink)
