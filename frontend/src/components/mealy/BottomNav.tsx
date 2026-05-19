import type { MealyCore } from "./controller/useMealyCommands"
import { useI18n } from "./i18n"
import type { BottomNavItem } from "./types"

type BottomNavCore = Pick<MealyCore, "currentScreen" | "isBooting" | "planData" | "resetToScreen">

export function shouldShowBottomNav(core: Pick<BottomNavCore, "currentScreen" | "isBooting">) {
  return (
    !core.isBooting &&
    core.currentScreen.name !== "onboarding" &&
    core.currentScreen.name !== "generating" &&
    core.currentScreen.name !== "recipe"
  )
}

export function BottomNav({ core }: { core: BottomNavCore }) {
  const { t } = useI18n()
  if (!shouldShowBottomNav(core)) return null
  const items: BottomNavItem[] = [
    { screen: { name: "home" }, label: t("nav.today") },
    {
      screen: { name: "weekly" },
      label: t("nav.week"),
      requiresPlan: true,
    },
    { screen: { name: "profile" }, label: t("nav.profile") },
  ]

  return (
    <nav className="bottom-nav" aria-label={t("nav.primary")}>
      {items.map((item) => {
        const disabled = item.requiresPlan && !core.planData
        const isActive = core.currentScreen.name === item.screen.name
        return (
          <button
            key={item.label}
            type="button"
            className={`bottom-nav__item ${isActive ? "is-active" : ""}`}
            onClick={() => core.resetToScreen(item.screen)}
            disabled={disabled}
            aria-current={isActive ? "page" : undefined}
          >
            <span>{item.label}</span>
          </button>
        )
      })}
    </nav>
  )
}
