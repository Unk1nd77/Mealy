"""Tests for catalog source resolution and snapshotting."""

from __future__ import annotations

import json

import pytest

from app.core import catalog_sources


@pytest.mark.asyncio
async def test_resolve_catalog_source_from_payload():
    resolved = await catalog_sources.resolve_catalog_source(
        {
            "payload": {
                "title": "Chicken bowl",
                "description": "Simple lunch",
                "ingredients": [{"name": "Chicken", "amount": 200, "unit": "g"}],
                "meal_type": "lunch",
            },
            "source_name": "seed.json",
            "provenance": {"dataset": "seed.json"},
        }
    )

    assert resolved.source_type == "payload"
    assert resolved.source_snapshot["title"] == "Chicken bowl"
    assert resolved.provenance["dataset"] == "seed.json"
    assert resolved.research_input["source_snapshot"]["payload_excerpt"]["meal_type"] == "lunch"


@pytest.mark.asyncio
async def test_resolve_catalog_source_fetches_url(monkeypatch):
    class _FakeResponse:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        text = "<html><head><title>Chicken Bowl</title><meta name='description' content='Tasty lunch'></head><body>Recipe text</body></html>"
        url = "https://example.com/recipe"

        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            assert url == "https://example.com/recipe"
            return _FakeResponse()

    monkeypatch.setattr(catalog_sources.httpx, "AsyncClient", lambda **kwargs: _FakeClient())

    resolved = await catalog_sources.resolve_catalog_source(
        {"source_url": "https://example.com/recipe"}
    )

    assert resolved.source_type == "web"
    assert resolved.source_snapshot["title"] == "Chicken Bowl"
    assert "Recipe text" in resolved.source_snapshot["html_excerpt"]
    assert resolved.provenance["resolver"] == "http_fetch"


def test_build_html_snapshot_parses_json_ld_recipe():
    recipe = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Курица с рисом",
        "description": "Полезный обед",
        "recipeIngredient": ["200 г куриное филе", "Рис - 100 г"],
        "nutrition": {
            "calories": "520 kcal",
            "proteinContent": "45 g",
            "fatContent": "8 g",
            "carbohydrateContent": "62 g",
        },
        "recipeYield": "2 порции",
        "totalTime": "PT45M",
        "recipeInstructions": [{"@type": "HowToStep", "text": "Запечь курицу."}],
    }
    html = (
        "<html><head><title>Fallback</title>"
        f'<script type="application/ld+json">{json.dumps(recipe, ensure_ascii=False)}</script>'
        "</head><body></body></html>"
    )

    resolved = catalog_sources._build_html_snapshot("https://example.com/recipe", html)
    structured = resolved.source_snapshot["structured_recipe"]

    assert resolved.source_snapshot["parser"] == "json_ld"
    assert resolved.source_snapshot["title"] == "Курица с рисом"
    assert structured["ingredients"] == [
        {"name": "куриное филе", "amount": 200.0, "unit": "g", "amount_text": "200 г"},
        {"name": "Рис", "amount": 100.0, "unit": "g", "amount_text": "100 г"},
    ]
    assert structured["nutrition"]["calories"] == 520.0
    assert structured["prep_time_min"] == 45
    assert structured["cooking_steps"] == ["Запечь курицу."]
