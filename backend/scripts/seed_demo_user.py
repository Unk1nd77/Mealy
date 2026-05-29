"""Create or refresh a demo user for manual QA and diploma defense."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import bcrypt as _bcrypt
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.relational_store import sync_user_normalized
from app.core.skills.calculator import calculate_target_calories
from app.db.models import (
    DEFAULT_MEAL_SCHEDULE,
    ActivityLevel,
    Gender,
    Goal,
    User,
)
from app.db.session import async_session


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or refresh Mealy demo user")
    parser.add_argument("--email", default="demo@example.com")
    parser.add_argument("--password", default="demo123456")
    parser.add_argument("--age", type=int, default=29)
    parser.add_argument("--weight-kg", type=float, default=72.0)
    parser.add_argument("--height-cm", type=float, default=176.0)
    parser.add_argument(
        "--gender",
        choices=[member.value for member in Gender],
        default=Gender.male.value,
    )
    parser.add_argument(
        "--activity-level",
        choices=[member.value for member in ActivityLevel],
        default=ActivityLevel.moderate.value,
    )
    parser.add_argument(
        "--goal",
        choices=[member.value for member in Goal],
        default=Goal.maintain.value,
    )
    parser.add_argument(
        "--allergies",
        default="nuts",
        help="Comma-separated allergies list",
    )
    parser.add_argument(
        "--preferences",
        default="high protein, simple dinners, fish",
        help="Comma-separated preferences list",
    )
    parser.add_argument(
        "--disliked-ingredients",
        default="liver",
        help="Comma-separated disliked ingredients list",
    )
    parser.add_argument(
        "--diseases",
        default="",
        help="Comma-separated diseases list",
    )
    return parser.parse_args()


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


async def _seed_demo_user(args: argparse.Namespace) -> None:
    gender = Gender(args.gender)
    activity_level = ActivityLevel(args.activity_level)
    goal = Goal(args.goal)

    target_calories = calculate_target_calories(
        weight_kg=args.weight_kg,
        height_cm=args.height_cm,
        age=args.age,
        gender=gender,
        activity_level=activity_level,
        goal=goal,
    )

    profile_lists = {
        "allergies": _split_csv(args.allergies),
        "preferences": _split_csv(args.preferences),
        "disliked_ingredients": _split_csv(args.disliked_ingredients),
        "diseases": _split_csv(args.diseases),
        "meal_schedule": DEFAULT_MEAL_SCHEDULE,
    }
    payload = {
        "password_hash": _bcrypt.hashpw(args.password.encode(), _bcrypt.gensalt()).decode(),
        "age": args.age,
        "weight_kg": args.weight_kg,
        "height_cm": args.height_cm,
        "gender": gender,
        "activity_level": activity_level,
        "goal": goal,
        "target_calories": target_calories,
    }

    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == args.email))
        user = result.scalar_one_or_none()

        action = "updated"
        if user is None:
            user = User(email=args.email, **payload)
            session.add(user)
            action = "created"
        else:
            for field, value in payload.items():
                setattr(user, field, value)

        await sync_user_normalized(session, user, **profile_lists)
        await session.commit()
        await session.refresh(user)

    print(
        json.dumps(
            {
                "status": action,
                "email": args.email,
                "password": args.password,
                "user_id": str(user.id),
                "target_calories": target_calories,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    asyncio.run(_seed_demo_user(_parse_args()))


if __name__ == "__main__":
    main()
