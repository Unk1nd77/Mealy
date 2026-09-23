"""API-эндпоинты для генерации и получения планов питания."""

from __future__ import annotations

import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cache
from app.core.agent.contracts import GENERATION_TASK_NAME, GenerationMode
from app.core.agent.observability import build_plan_observability
from app.core.relational_store import (
    build_plan_data_from_rows,
    create_generation_run,
    sync_plan_rows,
)
from app.core.skills.aggregator import aggregate_shopping_list
from app.core.skills.ics_export import generate_ics
from app.db.models import MealPlan, MealPlanStatus
from app.db.session import get_db
from app.worker import celery_app

router = APIRouter(prefix="/api", tags=["Plans"])
PLAN_RESPONSE_CACHE_TTL = 3600
SHOPPING_LIST_CACHE_TTL = 1800
PLAN_RESPONSE_CACHE_VERSION = "v1"
SHOPPING_LIST_CACHE_VERSION = "v1"

PDF_FONT_NAME = "MealyShoppingFont"
PDF_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
)


class GeneratePlanRequest(BaseModel):
    user_id: uuid.UUID
    days: int = Field(default=7, ge=1, le=14)
    mode: GenerationMode = "agentic"


class GeneratePlanResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    plan_id: str | None = None
    mode: str | None = None
    quality_status: str | None = None
    current_step: str | None = None
    steps: list[DemoStepResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class DemoStepResponse(BaseModel):
    key: str
    status: str
    message: str = ""



class PlanResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    start_date: date | None
    end_date: date | None
    plan_data: dict | None
    mode: str | None = None
    quality_status: str | None = None
    warnings: list[str] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class PlanObservabilityStepResponse(BaseModel):
    key: str
    status: str
    message: str


class PlanObservabilityDayCheckResponse(BaseModel):
    day_number: int
    total_calories: float
    target_calories: int
    deviation_kcal: float
    deviation_pct: float
    within_target: bool


class PlanObservabilityResponse(BaseModel):
    source: str
    summary: str
    steps: list[PlanObservabilityStepResponse] = Field(default_factory=list)
    day_checks: list[PlanObservabilityDayCheckResponse] = Field(default_factory=list)
    has_persisted_trace: bool = False


def _plan_response_cache_key(plan_id: uuid.UUID | str) -> str:
    return cache.build_key("plans", "response", PLAN_RESPONSE_CACHE_VERSION, plan_id)


def _shopping_list_cache_key(plan_id: uuid.UUID | str) -> str:
    return cache.build_key("plans", "shopping-list", SHOPPING_LIST_CACHE_VERSION, plan_id)


def _is_plan_response_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False

    required_keys = {"id", "user_id", "status", "start_date", "end_date", "plan_data"}
    if not required_keys.issubset(payload):
        return False

    if not isinstance(payload["id"], str) or not isinstance(payload["user_id"], str):
        return False
    if not isinstance(payload["status"], str):
        return False

    start_date = payload["start_date"]
    end_date = payload["end_date"]
    if start_date is not None and not isinstance(start_date, str):
        return False
    if end_date is not None and not isinstance(end_date, str):
        return False

    plan_data = payload["plan_data"]
    if plan_data is None:
        return True
    if not isinstance(plan_data, dict):
        return False

    return (
        isinstance(plan_data.get("days"), list)
        and isinstance(plan_data.get("total_days"), int)
        and "daily_target_calories" in plan_data
    )


def _is_shopping_list_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("plan_id"), str):
        return False

    items = payload.get("items")
    if not isinstance(items, list):
        return False

    for item in items:
        if not isinstance(item, dict):
            return False
        if not isinstance(item.get("name"), str):
            return False
        if not isinstance(item.get("unit"), str):
            return False
        if not isinstance(item.get("amount"), int | float):
            return False

    return True


def _serialize_plan_response(plan: MealPlan, plan_data: dict | None) -> dict:
    return {
        "id": str(plan.id),
        "user_id": str(plan.user_id),
        "status": plan.status.value,
        "start_date": plan.start_date.isoformat() if plan.start_date else None,
        "end_date": plan.end_date.isoformat() if plan.end_date else None,
        "plan_data": plan_data,
    }


def _fallback_plan_data(plan: MealPlan) -> dict | None:
    value = getattr(plan, "plan_data", None)
    return value if isinstance(value, dict) else None


async def _cache_plan_response(plan: MealPlan, plan_data: dict | None) -> None:
    await cache.set_json(
        _plan_response_cache_key(plan.id),
        _serialize_plan_response(plan, plan_data),
        ttl=PLAN_RESPONSE_CACHE_TTL,
    )


async def _cache_shopping_list(plan_id: uuid.UUID, shopping_list: list[dict]) -> dict:
    payload = {"plan_id": str(plan_id), "items": shopping_list}
    await cache.set_json(
        _shopping_list_cache_key(plan_id),
        payload,
        ttl=SHOPPING_LIST_CACHE_TTL,
    )
    return payload


def _build_shopping_list_pdf(plan_id: uuid.UUID, shopping_list: list[dict]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    font_name = "Helvetica"
    for font_path in PDF_FONT_CANDIDATES:
        if font_path.exists():
            try:
                pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, str(font_path)))
            except (OSError, ValueError):
                continue
            font_name = PDF_FONT_NAME
            break

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    _, height = A4
    margin_x = 48
    top = height - 56
    line_height = 18

    pdf.setTitle(f"Mealy shopping list {plan_id}")
    pdf.setFont(font_name, 16)
    pdf.drawString(margin_x, top, "Mealy Shopping List")

    pdf.setFont(font_name, 10)
    pdf.drawString(margin_x, top - 18, f"Plan ID: {plan_id}")

    y = top - 52
    pdf.setFont(font_name, 12)

    for index, item in enumerate(shopping_list, start=1):
        line = f"{index}. {item['name']} - {item['amount']} {item['unit']}"
        if y <= 56:
            pdf.showPage()
            pdf.setFont(font_name, 12)
            y = height - 56
        pdf.drawString(margin_x, y, line)
        y -= line_height

    pdf.save()
    return buffer.getvalue()


@router.post("/generate-plan", response_model=GeneratePlanResponse)
async def generate_plan(data: GeneratePlanRequest, db: AsyncSession = Depends(get_db)):
    mode = data.mode
    task = celery_app.send_task(
        GENERATION_TASK_NAME,
        args=[str(data.user_id), data.days, mode],
    )
    await create_generation_run(
        db,
        user_id=str(data.user_id),
        mode=mode,
        task_id=task.id,
        status="QUEUED",
    )
    logger.info(
        "Plan generation queued: task_id={} user_id={} mode={}",
        task.id,
        data.user_id,
        mode,
    )
    return GeneratePlanResponse(task_id=task.id)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    status_map = {
        "PENDING": "PENDING",
        "STARTED": "GENERATING",
        "GENERATING": "GENERATING",
        "SUCCESS": "READY",
        "FAILURE": "FAILED",
    }

    status = status_map.get(result.state, result.state)

    response = TaskStatusResponse(task_id=task_id, status=status)
    progress_meta = result.info if isinstance(result.info, dict) else {}
    response.plan_id = progress_meta.get("plan_id")
    response.mode = progress_meta.get("mode")
    response.quality_status = progress_meta.get("quality_status")
    response.current_step = progress_meta.get("current_step")
    response.steps = progress_meta.get("steps") or []
    response.warnings = progress_meta.get("warnings") or []

    if result.state == "SUCCESS" and result.result:
        response.plan_id = result.result.get("plan_id")
        response.mode = result.result.get("mode") or response.mode
        response.quality_status = result.result.get("quality_status") or response.quality_status
        response.current_step = result.result.get("current_step") or response.current_step
        response.steps = result.result.get("steps") or response.steps
        response.warnings = result.result.get("warnings") or response.warnings
        if result.result.get("status") == "FAILED":
            response.status = "FAILED"
            response.error = result.result.get("error")
    elif result.state == "FAILURE":
        response.error = str(result.result)

    return response


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cached_response = await cache.get_json(
        _plan_response_cache_key(plan_id),
        validator=_is_plan_response_payload,
    )
    if cached_response:
        return PlanResponse(
            id=uuid.UUID(cached_response["id"]),
            user_id=uuid.UUID(cached_response["user_id"]),
            status=cached_response["status"],
            start_date=date.fromisoformat(cached_response["start_date"])
            if cached_response["start_date"]
            else None,
            end_date=date.fromisoformat(cached_response["end_date"])
            if cached_response["end_date"]
            else None,
            plan_data=cached_response["plan_data"],
        )

    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_data = await build_plan_data_from_rows(
        db,
        plan,
        fallback_plan_data=_fallback_plan_data(plan),
    )
    if plan.status == MealPlanStatus.ready and plan_data:
        await _cache_plan_response(plan, plan_data)

    generation_meta = (plan_data or {}).get("generation_meta") or {}

    return PlanResponse(
        id=plan.id,
        user_id=plan.user_id,
        status=plan.status.value,
        start_date=plan.start_date,
        end_date=plan.end_date,
        plan_data=plan_data,
        mode=generation_meta.get("mode"),
        quality_status=generation_meta.get("quality_status"),
        warnings=generation_meta.get("warnings") or [],
    )


@router.get("/plans/{plan_id}/observability", response_model=PlanObservabilityResponse)
async def get_plan_observability(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    _, plan_data = await _load_ready_plan_with_data(plan_id, db)
    return PlanObservabilityResponse.model_validate(build_plan_observability(plan_data))


@router.get("/plans/{plan_id}/shopping-list")
async def get_shopping_list(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    cached_payload = await cache.get_json(
        _shopping_list_cache_key(plan_id),
        validator=_is_shopping_list_payload,
    )
    if cached_payload:
        return cached_payload

    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan_data = await build_plan_data_from_rows(
        db,
        plan,
        fallback_plan_data=_fallback_plan_data(plan),
    )
    if plan.status != MealPlanStatus.ready or not plan_data:
        raise HTTPException(status_code=400, detail="Plan is not ready yet")

    shopping_list = aggregate_shopping_list(plan_data)
    return await _cache_shopping_list(plan_id, shopping_list)


@router.get("/plans/{plan_id}/shopping-list.pdf")
async def export_shopping_list_pdf(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    plan = await _load_ready_plan(plan_id, db)
    plan_data = await build_plan_data_from_rows(
        db,
        plan,
        fallback_plan_data=_fallback_plan_data(plan),
    )
    shopping_list = aggregate_shopping_list(plan_data or {})
    pdf_content = _build_shopping_list_pdf(plan_id, shopping_list)

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="mealy-shopping-list-{plan_id}.pdf"'
        },
    )


@router.get("/plans/{plan_id}/calendar.ics")
async def export_calendar(plan_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Экспорт плана питания в формат iCalendar (.ics)."""
    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan_data = await build_plan_data_from_rows(
        db,
        plan,
        fallback_plan_data=_fallback_plan_data(plan),
    )
    if plan.status != MealPlanStatus.ready or not plan_data:
        raise HTTPException(status_code=400, detail="Plan is not ready yet")

    ics_content = generate_ics(
        plan_data=plan_data,
        plan_id=str(plan_id),
        start_date=plan.start_date,
    )

    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="mealy-plan-{plan_id}.ics"'},
    )


# ── Swap / Cancel ──────────────────────────────────


class SwapMealRequest(BaseModel):
    day_number: int = Field(ge=1)
    meal_type: str
    new_recipe_id: uuid.UUID | None = None


class CancelMealRequest(BaseModel):
    day_number: int = Field(ge=1)
    meal_type: str


async def _load_ready_plan(plan_id: uuid.UUID, db: AsyncSession) -> MealPlan:
    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != MealPlanStatus.ready:
        raise HTTPException(status_code=400, detail="Plan is not ready yet")
    return plan


async def _load_ready_plan_with_data(
    plan_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[MealPlan, dict]:
    plan = await _load_ready_plan(plan_id, db)
    plan_data = await build_plan_data_from_rows(
        db,
        plan,
        fallback_plan_data=_fallback_plan_data(plan),
    )
    if not plan_data:
        raise HTTPException(status_code=400, detail="Plan is not ready yet")
    return plan, plan_data


def _find_day_and_meal(plan_data: dict, day_number: int, meal_type: str) -> tuple[dict, dict, int]:
    """Find day dict, meal dict, and meal index in the day."""
    for day in plan_data.get("days", []):
        if day.get("day_number") == day_number:
            for idx, meal in enumerate(day.get("meals", [])):
                if meal.get("type") == meal_type:
                    return day, meal, idx
            raise HTTPException(
                status_code=404,
                detail=f"Meal type '{meal_type}' not found in day {day_number}",
            )
    raise HTTPException(status_code=404, detail=f"Day {day_number} not found in plan")


def _recalc_day_totals(day: dict) -> None:
    """Recalculate day totals from meals."""
    meals = day.get("meals", [])
    day["total_calories"] = sum(m.get("calories", 0) for m in meals)
    day["total_protein"] = sum(m.get("protein", 0) for m in meals)
    day["total_fat"] = sum(m.get("fat", 0) for m in meals)
    day["total_carbs"] = sum(m.get("carbs", 0) for m in meals)


@router.get("/plans/{plan_id}/alternatives")
async def get_alternatives(
    plan_id: uuid.UUID,
    day_number: int,
    meal_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Получить альтернативные рецепты для замены блюда."""
    _, plan_data = await _load_ready_plan_with_data(plan_id, db)
    _, current_meal, _ = _find_day_and_meal(plan_data, day_number, meal_type)

    current_calories = current_meal.get("calories", 0)
    current_recipe_id = current_meal.get("recipe_id")

    # Get IDs of all recipes used in this day (to avoid duplicates)
    day_data = next((d for d in plan_data.get("days", []) if d.get("day_number") == day_number), {})
    used_ids = {m.get("recipe_id") for m in day_data.get("meals", [])}

    # Load user profile for allergy filtering
    from app.core.rag.retriever import _get_all_recipes

    all_recipes = await _get_all_recipes(db)

    # Filter: same meal_type, similar calories ±30%, not current, not used today
    user_profile = plan_data.get("user_profile", {})
    user_allergens = set(user_profile.get("allergies", []))

    alternatives = []
    for r in all_recipes:
        r_type = (r.get("meal_type") or "").strip()
        # Match meal_type (including universal types like "lunch/dinner")
        if meal_type not in r_type and r_type != meal_type:
            continue
        if r["id"] == current_recipe_id or r["id"] in used_ids:
            continue
        # Allergen check
        if user_allergens & set(r.get("allergens", [])):
            continue
        # Calorie range ±30%
        if current_calories > 0:
            r_cal = r.get("calories", 0)
            if abs(r_cal - current_calories) / current_calories > 0.3:
                continue
        alternatives.append(
            {
                "id": r["id"],
                "title": r["title"],
                "calories": r["calories"],
                "protein": r["protein"],
                "fat": r["fat"],
                "carbs": r["carbs"],
                "meal_type": r.get("meal_type"),
                "prep_time_min": r.get("prep_time_min"),
                "category": r.get("category"),
            }
        )

    return {"alternatives": alternatives[:5]}


@router.post("/plans/{plan_id}/swap-meal")
async def swap_meal(
    plan_id: uuid.UUID,
    data: SwapMealRequest,
    db: AsyncSession = Depends(get_db),
):
    """Заменить одно блюдо в плане."""
    plan, plan_data = await _load_ready_plan_with_data(plan_id, db)
    day, old_meal, meal_idx = _find_day_and_meal(plan_data, data.day_number, data.meal_type)

    # Find the new recipe
    from app.core.rag.retriever import _get_all_recipes

    all_recipes = await _get_all_recipes(db)

    if data.new_recipe_id:
        new_recipe = next((r for r in all_recipes if r["id"] == str(data.new_recipe_id)), None)
        if not new_recipe:
            raise HTTPException(status_code=404, detail="Recipe not found")
    else:
        # Auto-select: same meal_type, closest calories, not current
        current_cal = old_meal.get("calories", 0)
        current_id = old_meal.get("recipe_id")
        used_ids = {m.get("recipe_id") for m in day.get("meals", [])}

        candidates = [
            r
            for r in all_recipes
            if data.meal_type in ((r.get("meal_type") or "").strip())
            and r["id"] != current_id
            and r["id"] not in used_ids
        ]
        if not candidates:
            raise HTTPException(status_code=404, detail="No alternative recipes available")

        candidates.sort(key=lambda r: abs(r["calories"] - current_cal))
        new_recipe = candidates[0]

    # Build new meal entry
    new_meal = {
        "type": data.meal_type,
        "time": old_meal.get("time", "12:00"),
        "recipe_id": new_recipe["id"],
        "title": new_recipe["title"],
        "calories": new_recipe["calories"],
        "protein": new_recipe["protein"],
        "fat": new_recipe["fat"],
        "carbs": new_recipe["carbs"],
        "ingredients_summary": new_recipe.get("ingredients", []),
    }

    day["meals"][meal_idx] = new_meal
    _recalc_day_totals(day)

    await sync_plan_rows(db, plan_record=plan, plan_data=plan_data, event_type="meal_swapped")
    await db.commit()
    await cache.delete(_plan_response_cache_key(plan_id))
    await cache.delete(_shopping_list_cache_key(plan_id))

    logger.info(
        "Swapped meal: plan={} day={} type={} → {}",
        plan_id,
        data.day_number,
        data.meal_type,
        new_recipe["title"],
    )

    return {"day": day}


@router.post("/plans/{plan_id}/cancel-meal")
async def cancel_meal(
    plan_id: uuid.UUID,
    data: CancelMealRequest,
    db: AsyncSession = Depends(get_db),
):
    """Убрать блюдо из плана (пересчитать итоги дня)."""
    plan, plan_data = await _load_ready_plan_with_data(plan_id, db)
    day, _, meal_idx = _find_day_and_meal(plan_data, data.day_number, data.meal_type)

    day["meals"].pop(meal_idx)
    _recalc_day_totals(day)

    await sync_plan_rows(db, plan_record=plan, plan_data=plan_data, event_type="meal_cancelled")
    await db.commit()
    await cache.delete(_plan_response_cache_key(plan_id))
    await cache.delete(_shopping_list_cache_key(plan_id))

    logger.info("Cancelled meal: plan={} day={} type={}", plan_id, data.day_number, data.meal_type)

    return {"day": day}
