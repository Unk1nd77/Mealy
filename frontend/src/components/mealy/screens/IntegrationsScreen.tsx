import "../../../styles/mealy/02-form-panels.css";
import "../../../styles/mealy/03-cards.css";
import "../../../styles/mealy/04-generation.css";
import "../../../styles/mealy/07-actions.css";

import { PLAN_DAYS } from "../config";
import type { MealyCommands, MealyCore } from "../controller/useMealyCommands";
import { useI18n } from "../i18n";
import { ScreenHeader } from "../ui/ScreenHeader";
import {
  CalendarIcon,
  CartIcon,
  ChevronRightIcon,
  ClipboardIcon,
  FileIcon,
  ShareIcon,
} from "../ui/icons";

type IntegrationsCore = Pick<
  MealyCore,
  "planData" | "planRecord" | "popScreen" | "shoppingList" | "shoppingLoading"
>;
type IntegrationsCommands = Pick<
  MealyCommands,
  | "copyPlanSummary"
  | "copyShoppingItems"
  | "openCalendarExport"
  | "openShoppingListPdf"
  | "sharePlanSummary"
>;

export function IntegrationsScreen({
  commands,
  core,
}: {
  commands: IntegrationsCommands;
  core: IntegrationsCore;
}) {
  const { t } = useI18n();
  const hasSystemShare =
    typeof navigator !== "undefined" && typeof navigator.share === "function";

  const actions = [
    {
      label: t("integrations.localCalendar"),
      description: t("integrations.localCalendarDesc"),
      meta: core.planRecord?.id
        ? t("integrations.localCalendarMeta")
        : t("integrations.needsPlan"),
      icon: <CalendarIcon className="icon" />,
      onClick: commands.openCalendarExport,
      disabled: !core.planRecord?.id,
    },
    {
      label: t("integrations.systemShare"),
      description: t("integrations.systemShareDesc"),
      meta: hasSystemShare
        ? t("integrations.nativeShare")
        : t("integrations.clipboardFallback"),
      icon: <ShareIcon className="icon" />,
      onClick: () => void commands.sharePlanSummary(),
      disabled: !core.planData,
    },
    {
      label: t("integrations.notesChat"),
      description: t("integrations.notesChatDesc"),
      meta: t("integrations.plainText"),
      icon: <ClipboardIcon className="icon" />,
      onClick: () => void commands.copyPlanSummary(),
      disabled: !core.planData,
    },
    {
      label: t("integrations.shoppingPdf"),
      description: t("integrations.shoppingPdfDesc"),
      meta: t("integrations.pdfExport"),
      icon: <FileIcon className="icon" />,
      onClick: commands.openShoppingListPdf,
      disabled: !core.planRecord?.id,
    },
    {
      label: t("integrations.groceryClipboard"),
      description: t("integrations.groceryClipboardDesc"),
      meta: core.shoppingList?.length
        ? t("integrations.itemsReady", { count: core.shoppingList.length })
        : t("integrations.loadsOnDemand"),
      icon: <CartIcon className="icon" />,
      onClick: () => void commands.copyShoppingItems(),
      disabled: !core.planRecord?.id || core.shoppingLoading,
    },
  ];

  return (
    <section className="screen-card screen-card--integrations">
      <ScreenHeader
        title={t("integrations.title")}
        subtitle={t("integrations.subtitle")}
        onBack={core.popScreen}
      />
      <div className="integration-summary">
        <div>
          <span className="section-heading__eyebrow">
            {t("integrations.connectedPlan")}
          </span>
          <h2>
            {core.planData
              ? t("integrations.planDays", { count: PLAN_DAYS })
              : t("integrations.noPlan")}
          </h2>
          <p>
            {core.planData
              ? t("integrations.planReady")
              : t("integrations.planMissing")}
          </p>
        </div>
        <div className="integration-summary__metric">
          <strong>{core.planData?.days.length ?? 0}</strong>
          <span>{t("integrations.days")}</span>
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
        <strong>{t("integrations.calendarNote")}</strong>
        <p>{t("integrations.calendarNoteText")}</p>
      </div>
    </section>
  );
}
