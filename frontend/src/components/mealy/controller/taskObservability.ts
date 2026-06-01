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
      ? `Текущий этап: ${task.current_step.replaceAll("_", " ")}`
      : "Генерация выполняется.",
    steps: task.steps.map(normalizeObservabilityStep),
    day_checks: [],
    has_persisted_trace: false,
  }
}
