import type { FormEvent } from "react";

import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { useText } from "../text";
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
  const { t } = useText();

  function handleSubmit(event: FormEvent) {
    if (core.authMode === "login") {
      void commands.loginExistingUser(event);
      return;
    }
    if (core.onboardingStep < core.onboardingSteps) {
      event.preventDefault();
      commands.goToNextStep();
      return;
    }
    void commands.createUserAndGenerate(event);
  }

  return (
    <section className="screen-card screen-card--onboarding">
      <header className="onboarding-topbar">
        <div className="onboarding-brand">
          <strong>Mealy</strong>
          <span>{t("onboarding.brandSub")}</span>
        </div>
        <div className="mode-switch" role="tablist" aria-label="Сценарий аккаунта">
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
          onSubmit={handleSubmit}
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
                key="continue-step"
                type="button"
                className="button button--primary"
                onClick={(event) => {
                  event.preventDefault();
                  commands.goToNextStep();
                }}
              >
                {t("onboarding.continue")}
              </button>
            ) : (
              <button
                key="submit-onboarding"
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
