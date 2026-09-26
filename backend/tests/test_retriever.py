"""Тесты retriever cache recovery."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

os.environ["DEBUG"] = "true"

import pytest

from app.core.rag import retriever


def test_infer_meal_type_from_tags_for_cached_recipe():
    recipe = {
        "title": "Овсяная каша с ягодами",
        "tags": ["завтрак", "быстро"],
        "meal_type": None,
    }

    normalized = retriever._normalize_cached_recipe(recipe)

    assert normalized["meal_type"] == "breakfast"


@pytest.mark.asyncio
async def test_get_all_recipes_normalizes_cache_without_rebuild_when_possible(monkeypatch):
    stale_cache = [{"title": "Паста", "tags": [], "meal_type": None}]

    get_json = AsyncMock(return_value=stale_cache)
    delete = AsyncMock()
    load_all = AsyncMock()

    monkeypatch.setattr(retriever.cache, "get_json", get_json)
    monkeypatch.setattr(retriever.cache, "delete", delete)
    monkeypatch.setattr(retriever, "_load_all_recipes", load_all)

    result = await retriever._get_all_recipes(SimpleNamespace())

    assert result == [{"title": "Паста", "tags": [], "meal_type": "universal"}]
    delete.assert_not_awaited()
    load_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_recipes_keeps_preferred_first_but_preserves_safe_fallback(monkeypatch):
    recipes = [
        {
            "id": "1",
            "title": "Protein Lunch",
            "tags": ["высокобелковый"],
            "allergens": [],
            "ingredients_short": "",
        },
        {
            "id": "2",
            "title": "Safe Breakfast",
            "tags": ["завтрак"],
            "allergens": [],
            "ingredients_short": "",
        },
        {
            "id": "3",
            "title": "Safe Snack",
            "tags": ["перекус"],
            "allergens": [],
            "ingredients_short": "",
        },
    ]

    monkeypatch.setattr(retriever, "_get_all_recipes", AsyncMock(return_value=recipes))

    result = await retriever.search_recipes(
        SimpleNamespace(),
        preferred_tags=["высокобелковый"],
        limit=3,
    )

    assert [recipe["id"] for recipe in result] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_vector_ranking_never_bypasses_allergen_filter(monkeypatch):
    ranked = [
        {
            "id": "unsafe",
            "title": "Ореховый десерт",
            "tags": ["десерт"],
            "allergens": ["nuts"],
            "ingredients_short": "миндаль",
            "_semantic_similarity": 0.99,
        },
        {
            "id": "safe",
            "title": "Запеченная рыба",
            "tags": ["ужин"],
            "allergens": ["fish"],
            "ingredients_short": "рыба, лимон",
            "_semantic_similarity": 0.71,
        },
    ]
    monkeypatch.setattr(
        retriever,
        "_get_hybrid_recipe_order",
        AsyncMock(return_value=(ranked, True)),
    )

    result = await retriever.search_recipes(
        SimpleNamespace(),
        allergies=["орехи"],
        semantic_query="полезный десерт или ужин",
    )

    assert [recipe["id"] for recipe in result] == ["safe"]


def test_assess_recipe_pool_requires_weekly_adjacent_day_variety_and_calorie_reachability():
    user_profile = {
        "target_calories": 2000,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 35},
            {"type": "dinner", "time": "19:00", "calories_pct": 30},
            {"type": "snack", "time": "16:00", "calories_pct": 10},
        ],
    }
    recipes = [
        {"id": "b1", "title": "Breakfast 1", "meal_type": "breakfast", "calories": 450},
        {"id": "b2", "title": "Breakfast 2", "meal_type": "breakfast", "calories": 500},
        {"id": "l1", "title": "Lunch 1", "meal_type": "lunch", "calories": 650},
        {"id": "l2", "title": "Lunch 2", "meal_type": "lunch", "calories": 700},
        {"id": "d1", "title": "Dinner 1", "meal_type": "dinner", "calories": 550},
        {"id": "d2", "title": "Dinner 2", "meal_type": "dinner", "calories": 600},
        {"id": "s1", "title": "Snack 1", "meal_type": "snack", "calories": 180},
        {"id": "s2", "title": "Snack 2", "meal_type": "snack", "calories": 220},
    ]

    diagnostics = retriever.assess_recipe_pool(
        recipes, user_profile=user_profile, min_recipes_per_slot=2
    )

    assert diagnostics["feasible"] is True
    assert diagnostics["missing_slots"] == []
    assert diagnostics["slot_counts"] == {
        "breakfast": 2,
        "lunch": 2,
        "dinner": 2,
        "snack": 2,
    }
    assert diagnostics["min_achievable_calories"] <= 2100
    assert diagnostics["max_achievable_calories"] >= 1900


def test_assess_recipe_pool_reports_missing_slots():
    user_profile = {
        "target_calories": 1900,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 35},
            {"type": "dinner", "time": "19:00", "calories_pct": 30},
            {"type": "snack", "time": "16:00", "calories_pct": 10},
        ],
    }
    recipes = [
        {"id": "s1", "title": "Brownie", "meal_type": "snack", "calories": 676},
    ]

    diagnostics = retriever.assess_recipe_pool(
        recipes, user_profile=user_profile, min_recipes_per_slot=1
    )

    assert diagnostics["feasible"] is False
    assert diagnostics["missing_slots"] == ["breakfast", "lunch", "dinner"]
