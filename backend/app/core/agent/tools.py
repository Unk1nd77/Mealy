"""Allowlisted tool dispatch and per-day server-owned recipe/profile context."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.agent.contracts import AgentConfigurationError
from app.core.agent.guards import AgentSessionState, _compute_plan_hash
from app.core.agent.schemas import DayPlan
from app.core.rag import retriever
from app.core.skills import validator
from app.db.models import DEFAULT_MEAL_SCHEDULE

_MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack", "universal"]


def _tool_error(code: str, message: str) -> dict:
    return {"ok": False, "error": {"code": code, "message": message}}


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
            valid, error = validator.validate_day_plan(
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
