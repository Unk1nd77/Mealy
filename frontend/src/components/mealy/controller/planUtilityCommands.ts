import { APP_NAME } from "../config"
import { isMockPlanId } from "../mockPlan"
import { buildPlanSummaryText, formatShoppingItems } from "../planText"
import { copyText } from "./commandUtils"
import type { MealyCore } from "./useMealyCommands"

export function createPlanUtilityCommands(core: MealyCore) {
  async function getShoppingItems() {
    if (core.shoppingList?.length) return core.shoppingList
    if (!core.planRecord?.id) throw new Error("No active plan is available.")
    core.patch({ shoppingLoading: true })
    try {
      const items = await core.client.shoppingList(core.planRecord.id)
      core.patch({ shoppingList: items })
      return items
    } finally {
      core.patch({ shoppingLoading: false })
    }
  }

  async function copyPlanSummary() {
    try {
      await copyText(
        core,
        buildPlanSummaryText({ ...core, plan: core.planRecord }),
        "Plan summary copied for Notes, chat, or files.",
      )
    } catch (error) {
      core.patch({
        errorNotice: error instanceof Error ? error.message : "Could not copy plan summary.",
      })
    }
  }

  async function sharePlanSummary() {
    const text = buildPlanSummaryText({ ...core, plan: core.planRecord })
    if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
      try {
        await navigator.share({ title: `${APP_NAME} meal plan`, text })
        core.patch({ globalNotice: "Shared through the system share sheet." })
        return
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return
        core.patch({
          errorNotice: error instanceof Error ? error.message : "Could not open share sheet.",
        })
        return
      }
    }
    await copyText(core, text, "Share sheet is unavailable. Plan summary copied instead.")
  }

  async function copyShoppingItems() {
    try {
      const items = await getShoppingItems()
      if (!items.length) return core.patch({ errorNotice: "Shopping list is empty for this plan." })
      await copyText(core, formatShoppingItems(items), "Shopping list copied.")
      core.patch({ shoppingCopied: true })
    } catch (error) {
      core.patch({
        errorNotice: error instanceof Error ? error.message : "Could not copy shopping list.",
      })
    }
  }

  async function downloadProtectedFile(path: string, filename: string) {
    if (typeof window === "undefined") return
    const blob = await core.client.download(path)
    const objectUrl = window.URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = objectUrl
    link.download = filename
    link.click()
    window.URL.revokeObjectURL(objectUrl)
  }

  function openCalendarExport() {
    if (!core.planRecord?.id) return
    if (isMockPlanId(core.planRecord.id)) {
      core.patch({ globalNotice: "Mock mode: calendar export needs a backend plan." })
      return
    }
    void downloadProtectedFile(
      `/api/plans/${core.planRecord.id}/calendar.ics`,
      `mealy-plan-${core.planRecord.id}.ics`,
    )
      .then(() => core.patch({ globalNotice: "Calendar file downloaded." }))
      .catch((error: Error) => core.patch({ errorNotice: error.message }))
  }

  function openShoppingListPdf() {
    if (!core.planRecord?.id) return
    if (isMockPlanId(core.planRecord.id)) {
      core.patch({ globalNotice: "Mock mode: PDF export needs a backend plan." })
      return
    }
    void downloadProtectedFile(
      `/api/plans/${core.planRecord.id}/shopping-list.pdf`,
      `mealy-shopping-list-${core.planRecord.id}.pdf`,
    )
      .then(() => core.patch({ globalNotice: "Shopping PDF downloaded." }))
      .catch((error: Error) => core.patch({ errorNotice: error.message }))
  }

  return {
    copyPlanSummary,
    copyShoppingItems,
    openCalendarExport,
    openShoppingListPdf,
    sharePlanSummary,
  }
}
