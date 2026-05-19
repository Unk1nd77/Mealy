import "../../../styles/mealy/02-form-actions.css"
import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/07-actions.css"
import "../../../styles/mealy/11-webapp-states-mobile.css"
import "../../../styles/mealy/11-webapp-states.css"

import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { useI18n } from "../i18n"
import { ScreenHeader } from "../ui/ScreenHeader"
import { SparkIcon } from "../ui/icons"

type EmptyHomeCore = Pick<MealyCore, "clearAppState" | "user">
type EmptyHomeCommands = Pick<MealyCommands, "regenerateWeek">

export function EmptyHomeScreen({
  commands,
  core,
}: {
  commands: EmptyHomeCommands
  core: EmptyHomeCore
}) {
  const { t } = useI18n()
  const action = core.user ? commands.regenerateWeek : core.clearAppState
  const label = core.user ? t("empty.generate") : t("empty.start")

  return (
    <section className="screen-card screen-card--empty-home">
      <ScreenHeader title={t("nav.today")} subtitle={t("empty.todaySubtitle")} />
      <div className="empty-home-panel">
        <div className="empty-home-panel__main">
          <span className="empty-state__icon">
            <SparkIcon className="icon icon--large" />
          </span>
          <div>
            <p className="section-heading__eyebrow">{t("empty.noWeek")}</p>
            <h2>{t("empty.title")}</h2>
            <p>{t("empty.copy")}</p>
          </div>
        </div>
        <div className="empty-home-preview">
          <div>
            <strong>{t("nav.today")}</strong>
            <span>{t("empty.previewToday")}</span>
          </div>
          <div>
            <strong>{t("nav.week")}</strong>
            <span>{t("empty.previewWeek")}</span>
          </div>
          <div>
            <strong>{t("empty.actions")}</strong>
            <span>{t("empty.previewActions")}</span>
          </div>
          <button type="button" className="button button--primary" onClick={action}>
            {label}
          </button>
        </div>
      </div>
    </section>
  )
}
