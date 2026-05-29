import type { TranslationKey } from "./i18n"
import type { ObservabilityResponse, ObservabilityStep } from "./types"

type Translate = (key: TranslationKey, values?: Record<string, string | number>) => string

const STEP_KEY_MAP: Record<string, TranslationKey> = {
  profile: "observability.step.profile",
  catalog: "observability.step.catalog",
  planner: "observability.step.planner",
  validation: "observability.step.validation",
  context: "observability.step.context",
  generate: "observability.step.generate",
  validate: "observability.step.validate",
  reflection: "observability.step.reflection",
  source: "observability.step.source",
  "shopping-list": "observability.step.shopping",
}

const MESSAGE_KEY_MAP: Record<string, TranslationKey> = {
  profile: "observability.message.profile",
  catalog: "observability.message.catalog",
  planner: "observability.message.planner",
  validation: "observability.message.validation",
  context: "observability.message.context",
  generate: "observability.message.generate",
  validate: "observability.message.validate",
  reflection: "observability.message.reflection",
}

const STATUS_KEY_MAP: Record<string, TranslationKey> = {
  completed: "observability.status.completed",
  pending: "observability.status.pending",
  running: "observability.status.running",
  generating: "observability.status.generating",
  failed: "observability.status.failed",
  limited: "observability.status.limited",
}

function normalizeStepKey(key: string) {
  return key.trim().toLowerCase().replaceAll("-", "_")
}

export function formatObservabilityStepKey(key: string, t: Translate) {
  const normalized = normalizeStepKey(key)
  const mapped =
    STEP_KEY_MAP[key] ??
    STEP_KEY_MAP[normalized.replaceAll("_", "-")] ??
    STEP_KEY_MAP[normalized]
  if (mapped) return t(mapped)
  return key.replaceAll("_", " ")
}

export function formatObservabilityStatus(status: string, t: Translate) {
  const normalized = normalizeStepKey(status)
  const mapped = STATUS_KEY_MAP[status] ?? STATUS_KEY_MAP[normalized]
  if (mapped) return t(mapped)
  return status.replaceAll("_", " ")
}

export function formatObservabilityStepMessage(step: ObservabilityStep, t: Translate) {
  const normalized = normalizeStepKey(step.key)
  const mapped =
    MESSAGE_KEY_MAP[step.key] ??
    MESSAGE_KEY_MAP[normalized.replaceAll("_", "-")] ??
    MESSAGE_KEY_MAP[normalized]
  if (mapped) return t(mapped)
  return step.message
}

export function formatObservabilitySummary(
  observability: ObservabilityResponse,
  mode: "generation" | "result",
  t: Translate,
) {
  if (mode === "generation") {
    const active = observability.steps.find(
      (step) => step.status !== "completed" && step.status !== "failed",
    )
    if (active) {
      return t("observability.summary.active", {
        step: formatObservabilityStepKey(active.key, t),
      })
    }
    return t("observability.summary.progress")
  }

  const allCompleted =
    observability.steps.length > 0 &&
    observability.steps.every((step) => step.status === "completed")

  if (allCompleted || observability.source === "derived_plan") {
    return t("observability.summary.ready")
  }

  return t("observability.summary.review")
}
