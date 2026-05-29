import { normalizeObservabilityStep } from "../api"
import type { ObservabilityResponse, TaskResponse } from "../types"

export function observabilityFromTask(
  task: TaskResponse,
  fallback: ObservabilityResponse | null,
): ObservabilityResponse | null {
  if (!task.steps?.length) return fallback
  return {
    source: "live_task",
    summary: task.current_step
      ? `Current step: ${task.current_step.replaceAll("_", " ")}`
      : "Generation is in progress.",
    steps: task.steps.map(normalizeObservabilityStep),
    day_checks: [],
    has_persisted_trace: false,
  }
}
