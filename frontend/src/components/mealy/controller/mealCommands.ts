import type { MealyCore } from "./useMealyCommands"

export function createMealCommands(core: MealyCore) {
  async function swapCurrentMeal(recipeId: string, dayNumber?: number, mealType?: string) {
    if (!core.planRecord?.id) return
    const context = core.getMealContext(recipeId, dayNumber, mealType)
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
      if (nextMeal)
        core.replaceCurrentScreen({
          name: "recipe",
          recipeId: nextMeal.recipe_id,
          dayNumber: context.day.day_number,
          mealType: nextMeal.type,
        })
      core.patch({ globalNotice: "Блюдо заменено, дневные итоги пересчитаны." })
    } catch (error) {
      core.patch({
        errorNotice: error instanceof Error ? error.message : "Не удалось заменить блюдо.",
      })
    } finally {
      core.patch({ mealActionLoading: null })
    }
  }

  async function cancelCurrentMeal(recipeId: string, dayNumber?: number, mealType?: string) {
    if (!core.planRecord?.id) return
    const context = core.getMealContext(recipeId, dayNumber, mealType)
    if (!context) return
    core.patch({ mealActionLoading: "cancel", errorNotice: "", globalNotice: "" })
    try {
      await core.client.cancelMeal(core.planRecord.id, context.day.day_number, context.meal.type)
      await core.refreshPlan(core.planRecord.id)
      core.patch({ globalNotice: "Блюдо убрано, дневные итоги пересчитаны." })
      core.popScreen()
    } catch (error) {
      core.patch({
        errorNotice: error instanceof Error ? error.message : "Не удалось убрать блюдо.",
      })
    } finally {
      core.patch({ mealActionLoading: null })
    }
  }

  return { cancelCurrentMeal, swapCurrentMeal }
}
