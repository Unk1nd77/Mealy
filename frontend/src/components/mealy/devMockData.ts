import { MOCK_PLAN_ID, MOCK_USER_ID, PLAN_DAYS } from "./config"
import { dayIndexes, mealSeeds, type MockMealSeed } from "./devMockSeeds"
import type {
  DayPlan,
  ObservabilityResponse,
  PlanResponse,
  RecipeDetail,
  ShoppingItem,
  UserResponse,
  WeeklyPlan,
} from "./types"

export function buildDevMockState() {
  const startDate = new Date()
  const endDate = new Date(startDate)
  endDate.setDate(startDate.getDate() + PLAN_DAYS - 1)

  const user: UserResponse = {
    id: MOCK_USER_ID,
    email: "demo@mealy.local",
    age: 30,
    weight_kg: 75,
    height_cm: 175,
    gender: "female",
    activity_level: "moderate",
    goal: "maintain",
    allergies: ["nuts"],
    preferences: ["high protein", "simple dinners", "fish"],
    disliked_ingredients: ["liver"],
    diseases: [],
    target_calories: 2200,
    meal_schedule: [
      { type: "breakfast", time: "08:00", calories_pct: 0.22 },
      { type: "lunch", time: "12:45", calories_pct: 0.33 },
      { type: "snack", time: "16:15", calories_pct: 0.13 },
      { type: "dinner", time: "19:30", calories_pct: 0.32 },
    ],
  }

  const recipesMap = buildRecipesMap()
  const days = dayIndexes
    .slice(0, PLAN_DAYS)
    .map((indexes, dayIndex) => buildDay(dayIndex + 1, indexes.map(mealSeedAt)))
  const planData: WeeklyPlan = {
    user_profile: { goal: user.goal },
    total_days: PLAN_DAYS,
    daily_target_calories: user.target_calories ?? 2200,
    days,
  }
  const planRecord: PlanResponse = {
    id: MOCK_PLAN_ID,
    user_id: MOCK_USER_ID,
    status: "ready",
    start_date: toDateInput(startDate),
    end_date: toDateInput(endDate),
    plan_data: planData,
  }

  return {
    observability: buildMockObservability(days, planData.daily_target_calories),
    planRecord,
    recipesMap,
    shoppingList: buildShoppingList(days),
    user,
  }
}

function buildDay(dayNumber: number, meals: MockMealSeed[]): DayPlan {
  return {
    day_number: dayNumber,
    total_calories: sum(meals, "calories"),
    total_protein: sum(meals, "protein"),
    total_fat: sum(meals, "fat"),
    total_carbs: sum(meals, "carbs"),
    meals: meals.map((meal) => ({
      ...meal,
      ingredients_summary: meal.ingredients.slice(0, 3),
    })),
  }
}

function mealSeedAt(index: number): MockMealSeed {
  const seed = mealSeeds[index]
  if (!seed) {
    throw new Error(`Missing mock meal seed at index ${index}`)
  }
  return seed
}

function buildRecipesMap(): Record<string, RecipeDetail> {
  return Object.fromEntries(
    mealSeeds.map((meal) => [
      meal.recipe_id,
      {
        id: meal.recipe_id,
        title: meal.title,
        description: meal.description,
        ingredients: meal.ingredients,
        calories: meal.calories,
        protein: meal.protein,
        fat: meal.fat,
        carbs: meal.carbs,
        tags: meal.tags,
        meal_type: meal.type,
        ingredients_short: meal.ingredients.map((item) => item.name).join(", "),
        prep_time_min: meal.type === "snack" ? 8 : 25,
        category: meal.type,
      },
    ]),
  )
}

function buildShoppingList(days: DayPlan[]): ShoppingItem[] {
  const grouped = new Map<string, ShoppingItem>()
  for (const meal of days.flatMap((day) => day.meals)) {
    for (const ingredient of meal.ingredients_summary) {
      const key = `${ingredient.name}-${ingredient.unit}`
      const current = grouped.get(key)
      grouped.set(key, {
        name: ingredient.name,
        unit: ingredient.unit,
        amount: Math.round(((current?.amount ?? 0) + ingredient.amount) * 100) / 100,
      })
    }
  }
  return Array.from(grouped.values()).sort((left, right) => left.name.localeCompare(right.name))
}

function buildMockObservability(days: DayPlan[], targetCalories: number): ObservabilityResponse {
  return {
    source: "dev_mock",
    summary: "Mock generation trace for frontend inspection.",
    steps: [
      { key: "profile", status: "completed", message: "Demo profile loaded." },
      { key: "catalog", status: "completed", message: "Recipe catalog matched to constraints." },
      { key: "planner", status: "completed", message: "Seven-day rhythm assembled." },
      { key: "validation", status: "completed", message: "Calories and macros checked." },
    ],
    day_checks: days.map((day) => {
      const deviationKcal = Math.round(day.total_calories - targetCalories)
      const deviationPct = Math.round((deviationKcal / targetCalories) * 1000) / 10
      return {
        day_number: day.day_number,
        total_calories: day.total_calories,
        target_calories: targetCalories,
        deviation_kcal: deviationKcal,
        deviation_pct: deviationPct,
        within_target: Math.abs(deviationPct) <= 12,
      }
    }),
    has_persisted_trace: false,
  }
}

function sum(meals: MockMealSeed[], key: "calories" | "protein" | "fat" | "carbs") {
  return meals.reduce((total, meal) => total + meal[key], 0)
}

function toDateInput(date: Date) {
  return date.toISOString().slice(0, 10)
}
