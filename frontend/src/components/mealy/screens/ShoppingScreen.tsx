import "../../../styles/mealy/02-form-actions.css"
import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/04-generation.css"
import "../../../styles/mealy/07-actions.css"

import { PLAN_DAYS } from "../config"
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { ScreenHeader } from "../ui/ScreenHeader"
import { TimeIcon } from "../ui/icons"
import { ObservabilityPanel } from "../ui/planWidgets"

type ShoppingCore = Pick<
  MealyCore,
  | "observability"
  | "observabilityLoading"
  | "popScreen"
  | "shoppingCopied"
  | "shoppingList"
  | "shoppingLoading"
>
type ShoppingCommands = Pick<MealyCommands, "copyShoppingItems" | "openShoppingListPdf">

export function ShoppingScreen({
  commands,
  core,
}: {
  commands: ShoppingCommands
  core: ShoppingCore
}) {
  return (
    <section className="screen-card">
      <ScreenHeader
        title="Shopping List"
        subtitle={`Aggregated ingredients for the current ${PLAN_DAYS}-day plan.`}
        onBack={core.popScreen}
      />
      <ObservabilityPanel
        mode="result"
        observability={core.observability}
        observabilityLoading={core.observabilityLoading}
      />
      <div className="section-toolbar">
        <div className="soft-copy">
          {core.shoppingList?.length
            ? `${core.shoppingList.length} items grouped for the week`
            : "Loading items..."}
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
            {core.shoppingCopied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
      {core.shoppingLoading ? (
        <div className="loading-card">
          <TimeIcon className="icon icon--brand" />
          <span>Building your grocery list...</span>
        </div>
      ) : null}
      {!core.shoppingLoading && core.shoppingList?.length ? (
        <div className="shopping-list">
          {core.shoppingList.map((item) => (
            <div key={`${item.name}-${item.unit}`} className="shopping-row">
              <div>
                <strong>{item.name}</strong>
                <span>{item.unit}</span>
              </div>
              <span>
                {item.amount} {item.unit}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      {!core.shoppingLoading && !core.shoppingList?.length ? (
        <div className="empty-state empty-state--compact">
          <h3>No shopping items yet</h3>
          <p>Generate a plan or reopen the screen after the current week is ready.</p>
        </div>
      ) : null}
    </section>
  )
}
