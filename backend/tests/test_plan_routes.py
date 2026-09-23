"""Unit-тесты API-роутов планов без живых внешних зависимостей."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.api.routes import plans


class _FakeAsyncResult:
    def __init__(self, state: str, result=None, info=None):
        self.state = state
        self.result = result
        self.info = info


@pytest.mark.asyncio
async def test_get_task_status_uses_progress_meta(monkeypatch):
    monkeypatch.setattr(
        plans,
        "AsyncResult",
        lambda task_id, app=None: _FakeAsyncResult(
            "GENERATING",
            info={
                "mode": "agent_cli",
                "quality_status": "partially_valid",
                "current_step": "validate",
                "steps": [{"key": "validate", "status": "running", "message": "Checking"}],
                "warnings": ["Day 2 fallback"],
            },
        ),
    )

    response = await plans.get_task_status("task-1")

    assert response.status == "GENERATING"
    assert response.mode == "agent_cli"
    assert response.quality_status == "partially_valid"
    assert response.current_step == "validate"
    assert response.steps[0]["key"] == "validate"
    assert response.warnings == ["Day 2 fallback"]


@pytest.mark.asyncio
async def test_get_task_status_uses_success_result_payload(monkeypatch):
    monkeypatch.setattr(
        plans,
        "AsyncResult",
        lambda task_id, app=None: _FakeAsyncResult(
            "SUCCESS",
            result={
                "plan_id": "plan-123",
                "status": "READY",
                "mode": "agent_cli",
                "quality_status": "valid",
                "current_step": "shopping-list",
                "steps": [{"key": "shopping-list", "status": "completed", "message": "Done"}],
                "warnings": [],
            },
            info={"mode": "llm_direct"},
        ),
    )

    response = await plans.get_task_status("task-1")

    assert response.status == "READY"
    assert response.plan_id == "plan-123"
    assert response.mode == "agent_cli"
    assert response.current_step == "shopping-list"
    assert response.steps[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_task_status_maps_failure_error(monkeypatch):
    monkeypatch.setattr(
        plans,
        "AsyncResult",
        lambda task_id, app=None: _FakeAsyncResult(
            "FAILURE",
            result=RuntimeError("boom"),
            info={"mode": "agent_cli", "current_step": "generate"},
        ),
    )

    response = await plans.get_task_status("task-1")

    assert response.status == "FAILED"
    assert response.error == "boom"
    assert response.mode == "agent_cli"


@pytest.mark.asyncio
@pytest.mark.parametrize("requested_mode", ["agentic", "agent_cli", "llm_direct"])
async def test_generate_plan_enqueues_legacy_wire_mode_and_persists_agentic(
    monkeypatch, requested_mode
):
    """Mixed rollout: old workers understand agent_cli; new API state stays agentic."""
    send_task = Mock(return_value=SimpleNamespace(id="task-123"))
    create_run = AsyncMock()
    monkeypatch.setattr(plans.celery_app, "send_task", send_task)
    monkeypatch.setattr(plans, "create_generation_run", create_run)
    user_id = uuid.uuid4()

    response = await plans.generate_plan(
        plans.GeneratePlanRequest(user_id=user_id, days=7, mode=requested_mode),
        db=AsyncMock(),
    )

    assert response.task_id == "task-123"
    send_task.assert_called_once_with(
        plans.GENERATION_TASK_NAME,
        args=[str(user_id), 7, "agent_cli"],
    )
    assert create_run.await_args.kwargs["mode"] == "agentic"
    assert create_run.await_args.kwargs["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_generate_plan_rejects_unknown_mode_before_publish(monkeypatch):
    send_task = Mock()
    monkeypatch.setattr(plans.celery_app, "send_task", send_task)
    with pytest.raises(ValidationError):
        plans.GeneratePlanRequest(user_id=uuid.uuid4(), mode="unknown")
    send_task.assert_not_awaited()
