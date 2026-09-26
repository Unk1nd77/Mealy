from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core import catalog_maintenance
from app.core.source_discovery import DiscoverySourceOutput


def _profile():
    return {
        "target_calories": 1900,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 35},
            {"type": "dinner", "time": "19:00", "calories_pct": 30},
            {"type": "snack", "time": "16:00", "calories_pct": 10},
        ],
        "allergies": [],
        "disliked_ingredients": [],
        "diseases": [],
        "preferences": [],
    }


@pytest.fixture
def maintenance_session(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [])
    )

    @asynccontextmanager
    async def factory():
        yield session

    monkeypatch.setattr(catalog_maintenance, "async_session", factory)
    return session


@pytest.mark.asyncio
async def test_auto_fill_does_nothing_when_catalog_is_already_feasible(
    monkeypatch, maintenance_session
):
    assess = AsyncMock(
        return_value={"feasible": True, "missing_slots": [], "slot_counts": {}}
    )
    discover = AsyncMock()
    monkeypatch.setattr(catalog_maintenance.retriever, "assess_profile_recipe_pool", assess)
    monkeypatch.setattr(catalog_maintenance, "discover_source_urls", discover)

    result = await catalog_maintenance.ensure_catalog_coverage(_profile(), days=7)

    assert result["feasible"] is True
    assert result["auto_fill"]["attempted_sources"] == 0
    discover.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_fill_reuses_catalog_pipeline_and_stops_after_coverage_recovers(
    monkeypatch, maintenance_session
):
    before = {
        "feasible": False,
        "missing_slots": ["breakfast"],
        "slot_counts": {"breakfast": 0, "lunch": 2, "dinner": 2, "snack": 2},
    }
    after = {
        "feasible": True,
        "missing_slots": [],
        "slot_counts": {"breakfast": 2, "lunch": 2, "dinner": 2, "snack": 2},
    }
    assess = AsyncMock(side_effect=[before, after])
    discover = AsyncMock(
        return_value=[
            DiscoverySourceOutput(url="https://eda.ru/recepty/zavtraki/test-1"),
        ]
    )
    pipeline = AsyncMock(
        return_value=SimpleNamespace(items=[{"status": "ACCEPTED"}])
    )
    monkeypatch.setattr(catalog_maintenance.retriever, "assess_profile_recipe_pool", assess)
    monkeypatch.setattr(catalog_maintenance, "discover_source_urls", discover)
    monkeypatch.setattr(catalog_maintenance, "run_source_discovery_pipeline", pipeline)
    monkeypatch.setattr(catalog_maintenance, "build_research_agent", lambda: AsyncMock())
    monkeypatch.setattr(catalog_maintenance, "build_verification_agent", lambda: AsyncMock())
    monkeypatch.setattr(catalog_maintenance.settings, "CATALOG_AUTO_FILL_BATCH_SIZE", 1)
    monkeypatch.setattr(catalog_maintenance.settings, "CATALOG_AUTO_FILL_MAX_SOURCES", 4)

    result = await catalog_maintenance.ensure_catalog_coverage(_profile(), days=7)

    assert result["feasible"] is True
    assert result["auto_fill"]["attempted_sources"] == 1
    assert result["auto_fill"]["accepted_sources"] == 1
    assert pipeline.await_count == 1
    kwargs = pipeline.await_args.kwargs
    assert kwargs["seed_input"]["automatic_catalog_fill"] is True
    assert kwargs["seed_input"]["target_slot"] == "breakfast"


@pytest.mark.asyncio
async def test_auto_fill_is_bounded_when_coverage_cannot_recover(
    monkeypatch, maintenance_session
):
    insufficient = {
        "feasible": False,
        "missing_slots": ["breakfast"],
        "slot_counts": {"breakfast": 0, "lunch": 2, "dinner": 2, "snack": 2},
    }
    assess = AsyncMock(side_effect=[insufficient, insufficient])
    discover = AsyncMock(
        return_value=[
            DiscoverySourceOutput(url="https://eda.ru/recepty/zavtraki/test-1"),
        ]
    )
    pipeline = AsyncMock(return_value=SimpleNamespace(items=[{"status": "FAILED"}]))
    monkeypatch.setattr(catalog_maintenance.retriever, "assess_profile_recipe_pool", assess)
    monkeypatch.setattr(catalog_maintenance, "discover_source_urls", discover)
    monkeypatch.setattr(catalog_maintenance, "run_source_discovery_pipeline", pipeline)
    monkeypatch.setattr(catalog_maintenance, "build_research_agent", lambda: AsyncMock())
    monkeypatch.setattr(catalog_maintenance, "build_verification_agent", lambda: AsyncMock())
    monkeypatch.setattr(catalog_maintenance.settings, "CATALOG_AUTO_FILL_BATCH_SIZE", 1)
    monkeypatch.setattr(catalog_maintenance.settings, "CATALOG_AUTO_FILL_MAX_SOURCES", 1)

    result = await catalog_maintenance.ensure_catalog_coverage(_profile(), days=7)

    assert result["feasible"] is False
    assert result["auto_fill"]["attempted_sources"] == 1
    assert pipeline.await_count == 1
