import type { OnboardingForm } from "./types"

export const APP_NAME = "Mealy"
export const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? "http://localhost:8000"
export const USE_DEMO_PIPELINE = import.meta.env.PUBLIC_USE_DEMO_PIPELINE === "true"
export const DEV_SKIP_ONBOARDING = import.meta.env.PUBLIC_DEV_SKIP_ONBOARDING === "true"
export const DEV_AUTO_GENERATE_PLAN = import.meta.env.PUBLIC_DEV_AUTO_GENERATE_PLAN === "true"
export const DEV_USE_MOCK_DATA =
  import.meta.env.DEV && import.meta.env.PUBLIC_DEV_USE_MOCK_DATA === "true"
export const DEV_EMAIL = import.meta.env.PUBLIC_DEV_EMAIL ?? "demo@example.com"
export const DEV_PASSWORD = import.meta.env.PUBLIC_DEV_PASSWORD ?? "demo123456"
export const STORAGE_KEY = "mealy/mobile-session/v1"
export const LEGACY_STORAGE_KEYS = ["nutri-agent/mobile-session/v2"]
export const MOCK_PLAN_ID = "mock-week-plan"
export const MOCK_USER_ID = "mock-user"
export const PLAN_DAYS = 7
export const REGISTER_STEPS = 4

export const emptyOnboardingForm: OnboardingForm = {
  email: "",
  password: "",
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

export function buildDevUserBody(): OnboardingForm {
  return {
    email: DEV_EMAIL,
    password: DEV_PASSWORD,
    age: "29",
    weight_kg: "72",
    height_cm: "176",
    gender: "male",
    activity_level: "moderate",
    goal: "maintain",
    allergies: "nuts",
    preferences: "high protein, simple dinners, fish",
    disliked_ingredients: "liver",
    diseases: "",
  }
}
