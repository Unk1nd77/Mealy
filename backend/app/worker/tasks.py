"""Celery-задачи для фоновой генерации планов питания."""

from __future__ import annotations

import asyncio
from copy import deepcopy

from loguru import logger

from app.core.agent.contracts import GENERATION_TASK_NAME
from app.core.agent.use_case import generate_meal_plan as generate_production_plan
from app.core.catalog_agent_runtime import run_catalog_agent_pipeline
from app.core.catalog_agents import build_research_agent, build_verification_agent
from app.core.relational_store import finalize_generation_run_by_task_id
from app.core.source_discovery import DiscoverySourceOutput
from app.core.source_discovery_runtime import run_source_discovery_pipeline
from app.core.source_harvester import discover_source_urls
from app.worker import celery_app

_worker_loop: asyncio.AbstractEventLoop | None = None


def _run_async(coro):
    """Helper to run async code inside sync Celery task.

    Celery tasks in this worker share module-level async resources such as the
    SQLAlchemy async engine and Redis clients. Recreating and closing a brand
    new event loop for every task makes those resources cross loop boundaries,
    which triggers "Future attached to a different loop" / "Event loop is
    closed" errors on later tasks. Keep one stable loop per worker process.
    """
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()

    asyncio.set_event_loop(_worker_loop)
    return _worker_loop.run_until_complete(coro)


def _publish_progress(task, state: dict, *, celery_state: str = "GENERATING") -> None:
    task.update_state(state=celery_state, meta=deepcopy(state))


def _empty_catalog_steps() -> list[dict]:
    return [
        {"key": "research", "status": "pending", "message": ""},
        {"key": "candidate", "status": "pending", "message": ""},
        {"key": "verify", "status": "pending", "message": ""},
        {"key": "admit", "status": "pending", "message": ""},
    ]


def _empty_discovery_steps() -> list[dict]:
    return [
        {"key": "discover", "status": "pending", "message": ""},
        {"key": "source", "status": "pending", "message": ""},
        {"key": "research", "status": "pending", "message": ""},
        {"key": "candidate", "status": "pending", "message": ""},
        {"key": "verify", "status": "pending", "message": ""},
        {"key": "admit", "status": "pending", "message": ""},
    ]


def _build_discovery_agent():
    async def discovery_agent(seed_input: dict) -> list[DiscoverySourceOutput]:
        urls = seed_input.get("source_urls") or []
        if seed_input.get("source_url"):
            urls = [seed_input["source_url"], *urls]
        if urls:
            outputs: list[DiscoverySourceOutput] = []
            for url in urls:
                outputs.append(
                    DiscoverySourceOutput(
                        url=url,
                        source_type="web",
                        discovery_query=seed_input.get("query"),
                        discovery_payload={"seed_input": seed_input},
                        provenance=seed_input.get("provenance") or {},
                        discovered_by="source_discovery_seed",
                    )
                )
            return outputs
        return await discover_source_urls(
            query=seed_input.get("query"),
            domains=seed_input.get("domains"),
        )

    return discovery_agent


async def _generate_agentic(
    user_id: str,
    days: int,
    *,
    task=None,
    progress_state_holder: dict | None = None,
) -> dict:
    def progress(state: dict, celery_state: str = "GENERATING") -> None:
        if progress_state_holder is not None:
            progress_state_holder["state"] = deepcopy(state)
        if task is not None:
            _publish_progress(task, state, celery_state=celery_state)

    return await generate_production_plan(user_id=user_id, days=days, progress_callback=progress)


async def _finalize_generation_task_run(task_id: str, result: dict) -> None:
    from app.db.session import async_session

    async with async_session() as session:
        await finalize_generation_run_by_task_id(session, task_id=task_id, result=result)


async def _run_catalog_ingest(
    seed_input: dict, task=None, progress_state_holder: dict | None = None
) -> dict:
    from app.db.session import async_session

    progress_state = {
        "mode": "catalog_llm_pair",
        "status": "RUNNING",
        "current_step": None,
        "steps": _empty_catalog_steps(),
        "candidate_id": None,
        "review_id": None,
        "recipe_id": None,
        "reason_codes": [],
        "error": None,
    }

    def _on_progress(state: dict[str, object]) -> None:
        merged = {**progress_state, **deepcopy(state)}
        if progress_state_holder is not None:
            progress_state_holder["state"] = deepcopy(merged)
        if task is not None:
            _publish_progress(task, merged)

    async with async_session() as session:
        result = await run_catalog_agent_pipeline(
            session,
            seed_input=seed_input,
            research_agent=build_research_agent(),
            verification_agent=build_verification_agent(),
            progress_callback=_on_progress if task is not None else None,
        )

    payload = {
        "status": result.status,
        "mode": "catalog_llm_pair",
        "candidate_id": result.candidate_id,
        "review_id": result.review_id,
        "recipe_id": result.recipe_id,
        "reason_codes": result.reason_codes or [],
        "error": result.error,
        "steps": result.steps or _empty_catalog_steps(),
        "current_step": result.current_step,
    }
    if progress_state_holder is not None:
        progress_state_holder["state"] = deepcopy(payload)
    if task is not None:
        _publish_progress(
            task, payload, celery_state="SUCCESS" if result.status == "ACCEPTED" else "GENERATING"
        )
    return payload


async def _run_source_discovery_ingest(
    seed_input: dict, task=None, progress_state_holder: dict | None = None
) -> dict:
    from app.db.session import async_session

    progress_state = {
        "mode": "source_discovery_ingest",
        "status": "RUNNING",
        "current_step": None,
        "steps": _empty_discovery_steps(),
        "source_candidate_id": None,
        "candidate_id": None,
        "review_id": None,
        "recipe_id": None,
        "reason_codes": [],
        "error": None,
        "items": [],
    }

    def _on_progress(state: dict[str, object]) -> None:
        merged = {**progress_state, **deepcopy(state)}
        if progress_state_holder is not None:
            progress_state_holder["state"] = deepcopy(merged)
        if task is not None:
            _publish_progress(task, merged)

    async with async_session() as session:
        result = await run_source_discovery_pipeline(
            session,
            seed_input=seed_input,
            discovery_agent=_build_discovery_agent(),
            research_agent=build_research_agent(),
            verification_agent=build_verification_agent(),
            progress_callback=_on_progress if task is not None else None,
        )

    payload = {
        "status": result.status,
        "mode": "source_discovery_ingest",
        "source_candidate_id": result.source_candidate_id,
        "candidate_id": result.candidate_id,
        "review_id": result.review_id,
        "recipe_id": result.recipe_id,
        "reason_codes": result.reason_codes or [],
        "error": result.error,
        "items": result.items or [],
        "steps": result.steps or _empty_discovery_steps(),
        "current_step": result.current_step,
    }
    if progress_state_holder is not None:
        progress_state_holder["state"] = deepcopy(payload)
    if task is not None:
        _publish_progress(
            task, payload, celery_state="SUCCESS" if result.status == "ACCEPTED" else "GENERATING"
        )
    return payload


@celery_app.task(name=GENERATION_TASK_NAME, bind=True)
def generate_meal_plan(self, user_id: str, days: int = 7, mode: str = "agentic"):
    logger.info(
        "Task started: generate_meal_plan user={} days={} mode={}",
        user_id,
        days,
        mode,
    )
    self.update_state(state="GENERATING")
    progress_state_holder: dict[str, dict] = {}
    try:
        if mode != "agentic":
            raise ValueError(f"Unsupported generation mode: {mode}")
        result = _run_async(
            _generate_agentic(
                user_id,
                days,
                task=self,
                progress_state_holder=progress_state_holder,
            )
        )
        _run_async(_finalize_generation_task_run(str(self.request.id), result))
        return result
    except Exception as exc:
        logger.exception(
            "Task failed: generate_meal_plan user={} days={} mode={}", user_id, days, mode
        )
        last_state = progress_state_holder.get("state") or {}
        result = {
            "status": "FAILED",
            "mode": "agentic",
            "quality_status": "failed",
            "warnings": last_state.get("warnings") or [str(exc)],
            "error": str(exc),
            "steps": last_state.get("steps") or [],
            "current_step": last_state.get("current_step"),
        }
        _run_async(_finalize_generation_task_run(str(self.request.id), result))
        return result


@celery_app.task(name="run_catalog_ingest", bind=True)
def run_catalog_ingest(self, seed_input: dict):
    logger.info("Task started: run_catalog_ingest")
    self.update_state(state="GENERATING")
    progress_state_holder: dict[str, dict] = {}
    try:
        return _run_async(
            _run_catalog_ingest(
                seed_input,
                task=self,
                progress_state_holder=progress_state_holder,
            )
        )
    except Exception as exc:
        logger.exception("Task failed: run_catalog_ingest")
        last_state = progress_state_holder.get("state") or {}
        return {
            "status": "FAILED",
            "mode": "catalog_llm_pair",
            "candidate_id": last_state.get("candidate_id"),
            "review_id": last_state.get("review_id"),
            "recipe_id": last_state.get("recipe_id"),
            "reason_codes": last_state.get("reason_codes") or [],
            "error": str(exc),
            "steps": last_state.get("steps") or _empty_catalog_steps(),
            "current_step": last_state.get("current_step"),
        }


@celery_app.task(name="run_source_discovery_ingest", bind=True)
def run_source_discovery_ingest(self, seed_input: dict):
    logger.info("Task started: run_source_discovery_ingest")
    self.update_state(state="GENERATING")
    progress_state_holder: dict[str, dict] = {}
    try:
        return _run_async(
            _run_source_discovery_ingest(
                seed_input,
                task=self,
                progress_state_holder=progress_state_holder,
            )
        )
    except Exception as exc:
        logger.exception("Task failed: run_source_discovery_ingest")
        last_state = progress_state_holder.get("state") or {}
        return {
            "status": "FAILED",
            "mode": "source_discovery_ingest",
            "source_candidate_id": last_state.get("source_candidate_id"),
            "candidate_id": last_state.get("candidate_id"),
            "review_id": last_state.get("review_id"),
            "recipe_id": last_state.get("recipe_id"),
            "reason_codes": last_state.get("reason_codes") or [],
            "error": str(exc),
            "items": last_state.get("items") or [],
            "steps": last_state.get("steps") or _empty_discovery_steps(),
            "current_step": last_state.get("current_step"),
        }
