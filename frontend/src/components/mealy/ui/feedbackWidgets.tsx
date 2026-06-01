import { useText } from "../text"
import {
  formatObservabilityStatus,
  formatObservabilityStepKey,
  formatObservabilityStepMessage,
  formatObservabilitySummary,
} from "../observabilityFormatters"
import type { ObservabilityResponse } from "../types"
import { TimeIcon } from "./icons"

export function ObservabilityPanel({
  mode,
  observability,
  observabilityLoading,
}: {
  mode: "generation" | "result"
  observability: ObservabilityResponse | null
  observabilityLoading: boolean
}) {
  const { t } = useText()

  if (!observability && !observabilityLoading) return null
  const title =
    mode === "generation"
      ? t("observability.title.generation")
      : t("observability.title.result")
  const eyebrow =
    mode === "generation"
      ? t("observability.eyebrow.generation")
      : t("observability.eyebrow.result")

  return (
    <section className="section-block observability-panel">
      <div className="section-heading">
        <div>
          <span className="section-heading__eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
      </div>
      {observabilityLoading ? (
        <div className="loading-card">
          <TimeIcon className="icon icon--brand" />
          <span>{t("observability.loading")}</span>
        </div>
      ) : null}
      {observability ? (
        <>
          <div className="observability-summary">
            <strong>{formatObservabilitySummary(observability, mode, t)}</strong>
            <span>{t("observability.summaryHint")}</span>
          </div>
          <div className="observability-steps">
            {observability.steps.map((step) => (
              <div key={`${step.key}-${step.status}`} className="observability-step">
                <div className={`observability-step__status is-${step.status}`}>
                  {formatObservabilityStatus(step.status, t)}
                </div>
                <div>
                  <strong>{formatObservabilityStepKey(step.key, t)}</strong>
                  <p>{formatObservabilityStepMessage(step, t)}</p>
                </div>
              </div>
            ))}
          </div>
          {mode === "result" && observability.day_checks.length ? (
            <div className="observability-days">
              {observability.day_checks.map((dayCheck) => (
                <div key={dayCheck.day_number} className="observability-day">
                  <strong>{t("observability.day", { count: dayCheck.day_number })}</strong>
                  <span>
                    {Math.round(dayCheck.total_calories)} /{" "}
                    {Math.round(dayCheck.target_calories)} {t("common.kcal")}
                  </span>
                  <span>
                    {t("observability.deviation", {
                      kcal: Math.round(dayCheck.deviation_kcal),
                      pct: dayCheck.deviation_pct,
                    })}
                  </span>
                  <span className={dayCheck.within_target ? "is-good" : "is-warning"}>
                    {dayCheck.within_target
                      ? t("observability.withinTarget")
                      : t("observability.needsReview")}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
