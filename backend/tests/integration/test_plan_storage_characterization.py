"""Real normalized persistence against the runner-owned disposable database only."""

import json
import os
import uuid
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import canonical_pipeline, relational_store
from app.db.models import ActivityLevel, Gender, Goal, MealPlan, MealPlanStatus, Recipe, User
from tests.agent.sample_data import _valid_llm_json

pytestmark = pytest.mark.integration


@pytest.fixture
async def storage(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if os.environ.get("MEALY_DISPOSABLE_DB") != "1" or not url:
        pytest.skip("Run check_agentic_baseline.py --database; never use a production DB")
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(canonical_pipeline.cache, "set_json", AsyncMock())
    try:
        async with sessions() as session:
            user = User(
                email=f"storage-{uuid.uuid4()}@example.com",
                password_hash="synthetic",
                age=30,
                weight_kg=70,
                height_cm=175,
                gender=Gender.male,
                activity_level=ActivityLevel.moderate,
                goal=Goal.maintain,
                target_calories=2000,
            )
            session.add(user)
            await relational_store.sync_user_normalized(
                session,
                user,
                allergies=[],
                preferences=[],
                disliked_ingredients=[],
                diseases=[],
                meal_schedule=None,
            )
            day = json.loads(_valid_llm_json())["day"]
            for meal in day["meals"]:
                rid = uuid.uuid4()
                session.add(
                    Recipe(
                        id=rid,
                        title=meal["title"],
                        meal_type=meal["type"],
                        calories=meal["calories"],
                        protein=meal["protein"],
                        fat=meal["fat"],
                        carbs=meal["carbs"],
                    )
                )
                meal["recipe_id"] = str(rid)
                meal["portion_factor"] = 1
                meal["ingredients_summary"] = [
                    {"name": "synthetic rice", "amount": 100, "unit": "g"}
                ]
            await session.commit()
            plan = await canonical_pipeline.create_plan_record(
                session, user_id=str(user.id), days=1
            )
            plan_id = plan.id
        payload = {
            "total_days": 1,
            "daily_target_calories": 2000,
            "days": [day],
            "generation_meta": {
                "mode": "agentic",
                "quality_status": "valid",
                "days": [{"tool_call_trace": [{"tool": "search_recipes"}]}],
            },
        }
        yield sessions, plan_id, payload
    finally:
        await engine.dispose()


async def test_baseline_roundtrip_keeps_meals_but_loses_generation_metadata(storage):
    """C11: regression witness. Stage3 must change the metadata assertion, not remove it."""
    sessions, plan_id, payload = storage
    async with sessions() as session:
        plan = await session.get(MealPlan, plan_id)
        await canonical_pipeline.finalize_plan_record(
            session, plan_record=plan, plan_data=payload, status=MealPlanStatus.ready
        )
    async with sessions() as session:
        plan = await session.get(MealPlan, plan_id)
        actual = await relational_store.build_plan_data_from_rows(session, plan)
        assert plan.status is MealPlanStatus.ready
        assert actual["total_days"] == 1
        assert actual["daily_target_calories"] == 2000
        assert actual["days"][0]["total_calories"] == 2000

        def key(meal):
            return meal["type"]

        assert sorted(actual["days"][0]["meals"], key=key) == sorted(
            payload["days"][0]["meals"], key=key
        )
        assert payload["generation_meta"]["days"][0]["tool_call_trace"]
        assert actual["generation_meta"] == {}


async def test_db_unique_day_constraint_and_explicit_rollback_preserve_saved_rows(storage):
    sessions, plan_id, payload = storage
    async with sessions() as session:
        plan = await session.get(MealPlan, plan_id)
        await canonical_pipeline.finalize_plan_record(
            session, plan_record=plan, plan_data=payload, status=MealPlanStatus.ready
        )
    invalid = deepcopy(payload)
    invalid["days"].append(deepcopy(invalid["days"][0]))
    async with sessions() as session:
        plan = await session.get(MealPlan, plan_id)
        with pytest.raises(IntegrityError):
            await canonical_pipeline.finalize_plan_record(
                session, plan_record=plan, plan_data=invalid, status=MealPlanStatus.ready
            )
        await session.rollback()
    async with sessions() as session:
        plan = await session.get(MealPlan, plan_id)
        actual = await relational_store.build_plan_data_from_rows(session, plan)
        assert actual["total_days"] == 1
        assert len(actual["days"][0]["meals"]) == 4
        assert plan.status is MealPlanStatus.ready
