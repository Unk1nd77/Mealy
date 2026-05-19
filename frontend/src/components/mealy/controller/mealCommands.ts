import type { MealyCore } from "./useMealyCommands"

export function createMealCommands(core: MealyCore) {
  async function swapCurrentMeal(recipeId: string) {
    if (!core.planRecord?.id) return
    const context = core.getMealContext(recipeId)
    if (!context) return
    core.patch({ mealActionLoading: "swap", errorNotice: "", globalNotice: "" })
    try {
      const payload = await core.client.swapMeal(
        core.planRecord.id,
        context.day.day_number,
        context.meal.type,
      )
      const nextMeal = payload.day.meals.find((meal) => meal.type === context.meal.type)
      await core.refreshPlan(core.planRecord.id)
      if (nextMeal) core.replaceCurrentScreen({ name: "recipe", recipeId: nextMeal.recipe_id })
      core.patch({ globalNotice: "Meal swapped and daily totals recalculated." })
    } catch (error) {
      core.patch({
        errorNotice: error instanceof Error ? error.message : "Could not swap this meal.",
      })
    } finally {
      core.patch({ mealActionLoading: null })
    }
  }

  async function cancelCurrentMeal(recipeId: string) {
    if (!core.planRecord?.id) return
    const context = core.getMealContext(recipeId)
    if (!context) return
    core.patch({ mealActionLoading: "cancel", errorNotice: "", globalNotice: "" })
    try {
      await core.client.cancelMeal(core.planRecord.id, context.day.day_number, context.meal.type)
      await core.refreshPlan(core.planRecord.id)
      core.patch({ globalNotice: "Meal removed and daily totals recalculated." })
      core.popScreen()
    } catch (error) {
      core.patch({
        errorNotice: error instanceof Error ? error.message : "Could not remove this meal.",
      })
    } finally {
      core.patch({ mealActionLoading: null })
    }
  }

  return { cancelCurrentMeal, swapCurrentMeal }
}
