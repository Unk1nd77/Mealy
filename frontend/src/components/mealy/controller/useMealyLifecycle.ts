import { useEffect } from "react"

import { DEV_SKIP_ONBOARDING, DEV_USE_MOCK_DATA, emptyOnboardingForm } from "../config"
import { clearStoredSession, readStoredSession } from "../session"
import { joinList } from "../utils"
import type { MealyCore } from "./useMealyCommands"

export function useMealyLifecycle(core: MealyCore) {
  useEffect(() => {
    core.aliveRef.current = true
    return () => {
      core.aliveRef.current = false
    }
  }, [core.aliveRef])

  useEffect(() => {
    if (!core.user) return
    core.patch({
      profileDraft: {
        age: String(core.user.age),
        weight_kg: String(core.user.weight_kg),
        height_cm: String(core.user.height_cm),
        gender: core.user.gender,
        activity_level: core.user.activity_level,
        goal: core.user.goal,
        allergies: joinList(core.user.allergies),
        preferences: joinList(core.user.preferences),
        disliked_ingredients: joinList(core.user.disliked_ingredients),
        diseases: joinList(core.user.diseases),
      },
    })
  }, [core.user])

  useEffect(() => {
    if (core.authMode === "login" && core.onboardingStep !== 1) {
      core.patch({ onboardingStep: 1 })
    }
  }, [core.authMode, core.onboardingStep])

  useEffect(() => {
    core.patch({ selectedDayNumber: core.todayIndex })
  }, [core.todayIndex, core.planRecord?.id])

  useEffect(() => {
    async function restoreSession() {
      if (DEV_USE_MOCK_DATA) {
        clearStoredSession()
        await core.loadMockPlan("Dev mode: mock week loaded.")
        core.patch({ isBooting: false })
        return
      }

      const stored = readStoredSession()
      if (!stored?.userId && !stored?.planId && !stored?.taskId) {
        if (DEV_SKIP_ONBOARDING) {
          await core.bootstrapDevSession().catch((error: Error) => {
            core.patch({ errorNotice: error.message })
            core.resetToScreen({ name: "home" })
          })
        }
        core.patch({ isBooting: false })
        return
      }

      try {
        core.patch({ accessToken: stored.accessToken ?? null })
        if (stored.userId && stored.taskId) {
          core.patch({ taskId: stored.taskId, isBooting: false })
          core.resetToScreen({ name: "generating" })
          void core.monitorTask(stored.taskId, stored.userId, stored.accessToken ?? null)
          return
        }
        if (stored.userId && stored.planId) {
          await core.hydratePlan(stored.userId, stored.planId, stored.accessToken ?? null)
          core.resetToScreen({ name: "home" })
          core.patch({ isBooting: false })
          return
        }
        if (stored.userId) {
          const user = await core.clientFor(stored.accessToken ?? null).getUser(stored.userId)
          core.patch({ user, isBooting: false })
          core.resetToScreen({ name: "home" })
          return
        }
      } catch {
        clearStoredSession()
        core.patch({
          accessToken: null,
          onboardingForm: emptyOnboardingForm,
          planRecord: null,
          recipesMap: {},
          shoppingList: null,
          user: null,
        })
        if (DEV_SKIP_ONBOARDING) {
          await core.bootstrapDevSession().catch((error: Error) => {
            core.patch({ errorNotice: error.message })
            core.resetToScreen({ name: "home" })
          })
        } else {
          core.resetToScreen({ name: "onboarding" })
        }
      }
      core.patch({ isBooting: false })
    }
    void restoreSession()
  }, [])

  useEffect(() => {
    if (
      core.currentScreen.name !== "shopping" ||
      !core.planRecord?.id ||
      core.shoppingList ||
      core.shoppingLoading
    ) {
      return
    }
    void core.loadShoppingList(core.planRecord.id, core.accessToken)
  }, [core.currentScreen.name, core.planRecord?.id, core.shoppingList, core.shoppingLoading])

  useEffect(() => {
    if (!core.planRecord?.id) {
      core.patch({ observability: null, observabilityLoading: false })
      return
    }
    void core.loadObservability(core.planRecord.id, core.accessToken)
  }, [core.planRecord?.id])

  useEffect(() => {
    if (!core.shoppingCopied) return
    const timeout = window.setTimeout(() => core.patch({ shoppingCopied: false }), 1600)
    return () => window.clearTimeout(timeout)
  }, [core.shoppingCopied])
}
