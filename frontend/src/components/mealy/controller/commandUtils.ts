import type { MealyCore } from "./useMealyCommands"

export async function copyText(core: MealyCore, text: string, message: string) {
  if (typeof navigator === "undefined" || !navigator.clipboard) {
    core.patch({ errorNotice: "Clipboard is unavailable in this browser." })
    return false
  }
  await navigator.clipboard.writeText(text)
  core.patch({ globalNotice: message })
  return true
}
