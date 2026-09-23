"""Shared metadata helpers for generation pipelines."""

from __future__ import annotations

from typing import Any

PIPELINE_STEPS = ["context", "generate", "validate", "auto-fix", "save", "shopping-list"]


def build_generation_meta(
    *,
    mode: str,
    quality_status: str,
    warnings: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "pipeline_version": "canonical_v1",
        "mode": mode,
        "quality_status": quality_status,
        "warnings": warnings or [],
    }
    if extra:
        payload.update(extra)
    return payload


def _empty_steps() -> list[dict[str, Any]]:
    return [{"key": step, "status": "pending", "message": ""} for step in PIPELINE_STEPS]


def _set_step(
    state: dict[str, Any],
    key: str,
    *,
    status: str,
    message: str,
    activate: bool = True,
) -> None:
    if activate:
        state["current_step"] = key
    for step in state["steps"]:
        if step["key"] == key:
            step["status"] = status
            step["message"] = message
            break
