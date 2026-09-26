"""Deterministic catalog coverage checks and bounded automatic replenishment."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from sqlalchemy import select

from app.config import settings
from app.core.catalog_agents import build_research_agent, build_verification_agent
from app.core.rag import retriever
from app.core.source_discovery import DiscoverySourceOutput
from app.core.source_discovery_runtime import run_source_discovery_pipeline
from app.core.source_harvester import discover_source_urls
from app.db.models import DEFAULT_MEAL_SCHEDULE, SourceCandidate
from app.db.session import async_session

CatalogMaintenanceProgress = Callable[[dict[str, Any]], None]

_SLOT_QUERY_VARIANTS: dict[str, tuple[str, ...]] = {
    "breakfast": ("овсяная каша", "омлет", "сырники"),
    "lunch": ("суп", "курица с гарниром", "паста"),
    "dinner": ("рыба с овощами", "запеченная курица", "тушеные овощи"),
    "snack": ("перекус", "йогурт", "салат"),
    "second_snack": ("перекус", "йогурт", "салат"),
}


def _emit(
    progress_callback: CatalogMaintenanceProgress | None,
    *,
    phase: str,
    message: str,
    slot: str | None = None,
    diagnostics: dict[str, Any] | None = None,
    attempted_sources: int = 0,
    accepted_sources: int = 0,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "phase": phase,
            "message": message,
            "slot": slot,
            "diagnostics": deepcopy(diagnostics) if diagnostics is not None else None,
            "attempted_sources": attempted_sources,
            "accepted_sources": accepted_sources,
        }
    )


def _target_slots(diagnostics: dict[str, Any], user_profile: dict[str, Any]) -> list[str]:
    missing = [str(slot) for slot in diagnostics.get("missing_slots") or []]
    if missing:
        return list(dict.fromkeys(missing))
    schedule = user_profile.get("meal_schedule") or DEFAULT_MEAL_SCHEDULE
    return list(
        dict.fromkeys(
            str(slot.get("type") or "").strip()
            for slot in schedule
            if str(slot.get("type") or "").strip()
        )
    )


def _queries_for_slot(slot: str) -> tuple[str, ...]:
    return _SLOT_QUERY_VARIANTS.get(slot, (slot.replace("_", " "),))


def _with_auto_fill_provenance(
    source: DiscoverySourceOutput,
    *,
    slot: str,
    query: str,
) -> DiscoverySourceOutput:
    return DiscoverySourceOutput(
        url=source.url,
        source_type=source.source_type,
        discovery_query=source.discovery_query or query,
        discovery_payload={
            **(source.discovery_payload or {}),
            "automatic_catalog_fill": True,
            "target_slot": slot,
        },
        provenance={
            **(source.provenance or {}),
            "automatic_catalog_fill": True,
            "target_slot": slot,
            "catalog_fill_query": query,
        },
        discovered_by="catalog_auto_fill",
    )


async def ensure_catalog_coverage(
    user_profile: dict[str, Any],
    *,
    days: int,
    progress_callback: CatalogMaintenanceProgress | None = None,
) -> dict[str, Any]:
    """Ensure bounded, profile-safe catalog coverage before meal-plan LLM calls.

    The function reuses the existing discovery/research/verification/admission
    workflow. It never inserts recipes directly and stops as soon as coverage is
    sufficient or the configured source-attempt budget is exhausted.
    """
    async with async_session() as session:
        diagnostics = await retriever.assess_profile_recipe_pool(
            session,
            user_profile=user_profile,
            days=days,
        )
        summary = {
            "enabled": settings.CATALOG_AUTO_FILL_ENABLED,
            "attempted_sources": 0,
            "accepted_sources": 0,
            "target_slots": [],
        }
        if diagnostics["feasible"]:
            _emit(
                progress_callback,
                phase="ready",
                message="Каталог уже содержит достаточно подходящих рецептов.",
                diagnostics=diagnostics,
            )
            return {**diagnostics, "auto_fill": summary}

        targets = _target_slots(diagnostics, user_profile)
        summary["target_slots"] = targets
        if not settings.CATALOG_AUTO_FILL_ENABLED:
            _emit(
                progress_callback,
                phase="disabled",
                message="Автопополнение каталога отключено.",
                diagnostics=diagnostics,
            )
            return {**diagnostics, "auto_fill": summary}

        existing = await session.execute(select(SourceCandidate.url))
        seen_urls = {str(url) for url in existing.scalars().all()}
        total_budget = settings.CATALOG_AUTO_FILL_MAX_SOURCES
        per_slot_budget = max(1, total_budget // max(1, len(targets)))
        batch_size = min(
            settings.CATALOG_AUTO_FILL_BATCH_SIZE,
            settings.CATALOG_MAX_SOURCES_PER_JOB,
        )
        research_agent = build_research_agent()
        verification_agent = build_verification_agent()

        for slot in targets:
            attempted_for_slot = 0
            for query in _queries_for_slot(slot):
                if diagnostics["feasible"] or summary["attempted_sources"] >= total_budget:
                    break
                current_missing = set(diagnostics.get("missing_slots") or [])
                if current_missing and slot not in current_missing:
                    break
                remaining_slot = per_slot_budget - attempted_for_slot
                remaining_total = total_budget - summary["attempted_sources"]
                if remaining_slot <= 0 or remaining_total <= 0:
                    break

                _emit(
                    progress_callback,
                    phase="discover",
                    slot=slot,
                    message=f"Ищем рецепты для {slot}: {query}.",
                    diagnostics=diagnostics,
                    attempted_sources=summary["attempted_sources"],
                    accepted_sources=summary["accepted_sources"],
                )
                discovered = await discover_source_urls(query=query)
                fresh = [source for source in discovered if source.url not in seen_urls]
                batch = fresh[: min(batch_size, remaining_slot, remaining_total)]
                if not batch:
                    continue

                batch = [
                    _with_auto_fill_provenance(source, slot=slot, query=query)
                    for source in batch
                ]
                seen_urls.update(source.url for source in batch)
                summary["attempted_sources"] += len(batch)
                attempted_for_slot += len(batch)

                async def discovery_agent(
                    _seed_input: dict[str, Any],
                    selected: tuple[DiscoverySourceOutput, ...] = tuple(batch),
                ) -> list[DiscoverySourceOutput]:
                    return list(selected)

                _emit(
                    progress_callback,
                    phase="ingest",
                    slot=slot,
                    message=f"Проверяем {len(batch)} источника для {slot}.",
                    diagnostics=diagnostics,
                    attempted_sources=summary["attempted_sources"],
                    accepted_sources=summary["accepted_sources"],
                )
                result = await run_source_discovery_pipeline(
                    session,
                    seed_input={
                        "query": query,
                        "automatic_catalog_fill": True,
                        "target_slot": slot,
                    },
                    discovery_agent=discovery_agent,
                    research_agent=research_agent,
                    verification_agent=verification_agent,
                )
                summary["accepted_sources"] += sum(
                    1 for item in (result.items or []) if item.get("status") == "ACCEPTED"
                )
                diagnostics = await retriever.assess_profile_recipe_pool(
                    session,
                    user_profile=user_profile,
                    days=days,
                )
                _emit(
                    progress_callback,
                    phase="recheck",
                    slot=slot,
                    message=(
                        "Покрытие каталога восстановлено."
                        if diagnostics["feasible"]
                        else f"Проверяем покрытие после пополнения {slot}."
                    ),
                    diagnostics=diagnostics,
                    attempted_sources=summary["attempted_sources"],
                    accepted_sources=summary["accepted_sources"],
                )
                if diagnostics["feasible"]:
                    return {**diagnostics, "auto_fill": summary}

        _emit(
            progress_callback,
            phase="exhausted",
            message="Лимит автопополнения исчерпан, покрытия каталога всё ещё недостаточно.",
            diagnostics=diagnostics,
            attempted_sources=summary["attempted_sources"],
            accepted_sources=summary["accepted_sources"],
        )
        return {**diagnostics, "auto_fill": summary}
