import type { OnboardingForm } from "./types"

export const APP_NAME = "Mealy"
export const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? "http://localhost:8000"
export const STORAGE_KEY = "mealy/mobile-session/v1"
export const LEGACY_STORAGE_KEYS = ["nutri-agent/mobile-session/v2"]
export const PLAN_DAYS = 7
export const REGISTER_STEPS = 4

export const emptyOnboardingForm: OnboardingForm = {
  email: "",
  password: "",
  age: "",
  weight_kg: "",
  height_cm: "",
  gender: "female",
  activity_level: "moderate",
  goal: "maintain",
  allergies: "",
  preferences: "",
  disliked_ingredients: "",
  diseases: "",
}
