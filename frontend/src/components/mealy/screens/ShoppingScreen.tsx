import { useState } from "react";

import { PLAN_DAYS } from "../config";
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { formatAmount } from "../formatters";
import { useI18n } from "../i18n";
import { ScreenHeader } from "../ui/ScreenHeader";
import { TimeIcon } from "../ui/icons";
import { ObservabilityPanel } from "../ui/planWidgets";

type ShoppingCore = Pick<
  MealyCore,
  | "observability"
  | "observabilityLoading"
  | "popScreen"
  | "shoppingCopied"
  | "shoppingList"
  | "shoppingLoading"
>;
type ShoppingCommands = Pick<
  MealyCommands,
  "copyShoppingItems" | "openShoppingListPdf"
>;

export function ShoppingScreen({
  commands,
  core,
}: {
  commands: ShoppingCommands;
  core: ShoppingCore;
}) {
  const { language, t } = useI18n();

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
          <button
            type="button"
            className="button button--ghost button--small"
            onClick={commands.openShoppingListPdf}
            disabled={!core.shoppingList?.length}
          >
            PDF
          </button>
          <button
            type="button"
            className="button button--ghost button--small"
            onClick={commands.copyShoppingItems}
            disabled={!core.shoppingList?.length}
          >
            {core.shoppingCopied ? t("shopping.copied") : t("shopping.copy")}
          </button>
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
                <span>{formatAmount(item, language, true)}</span>
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
