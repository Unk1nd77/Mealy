"""Async Redis cache layer.

Provides JSON get/set/delete with TTL and key prefixing.
Uses the same Redis instance as Celery (keys are namespaced by prefix).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import redis.asyncio as aioredis
from loguru import logger
from redis.exceptions import RedisError

from app.config import settings

PREFIX = "nutri:"

_clients_by_loop: dict[int, aioredis.Redis] = {}
JSONValidator = Callable[[Any], bool]


def build_key(*parts: object) -> str:
    """Build a deterministic cache key from non-empty parts."""
    return ":".join(str(part) for part in parts if str(part))


async def get_redis() -> aioredis.Redis:
    """Return an async Redis client bound to the current event loop.

    redis.asyncio connections are loop-bound. Reusing one global client across
    different Celery task loops causes cross-loop futures and closed-loop errors.
    """
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    client = _clients_by_loop.get(loop_id)
    if client is None:
        client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        _clients_by_loop[loop_id] = client
    return client


async def get_json(
    key: str,
    *,
    validator: JSONValidator | None = None,
    delete_invalid: bool = True,
) -> Any | None:
    """Get and validate a JSON-serialized value from cache."""
    r = await get_redis()
    full_key = f"{PREFIX}{key}"
    raw = await r.get(full_key)
    if raw is None:
        return None

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Cache: invalid JSON for key {}", key)
        if delete_invalid:
            await r.delete(full_key)
        return None

    if validator and not validator(payload):
        logger.warning("Cache: stale or invalid payload for key {}", key)
        if delete_invalid:
            await r.delete(full_key)
        return None

    return payload


async def set_json(key: str, value: Any, ttl: int = 3600) -> None:
    """Store a JSON-serializable value in cache with TTL (seconds)."""
    r = await get_redis()
    raw = json.dumps(value, ensure_ascii=False, default=str)
    await r.set(f"{PREFIX}{key}", raw, ex=ttl)


async def delete(key: str) -> None:
    """Delete a key from cache."""
    try:
        r = await get_redis()
        await r.delete(f"{PREFIX}{key}")
    except RedisError as exc:
        logger.warning(
            "Cache: delete skipped for key {} because Redis is unavailable: {}", key, exc
        )


async def close() -> None:
    """Close all cached Redis clients. Call on app shutdown."""
    clients = list(_clients_by_loop.values())
    _clients_by_loop.clear()
    for client in clients:
        await client.aclose()
