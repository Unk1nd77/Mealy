"""Backfill missing or stale recipe embeddings in bounded batches."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.embeddings import build_recipe_embedding_text, embed_texts
from app.core.relational_store import recipe_to_dict
from app.db.models import Recipe
from app.db.session import async_session


async def backfill(*, force: bool = False, batch_size: int | None = None) -> tuple[int, int]:
    size = batch_size or settings.EMBEDDING_BATCH_SIZE
    updated = 0
    async with async_session() as session:
        stmt = select(Recipe).options(
            selectinload(Recipe.normalized_ingredients),
            selectinload(Recipe.normalized_tags),
            selectinload(Recipe.normalized_allergens),
        )
        if not force:
            stmt = stmt.where(
                or_(
                    Recipe.embedding.is_(None),
                    Recipe.embedding_model.is_distinct_from(settings.EMBEDDING_MODEL_NAME),
                )
            )
        recipes = list((await session.execute(stmt.order_by(Recipe.id))).scalars().all())
        total = len(recipes)
        for offset in range(0, total, size):
            batch = recipes[offset : offset + size]
            vectors = await embed_texts(
                [build_recipe_embedding_text(recipe_to_dict(recipe)) for recipe in batch],
                input_type="search_document",
            )
            for recipe, vector in zip(batch, vectors, strict=True):
                recipe.embedding = vector
                recipe.embedding_model = settings.EMBEDDING_MODEL_NAME
                recipe.embedding_updated_at = datetime.utcnow()
            await session.commit()
            updated += len(batch)
            print(f"Embedded {updated}/{total} recipes")
    return updated, total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--batch-size", type=int)
    args = parser.parse_args()
    updated, total = asyncio.run(backfill(force=args.force, batch_size=args.batch_size))
    print(f"Backfill complete: {updated} of {total} selected recipes updated")


if __name__ == "__main__":
    main()
