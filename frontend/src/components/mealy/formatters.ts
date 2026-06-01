import type {
  ActivityLevel,
  Goal,
  Ingredient,
  PlanResponse,
  ShoppingItem,
} from "./types";

export function formatGoal(goal: Goal | string | undefined): string {
  switch (goal) {
    case "lose":
      return "Снижение веса";
    case "gain":
      return "Набор мышц";
    default:
      return "Баланс";
  }
}

export function formatActivity(activity: ActivityLevel | string | undefined): string {
  switch (activity) {
    case "sedentary":
      return "Низкая активность";
    case "light":
      return "Лёгкая активность";
    case "active":
      return "Высокая активность";
    case "very_active":
      return "Очень высокая активность";
    default:
      return "Средняя активность";
  }
}

export function formatMealType(type: string): string {
  switch (type) {
    case "breakfast":
      return "Завтрак";
    case "lunch":
      return "Обед";
    case "dinner":
      return "Ужин";
    case "snack":
      return "Перекус";
    case "second_snack":
      return "Поздний перекус";
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
  { key: "protein", label: "Белок", short: "Б", color: "#30d158" },
  { key: "fat", label: "Жиры", short: "Ж", color: "#ff9f0a" },
  { key: "carbs", label: "Углеводы", short: "У", color: "#ff2d55" },
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

export function formatShortDate(offset = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + offset);
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatPlanDayLabel(
  plan: PlanResponse | null,
  dayNumber: number,
): string {
  if (!plan?.start_date) {
    return formatShortDate(dayNumber - 1);
  }

  const date = new Date(`${plan.start_date}T00:00:00`);
  date.setDate(date.getDate() + dayNumber - 1);
  return new Intl.DateTimeFormat("ru-RU", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(date);
}

function unitLabel(unit: string): string {
  if (unit === "piece" || unit === "pc" || unit === "pcs") return "шт";
  if (unit === "slice") return "ломт.";
  if (unit === "tbsp") return "ст. л.";
  if (unit === "tsp") return "ч. л.";
  return unit;
}

export function formatAmount(
  item: Ingredient | ShoppingItem,
  groceryMode = false,
): string {
  const unit = item.unit.toLowerCase();
  const amount = Number(item.amount) || 0;

  if (groceryMode && unit === "g") {
    return `${Math.round(amount)} г`;
  }
  if (groceryMode && unit === "ml") {
    return `${Math.round(amount)} мл`;
  }

  if (unit === "g" && amount >= 1000) {
    const value = Math.round((amount / 1000) * 10) / 10;
    return `${value} кг`;
  }
  if (unit === "ml" && amount >= 1000) {
    const value = Math.round((amount / 1000) * 10) / 10;
    return `${value} л`;
  }
  if (unit === "g") return `${Math.round(amount)} г`;
  if (unit === "ml") return `${Math.round(amount)} мл`;
  if (unit === "piece" || unit === "pc" || unit === "pcs" || unit === "slice")
    return `${Math.round(amount)} ${unitLabel(unit)}`;
  return `${Math.round(amount * 10) / 10} ${unitLabel(unit)}`;
}
