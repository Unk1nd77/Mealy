"""Agentic-only day runtime. No pipeline, CLI, worker or persistence imports."""

from __future__ import annotations

import json

import httpx
from loguru import logger
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.agent.contracts import AgentConfigurationError, AgentLimitError, GeneratedDayResult
from app.core.agent.guards import _build_args_summary, _compute_plan_hash
from app.core.agent.plan_output import _enrich_day_plan, _normalize_day_totals
from app.core.agent.prompt_loader import _load_prompt
from app.core.agent.schemas import MealPlanOutput
from app.core.agent.tools import ToolExecutor, _build_tool_definitions, _tool_error
from app.core.skills import validator
from app.db.session import async_session


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


async def _run_agentic_loop(
    user_profile: dict,
    db_session: AsyncSession,
    day_number: int = 1,
    *,
    previous_day_titles: list[str] | None = None,
    avoid_recipe_ids: set[str] | None = None,
) -> GeneratedDayResult:
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
            backend_valid, backend_error = validator.validate_day_plan(
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
    day_number: int = 1,
    *,
    previous_day_titles: list[str] | None = None,
    avoid_recipe_ids: set[str] | None = None,
) -> GeneratedDayResult:
    """Run one tool session and close its read session, including on failure."""
    async with async_session() as session:
        return await _run_agentic_loop(
            user_profile,
            session,
            day_number,
            previous_day_titles=previous_day_titles,
            avoid_recipe_ids=avoid_recipe_ids,
        )
