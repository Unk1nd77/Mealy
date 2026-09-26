"""Shared deterministic enrichment and totals (not canonical nutrient validation)."""

from app.core.agent.schemas import DayPlan, DayPlanFull, MealItemFull


def _enrich_day_plan(plan: DayPlan, recipes: list[dict]) -> DayPlanFull:
    """Post-hoc: подставляет ингредиенты из рецептов вместо LLM-генерации."""
    recipes_by_id = {r["id"] if isinstance(r, dict) else str(r.id): r for r in recipes}

    enriched_meals = []
    for meal in plan.meals:
        recipe = recipes_by_id.get(meal.recipe_id)
        ingredients = []
        if recipe:
            raw_ingredients = (
                recipe.get("ingredients") if isinstance(recipe, dict) else recipe.ingredients
            )
            ingredients = [
                {"name": ing["name"], "amount": ing["amount"], "unit": ing["unit"]}
                for ing in (raw_ingredients or [])
            ]

        enriched_meals.append(
            MealItemFull(
                type=meal.type,
                time=meal.time,
                recipe_id=meal.recipe_id,
                title=meal.title,
                calories=meal.calories,
                protein=meal.protein,
                fat=meal.fat,
                carbs=meal.carbs,
                ingredients_summary=ingredients,
            )
        )

    return DayPlanFull(
        day_number=plan.day_number,
        total_calories=plan.total_calories,
        total_protein=plan.total_protein,
        total_fat=plan.total_fat,
        total_carbs=plan.total_carbs,
        meals=enriched_meals,
    )


def _normalize_day_totals(plan: DayPlan) -> DayPlan:
    """Recalculate aggregate day macros from meals before validation/save.

    These totals are deterministic derived fields. Keeping them server-side avoids
    wasting retries on arithmetic drift in the model output.
    """
    plan.total_calories = round(sum(meal.calories for meal in plan.meals))
    plan.total_protein = round(sum(meal.protein for meal in plan.meals), 1)
    plan.total_fat = round(sum(meal.fat for meal in plan.meals), 1)
    plan.total_carbs = round(sum(meal.carbs for meal in plan.meals), 1)
    return plan
