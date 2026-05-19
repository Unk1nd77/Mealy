import { useReducer, useRef } from "react"

import { DEV_AUTO_GENERATE_PLAN, buildDevUserBody } from "../config"
import { createMealyClient, formToUserPayload } from "../client"
import { normalizeObservabilityStep, normalizeTaskStatus } from "../api"
import { getTodayIndex } from "../formatters"
import { isMockPlanId } from "../mockPlan"
import { clearStoredSession, patchStoredSession, writeStoredSession } from "../session"
import type { MealContext, OnboardingForm, ProfileDraft, RecipeDetail, WeeklyPlan } from "../types"
import { sleep } from "../utils"
import { registerOrCreateUser } from "./authFlow"
import { deriveMealyState } from "./derivedState"
import { mealyReducer, initialMealyState } from "./state"
import { observabilityFromTask } from "./taskObservability"
import { useScreenStack } from "../useScreenStack"

export function useMealyController() {
  const aliveRef = useRef(true)
  const [state, patch] = useReducer(mealyReducer, initialMealyState)
  const nav = useScreenStack({ name: "onboarding" })
  const client = createMealyClient(state.accessToken, () => {
    setAccessToken(null)
    notice("Session expired. Sign in again to access protected data.")
  })
  const clientFor = (token?: string | null) =>
    createMealyClient(token === undefined ? state.accessToken : token)
  const derived = deriveMealyState(state)
  const { planData } = derived
  function notice(globalNotice = "", errorNotice = "") {
    patch({ globalNotice, errorNotice })
  }
  function setAccessToken(accessToken: string | null) {
    patch({ accessToken })
    patchStoredSession({ accessToken: accessToken ?? undefined })
  }
  function updateOnboarding<K extends keyof OnboardingForm>(key: K, value: OnboardingForm[K]) {
    patch({ onboardingForm: { ...state.onboardingForm, [key]: value } })
  }
  function updateProfileDraft<K extends keyof ProfileDraft>(key: K, value: ProfileDraft[K]) {
    patch({ profileDraft: { ...state.profileDraft, [key]: value } })
  }
  function getMealContext(recipeId: string): MealContext | null {
    for (const day of planData?.days ?? []) {
      const meal = day.meals.find((item) => item.recipe_id === recipeId)
      if (meal) return { day, meal }
    }
    return null
  }
  function recipeById(recipeId: string): RecipeDetail | null {
    return state.recipesMap[recipeId] ?? null
  }
  async function loadRecipeDetails(
    nextPlanData: WeeklyPlan | null = planData,
    token?: string | null,
  ) {
    if (!nextPlanData) return patch({ recipesMap: {} })
    const ids = Array.from(
      new Set(nextPlanData.days.flatMap((day) => day.meals.map((meal) => meal.recipe_id))),
    )
    if (!ids.length) return patch({ recipesMap: {} })
    const recipes = await clientFor(token)
      .batchRecipes(ids)
      .catch(() => [])
    const recipesMap = Object.fromEntries(recipes.map((recipe) => [recipe.id, recipe]))
    if (aliveRef.current) patch({ recipesMap })
  }
  async function loadMockPlan(globalNotice = "Dev mock week loaded.") {
    if (!import.meta.env.DEV) {
      patch({ errorNotice: "Mock data is only available in development mode." })
      return
    }
    const { buildDevMockState } = await import("../devMockData")
    const mock = buildDevMockState()
    if (!aliveRef.current) return
    patch({
      accessToken: null,
      errorNotice: "",
      generationError: "",
      generationStatus: "READY",
      globalNotice,
      observability: mock.observability,
      observabilityLoading: false,
      planRecord: mock.planRecord,
      recipesMap: mock.recipesMap,
      selectedDayNumber: getTodayIndex(mock.planRecord),
      shoppingList: mock.shoppingList,
      shoppingLoading: false,
      taskId: null,
      user: mock.user,
    })
    clearStoredSession()
    nav.resetToScreen({ name: "home" })
  }
  async function hydratePlan(userId: string, planId: string, token?: string | null) {
    const scopedClient = clientFor(token)
    const [user, planRecord] = await Promise.all([
      scopedClient.getUser(userId),
      scopedClient.getPlan(planId),
    ])
    if (!aliveRef.current) return
    patch({ user, planRecord, shoppingList: null })
    patchStoredSession({ userId, planId, taskId: undefined })
    await loadRecipeDetails(planRecord.plan_data, token)
  }
  async function refreshPlan(planId: string, token?: string | null) {
    if (isMockPlanId(planId)) {
      await loadMockPlan("Mock week refreshed.")
      return state.planRecord
    }
    const planRecord = await clientFor(token).getPlan(planId)
    if (!aliveRef.current) return planRecord
    patch({ planRecord, shoppingList: null })
    await loadRecipeDetails(planRecord.plan_data, token)
    return planRecord
  }
  async function monitorTask(taskId: string, userId: string, token?: string | null) {
    const scopedClient = clientFor(token)
    patch({ taskId, generationError: "", generationStatus: "PENDING", observability: null })
    for (let attempt = 0; attempt < 120; attempt += 1) {
      if (attempt) await sleep(attempt < 10 ? 1800 : attempt < 30 ? 3200 : 5200)
      const task = await scopedClient.getTask(taskId).catch((error: Error) => {
        patch({ generationError: error.message, errorNotice: error.message })
        return null
      })
      if (!task || !aliveRef.current) return
      const status = normalizeTaskStatus(task.status)
      patch({
        generationStatus: status,
        observability: observabilityFromTask(task, state.observability),
      })
      if (status === "FAILED")
        return patch({
          generationError: task.error || "Plan generation failed.",
          errorNotice: task.error || "Plan generation failed.",
        })
      if (status === "READY" && task.plan_id) {
        await hydratePlan(userId, task.plan_id, token)
        patchStoredSession({ userId, planId: task.plan_id, taskId: undefined })
        patch({ taskId: null, shoppingList: null, globalNotice: "Your fresh week is ready." })
        nav.resetToScreen({ name: "home" })
        return
      }
    }
    patch({ generationError: "Generation took too long. Please try again." })
  }
  async function bootstrapDevSession() {
    const devForm = buildDevUserBody()
    const { user, token } = await registerOrCreateUser({
      client,
      fallbackPassword: devForm.password,
      payload: formToUserPayload(devForm),
    })
    if (!aliveRef.current) return
    patch({
      accessToken: token,
      user,
      onboardingForm: devForm,
      globalNotice: "Dev mode: registration skipped. Use the app manually from Today.",
    })
    writeStoredSession({ userId: user.id, accessToken: token ?? undefined })
    if (!DEV_AUTO_GENERATE_PLAN) return nav.resetToScreen({ name: "home" })
    nav.resetToScreen({ name: "generating" })
    const { task_id } = await clientFor(token).generatePlan(user.id)
    writeStoredSession({ userId: user.id, taskId: task_id, accessToken: token ?? undefined })
    await monitorTask(task_id, user.id, token)
  }
  async function loadObservability(planId: string, token?: string | null) {
    if (isMockPlanId(planId)) {
      if (!import.meta.env.DEV) return
      const { buildDevMockState } = await import("../devMockData")
      if (aliveRef.current) {
        patch({ observability: buildDevMockState().observability, observabilityLoading: false })
      }
      return
    }
    patch({ observabilityLoading: true })
    try {
      const payload = await clientFor(token).observability(planId)
      if (aliveRef.current)
        patch({
          observability: { ...payload, steps: payload.steps.map(normalizeObservabilityStep) },
        })
    } catch (error) {
      if (aliveRef.current)
        patch({
          observability: null,
          errorNotice: error instanceof Error ? error.message : "Could not load generation trace.",
        })
    } finally {
      if (aliveRef.current) patch({ observabilityLoading: false })
    }
  }
  async function loadShoppingList(planId: string, token?: string | null) {
    if (isMockPlanId(planId)) {
      if (!import.meta.env.DEV) return
      const { buildDevMockState } = await import("../devMockData")
      if (aliveRef.current) {
        patch({ shoppingList: buildDevMockState().shoppingList, shoppingLoading: false })
      }
      return
    }
    patch({ shoppingLoading: true })
    try {
      const shoppingList = await clientFor(token).shoppingList(planId)
      if (aliveRef.current) patch({ shoppingList })
    } catch (error) {
      if (aliveRef.current)
        patch({
          errorNotice: error instanceof Error ? error.message : "Could not load shopping list.",
        })
    } finally {
      if (aliveRef.current) patch({ shoppingLoading: false })
    }
  }
  function clearAppState() {
    clearStoredSession()
    patch({ ...initialMealyState, isBooting: false })
    nav.resetToScreen({ name: "onboarding" })
  }
  function signOut() {
    clearAppState()
    notice("Signed out.")
  }

  return {
    ...state,
    ...derived,
    ...nav,
    aliveRef,
    patch,
    updateOnboarding,
    updateProfileDraft,
    clearAppState,
    signOut,
    recipeById,
    getMealContext,
    bootstrapDevSession,
    hydratePlan,
    refreshPlan,
    monitorTask,
    loadShoppingList,
    loadObservability,
    loadMockPlan,
    setAccessToken,
    notice,
    client,
    clientFor,
  }
}
