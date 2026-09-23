"""Verify catalog embeddings, HNSW index, and hybrid retrieval end to end."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.config import settings
from app.core.rag.retriever import search_recipes
from app.db.session import async_session


async def verify(query: str) -> None:
    async with async_session() as session:
        counts = (
            await session.execute(
                text(
                    "SELECT count(*) AS recipes, count(embedding) AS embedded, "
                    "count(*) FILTER (WHERE embedding_model = :model) AS current_model "
                    "FROM recipes"
                ),
                {"model": settings.EMBEDDING_MODEL_NAME},
            )
        ).one()
        index_exists = bool(
            (
                await session.execute(
                    text(
                        "SELECT 1 FROM pg_indexes "
                        "WHERE tablename = 'recipes' "
                        "AND indexname = 'ix_recipes_embedding_hnsw'"
                    )
                )
            ).scalar_one_or_none()
        )
        results = await search_recipes(session, semantic_query=query, limit=5)

    print(
        f"recipes={counts.recipes} embedded={counts.embedded} "
        f"current_model={counts.current_model} hnsw={index_exists}"
    )
    for position, recipe in enumerate(results, start=1):
        score = recipe.get("_semantic_similarity")
        print(f"{position}. {recipe['title']} | similarity={score}")

    if not index_exists or counts.recipes == 0 or counts.embedded != counts.recipes:
        raise RuntimeError("Catalog vector verification failed")
    if not results or all(item.get("_semantic_similarity") is None for item in results):
        raise RuntimeError("Vector retrieval did not return semantic scores")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="полезный рыбный ужин")
    args = parser.parse_args()
    asyncio.run(verify(args.query))


if __name__ == "__main__":
    main()
