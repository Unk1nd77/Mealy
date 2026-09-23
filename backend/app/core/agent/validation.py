"""Final day/week validation and deterministic repair shared with the legacy adapter."""

from app.core.agent.generation import GeneratedPlanDraft
from app.core.cli_contract import validate_plan_payload
from app.core.day_plan_repair import repair_day_plan
from app.core.generation_meta import ProgressCallback, _emit_progress, _set_step
from app.core.recipe_usage import _collect_used_recipe_base_ids, _validate_day_recipe_usage


def validate_generated_draft(
    draft: GeneratedPlanDraft,
    *,
    state: dict,
    progress_callback: ProgressCallback | None,
    allow_universal: bool,
) -> None:
    shared_user = draft.user_profile
    generated_days = draft.days
    recipes_by_day = draft.recipes_by_day
    avoid_recipe_base_ids_by_day = draft.avoid_recipe_ids_by_day
    warnings = draft.warnings
    current_recipes = []
    tool_use = allow_universal
    _set_step(
        state,
        "validate",
        status="running",
        message="Проверяем итоговые day-планы через CLI contract.",
    )
    _emit_progress(progress_callback, state)

    validation_errors: list[str] = []
    days_to_repair: list[tuple[int, str]] = []
    for day in generated_days:
        usage_error = _validate_day_recipe_usage(
            day_plan=day,
            recipes=recipes_by_day.get(day["day_number"], current_recipes),
            previous_recipe_base_ids=avoid_recipe_base_ids_by_day.get(day["day_number"], set()),
            allow_universal=tool_use,
        )
        if usage_error:
            error = f"Day {day['day_number']}: {usage_error}"
            validation_errors.append(error)
            days_to_repair.append((day["day_number"], usage_error))
            continue

        validation_payload = {
            "daily_target_calories": shared_user["target_calories"],
            "day": day,
        }
        result, exit_code = validate_plan_payload(
            validation_payload,
            target_calories=shared_user["target_calories"],
            meal_schedule=shared_user.get("meal_schedule"),
        )
        if exit_code != 0:
            error = f"Day {day['day_number']}: {result.get('error', 'validation failed')}"
            validation_errors.append(error)
            days_to_repair.append((day["day_number"], result.get("error", "validation failed")))

    if validation_errors:
        _set_step(
            state,
            "validate",
            status="completed",
            message=f"Найдены ошибки: {len(validation_errors)} дн.",
        )
        _set_step(
            state,
            "auto-fix",
            status="running",
            message="Восстанавливаем day-plans по расписанию и recipe pool.",
        )
        _emit_progress(progress_callback, state)

        repair_notes: list[str] = []
        for day_number, initial_error in days_to_repair:
            previous_final_recipe_base_ids = _collect_used_recipe_base_ids(
                days=generated_days[: day_number - 1],
                recipes_by_day=recipes_by_day,
            )
            effective_avoid_recipe_base_ids = previous_final_recipe_base_ids
            repaired_day, applied_fixes, repair_error = repair_day_plan(
                day_plan=generated_days[day_number - 1],
                recipes=recipes_by_day.get(day_number, current_recipes),
                meal_schedule=shared_user.get("meal_schedule") or [],
                target_calories=shared_user["target_calories"],
                avoid_recipe_base_ids=effective_avoid_recipe_base_ids,
            )
            if repaired_day is None and day_number > 1:
                previous_day_recipe_base_ids = _collect_used_recipe_base_ids(
                    days=generated_days[day_number - 2 : day_number - 1],
                    recipes_by_day=recipes_by_day,
                )
                relaxed_day, relaxed_fixes, relaxed_error = repair_day_plan(
                    day_plan=generated_days[day_number - 1],
                    recipes=recipes_by_day.get(day_number, current_recipes),
                    meal_schedule=shared_user.get("meal_schedule") or [],
                    target_calories=shared_user["target_calories"],
                    avoid_recipe_base_ids=previous_day_recipe_base_ids,
                )
                if relaxed_day is not None:
                    repaired_day = relaxed_day
                    applied_fixes = [
                        "weekly uniqueness relaxed to previous-day uniqueness",
                        *relaxed_fixes,
                    ]
                    repair_error = None
                    effective_avoid_recipe_base_ids = previous_day_recipe_base_ids
                else:
                    repair_error = relaxed_error or repair_error
            if repaired_day is None:
                _set_step(
                    state,
                    "auto-fix",
                    status="failed",
                    message=repair_error or validation_errors[0],
                )
                raise RuntimeError(f"Day {day_number}: {repair_error or initial_error}")

            generated_days[day_number - 1] = repaired_day
            state["quality_status"] = "partially_valid"
            note = (
                f"Day {day_number}: auto-fix after '{initial_error}'. "
                f"Applied: {', '.join(applied_fixes) if applied_fixes else 'totals normalization'}"
            )
            repair_notes.append(note)
            warnings.append(note)

            validation_payload = {
                "daily_target_calories": shared_user["target_calories"],
                "day": repaired_day,
            }
            usage_error = _validate_day_recipe_usage(
                day_plan=repaired_day,
                recipes=recipes_by_day.get(day_number, current_recipes),
                previous_recipe_base_ids=effective_avoid_recipe_base_ids,
                allow_universal=tool_use,
            )
            if usage_error:
                _set_step(
                    state,
                    "auto-fix",
                    status="failed",
                    message=usage_error,
                )
                raise RuntimeError(f"Day {day_number}: {usage_error}")
            result, exit_code = validate_plan_payload(
                validation_payload,
                target_calories=shared_user["target_calories"],
                meal_schedule=shared_user.get("meal_schedule"),
            )
            if exit_code != 0:
                _set_step(
                    state,
                    "auto-fix",
                    status="failed",
                    message=result.get("error", validation_errors[0]),
                )
                raise RuntimeError(
                    f"Day {day_number}: {result.get('error', 'validation failed after auto-fix')}"
                )

        _set_step(
            state,
            "auto-fix",
            status="completed",
            message=f"Auto-fix применён: {len(repair_notes)} дн.",
        )

    _set_step(
        state,
        "validate",
        status="completed",
        message="Итоговый план прошёл валидацию.",
    )
    if not validation_errors:
        _set_step(
            state,
            "auto-fix",
            status="completed" if state["quality_status"] != "valid" else "skipped",
            message=(
                "Во время генерации использовался встроенный retry/reflection."
                if state["quality_status"] != "valid"
                else "Исправления не потребовались."
            ),
            activate=False,
        )
