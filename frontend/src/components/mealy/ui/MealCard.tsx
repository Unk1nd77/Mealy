import { formatMealType, mealVisualClass } from "../formatters"
import type { MealItem } from "../types"
import { ChevronRightIcon } from "./icons"

export function MealCard({
  meal,
  mode,
  onOpen,
}: {
  meal: MealItem
  mode: "home" | "weekly"
  onOpen: (recipeId: string) => void
}) {
  return (
    <button
      type="button"
      className={`meal-card ${mode === "home" ? "meal-card--featured" : ""}`}
      onClick={() => onOpen(meal.recipe_id)}
    >
      <div className={mealVisualClass(meal.type)}>
        <div className="meal-visual__content">
          <span className="pill pill--soft">{formatMealType(meal.type)}</span>
          <strong>{meal.title}</strong>
          <p>
            {meal.time || "Flexible time"} · {Math.round(meal.calories)} kcal
          </p>
        </div>
      </div>
      <div className="meal-card__body">
        <div>
          <h3>{meal.title}</h3>
          <p>
            {meal.time || "Planned meal"} · P {Math.round(meal.protein)} · C{" "}
            {Math.round(meal.carbs)}
          </p>
        </div>
        <span className="meal-card__cta">
          <ChevronRightIcon className="icon" />
        </span>
      </div>
    </button>
  )
}
