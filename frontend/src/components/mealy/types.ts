import type { ReactNode } from "react"

export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active"
export type Goal = "lose" | "maintain" | "gain"
export type Gender = "male" | "female"

export type MealSlot = {
  type: string
  time: string
  calories_pct: number
}

export type Ingredient = {
  name: string
  amount: number
  unit: string
}

export type MealItem = {
  type: string
  time?: string
  recipe_id: string
  title: string
  calories: number
  protein: number
  fat: number
  carbs: number
  ingredients_summary: Ingredient[]
}

export type DayPlan = {
  day_number: number
  total_calories: number
  total_protein: number
  total_fat: number
  total_carbs: number
  meals: MealItem[]
}

export type WeeklyPlan = {
  user_profile?: {
    goal?: Goal
  }
  total_days: number
  daily_target_calories: number
  days: DayPlan[]
}

export type RecipeDetail = {
  id: string
  title: string
  description?: string
  ingredients: Ingredient[]
  calories: number
  protein: number
  fat: number
  carbs: number
  tags?: string[]
  meal_type?: string
  allergens?: string[]
  ingredients_short?: string
  prep_time_min?: number
  category?: string
}

export type ShoppingItem = {
  name: string
  amount: number
  unit: string
}

export type UserResponse = {
  id: string
  email: string
  age: number
  weight_kg: number
  height_cm: number
  gender: Gender
  activity_level: ActivityLevel
  goal: Goal
  allergies: string[]
  preferences: string[]
  disliked_ingredients: string[]
  diseases: string[]
  target_calories: number | null
  meal_schedule: MealSlot[] | null
}

export type PlanResponse = {
  id: string
  user_id: string
  status: string
  start_date: string | null
  end_date: string | null
  plan_data: WeeklyPlan | null
}

export type TaskResponse = {
  status: string
  plan_id?: string
  error?: string
  current_step?: string
  steps?: ObservabilityStep[]
}

export type AuthResponse = {
  access_token?: string
  token_type?: string
  user_id?: string
  user?: UserResponse
}

export type ObservabilityStep = {
  key: string
  status: string
  message: string
}

export type ObservabilityDayCheck = {
  day_number: number
  total_calories: number
  target_calories: number
  deviation_kcal: number
  deviation_pct: number
  within_target: boolean
}

export type ObservabilityResponse = {
  source: string
  summary: string
  steps: ObservabilityStep[]
  day_checks: ObservabilityDayCheck[]
  has_persisted_trace: boolean
}

export type MealContext = {
  day: DayPlan
  meal: MealItem
}

export type StoredSession = {
  userId?: string | undefined
  planId?: string | undefined
  taskId?: string | undefined
  accessToken?: string | undefined
}

export type Screen =
  | { name: "onboarding" }
  | { name: "generating" }
  | { name: "home" }
  | { name: "weekly" }
  | { name: "shopping" }
  | { name: "integrations" }
  | { name: "profile" }
  | { name: "recipe"; recipeId: string }

export type OnboardingForm = {
  email: string
  password: string
  age: string
  weight_kg: string
  height_cm: string
  gender: Gender
  activity_level: ActivityLevel
  goal: Goal
  allergies: string
  preferences: string
  disliked_ingredients: string
  diseases: string
}

export type ProfileDraft = {
  age: string
  weight_kg: string
  height_cm: string
  gender: Gender
  activity_level: ActivityLevel
  goal: Goal
  allergies: string
  preferences: string
  disliked_ingredients: string
  diseases: string
}

export type AuthMode = "register" | "login"

export type QuickAction = {
  label: string
  description: string
  icon: ReactNode
  onClick: () => void
}

export type BottomNavItem = {
  screen: Exclude<Screen, { name: "onboarding" } | { name: "generating" } | { name: "recipe" }>
  label: string
  requiresPlan?: boolean
}
