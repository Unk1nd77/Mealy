import type { MealyCore } from "./controller/useMealyCommands";
import { useText } from "./text";
import { CalendarIcon, CartIcon, SparkIcon, UserIcon } from "./ui/icons";
import type { BottomNavItem } from "./types";

type BottomNavCore = Pick<
  MealyCore,
  "currentScreen" | "isBooting" | "planData" | "resetToScreen"
>;

export function shouldShowBottomNav(
  core: Pick<BottomNavCore, "currentScreen" | "isBooting">,
) {
  return (
    !core.isBooting &&
    core.currentScreen.name !== "onboarding" &&
    core.currentScreen.name !== "generating" &&
    core.currentScreen.name !== "recipe"
  );
}

type BottomNavItemWithIcon = BottomNavItem & { icon: React.ReactNode };

export function BottomNav({ core }: { core: BottomNavCore }) {
  const { t } = useText();
  if (!shouldShowBottomNav(core)) return null;

  const items: BottomNavItemWithIcon[] = [
    {
      screen: { name: "home" },
      label: t("nav.today"),
      icon: <SparkIcon className="icon" />,
    },
    {
      screen: { name: "weekly" },
      label: t("nav.week"),
      icon: <CalendarIcon className="icon" />,
      requiresPlan: true,
    },
    {
      screen: { name: "shopping" },
      label: t("nav.shopping"),
      icon: <CartIcon className="icon" />,
      requiresPlan: true,
    },
    {
      screen: { name: "profile" },
      label: t("nav.profile"),
      icon: <UserIcon className="icon" />,
    },
  ];

  return (
    <nav className="bottom-nav" aria-label={t("nav.primary")}>
      {items.map((item) => {
        const disabled = item.requiresPlan && !core.planData;
        const isActive = core.currentScreen.name === item.screen.name;
        return (
          <button
            key={item.screen.name}
            type="button"
            className={`bottom-nav__item ${isActive ? "is-active" : ""}`}
            onClick={() => core.resetToScreen(item.screen)}
            disabled={disabled}
            aria-current={isActive ? "page" : undefined}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
