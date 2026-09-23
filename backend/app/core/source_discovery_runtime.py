"""Runtime harness for autonomous source discovery before catalog ingest."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.config import settings
from app.core.catalog_agent_runtime import CatalogAgentRuntimeResult, run_catalog_agent_pipeline
from app.core.source_discovery import (
    DiscoveryStep,
    attach_source_candidate_to_recipe_candidate,
    create_source_candidate,
)
from app.db.models import SourceCandidateStatus

DiscoveryProgressCallback = Callable[[dict[str, Any]], None]

DISCOVERY_PIPELINE_STEPS = ["discover", "source", "research", "candidate", "verify", "admit"]


@dataclass
class DiscoveryRuntimeResult:
    status: str
    source_candidate_id: str | None
    candidate_id: str | None = None
    review_id: str | None = None
    recipe_id: str | None = None
    reason_codes: list[str] | None = None
    error: str | None = None
    steps: list[dict[str, Any]] | None = None
    current_step: str | None = None
    items: list[dict[str, Any]] | None = None


def _empty_steps() -> list[dict[str, Any]]:
    return [{"key": step, "status": "pending", "message": ""} for step in DISCOVERY_PIPELINE_STEPS]


def _set_step(
    state: dict[str, Any], key: str, *, status: str, message: str, activate: bool = True
) -> None:
    if activate:
        state["current_step"] = key
    for step in state["steps"]:
        if step["key"] == key:
            step["status"] = status
            step["message"] = message
            break


def _emit(progress_callback: DiscoveryProgressCallback | None, state: dict[str, Any]) -> None:
    if progress_callback is not None:
        progress_callback(deepcopy(state))


async def run_source_discovery_pipeline(
    session,
    *,
    seed_input: dict[str, Any],
    discovery_agent: DiscoveryStep,
    research_agent,
    verification_agent,
    progress_callback: DiscoveryProgressCallback | None = None,
) -> DiscoveryRuntimeResult:
    state: dict[str, Any] = {
        "status": "RUNNING",
        "current_step": None,
        "steps": _empty_steps(),
        "source_candidate_id": None,
        "candidate_id": None,
        "review_id": None,
        "recipe_id": None,
        "reason_codes": [],
        "error": None,
        "items": [],
    }

    try:
        _set_step(
            state, "discover", status="running", message="Discovery agent is finding source URLs."
        )
        _emit(progress_callback, state)
        discovered_sources = await discovery_agent(seed_input)
        if not discovered_sources:
            raise RuntimeError("Discovery returned no source URLs")
        discovered_sources = discovered_sources[: settings.CATALOG_MAX_SOURCES_PER_JOB]
        _set_step(
            state,
            "discover",
            status="completed",
            message=f"Discovery agent produced {len(discovered_sources)} source candidates.",
        )

        for position, source in enumerate(discovered_sources, start=1):
            _set_step(
                state,
                "source",
                status="running",
                message=f"Fetching and validating source {position}/{len(discovered_sources)}.",
            )
            _emit(progress_callback, state)
            try:
                source_candidate = await create_source_candidate(
                    session,
                    url=source.url,
                    source_type=source.source_type,
                    discovery_query=source.discovery_query,
                    discovery_payload=source.discovery_payload,
                    provenance=source.provenance,
                    discovered_by=source.discovered_by,
                )
            except Exception as exc:
                state["items"].append(
                    {
                        "url": source.url,
                        "status": "FAILED",
                        "source_candidate_id": None,
                        "candidate_id": None,
                        "review_id": None,
                        "recipe_id": None,
                        "reason_codes": ["source_fetch_failed"],
                        "error": str(exc),
                    }
                )
                continue
            source_candidate_id = str(source_candidate.id)
            if state["source_candidate_id"] is None:
                state["source_candidate_id"] = source_candidate_id

            if source_candidate.status == SourceCandidateStatus.rejected:
                report = source_candidate.validation_report or {}
                item = {
                    "url": source.url,
                    "status": "REJECTED",
                    "source_candidate_id": source_candidate_id,
                    "candidate_id": None,
                    "review_id": None,
                    "recipe_id": None,
                    "reason_codes": report.get("reason_codes") or [],
                    "error": (report.get("notes") or ["Source validation failed."])[0],
                }
                state["items"].append(item)
                state["reason_codes"] = item["reason_codes"]
                state["error"] = item["error"]
                continue

            _set_step(
                state,
                "source",
                status="completed",
                message=f"Source {position}/{len(discovered_sources)} passed validation.",
            )

            def catalog_progress(
                inner_state: dict[str, Any],
                source_position: int = position,
                source_count: int = len(discovered_sources),
            ) -> None:
                for step in state["steps"]:
                    if step["key"] in {"research", "candidate", "verify", "admit"}:
                        match = next(
                            (
                                inner_step
                                for inner_step in inner_state.get("steps", [])
                                if inner_step["key"] == step["key"]
                            ),
                            None,
                        )
                        if match is not None:
                            step["status"] = match["status"]
                            step["message"] = (
                                f"Source {source_position}/{source_count}: {match['message']}"
                            )
                state["current_step"] = inner_state.get("current_step") or state["current_step"]
                state["candidate_id"] = inner_state.get("candidate_id")
                state["review_id"] = inner_state.get("review_id")
                state["recipe_id"] = inner_state.get("recipe_id")
                state["reason_codes"] = inner_state.get("reason_codes") or []
                state["error"] = inner_state.get("error")
                _emit(progress_callback, state)

            catalog_result: CatalogAgentRuntimeResult = await run_catalog_agent_pipeline(
                session,
                seed_input={
                    **seed_input,
                    "source_url": source_candidate.url,
                    "source_type": source_candidate.source_type,
                    "source_snapshot": source_candidate.source_snapshot,
                    "provenance": source_candidate.provenance,
                },
                research_agent=research_agent,
                verification_agent=verification_agent,
                progress_callback=catalog_progress,
            )
            item = {
                "url": source_candidate.url,
                "status": catalog_result.status,
                "source_candidate_id": source_candidate_id,
                "candidate_id": catalog_result.candidate_id,
                "review_id": catalog_result.review_id,
                "recipe_id": catalog_result.recipe_id,
                "reason_codes": catalog_result.reason_codes or [],
                "error": catalog_result.error,
            }
            state["items"].append(item)
            if catalog_result.candidate_id:
                await attach_source_candidate_to_recipe_candidate(
                    session,
                    source_candidate_id=source_candidate_id,
                    recipe_candidate_id=catalog_result.candidate_id,
                )

        preferred = next(
            (item for item in state["items"] if item["status"] == "ACCEPTED"),
            next(
                (item for item in state["items"] if item["status"] == "REVIEW"),
                state["items"][0],
            ),
        )
        state.update(
            {
                "status": preferred["status"],
                "source_candidate_id": preferred["source_candidate_id"],
                "candidate_id": preferred["candidate_id"],
                "review_id": preferred["review_id"],
                "recipe_id": preferred["recipe_id"],
                "reason_codes": preferred["reason_codes"],
                "error": preferred["error"],
            }
        )
        _emit(progress_callback, state)
        return DiscoveryRuntimeResult(
            status=state["status"],
            source_candidate_id=state["source_candidate_id"],
            candidate_id=state["candidate_id"],
            review_id=state["review_id"],
            recipe_id=state["recipe_id"],
            reason_codes=state["reason_codes"],
            error=state["error"],
            steps=deepcopy(state["steps"]),
            current_step=state["current_step"],
            items=deepcopy(state["items"]),
        )
    except Exception as exc:
        state["status"] = "FAILED"
        state["error"] = str(exc)
        for step in reversed(state["steps"]):
            if step["status"] == "running":
                step["status"] = "failed"
                if not step["message"]:
                    step["message"] = str(exc)
                break
        _emit(progress_callback, state)
        return DiscoveryRuntimeResult(
            status=state["status"],
            source_candidate_id=state["source_candidate_id"],
            candidate_id=state["candidate_id"],
            review_id=state["review_id"],
            recipe_id=state["recipe_id"],
            reason_codes=state["reason_codes"],
            error=state["error"],
            steps=deepcopy(state["steps"]),
            current_step=state["current_step"],
            items=deepcopy(state["items"]),
        )
