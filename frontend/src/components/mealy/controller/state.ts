import { emptyOnboardingForm } from "../config"
import type {
  AuthMode,
  ObservabilityResponse,
  OnboardingForm,
  PlanResponse,
  ProfileDraft,
  RecipeDetail,
  ShoppingItem,
  UserResponse,
} from "../types"

export type MealAction = "swap" | "cancel" | null

export type MealyState = {
  accessToken: string | null
  authMode: AuthMode
  errorNotice: string
  generationError: string
  generationStatus: string
  globalNotice: string
  isBooting: boolean
  isSavingProfile: boolean
  isWorking: boolean
  mealActionLoading: MealAction
  observability: ObservabilityResponse | null
  observabilityLoading: boolean
  onboardingForm: OnboardingForm
  onboardingStep: number
  planRecord: PlanResponse | null
  profileDraft: ProfileDraft
  recipesMap: Record<string, RecipeDetail>
  selectedDayNumber: number
  shoppingList: ShoppingItem[] | null
  shoppingLoading: boolean
  taskId: string | null
  user: UserResponse | null
}

export const initialProfileDraft: ProfileDraft = {
  age: "30",
  weight_kg: "75",
  height_cm: "175",
  gender: "female",
  activity_level: "moderate",
  goal: "maintain",
  allergies: "",
  preferences: "",
  disliked_ingredients: "",
  diseases: "",
}

export const initialMealyState: MealyState = {
  accessToken: null,
  authMode: "register",
  errorNotice: "",
  generationError: "",
  generationStatus: "PENDING",
  globalNotice: "",
  isBooting: true,
  isSavingProfile: false,
  isWorking: false,
  mealActionLoading: null,
  observability: null,
  observabilityLoading: false,
  onboardingForm: emptyOnboardingForm,
  onboardingStep: 1,
  planRecord: null,
  profileDraft: initialProfileDraft,
  recipesMap: {},
  selectedDayNumber: 1,
  shoppingList: null,
  shoppingLoading: false,
  taskId: null,
  user: null,
}

export type MealyPatch = Partial<MealyState>

export function mealyReducer(state: MealyState, patch: MealyPatch): MealyState {
  return { ...state, ...patch }
}
