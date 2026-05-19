import uuid
from datetime import UTC, datetime, timedelta

import bcrypt as _bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AuthResponse, LoginRequest, UserCreate, UserResponse, UserUpdate
from app.config import settings
from app.core import cache
from app.core.relational_store import load_user_profile_from_rows, sync_user_normalized
from app.core.skills.calculator import calculate_target_calories
from app.db.models import DEFAULT_MEAL_SCHEDULE, ActivityLevel, Gender, Goal, User
from app.db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["Auth"])
bearer_scheme = HTTPBearer(auto_error=False)


async def _build_profile_cache_from_rows(db: AsyncSession, user: User) -> dict:
    return await load_user_profile_from_rows(db, user)


def _create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def _verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode(), password_hash.encode())


async def _authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not _verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return user


async def _get_or_create_dev_user(db: AsyncSession) -> User:
    """Возвращает demo-юзера для DEV_MODE, создавая его при необходимости."""
    result = await db.execute(select(User).where(User.email == settings.DEV_USER_EMAIL))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    target_calories = calculate_target_calories(
        weight_kg=72.0,
        height_cm=176.0,
        age=29,
        gender=Gender.male,
        activity_level=ActivityLevel.moderate,
        goal=Goal.maintain,
    )
    user = User(
        email=settings.DEV_USER_EMAIL,
        password_hash=_bcrypt.hashpw(
            settings.DEV_USER_PASSWORD.encode(), _bcrypt.gensalt()
        ).decode(),
        age=29,
        weight_kg=72.0,
        height_cm=176.0,
        gender=Gender.male,
        activity_level=ActivityLevel.moderate,
        goal=Goal.maintain,
        target_calories=target_calories,
    )
    db.add(user)
    await sync_user_normalized(
        db,
        user,
        allergies=[],
        preferences=[],
        disliked_ingredients=[],
        diseases=[],
        meal_schedule=DEFAULT_MEAL_SCHEDULE,
    )
    await db.commit()
    await db.refresh(user)
    logger.warning("DEV_MODE: auto-created demo user {}", user.email)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        if settings.DEV_MODE:
            return await _get_or_create_dev_user(db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def _issue_auth_response(db: AsyncSession, user: User) -> AuthResponse:
    access_token, expires_in = _create_access_token(user.id)
    profile = await _build_profile_cache_from_rows(db, user)
    return AuthResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(profile),
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user(data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    existing_user = existing.scalar_one_or_none()
    if existing_user:
        if settings.DEV_MODE:
            logger.warning(
                "DEV_MODE: /register treats existing email {} as login", data.email
            )
            return await _issue_auth_response(db, existing_user)
        raise HTTPException(status_code=409, detail="Email already registered")

    target_calories = calculate_target_calories(
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        age=data.age,
        gender=data.gender,
        activity_level=data.activity_level,
        goal=data.goal,
    )
    meal_schedule = (
        [slot.model_dump() for slot in data.meal_schedule]
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
        target_calories=target_calories,
    )
    db.add(user)
    await sync_user_normalized(
        db,
        user,
        allergies=data.allergies,
        preferences=data.preferences,
        disliked_ingredients=data.disliked_ingredients,
        diseases=data.diseases,
        meal_schedule=meal_schedule,
    )
    await db.commit()
    await db.refresh(user)

    await cache.set_json(
        f"user:{user.id}",
        await _build_profile_cache_from_rows(db, user),
        ttl=600,
    )
    logger.info("User registered via auth: {}", user.email)
    return await _issue_auth_response(db, user)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await _authenticate_user(data.email, data.password, db)
    logger.info("User logged in: {}", user.email)
    return await _issue_auth_response(db, user)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return UserResponse.model_validate(await _build_profile_cache_from_rows(db, current_user))


@router.put("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    current_profile = await _build_profile_cache_from_rows(db, current_user)
    allergies = update_data.pop("allergies", current_profile["allergies"])
    preferences = update_data.pop("preferences", current_profile["preferences"])
    disliked_ingredients = update_data.pop(
        "disliked_ingredients", current_profile["disliked_ingredients"]
    )
    diseases = update_data.pop("diseases", current_profile["diseases"])
    meal_schedule = update_data.pop("meal_schedule", current_profile["meal_schedule"])
    if meal_schedule is not None:
        meal_schedule = [
            slot.model_dump() if hasattr(slot, "model_dump") else slot for slot in meal_schedule
        ]

    for field, value in update_data.items():
        setattr(current_user, field, value)

    current_user.target_calories = calculate_target_calories(
        weight_kg=current_user.weight_kg,
        height_cm=current_user.height_cm,
        age=current_user.age,
        gender=current_user.gender,
        activity_level=current_user.activity_level,
        goal=current_user.goal,
    )

    await sync_user_normalized(
        db,
        current_user,
        allergies=allergies,
        preferences=preferences,
        disliked_ingredients=disliked_ingredients,
        diseases=diseases,
        meal_schedule=meal_schedule or DEFAULT_MEAL_SCHEDULE,
    )
    await db.commit()
    await db.refresh(current_user)
    await cache.delete(f"user:{current_user.id}")
    profile = await _build_profile_cache_from_rows(db, current_user)
    await cache.set_json(
        f"user:{current_user.id}",
        profile,
        ttl=600,
    )
    logger.info("User updated via auth: {}", current_user.email)
    return UserResponse.model_validate(profile)
