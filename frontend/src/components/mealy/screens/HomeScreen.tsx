import "../../../styles/mealy/02-form-actions.css"
import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/04-generation.css"
import "../../../styles/mealy/05-home-hero.css"
import "../../../styles/mealy/05-home.css"
import "../../../styles/mealy/06-charts.css"
import "../../../styles/mealy/07-actions.css"
import "../../../styles/mealy/08-meals.css"
import "../../../styles/mealy/10-webapp.css"
import "../../../styles/mealy/11-webapp-states-mobile.css"
import "../../../styles/mealy/11-webapp-states.css"

import { PLAN_DAYS } from "../config"
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { formatGoal, formatMealType, formatPlanDayLabel } from "../formatters"
import { CalendarIcon, CartIcon, RefreshIcon, ShareIcon, UserIcon } from "../ui/icons"
import {
  MacroBreakdownChart,
  MealCard,
  ObservabilityPanel,
  QuickActions,
  WeeklyCaloriesChart,
} from "../ui/planWidgets"
import { EmptyHomeScreen } from "./EmptyHomeScreen"

type HomeCore = Pick<
  MealyCore,
  | "bootstrapDevSession"
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
>

type HomeCommands = Pick<MealyCommands, "openCalendarExport" | "regenerateWeek">

export function HomeScreen({ commands, core }: { commands: HomeCommands; core: HomeCore }) {
  if (!core.planData || !core.todayPlan) {
    return <EmptyHomeScreen commands={commands} core={core} />
  }

  const actions = [
    {
      label: "Weekly Plan",
      description: `Review all ${PLAN_DAYS} generated days and switch by date.`,
      icon: <CalendarIcon className="icon" />,
      onClick: () => core.pushScreen({ name: "weekly" }),
    },
    {
      label: "Shopping List",
      description: "See the aggregated grocery list for the full week.",
      icon: <CartIcon className="icon" />,
      onClick: () => core.pushScreen({ name: "shopping" }),
    },
    {
      label: "System Integrations",
      description: "Send the plan to Calendar, Files, Notes, or the system share sheet.",
      icon: <ShareIcon className="icon" />,
      onClick: () => core.pushScreen({ name: "integrations" }),
    },
    {
      label: "Profile",
      description: "Update goals, dislikes, allergies, and activity.",
      icon: <UserIcon className="icon" />,
      onClick: () => core.pushScreen({ name: "profile" }),
    },
    {
      label: "Refresh Week",
      description: "Run the planner again with your current constraints.",
      icon: <RefreshIcon className="icon" />,
      onClick: commands.regenerateWeek,
    },
  ]
  const nextMeal = core.todayPlan.meals[0]
  const prepMeal = core.todayPlan.meals[1] ?? nextMeal
  const remainingCalories = Math.max(Math.round(core.dailyTarget - core.todayCalories), 0)

  return (
    <section className="screen-card screen-card--home">
      <div className="home-hero">
        <div className="home-hero__top">
          <div>
            <div className="eyebrow eyebrow--light">
              Today · {formatPlanDayLabel(core.planRecord, core.todayIndex)}
            </div>
            <h1>Today is already planned.</h1>
            <p>Mealy keeps the day simple: next meal, daily energy, and what to prepare next.</p>
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
                {Math.round(core.todayCalories)} / {Math.round(core.dailyTarget)} kcal
              </strong>
              <p>{remainingCalories} kcal left in the day plan</p>
            </div>
          </div>
          <div className="progress-bar">
            <span style={{ width: `${core.todayProgress}%` }} />
          </div>
          <div className="hero-stats">
            <div>
              <strong>{core.todayPlan.meals.length}</strong>
              <span>Meals</span>
            </div>
            <div>
              <strong>{Math.round(core.todayPlan.total_protein)}g</strong>
              <span>Protein</span>
            </div>
            <div>
              <strong>{Math.round(core.todayPlan.total_carbs)}g</strong>
              <span>Carbs</span>
            </div>
          </div>
          <button
            type="button"
            className="mini-link mini-link--light"
            onClick={commands.openCalendarExport}
          >
            Add to Calendar
          </button>
        </div>
      </div>
      {nextMeal ? (
        <section className="today-focus">
          <div className="section-heading section-heading--compact">
            <div>
              <span className="section-heading__eyebrow">Next up</span>
              <h2>{nextMeal.title}</h2>
            </div>
            <span className="today-focus__time">{nextMeal.time || "Flexible"}</span>
          </div>
          <button
            type="button"
            className="next-meal"
            onClick={() => core.pushScreen({ name: "recipe", recipeId: nextMeal.recipe_id })}
          >
            <span className="next-meal__type">{formatMealType(nextMeal.type)}</span>
            <strong>{Math.round(nextMeal.calories)} kcal</strong>
            <span>
              P {Math.round(nextMeal.protein)} · F {Math.round(nextMeal.fat)} · C{" "}
              {Math.round(nextMeal.carbs)}
            </span>
          </button>
          {prepMeal && prepMeal.recipe_id !== nextMeal.recipe_id ? (
            <p className="today-focus__prep">
              Prepare next: <strong>{prepMeal.title}</strong>
            </p>
          ) : null}
        </section>
      ) : null}
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">Day rhythm</span>
            <h2>Meals in the order they happen</h2>
          </div>
          <button
            type="button"
            className="mini-link"
            onClick={() => core.pushScreen({ name: "weekly" })}
          >
            Full week
          </button>
        </div>
        <div className="day-rhythm">
          {core.todayPlan.meals.map((meal) => (
            <button
              key={`${meal.recipe_id}-${meal.type}`}
              type="button"
              className="rhythm-row"
              onClick={() => core.pushScreen({ name: "recipe", recipeId: meal.recipe_id })}
            >
              <span className={`rhythm-row__dot rhythm-row__dot--${meal.type}`} />
              <span className="rhythm-row__time">{meal.time || "Any time"}</span>
              <span className="rhythm-row__title">
                <strong>{meal.title}</strong>
                <small>{formatMealType(meal.type)}</small>
              </span>
              <span className="rhythm-row__energy">{Math.round(meal.calories)} kcal</span>
            </button>
          ))}
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">Recipes</span>
            <h2>Open a meal when you are ready to cook</h2>
          </div>
        </div>
        <div className="meal-stack">
          {core.todayPlan.meals.map((meal) => (
            <MealCard
              key={`${meal.recipe_id}-${meal.type}`}
              meal={meal}
              mode="home"
              onOpen={(recipeId) => core.pushScreen({ name: "recipe", recipeId })}
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
          title="Macro balance for today"
          eyebrow="Macro distribution"
        />
      </div>
      <ObservabilityPanel
        mode="result"
        observability={core.observability}
        observabilityLoading={core.observabilityLoading}
      />
      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="section-heading__eyebrow">Quick actions</span>
            <h2>Jump into the rest of the app</h2>
          </div>
        </div>
        <QuickActions actions={actions} />
      </section>
    </section>
  )
}
