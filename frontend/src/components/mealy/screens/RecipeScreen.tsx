import "../../../styles/mealy/02-form-actions.css"
import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/04-generation.css"
import "../../../styles/mealy/07-actions.css"
import "../../../styles/mealy/08-meals.css"
import "../../../styles/mealy/09-detail.css"

import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { formatMealType, mealVisualClass } from "../formatters"
import { ScreenHeader } from "../ui/ScreenHeader"

type RecipeCore = Pick<
  MealyCore,
  "getMealContext" | "mealActionLoading" | "popScreen" | "pushScreen" | "recipeById"
>
type RecipeCommands = Pick<MealyCommands, "cancelCurrentMeal" | "swapCurrentMeal">

export function RecipeScreen({
  commands,
  core,
  recipeId,
}: {
  commands: RecipeCommands
  core: RecipeCore
  recipeId: string
}) {
  const recipe = core.recipeById(recipeId)
  const context = core.getMealContext(recipeId)
  const meal = context?.meal

  if (!meal) {
    return (
      <section className="screen-card">
        <ScreenHeader
          title="Recipe"
          subtitle="Could not find this recipe in the current plan."
          onBack={core.popScreen}
        />
        <div className="empty-state">
          <h3>Recipe not available</h3>
          <p>Return to Today or Weekly Plan and pick another meal card.</p>
        </div>
      </section>
    )
  }

  const ingredients = recipe?.ingredients ?? meal.ingredients_summary ?? []
  return (
    <section className="screen-card screen-card--detail">
      <ScreenHeader
        title={meal.title}
        subtitle="Recipe detail with macros, ingredients, and a quick jump into groceries."
        onBack={core.popScreen}
      />
      <div className={`${mealVisualClass(meal.type)} meal-visual--detail`}>
        <div className="meal-visual__content meal-visual__content--detail">
          <span className="pill pill--soft">{formatMealType(meal.type)}</span>
          <strong>{meal.title}</strong>
          <p>
            {meal.time || "Anytime meal"} ·{" "}
            {recipe?.prep_time_min ? `${recipe.prep_time_min} min` : "Ready when you are"}
          </p>
        </div>
      </div>
      <div className="macro-grid">
        <div>
          <strong>{Math.round(meal.calories)}</strong>
          <span>kcal</span>
        </div>
        <div>
          <strong>{Math.round(meal.protein)}g</strong>
          <span>Protein</span>
        </div>
        <div>
          <strong>{Math.round(meal.fat)}g</strong>
          <span>Fat</span>
        </div>
        <div>
          <strong>{Math.round(meal.carbs)}g</strong>
          <span>Carbs</span>
        </div>
      </div>
      <section className="detail-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">Plan controls</span>
            <h2>Adjust this meal</h2>
          </div>
        </div>
        <div className="meal-control-grid">
          <button
            type="button"
            className="button button--ghost"
            onClick={() => void commands.swapCurrentMeal(recipeId)}
            disabled={core.mealActionLoading !== null}
          >
            {core.mealActionLoading === "swap" ? "Replacing..." : "Replace meal"}
          </button>
          <button
            type="button"
            className="button button--ghost"
            onClick={() => void commands.cancelCurrentMeal(recipeId)}
            disabled={core.mealActionLoading !== null}
          >
            {core.mealActionLoading === "cancel" ? "Removing..." : "Remove"}
          </button>
        </div>
      </section>
      <section className="detail-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">Description</span>
            <h2>What this meal does</h2>
          </div>
        </div>
        <p className="soft-copy">
          {recipe?.description ||
            "A guided meal from your current plan. Exact ingredients come from the verified recipe catalog used during generation."}
        </p>
      </section>
      <section className="detail-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">Ingredients</span>
            <h2>What to prepare</h2>
          </div>
        </div>
        <div className="ingredient-list">
          {ingredients.map((ingredient) => (
            <div
              key={`${ingredient.name}-${ingredient.amount}-${ingredient.unit}`}
              className="ingredient-row"
            >
              <div>
                <strong>{ingredient.name}</strong>
                <span>{ingredient.unit}</span>
              </div>
              <span>
                {ingredient.amount} {ingredient.unit}
              </span>
            </div>
          ))}
        </div>
      </section>
      <div className="sticky-footer">
        <div className="sticky-footer__summary">
          <strong>{Math.round(meal.calories)} kcal</strong>
          <span>{formatMealType(meal.type)}</span>
        </div>
        <button
          type="button"
          className="button button--primary"
          onClick={() => core.pushScreen({ name: "shopping" })}
        >
          Open shopping list
        </button>
      </div>
    </section>
  )
}
