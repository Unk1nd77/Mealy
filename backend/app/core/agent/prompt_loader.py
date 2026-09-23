"""Shared template loading; legacy and agentic prompts retain their current content."""

from pathlib import Path

import yaml
from jinja2 import Template

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt() -> dict[str, Template]:
    with (PROMPTS_DIR / "meal_plan.yml").open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return {key: Template(val) for key, val in raw.items()}
