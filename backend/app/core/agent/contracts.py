"""Shared day result and agent failures; no runtime or persistence dependencies."""

from dataclasses import dataclass, field
from typing import Literal

from app.core.agent.schemas import DayPlanFull

GenerationMode = Literal["agentic"]
GENERATION_TASK_NAME = "generate_meal_plan"


class AgentLimitError(Exception):
    """Raised when AGENT_MAX_LLM_CALLS is exhausted before a valid final response."""

    def __init__(self, llm_calls: int, pending_tool_call_ids: list[str]):
        self.llm_calls = llm_calls
        self.pending_tool_call_ids = pending_tool_call_ids
        super().__init__(
            f"Agent LLM call limit reached after {llm_calls} calls. "
            f"Pending tool calls: {pending_tool_call_ids}"
        )


class AgentConfigurationError(Exception):
    """Raised when the agentic runtime cannot register its required tools."""


@dataclass
class GeneratedDayResult:
    plan: DayPlanFull
    quality_status: str
    attempts_used: int
    validation_error: str | None = None
    tool_call_trace: list[dict] = field(default_factory=list)
    # Each entry: {"tool": str, "llm_call": int, "args_summary": str}
    collected_recipes: list[dict] = field(default_factory=list, repr=False)
