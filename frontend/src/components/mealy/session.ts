import { LEGACY_STORAGE_KEYS, STORAGE_KEY } from "./config"
import type { StoredSession } from "./types"

export function readStoredSession(): StoredSession | null {
  if (typeof window === "undefined") {
    return null
  }

  try {
    for (const key of [STORAGE_KEY, ...LEGACY_STORAGE_KEYS]) {
      const raw = window.localStorage.getItem(key)
      if (raw) {
        return JSON.parse(raw) as StoredSession
      }
    }
    return null
  } catch {
    return null
  }
}

export function writeStoredSession(next: StoredSession): void {
  if (typeof window === "undefined") {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  for (const key of LEGACY_STORAGE_KEYS) {
    window.localStorage.removeItem(key)
  }
}

export function patchStoredSession(patch: Partial<StoredSession>): void {
  const current = readStoredSession() ?? {}
  const next = { ...current, ...patch }

  if (!next.userId && !next.planId && !next.taskId) {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(STORAGE_KEY)
    }
    return
  }

  writeStoredSession(next)
}

export function clearStoredSession(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY)
    for (const key of LEGACY_STORAGE_KEYS) {
      window.localStorage.removeItem(key)
    }
  }
}
