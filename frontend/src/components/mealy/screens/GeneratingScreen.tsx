import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { useI18n } from "../i18n";
import { CheckIcon, SparkIcon } from "../ui/icons";
import { ObservabilityPanel } from "../ui/planWidgets";

type GeneratingCore = Pick<
  MealyCore,
  | "generationError"
  | "generationStatus"
  | "observability"
  | "observabilityLoading"
  | "resetToScreen"
  | "user"
>;
type GeneratingCommands = Pick<MealyCommands, "regenerateWeek">;

export function GeneratingScreen({
  commands,
  core,
}: {
  commands: GeneratingCommands;
  core: GeneratingCore;
}) {
  const { t } = useI18n();

  const statusText =
    core.generationStatus === "READY"
      ? t("generating.statusReady")
      : core.generationStatus === "FAILED"
        ? t("generating.statusFailed")
        : core.generationStatus === "GENERATING"
          ? t("generating.statusGenerating")
          : t("generating.statusPending");

  const stages = [
    {
      label: t("generating.stage1"),
      active: core.generationStatus !== "PENDING" || !!core.user,
    },
    {
      label: t("generating.stage2"),
      active:
        core.generationStatus === "GENERATING" ||
        core.generationStatus === "READY",
    },
    {
      label: t("generating.stage3"),
      active: core.generationStatus === "READY",
    },
  ];

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
        <span className="section-copy__eyebrow">{t("generating.eyebrow")}</span>
        <h1>{t("generating.title")}</h1>
        <p>{statusText}</p>
      </div>
      <div className="progress-stack">
        {stages.map((stage) => (
          <div
            key={stage.label}
            className={`progress-step ${stage.active ? "is-active" : ""}`}
          >
            <span className="progress-step__icon">
              {stage.active ? (
                <CheckIcon className="icon" />
              ) : (
                <span className="progress-step__dot" />
              )}
            </span>
            <div>
              <strong>{stage.label}</strong>
              <p>
                {stage.active
                  ? t("generating.stageActive")
                  : t("generating.stageWaiting")}
              </p>
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
          <strong>{t("generating.errorTitle")}</strong>
          <p>{core.generationError}</p>
          <button
            type="button"
            className="button button--primary"
            onClick={commands.regenerateWeek}
          >
            {t("generating.tryAgain")}
          </button>
        </div>
      ) : (
        <div className="form-actions form-actions--centered">
          <button
            type="button"
            className="secondary-cta secondary-cta--quiet"
            onClick={() => core.resetToScreen({ name: "home" })}
          >
            {t("generating.cancel")}
          </button>
        </div>
      )}
    </section>
  );
}
