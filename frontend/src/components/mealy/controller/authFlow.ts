import { extractBearerToken, readError } from "../api"
import { createMealyClient, type UserPayload } from "../client"
import type { AuthResponse } from "../types"

type MealyClient = ReturnType<typeof createMealyClient>

export async function resolveAuthUser(auth: AuthResponse, token: string | null) {
  if (auth.user) return auth.user
  if (!auth.user_id) {
    throw new Error("Auth endpoint did not return a usable user payload.")
  }
  return createMealyClient(token).getUser(auth.user_id)
}

export async function registerOrCreateUser({
  client,
  fallbackPassword,
  payload,
}: {
  client: MealyClient
  fallbackPassword?: string
  payload: UserPayload
}) {
  const response = await client.registerRaw(payload)
  if (response.ok) {
    const auth = (await response.json()) as AuthResponse
    const token = extractBearerToken(auth)
    return { user: await resolveAuthUser(auth, token), token }
  }

  if (response.status === 409 && payload.email && fallbackPassword) {
    const auth = await client.login(payload.email, fallbackPassword)
    const token = extractBearerToken(auth)
    return { user: await resolveAuthUser(auth, token), token }
  }

  if (response.status === 404 || response.status === 405) {
    return { user: await client.createUser(payload), token: null }
  }

  throw new Error(await readError(response))
}
