"""Controlled live check for one allowlisted recipe source."""

from __future__ import annotations

import os

import pytest

from app.core.catalog_sources import fetch_source_url


@pytest.mark.live_source
@pytest.mark.asyncio
async def test_live_gastronom_recipe_snapshot():
    if os.getenv("RUN_LIVE_SOURCE_TESTS") != "1":
        pytest.skip("RUN_LIVE_SOURCE_TESTS=1 is required")

    resolved = await fetch_source_url(
        "https://www.gastronom.ru/recipe/66683/beloe-polusladkoe-vino-v-domashnih-usloviyah"
    )

    assert resolved.source_url.startswith("https://www.gastronom.ru/")
    assert resolved.source_snapshot["title"]
    assert resolved.source_snapshot["parser"] in {"json_ld", "legacy_html"}
