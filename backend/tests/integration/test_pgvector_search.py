"""Real PostgreSQL/pgvector integration check."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pgvector_hnsw_cosine_search():
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(
                text("CREATE TEMP TABLE vector_probe (id text, embedding vector(3))")
            )
            await connection.execute(
                text(
                    "CREATE INDEX vector_probe_hnsw ON vector_probe "
                    "USING hnsw (embedding vector_cosine_ops)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO vector_probe (id, embedding) VALUES "
                    "('fish', '[1,0,0]'), ('dessert', '[0,1,0]'), ('soup', '[0.7,0.3,0]')"
                )
            )
            rows = (
                (
                    await connection.execute(
                        text(
                            "SELECT id FROM vector_probe "
                            "ORDER BY embedding <=> CAST('[1,0,0]' AS vector) LIMIT 2"
                        )
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    assert rows == ["fish", "soup"]
