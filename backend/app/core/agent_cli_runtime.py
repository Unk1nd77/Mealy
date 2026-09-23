"""Server-side agent_cli runtime built around the shared CLI contract."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from loguru import logger

from app.config import settings
from app.core.agent.generation import GeneratedPlanDraft, generate_days
from app.core.agent.orchestrator import generate_day_plan
from app.core.agent.validation import validate_generated_draft
from app.core.cli_contract import (
    build_context_payload,
    build_shopping_list_payload,
    save_plan_payload,
)
from app.core.generation_meta import (
    PIPELINE_STEPS,
    ProgressCallback,
    _emit_progress,
    _empty_steps,
    _set_step,
    build_generation_meta,
)
from app.core.meal_compatibility import slot_compatible_types

_slot_compatible_types = slot_compatible_types  # Transitional compatibility export.


async def run_agent_cli_pipeline(
    *,
    user_id: str,
    days: int,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run the canonical context->generate->validate->auto-fix->save pipeline."""
    state: dict[str, Any] = {
        "mode": "agent_cli",
        "quality_status": "valid",
        "current_step": None,
        "steps": _empty_steps(),
        "warnings": [],
    }
    warnings: list[str] = []
    shared_user: dict[str, Any] | None = None
    current_recipes: list[dict[str, Any]] = []
    tool_use = settings.AGENT_TOOL_USE_ENABLED

    async def load_context(day: int) -> dict:
        if tool_use:
            return await build_context_payload(user_id, day=day, include_recipes=False)
        return await build_context_payload(user_id, day=day)

    try:
        _set_step(state, "context", status="running", message="Готовим CLI-контекст для агента.")
        _emit_progress(progress_callback, state)

        for day_number in range(1, days + 1):
            context = await load_context(day_number)
            shared_user = context["user"]
            current_recipes = context["available_recipes"]
            if not current_recipes and not tool_use:
                raise RuntimeError(f"No recipes available for day {day_number} after filters")
            diagnostics = context.get("catalog_diagnostics") or {}
            if diagnostics and not diagnostics.get("feasible", True):
                slot_counts = diagnostics.get("slot_counts") or {}
                raise RuntimeError(
                    "catalog_insufficient: "
                    f"target={diagnostics.get('target_calories')} "
                    f"max_achievable={diagnostics.get('max_achievable_calories')} "
                    f"slot_counts={slot_counts}"
                )

        _set_step(
            state,
            "context",
            status="completed",
            message=(
                f"Профиль готов. Составляем план на {days} дн."
                if tool_use
                else f"CLI-контекст готов: {len(current_recipes)} рецептов, {days} дн."
            ),
        )
        _set_step(state, "generate", status="running", message=f"Агент собирает план на {days} дн.")
        _emit_progress(progress_callback, state)

        draft = await generate_days(
            days,
            load_context=load_context,
            generate_day=generate_day_plan,
            use_collected_recipes=tool_use,
            carry_history=True,
            draft=GeneratedPlanDraft(warnings=warnings),
        )
        shared_user = draft.user_profile
        generated_days = draft.days
        day_generation_meta = draft.day_metadata
        state["quality_status"] = draft.quality_status

        _set_step(
            state,
            "generate",
            status="completed",
            message=f"План агентом собран: {len(generated_days)} дн.",
        )
        validate_generated_draft(
            draft,
            state=state,
            progress_callback=progress_callback,
            allow_universal=tool_use,
        )

        state["warnings"] = warnings
        plan_data = {
            "user_profile": shared_user,
            "total_days": days,
            "daily_target_calories": shared_user["target_calories"],
            "days": generated_days,
            "generation_meta": build_generation_meta(
                mode="agent_cli",
                quality_status=state["quality_status"],
                warnings=warnings,
                extra={
                    "steps": PIPELINE_STEPS,
                    "days": day_generation_meta,
                },
            ),
        }

        _set_step(state, "save", status="running", message="Сохраняем агентный результат в БД.")
        _emit_progress(progress_callback, state)
        save_result = await save_plan_payload(user_id, plan_data, days_count=days)
        plan_id = save_result["plan_id"]
        state["plan_id"] = plan_id

        _set_step(state, "save", status="completed", message=f"План сохранён: {plan_id}.")
        _set_step(
            state, "shopping-list", status="running", message="Строим shopping list из плана."
        )
        shopping_list = build_shopping_list_payload(plan_data, input_format="week")
        _set_step(
            state,
            "shopping-list",
            status="completed",
            message=f"Список покупок собран: {len(shopping_list)} позиций.",
        )
        _emit_progress(progress_callback, state, celery_state="SUCCESS")

        logger.info(
            "Agent CLI pipeline completed: user_id={} plan_id={} days={}",
            user_id,
            plan_id,
            days,
        )
        return {
            "plan_id": plan_id,
            "status": "READY",
            "mode": "agent_cli",
            "quality_status": state["quality_status"],
            "warnings": warnings,
            "steps": deepcopy(state["steps"]),
            "current_step": state["current_step"],
            "shopping_list": shopping_list,
        }
    except Exception:
        state["quality_status"] = "failed"
        for step in reversed(state["steps"]):
            if step["status"] == "running":
                step["status"] = "failed"
                break
        state["warnings"] = warnings
        _emit_progress(progress_callback, state)
        raise
