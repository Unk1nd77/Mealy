import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { useText } from "../text";
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
  const { t } = useText();

  const statusText =
    core.generationStatus === "READY"
      ? t("generating.statusReady")
      : core.generationStatus === "FAILED"
        ? t("generating.statusFailed")
        : core.generationStatus === "GENERATING"
          ? t("generating.statusGenerating")
          : t("generating.statusPending");

  return (
    <section className="screen-card screen-card--generation">
      <div className="generation-status-card">
        <span className="generation-status-card__dot" aria-hidden="true" />
        <span className="section-copy__eyebrow">{t("generating.eyebrow")}</span>
        <h1>{t("generating.title")}</h1>
        <p>{statusText}</p>
        <div className="generation-status-card__bar" aria-hidden="true">
          <span />
        </div>
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
