from app.core.day_plan_repair import repair_day_plan


def _recipe(
    recipe_id: str,
    title: str,
    base_recipe_id: str | None = None,
    meal_type: str = "snack",
) -> dict:
    recipe = {
        "id": recipe_id,
        "title": title,
        "meal_type": meal_type,
        "calories": 300,
        "protein": 25,
        "fat": 8,
        "carbs": 32,
        "ingredients": [],
    }
    if base_recipe_id is not None:
        recipe["base_recipe_id"] = base_recipe_id
    return recipe


def test_repair_day_plan_replaces_cross_day_repeat_even_when_day_is_valid():
    schedule = [{"type": "snack", "time": "16:00", "calories_pct": 100}]
    day_plan = {
        "day_number": 2,
        "total_calories": 300,
        "total_protein": 25,
        "total_fat": 8,
        "total_carbs": 32,
        "meals": [
            {
                "type": "snack",
                "time": "16:00",
                "recipe_id": "banana-cottage-cheese",
                "title": "Банановый коктейль с творогом",
                "calories": 300,
                "protein": 25,
                "fat": 8,
                "carbs": 32,
                "ingredients_summary": [],
            }
        ],
    }

    repaired_day, applied_fixes, repair_error = repair_day_plan(
        day_plan=day_plan,
        recipes=[
            _recipe("banana-cottage-cheese", "Банановый коктейль с творогом"),
            _recipe("apple-yogurt", "Яблочный йогурт"),
        ],
        meal_schedule=schedule,
        target_calories=300,
        avoid_recipe_base_ids={"banana-cottage-cheese"},
    )

    assert repair_error is None
    assert repaired_day is not None
    assert repaired_day["meals"][0]["recipe_id"] == "apple-yogurt"
    assert applied_fixes == ["snack: banana-cottage-cheese -> apple-yogurt"]


def test_repair_day_plan_detects_repeat_by_catalog_base_recipe_id():
    schedule = [{"type": "snack", "time": "16:00", "calories_pct": 100}]
    day_plan = {
        "day_number": 2,
        "total_calories": 300,
        "total_protein": 25,
        "total_fat": 8,
        "total_carbs": 32,
        "meals": [
            {
                "type": "snack",
                "time": "16:00",
                "recipe_id": "banana-cottage-cheese::portion-300",
                "title": "Банановый коктейль с творогом",
                "calories": 300,
                "protein": 25,
                "fat": 8,
                "carbs": 32,
                "ingredients_summary": [],
            }
        ],
    }

    repaired_day, applied_fixes, repair_error = repair_day_plan(
        day_plan=day_plan,
        recipes=[
            _recipe(
                "banana-cottage-cheese::portion-300",
                "Банановый коктейль с творогом",
                base_recipe_id="banana-cottage-cheese",
            ),
            _recipe(
                "apple-yogurt::portion-300",
                "Яблочный йогурт",
                base_recipe_id="apple-yogurt",
            ),
        ],
        meal_schedule=schedule,
        target_calories=300,
        avoid_recipe_base_ids={"banana-cottage-cheese"},
    )

    assert repair_error is None
    assert repaired_day is not None
    assert repaired_day["meals"][0]["recipe_id"] == "apple-yogurt::portion-300"
    assert applied_fixes == [
        "snack: banana-cottage-cheese::portion-300 -> apple-yogurt::portion-300"
    ]


def test_repair_day_plan_replaces_recipe_that_does_not_match_slot():
    schedule = [{"type": "snack", "time": "16:00", "calories_pct": 100}]
    day_plan = {
        "day_number": 6,
        "total_calories": 300,
        "total_protein": 25,
        "total_fat": 8,
        "total_carbs": 32,
        "meals": [
            {
                "type": "snack",
                "time": "16:00",
                "recipe_id": "chicken-soup",
                "title": "Куриный суп с лапшой",
                "calories": 300,
                "protein": 25,
                "fat": 8,
                "carbs": 32,
                "ingredients_summary": [],
            }
        ],
    }

    repaired_day, applied_fixes, repair_error = repair_day_plan(
        day_plan=day_plan,
        recipes=[
            _recipe("chicken-soup", "Куриный суп с лапшой", meal_type="lunch"),
            _recipe("apple-yogurt", "Яблочный йогурт"),
        ],
        meal_schedule=schedule,
        target_calories=300,
    )

    assert repair_error is None
    assert repaired_day is not None
    assert repaired_day["meals"][0]["recipe_id"] == "apple-yogurt"
    assert applied_fixes == ["snack: chicken-soup -> apple-yogurt"]
