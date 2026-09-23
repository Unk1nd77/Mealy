"""One production use case: profile -> tools -> final guards/repair -> save.

HTTP submits this use case through Celery; neither transport selects a runtime.
Legacy mode names are normalized at the transport boundary, not here.
"""

from copy import deepcopy

from app.core.agent import runtime
from app.core.agent.generation import GeneratedPlanDraft, generate_days
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


async def generate_meal_plan(
    *, user_id: str, days: int, progress_callback: ProgressCallback | None = None
) -> dict:
    if type(days) is not int or not 1 <= days <= 14:
        raise ValueError("days must be an integer between 1 and 14")
    state = {
        "mode": "agentic",
        "quality_status": "valid",
        "current_step": None,
        "steps": _empty_steps(),
        "warnings": [],
    }
    draft = GeneratedPlanDraft()
    try:
        _set_step(state, "context", status="running", message="Загружаем профиль питания.")
        _emit_progress(progress_callback, state)
        context = await build_context_payload(user_id, include_recipes=False)
        # A single server-owned snapshot for the whole run; each executor copies it.
        context = deepcopy(context)

        async def load_context(day_number: int) -> dict:
            return context

        async def generate_day(profile, recipes, *, day_number, **history):
            return await runtime.generate_day_plan(profile, day_number, **history)

        _set_step(state, "context", status="completed", message="Профиль готов.")
        _set_step(state, "generate", status="running", message=f"Составляем план на {days} дн.")
        _emit_progress(progress_callback, state)
        await generate_days(
            days,
            load_context=load_context,
            generate_day=generate_day,
            use_collected_recipes=True,
            carry_history=True,
            draft=draft,
        )
        state["quality_status"] = draft.quality_status
        _set_step(state, "generate", status="completed", message=f"Собрано дней: {days}.")
        validate_generated_draft(
            draft, state=state, progress_callback=progress_callback, allow_universal=True
        )
        state["warnings"] = draft.warnings
        plan_data = {
            "user_profile": draft.user_profile,
            "total_days": days,
            "daily_target_calories": draft.user_profile["target_calories"],
            "days": draft.days,
            "generation_meta": build_generation_meta(
                mode="agentic",
                quality_status=state["quality_status"],
                warnings=draft.warnings,
                extra={"steps": PIPELINE_STEPS, "days": draft.day_metadata},
            ),
        }
        _set_step(state, "save", status="running", message="Сохраняем проверенный план.")
        _emit_progress(progress_callback, state)
        saved = await save_plan_payload(user_id, plan_data, days_count=days)
        state["plan_id"] = saved["plan_id"]
        _set_step(state, "save", status="completed", message="План сохранён.")
        _set_step(state, "shopping-list", status="running", message="Собираем список покупок.")
        shopping = build_shopping_list_payload(plan_data, input_format="week")
        _set_step(state, "shopping-list", status="completed", message=f"Позиций: {len(shopping)}.")
        _emit_progress(progress_callback, state, celery_state="SUCCESS")
        return {**deepcopy(state), "status": "READY", "shopping_list": shopping}
    except Exception:
        state["quality_status"] = "failed"
        state["warnings"] = draft.warnings
        for step in reversed(state["steps"]):
            if step["status"] == "running":
                step["status"] = "failed"
                break
        _emit_progress(progress_callback, state)
        raise
