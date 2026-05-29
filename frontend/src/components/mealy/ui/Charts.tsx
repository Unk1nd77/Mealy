import { MACRO_SERIES } from "../formatters";
import { useI18n } from "../i18n";
import type { DayPlan } from "../types";

export function WeeklyCaloriesChart({
  activeDayNumber,
  dailyTarget,
  days,
}: {
  activeDayNumber: number;
  dailyTarget: number;
  days: DayPlan[];
}) {
  const { t } = useI18n();
  if (!days.length) return null;
  const maxCalories = Math.max(
    ...days.map((day) => day.total_calories),
    dailyTarget || 0,
    1,
  );
  const targetY = 132 - (dailyTarget / maxCalories) * 108;
  return (
    <section className="section-block">
      <div className="section-heading">
        <div>
          <span className="section-heading__eyebrow">
            {t("week.energyProfile")}
          </span>
          <h2>{t("week.caloriesTitle")}</h2>
        </div>
        <div className="chart-target">
          <strong>{Math.round(dailyTarget)}</strong>
          <span>{t("week.dailyTarget")}</span>
        </div>
      </div>
      <div className="chart-card chart-card--weekly">
        <svg
          className="weekly-chart"
          viewBox={`0 0 ${days.length * 54} 176`}
          role="img"
          aria-label={t("week.chartLabel")}
        >
          {days.map((day, index) => {
            const barHeight = Math.max(
              (day.total_calories / maxCalories) * 108,
              8,
            );
            const x = index * 54 + 11;
            const y = 132 - barHeight;
            const isActive = day.day_number === activeDayNumber;
            return (
              <g key={day.day_number}>
                <line
                  x1={x + 16}
                  x2={x + 16}
                  y1={20}
                  y2={132}
                  className="weekly-chart__guide"
                />
                <rect
                  x={x}
                  y={y}
                  width={32}
                  height={barHeight}
                  rx={12}
                  className={
                    isActive
                      ? "weekly-chart__bar is-active"
                      : "weekly-chart__bar"
                  }
                />
                {dailyTarget > 0 ? (
                  <line
                    x1={x - 3}
                    x2={x + 35}
                    y1={targetY}
                    y2={targetY}
                    className="weekly-chart__target"
                  />
                ) : null}
                <text
                  x={x + 16}
                  y={152}
                  textAnchor="middle"
                  className="weekly-chart__label"
                >
                  {day.day_number}
                </text>
                <text
                  x={x + 16}
                  y={y - 8}
                  textAnchor="middle"
                  className="weekly-chart__value"
                >
                  {Math.round(day.total_calories)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}

export function MacroBreakdownChart({
  day,
  eyebrow,
  title,
}: {
  day: DayPlan;
  eyebrow: string;
  title: string;
}) {
  const { t } = useI18n();
  const entries = [
    {
      ...MACRO_SERIES[0],
      value: day.total_protein,
      shortKey: "macro.p" as const,
      labelKey: "common.protein" as const,
    },
    {
      ...MACRO_SERIES[1],
      value: day.total_fat,
      shortKey: "macro.f" as const,
      labelKey: "common.fat" as const,
    },
    {
      ...MACRO_SERIES[2],
      value: day.total_carbs,
      shortKey: "macro.c" as const,
      labelKey: "common.carbs" as const,
    },
  ];
  const total = entries.reduce((sum, item) => sum + item.value, 0);
  const circumference = 2 * Math.PI * 44;
  let offset = 0;
  return (
    <section className="section-block">
      <div className="section-heading">
        <div>
          <span className="section-heading__eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        <div className="chart-target">
          <strong>{Math.round(total)}</strong>
          <span>{t("common.grams")}</span>
        </div>
      </div>
      <div className="chart-card chart-card--macro">
        <div className="macro-ring">
          <svg
            viewBox="0 0 120 120"
            role="img"
            aria-label={t("home.macroEyebrow")}
          >
            <circle cx="60" cy="60" r="44" className="macro-ring__track" />
            {entries.map((entry) => {
              const segment =
                (total > 0 ? entry.value / total : 0) * circumference;
              const dashOffset = -offset;
              offset += segment;
              return (
                <circle
                  key={entry.key}
                  cx="60"
                  cy="60"
                  r="44"
                  pathLength={circumference}
                  strokeDasharray={`${segment} ${circumference - segment}`}
                  strokeDashoffset={dashOffset}
                  className="macro-ring__segment"
                  style={{ stroke: entry.color }}
                />
              );
            })}
          </svg>
          <div className="macro-ring__center">
            <strong>{Math.round(day.total_calories)}</strong>
            <span>{t("common.kcal")}</span>
          </div>
        </div>
        <div className="macro-legend">
          {entries.map((entry) => {
            const share =
              total > 0 ? Math.round((entry.value / total) * 100) : 0;
            return (
              <div key={entry.key} className="macro-legend__item">
                <span
                  className="macro-legend__swatch"
                  style={{ backgroundColor: entry.color }}
                />
                <div>
                  <strong>
                    {t(entry.shortKey)} {Math.round(entry.value)}
                    {t("common.gram")}
                  </strong>
                  <span>
                    {t(entry.labelKey)} · {share}%
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
