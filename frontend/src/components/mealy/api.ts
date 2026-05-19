import { USE_DEMO_PIPELINE } from "./config"
import type { AuthResponse, ObservabilityStep } from "./types"

export async function readError(response: Response): Promise<string> {
  try {
    const text = await response.text()
    return text || `HTTP ${response.status}`
  } catch {
    return `HTTP ${response.status}`
  }
}
export function generationEndpoint(): string {
  return USE_DEMO_PIPELINE ? "/api/demo/generate-plan" : "/api/generate-plan"
}

export function taskEndpoint(taskId: string): string {
  return USE_DEMO_PIPELINE ? `/api/demo/tasks/${taskId}` : `/api/tasks/${taskId}`
}

export function normalizeTaskStatus(status: string): string {
  if (status === "RUNNING" || status === "STARTED") {
    return "GENERATING"
  }
  return status
}

export function normalizeObservabilityStep(
  step: ObservabilityStep,
  index: number,
): ObservabilityStep {
  return {
    key: step.key?.trim() || `step-${index + 1}`,
    status: step.status?.trim().toLowerCase() || "completed",
    message: step.message?.trim() || "Generation stage completed.",
  }
}

export function extractBearerToken(response: AuthResponse): string | null {
  return response.access_token?.trim() || null
}
