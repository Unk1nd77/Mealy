"""Deterministic catalog agent tool checks."""

from app.core.catalog_agent_tools import verify_candidate_grounding


def test_grounding_requires_structured_ingredient_amounts():
    report = verify_candidate_grounding(
        {
            "title": "Курица с рисом",
            "ingredients": [{"name": "Курица", "amount": 200, "unit": "g"}],
        },
        {
            "title": "Курица с рисом",
            "structured_recipe": {
                "title": "Курица с рисом",
                "ingredient_lines": ["Курица"],
                "nutrition": {"calories": 500, "protein": 40, "fat": 10, "carbs": 60},
            },
        },
        {"trust_level": "trusted_editorial"},
    )

    assert report["ingredient_support_ratio"] == 1.0
    assert report["ingredient_amount_support_ratio"] == 0.0
    assert report["supported"] is False
    assert "ingredient_amounts_not_structured" in report["reason_codes"]


def test_grounding_accepts_matching_structured_amounts():
    report = verify_candidate_grounding(
        {
            "title": "Курица с рисом",
            "ingredients": [{"name": "Курица", "amount": 200, "unit": "g"}],
        },
        {
            "title": "Курица с рисом",
            "structured_recipe": {
                "title": "Курица с рисом",
                "ingredients": [{"name": "Курица", "amount": 200, "unit": "g"}],
                "nutrition": {"calories": 500, "protein": 40, "fat": 10, "carbs": 60},
            },
        },
        {"trust_level": "trusted_editorial"},
    )

    assert report["ingredient_amount_support_ratio"] == 1.0
    assert report["supported"] is True
