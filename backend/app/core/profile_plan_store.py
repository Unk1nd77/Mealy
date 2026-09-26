"""Shared profile loading and plan persistence for agentic-only use case."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.relational_store import load_user_profile_from_rows, sync_plan_rows
from app.db.models import MealPlan, MealPlanStatus, User


async def load_user_profile(session: AsyncSession, user_id: str) -> dict:
    """Load a user profile from cache or database in a canonical shape."""
    cached = await cache.get_json(f"user:{user_id}")
    if cached:
        if "id" not in cached:
            cached["id"] = user_id
            await cache.set_json(f"user:{user_id}", cached, ttl=600)
        return cached

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError(f"User {user_id} not found")

    profile = await load_user_profile_from_rows(session, user)
    await cache.set_json(f"user:{user_id}", profile, ttl=600)
    return profile


async def create_plan_record(
    session: AsyncSession,
    *,
    user_id: str,
    days: int,
    status: MealPlanStatus = MealPlanStatus.generating,
) -> MealPlan:
    """Create an empty plan record before generation begins."""
    plan_record = MealPlan(
        user_id=uuid.UUID(user_id),
        status=status,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=days - 1),
    )
    session.add(plan_record)
    await session.commit()
    await session.refresh(plan_record)
    return plan_record


async def finalize_plan_record(
    session: AsyncSession,
    *,
    plan_record: MealPlan,
    plan_data: dict,
    status: MealPlanStatus,
) -> None:
    """Persist generated plan data and cache it when ready."""
    plan_record.status = status
    await sync_plan_rows(
        session,
        plan_record=plan_record,
        plan_data=plan_data,
        event_type="generated" if status == MealPlanStatus.ready else "generation_failed",
    )
    await session.commit()

    if status == MealPlanStatus.ready:
        await cache.set_json(f"plan:{plan_record.id}", plan_data, ttl=3600)
