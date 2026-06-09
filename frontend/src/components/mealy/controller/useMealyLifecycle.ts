import { useEffect } from "react"

import { emptyOnboardingForm } from "../config"
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
    if (!core.isBooting) return
    const timeout = window.setTimeout(() => {
      if (!core.aliveRef.current) return
      clearStoredSession()
      core.patch({
        accessToken: null,
        isBooting: false,
        planRecord: null,
        recipesMap: {},
        shoppingList: null,
        taskId: null,
        user: null,
      })
      core.resetToScreen({ name: "onboarding" })
    }, 2500)
    return () => window.clearTimeout(timeout)
  }, [core.aliveRef, core.isBooting])

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
      const stored = readStoredSession()
      if (!stored?.userId && !stored?.planId && !stored?.taskId) {
        core.patch({ isBooting: false })
        return
      }

      try {
        core.patch({ accessToken: stored.accessToken ?? null, isBooting: false })
        if (stored.userId && stored.taskId) {
          core.patch({ taskId: stored.taskId })
          core.resetToScreen({ name: "generating" })
          void core.monitorTask(stored.taskId, stored.userId, stored.accessToken ?? null)
          return
        }
        if (stored.userId && stored.planId) {
          core.resetToScreen({ name: "home" })
          await core.hydratePlan(stored.userId, stored.planId, stored.accessToken ?? null)
          return
        }
        if (stored.userId) {
          core.resetToScreen({ name: "home" })
          const user = await core.clientFor(stored.accessToken ?? null).getUser(stored.userId)
          core.patch({ user })
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
        core.resetToScreen({ name: "onboarding" })
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
}
