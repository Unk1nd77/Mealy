import { useState } from "react";

import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { formatAmount, formatMealType, mealVisualClass } from "../formatters";
import { useText } from "../text";
import type { Ingredient } from "../types";
import { ScreenHeader } from "../ui/ScreenHeader";

type RecipeCore = Pick<
  MealyCore,
  | "getMealContext"
  | "mealActionLoading"
  | "popScreen"
  | "pushScreen"
  | "recipeById"
>;
type RecipeCommands = Pick<
  MealyCommands,
  "cancelCurrentMeal" | "swapCurrentMeal"
>;

export function RecipeScreen({
  commands,
  core,
  recipeId,
  dayNumber,
  mealType,
}: {
  commands: RecipeCommands;
  core: RecipeCore;
  recipeId: string;
  dayNumber?: number;
  mealType?: string;
}) {
  const { t } = useText();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const recipe = core.recipeById(recipeId);
  const context = core.getMealContext(recipeId, dayNumber, mealType);
  const meal = context?.meal;

  if (!meal) {
    return (
      <section className="screen-card">
        <ScreenHeader
          title={t("recipe.titleFallback")}
          subtitle={t("recipe.notAvailableSubtitle")}
          onBack={core.popScreen}
        />
        <div className="empty-state">
          <h3>{t("recipe.notAvailable")}</h3>
          <p>{t("recipe.notAvailableCopy")}</p>
        </div>
      </section>
    );
  }

  const ingredients = recipe?.ingredients ?? meal.ingredients_summary ?? [];
  const cookingSteps = recipe?.cooking_steps ?? [];
  return (
    <section className="screen-card screen-card--detail">
      <ScreenHeader
        title={meal.title}
        subtitle={t("recipe.subtitle")}
        onBack={core.popScreen}
      />
      <div className={`${mealVisualClass(meal.type)} meal-visual--detail`}>
        <div className="meal-visual__content meal-visual__content--detail">
          <span className="pill pill--soft">{formatMealType(meal.type)}</span>
          <strong>{meal.title}</strong>
          <p>
            {meal.time || t("recipe.anytime")} ·{" "}
            {recipe?.prep_time_min
              ? t("recipe.prepTime", { count: recipe.prep_time_min })
              : t("recipe.ready")}
          </p>
        </div>
      </div>
      <div className="macro-grid">
        <div>
          <strong>{Math.round(meal.calories)}</strong>
          <span>{t("common.kcal")}</span>
        </div>
        <div>
          <strong>{Math.round(meal.protein)}g</strong>
          <span>{t("common.protein")}</span>
        </div>
        <div>
          <strong>{Math.round(meal.fat)}g</strong>
          <span>{t("common.fat")}</span>
        </div>
        <div>
          <strong>{Math.round(meal.carbs)}g</strong>
          <span>{t("common.carbs")}</span>
        </div>
      </div>
      <section className="detail-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">
              {t("recipe.planControls")}
            </span>
            <h2>{t("recipe.adjust")}</h2>
          </div>
        </div>
        <div className="meal-control-grid">
          <button
            type="button"
            className="button button--ghost"
            onClick={() =>
              void commands.swapCurrentMeal(recipeId, dayNumber, mealType)
            }
            disabled={core.mealActionLoading !== null}
          >
            {core.mealActionLoading === "swap"
              ? t("recipe.replacing")
              : t("recipe.replace")}
          </button>
          {confirmRemove ? (
            <div className="remove-confirm">
              <p>
                <strong>{t("recipe.removeConfirm")}</strong>
                <span>{t("recipe.removeConfirmText")}</span>
              </p>
              <div className="meal-control-grid">
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => {
                    setConfirmRemove(false);
                    void commands.cancelCurrentMeal(
                      recipeId,
                      dayNumber,
                      mealType,
                    );
                  }}
                  disabled={core.mealActionLoading !== null}
                >
                  {core.mealActionLoading === "cancel"
                    ? t("recipe.removing")
                    : t("recipe.removeYes")}
                </button>
                <button
                  type="button"
                  className="button button--ghost"
                  onClick={() => setConfirmRemove(false)}
                  disabled={core.mealActionLoading !== null}
                >
                  {t("recipe.removeNo")}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setConfirmRemove(true)}
              disabled={core.mealActionLoading !== null}
            >
              {t("recipe.remove")}
            </button>
          )}
        </div>
      </section>

      <section className="detail-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">
              {t("recipe.ingredients")}
            </span>
            <h2>{t("recipe.ingredientsTitle")}</h2>
          </div>
        </div>
        <div className="ingredient-list">
          {ingredients.map((ingredient: Ingredient) => (
            <div
              key={`${ingredient.name}-${ingredient.amount}-${ingredient.unit}`}
              className="ingredient-row"
            >
              <div>
                <strong>{ingredient.name}</strong>
              </div>
              <span>{formatAmount(ingredient)}</span>
            </div>
          ))}
        </div>
      </section>
      {cookingSteps.length ? (
        <section className="detail-block">
          <div className="section-heading">
            <div>
              <span className="section-heading__eyebrow">
                {t("recipe.steps")}
              </span>
              <h2>{t("recipe.stepsTitle")}</h2>
            </div>
          </div>
          <ol className="recipe-steps">
            {cookingSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </section>
      ) : null}
      <div className="sticky-footer">
        <div className="sticky-footer__summary">
          <strong>
            {Math.round(meal.calories)} {t("common.kcal")}
          </strong>
          <span>{formatMealType(meal.type)}</span>
        </div>
        <button
          type="button"
          className="button button--primary"
          onClick={() => core.pushScreen({ name: "shopping" })}
        >
          {t("recipe.openShopping")}
        </button>
      </div>
    </section>
  );
}
