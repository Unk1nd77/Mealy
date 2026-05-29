import type {
  ActivityLevel,
  Goal,
  Ingredient,
  PlanResponse,
  ShoppingItem,
} from "./types";
import type { Language } from "./i18n";

export function formatGoal(
  goal: Goal | string | undefined,
  language: Language = "en",
): string {
  switch (goal) {
    case "lose":
      return language === "ru" ? "Снижение веса" : "Fat loss";
    case "gain":
      return language === "ru" ? "Набор мышц" : "Muscle gain";
    default:
      return language === "ru" ? "Баланс" : "Balance";
  }
}

export function formatActivity(
  activity: ActivityLevel | string | undefined,
  language: Language = "en",
): string {
  switch (activity) {
    case "sedentary":
      return language === "ru" ? "Низкая активность" : "Low activity";
    case "light":
      return language === "ru" ? "Лёгкая активность" : "Light activity";
    case "active":
      return language === "ru" ? "Высокая активность" : "High activity";
    case "very_active":
      return language === "ru" ? "Очень высокая активность" : "Very active";
    default:
      return language === "ru" ? "Средняя активность" : "Moderate activity";
  }
}

export function formatMealType(
  type: string,
  language: Language = "en",
): string {
  switch (type) {
    case "breakfast":
      return language === "ru" ? "Завтрак" : "Breakfast";
    case "lunch":
      return language === "ru" ? "Обед" : "Lunch";
    case "dinner":
      return language === "ru" ? "Ужин" : "Dinner";
    case "snack":
      return language === "ru" ? "Перекус" : "Snack";
    case "second_snack":
      return language === "ru" ? "Поздний перекус" : "Late snack";
    default:
      return type.replaceAll("_", " ");
  }
}
export function mealVisualClass(type: string): string {
  switch (type) {
    case "breakfast":
      return "meal-visual breakfast";
    case "lunch":
      return "meal-visual lunch";
    case "dinner":
      return "meal-visual dinner";
    case "snack":
      return "meal-visual snack";
    default:
      return "meal-visual";
  }
}

export const MACRO_SERIES = [
  { key: "protein", label: "Protein", short: "P", color: "#30d158" },
  { key: "fat", label: "Fat", short: "F", color: "#ff9f0a" },
  { key: "carbs", label: "Carbs", short: "C", color: "#ff2d55" },
] as const;

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function getTodayIndex(plan: PlanResponse | null): number {
  const totalDays = plan?.plan_data?.days.length ?? 1;
  if (!plan?.start_date) {
    return 1;
  }

  const start = new Date(`${plan.start_date}T00:00:00`);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diff = Math.floor((today.getTime() - start.getTime()) / 86_400_000);
  return clamp(diff + 1, 1, totalDays);
}

export function formatShortDate(offset = 0, language: Language = "en"): string {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return new Intl.DateTimeFormat(language === "ru" ? "ru-RU" : "en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatPlanDayLabel(
  plan: PlanResponse | null,
  dayNumber: number,
  language: Language = "en",
): string {
  if (!plan?.start_date) {
    return formatShortDate(dayNumber - 1, language);
  }

  const date = new Date(`${plan.start_date}T00:00:00`);
  date.setDate(date.getDate() + dayNumber - 1);
  return new Intl.DateTimeFormat(language === "ru" ? "ru-RU" : "en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date);
}

const COUNTABLE_PRODUCE: Array<{
  match: RegExp;
  grams: number;
  en: string;
  ru: string;
}> = [
  { match: /лимон|lemon/i, grams: 90, en: "pc", ru: "шт" },
  { match: /томат|помидор|tomato/i, grams: 120, en: "pc", ru: "шт" },
  { match: /банан|banana/i, grams: 120, en: "pc", ru: "шт" },
  { match: /авокадо|avocado/i, grams: 170, en: "pc", ru: "шт" },
  { match: /яблок|apple/i, grams: 170, en: "pc", ru: "шт" },
  { match: /лук(?!.*зел)|onion/i, grams: 100, en: "pc", ru: "шт" },
  { match: /перец|pepper/i, grams: 160, en: "pc", ru: "шт" },
  { match: /огур|cucumber/i, grams: 120, en: "pc", ru: "шт" },
  { match: /кабач|zucchini/i, grams: 250, en: "pc", ru: "шт" },
  { match: /баклажан|eggplant/i, grams: 250, en: "pc", ru: "шт" },
];

function roundTo(value: number, step: number): number {
  return Math.ceil(value / step) * step;
}

function unitLabel(unit: string, language: Language): string {
  if (unit === "piece" || unit === "pc" || unit === "pcs")
    return language === "ru" ? "шт" : "pc";
  if (unit === "slice") return language === "ru" ? "ломт." : "slice";
  if (unit === "tbsp") return language === "ru" ? "ст. л." : "tbsp";
  if (unit === "tsp") return language === "ru" ? "ч. л." : "tsp";
  return unit;
}

export function formatAmount(
  item: Ingredient | ShoppingItem,
  language: Language = "en",
  groceryMode = false,
): string {
  const unit = item.unit.toLowerCase();
  const amount = Number(item.amount) || 0;

  if (groceryMode && unit === "g") {
    const countable = COUNTABLE_PRODUCE.find((entry) =>
      entry.match.test(item.name),
    );
    if (countable) {
      const pieces = Math.max(1, Math.ceil(amount / countable.grams));
      return `${pieces} ${language === "ru" ? countable.ru : countable.en}`;
    }
    if (
      /творог|йогурт|сыр|паста|рис|греч|мука|фарш|chicken|beef|rice|flour|cheese/i.test(
        item.name,
      )
    ) {
      return `${roundTo(amount, amount >= 500 ? 100 : 50)} ${language === "ru" ? "г" : "g"}`;
    }
  }

  if (unit === "g" && amount >= 1000) {
    const value = Math.round((amount / 1000) * 10) / 10;
    return `${value} ${language === "ru" ? "кг" : "kg"}`;
  }
  if (unit === "ml" && amount >= 1000) {
    const value = Math.round((amount / 1000) * 10) / 10;
    return `${value} ${language === "ru" ? "л" : "l"}`;
  }
  if (unit === "g")
    return `${Math.round(amount)} ${language === "ru" ? "г" : "g"}`;
  if (unit === "ml") return `${Math.round(amount)} ${unit}`;
  if (unit === "piece" || unit === "pc" || unit === "pcs" || unit === "slice")
    return `${Math.round(amount)} ${unitLabel(unit, language)}`;
  return `${Math.round(amount * 10) / 10} ${unitLabel(unit, language)}`;
}
