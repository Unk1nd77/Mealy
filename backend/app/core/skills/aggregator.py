"""Агрегация списка покупок из плана питания."""

from __future__ import annotations

from collections import defaultdict
import re

_UNIT_ALIASES = {
    "g": "g",
    "gr": "g",
    "gram": "g",
    "grams": "g",
    "г": "g",
    "гр": "g",
    "грамм": "g",
    "грамма": "g",
    "граммов": "g",
    "kg": "kg",
    "кг": "kg",
    "ml": "ml",
    "мл": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "л": "l",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "ст. л.": "tbsp",
    "ст л": "tbsp",
    "столовая ложка": "tbsp",
    "столовые ложки": "tbsp",
    "столовых ложек": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "ч. л.": "tsp",
    "ч л": "tsp",
    "чайная ложка": "tsp",
    "чайные ложки": "tsp",
    "чайных ложек": "tsp",
    "piece": "piece",
    "pieces": "piece",
    "pc": "piece",
    "pcs": "piece",
    "шт": "piece",
    "штука": "piece",
    "штуки": "piece",
    "штук": "piece",
    "slice": "piece",
    "ломтик": "piece",
    "ломтика": "piece",
}

_LIQUID_NAME_RE = re.compile(
    r"вода|water|молоко|milk|кефир|йогурт питьевой|бульон|broth|сок|juice|"
    r"соевый соус|soy sauce|соус|sauce|уксус|vinegar|масло|oil",
    re.IGNORECASE,
)

_TABLESPOON_GRAMS_BY_NAME: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"сахар|sugar", re.IGNORECASE), 12.5),
    (re.compile(r"мука|flour", re.IGNORECASE), 8.0),
    (re.compile(r"соль|salt", re.IGNORECASE), 18.0),
    (re.compile(r"мед|honey", re.IGNORECASE), 21.0),
    (re.compile(r"какао|cocoa", re.IGNORECASE), 7.0),
]

_PIECE_GRAMS_BY_NAME: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"яйц|egg", re.IGNORECASE), 55.0),
    (re.compile(r"лимон|lemon", re.IGNORECASE), 90.0),
    (re.compile(r"томат|помидор|tomato", re.IGNORECASE), 120.0),
    (re.compile(r"банан|banana", re.IGNORECASE), 120.0),
    (re.compile(r"авокадо|avocado", re.IGNORECASE), 170.0),
    (re.compile(r"яблок|apple", re.IGNORECASE), 170.0),
    (re.compile(r"лук(?!.*зел)|onion", re.IGNORECASE), 100.0),
    (re.compile(r"перец|pepper", re.IGNORECASE), 160.0),
    (re.compile(r"огур|cucumber", re.IGNORECASE), 120.0),
    (re.compile(r"кабач|zucchini", re.IGNORECASE), 250.0),
    (re.compile(r"баклажан|eggplant", re.IGNORECASE), 250.0),
    (re.compile(r"ломтик|slice|хлеб|bread", re.IGNORECASE), 30.0),
]


def _display_name(name: str) -> str:
    return name[0].upper() + name[1:] if name else name


def _normalize_name(name: object) -> str:
    return " ".join(str(name or "").strip().lower().split())


def _normalize_unit(unit: object) -> str:
    return _UNIT_ALIASES.get(" ".join(str(unit or "g").strip().lower().split()), "g")


def _tablespoon_grams(name: str) -> float:
    for pattern, grams in _TABLESPOON_GRAMS_BY_NAME:
        if pattern.search(name):
            return grams
    return 15.0


def _piece_grams(name: str) -> float:
    for pattern, grams in _PIECE_GRAMS_BY_NAME:
        if pattern.search(name):
            return grams
    return 100.0


def _normalize_amount(name: str, amount: float, unit: str) -> tuple[float, str]:
    if unit == "kg":
        return amount * 1000, "g"
    if unit == "l":
        return amount * 1000, "ml"
    if unit in {"g", "ml"}:
        return amount, unit
    if unit == "tbsp":
        if _LIQUID_NAME_RE.search(name):
            return amount * 15, "ml"
        return amount * _tablespoon_grams(name), "g"
    if unit == "tsp":
        if _LIQUID_NAME_RE.search(name):
            return amount * 5, "ml"
        return amount * (_tablespoon_grams(name) / 3), "g"
    if unit == "piece":
        return amount * _piece_grams(name), "g"
    return amount, "g"


def aggregate_shopping_list(plan_data: dict) -> list[dict]:
    """Агрегирует ингредиенты из всех дней плана в единый список покупок.

    Суммирует одинаковые ингредиенты после приведения единиц к граммам/мл.
    """
    totals: dict[tuple[str, str], float] = defaultdict(float)

    for day in plan_data.get("days", []):
        for meal in day.get("meals", []):
            for ing in meal.get("ingredients_summary", []):
                name = _normalize_name(ing.get("name"))
                if not name:
                    continue
                amount, unit = _normalize_amount(
                    name,
                    float(ing.get("amount", 0) or 0),
                    _normalize_unit(ing.get("unit")),
                )
                totals[(name, unit)] += amount

    result = []
    for (name, unit), amount in sorted(totals.items()):
        result.append(
            {
                "name": _display_name(name),
                "amount": round(amount, 1),
                "unit": unit,
            }
        )

    return result
