"""Unit-тесты demo pipeline как отдельного режима выполнения."""

from __future__ import annotations

import types

import pytest

from app.core import demo_pipeline


class _DummySessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _profile() -> dict:
    return {
        "id": "user-1",
        "email": "demo@nutriagent.local",
        "gender": "male",
        "age": 30,
        "weight_kg": 80,
        "height_cm": 180,
        "goal": "maintain",
        "target_calories": 2200,
        "allergies": [],
        "preferences": ["high-protein"],
        "disliked_ingredients": [],
        "diseases": [],
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
        ],
    }


def _day(day_number: int) -> dict:
    return {
        "day_number": day_number,
        "total_calories": 1800.0,
        "total_protein": 120.0,
        "total_fat": 60.0,
        "total_carbs": 150.0,
        "meals": [
            {
                "type": "breakfast",
                "time": "08:00",
                "recipe_id": f"recipe-{day_number}",
                "title": "Breakfast",
                "calories": 1800.0,
                "protein": 120.0,
                "fat": 60.0,
                "carbs": 150.0,
                "ingredients_summary": [{"name": "Eggs", "amount": 3, "unit": "pcs"}],
            }
        ],
    }


@pytest.mark.asyncio
async def test_demo_pipeline_tracks_warnings_and_ready_status(monkeypatch):
    task = demo_pipeline.create_demo_task("user-1", 1)

    async def fake_load_user_profile(session, user_id: str):
        return _profile()

    async def fake_load_demo_recipes(session, user_profile: dict):
        return (
            [{"id": "recipe-1", "title": "Breakfast", "ingredients": []}],
            "Для демо soft-предпочтения ослаблены, чтобы собрать валидный рацион.",
        )

    async def fake_create_plan_record(session, *, user_id: str, days: int, status):
        return types.SimpleNamespace(id="plan-123")

    async def fake_finalize_plan_record(session, *, plan_record, plan_data: dict, status):
        return None

    monkeypatch.setattr(demo_pipeline, "async_session", lambda: _DummySessionContext())
    monkeypatch.setattr(demo_pipeline, "load_user_profile", fake_load_user_profile)
    monkeypatch.setattr(demo_pipeline, "_load_demo_recipes", fake_load_demo_recipes)
    monkeypatch.setattr(
        demo_pipeline,
        "_resolve_demo_target_calories",
        lambda *args, **kwargs: (
            1800,
            "Для демо target_calories скорректирован с 2200 до 1800.",
        ),
    )
    monkeypatch.setattr(
        demo_pipeline,
        "_find_plan_combination",
        lambda **kwargs: (_day(kwargs["day_number"]), None),
    )
    monkeypatch.setattr(demo_pipeline, "validate_day_plan", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(demo_pipeline, "create_plan_record", fake_create_plan_record)
    monkeypatch.setattr(demo_pipeline, "finalize_plan_record", fake_finalize_plan_record)
    monkeypatch.setattr(
        demo_pipeline,
        "aggregate_shopping_list",
        lambda plan_data: [{"name": "Eggs", "amount": 3.0, "unit": "pcs"}],
    )

    await demo_pipeline.run_demo_pipeline(task)

    assert task.status == "READY"
    assert task.quality_status == "partially_valid"
    assert len(task.warnings or []) == 2
    assert task.plan_id == "plan-123"
    assert task.payload()["mode"] == "demo"


@pytest.mark.asyncio
async def test_demo_pipeline_marks_failed_step_on_exception(monkeypatch):
    task = demo_pipeline.create_demo_task("user-1", 1)

    async def fake_load_user_profile(session, user_id: str):
        raise ValueError("Профиль пользователя не найден.")

    monkeypatch.setattr(demo_pipeline, "async_session", lambda: _DummySessionContext())
    monkeypatch.setattr(demo_pipeline, "load_user_profile", fake_load_user_profile)

    await demo_pipeline.run_demo_pipeline(task)

    assert task.status == "FAILED"
    assert task.error == "Профиль пользователя не найден."
    context_step = next(step for step in task.steps if step["key"] == "context")
    assert context_step["status"] == "failed"


def _schedule() -> list[dict]:
    return [
        {"type": "breakfast", "time": "08:00", "calories_pct": 25},
        {"type": "lunch", "time": "13:00", "calories_pct": 35},
        {"type": "dinner", "time": "19:00", "calories_pct": 30},
        {"type": "snack", "time": "16:00", "calories_pct": 10},
    ]


def _recipe(recipe_id: str, title: str, meal_type: str, calories: int) -> dict:
    return {
        "id": recipe_id,
        "title": title,
        "meal_type": meal_type,
        "calories": float(calories),
        "protein": 10.0,
        "fat": 10.0,
        "carbs": 10.0,
        "ingredients": [],
    }


def test_recipe_matches_slot_uses_strict_breakfast_rules():
    assert demo_pipeline._recipe_matches_slot(
        _recipe("bf", "Omelette", "breakfast", 350), "breakfast"
    )
    assert not demo_pipeline._recipe_matches_slot(_recipe("ln", "Pilaf", "lunch", 580), "breakfast")
    assert not demo_pipeline._recipe_matches_slot(
        _recipe("ld", "Pasta", "lunch/dinner", 560), "breakfast"
    )
    assert not demo_pipeline._recipe_matches_slot(
        _recipe("un", "Universal", "universal", 400), "breakfast"
    )


def test_candidate_lists_do_not_fallback_to_full_catalog_for_breakfast():
    recipes = [
        _recipe("ln1", "Pilaf", "lunch", 580),
        _recipe("dn1", "Steak", "dinner", 540),
        _recipe("sn1", "Yogurt", "snack", 280),
    ]

    candidates = demo_pipeline._candidate_lists(
        recipes, _schedule(), target_calories=2200, max_candidates_per_slot=4
    )

    assert candidates[0] == []
    assert [recipe["title"] for recipe in candidates[1]] == ["Pilaf"]
    assert [recipe["title"] for recipe in candidates[2]] == ["Steak"]
    assert [recipe["title"] for recipe in candidates[3]] == ["Yogurt"]


def test_find_plan_combination_returns_error_when_slot_has_no_matching_recipes():
    recipes = [
        _recipe("ln1", "Pilaf", "lunch", 580),
        _recipe("dn1", "Steak", "dinner", 540),
        _recipe("sn1", "Yogurt", "snack", 280),
    ]

    day_plan, error = demo_pipeline._find_plan_combination(
        recipes=recipes,
        schedule=_schedule(),
        target_calories=2200,
        day_number=1,
        max_candidates_per_slot=4,
    )

    assert day_plan is None
    assert error == "Недостаточно рецептов для всех слотов расписания."


def test_resolve_demo_target_calories_caps_target_to_really_achievable_day():
    recipes = [
        _recipe("bf1", "Pancakes", "breakfast", 450),
        _recipe("bf2", "Porridge", "breakfast", 350),
        _recipe("ln1", "Pasta", "lunch", 620),
        _recipe("ln2", "Pilaf", "lunch", 580),
        _recipe("dn1", "Steak", "dinner", 560),
        _recipe("dn2", "Fish", "dinner", 500),
        _recipe("sn1", "Yogurt", "snack", 280),
        _recipe("sn2", "Smoothie", "snack", 250),
    ]

    adjusted_target, message = demo_pipeline._resolve_demo_target_calories(
        2633, recipes, _schedule()
    )

    assert adjusted_target == 1910
    assert message is not None
    assert "2633" in message
    assert "1910" in message


def test_find_plan_combination_respects_blocked_signatures():
    recipes = [
        _recipe("bf1", "Pancakes", "breakfast", 450),
        _recipe("bf2", "Porridge", "breakfast", 350),
        _recipe("ln1", "Pasta", "lunch", 620),
        _recipe("ln2", "Pilaf", "lunch", 580),
        _recipe("dn1", "Steak", "dinner", 560),
        _recipe("dn2", "Fish", "dinner", 500),
        _recipe("sn1", "Yogurt", "snack", 280),
        _recipe("sn2", "Smoothie", "snack", 250),
    ]

    first_day, first_error = demo_pipeline._find_plan_combination(
        recipes=recipes,
        schedule=_schedule(),
        target_calories=1910,
        day_number=1,
    )
    assert first_day is not None
    assert first_error is None

    second_day, _ = demo_pipeline._find_plan_combination(
        recipes=recipes,
        schedule=_schedule(),
        target_calories=1910,
        day_number=2,
        blocked_signatures={demo_pipeline._plan_signature(first_day)},
    )
    assert second_day is not None
    assert demo_pipeline._plan_signature(second_day) != demo_pipeline._plan_signature(first_day)
