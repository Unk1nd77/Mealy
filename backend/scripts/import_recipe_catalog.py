"""Import a normalized recipe catalog from a local file or HTTPS URL."""

import argparse
import asyncio
import json
import sys
import urllib.request
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.recipe_catalog import RecipeCatalogError, normalize_recipe_payload
from app.core.relational_store import sync_recipe_normalized
from app.db.models import Recipe
from app.db.session import async_session


def _load_payload(source: str) -> list[dict[str, Any]]:
    if source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=60) as response:  # noqa: S310
            value = json.loads(response.read().decode("utf-8"))
    else:
        value = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("Catalog payload must be a JSON array")
    return value


async def import_catalog(source: str) -> None:
    payloads = _load_payload(source)
    imported = 0
    skipped = 0
    async with async_session() as session:
        existing_keys = set(
            (await session.execute(select(Recipe.title, Recipe.ingredients_short))).all()
        )
        for payload in payloads:
            try:
                normalized = normalize_recipe_payload(payload)
            except RecipeCatalogError as exc:
                skipped += 1
                print(f"Skip invalid recipe '{payload.get('title', 'unknown')}': {exc}")
                continue
            recipe_key = (normalized["title"], normalized.get("ingredients_short"))
            if recipe_key in existing_keys:
                skipped += 1
                continue
            recipe = Recipe(
                id=uuid.uuid4(),
                title=normalized["title"],
                description=normalized.get("description", ""),
                calories=normalized["calories"],
                protein=normalized["protein"],
                fat=normalized["fat"],
                carbs=normalized["carbs"],
                meal_type=normalized.get("meal_type"),
                ingredients_short=normalized.get("ingredients_short"),
                prep_time_min=normalized.get("prep_time_min"),
                category=normalized.get("category"),
            )
            session.add(recipe)
            await sync_recipe_normalized(
                session,
                recipe,
                ingredients=normalized["ingredients"],
                tags=normalized.get("tags", []),
                allergens=normalized.get("allergens", []),
            )
            existing_keys.add(recipe_key)
            imported += 1
        await session.commit()
    print(f"Imported {imported} recipes, skipped {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    args = parser.parse_args()
    asyncio.run(import_catalog(args.source))


if __name__ == "__main__":
    main()
