"""Shared profile-context, persistence, and shopping helpers for agentic plans."""

from __future__ import annotations

from typing import Any

from app.core.rag import retriever
from app.core.profile_plan_store import (
    create_plan_record,
    finalize_plan_record,
    load_user_profile,
)
from app.core.skills.aggregator import aggregate_shopping_list
from app.db.models import MealPlanStatus
from app.db.session import async_session


async def build_context_payload(
    user_id: str,
    day: int = 1,
    *,
    include_recipes: bool = False,
) -> dict[str, Any]:
    """Load the server-owned profile; recipe search occurs only through agent tools."""
    if include_recipes:
        raise ValueError("Eager recipe context has been removed; agent retrieves via tools")
    async with async_session() as session:
        user = await load_user_profile(session, user_id)
    return {"user": user, "day_number": day, "available_recipes": []}


async def assess_catalog_coverage(user_profile: dict[str, Any], *, days: int) -> dict[str, Any]:
    """Check whether the current safe catalog can support this plan before LLM use."""
    async with async_session() as session:
        return await retriever.assess_profile_recipe_pool(
            session,
            user_profile=user_profile,
            days=days,
        )


def normalize_plan_for_shopping(
    plan_data: dict[str, Any],
    *,
    input_format: str = "auto",
) -> dict[str, Any]:
    """Normalize a day-plan payload to weekly shape before aggregation."""
    if input_format == "day" or (
        input_format == "auto" and "day" in plan_data and "days" not in plan_data
    ):
        if "day" not in plan_data:
            raise ValueError("Expected day-format JSON with top-level key 'day'")
        return {
            "total_days": 1,
            "daily_target_calories": plan_data.get("daily_target_calories"),
            "days": [plan_data["day"]],
        }
    return plan_data


def build_shopping_list_payload(
    plan_data: dict[str, Any],
    *,
    input_format: str = "auto",
) -> list[dict[str, Any]]:
    """Build shopping list from a day or weekly plan payload."""
    normalized = normalize_plan_for_shopping(plan_data, input_format=input_format)
    return aggregate_shopping_list(normalized)


async def save_plan_payload(
    user_id: str,
    plan_data: dict[str, Any],
    *,
    days_count: int,
) -> dict[str, Any]:
    """Persist a validated plan and return its identifier and status."""
    async with async_session() as session:
        plan_record = await create_plan_record(
            session,
            user_id=user_id,
            days=days_count,
            status=MealPlanStatus.generating,
        )
        await finalize_plan_record(
            session,
            plan_record=plan_record,
            plan_data=plan_data,
            status=MealPlanStatus.ready,
        )
        return {
            "plan_id": str(plan_record.id),
            "status": "READY",
            "days": days_count,
        }

