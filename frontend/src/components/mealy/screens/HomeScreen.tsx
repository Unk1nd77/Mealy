import { API_BASE, PLAN_DAYS } from "../config";
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { formatGoal, formatMealType, formatPlanDayLabel } from "../formatters";
import { useText } from "../text";
import {
  MacroBreakdownChart,
  MealCard,
  ObservabilityPanel,
  WeeklyCaloriesChart,
} from "../ui/planWidgets";
import { EmptyHomeScreen } from "./EmptyHomeScreen";

type HomeCore = Pick<
  MealyCore,
  | "clearAppState"
  | "dailyTarget"
  | "observability"
  | "observabilityLoading"
  | "planData"
  | "planRecord"
  | "pushScreen"
  | "todayCalories"
  | "todayIndex"
  | "todayPlan"
  | "todayProgress"
  | "user"
>;

type HomeCommands = Pick<MealyCommands, "regenerateWeek">;

export function HomeScreen({
  commands,
  core,
}: {
  commands: HomeCommands;
  core: HomeCore;
}) {
  const { t } = useText();

  if (!core.planData || !core.todayPlan) {
    return <EmptyHomeScreen commands={commands} core={core} />;
  }

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

  const nextMeal = core.todayPlan.meals[0];
  const prepMeal = core.todayPlan.meals[1] ?? nextMeal;
  const overBudget = Math.round(core.todayCalories - core.dailyTarget);
  const remainingCalories = Math.round(core.dailyTarget - core.todayCalories);
  const calendarHref = core.planRecord
    ? `${API_BASE}/api/plans/${core.planRecord.id}/calendar.ics`
    : undefined;

  return (
    <section className="screen-card screen-card--home">
      <div className="home-hero">
        <div className="home-hero__top">
          <div>
            <div className="eyebrow eyebrow--light">
              {t("nav.today")} ·{" "}
              {formatPlanDayLabel(core.planRecord, core.todayIndex)}
            </div>
            <h1>{t("home.todayPlanned")}</h1>
            <p>{t("home.heroCopy")}</p>
          </div>
          <span className="hero-badge">
            {formatGoal(core.planData.user_profile?.goal || core.user?.goal)}
          </span>
        </div>
        <div className="home-hero__bottom">
          <div className="progress-cluster">
            <div className="progress-cluster__value">{core.todayProgress}%</div>
            <div>
              <strong>
                {Math.round(core.todayCalories)} /{" "}
                {Math.round(core.dailyTarget)} {t("common.kcal")}
              </strong>
              <p>
                {overBudget > 0
                  ? t("home.kcalOver", { count: overBudget })
                  : t("home.kcalLeft", { count: remainingCalories })}
              </p>
            </div>
          </div>
          <div className="progress-bar">
            <span style={{ width: `${Math.min(core.todayProgress, 100)}%` }} />
          </div>
          <div className="hero-stats">
            <div>
              <strong>{core.todayPlan.meals.length}</strong>
              <span>{t("common.meals")}</span>
            </div>
            <div>
              <strong>
                {Math.round(core.todayPlan.total_protein)}
                {t("common.gram")}
              </strong>
              <span>{t("common.protein")}</span>
            </div>
            <div>
              <strong>
                {Math.round(core.todayPlan.total_fat)}
                {t("common.gram")}
              </strong>
              <span>{t("common.fat")}</span>
            </div>
            <div>
              <strong>
                {Math.round(core.todayPlan.total_carbs)}
                {t("common.gram")}
              </strong>
              <span>{t("common.carbs")}</span>
            </div>
          </div>
          <a
            href={calendarHref}
            className="mini-link mini-link--light"
            download={core.planRecord ? `mealy-plan-${core.planRecord.id}.ics` : undefined}
          >
            {t("home.addCalendar")}
          </a>
        </div>
      </div>
      {nextMeal ? (
        <section className="today-focus">
          <div className="section-heading section-heading--compact">
            <div>
              <span className="section-heading__eyebrow">
                {t("home.nextUp")}
              </span>
              <h2>{nextMeal.title}</h2>
            </div>
            <span className="today-focus__time">
              {nextMeal.time || t("home.flexible")}
            </span>
          </div>
          <button
            type="button"
            className="next-meal"
            onClick={() => {
              const screen = {
                name: "recipe" as const,
                recipeId: nextMeal.recipe_id,
                mealType: nextMeal.type,
              };
              if (core.todayPlan?.day_number !== undefined) {
                core.pushScreen({
                  ...screen,
                  dayNumber: core.todayPlan.day_number,
                });
              } else {
                core.pushScreen(screen);
              }
            }}
          >
            <span className="next-meal__type">
              {formatMealType(nextMeal.type)}
            </span>
            <strong>
              {Math.round(nextMeal.calories)} {t("common.kcal")}
            </strong>
            <span>
              {t("macro.p")} {Math.round(nextMeal.protein)}
              {t("common.gram")} · {t("macro.f")} {Math.round(nextMeal.fat)}
              {t("common.gram")} · {t("macro.c")} {Math.round(nextMeal.carbs)}
              {t("common.gram")}
            </span>
          </button>
          {prepMeal && prepMeal.recipe_id !== nextMeal.recipe_id ? (
            <p className="today-focus__prep">
              {t("home.prepareNext")} <strong>{prepMeal.title}</strong>
            </p>
          ) : null}
        </section>
      ) : null}
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">
              {t("home.dayRhythm")}
            </span>
            <h2>{t("home.dayRhythmTitle")}</h2>
          </div>
          <button
            type="button"
            className="mini-link"
            onClick={() => core.pushScreen({ name: "weekly" })}
          >
            {t("home.fullWeek")}
          </button>
        </div>
        <div className="day-rhythm">
          {core.todayPlan.meals.map((meal) => (
            <button
              key={`${meal.recipe_id}-${meal.type}`}
              type="button"
              className="rhythm-row"
              onClick={() => {
                const screen = {
                  name: "recipe" as const,
                  recipeId: meal.recipe_id,
                  mealType: meal.type,
                };
                if (core.todayPlan?.day_number !== undefined) {
                  core.pushScreen({
                    ...screen,
                    dayNumber: core.todayPlan.day_number,
                  });
                } else {
                  core.pushScreen(screen);
                }
              }}
            >
              <span
                className={`rhythm-row__dot rhythm-row__dot--${meal.type}`}
              />
              <span className="rhythm-row__time">
                {meal.time || t("home.anyTime")}
              </span>
              <span className="rhythm-row__title">
                <strong>{meal.title}</strong>
                <small>{formatMealType(meal.type)}</small>
              </span>
              <span className="rhythm-row__energy">
                {Math.round(meal.calories)} {t("common.kcal")}
              </span>
            </button>
          ))}
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">
              {t("home.recipes")}
            </span>
            <h2>{t("home.recipesTitle")}</h2>
          </div>
        </div>
        <div className="meal-stack">
          {core.todayPlan.meals.map((meal) => (
            <MealCard
              key={`${meal.recipe_id}-${meal.type}`}
              {...(core.todayPlan?.day_number !== undefined
                ? { dayNumber: core.todayPlan.day_number }
                : {})}
              meal={meal}
              mode="home"
              onOpen={(recipeId, mealType, dayNumber) => {
                const screen = {
                  name: "recipe" as const,
                  recipeId,
                  mealType,
                };
                if (dayNumber !== undefined) {
                  core.pushScreen({ ...screen, dayNumber });
                } else {
                  core.pushScreen(screen);
                }
              }}
            />
          ))}
        </div>
      </section>
      <div className="insights-stack">
        <WeeklyCaloriesChart
          activeDayNumber={core.todayPlan.day_number}
          dailyTarget={core.dailyTarget}
          days={core.planData.days}
        />
        <MacroBreakdownChart
          day={core.todayPlan}
          title={t("home.macroTitle")}
          eyebrow={t("home.macroEyebrow")}
        />
      </div>
      <ObservabilityPanel
        mode="result"
        observability={core.observability}
        observabilityLoading={core.observabilityLoading}
      />
    </section>
  );
}
