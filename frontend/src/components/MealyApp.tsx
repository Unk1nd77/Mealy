import { lazy, Suspense, useEffect } from "react"

import { BottomNav, shouldShowBottomNav } from "./mealy/BottomNav"
import { useMealyCommands } from "./mealy/controller/useMealyCommands"
import { useMealyController } from "./mealy/controller/useMealyController"
import { useMealyLifecycle } from "./mealy/controller/useMealyLifecycle"
import { I18nProvider, LanguageToggle, useI18n } from "./mealy/i18n"
import { BootScreen } from "./mealy/screens/BootScreen"

const GeneratingScreen = lazy(() =>
  import("./mealy/screens/GeneratingScreen").then((module) => ({
    default: module.GeneratingScreen,
  })),
)
const HomeScreen = lazy(() =>
  import("./mealy/screens/HomeScreen").then((module) => ({ default: module.HomeScreen })),
)
const IntegrationsScreen = lazy(() =>
  import("./mealy/screens/IntegrationsScreen").then((module) => ({
    default: module.IntegrationsScreen,
  })),
)
const OnboardingScreen = lazy(() =>
  import("./mealy/screens/OnboardingScreen").then((module) => ({
    default: module.OnboardingScreen,
  })),
)
const ProfileScreen = lazy(() =>
  import("./mealy/screens/ProfileScreen").then((module) => ({ default: module.ProfileScreen })),
)
const RecipeScreen = lazy(() =>
  import("./mealy/screens/RecipeScreen").then((module) => ({ default: module.RecipeScreen })),
)
const ShoppingScreen = lazy(() =>
  import("./mealy/screens/ShoppingScreen").then((module) => ({ default: module.ShoppingScreen })),
)
const WeeklyScreen = lazy(() =>
  import("./mealy/screens/WeeklyScreen").then((module) => ({ default: module.WeeklyScreen })),
)

export default function MealyApp() {
  return (
    <I18nProvider>
      <MealyAppContent />
    </I18nProvider>
  )
}

function MealyAppContent() {
  const core = useMealyController()
  const commands = useMealyCommands(core)
  const { t } = useI18n()
  const notice = formatNotice(core.errorNotice, core.globalNotice, t)
  useMealyLifecycle(core)

  useEffect(() => {
    if (!core.globalNotice && !core.errorNotice) return
    const timeout = window.setTimeout(
      () => core.patch({ globalNotice: "", errorNotice: "" }),
      core.errorNotice ? 4800 : 3200,
    )
    return () => window.clearTimeout(timeout)
  }, [core.errorNotice, core.globalNotice, core.patch])

  return (
    <main className="app-shell">
      <div className={`phone-shell ${shouldShowBottomNav(core) ? "has-bottom-nav" : ""}`}>
        {notice && (
          <div className={`floating-notice ${core.errorNotice ? "is-error" : ""}`}>
            <strong>{notice.title}</strong>
            <span>{notice.message}</span>
          </div>
        )}
        <Suspense fallback={<BootScreen />}>
          <CurrentScreen commands={commands} core={core} />
        </Suspense>
        <BottomNav core={core} />
        <LanguageToggle />
      </div>
    </main>
  )
}

function formatNotice(
  errorNotice: string,
  globalNotice: string,
  t: ReturnType<typeof useI18n>["t"],
) {
  if (errorNotice) {
    if (isNetworkLoadError(errorNotice)) {
      return {
        title: t("error.loadTitle"),
        message: t("error.loadHint"),
      }
    }
    return {
      title: t("app.attention"),
      message: errorNotice,
    }
  }
  if (!globalNotice) return null
  return {
    title: t("app.updated"),
    message: globalNotice,
  }
}

function isNetworkLoadError(message: string) {
  return /load failed|failed to fetch|networkerror|network error/i.test(message)
}

function CurrentScreen({
  commands,
  core,
}: {
  commands: ReturnType<typeof useMealyCommands>
  core: ReturnType<typeof useMealyController>
}) {
  if (core.isBooting) return <BootScreen />
  switch (core.currentScreen.name) {
    case "generating":
      return <GeneratingScreen commands={commands} core={core} />
    case "home":
      return <HomeScreen commands={commands} core={core} />
    case "weekly":
      return <WeeklyScreen commands={commands} core={core} />
    case "shopping":
      return <ShoppingScreen commands={commands} core={core} />
    case "integrations":
      return <IntegrationsScreen commands={commands} core={core} />
    case "profile":
      return <ProfileScreen commands={commands} core={core} />
    case "recipe":
      return <RecipeScreen commands={commands} core={core} recipeId={core.currentScreen.recipeId} />
    default:
      return <OnboardingScreen commands={commands} core={core} />
  }
}
