import type { MealItem, ShoppingItem } from "./types";

export type MockMealSeed = Omit<
  MealItem,
  "recipe_id" | "ingredients_summary"
> & {
  recipe_id: string;
  description: string;
  ingredients: ShoppingItem[];
  tags: string[];
};

export const mealSeeds: MockMealSeed[] = [
  {
    type: "breakfast",
    time: "08:00",
    recipe_id: "mock-greek-yogurt-bowl",
    title: "Йогуртовая чаша с ягодами",
    calories: 430,
    protein: 34,
    fat: 12,
    carbs: 48,
    description:
      "Греческий йогурт, черника, овсяные хлопья и семена чиа — сытный завтрак с высоким содержанием белка.",
    ingredients: [
      { name: "Греческий йогурт", amount: 220, unit: "g" },
      { name: "Черника", amount: 90, unit: "g" },
      { name: "Овсяные хлопья", amount: 45, unit: "g" },
      { name: "Семена чиа", amount: 10, unit: "g" },
    ],
    tags: ["завтрак", "высокий белок", "быстро"],
  },
  {
    type: "lunch",
    time: "12:45",
    recipe_id: "mock-salmon-rice-plate",
    title: "Рис с лососем",
    calories: 690,
    protein: 44,
    fat: 25,
    carbs: 68,
    description:
      "Запечённый лосось с рисом, огурцом, авокадо и лимонно-травяной заправкой.",
    ingredients: [
      { name: "Филе лосося", amount: 170, unit: "g" },
      { name: "Отварной рис", amount: 180, unit: "g" },
      { name: "Авокадо", amount: 70, unit: "g" },
      { name: "Огурец", amount: 100, unit: "g" },
    ],
    tags: ["обед", "омега-3", "баланс"],
  },
  {
    type: "snack",
    time: "16:30",
    recipe_id: "mock-apple-almond-snack",
    title: "Яблоко с миндалём",
    calories: 260,
    protein: 8,
    fat: 15,
    carbs: 30,
    description: "Простой перекус: свежее яблоко, миндаль и творог.",
    ingredients: [
      { name: "Яблоко", amount: 1, unit: "pc" },
      { name: "Миндаль", amount: 22, unit: "g" },
      { name: "Творог", amount: 100, unit: "g" },
    ],
    tags: ["перекус", "просто"],
  },
  {
    type: "dinner",
    time: "19:30",
    recipe_id: "mock-chicken-vegetable-tray",
    title: "Запечённая курица с овощами",
    calories: 650,
    protein: 52,
    fat: 22,
    carbs: 54,
    description:
      "Куриная грудка, картофель, морковь и зелень — всё на одном противне.",
    ingredients: [
      { name: "Куриная грудка", amount: 190, unit: "g" },
      { name: "Картофель", amount: 220, unit: "g" },
      { name: "Морковь", amount: 120, unit: "g" },
      { name: "Оливковое масло", amount: 12, unit: "ml" },
    ],
    tags: ["ужин", "заготовка"],
  },
  {
    type: "breakfast",
    time: "08:15",
    recipe_id: "mock-spinach-omelette",
    title: "Омлет со шпинатом",
    calories: 470,
    protein: 35,
    fat: 27,
    carbs: 24,
    description:
      "Яичный омлет со шпинатом, фетой, томатом и цельнозерновым тостом.",
    ingredients: [
      { name: "Яйца", amount: 3, unit: "pcs" },
      { name: "Шпинат", amount: 80, unit: "g" },
      { name: "Фета", amount: 35, unit: "g" },
      { name: "Цельнозерновой тост", amount: 1, unit: "pc" },
    ],
    tags: ["завтрак", "сытный"],
  },
  {
    type: "lunch",
    time: "13:00",
    recipe_id: "mock-turkey-quinoa-bowl",
    title: "Индейка с киноа",
    calories: 710,
    protein: 50,
    fat: 20,
    carbs: 78,
    description:
      "Нежирный фарш из индейки, киноа, черри-помидоры, зелень и йогуртовый соус.",
    ingredients: [
      { name: "Фарш из индейки", amount: 180, unit: "g" },
      { name: "Киноа", amount: 170, unit: "g" },
      { name: "Черри-помидоры", amount: 120, unit: "g" },
      { name: "Греческий йогурт", amount: 60, unit: "g" },
    ],
    tags: ["обед", "высокий белок"],
  },
  {
    type: "snack",
    time: "16:00",
    recipe_id: "mock-hummus-crunch",
    title: "Хумус с овощами",
    calories: 310,
    protein: 11,
    fat: 14,
    carbs: 38,
    description: "Хумус с хрустящими овощами и ржаными хлебцами.",
    ingredients: [
      { name: "Хумус", amount: 80, unit: "g" },
      { name: "Болгарский перец", amount: 100, unit: "g" },
      { name: "Морковь", amount: 100, unit: "g" },
      { name: "Ржаные хлебцы", amount: 35, unit: "g" },
    ],
    tags: ["перекус", "клетчатка"],
  },
  {
    type: "dinner",
    time: "19:15",
    recipe_id: "mock-beef-noodle-stir",
    title: "Говядина с лапшой",
    calories: 720,
    protein: 47,
    fat: 24,
    carbs: 78,
    description: "Полоски говядины, лапша, брокколи и имбирно-соевый соус.",
    ingredients: [
      { name: "Нежирная говядина", amount: 170, unit: "g" },
      { name: "Лапша", amount: 190, unit: "g" },
      { name: "Брокколи", amount: 150, unit: "g" },
      { name: "Соевый соус", amount: 20, unit: "ml" },
    ],
    tags: ["ужин", "тёплое"],
  },
];

export const dayIndexes = [
  [0, 1, 2, 3],
  [4, 5, 6, 7],
  [0, 5, 2, 7],
  [4, 1, 6, 3],
  [0, 5, 6, 3],
  [4, 1, 2, 7],
  [0, 1, 6, 3],
];
