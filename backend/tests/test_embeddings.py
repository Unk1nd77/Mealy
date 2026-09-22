"""Tests for the OpenRouter embedding client."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core import embeddings


def test_build_recipe_embedding_text_contains_searchable_fields():
    text = embeddings.build_recipe_embedding_text(
        {
            "title": "Курица с рисом",
            "description": "Полезный обед",
            "meal_type": "lunch",
            "ingredients": [{"name": "Куриное филе", "amount": 200, "unit": "g"}],
            "tags": ["высокобелковый"],
            "allergens": [],
        }
    )

    assert "Курица с рисом" in text
    assert "Куриное филе" in text
    assert "высокобелковый" in text


@pytest.mark.asyncio
async def test_embed_texts_preserves_provider_index_order(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(embeddings.settings, "EMBEDDING_DIMENSIONS", 3)
    captured_payload = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0, 0.0]},
                    {"index": 0, "embedding": [1.0, 0.0, 0.0]},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await embeddings.embed_texts(
            ["first", "second"], input_type="search_document", client=client
        )

    assert result == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    assert captured_payload["model"] == embeddings.settings.EMBEDDING_MODEL_NAME
    assert captured_payload["dimensions"] == 3
    assert captured_payload["input_type"] == "search_document"


@pytest.mark.asyncio
async def test_embed_texts_rejects_wrong_vector_dimension(monkeypatch):
    monkeypatch.setattr(embeddings.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(embeddings.settings, "EMBEDDING_DIMENSIONS", 3)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(embeddings.EmbeddingServiceError, match="dimension"):
            await embeddings.embed_texts(["query"], client=client)
