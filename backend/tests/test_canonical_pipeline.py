"""Tests for canonical pipeline recipe selection and scaling."""

from __future__ import annotations

import pytest

from app.core import canonical_pipeline


@pytest.mark.asyncio
async def test_load_candidate_recipes_adds_scaled_variants_for_high_targets(monkeypatch):
    async def fake_search_recipes(session, **kwargs):
        return [
            {
                "id": "breakfast-1",
                "title": "Breakfast Base",
                "description": "",
                "ingredients": [{"name": "Oats", "amount": 100, "unit": "g"}],
                "calories": 350,
                "protein": 15,
                "fat": 8,
                "carbs": 55,
                "tags": [],
                "meal_type": "breakfast",
                "allergens": [],
                "ingredients_short": "Oats",
                "prep_time_min": 10,
                "category": "Breakfast",
            },
            {
                "id": "lunch-1",
                "title": "Lunch Base",
                "description": "",
                "ingredients": [{"name": "Rice", "amount": 200, "unit": "g"}],
                "calories": 700,
                "protein": 30,
                "fat": 15,
                "carbs": 95,
                "tags": [],
                "meal_type": "lunch",
                "allergens": [],
                "ingredients_short": "Rice",
                "prep_time_min": 20,
                "category": "Lunch",
            },
        ]

    monkeypatch.setattr(canonical_pipeline, "search_recipes", fake_search_recipes)

    user_profile = {
        "target_calories": 2600,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 75},
        ],
        "allergies": [],
        "disliked_ingredients": [],
        "preferences": [],
        "diseases": [],
    }

    recipes = await canonical_pipeline.load_candidate_recipes(
        session=None,
        user_profile=user_profile,
        limit=10,
    )

    ids = {str(recipe["id"]) for recipe in recipes}
    assert any("::x" in recipe_id for recipe_id in ids)


def test_assess_recipe_pool_uses_scaled_variants_when_present():
    user_profile = {
        "target_calories": 2600,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 35},
            {"type": "dinner", "time": "19:00", "calories_pct": 30},
            {"type": "snack", "time": "16:00", "calories_pct": 10},
        ],
    }
    recipes = [
        {"id": "b1", "title": "B", "meal_type": "breakfast", "calories": 500},
        {"id": "b1::x1.50", "title": "B x1.50", "meal_type": "breakfast", "calories": 750},
        {"id": "l1", "title": "L", "meal_type": "lunch", "calories": 700},
        {"id": "l1::x1.50", "title": "L x1.50", "meal_type": "lunch", "calories": 1050},
        {"id": "d1", "title": "D", "meal_type": "dinner", "calories": 650},
        {"id": "d1::x1.50", "title": "D x1.50", "meal_type": "dinner", "calories": 975},
        {"id": "s1", "title": "S", "meal_type": "snack", "calories": 220},
    ]

    diagnostics = canonical_pipeline.assess_recipe_pool(recipes, user_profile=user_profile)

    assert diagnostics["feasible"] is True
    assert diagnostics["max_achievable_calories"] >= 2600 * 0.95


@pytest.mark.asyncio
async def test_load_candidate_recipes_passes_profile_constraints_and_supports_goal_target(
    monkeypatch,
):
    captured_kwargs = {}

    async def fake_search_recipes(session, **kwargs):
        captured_kwargs.update(kwargs)
        return [
            {
                "id": "protein-breakfast",
                "title": "Protein Breakfast",
                "description": "",
                "ingredients": [{"name": "Oats", "amount": 100, "unit": "g"}],
                "calories": 420,
                "protein": 35,
                "fat": 10,
                "carbs": 45,
                "tags": ["high protein"],
                "meal_type": "breakfast",
                "allergens": [],
                "ingredients_short": "Oats",
                "prep_time_min": 10,
                "category": "Breakfast",
            },
            {
                "id": "protein-lunch",
                "title": "Protein Lunch",
                "description": "",
                "ingredients": [{"name": "Chicken", "amount": 200, "unit": "g"}],
                "calories": 700,
                "protein": 55,
                "fat": 18,
                "carbs": 70,
                "tags": ["high protein"],
                "meal_type": "lunch",
                "allergens": [],
                "ingredients_short": "Chicken",
                "prep_time_min": 20,
                "category": "Lunch",
            },
            {
                "id": "protein-dinner",
                "title": "Protein Dinner",
                "description": "",
                "ingredients": [{"name": "Fish", "amount": 180, "unit": "g"}],
                "calories": 620,
                "protein": 50,
                "fat": 20,
                "carbs": 55,
                "tags": ["high protein"],
                "meal_type": "dinner",
                "allergens": [],
                "ingredients_short": "Fish",
                "prep_time_min": 20,
                "category": "Dinner",
            },
            {
                "id": "protein-snack",
                "title": "Protein Snack",
                "description": "",
                "ingredients": [{"name": "Yogurt", "amount": 200, "unit": "g"}],
                "calories": 220,
                "protein": 22,
                "fat": 5,
                "carbs": 20,
                "tags": ["high protein"],
                "meal_type": "snack",
                "allergens": [],
                "ingredients_short": "Yogurt",
                "prep_time_min": 5,
                "category": "Snack",
            },
        ]

    monkeypatch.setattr(canonical_pipeline, "search_recipes", fake_search_recipes)

    user_profile = {
        "target_calories": 2600,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 35},
            {"type": "dinner", "time": "19:00", "calories_pct": 30},
            {"type": "snack", "time": "16:00", "calories_pct": 10},
        ],
        "allergies": ["орехи"],
        "disliked_ingredients": ["лук"],
        "preferences": ["high protein"],
        "diseases": ["diabetes"],
    }

    recipes = await canonical_pipeline.load_candidate_recipes(
        session=None,
        user_profile=user_profile,
        limit=8,
    )
    diagnostics = canonical_pipeline.assess_recipe_pool(recipes, user_profile=user_profile)

    assert captured_kwargs["allergies"] == ["орехи"]
    assert captured_kwargs["dislikes"] == ["лук"]
    assert captured_kwargs["preferred_tags"] == ["high protein"]
    assert captured_kwargs["diseases"] == ["diabetes"]
    assert captured_kwargs["limit"] == 24
    assert diagnostics["feasible"] is True
    assert diagnostics["target_calories"] == 2600
    assert any(recipe.get("base_recipe_id") == "protein-lunch" for recipe in recipes)
    assert all("high protein" in recipe["tags"] for recipe in recipes)
