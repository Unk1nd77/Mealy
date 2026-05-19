import { REGISTER_STEPS } from "../config"
import { getTodayIndex } from "../formatters"
import type { MealyState } from "./state"

export function deriveMealyState(state: MealyState) {
  const planData = state.planRecord?.plan_data ?? null
  const todayIndex = getTodayIndex(state.planRecord)
  const todayPlan =
    planData?.days.find((day) => day.day_number === todayIndex) ?? planData?.days[0] ?? null
  const dailyTarget = planData?.daily_target_calories ?? state.user?.target_calories ?? 0
  const todayCalories = todayPlan?.total_calories ?? 0
  const todayProgress =
    dailyTarget > 0 ? Math.min(Math.round((todayCalories / dailyTarget) * 100), 100) : 0
  const onboardingSteps = state.authMode === "login" ? 1 : REGISTER_STEPS

  return {
    dailyTarget,
    onboardingSteps,
    planData,
    todayCalories,
    todayIndex,
    todayPlan,
    todayProgress,
  }
}
