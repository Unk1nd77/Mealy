import "../../../styles/mealy/02-form-panels.css"
import "../../../styles/mealy/03-cards.css"
import "../../../styles/mealy/04-generation.css"
import "../../../styles/mealy/07-actions.css"

import { PLAN_DAYS } from "../config"
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands"
import { ScreenHeader } from "../ui/ScreenHeader"
import {
  CalendarIcon,
  CartIcon,
  ChevronRightIcon,
  ClipboardIcon,
  FileIcon,
  ShareIcon,
} from "../ui/icons"

type IntegrationsCore = Pick<
  MealyCore,
  "planData" | "planRecord" | "popScreen" | "shoppingList" | "shoppingLoading"
>
type IntegrationsCommands = Pick<
  MealyCommands,
  | "copyPlanSummary"
  | "copyShoppingItems"
  | "openCalendarExport"
  | "openShoppingListPdf"
  | "sharePlanSummary"
>

export function IntegrationsScreen({
  commands,
  core,
}: {
  commands: IntegrationsCommands
  core: IntegrationsCore
}) {
  const hasSystemShare = typeof navigator !== "undefined" && typeof navigator.share === "function"
  const actions = [
    {
      label: "Local Calendar",
      description: "Download an iCalendar file with every meal time.",
      meta: core.planRecord?.id ? "ICS export" : "Needs an active plan",
      icon: <CalendarIcon className="icon" />,
      onClick: commands.openCalendarExport,
      disabled: !core.planRecord?.id,
    },
    {
      label: "System Share",
      description: "Send the week summary through the mobile share sheet.",
      meta: hasSystemShare ? "Native share sheet" : "Clipboard fallback",
      icon: <ShareIcon className="icon" />,
      onClick: () => void commands.sharePlanSummary(),
      disabled: !core.planData,
    },
    {
      label: "Notes and Chat",
      description: "Copy a readable day-by-day summary.",
      meta: "Plain text",
      icon: <ClipboardIcon className="icon" />,
      onClick: () => void commands.copyPlanSummary(),
      disabled: !core.planData,
    },
    {
      label: "Shopping PDF",
      description: "Save a printable grocery list.",
      meta: "PDF export",
      icon: <FileIcon className="icon" />,
      onClick: commands.openShoppingListPdf,
      disabled: !core.planRecord?.id,
    },
    {
      label: "Grocery Clipboard",
      description: "Copy the aggregated shopping list.",
      meta: core.shoppingList?.length
        ? `${core.shoppingList.length} items ready`
        : "Loads on demand",
      icon: <CartIcon className="icon" />,
      onClick: () => void commands.copyShoppingItems(),
      disabled: !core.planRecord?.id || core.shoppingLoading,
    },
  ]

  return (
    <section className="screen-card screen-card--integrations">
      <ScreenHeader
        title="Integrations"
        subtitle="Local-first exports for the systems you already use on your phone."
        onBack={core.popScreen}
      />
      <div className="integration-summary">
        <div>
          <span className="section-heading__eyebrow">Connected plan</span>
          <h2>{core.planData ? `${PLAN_DAYS}-day meal plan` : "No active plan"}</h2>
          <p>
            {core.planData
              ? "Calendar, share, file, and clipboard actions use the same saved plan."
              : "Generate a plan first, then exports will become available here."}
          </p>
        </div>
        <div className="integration-summary__metric">
          <strong>{core.planData?.days.length ?? 0}</strong>
          <span>days</span>
        </div>
      </div>
      <div className="integration-list">
        {actions.map((action) => (
          <button
            key={action.label}
            type="button"
            className="integration-action"
            onClick={action.onClick}
            disabled={action.disabled}
          >
            <span className="action-card__icon">{action.icon}</span>
            <div>
              <strong>{action.label}</strong>
              <p>{action.description}</p>
              <span>{action.meta}</span>
            </div>
            <ChevronRightIcon className="icon action-card__chevron" />
          </button>
        ))}
      </div>
      <div className="disclaimer-banner">
        <strong>Local calendar note</strong>
        <p>
          Browsers cannot silently write into a local calendar. Mealy exports a standard `.ics`
          file, and the calendar app handles the import confirmation.
        </p>
      </div>
    </section>
  )
}
