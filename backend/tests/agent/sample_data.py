"""Synthetic profile and recipe data for agentic runtime tests."""


def _valid_llm_json(total_calories: int = 2000) -> str:
    return f"""
    {{
      "daily_target_calories": 2000,
      "day": {{
        "day_number": 1,
        "total_calories": {total_calories},
        "total_protein": 140,
        "total_fat": 70,
        "total_carbs": 180,
        "meals": [
          {{
            "type": "breakfast",
            "time": "08:00",
            "recipe_id": "recipe-1",
            "title": "Breakfast bowl",
            "calories": 500,
            "protein": 35,
            "fat": 15,
            "carbs": 45
          }},
          {{
            "type": "lunch",
            "time": "13:00",
            "recipe_id": "recipe-2",
            "title": "Lunch plate",
            "calories": 700,
            "protein": 45,
            "fat": 20,
            "carbs": 60
          }},
          {{
            "type": "dinner",
            "time": "19:00",
            "recipe_id": "recipe-3",
            "title": "Dinner plate",
            "calories": 600,
            "protein": 40,
            "fat": 20,
            "carbs": 50
          }},
          {{
            "type": "snack",
            "time": "16:00",
            "recipe_id": "recipe-4",
            "title": "Snack",
            "calories": 200,
            "protein": 20,
            "fat": 15,
            "carbs": 25
          }}
        ]
      }}
    }}
    """


def _recipes() -> list[dict]:
    return [
        {
            "id": "recipe-1",
            "title": "Breakfast bowl",
            "calories": 500,
            "protein": 35,
            "fat": 15,
            "carbs": 45,
            "ingredients": [{"name": "Oats", "amount": 80, "unit": "g"}],
        },
        {
            "id": "recipe-2",
            "title": "Lunch plate",
            "calories": 700,
            "protein": 45,
            "fat": 20,
            "carbs": 60,
            "ingredients": [{"name": "Chicken", "amount": 200, "unit": "g"}],
        },
        {
            "id": "recipe-3",
            "title": "Dinner plate",
            "calories": 600,
            "protein": 40,
            "fat": 20,
            "carbs": 50,
            "ingredients": [{"name": "Rice", "amount": 150, "unit": "g"}],
        },
        {
            "id": "recipe-4",
            "title": "Snack",
            "calories": 200,
            "protein": 20,
            "fat": 15,
            "carbs": 25,
            "ingredients": [{"name": "Yogurt", "amount": 180, "unit": "g"}],
        },
    ]


def _user_profile() -> dict:
    return {
        "gender": "male",
        "age": 30,
        "weight_kg": 80,
        "height_cm": 180,
        "goal": "maintain",
        "target_calories": 2000,
        "meal_schedule": [
            {"type": "breakfast", "time": "08:00", "calories_pct": 25},
            {"type": "lunch", "time": "13:00", "calories_pct": 35},
            {"type": "dinner", "time": "19:00", "calories_pct": 30},
            {"type": "snack", "time": "16:00", "calories_pct": 10},
        ],
    }
