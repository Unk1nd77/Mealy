import { useState } from "react";

import { API_BASE, PLAN_DAYS } from "../config";
import type { MealyCore } from "../controller/useMealyCommands";
import { formatAmount } from "../formatters";
import { useText } from "../text";
import { ScreenHeader } from "../ui/ScreenHeader";
import { TimeIcon } from "../ui/icons";
import { ObservabilityPanel } from "../ui/planWidgets";

type ShoppingCore = Pick<
  MealyCore,
  | "observability"
  | "observabilityLoading"
  | "popScreen"
  | "shoppingList"
  | "shoppingLoading"
  | "planRecord"
>;
export function ShoppingScreen({
  core,
}: {
  core: ShoppingCore;
}) {
  const { t } = useText();
  const planId = core.planRecord?.id;
  const shoppingPdfHref = planId
    ? `${API_BASE}/api/plans/${planId}/shopping-list.pdf`
    : undefined;

  const [checked, setChecked] = useState<Set<string>>(new Set());

  function toggleChecked(key: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function clearChecked() {
    setChecked(new Set());
  }

  return (
    <section className="screen-card">
      <ScreenHeader
        title={t("shopping.title")}
        subtitle={t("shopping.subtitle", { count: PLAN_DAYS })}
        onBack={core.popScreen}
      />
      <ObservabilityPanel
        mode="result"
        observability={core.observability}
        observabilityLoading={core.observabilityLoading}
      />
      <div className="section-toolbar">
        <div className="soft-copy">
          {core.shoppingList === null
            ? t("common.loading")
            : core.shoppingList.length === 0
              ? t("shopping.emptyTitle")
              : t("shopping.grouped", { count: core.shoppingList.length })}
        </div>
        <div className="chip-row">
          {shoppingPdfHref && core.shoppingList?.length ? (
            <a
              href={shoppingPdfHref}
              className="mini-link"
              download={`mealy-shopping-list-${planId}.pdf`}
            >
              {t("shopping.downloadPdf")}
            </a>
          ) : null}
          {checked.size > 0 ? (
            <button
              type="button"
              className="button button--ghost button--small"
              onClick={clearChecked}
            >
              {t("shopping.clearChecked")}
            </button>
          ) : null}
        </div>
      </div>
      {core.shoppingLoading ? (
        <div className="loading-card">
          <TimeIcon className="icon icon--brand" />
          <span>{t("shopping.loading")}</span>
        </div>
      ) : null}
      {!core.shoppingLoading && core.shoppingList?.length ? (
        <div className="shopping-list">
          {core.shoppingList.map((item) => {
            const key = `${item.name}-${item.unit}`;
            const isChecked = checked.has(key);
            return (
              <button
                key={key}
                type="button"
                className={`shopping-row shopping-row--interactive ${isChecked ? "is-checked" : ""}`}
                onClick={() => toggleChecked(key)}
              >
                <span
                  className={`shopping-check ${isChecked ? "is-checked" : ""}`}
                  aria-hidden="true"
                />
                <div>
                  <strong>{item.name}</strong>
                </div>
                <span>{formatAmount(item, true)}</span>
              </button>
            );
          })}
        </div>
      ) : null}
      {!core.shoppingLoading && !core.shoppingList?.length ? (
        <div className="empty-state empty-state--compact">
          <h3>{t("shopping.emptyTitle")}</h3>
          <p>{t("shopping.emptyCopy")}</p>
        </div>
      ) : null}
    </section>
  );
}
