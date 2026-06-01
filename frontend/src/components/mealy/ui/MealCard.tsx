import { formatMealType, mealVisualClass } from "../formatters"
import { useText } from "../text"
import type { MealItem } from "../types"
import { ChevronRightIcon } from "./icons"

export function MealCard({
  meal,
  mode,
  dayNumber,
  onOpen,
}: {
  meal: MealItem
  mode: "home" | "weekly"
  dayNumber?: number
  onOpen: (recipeId: string, mealType: string, dayNumber?: number) => void
}) {
  const { t } = useText()
  const macroLine = `${t("macro.p")} ${Math.round(meal.protein)}${t("common.gram")} · ${t("macro.f")} ${Math.round(meal.fat)}${t("common.gram")} · ${t("macro.c")} ${Math.round(meal.carbs)}${t("common.gram")}`

  return (
    <button
      type="button"
      className={`meal-card ${mode === "home" ? "meal-card--featured" : ""}`}
      onClick={() => onOpen(meal.recipe_id, meal.type, dayNumber)}
    >
      <div className={mealVisualClass(meal.type)}>
        <div className="meal-visual__content">
          <span className="pill pill--soft">{formatMealType(meal.type)}</span>
          <strong>{meal.title}</strong>
          <p>
            {meal.time || t("home.flexible")} · {Math.round(meal.calories)} {t("common.kcal")}
          </p>
        </div>
        {mode === "home" ? (
          <span className="meal-card__cta meal-card__cta--overlay">
            <ChevronRightIcon className="icon" />
          </span>
        ) : null}
      </div>
      {mode === "home" ? null : (
        <div className="meal-card__body">
          <div>
            <h3>{meal.title}</h3>
            <p>
              {meal.time || t("recipe.ready")} · {macroLine}
            </p>
          </div>
          <span className="meal-card__cta">
            <ChevronRightIcon className="icon" />
          </span>
        </div>
      )}
    </button>
  )
}
