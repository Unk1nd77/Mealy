import type { MealyCore } from "../controller/useMealyCommands";
import { formatActivity, formatGoal } from "../formatters";
import { useText } from "../text";
import type { ActivityLevel, Gender, Goal } from "../types";

export type OnboardingCore = Pick<
  MealyCore,
  "authMode" | "onboardingForm" | "onboardingStep" | "updateOnboarding"
>;

export function StepBody({ core }: { core: OnboardingCore }) {
  if (core.onboardingStep === 1) return <AccountStep core={core} />;
  if (core.authMode !== "register") return null;
  if (core.onboardingStep === 2) return <BodyStep core={core} />;
  if (core.onboardingStep === 3) return <GoalStep core={core} />;
  if (core.onboardingStep === 4) return <RestrictionsStep core={core} />;
  return null;
}

function AccountStep({ core }: { core: OnboardingCore }) {
  const { t } = useText();

  return (
    <>
      <Copy
        eyebrow={t("onboarding.account")}
        title={
          core.authMode === "login"
            ? t("onboarding.savedProfile")
            : t("onboarding.basics")
        }
      />
      <TextField
        core={core}
        field="email"
        label={t("onboarding.email")}
        type="email"
        placeholder={t("onboarding.emailPlaceholder")}
      />
      <TextField
        core={core}
        field="password"
        label={t("onboarding.password")}
        type="password"
        placeholder={t("onboarding.passwordPlaceholder")}
      />
    </>
  );
}

function BodyStep({ core }: { core: OnboardingCore }) {
  const { t } = useText();

  return (
    <>
      <Copy
        eyebrow={t("onboarding.bodyMetrics")}
        title={t("onboarding.cleanInputs")}
      />
      <div className="field-grid">
        <TextField
          core={core}
          field="age"
          label={t("onboarding.age")}
          type="number"
        />
        <TextField
          core={core}
          field="weight_kg"
          label={t("onboarding.weight")}
          type="number"
        />
        <TextField
          core={core}
          field="height_cm"
          label={t("onboarding.height")}
          type="number"
        />
        <label className="field">
          <span>{t("onboarding.gender")}</span>
          <select
            value={core.onboardingForm.gender}
            onChange={(event) =>
              core.updateOnboarding("gender", event.target.value as Gender)
            }
          >
            <option value="female">{t("onboarding.genderFemale")}</option>
            <option value="male">{t("onboarding.genderMale")}</option>
          </select>
        </label>
      </div>
    </>
  );
}

function GoalStep({ core }: { core: OnboardingCore }) {
  const { t } = useText();

  return (
    <>
      <Copy
        eyebrow={t("onboarding.goalRhythm")}
        title={t("onboarding.weekTone")}
      />
      <label className="field">
        <span>{t("onboarding.activity")}</span>
        <select
          value={core.onboardingForm.activity_level}
          onChange={(event) =>
            core.updateOnboarding(
              "activity_level",
              event.target.value as ActivityLevel,
            )
          }
        >
          <option value="sedentary">{t("onboarding.lowActivity")}</option>
          <option value="light">{t("onboarding.lightActivity")}</option>
          <option value="moderate">{t("onboarding.moderateActivity")}</option>
          <option value="active">{t("onboarding.highActivity")}</option>
          <option value="very_active">{t("onboarding.veryActive")}</option>
        </select>
      </label>
      <label className="field">
        <span>{t("onboarding.goal")}</span>
        <select
          value={core.onboardingForm.goal}
          onChange={(event) =>
            core.updateOnboarding("goal", event.target.value as Goal)
          }
        >
          <option value="lose">{t("onboarding.fatLoss")}</option>
          <option value="maintain">{t("onboarding.maintain")}</option>
          <option value="gain">{t("onboarding.gainMuscle")}</option>
        </select>
      </label>
    </>
  );
}

function RestrictionsStep({ core }: { core: OnboardingCore }) {
  const { t } = useText();

  return (
    <>
      <Copy
        eyebrow={t("onboarding.restrictionsReview")}
        title={t("onboarding.guardrails")}
      />
      <TextArea
        core={core}
        field="allergies"
        label={t("onboarding.allergies")}
        placeholder={t("onboarding.allergiesPlaceholder")}
      />
      <TextArea
        core={core}
        field="preferences"
        label={t("onboarding.preferences")}
        placeholder={t("onboarding.preferencesPlaceholder")}
      />
      <TextArea
        core={core}
        field="disliked_ingredients"
        label={t("onboarding.disliked")}
        placeholder={t("onboarding.dislikedPlaceholder")}
      />
      <TextArea
        core={core}
        field="diseases"
        label={t("onboarding.conditions")}
        placeholder={t("onboarding.conditionsPlaceholder")}
      />
      <div className="review-card">
        <div>
          <strong>{formatGoal(core.onboardingForm.goal)}</strong>
          <span>
            {formatActivity(core.onboardingForm.activity_level)}
          </span>
        </div>
        <div>
          <strong>
            {core.onboardingForm.weight_kg} kg / {core.onboardingForm.height_cm}{" "}
            cm
          </strong>
          <span>
            {core.onboardingForm.gender === "female"
              ? t("onboarding.genderFemale")
              : t("onboarding.genderMale")}
          </span>
        </div>
      </div>
    </>
  );
}

function Copy({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div className="section-copy">
      <span className="section-copy__eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
    </div>
  );
}

function TextField({
  core,
  field,
  label,
  placeholder,
  type,
}: {
  core: OnboardingCore;
  field: "email" | "password" | "age" | "weight_kg" | "height_cm";
  label: string;
  placeholder?: string;
  type: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={core.onboardingForm[field]}
        onChange={(event) => core.updateOnboarding(field, event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function TextArea({
  core,
  field,
  label,
  placeholder,
}: {
  core: OnboardingCore;
  field: "preferences" | "allergies" | "disliked_ingredients" | "diseases";
  label: string;
  placeholder: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        value={core.onboardingForm[field]}
        onChange={(event) => core.updateOnboarding(field, event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}
