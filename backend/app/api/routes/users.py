import uuid

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.api.schemas import UserCreate, UserResponse, UserUpdate
from app.core import cache
from app.core.relational_store import load_user_profile_from_rows, sync_user_normalized
from app.core.skills.calculator import calculate_target_calories
from app.db.models import DEFAULT_MEAL_SCHEDULE, User
from app.db.session import get_db

router = APIRouter(prefix="/api/users", tags=["Users"])


async def _build_profile_cache_from_rows(db: AsyncSession, user: User) -> dict:
    return await load_user_profile_from_rows(db, user)


async def _user_response(db: AsyncSession, user: User) -> UserResponse:
    return UserResponse.model_validate(await _build_profile_cache_from_rows(db, user))


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    target_cal = calculate_target_calories(
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        age=data.age,
        gender=data.gender,
        activity_level=data.activity_level,
        goal=data.goal,
    )

    schedule = (
        [s.model_dump() for s in data.meal_schedule]
        if data.meal_schedule
        else DEFAULT_MEAL_SCHEDULE
    )

    user = User(
        email=data.email,
        password_hash=_bcrypt.hashpw(data.password.encode(), _bcrypt.gensalt()).decode(),
        age=data.age,
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        gender=data.gender,
        activity_level=data.activity_level,
        goal=data.goal,
        target_calories=target_cal,
    )

    db.add(user)
    await sync_user_normalized(
        db,
        user,
        allergies=data.allergies,
        preferences=data.preferences,
        disliked_ingredients=data.disliked_ingredients,
        diseases=data.diseases,
        meal_schedule=schedule,
    )
    await db.commit()
    await db.refresh(user)

    logger.info("User created: {} (target_calories={})", user.email, target_cal)
    profile = await _build_profile_cache_from_rows(db, user)
    await cache.set_json(f"user:{user.id}", profile, ttl=600)

    return UserResponse.model_validate(profile)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return await _user_response(db, user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Cannot update another user's profile")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)
    current_profile = await _build_profile_cache_from_rows(db, user)
    allergies = update_data.pop("allergies", current_profile["allergies"])
    preferences = update_data.pop("preferences", current_profile["preferences"])
    disliked_ingredients = update_data.pop(
        "disliked_ingredients", current_profile["disliked_ingredients"]
    )
    diseases = update_data.pop("diseases", current_profile["diseases"])
    meal_schedule = update_data.pop("meal_schedule", current_profile["meal_schedule"])
    if meal_schedule is not None:
        meal_schedule = [s.model_dump() if hasattr(s, "model_dump") else s for s in meal_schedule]
    for field, value in update_data.items():
        setattr(user, field, value)

    user.target_calories = calculate_target_calories(
        weight_kg=user.weight_kg,
        height_cm=user.height_cm,
        age=user.age,
        gender=user.gender,
        activity_level=user.activity_level,
        goal=user.goal,
    )

    await sync_user_normalized(
        db,
        user,
        allergies=allergies,
        preferences=preferences,
        disliked_ingredients=disliked_ingredients,
        diseases=diseases,
        meal_schedule=meal_schedule or DEFAULT_MEAL_SCHEDULE,
    )
    await db.commit()
    await db.refresh(user)

    logger.info("User updated: {} (target_calories={})", user.email, user.target_calories)
    await cache.delete(f"user:{user_id}")
    profile = await _build_profile_cache_from_rows(db, user)
    await cache.set_json(f"user:{user.id}", profile, ttl=600)

    return UserResponse.model_validate(profile)
