import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

export type Language = "en" | "ru"

const LANGUAGE_STORAGE_KEY = "mealy/language/v1"

const en = {
  "app.updated": "Updated",
  "app.attention": "Attention",
  "error.loadTitle": "Could not load data",
  "error.loadHint": "Check the backend or try again.",
  "nav.primary": "Primary",
  "nav.today": "Today",
  "nav.week": "Week",
  "nav.profile": "Profile",
  "week.regenerate": "Regenerate week",
  "week.calendar": "Calendar",
  "week.more": "More",
  "week.daysLabel": "Plan days",
  "week.day": "Day",
  "week.fromTarget": "from target",
  "week.protein": "Protein",
  "week.macros": "Macros",
  "language.toggle": "Switch language",
  "screen.back": "Go back",
  "onboarding.brandSub": "Nutrition plan setup",
  "onboarding.mode.create": "Create",
  "onboarding.mode.signIn": "Sign in",
  "onboarding.setup": "Setup",
  "onboarding.title": "Build your 7-day plan",
  "onboarding.copy":
    "Add the essentials once. Mealy uses them to prepare meals, nutrition balance, and weekly rhythm.",
  "onboarding.account": "Account",
  "onboarding.basics": "Start with the basics",
  "onboarding.savedProfile": "Use your saved profile",
  "onboarding.email": "Email",
  "onboarding.password": "Password",
  "onboarding.emailPlaceholder": "you@example.com",
  "onboarding.passwordPlaceholder": "At least 6 characters",
  "onboarding.bodyMetrics": "Body metrics",
  "onboarding.cleanInputs": "Give the planner clean inputs",
  "onboarding.age": "Age",
  "onboarding.weight": "Weight, kg",
  "onboarding.height": "Height, cm",
  "onboarding.gender": "Gender",
  "onboarding.genderFemale": "Female",
  "onboarding.genderMale": "Male",
  "onboarding.goalRhythm": "Goal and rhythm",
  "onboarding.weekTone": "Shape the tone of the week",
  "onboarding.activity": "Activity",
  "onboarding.goal": "Goal",
  "onboarding.preferences": "Preferences",
  "onboarding.lowActivity": "Low activity",
  "onboarding.lightActivity": "Light activity",
  "onboarding.moderateActivity": "Moderate activity",
  "onboarding.highActivity": "High activity",
  "onboarding.veryActive": "Very active",
  "onboarding.fatLoss": "Fat loss",
  "onboarding.maintain": "Maintain",
  "onboarding.gainMuscle": "Gain muscle",
  "onboarding.restrictionsReview": "Restrictions and review",
  "onboarding.guardrails": "Lock your guardrails",
  "onboarding.allergies": "Allergies",
  "onboarding.disliked": "Disliked ingredients",
  "onboarding.conditions": "Conditions",
  "onboarding.back": "Back",
  "onboarding.continue": "Continue",
  "onboarding.starting": "Starting...",
  "onboarding.generate": "Generate my week",
  "empty.todaySubtitle": "Your daily nutrition hub appears here after onboarding.",
  "empty.noWeek": "No active week",
  "empty.title": "Generate your first 7-day plan",
  "empty.copy":
    "Mealy will prepare daily meals, week view, recipes, and plan actions from your profile.",
  "empty.previewToday": "Next meal and daily progress",
  "empty.previewWeek": "Seven planned days",
  "empty.actions": "Actions",
  "empty.previewActions": "Shopping, calendar, and sharing",
  "empty.start": "Start onboarding",
  "empty.generate": "Generate my first week",
  "profile.title": "Profile",
  "profile.subtitle": "Edit the nutrition inputs that shape your next generated week.",
  "profile.body": "Body",
  "profile.coreMeasurements": "Core measurements",
  "profile.restrictions": "Restrictions",
  "profile.foodGuardrails": "Food guardrails",
  "profile.save": "Save profile",
  "profile.saving": "Saving...",
  "profile.signOut": "Sign out",
} as const

const ru: Record<keyof typeof en, string> = {
  "app.updated": "Обновлено",
  "app.attention": "Внимание",
  "error.loadTitle": "Не удалось загрузить данные",
  "error.loadHint": "Проверь backend или попробуй ещё раз.",
  "nav.primary": "Основная навигация",
  "nav.today": "Сегодня",
  "nav.week": "Неделя",
  "nav.profile": "Профиль",
  "week.regenerate": "Пересобрать неделю",
  "week.calendar": "Календарь",
  "week.more": "Ещё",
  "week.daysLabel": "Дни плана",
  "week.day": "День",
  "week.fromTarget": "от цели",
  "week.protein": "Белок",
  "week.macros": "КБЖУ",
  "language.toggle": "Сменить язык",
  "screen.back": "Назад",
  "onboarding.brandSub": "Настройка плана питания",
  "onboarding.mode.create": "Создать",
  "onboarding.mode.signIn": "Войти",
  "onboarding.setup": "Настройка",
  "onboarding.title": "Соберите план на 7 дней",
  "onboarding.copy":
    "Заполните основные данные один раз. Mealy подготовит блюда, баланс питания и недельный ритм.",
  "onboarding.account": "Аккаунт",
  "onboarding.basics": "Начните с основного",
  "onboarding.savedProfile": "Войдите в сохранённый профиль",
  "onboarding.email": "Email",
  "onboarding.password": "Пароль",
  "onboarding.emailPlaceholder": "you@example.com",
  "onboarding.passwordPlaceholder": "Минимум 6 символов",
  "onboarding.bodyMetrics": "Параметры тела",
  "onboarding.cleanInputs": "Дайте планировщику точные данные",
  "onboarding.age": "Возраст",
  "onboarding.weight": "Вес, кг",
  "onboarding.height": "Рост, см",
  "onboarding.gender": "Пол",
  "onboarding.genderFemale": "Женский",
  "onboarding.genderMale": "Мужской",
  "onboarding.goalRhythm": "Цель и ритм",
  "onboarding.weekTone": "Настройте характер недели",
  "onboarding.activity": "Активность",
  "onboarding.goal": "Цель",
  "onboarding.preferences": "Предпочтения",
  "onboarding.lowActivity": "Низкая активность",
  "onboarding.lightActivity": "Лёгкая активность",
  "onboarding.moderateActivity": "Средняя активность",
  "onboarding.highActivity": "Высокая активность",
  "onboarding.veryActive": "Очень высокая",
  "onboarding.fatLoss": "Снижение веса",
  "onboarding.maintain": "Поддержание",
  "onboarding.gainMuscle": "Набор мышц",
  "onboarding.restrictionsReview": "Ограничения и проверка",
  "onboarding.guardrails": "Зафиксируйте важные ограничения",
  "onboarding.allergies": "Аллергии",
  "onboarding.disliked": "Нелюбимые ингредиенты",
  "onboarding.conditions": "Состояния",
  "onboarding.back": "Назад",
  "onboarding.continue": "Продолжить",
  "onboarding.starting": "Запускаем...",
  "onboarding.generate": "Сгенерировать неделю",
  "empty.todaySubtitle": "Здесь появится дневной центр питания после онбординга.",
  "empty.noWeek": "Нет активной недели",
  "empty.title": "Сгенерируйте первый план на 7 дней",
  "empty.copy": "Mealy подготовит блюда, неделю, рецепты и действия плана на основе профиля.",
  "empty.previewToday": "Ближайший приём пищи и прогресс дня",
  "empty.previewWeek": "Семь запланированных дней",
  "empty.actions": "Действия",
  "empty.previewActions": "Покупки, календарь и отправка",
  "empty.start": "Начать онбординг",
  "empty.generate": "Сгенерировать первую неделю",
  "profile.title": "Профиль",
  "profile.subtitle": "Измените параметры питания для следующей сгенерированной недели.",
  "profile.body": "Тело",
  "profile.coreMeasurements": "Основные параметры",
  "profile.restrictions": "Ограничения",
  "profile.foodGuardrails": "Пищевые правила",
  "profile.save": "Сохранить профиль",
  "profile.saving": "Сохраняем...",
  "profile.signOut": "Выйти",
}

export type TranslationKey = keyof typeof en

type I18nContextValue = {
  language: Language
  toggleLanguage: () => void
  t: (key: TranslationKey) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

function readInitialLanguage(): Language {
  if (typeof window === "undefined") return "en"
  return window.localStorage.getItem(LANGUAGE_STORAGE_KEY) === "ru" ? "ru" : "en"
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(readInitialLanguage)

  useEffect(() => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
    document.documentElement.lang = language
  }, [language])

  const value = useMemo<I18nContextValue>(() => {
    const messages = language === "ru" ? ru : en
    return {
      language,
      toggleLanguage: () => setLanguage((current) => (current === "en" ? "ru" : "en")),
      t: (key) => messages[key],
    }
  }, [language])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const value = useContext(I18nContext)
  if (!value) throw new Error("useI18n must be used inside I18nProvider")
  return value
}

export function LanguageToggle() {
  const { language, toggleLanguage, t } = useI18n()

  return (
    <button
      type="button"
      className="language-toggle"
      onClick={toggleLanguage}
      aria-label={t("language.toggle")}
    >
      <span className={language === "en" ? "is-active" : ""}>EN</span>
      <span className={language === "ru" ? "is-active" : ""}>RU</span>
    </button>
  )
}
