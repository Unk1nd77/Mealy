"""Recipe identity, slot and cross-day guards shared by generation and repair."""

from typing import Any

from app.core.meal_compatibility import recipe_type_matches


def _recipe_base_id(recipe: dict[str, Any]) -> str:
    base_id = recipe.get("base_recipe_id")
    if base_id:
        return str(base_id)
    recipe_id = str(recipe.get("id"))
    return recipe_id.split("::", 1)[0]


def _meal_base_id(meal: dict[str, Any]) -> str:
    recipe_id = str(meal.get("recipe_id"))
    return recipe_id.split("::", 1)[0]


def _meal_base_id_from_recipes(
    meal: dict[str, Any], recipes_by_id: dict[str, dict[str, Any]]
) -> str:
    recipe = recipes_by_id.get(str(meal.get("recipe_id")))
    if recipe is not None:
        return _recipe_base_id(recipe)
    return _meal_base_id(meal)


def _collect_used_recipe_base_ids(
    *,
    days: list[dict[str, Any]],
    recipes_by_day: dict[int, list[dict[str, Any]]],
) -> set[str]:
    used: set[str] = set()
    for day in days:
        day_number = int(day["day_number"])
        recipes_by_id = {str(recipe["id"]): recipe for recipe in recipes_by_day.get(day_number, [])}
        for meal in day.get("meals", []):
            used.add(_meal_base_id_from_recipes(meal, recipes_by_id))
    return used


def _validate_day_recipe_usage(
    *,
    day_plan: dict[str, Any],
    recipes: list[dict[str, Any]],
    previous_recipe_base_ids: set[str] | None = None,
    allow_universal: bool = False,
) -> str | None:
    recipes_by_id = {str(recipe["id"]): recipe for recipe in recipes}

    for meal in day_plan.get("meals", []):
        recipe = recipes_by_id.get(str(meal.get("recipe_id")))
        if recipe is None:
            return f"Рецепт {meal.get('recipe_id')} отсутствует в доступном контексте."

        if not recipe_type_matches(
            recipe.get("meal_type"),
            str(meal.get("type")),
            allow_universal=allow_universal,
        ):
            return (
                f"Рецепт '{recipe.get('title')}' с meal_type={recipe.get('meal_type')} "
                f"нельзя использовать для слота {meal.get('type')}."
            )

        if previous_recipe_base_ids and _recipe_base_id(recipe) in previous_recipe_base_ids:
            return f"Повтор блюда между днями: {recipe.get('title')}"

    return None
