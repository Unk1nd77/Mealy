"""Relational persistence helpers for the normalized PostgreSQL domain model."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    DEFAULT_MEAL_SCHEDULE,
    GenerationRun,
    GenerationRunStep,
    MealPlan,
    MealPlanDay,
    MealPlanEvent,
    MealPlanMeal,
    MealPlanMealIngredient,
    MealScheduleSlot,
    Recipe,
    RecipeAllergen,
    RecipeIngredient,
    RecipeTag,
    User,
    UserAllergy,
    UserDisease,
    UserDislikedIngredient,
    UserPreference,
)


def _clean_strings(values: Iterable[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = str(value).strip()
        key = item.lower()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned


def _parse_time(value: str | time | None) -> time | None:
    if isinstance(value, time):
        return value
    if not value:
        return None
    return time.fromisoformat(str(value))


def _format_time(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def _profile_from_user_object(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email,
        "gender": user.gender.value,
        "activity_level": user.activity_level.value,
        "age": user.age,
        "weight_kg": user.weight_kg,
        "height_cm": user.height_cm,
        "goal": user.goal.value,
        "target_calories": user.target_calories,
        "allergies": getattr(user, "allergies", None) or [],
        "preferences": getattr(user, "preferences", None) or [],
        "disliked_ingredients": getattr(user, "disliked_ingredients", None) or [],
        "diseases": getattr(user, "diseases", None) or [],
        "meal_schedule": getattr(user, "meal_schedule", None) or DEFAULT_MEAL_SCHEDULE,
        "created_at": user.created_at,
    }


async def sync_user_normalized(
    session: AsyncSession,
    user: User,
    *,
    allergies: list[str] | None,
    preferences: list[str] | None,
    disliked_ingredients: list[str] | None,
    diseases: list[str] | None,
    meal_schedule: list[dict[str, Any]] | None,
) -> None:
    """Mirror profile lists/schedule into normalized rows."""
    if not isinstance(session, AsyncSession):
        user.allergies = _clean_strings(allergies)
        user.preferences = _clean_strings(preferences)
        user.disliked_ingredients = _clean_strings(disliked_ingredients)
        user.diseases = _clean_strings(diseases)
        user.meal_schedule = meal_schedule or DEFAULT_MEAL_SCHEDULE
        return
    await session.flush()
    user_id = user.id

    for model in (
        UserAllergy,
        UserPreference,
        UserDislikedIngredient,
        UserDisease,
        MealScheduleSlot,
    ):
        await session.execute(delete(model).where(model.user_id == user_id))

    session.add_all(
        UserAllergy(user_id=user_id, allergen=value) for value in _clean_strings(allergies)
    )
    session.add_all(
        UserPreference(user_id=user_id, preference=value) for value in _clean_strings(preferences)
    )
    session.add_all(
        UserDislikedIngredient(user_id=user_id, ingredient=value)
        for value in _clean_strings(disliked_ingredients)
    )
    session.add_all(
        UserDisease(user_id=user_id, disease=value) for value in _clean_strings(diseases)
    )

    schedule = meal_schedule or DEFAULT_MEAL_SCHEDULE
    for index, slot in enumerate(schedule, start=1):
        planned_time = _parse_time(slot.get("time") or slot.get("planned_time"))
        if planned_time is None:
            continue
        session.add(
            MealScheduleSlot(
                user_id=user_id,
                slot_order=index,
                meal_type=str(slot["type"]),
                planned_time=planned_time,
                calories_pct=int(slot["calories_pct"]),
            )
        )


async def load_user_profile_from_rows(session: AsyncSession, user: User) -> dict[str, Any]:
    """Build the canonical user profile dict from normalized rows with legacy fallback."""
    user_id = user.id
    if not isinstance(session, AsyncSession):
        return _profile_from_user_object(user)
    allergies = [
        row.allergen
        for row in (
            await session.execute(
                select(UserAllergy)
                .where(UserAllergy.user_id == user_id)
                .order_by(UserAllergy.allergen)
            )
        ).scalars()
    ]
    preferences = [
        row.preference
        for row in (
            await session.execute(
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
                .order_by(UserPreference.preference)
            )
        ).scalars()
    ]
    disliked = [
        row.ingredient
        for row in (
            await session.execute(
                select(UserDislikedIngredient)
                .where(UserDislikedIngredient.user_id == user_id)
                .order_by(UserDislikedIngredient.ingredient)
            )
        ).scalars()
    ]
    diseases = [
        row.disease
        for row in (
            await session.execute(
                select(UserDisease)
                .where(UserDisease.user_id == user_id)
                .order_by(UserDisease.disease)
            )
        ).scalars()
    ]
    schedule_rows = (
        await session.execute(
            select(MealScheduleSlot)
            .where(MealScheduleSlot.user_id == user_id)
            .order_by(MealScheduleSlot.slot_order)
        )
    ).scalars()
    meal_schedule = [
        {
            "type": row.meal_type,
            "time": _format_time(row.planned_time),
            "calories_pct": row.calories_pct,
        }
        for row in schedule_rows
    ]

    return {
        "id": str(user.id),
        "email": user.email,
        "gender": user.gender.value,
        "activity_level": user.activity_level.value,
        "age": user.age,
        "weight_kg": user.weight_kg,
        "height_cm": user.height_cm,
        "goal": user.goal.value,
        "target_calories": user.target_calories,
        "allergies": allergies,
        "preferences": preferences,
        "disliked_ingredients": disliked,
        "diseases": diseases,
        "meal_schedule": meal_schedule or DEFAULT_MEAL_SCHEDULE,
        "created_at": user.created_at,
    }


async def sync_recipe_normalized(
    session: AsyncSession,
    recipe: Recipe,
    *,
    ingredients: list[dict[str, Any]],
    tags: list[str] | None,
    allergens: list[str] | None,
) -> None:
    """Mirror recipe ingredients/tags/allergens into normalized rows."""
    if not isinstance(session, AsyncSession):
        return
    await session.flush()
    recipe_id = recipe.id
    for model in (RecipeIngredient, RecipeTag, RecipeAllergen):
        await session.execute(delete(model).where(model.recipe_id == recipe_id))

    for index, ingredient in enumerate(ingredients or [], start=1):
        session.add(
            RecipeIngredient(
                recipe_id=recipe_id,
                position=index,
                name=str(ingredient["name"]),
                amount=float(ingredient["amount"]),
                unit=str(ingredient["unit"]),
            )
        )
    session.add_all(RecipeTag(recipe_id=recipe_id, tag=tag) for tag in _clean_strings(tags))
    session.add_all(
        RecipeAllergen(recipe_id=recipe_id, allergen=allergen)
        for allergen in _clean_strings(allergens)
    )


def recipe_to_dict(recipe: Recipe) -> dict[str, Any]:
    """Serialize a Recipe using normalized child rows."""
    ingredients = [
        {"name": item.name, "amount": item.amount, "unit": item.unit}
        for item in recipe.normalized_ingredients
    ]
    tags = [item.tag for item in recipe.normalized_tags]
    allergens = [item.allergen for item in recipe.normalized_allergens]
    return {
        "id": str(recipe.id),
        "title": recipe.title,
        "description": recipe.description,
        "ingredients": ingredients,
        "calories": recipe.calories,
        "protein": recipe.protein,
        "fat": recipe.fat,
        "carbs": recipe.carbs,
        "tags": tags,
        "meal_type": recipe.meal_type,
        "allergens": allergens,
        "ingredients_short": recipe.ingredients_short or "",
        "prep_time_min": recipe.prep_time_min,
        "category": recipe.category,
    }


async def load_recipes_from_rows(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(
        select(Recipe).options(
            selectinload(Recipe.normalized_ingredients),
            selectinload(Recipe.normalized_tags),
            selectinload(Recipe.normalized_allergens),
        )
    )
    return [recipe_to_dict(recipe) for recipe in result.scalars().all()]


async def sync_plan_rows(
    session: AsyncSession,
    *,
    plan_record: MealPlan,
    plan_data: dict[str, Any],
    event_type: str = "created",
) -> None:
    """Persist a generated plan into normalized day/meal/ingredient rows."""
    await session.flush()
    await session.execute(delete(MealPlanDay).where(MealPlanDay.meal_plan_id == plan_record.id))

    start_date = plan_record.start_date
    for day in plan_data.get("days", []):
        day_number = int(day["day_number"])
        plan_date = start_date + timedelta(days=day_number - 1) if start_date else None
        day_row = MealPlanDay(
            meal_plan_id=plan_record.id,
            day_number=day_number,
            plan_date=plan_date,
            total_calories=float(day.get("total_calories") or 0),
            total_protein=float(day.get("total_protein") or 0),
            total_fat=float(day.get("total_fat") or 0),
            total_carbs=float(day.get("total_carbs") or 0),
        )
        session.add(day_row)
        await session.flush()

        for meal in day.get("meals", []):
            raw_recipe_id = str(meal.get("recipe_id") or "")
            try:
                recipe_id = uuid.UUID(raw_recipe_id.split("::", 1)[0])
            except ValueError:
                recipe_id = None
            meal_row = MealPlanMeal(
                day_id=day_row.id,
                recipe_id=recipe_id,
                meal_type=str(meal["type"]),
                planned_time=_parse_time(meal.get("time")),
                title_snapshot=str(meal.get("title") or ""),
                calories=float(meal.get("calories") or 0),
                protein=float(meal.get("protein") or 0),
                fat=float(meal.get("fat") or 0),
                carbs=float(meal.get("carbs") or 0),
                portion_factor=float(meal.get("portion_factor") or 1),
            )
            session.add(meal_row)
            await session.flush()
            for index, ingredient in enumerate(meal.get("ingredients_summary") or [], start=1):
                session.add(
                    MealPlanMealIngredient(
                        meal_id=meal_row.id,
                        position=index,
                        ingredient_name=str(ingredient["name"]),
                        amount=float(ingredient["amount"]),
                        unit=str(ingredient["unit"]),
                    )
                )

    session.add(
        MealPlanEvent(
            meal_plan_id=plan_record.id,
            event_type=event_type,
            actor_type="backend",
            reason=f"Persisted normalized rows for {len(plan_data.get('days', []))} day(s)",
        )
    )


async def build_plan_data_from_rows(
    session: AsyncSession,
    plan: MealPlan,
    *,
    fallback_plan_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Rebuild API-compatible plan data from normalized rows."""
    if not isinstance(session, AsyncSession):
        return fallback_plan_data
    result = await session.execute(
        select(MealPlanDay)
        .where(MealPlanDay.meal_plan_id == plan.id)
        .options(
            selectinload(MealPlanDay.meals).selectinload(MealPlanMeal.ingredients),
        )
        .order_by(MealPlanDay.day_number)
    )
    day_rows = list(result.scalars().all())
    if not day_rows:
        return fallback_plan_data

    user = await session.get(User, plan.user_id)
    user_profile = await load_user_profile_from_rows(session, user) if user else None

    days: list[dict[str, Any]] = []
    for day in day_rows:
        meals = [
            {
                "type": meal.meal_type,
                "time": _format_time(meal.planned_time),
                "recipe_id": str(meal.recipe_id) if meal.recipe_id else None,
                "title": meal.title_snapshot,
                "calories": meal.calories,
                "protein": meal.protein,
                "fat": meal.fat,
                "carbs": meal.carbs,
                "portion_factor": meal.portion_factor,
                "ingredients_summary": [
                    {
                        "name": ingredient.ingredient_name,
                        "amount": ingredient.amount,
                        "unit": ingredient.unit,
                    }
                    for ingredient in meal.ingredients
                ],
            }
            for meal in day.meals
        ]
        days.append(
            {
                "day_number": day.day_number,
                "total_calories": day.total_calories,
                "total_protein": day.total_protein,
                "total_fat": day.total_fat,
                "total_carbs": day.total_carbs,
                "meals": meals,
            }
        )

    return {
        "user_profile": user_profile,
        "total_days": len(days),
        "daily_target_calories": user_profile.get("target_calories") if user_profile else None,
        "days": days,
        "generation_meta": {},
    }


async def create_generation_run(
    session: AsyncSession,
    *,
    user_id: str,
    mode: str,
    task_id: str | None = None,
    status: str = "GENERATING",
) -> GenerationRun:
    run = GenerationRun(
        user_id=uuid.UUID(user_id),
        task_id=task_id,
        mode=mode,
        status=status,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def finalize_generation_run(
    session: AsyncSession,
    *,
    generation_run_id: uuid.UUID | None,
    meal_plan_id: uuid.UUID | None,
    status: str,
    quality_status: str | None,
    steps: list[dict[str, Any]],
    error_message: str | None = None,
) -> None:
    if generation_run_id is None:
        return
    run = await session.get(GenerationRun, generation_run_id)
    if run is None:
        return
    run.meal_plan_id = meal_plan_id
    run.status = status
    run.quality_status = quality_status
    run.error_message = error_message
    run.finished_at = datetime.utcnow()
    await session.execute(
        delete(GenerationRunStep).where(GenerationRunStep.generation_run_id == generation_run_id)
    )
    for step in steps:
        session.add(
            GenerationRunStep(
                generation_run_id=generation_run_id,
                step_key=str(step.get("key") or ""),
                status=str(step.get("status") or ""),
                message=step.get("message"),
            )
        )
    await session.commit()


async def finalize_generation_run_by_task_id(
    session: AsyncSession,
    *,
    task_id: str,
    result: dict[str, Any],
) -> None:
    run = (
        await session.execute(select(GenerationRun).where(GenerationRun.task_id == task_id))
    ).scalar_one_or_none()
    if run is None:
        return
    plan_id = result.get("plan_id")
    await finalize_generation_run(
        session,
        generation_run_id=run.id,
        meal_plan_id=uuid.UUID(plan_id) if plan_id else None,
        status=str(result.get("status") or "FAILED"),
        quality_status=result.get("quality_status"),
        steps=result.get("steps") or [],
        error_message=result.get("error"),
    )
