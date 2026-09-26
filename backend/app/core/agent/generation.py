"""Shared sequential day/week generation without transport or persistence policy.

The production agentic use case generates days sequentially and carries only
previous-day recipe history so non-adjacent repeats remain available.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.agent.contracts import GeneratedDayResult
from app.core.recipe_usage import _meal_base_id_from_recipes, _recipe_base_id


@dataclass
class GeneratedPlanDraft:
    user_profile: dict | None = None
    days: list[dict] = field(default_factory=list)
    day_metadata: list[dict] = field(default_factory=list)
    quality_status: str = "valid"
    warnings: list[str] = field(default_factory=list)
    recipes_by_day: dict[int, list[dict]] = field(default_factory=dict)
    avoid_recipe_ids_by_day: dict[int, set[str]] = field(default_factory=dict)


async def generate_days(
    days: int,
    *,
    load_context: Callable[[int], Awaitable[dict[str, Any]]],
    generate_day: Callable[..., Awaitable[GeneratedDayResult]],
    use_collected_recipes: bool,
    carry_history: bool,
    draft: GeneratedPlanDraft,
) -> GeneratedPlanDraft:
    """The same interface for one day and a week; errors propagate to the adapter.

    The mutable draft preserves warnings produced before a later day fails. It is
    request-local, never persisted here, and not a substitute for final validation.
    """
    previous_day_recipe_ids: set[str] = set()
    previous_titles: list[str] = []
    for day_number in range(1, days + 1):
        context = await load_context(day_number)
        draft.user_profile = context["user"]
        recipes = context["available_recipes"]
        if carry_history:
            recipes = sorted(
                recipes,
                key=lambda recipe: (
                    _recipe_base_id(recipe) in previous_day_recipe_ids,
                    recipe.get("title", ""),
                ),
            )
        draft.avoid_recipe_ids_by_day[day_number] = set(previous_day_recipe_ids)
        history = (
            {
                "previous_day_titles": previous_titles,
                "avoid_recipe_ids": previous_day_recipe_ids,
            }
            if carry_history
            else {}
        )
        result = await generate_day(context["user"], recipes, day_number=day_number, **history)
        if use_collected_recipes:
            recipes = result.collected_recipes
        draft.recipes_by_day[day_number] = recipes
        draft.days.append(result.plan.model_dump())
        draft.day_metadata.append(
            {
                "day_number": day_number,
                "quality_status": result.quality_status,
                "attempts_used": result.attempts_used,
                "validation_error": result.validation_error,
                "tool_call_trace": result.tool_call_trace,
            }
        )
        if result.quality_status != "valid":
            draft.quality_status = "partially_valid"
        if result.validation_error:
            draft.warnings.append(f"Day {day_number}: {result.validation_error}")
        if carry_history:
            recipes_by_id = {str(recipe["id"]): recipe for recipe in recipes}
            previous_day_recipe_ids = {
                _meal_base_id_from_recipes(meal, recipes_by_id)
                for meal in draft.days[-1].get("meals", [])
            }
            previous_titles = [
                meal.get("title", "") for meal in draft.days[-1].get("meals", [])
            ]
    return draft
