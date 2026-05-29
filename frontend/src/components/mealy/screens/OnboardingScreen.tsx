import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { useI18n } from "../i18n";
import { StepBody, type OnboardingCore } from "./onboardingSteps";

type OnboardingCommands = Pick<
  MealyCommands,
  | "createUserAndGenerate"
  | "goToNextStep"
  | "goToPreviousStep"
  | "loginExistingUser"
>;
type OnboardingShellCore = OnboardingCore &
  Pick<MealyCore, "isWorking" | "onboardingSteps" | "patch">;

export function OnboardingScreen({
  commands,
  core,
}: {
  commands: OnboardingCommands;
  core: OnboardingShellCore;
}) {
  const canGoBack = core.authMode === "register" && core.onboardingStep > 1;
  const { t } = useI18n();

  return (
    <section className="screen-card screen-card--onboarding">
      <header className="onboarding-topbar">
        <div className="onboarding-brand">
          <strong>Mealy</strong>
          <span>{t("onboarding.brandSub")}</span>
        </div>
        <div className="mode-switch" role="tablist" aria-label="Account flow">
          {(["register", "login"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              className={`mode-chip ${core.authMode === mode ? "is-active" : ""}`}
              onClick={() => core.patch({ authMode: mode, onboardingStep: 1 })}
            >
              {mode === "register"
                ? t("onboarding.mode.create")
                : t("onboarding.mode.signIn")}
            </button>
          ))}
        </div>
      </header>
      <div className="onboarding-workspace">
        <aside className="onboarding-rail">
          <div>
            <span className="section-copy__eyebrow">
              {t("onboarding.setup")}
            </span>
            <h1>{t("onboarding.title")}</h1>
            <p>{t("onboarding.copy")}</p>
          </div>
        </aside>
        <form
          onSubmit={
            core.authMode === "login"
              ? commands.loginExistingUser
              : commands.createUserAndGenerate
          }
          className="form-shell onboarding-panel"
        >
          <div className="step-track">
            {Array.from(
              { length: core.authMode === "login" ? 1 : core.onboardingSteps },
              (_, index) => index + 1,
            ).map((step) => (
              <span
                key={step}
                className={`step-dot ${step <= core.onboardingStep ? "is-active" : ""}`}
              />
            ))}
          </div>
          <StepBody core={core} />
          <div
            className={`sticky-actions ${canGoBack ? "" : "sticky-actions--single"}`}
          >
            {canGoBack ? (
              <button
                type="button"
                className="button button--ghost"
                onClick={commands.goToPreviousStep}
              >
                {t("onboarding.back")}
              </button>
            ) : null}
            {core.authMode === "register" &&
            core.onboardingStep < core.onboardingSteps ? (
              <button
                type="button"
                className="button button--primary"
                onClick={commands.goToNextStep}
              >
                {t("onboarding.continue")}
              </button>
            ) : (
              <button
                type="submit"
                className="button button--primary"
                disabled={core.isWorking}
              >
                {core.isWorking
                  ? t("onboarding.starting")
                  : core.authMode === "login"
                    ? t("onboarding.mode.signIn")
                    : t("onboarding.generate")}
              </button>
            )}
          </div>
        </form>
      </div>
    </section>
  );
}
