"""Session readiness, exact-draft hashes and trace argument redaction."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

_PROFILE_FIELDS = {
    "target_calories",
    "meal_schedule",
    "allergies",
    "disliked_ingredients",
    "diseases",
    "preferences",
    "goal",
    "user_id",
    "id",
    "gender",
    "age",
    "weight_kg",
    "height_cm",
    "email",
}


@dataclass
class AgentSessionState:
    """Tracks mandatory steps completed during one Agentic Loop session."""

    profile_fetched: bool = False
    recipes_fetched: bool = False
    last_validated_hash: str | None = None  # sha256 of last successfully validated plan JSON

    def ready_for_final(self) -> bool:
        return (
            self.profile_fetched and self.recipes_fetched and self.last_validated_hash is not None
        )

    def missing_steps(self) -> list[str]:
        missing = []
        if not self.profile_fetched:
            missing.append("get_user_profile")
        if not self.recipes_fetched:
            missing.append("search_recipes")
        if self.last_validated_hash is None:
            missing.append("validate_day_plan")
        return missing


def _compute_plan_hash(plan_data: Any) -> str:
    canonical = json.dumps(plan_data, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _build_args_summary(args: dict) -> str:
    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items() if k not in _PROFILE_FIELDS}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return str(redact(args))[:200]
