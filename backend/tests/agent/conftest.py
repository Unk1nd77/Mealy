import json
from unittest.mock import AsyncMock

import pytest
from hypothesis import HealthCheck, settings

from app.core.agent import orchestrator as agent
from tests.test_orchestrator import _recipes, _user_profile, _valid_llm_json

settings.register_profile("ci", max_examples=200, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("dev", max_examples=50)


@pytest.fixture(autouse=True)
def tool_mode(monkeypatch):
    monkeypatch.setattr(agent.settings, "AGENT_TOOL_USE_ENABLED", True)
    monkeypatch.setattr(agent.settings, "AGENT_MAX_LLM_CALLS", 10)
    monkeypatch.setattr(agent.settings, "AGENT_MAX_SEARCH_CALLS", 5)


@pytest.fixture
def profile():
    return _user_profile()


@pytest.fixture
def plan_data():
    return json.loads(_valid_llm_json())["day"]


@pytest.fixture
def recipes():
    return [
        dict(r, meal_type=t, tags=[])
        for r, t in zip(
            _recipes(),
            ("breakfast", "lunch", "dinner", "snack"),
            strict=True,
        )
    ]


@pytest.fixture
def executor(profile):
    return agent.ToolExecutor(profile, AsyncMock())


@pytest.fixture
def search_mock(monkeypatch, recipes):
    mock = AsyncMock(return_value=recipes)
    monkeypatch.setattr(agent.retriever, "search_recipes", mock)
    return mock
