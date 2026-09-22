"""Deterministic, allowlisted tools used by catalog agents."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.catalog_ingest import build_validation_report

_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)
_STOP_WORDS = {
    "для",
    "или",
    "при",
    "как",
    "это",
    "the",
    "and",
    "with",
    "recipe",
}


def _tokens(value: Any) -> set[str]:
    return {
        token.lower()
        for token in _WORD_RE.findall(str(value or ""))
        if len(token) >= 3 and token.lower() not in _STOP_WORDS
    }


def inspect_source_evidence(source_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Summarize which recipe fields are directly present in the fetched source."""
    snapshot = source_snapshot or {}
    structured = snapshot.get("structured_recipe") or {}
    return {
        "tool": "inspect_source_evidence",
        "parser": snapshot.get("parser"),
        "has_title": bool(structured.get("title") or snapshot.get("title")),
        "has_description": bool(structured.get("description") or snapshot.get("description")),
        "structured_ingredients": len(structured.get("ingredients") or []),
        "raw_ingredient_lines": len(structured.get("ingredient_lines") or []),
        "nutrition_fields": sorted((structured.get("nutrition") or {}).keys()),
        "cooking_steps": len(structured.get("cooking_steps") or []),
        "prep_time_present": structured.get("prep_time_min") is not None,
    }


def validate_recipe_draft(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the canonical schema and plausibility checks as an agent tool."""
    report = build_validation_report(payload)
    return {
        "tool": "validate_recipe_draft",
        "ok": report["ok"],
        "reason_codes": report["reason_codes"],
        "notes": report["notes"],
    }


def verify_candidate_grounding(
    payload: dict[str, Any],
    source_snapshot: dict[str, Any] | None,
    provenance: dict[str, Any] | None,
) -> dict[str, Any]:
    """Measure whether candidate content can be found in captured source evidence."""
    snapshot = source_snapshot or {}
    structured = snapshot.get("structured_recipe") or {}
    trust_level = str((provenance or {}).get("trust_level") or "unknown")
    if trust_level == "internal_curated_seed":
        return {
            "tool": "verify_candidate_grounding",
            "trust_level": trust_level,
            "support_score": 1.0,
            "supported": True,
            "reason_codes": [],
        }

    evidence_blob = json.dumps(snapshot, ensure_ascii=False).lower()
    title_tokens = _tokens(payload.get("title"))
    title_overlap = len(title_tokens & _tokens(structured.get("title") or snapshot.get("title")))
    ingredient_names = [
        str(item.get("name") or "").strip().lower()
        for item in payload.get("ingredients") or []
        if isinstance(item, dict) and item.get("name")
    ]
    supported_ingredients = sum(
        1 for name in ingredient_names if any(token in evidence_blob for token in _tokens(name))
    )
    ingredient_ratio = supported_ingredients / len(ingredient_names) if ingredient_names else 0.0
    structured_ingredients = structured.get("ingredients") or []
    supported_amounts = 0
    for ingredient in payload.get("ingredients") or []:
        if not isinstance(ingredient, dict):
            continue
        name_tokens = _tokens(ingredient.get("name"))
        amount = float(ingredient.get("amount") or 0)
        unit = str(ingredient.get("unit") or "").lower()
        for source_ingredient in structured_ingredients:
            source_tokens = _tokens(source_ingredient.get("name"))
            source_amount = float(source_ingredient.get("amount") or 0)
            source_unit = str(source_ingredient.get("unit") or "").lower()
            if (
                name_tokens & source_tokens
                and unit == source_unit
                and abs(amount - source_amount) <= max(0.1, source_amount * 0.05)
            ):
                supported_amounts += 1
                break
    amount_ratio = supported_amounts / len(ingredient_names) if ingredient_names else 0.0
    nutrition = structured.get("nutrition") or {}
    nutrition_ratio = len(nutrition) / 4
    score = round(
        min(
            1.0,
            ingredient_ratio * 0.4
            + amount_ratio * 0.25
            + nutrition_ratio * 0.25
            + bool(title_overlap) * 0.1,
        ),
        3,
    )
    reasons: list[str] = []
    if ingredient_ratio < 0.5:
        reasons.append("ingredients_weakly_supported")
    if amount_ratio < 0.5:
        reasons.append("ingredient_amounts_not_structured")
    if not nutrition:
        reasons.append("nutrition_not_structured")
    if not title_overlap:
        reasons.append("title_not_aligned")
    return {
        "tool": "verify_candidate_grounding",
        "trust_level": trust_level,
        "support_score": score,
        "supported": score >= 0.65 and amount_ratio >= 0.5,
        "ingredient_support_ratio": round(ingredient_ratio, 3),
        "ingredient_amount_support_ratio": round(amount_ratio, 3),
        "nutrition_support_ratio": round(nutrition_ratio, 3),
        "title_aligned": bool(title_overlap),
        "reason_codes": reasons,
    }
