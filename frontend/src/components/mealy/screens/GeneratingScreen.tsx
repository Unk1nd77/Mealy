import "../../../styles/mealy/02-form-actions.css"
import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/04-generation-run.css"
import "../../../styles/mealy/04-generation.css"

import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { CheckIcon, SparkIcon } from "../ui/icons"
import { ObservabilityPanel } from "../ui/planWidgets"

type GeneratingCore = Pick<
  MealyCore,
  "generationError" | "generationStatus" | "observability" | "observabilityLoading" | "user"
>
type GeneratingCommands = Pick<MealyCommands, "regenerateWeek">

export function GeneratingScreen({
  commands,
  core,
}: {
  commands: GeneratingCommands
  core: GeneratingCore
}) {
  const statusText =
    core.generationStatus === "READY"
      ? "Your week is almost on screen."
      : core.generationStatus === "FAILED"
        ? core.generationError || "Generation failed."
        : core.generationStatus === "GENERATING"
          ? "Matching recipes, balancing calories, building the final week."
          : "Creating your nutrition profile and queueing the plan."
  const stages = [
    { label: "Profile parsed", active: core.generationStatus !== "PENDING" || !!core.user },
    {
      label: "Recipe pool matched",
      active: core.generationStatus === "GENERATING" || core.generationStatus === "READY",
    },
    { label: "Week balanced", active: core.generationStatus === "READY" },
  ]

  return (
    <section className="screen-card screen-card--generation">
      <div className="generation-orbit">
        <span className="generation-orbit__ring" />
        <span className="generation-orbit__ring generation-orbit__ring--accent" />
        <span className="generation-orbit__core">
          <SparkIcon className="icon icon--large" />
        </span>
      </div>
      <div className="section-copy section-copy--centered">
        <span className="section-copy__eyebrow">AI planning in progress</span>
        <h1>Designing your week</h1>
        <p>{statusText}</p>
      </div>
      <div className="progress-stack">
        {stages.map((stage) => (
          <div key={stage.label} className={`progress-step ${stage.active ? "is-active" : ""}`}>
            <span className="progress-step__icon">
              {stage.active ? (
                <CheckIcon className="icon" />
              ) : (
                <span className="progress-step__dot" />
              )}
            </span>
            <div>
              <strong>{stage.label}</strong>
              <p>{stage.active ? "Moving forward" : "Waiting for this stage"}</p>
            </div>
          </div>
        ))}
      </div>
      <ObservabilityPanel
        mode="generation"
        observability={core.observability}
        observabilityLoading={core.observabilityLoading}
      />
      {core.generationError ? (
        <div className="alert alert--error">
          <strong>Couldn&apos;t finish this run.</strong>
          <p>{core.generationError}</p>
          <button
            type="button"
            className="button button--primary"
            onClick={commands.regenerateWeek}
          >
            Try again
          </button>
        </div>
      ) : null}
    </section>
  )
}
