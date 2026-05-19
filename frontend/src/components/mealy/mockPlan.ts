import { MOCK_PLAN_ID } from "./config"

export function isMockPlanId(planId: string | undefined | null) {
  return planId === MOCK_PLAN_ID
}
