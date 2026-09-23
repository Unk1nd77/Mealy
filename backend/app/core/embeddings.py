"""OpenRouter embedding service and canonical text builders."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from typing import Any

import httpx

from app.config import settings


class EmbeddingServiceError(RuntimeError):
    """Raised when the embedding provider returns an unusable response."""


def build_recipe_embedding_text(recipe: dict[str, Any]) -> str:
    """Build stable semantic content from the fields used to select a recipe."""
    ingredients = recipe.get("ingredients") or []
    ingredient_names = [
        str(item.get("name") or "").strip()
        for item in ingredients
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    tags = [str(value).strip() for value in recipe.get("tags") or [] if str(value).strip()]
    allergens = [
        str(value).strip() for value in recipe.get("allergens") or [] if str(value).strip()
    ]
    parts = [
        f"Название: {str(recipe.get('title') or '').strip()}",
        f"Описание: {str(recipe.get('description') or '').strip()}",
        f"Тип приема пищи: {str(recipe.get('meal_type') or 'universal').strip()}",
        f"Категория: {str(recipe.get('category') or '').strip()}",
        f"Ингредиенты: {', '.join(ingredient_names)}",
        f"Теги: {', '.join(tags)}",
        f"Аллергены: {', '.join(allergens)}",
    ]
    return "\n".join(part for part in parts if part.split(":", 1)[-1].strip())


def build_profile_search_query(profile: dict[str, Any]) -> str:
    """Describe positive retrieval intent; exclusions stay in deterministic filters."""
    schedule = profile.get("meal_schedule") or []
    meal_types = [str(slot.get("type")) for slot in schedule if slot.get("type")]
    preferences = [str(value) for value in profile.get("preferences") or []]
    diseases = [str(value) for value in profile.get("diseases") or []]
    return "\n".join(
        [
            "Подбор разнообразных рецептов для персонального плана питания.",
            f"Цель: {profile.get('goal') or 'сбалансированное питание'}.",
            f"Целевой калораж: {profile.get('target_calories') or 'не указан'} ккал.",
            f"Предпочтения: {', '.join(preferences) or 'нет'}.",
            f"Состояния здоровья: {', '.join(diseases) or 'нет'}.",
            f"Нужные приемы пищи: {', '.join(meal_types) or 'разные'}.",
        ]
    )


def _validate_embedding(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != settings.EMBEDDING_DIMENSIONS:
        raise EmbeddingServiceError(
            "Embedding provider returned an unexpected vector dimension: "
            f"expected {settings.EMBEDDING_DIMENSIONS}, got "
            f"{len(value) if isinstance(value, list) else 'non-list'}"
        )
    vector = [float(item) for item in value]
    if not all(math.isfinite(item) for item in vector):
        raise EmbeddingServiceError("Embedding contains non-finite values")
    return vector


async def embed_texts(
    texts: Sequence[str],
    *,
    input_type: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[list[float]]:
    """Embed texts in provider-sized batches while preserving input order."""
    normalized = [str(text).strip() for text in texts]
    if not normalized:
        return []
    if any(not text for text in normalized):
        raise EmbeddingServiceError("Cannot create an embedding for empty text")
    if not settings.OPENROUTER_API_KEY:
        raise EmbeddingServiceError("OPENROUTER_API_KEY is not configured")

    owns_client = client is None
    http_client = client or httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SEC)
    vectors: list[list[float]] = []
    try:
        for offset in range(0, len(normalized), settings.EMBEDDING_BATCH_SIZE):
            batch = normalized[offset : offset + settings.EMBEDDING_BATCH_SIZE]
            payload: dict[str, Any] = {
                "model": settings.EMBEDDING_MODEL_NAME,
                "input": batch,
                "dimensions": settings.EMBEDDING_DIMENSIONS,
                "encoding_format": "float",
            }
            if input_type:
                payload["input_type"] = input_type

            response: httpx.Response | None = None
            for attempt in range(settings.EMBEDDING_MAX_RETRIES):
                response = await http_client.post(
                    f"{settings.OPENROUTER_BASE_URL}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code not in {429, 500, 502, 503, 504, 529}:
                    break
                if attempt < settings.EMBEDDING_MAX_RETRIES - 1:
                    await asyncio.sleep(0.5 * (2**attempt))
            assert response is not None
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise EmbeddingServiceError(
                    f"Embedding provider returned HTTP {response.status_code}"
                ) from exc

            data = response.json().get("data")
            if not isinstance(data, list) or len(data) != len(batch):
                raise EmbeddingServiceError("Embedding provider returned an incomplete batch")
            ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
            vectors.extend(_validate_embedding(item.get("embedding")) for item in ordered)
    finally:
        if owns_client:
            await http_client.aclose()
    return vectors


async def embed_recipe(recipe: dict[str, Any]) -> list[float]:
    return (await embed_texts([build_recipe_embedding_text(recipe)], input_type="search_document"))[
        0
    ]


async def embed_search_query(query: str) -> list[float]:
    return (await embed_texts([query], input_type="search_query"))[0]
