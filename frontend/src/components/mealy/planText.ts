import { APP_NAME } from "./config"
import { formatGoal, formatMealType, formatPlanDayLabel } from "./formatters"
import type { PlanResponse, ShoppingItem, UserResponse, WeeklyPlan } from "./types"

export function formatShoppingItems(items: ShoppingItem[]): string {
  return items.map((item) => `${item.name} - ${item.amount} ${item.unit}`).join("\n")
}

export function buildPlanSummaryText({
  dailyTarget,
  plan,
  planData,
  user,
}: {
  dailyTarget: number
  plan: PlanResponse | null
  planData: WeeklyPlan | null
  user: UserResponse | null
}): string {
  if (!planData?.days.length) {
    return `${APP_NAME} plan is not ready yet.`
  }

  const lines = [
    `${APP_NAME} meal plan`,
    `Daily target: ${Math.round(dailyTarget)} kcal`,
    `Goal: ${formatGoal(planData.user_profile?.goal || user?.goal)}`,
    "",
  ]

  for (const day of planData.days) {
    lines.push(`Day ${day.day_number} - ${formatPlanDayLabel(plan, day.day_number)}`)
    for (const meal of day.meals) {
      lines.push(
        `${meal.time || "Flexible"} ${formatMealType(meal.type)}: ${
          meal.title
        } (${Math.round(meal.calories)} kcal)`,
      )
    }
    lines.push("")
  }

  return lines.join("\n").trim()
}
