import type { ActivityLevel, Goal, PlanResponse } from "./types"

export function formatGoal(goal: Goal | string | undefined): string {
  switch (goal) {
    case "lose":
      return "Fat loss"
    case "gain":
      return "Muscle gain"
    default:
      return "Balance"
  }
}

export function formatActivity(activity: ActivityLevel | string | undefined): string {
  switch (activity) {
    case "sedentary":
      return "Low activity"
    case "light":
      return "Light activity"
    case "active":
      return "High activity"
    case "very_active":
      return "Very active"
    default:
      return "Moderate activity"
  }
}

export function formatMealType(type: string): string {
  switch (type) {
    case "breakfast":
      return "Breakfast"
    case "lunch":
      return "Lunch"
    case "dinner":
      return "Dinner"
    case "snack":
      return "Snack"
    case "second_snack":
      return "Late snack"
    default:
      return type.replaceAll("_", " ")
  }
}
export function mealVisualClass(type: string): string {
  switch (type) {
    case "breakfast":
      return "meal-visual breakfast"
    case "lunch":
      return "meal-visual lunch"
    case "dinner":
      return "meal-visual dinner"
    case "snack":
      return "meal-visual snack"
    default:
      return "meal-visual"
  }
}

export const MACRO_SERIES = [
  { key: "protein", label: "Protein", short: "P", color: "#30d158" },
  { key: "fat", label: "Fat", short: "F", color: "#ff9f0a" },
  { key: "carbs", label: "Carbs", short: "C", color: "#ff2d55" },
] as const

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

export function getTodayIndex(plan: PlanResponse | null): number {
  const totalDays = plan?.plan_data?.days.length ?? 1
  if (!plan?.start_date) {
    return 1
  }

  const start = new Date(`${plan.start_date}T00:00:00`)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.floor((today.getTime() - start.getTime()) / 86_400_000)
  return clamp(diff + 1, 1, totalDays)
}

export function formatShortDate(offset = 0): string {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date)
}

export function formatPlanDayLabel(plan: PlanResponse | null, dayNumber: number): string {
  if (!plan?.start_date) {
    return formatShortDate(dayNumber - 1)
  }

  const date = new Date(`${plan.start_date}T00:00:00`)
  date.setDate(date.getDate() + dayNumber - 1)
  return new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date)
}
