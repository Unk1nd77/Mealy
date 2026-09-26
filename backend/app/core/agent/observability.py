"""Diagnostics of stored plans, independent of the generation runtime."""

from typing import Any

OBSERVABILITY_TOLERANCE_PCT = 5.0
OBSERVABILITY_MESSAGE_LIMIT = 220


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
