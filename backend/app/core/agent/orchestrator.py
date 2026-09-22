"""Оркестратор генерации плана питания.

Пайплайн: Профиль → RAG → LLM (Structured Output) → Валидация → [Рефлексия] → Результат.
Ингредиенты подставляются post-hoc из данных рецепта, не от LLM.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import yaml
from jinja2 import Template
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.agent.schemas import DayPlan, DayPlanFull, MealItemFull, MealPlanOutput
from app.core.rag import retriever
from app.core.skills.validator import validate_day_plan
from app.db.models import DEFAULT_MEAL_SCHEDULE
from app.db.session import async_session


@dataclass
class AgentSessionState:
    """Tracks mandatory steps completed during one Agentic Loop session."""

    profile_fetched: bool = False
    recipes_fetched: bool = False
    last_validated_hash: str | None = None  # sha256 of last successfully validated plan JSON

    def ready_for_final(self) -> bool:
        return (
            self.profile_fetched and self.recipes_fetched and self.last_validated_hash is not None
        )

    def missing_steps(self) -> list[str]:
        missing = []
        if not self.profile_fetched:
            missing.append("get_user_profile")
        if not self.recipes_fetched:
            missing.append("search_recipes")
        if self.last_validated_hash is None:
            missing.append("validate_day_plan")
        return missing


class AgentLimitError(Exception):
    """Raised when AGENT_MAX_LLM_CALLS is exhausted before a valid final response."""

    def __init__(self, llm_calls: int, pending_tool_call_ids: list[str]):
        self.llm_calls = llm_calls
        self.pending_tool_call_ids = pending_tool_call_ids
        super().__init__(
            f"Agent LLM call limit reached after {llm_calls} calls. "
            f"Pending tool calls: {pending_tool_call_ids}"
        )


class AgentConfigurationError(Exception):
    """Raised on configuration errors (e.g. entering agentic loop with AGENT_TOOL_USE_ENABLED=False)."""


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
    tool_call_trace: list[dict] = field(default_factory=list)
    # Each entry: {"tool": str, "llm_call": int, "args_summary": str}
    collected_recipes: list[dict] = field(default_factory=list, repr=False)


_PROFILE_FIELDS = {
    "target_calories",
    "meal_schedule",
    "allergies",
    "disliked_ingredients",
    "diseases",
    "preferences",
    "goal",
    "user_id",
    "id",
    "gender",
    "age",
    "weight_kg",
    "height_cm",
    "email",
}
_MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "universal"]


def _tool_error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


def _compute_plan_hash(plan_data: Any) -> str:
    canonical = json.dumps(plan_data, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _build_args_summary(args: dict) -> str:
    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items() if k not in _PROFILE_FIELDS}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return str(redact(args))[:200]


def _build_tool_definitions() -> list[dict]:
    day_schema = DayPlan.model_json_schema()
    definitions = day_schema.pop("$defs", {})
    specs = {
        "get_user_profile": (
            "Получить профиль и расписание пользователя. Обязательный первый вызов.",
            {},
            [],
        ),
        "search_recipes": (
            "Семантический поиск рецептов. Ограничения профиля применяются автоматически.",
            {
                "query": {"type": "string", "minLength": 1},
                "meal_type": {"type": "string", "enum": _MEAL_TYPES},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
            },
            ["query"],
        ),
        "validate_day_plan": (
            "Проверить точный черновик дня перед финальным ответом. Исправлять все errors.",
            {"plan": day_schema},
            ["plan"],
        ),
    }
    tools = []
    for name, (description, properties, required) in specs.items():
        if not callable(getattr(ToolExecutor, f"_execute_{name}", None)):
            logger.warning("Agent tool unavailable: {}", name)
            continue
        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }
        if name == "validate_day_plan":
            parameters["$defs"] = definitions
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )
    if not tools:
        raise AgentConfigurationError("No agent tools could be registered")
    return tools


def _build_agentic_system_prompt() -> str:
    return _load_prompt()["system_tool_use"].render()


async def _call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    expect_final: bool,
) -> dict:
    payload = {
        "model": settings.LLM_MODEL_NAME,
        "messages": messages,
        "temperature": 0,
        "max_tokens": settings.LLM_MAX_OUTPUT_TOKENS,
        "tools": tools,
        "tool_choice": "auto",
    }
    if expect_final:
        payload["response_format"] = {"type": "json_object"}
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC) as client:
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()["choices"][0]


@dataclass
class ToolExecutor:
    user_profile: dict | None
    db_session: AsyncSession
    session_state: AgentSessionState = field(default_factory=AgentSessionState)
    search_call_count: int = 0
    collected_recipes: dict[str, dict] = field(default_factory=dict)
    avoid_recipe_ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        # Keep the constraints fixed for the entire session.
        self.user_profile = deepcopy(self.user_profile)
        self.avoid_recipe_ids = set(self.avoid_recipe_ids)

    async def dispatch(self, tool_name: str, arguments: dict) -> dict:
        if tool_name not in {"get_user_profile", "search_recipes", "validate_day_plan"}:
            return _tool_error("UNKNOWN_TOOL", f"Unknown tool: {tool_name}")
        if not isinstance(arguments, dict):
            if tool_name == "validate_day_plan":
                self.session_state.last_validated_hash = None
            return _tool_error("INVALID_ARGUMENTS", "Tool arguments must be a JSON object")
        try:
            if tool_name == "get_user_profile":
                return self._execute_get_user_profile()
            if tool_name == "search_recipes":
                return await self._execute_search_recipes(arguments)
            return self._execute_validate_day_plan(arguments)
        except Exception:
            if tool_name == "validate_day_plan":
                self.session_state.last_validated_hash = None
            logger.exception("Agent tool execution failed: {}", tool_name)
            return _tool_error("TOOL_EXECUTION_ERROR", "Tool execution failed")

    def _execute_get_user_profile(self) -> dict:
        if self.user_profile is None:
            return _tool_error("PROFILE_UNAVAILABLE", "User profile is not available")
        profile = self.user_profile
        result = {
            "target_calories": int(profile["target_calories"]),
            "meal_schedule": deepcopy(profile.get("meal_schedule") or DEFAULT_MEAL_SCHEDULE),
            "goal": str(profile.get("goal") or "maintain"),
            **{
                key: list(profile.get(key) or [])
                for key in (
                    "allergies",
                    "disliked_ingredients",
                    "diseases",
                    "preferences",
                )
            },
        }
        self.session_state.profile_fetched = True
        return result

    async def _execute_search_recipes(self, arguments: dict) -> dict:
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return _tool_error("INVALID_QUERY", "query must not be empty")
        meal_type = arguments.get("meal_type")
        if meal_type is not None and meal_type not in _MEAL_TYPES:
            return _tool_error("INVALID_MEAL_TYPE", f"meal_type must be one of: {_MEAL_TYPES}")
        limit = arguments.get("limit", 10)
        if type(limit) is not int or limit < 1:
            return _tool_error("INVALID_LIMIT", "limit must be a positive integer")
        clamped = limit > 20
        limit = min(limit, 20)
        if self.search_call_count >= settings.AGENT_MAX_SEARCH_CALLS:
            return _tool_error(
                "SEARCH_LIMIT_REACHED", "Recipe search call limit reached for this session"
            )
        if self.user_profile is None:
            return _tool_error("PROFILE_UNAVAILABLE", "User profile is not available")
        self.search_call_count += 1
        profile = self.user_profile
        try:
            recipes = await retriever.search_recipes(
                self.db_session,
                allergies=profile.get("allergies") or [],
                dislikes=profile.get("disliked_ingredients") or [],
                diseases=profile.get("diseases") or [],
                preferred_tags=profile.get("preferences") or [],
                semantic_query=query.strip(),
                meal_type=meal_type,
                exclude_recipe_ids=self.avoid_recipe_ids,
                limit=limit,
            )
            recipes = [
                r
                for r in recipes
                if (meal_type is None or retriever.meal_type_matches(r, meal_type))
                and str(r.get("base_recipe_id") or r["id"]).split("::", 1)[0]
                not in self.avoid_recipe_ids
            ][:limit]
            projected = [
                {
                    "id": str(r["id"]),
                    "title": r["title"],
                    "meal_type": retriever._infer_meal_type(r.get("tags"), r.get("meal_type")),
                    **{key: r[key] for key in ("calories", "protein", "fat", "carbs")},
                    "tags": r.get("tags") or [],
                }
                for r in recipes
            ]
        except Exception:
            logger.exception("Recipe search failed")
            return _tool_error("SEARCH_UNAVAILABLE", "Recipe search is temporarily unavailable")
        if recipes:
            self.session_state.recipes_fetched = True
            self.collected_recipes.update(
                {str(r["id"]): {**deepcopy(r), "id": str(r["id"])} for r in recipes}
            )
        result = {"recipes": projected}
        if clamped:
            result["message"] = "limit clamped to 20"
        elif not recipes:
            result["message"] = "No recipes found matching the given criteria and safety filters"
        return result

    def _execute_validate_day_plan(self, arguments: dict) -> dict:
        self.session_state.last_validated_hash = None
        plan_data = arguments.get("plan")
        try:
            plan = DayPlan.model_validate(plan_data)
            plan_hash = _compute_plan_hash(plan_data)
        except (ValidationError, TypeError, ValueError) as exc:
            return {
                "is_valid": False,
                "errors": [f"Schema validation error: {exc}"],
                "message": None,
            }
        if self.user_profile is None:
            return {"is_valid": False, "errors": ["User profile is not available"], "message": None}
        try:
            valid, error = validate_day_plan(
                plan,
                self.user_profile["target_calories"],
                meal_schedule=self.user_profile.get("meal_schedule"),
            )
        except Exception as exc:
            logger.exception("Day plan validation failed")
            return {
                "is_valid": False,
                "errors": [f"Internal validation error: {exc}"],
                "message": None,
            }
        if not valid:
            return {
                "is_valid": False,
                "errors": (error or "Plan validation failed").split("\n"),
                "message": None,
            }
        self.session_state.last_validated_hash = plan_hash
        return {"is_valid": True, "errors": [], "message": "План соответствует всем требованиям"}


async def _run_agentic_loop(
    user_profile: dict,
    db_session: AsyncSession,
    day_number: int = 1,
    *,
    previous_day_titles: list[str] | None = None,
    avoid_recipe_ids: set[str] | None = None,
) -> GeneratedDayResult:
    if not settings.AGENT_TOOL_USE_ENABLED:
        raise AgentConfigurationError("Agentic loop entered with AGENT_TOOL_USE_ENABLED=False")
    tools = _build_tool_definitions()
    if not tools:
        raise AgentConfigurationError("No agent tools could be registered")
    executor = ToolExecutor(user_profile, db_session, avoid_recipe_ids=avoid_recipe_ids or set())
    messages = [
        {"role": "system", "content": _build_agentic_system_prompt()},
        {"role": "user", "content": f"Составь план питания на день {day_number}."},
    ]
    if previous_day_titles:
        messages.append(
            {
                "role": "user",
                "content": "Избегай повторения предыдущих блюд: "
                + json.dumps(previous_day_titles, ensure_ascii=False),
            }
        )
    trace = []
    counts = dict.fromkeys(("get_user_profile", "search_recipes", "validate_day_plan"), 0)
    llm_calls = 0
    pending_ids = []
    outcome = "error"

    def feedback(content: str) -> None:
        messages.append({"role": "user", "content": content})

    try:
        while llm_calls < settings.AGENT_MAX_LLM_CALLS:
            llm_calls += 1
            try:
                choice = await _call_llm_with_tools(
                    messages,
                    tools,
                    expect_final=executor.session_state.last_validated_hash is not None,
                )
                message = choice["message"]
            except (httpx.HTTPError, KeyError, ValueError):
                logger.exception("Agent LLM request failed on call {}", llm_calls)
                feedback("LLM request failed. Continue using the tools and return valid JSON.")
                continue
            tool_calls = message.get("tool_calls") or []
            messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content"),
                    **({"tool_calls": tool_calls} if tool_calls else {}),
                }
            )
            if tool_calls:
                pending_ids = [tc["id"] for tc in tool_calls]
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    counts[name] = counts.get(name, 0) + 1
                    try:
                        arguments = json.loads(tc["function"].get("arguments", "{}"))
                        if not isinstance(arguments, dict):
                            raise ValueError("Tool arguments must be a JSON object")
                    except (ValueError, TypeError):
                        arguments = {}
                        if name == "validate_day_plan":
                            executor.session_state.last_validated_hash = None
                        result = _tool_error(
                            "INVALID_ARGUMENTS", "Tool arguments must be a valid JSON object"
                        )
                    else:
                        try:
                            result = await executor.dispatch(name, arguments)
                        except Exception:
                            logger.exception("Unhandled tool failure: {}", name)
                            if name == "validate_day_plan":
                                executor.session_state.last_validated_hash = None
                            result = _tool_error("TOOL_EXECUTION_ERROR", "Tool execution failed")
                    summary = _build_args_summary(arguments)
                    trace.append({"tool": name, "llm_call": llm_calls, "args_summary": summary})
                    logger.debug("[agentic] llm_call={} tool={} args={}", llm_calls, name, summary)
                    logger.debug(
                        "[agentic] llm_call={} tool={} result={}",
                        llm_calls,
                        name,
                        str(result)[:200],
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        }
                    )
                    pending_ids.remove(tc["id"])
                continue

            if not executor.session_state.ready_for_final():
                feedback(
                    "You must complete these steps before returning the final plan: "
                    + ", ".join(executor.session_state.missing_steps())
                    + ". Call the missing tools first."
                )
                continue
            try:
                parsed = json.loads(message.get("content") or "")
            except (json.JSONDecodeError, TypeError) as exc:
                feedback(f"Invalid JSON: {exc}. Return valid JSON.")
                continue
            try:
                output = MealPlanOutput.model_validate(parsed)
            except ValidationError as exc:
                feedback(f"Schema error: {exc}. Fix the structure.")
                continue
            try:
                response_hash = _compute_plan_hash(parsed["day"])
            except ValueError:
                feedback("Invalid JSON: all numbers must be finite.")
                continue
            if response_hash != executor.session_state.last_validated_hash:
                executor.session_state.last_validated_hash = None
                feedback(
                    "The returned plan differs from the last validated version. Please validate the exact plan you intend to submit."
                )
                continue
            unknown_ids = {
                meal.recipe_id for meal in output.day.meals
            } - executor.collected_recipes.keys()
            if unknown_ids:
                feedback(
                    f"Plan contains recipe IDs not returned by search_recipes in this session: {sorted(unknown_ids)}. Use only recipes from search results."
                )
                continue
            if (
                output.day.day_number != day_number
                or output.daily_target_calories != user_profile["target_calories"]
            ):
                executor.session_state.last_validated_hash = None
                feedback(
                    "Use the requested day_number and the target from get_user_profile. Validate the corrected plan again."
                )
                continue
            backend_valid, backend_error = validate_day_plan(
                output.day,
                user_profile["target_calories"],
                meal_schedule=user_profile.get("meal_schedule"),
            )
            recipes = list(executor.collected_recipes.values())
            enriched = _enrich_day_plan(output.day, recipes)
            _normalize_day_totals(enriched)
            outcome = "valid" if backend_valid else "partially_valid"
            return GeneratedDayResult(
                plan=enriched,
                quality_status=outcome,
                attempts_used=llm_calls,
                validation_error=backend_error,
                tool_call_trace=trace,
                collected_recipes=recipes,
            )
        raise AgentLimitError(llm_calls, pending_ids)
    except Exception as exc:
        outcome = type(exc).__name__
        raise
    finally:
        logger.info(
            "[agentic] llm_calls={} tool_counts={} search_attempts={} outcome={}",
            llm_calls,
            counts,
            executor.search_call_count,
            outcome,
        )


async def generate_day_plan(
    user_profile: dict,
    recipes: list[dict],
    day_number: int = 1,
    *,
    previous_day_titles: list[str] | None = None,
    avoid_recipe_ids: set[str] | None = None,
) -> GeneratedDayResult:
    logger.info("mode={}", "tool_use" if settings.AGENT_TOOL_USE_ENABLED else "pipeline")
    if settings.AGENT_TOOL_USE_ENABLED:
        # Own a read session, preserving the public signature for CLI and Celery.
        async with async_session() as session:
            return await _run_agentic_loop(
                user_profile,
                session,
                day_number,
                previous_day_titles=previous_day_titles,
                avoid_recipe_ids=avoid_recipe_ids,
            )
    return await _run_pipeline(
        user_profile,
        recipes,
        day_number,
        previous_day_titles=previous_day_titles,
        avoid_recipe_ids=avoid_recipe_ids,
    )


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


async def _run_pipeline(
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
            1
            if str(r["id"] if isinstance(r, dict) else r.id).split("::", 1)[0] in avoid_ids
            else 0,
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
