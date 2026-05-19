import "../../../styles/mealy/02-form-actions.css"
import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/02-forms-mobile.css"
import "../../../styles/mealy/02-forms.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/07-actions.css"
import "../../../styles/mealy/11-webapp-states-mobile.css"
import "../../../styles/mealy/11-webapp-states.css"

import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { useI18n } from "../i18n"
import type { Gender } from "../types"
import { ScreenHeader } from "../ui/ScreenHeader"

type ProfileCore = Pick<
  MealyCore,
  "isSavingProfile" | "profileDraft" | "signOut" | "updateProfileDraft"
>
type ProfileCommands = Pick<MealyCommands, "saveProfile">

export function ProfileScreen({
  commands,
  core,
}: {
  commands: ProfileCommands
  core: ProfileCore
}) {
  const { t } = useI18n()

  return (
    <section className="screen-card screen-card--profile">
      <ScreenHeader title={t("profile.title")} subtitle={t("profile.subtitle")} />
      <div className="profile-blocks">
        <section className="profile-block profile-block--body">
          <div className="profile-block__heading">
            <h3>{t("profile.body")}</h3>
            <span>{t("profile.coreMeasurements")}</span>
          </div>
          <div className="field-grid profile-metric-grid">
            <ProfileInput core={core} field="age" label={t("onboarding.age")} />
            <ProfileInput core={core} field="weight_kg" label={t("onboarding.weight")} />
            <ProfileInput core={core} field="height_cm" label={t("onboarding.height")} />
            <label className="field">
              <span>{t("onboarding.gender")}</span>
              <select
                value={core.profileDraft.gender}
                onChange={(event) =>
                  core.updateProfileDraft("gender", event.target.value as Gender)
                }
              >
                <option value="female">{t("onboarding.genderFemale")}</option>
                <option value="male">{t("onboarding.genderMale")}</option>
              </select>
            </label>
          </div>
        </section>
        <section className="profile-block profile-block--restrictions">
          <div className="profile-block__heading">
            <h3>{t("profile.restrictions")}</h3>
            <span>{t("profile.foodGuardrails")}</span>
          </div>
          <div className="profile-restriction-grid">
            <ProfileText core={core} field="allergies" label={t("onboarding.allergies")} />
            <ProfileText
              core={core}
              field="disliked_ingredients"
              label={t("onboarding.disliked")}
            />
            <ProfileText core={core} field="diseases" label={t("onboarding.conditions")} />
          </div>
        </section>
      </div>
      <div className="profile-actions">
        <button
          type="button"
          className="button button--primary"
          onClick={commands.saveProfile}
          disabled={core.isSavingProfile}
        >
          {core.isSavingProfile ? t("profile.saving") : t("profile.save")}
        </button>
        <button type="button" className="secondary-cta secondary-cta--quiet" onClick={core.signOut}>
          {t("profile.signOut")}
        </button>
      </div>
    </section>
  )
}

function ProfileInput({
  core,
  field,
  label,
}: {
  core: ProfileCore
  field: "age" | "weight_kg" | "height_cm"
  label: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type="number"
        value={core.profileDraft[field]}
        onChange={(event) => core.updateProfileDraft(field, event.target.value)}
      />
    </label>
  )
}

function ProfileText({
  core,
  field,
  label,
}: {
  core: ProfileCore
  field: "allergies" | "disliked_ingredients" | "diseases"
  label: string
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        value={core.profileDraft[field]}
        onChange={(event) => core.updateProfileDraft(field, event.target.value)}
      />
    </label>
  )
}
