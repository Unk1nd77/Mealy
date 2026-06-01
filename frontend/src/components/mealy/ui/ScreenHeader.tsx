import { ArrowLeftIcon } from "./icons"
import { APP_NAME } from "../config"
import { useText } from "../text"

export function ScreenHeader({
  title,
  subtitle,
  onBack,
}: {
  title: string
  subtitle?: string
  onBack?: () => void
}) {
  const { t } = useText()

  return (
    <header className="screen-header">
      <div className="screen-header__lead">
        {onBack ? (
          <button
            type="button"
            className="icon-button"
            onClick={onBack}
            aria-label={t("screen.back")}
          >
            <ArrowLeftIcon className="icon" />
          </button>
        ) : null}
        <div>
          <div className="screen-header__brand">{APP_NAME}</div>
          <h2>{title}</h2>
        </div>
      </div>
      {subtitle ? <p className="screen-header__copy">{subtitle}</p> : null}
    </header>
  )
}
