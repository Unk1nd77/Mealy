import { API_BASE, PLAN_DAYS } from "./config"
import { readError } from "./api"
import type {
  AuthResponse,
  DayPlan,
  ObservabilityResponse,
  OnboardingForm,
  PlanResponse,
  RecipeDetail,
  ShoppingItem,
  TaskResponse,
  UserResponse,
} from "./types"
import { splitList } from "./utils"

export type UserPayload = {
  email?: string
  password?: string
  age: number
  weight_kg: number
  height_cm: number
  gender: string
  activity_level: string
  goal: string
  allergies: string[]
  preferences: string[]
  disliked_ingredients: string[]
  diseases: string[]
}

export function formToUserPayload(form: OnboardingForm): UserPayload {
  return {
    email: form.email.trim(),
    password: form.password,
    age: Number(form.age),
    weight_kg: Number(form.weight_kg),
    height_cm: Number(form.height_cm),
    gender: form.gender,
    activity_level: form.activity_level,
    goal: form.goal,
    allergies: splitList(form.allergies),
    preferences: splitList(form.preferences),
    disliked_ingredients: splitList(form.disliked_ingredients),
    diseases: splitList(form.diseases),
  }
}

export function profileToUserPayload(form: Omit<OnboardingForm, "email" | "password">) {
  return {
    age: Number(form.age),
    weight_kg: Number(form.weight_kg),
    height_cm: Number(form.height_cm),
    gender: form.gender,
    activity_level: form.activity_level,
    goal: form.goal,
    allergies: splitList(form.allergies),
    preferences: splitList(form.preferences),
    disliked_ingredients: splitList(form.disliked_ingredients),
    diseases: splitList(form.diseases),
  }
}

export function createMealyClient(accessToken: string | null, onExpired?: () => void) {
  function headers(init?: HeadersInit, hasBody = false) {
    const next = new Headers(init)
    if (hasBody && !next.has("Content-Type")) {
      next.set("Content-Type", "application/json")
    }
    if (accessToken && !next.has("Authorization")) {
      next.set("Authorization", `Bearer ${accessToken}`)
    }
    return next
  }

  async function request(input: string, init?: RequestInit) {
    const response = await fetch(input, {
      ...init,
      headers: headers(init?.headers, Boolean(init?.body)),
    })
    if (response.status === 401 && accessToken) {
      onExpired?.()
    }
    return response
  }

  async function json<T>(input: string, init?: RequestInit): Promise<T> {
    const response = await request(input, init)
    if (!response.ok) {
      throw new Error(await readError(response))
    }
    return (await response.json()) as T
  }

  return {
    request,
    async authMe() {
      return json<UserResponse>(`${API_BASE}/api/auth/me`)
    },
    async batchRecipes(recipeIds: string[]) {
      return json<RecipeDetail[]>(`${API_BASE}/api/recipes/batch`, {
        method: "POST",
        body: JSON.stringify({ recipe_ids: recipeIds }),
      })
    },
    async cancelMeal(planId: string, day: number, mealType: string) {
      return json(`${API_BASE}/api/plans/${planId}/cancel-meal`, {
        method: "POST",
        body: JSON.stringify({ day_number: day, meal_type: mealType }),
      })
    },
    async createUser(payload: UserPayload) {
      return json<UserResponse>(`${API_BASE}/api/users`, {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    async download(path: string) {
      const response = await request(`${API_BASE}${path}`)
      if (!response.ok) {
        throw new Error(await readError(response))
      }
      return response.blob()
    },
    async generatePlan(userId: string) {
      return json<{ task_id: string }>(`${API_BASE}/api/generate-plan`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId, days: PLAN_DAYS, mode: "agentic" }),
      })
    },
    async getPlan(planId: string) {
      return json<PlanResponse>(`${API_BASE}/api/plans/${planId}`)
    },
    async getTask(taskId: string) {
      return json<TaskResponse>(`${API_BASE}/api/tasks/${encodeURIComponent(taskId)}`)
    },
    async getUser(userId: string) {
      return json<UserResponse>(`${API_BASE}/api/users/${userId}`)
    },
    async login(email: string, password: string) {
      return json<AuthResponse>(`${API_BASE}/api/auth/login`, {
        method: "POST",
        body: JSON.stringify({ email: email.trim(), password }),
      })
    },
    async observability(planId: string) {
      return json<ObservabilityResponse>(`${API_BASE}/api/plans/${planId}/observability`)
    },
    async register(payload: UserPayload) {
      return json<AuthResponse>(`${API_BASE}/api/auth/register`, {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    async registerRaw(payload: UserPayload) {
      return request(`${API_BASE}/api/auth/register`, {
        method: "POST",
        body: JSON.stringify(payload),
      })
    },
    async shoppingList(planId: string) {
      const payload = await json<{ items: ShoppingItem[] }>(
        `${API_BASE}/api/plans/${planId}/shopping-list`,
      )
      return payload.items
    },
    async swapMeal(planId: string, day: number, mealType: string) {
      return json<{ day: DayPlan }>(`${API_BASE}/api/plans/${planId}/swap-meal`, {
        method: "POST",
        body: JSON.stringify({ day_number: day, meal_type: mealType }),
      })
    },
    async updateMe(payload: Omit<UserPayload, "email" | "password">) {
      return json<UserResponse>(`${API_BASE}/api/auth/me`, {
        method: "PUT",
        body: JSON.stringify(payload),
      })
    },
    async updateUser(userId: string, payload: Omit<UserPayload, "email" | "password">) {
      return json<UserResponse>(`${API_BASE}/api/users/${userId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      })
    },
  }
}
