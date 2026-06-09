"""Оркестратор генерации плана питания.

Пайплайн: Профиль → RAG → LLM (Structured Output) → Валидация → [Рефлексия] → Результат.
Ингредиенты подставляются post-hoc из данных рецепта, не от LLM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from jinja2 import Template
from loguru import logger
from pydantic import ValidationError

from app.config import settings
from app.core.agent.schemas import DayPlan, DayPlanFull, MealItemFull, MealPlanOutput
from app.core.skills.validator import validate_day_plan

PROMPTS_DIR = Path(__file__).parent / "prompts"
MAX_RETRIES = settings.LLM_MAX_RETRIES
OBSERVABILITY_TOLERANCE_PCT = 5.0
OBSERVABILITY_MESSAGE_LIMIT = 220


@dataclass
class GeneratedDayResult:
    plan: DayPlanFull
    quality_status: str
    attempts_used: int
    validation_error: str | None = None


def _sanitize_observability_step(raw_step: object, fallback_index: int) -> dict[str, str]:
    if not isinstance(raw_step, dict):
        return {
            "key": f"step-{fallback_index}",
            "status": "completed",
            "message": "Generation stage completed.",
        }

    key = str(raw_step.get("key") or raw_step.get("stage") or f"step-{fallback_index}")
    status = str(raw_step.get("status") or "completed").lower()
    message = str(raw_step.get("message") or raw_step.get("summary") or "").strip()
    if not message:
        message = "Generation stage completed."
    if len(message) > OBSERVABILITY_MESSAGE_LIMIT:
        message = f"{message[: OBSERVABILITY_MESSAGE_LIMIT - 1].rstrip()}…"

    return {
        "key": key,
        "status": status,
        "message": message,
    }


def _load_prompt() -> dict[str, Template]:
    with (PROMPTS_DIR / "meal_plan.yml").open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {key: Template(val) for key, val in raw.items()}


def _build_system_prompt(
    templates: dict[str, Template],
    user_profile: dict,
    recipes: list[dict],
    *,
    previous_day_titles: list[str] | None = None,
    avoid_recipe_ids: list[str] | None = None,
) -> str:
    recipe_dicts = [
        {
            "id": r["id"] if isinstance(r, dict) else str(r.id),
            "title": r["title"] if isinstance(r, dict) else r.title,
            "calories": r["calories"] if isinstance(r, dict) else r.calories,
            "protein": r["protein"] if isinstance(r, dict) else r.protein,
            "fat": r["fat"] if isinstance(r, dict) else r.fat,
            "carbs": r["carbs"] if isinstance(r, dict) else r.carbs,
            "tags": (r.get("tags") if isinstance(r, dict) else r.tags) or [],
            "meal_type": (
                r.get("meal_type") if isinstance(r, dict) else getattr(r, "meal_type", None)
            )
            or "universal",
            "ingredients_short": (
                r.get("ingredients_short")
                if isinstance(r, dict)
                else getattr(r, "ingredients_short", None)
            )
            or "",
        }
        for r in recipes
    ]
    return templates["system"].render(
        **user_profile,
        recipes=recipe_dicts,
        previous_day_titles=previous_day_titles or [],
        avoid_recipe_ids=avoid_recipe_ids or [],
    )


async def _call_llm(messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.LLM_MODEL_NAME,
                "messages": messages,
                "temperature": 0,
                "max_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def _append_retry_feedback(
    messages: list[dict[str, Any]], assistant_raw: str, feedback: str
) -> None:
    preview = assistant_raw.strip()
    if len(preview) > settings.LLM_RETRY_RESPONSE_PREVIEW_CHARS:
        preview = f"{preview[: settings.LLM_RETRY_RESPONSE_PREVIEW_CHARS]}..."
    if preview:
        messages.append({"role": "assistant", "content": preview})
    messages.append({"role": "user", "content": feedback})
    retry_pairs = messages[2:]
    keep = settings.LLM_RETRY_HISTORY_LIMIT * 2
    if keep > 0 and len(retry_pairs) > keep:
        del messages[2 : len(messages) - keep]


def _parse_response(raw: str) -> MealPlanOutput:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        cleaned = "\n".join(lines)
    return MealPlanOutput.model_validate_json(cleaned)


def _enrich_day_plan(plan: DayPlan, recipes: list[dict]) -> DayPlanFull:
    """Post-hoc: подставляет ингредиенты из рецептов вместо LLM-генерации."""
    recipes_by_id = {r["id"] if isinstance(r, dict) else str(r.id): r for r in recipes}

    enriched_meals = []
    for meal in plan.meals:
        recipe = recipes_by_id.get(meal.recipe_id)
        ingredients = []
        if recipe:
            raw_ingredients = (
                recipe["ingredients"] if isinstance(recipe, dict) else recipe.ingredients
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


async def generate_day_plan(
    user_profile: dict,
    recipes: list[dict],
    day_number: int = 1,
    *,
    previous_day_titles: list[str] | None = None,
    avoid_recipe_ids: set[str] | None = None,
) -> GeneratedDayResult:
    """Генерирует план на 1 день с циклом рефлексии.

    Args:
        user_profile: dict с полями gender, age, weight_kg, height_cm, goal,
                      target_calories, allergies, preferences,
                      disliked_ingredients, diseases
        recipes: список рецептов из RAG (dict или ORM-объекты)
        day_number: номер дня

    Returns:
        DayPlanFull с ингредиентами из рецептов (не от LLM)
    """
    if not recipes:
        raise RuntimeError("No recipes available for generation after profile filters")

    recipe_context_limit = max(
        settings.LLM_CONTEXT_RECIPE_LIMIT,
        settings.AGENT_CLI_MIN_CONTEXT_RECIPE_LIMIT,
    )
    # Sort: unused recipes first, then by title for stability.
    # This ensures the LLM sees fresh options at the top even when
    # recipe_context_limit < total available recipes.
    avoid_ids = avoid_recipe_ids or set()
    sorted_recipes = sorted(
        recipes,
        key=lambda r: (
            1 if str(r["id"] if isinstance(r, dict) else r.id).split("::", 1)[0] in avoid_ids else 0,
            r["title"] if isinstance(r, dict) else r.title,
        ),
    )
    bounded_recipes = sorted_recipes[:recipe_context_limit]

    templates = _load_prompt()
    system_prompt = _build_system_prompt(
        templates,
        user_profile,
        bounded_recipes,
        previous_day_titles=previous_day_titles,
        avoid_recipe_ids=sorted(avoid_recipe_ids or []),
    )
    target_cal = user_profile["target_calories"]

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Составь план питания на день {day_number}. "
                "Верни только JSON-объект c ключами daily_target_calories и day. "
                "Ключ day должен быть объектом, не строкой."
            ),
        },
    ]

    best_plan: DayPlan | None = None
    best_deviation = float("inf")

    for attempt in range(1, MAX_RETRIES + 1):
        logger.info("Generation attempt {}/{} for day {}", attempt, MAX_RETRIES, day_number)

        raw_response = ""
        try:
            raw_response = await _call_llm(messages)
            logger.debug("LLM raw response (attempt {}): {}", attempt, raw_response[:500])

            output = _parse_response(raw_response)
            plan = output.day
            plan.day_number = day_number
            plan = _normalize_day_totals(plan)

        except httpx.HTTPError as e:
            logger.error("LLM request failed on attempt {}: {}", attempt, e)
            _append_retry_feedback(
                messages,
                raw_response,
                "Ошибка запроса к LLM. Повтори генерацию в корректном JSON по заданной схеме.",
            )
            continue
        except (ValidationError, json.JSONDecodeError, KeyError) as e:
            logger.error("Parse error on attempt {}: {}", attempt, e)
            _append_retry_feedback(
                messages,
                raw_response,
                f"Ошибка парсинга: {e}. Верни корректный JSON согласно схеме.",
            )
            continue

        meal_schedule = user_profile.get("meal_schedule")
        is_valid, error_msg = validate_day_plan(plan, target_cal, meal_schedule=meal_schedule)
        current_deviation = abs(plan.total_calories - target_cal)

        if current_deviation < best_deviation:
            best_plan = plan
            best_deviation = current_deviation

        if is_valid:
            logger.info("Day {} generated successfully on attempt {}", day_number, attempt)
            return GeneratedDayResult(
                plan=_enrich_day_plan(plan, bounded_recipes),
                quality_status="valid",
                attempts_used=attempt,
            )

        logger.warning("Validation failed on attempt {}: {}", attempt, error_msg)

        retry_prompt = templates["retry"].render(
            validation_error=error_msg,
            target_calories=target_cal,
        )
        _append_retry_feedback(messages, raw_response, retry_prompt)

    if best_plan:
        logger.warning(
            "Returning best plan after {} attempts (deviation: {:.0f} kcal)",
            MAX_RETRIES,
            best_deviation,
        )
        return GeneratedDayResult(
            plan=_enrich_day_plan(best_plan, bounded_recipes),
            quality_status="partially_valid",
            attempts_used=MAX_RETRIES,
            validation_error=(
                f"Не удалось получить полностью валидный план за {MAX_RETRIES} попытки, "
                f"возвращён лучший доступный вариант."
            ),
        )

    raise RuntimeError(f"Failed to generate valid plan after {MAX_RETRIES} attempts")


def build_plan_observability(plan_data: dict | None) -> dict[str, Any]:
    if not isinstance(plan_data, dict):
        return {
            "source": "derived_plan",
            "summary": "Generation diagnostics are unavailable for this plan.",
            "steps": [],
            "day_checks": [],
            "has_persisted_trace": False,
        }

    target_calories = int(plan_data.get("daily_target_calories") or 0)
    days = plan_data.get("days") if isinstance(plan_data.get("days"), list) else []
    stored_trace = (
        plan_data.get("generation_trace")
        if isinstance(plan_data.get("generation_trace"), list)
        else []
    )

    day_checks = []
    days_within_target = 0
    worst_deviation_pct = 0.0

    for day in days:
        if not isinstance(day, dict):
            continue
        total_calories = float(day.get("total_calories") or 0)
        deviation_kcal = abs(total_calories - target_calories) if target_calories > 0 else 0.0
        deviation_pct = (deviation_kcal / target_calories * 100) if target_calories > 0 else 0.0
        within_target = (
            deviation_pct <= OBSERVABILITY_TOLERANCE_PCT if target_calories > 0 else False
        )
        if within_target:
            days_within_target += 1
        worst_deviation_pct = max(worst_deviation_pct, deviation_pct)
        day_checks.append(
            {
                "day_number": int(day.get("day_number") or 0),
                "total_calories": round(total_calories, 1),
                "target_calories": target_calories,
                "deviation_kcal": round(deviation_kcal, 1),
                "deviation_pct": round(deviation_pct, 1),
                "within_target": within_target,
            }
        )

    if stored_trace:
        steps = [
            _sanitize_observability_step(raw_step, index)
            for index, raw_step in enumerate(stored_trace, start=1)
        ]
        source = "stored_plan"
    else:
        validation_message = (
            f"Saved plan stayed within {OBSERVABILITY_TOLERANCE_PCT:.0f}% of the target on all {days_within_target} day(s)."
            if day_checks and days_within_target == len(day_checks)
            else (
                f"Saved plan exceeded the {OBSERVABILITY_TOLERANCE_PCT:.0f}% target tolerance on "
                f"{len(day_checks) - days_within_target} day(s)."
                if day_checks
                else "No saved day diagnostics are available."
            )
        )
        steps = [
            {
                "key": "context",
                "status": "completed",
                "message": "Profile constraints and recipe candidates were applied before generation.",
            },
            {
                "key": "generate",
                "status": "completed" if day_checks else "pending",
                "message": f"Weekly plan contains {len(day_checks)} generated day(s).",
            },
            {
                "key": "validate",
                "status": "completed" if day_checks else "pending",
                "message": validation_message,
            },
            {
                "key": "reflection",
                "status": "limited",
                "message": "Raw prompts and model replies are intentionally omitted; this view shows safe post-run diagnostics only.",
            },
        ]
        source = "derived_plan"

    summary = (
        f"{days_within_target}/{len(day_checks)} day(s) are within the {OBSERVABILITY_TOLERANCE_PCT:.0f}% target band."
        if day_checks
        else "No generation diagnostics are available for this plan."
    )
    if day_checks:
        summary = f"{summary} Worst deviation: {worst_deviation_pct:.1f}%."

    return {
        "source": source,
        "summary": summary,
        "steps": steps,
        "day_checks": day_checks,
        "has_persisted_trace": bool(stored_trace),
    }
