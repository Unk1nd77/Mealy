"""Meal compatibility policies observed in existing generation and retrieval paths.

Policies are explicit because changing snack aliases or universal recipes is a
behaviour change, not deduplication. Retrieval receives an already inferred type.
"""

from typing import Literal

CompatibilityPolicy = Literal["generation", "retrieval"]


def normalize_meal_type(value: str | None) -> set[str]:
    if not value:
        return set()
    return {chunk.strip().lower() for chunk in value.replace(",", "/").split("/") if chunk.strip()}


def slot_compatible_types(
    slot_type: str, *, policy: CompatibilityPolicy = "generation"
) -> set[str]:
    if policy == "retrieval":
        return {slot_type, "universal"} | (
            {"lunch/dinner"} if slot_type in {"lunch", "dinner"} else set()
        )
    if slot_type in {"lunch", "dinner"}:
        return {slot_type, "lunch/dinner", "universal"}
    if slot_type in {"snack", "second_snack"}:
        return {"snack", "second_snack"}
    return {slot_type}


def recipe_type_matches(
    recipe_type: str | None,
    slot_type: str,
    *,
    policy: CompatibilityPolicy = "generation",
    allow_universal: bool = False,
) -> bool:
    # Retrieval historically compares the inferred string, not split tokens.
    types = {recipe_type} if policy == "retrieval" else normalize_meal_type(recipe_type)
    return bool(
        types & slot_compatible_types(slot_type, policy=policy)
        or (allow_universal and "universal" in types)
    )


def recipe_matches_slot(
    recipe: dict, slot_type: str, *, policy: CompatibilityPolicy = "generation"
) -> bool:
    return recipe_type_matches(recipe.get("meal_type"), slot_type, policy=policy)
