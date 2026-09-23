"""Characterize safety gaps BEFORE fixing them; these are not desired contracts."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.routes import plans
from app.core import agent_cli_runtime, canonical_pipeline, day_plan_repair, demo_pipeline
from app.core.rag import retriever
from app.db.models import MealPlanStatus
from app.db.session import get_db


async def test_baseline_anonymous_plan_cache_read(monkeypatch):
    """C03: actual ASGI request, no authentication and no real personal data."""
    plan_id, owner_id = uuid.uuid4(), uuid.uuid4()
    payload = {
        "id": str(plan_id),
        "user_id": str(owner_id),
        "status": "READY",
        "start_date": None,
        "end_date": None,
        "plan_data": {"days": [], "total_days": 1, "daily_target_calories": 2000},
    }
    monkeypatch.setattr(plans.cache, "get_json", AsyncMock(return_value=payload))
    session = AsyncMock()

    async def fake_db():
        yield session

    app = FastAPI()
    app.include_router(plans.router)
    app.dependency_overrides[get_db] = fake_db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        response = await c.get(f"/api/plans/{plan_id}")
    assert response.status_code == 200
    assert response.json()["user_id"] == str(owner_id)
    session.execute.assert_not_awaited()


@pytest.mark.parametrize("mode", ["agentic", "agent_cli", "llm_direct"])
async def test_baseline_broker_publish_precedes_durable_run(monkeypatch, mode):
    """C10: write failure leaves an already published message, observed ordering."""
    events = []

    def publish(*args, **kwargs):
        assert args == ("generate_meal_plan",)
        assert kwargs["args"][1:] == [7, "agentic"]
        events.append("published")
        return SimpleNamespace(id="synthetic-task")

    async def persist(*args, **kwargs):
        assert kwargs["mode"] == "agentic"
        events.append("db-write-attempt")
        raise RuntimeError("synthetic-db-failure")

    monkeypatch.setattr(plans.celery_app, "send_task", publish)
    monkeypatch.setattr(plans, "create_generation_run", persist)
    with pytest.raises(RuntimeError, match="synthetic-db-failure"):
        await plans.generate_plan(
            plans.GeneratePlanRequest(user_id=uuid.uuid4(), mode=mode), db=AsyncMock()
        )
    assert events == ["published", "db-write-attempt"]


async def test_baseline_cache_failure_occurs_after_db_commit(monkeypatch):
    """C11: caller sees failure despite commit; not an atomic DB integration test."""
    events = []

    async def sync(*args, **kwargs):
        events.append("rows")

    async def commit():
        events.append("commit")

    async def cache_write(*args, **kwargs):
        events.append("cache")
        raise RuntimeError("synthetic-cache-failure")

    monkeypatch.setattr(canonical_pipeline, "sync_plan_rows", sync)
    monkeypatch.setattr(canonical_pipeline.cache, "set_json", cache_write)
    session = AsyncMock()
    session.commit.side_effect = commit
    plan = SimpleNamespace(id=uuid.uuid4(), status=MealPlanStatus.generating)
    with pytest.raises(RuntimeError, match="synthetic-cache-failure"):
        await canonical_pipeline.finalize_plan_record(
            session, plan_record=plan, plan_data={"days": []}, status=MealPlanStatus.ready
        )
    assert events == ["rows", "commit", "cache"]
    assert plan.status is MealPlanStatus.ready


@pytest.mark.parametrize("days", [0, 15])
def test_api_rejects_days_outside_existing_contract(days):
    with pytest.raises(ValidationError):
        plans.GeneratePlanRequest(user_id=uuid.uuid4(), days=days)


def test_api_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        plans.GeneratePlanRequest(user_id=uuid.uuid4(), mode="unknown")


@pytest.mark.parametrize(
    "module",
    [agent_cli_runtime, canonical_pipeline, day_plan_repair, demo_pipeline, retriever],
    ids=lambda m: m.__name__,
)
def test_baseline_compatibility_truth_tables(module):
    """150 real helper calls. Disagreements are recorded, not silently reconciled."""
    ordinary = {
        "breakfast": {"breakfast"},
        "lunch": {"lunch", "universal"},
        "dinner": {"dinner", "universal"},
        "snack": {"snack", "second_snack"},
        "second_snack": {"snack", "second_snack"},
    }
    expected = {k: set(v) for k, v in ordinary.items()}
    if module is demo_pipeline:
        expected["second_snack"] = {"second_snack"}
    if module is retriever:
        expected = {slot: {slot, "universal"} for slot in ordinary}
    for slot in ordinary:
        for recipe_type in [*ordinary, "universal"]:
            observed = (
                retriever.meal_type_matches({"meal_type": recipe_type}, slot)
                if module is retriever
                else recipe_type in module._slot_compatible_types(slot)
            )
            assert observed == (recipe_type in expected[slot]), (slot, recipe_type)
