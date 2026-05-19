import type { ObservabilityResponse, QuickAction } from "../types"
import { ChevronRightIcon, TimeIcon } from "./icons"

export function QuickActions({ actions }: { actions: QuickAction[] }) {
  return (
    <div className="quick-actions">
      {actions.map((action) => (
        <button key={action.label} type="button" className="action-card" onClick={action.onClick}>
          <span className="action-card__icon">{action.icon}</span>
          <div>
            <strong>{action.label}</strong>
            <p>{action.description}</p>
          </div>
          <ChevronRightIcon className="icon action-card__chevron" />
        </button>
      ))}
    </div>
  )
}

export function ObservabilityPanel({
  mode,
  observability,
  observabilityLoading,
}: {
  mode: "generation" | "result"
  observability: ObservabilityResponse | null
  observabilityLoading: boolean
}) {
  if (!observability && !observabilityLoading) return null
  const title = mode === "generation" ? "Building your plan" : "Plan check"
  const eyebrow = mode === "generation" ? "Live status" : "Balance review"
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
          <span>Loading generation diagnostics...</span>
        </div>
      ) : null}
      {observability ? (
        <>
          <div className="observability-summary">
            <strong>{observability.summary}</strong>
            <span>Calories, macros, and restrictions are reviewed before the plan is shown.</span>
          </div>
          <div className="observability-steps">
            {observability.steps.map((step) => (
              <div key={`${step.key}-${step.status}`} className="observability-step">
                <div className={`observability-step__status is-${step.status}`}>
                  {step.status.replaceAll("_", " ")}
                </div>
                <div>
                  <strong>{step.key.replaceAll("_", " ")}</strong>
                  <p>{step.message}</p>
                </div>
              </div>
            ))}
          </div>
          {mode === "result" && observability.day_checks.length ? (
            <div className="observability-days">
              {observability.day_checks.map((dayCheck) => (
                <div key={dayCheck.day_number} className="observability-day">
                  <strong>Day {dayCheck.day_number}</strong>
                  <span>
                    {Math.round(dayCheck.total_calories)} / {Math.round(dayCheck.target_calories)}{" "}
                    kcal
                  </span>
                  <span>
                    Deviation {Math.round(dayCheck.deviation_kcal)} kcal ({dayCheck.deviation_pct}%)
                  </span>
                  <span className={dayCheck.within_target ? "is-good" : "is-warning"}>
                    {dayCheck.within_target ? "Within target band" : "Needs review"}
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
