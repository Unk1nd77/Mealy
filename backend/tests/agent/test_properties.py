import json
from unittest.mock import AsyncMock, patch

from hypothesis import given
from hypothesis import strategies as st

from app.core.agent import orchestrator as agent
from app.core.agent.schemas import MealPlanOutput
from app.core.rag import retriever
from tests.test_orchestrator import _recipes, _user_profile, _valid_llm_json


@given(
    st.lists(
        st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=4,
    )
)
def test_normalization_and_round_trip(calories):
    output = MealPlanOutput.model_validate_json(_valid_llm_json())
    for meal, value in zip(output.day.meals, calories, strict=True):
        meal.calories = value
    agent._normalize_day_totals(output.day)
    assert output.day.total_calories == round(sum(calories))
    assert output == MealPlanOutput.model_validate(json.loads(output.model_dump_json()))


@given(st.integers(1, 100), st.integers(1, 10000))
async def test_pipeline_compatibility(day, target):
    output = json.loads(_valid_llm_json())
    output["daily_target_calories"] = target
    profile = dict(_user_profile(), target_calories=target)
    with (
        patch.object(agent.settings, "AGENT_TOOL_USE_ENABLED", False),
        patch.object(agent, "_call_llm", new_callable=AsyncMock, return_value=json.dumps(output)),
        patch.object(agent, "validate_day_plan", return_value=(True, None)),
        patch.object(
            agent, "ToolExecutor", side_effect=AssertionError("must not construct executor")
        ),
        patch.object(agent, "async_session", side_effect=AssertionError("must not open session")),
    ):
        result = await agent.generate_day_plan(profile, _recipes(), day)
    assert result.plan.day_number == day and result.tool_call_trace == []


@given(
    st.lists(st.sampled_from(["milk", "eggs", "nuts", "fish", "gluten"]), min_size=1, unique=True)
)
async def test_retriever_safety_and_filters_before_limit(allergens):
    recipes = [
        {
            "id": str(i),
            "title": "Meal",
            "ingredients_short": "",
            "allergens": [a],
            "meal_type": "lunch",
            "tags": [],
        }
        for i, a in enumerate(allergens)
    ] + [
        {
            "id": "wrong-type",
            "title": "Meal",
            "ingredients_short": "",
            "allergens": [],
            "meal_type": "breakfast",
            "tags": [],
        },
        {
            "id": "excluded",
            "title": "Meal",
            "ingredients_short": "",
            "allergens": [],
            "meal_type": "lunch/dinner",
            "tags": [],
        },
        {
            "id": "safe",
            "title": "Meal",
            "ingredients_short": "",
            "allergens": [],
            "meal_type": "lunch/dinner",
            "tags": [],
        },
    ]
    with patch.object(
        retriever, "_get_hybrid_recipe_order", new_callable=AsyncMock, return_value=(recipes, False)
    ):
        result = await retriever.search_recipes(
            AsyncMock(),
            allergies=allergens,
            meal_type="lunch",
            exclude_recipe_ids={"excluded"},
            limit=1,
        )
    assert [r["id"] for r in result] == ["safe"]
