import { PLAN_DAYS } from "../config";
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { formatMealType, formatPlanDayLabel } from "../formatters";
import { useI18n } from "../i18n";
import type { DayPlan, MealItem } from "../types";
import { EmptyHomeScreen } from "./EmptyHomeScreen";

type WeeklyCore = Pick<
  MealyCore,
  | "clearAppState"
  | "dailyTarget"
  | "patch"
  | "planData"
  | "planRecord"
  | "pushScreen"
  | "selectedDayNumber"
  | "user"
>;
type WeeklyCommands = Pick<
  MealyCommands,
  "openCalendarExport" | "regenerateWeek"
>;

function splitDayLabel(label: string) {
  const [weekday = label, date = ""] = label
    .split(",")
    .map((part) => part.trim());
  return { weekday, date };
}

function dayMealPreview(meals: MealItem[]) {
  return meals.slice(0, 3);
}

function macroTotal(day: DayPlan) {
  return Math.round(day.total_protein + day.total_fat + day.total_carbs);
}

export function WeeklyScreen({
  commands,
  core,
}: {
  commands: WeeklyCommands;
  core: WeeklyCore;
}) {
  const { language, t } = useI18n();
  if (!core.planData)
    return <EmptyHomeScreen commands={commands} core={core} />;
  if (core.planData.days.length < PLAN_DAYS) {
    return (
      <section className="screen-card">
        <div className="empty-state">
          <h3>
            {t("week.shortPlanTitle", { count: core.planData.days.length })}
          </h3>
          <p>{t("week.shortPlanCopy")}</p>
          <button
            type="button"
            className="button button--primary"
            onClick={commands.regenerateWeek}
          >
            {t("week.regenerate")}
          </button>
        </div>
      </section>
    );
  }
  const activeDay =
    core.planData.days.find(
      (day) => day.day_number === core.selectedDayNumber,
    ) ?? core.planData.days[0];
  if (!activeDay) return <EmptyHomeScreen commands={commands} core={core} />;

  return (
    <section className="screen-card screen-card--week">
      <div className="section-toolbar section-toolbar--tight week-toolbar">
        <div className="toolbar-actions">
          <button
            type="button"
            className="mini-link week-action week-action--primary"
            onClick={commands.regenerateWeek}
          >
            {t("week.regenerate")}
          </button>
          <button
            type="button"
            className="mini-link week-action week-action--secondary"
            onClick={commands.openCalendarExport}
          >
            {t("week.calendar")}
          </button>
          <button
            type="button"
            className="mini-link week-action week-action--secondary week-toolbar__optional"
            onClick={() => core.pushScreen({ name: "integrations" })}
          >
            {t("week.more")}
          </button>
        </div>
      </div>

      <div
        className="week-calendar"
        role="tablist"
        aria-label={t("week.daysLabel")}
      >
        {core.planData.days.map((day) => {
          const label = splitDayLabel(
            formatPlanDayLabel(core.planRecord, day.day_number, language),
          );
          const isActive = day.day_number === activeDay.day_number;
          const caloriesDelta = Math.round(
            day.total_calories - core.dailyTarget,
          );

          return (
            <button
              key={day.day_number}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`week-day-card ${isActive ? "is-active" : ""}`}
              onClick={() => core.patch({ selectedDayNumber: day.day_number })}
            >
              <span className="week-day-card__date">
                <strong>{label.weekday}</strong>
                <small>
                  {label.date || `${t("week.day")} ${day.day_number}`}
                </small>
              </span>
              <span className="week-day-card__energy">
                {Math.round(day.total_calories)}
                <small>{t("common.kcal")}</small>
              </span>
              <span className="week-day-card__delta">
                {caloriesDelta === 0
                  ? t("week.onTarget")
                  : `${caloriesDelta > 0 ? "+" : ""}${caloriesDelta} ${t("week.fromTarget")}`}
              </span>
              <span className="week-day-card__meals">
                {dayMealPreview(day.meals).map((meal) => (
                  <span
                    key={`${day.day_number}-${meal.type}-${meal.recipe_id}`}
                  >
                    <i className={`meal-dot meal-dot--${meal.type}`} />
                    {formatMealType(meal.type, language)}
                  </span>
                ))}
              </span>
            </button>
          );
        })}
      </div>

      <div className="week-selected-day">
        <div className="week-selected-day__summary">
          <p className="section-heading__eyebrow">
            {t("week.day")} {activeDay.day_number}
          </p>
          <h3>
            {formatPlanDayLabel(
              core.planRecord,
              activeDay.day_number,
              language,
            )}
          </h3>
          <div className="week-metrics">
            <div>
              <strong>{Math.round(activeDay.total_calories)}</strong>
              <span>{t("common.kcal")}</span>
            </div>
            <div>
              <strong>{Math.round(activeDay.total_protein)}g</strong>
              <span>{t("week.protein")}</span>
            </div>
            <div>
              <strong>{macroTotal(activeDay)}g</strong>
              <span>{t("week.macros")}</span>
            </div>
          </div>
        </div>

        <div className="week-meal-agenda">
          {activeDay.meals.map((meal) => (
            <button
              key={`${meal.recipe_id}-${meal.type}`}
              type="button"
              className="week-meal-row"
              onClick={() =>
                core.pushScreen({
                  name: "recipe",
                  recipeId: meal.recipe_id,
                  dayNumber: activeDay.day_number,
                  mealType: meal.type,
                })
              }
            >
              <span className="week-meal-row__time">
                {meal.time || t("home.anyTime")}
              </span>
              <span className={`meal-dot meal-dot--${meal.type}`} />
              <span className="week-meal-row__main">
                <strong>{meal.title}</strong>
                <small>{formatMealType(meal.type, language)}</small>
              </span>
              <span className="week-meal-row__energy">
                {Math.round(meal.calories)} {t("common.kcal")}
              </span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
