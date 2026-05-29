"""Helpers for recipe cooking instructions carried by backend recipe data."""

from __future__ import annotations

import re
from collections.abc import Iterable

_NUMBERED_STEP_RE = re.compile(
    r"(?:^|\s)(?:\d+|[ivx]+)[.)]\s*(.+?)(?=\s(?:\d+|[ivx]+)[.)]\s*|$)",
    re.IGNORECASE,
)


def clean_cooking_steps(values: Iterable[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        step = " ".join(str(value).strip().split())
        if not step:
            continue
        if not re.search(r"[.!?…]$", step):
            step = f"{step}."
        key = step.lower()
        if key not in seen:
            cleaned.append(step)
            seen.add(key)
    return cleaned


def parse_cooking_steps(description: str | None) -> list[str]:
    normalized = " ".join((description or "").strip().split())
    if not normalized:
        return []
    steps = clean_cooking_steps(match.group(1) for match in _NUMBERED_STEP_RE.finditer(normalized))
    return steps if len(steps) > 1 else []


def description_with_cooking_steps(description: str | None, steps: Iterable[str] | None) -> str:
    clean_description = (description or "").strip()
    clean_steps = clean_cooking_steps(steps)
    if not clean_steps or parse_cooking_steps(clean_description):
        return clean_description
    numbered_steps = " ".join(f"{index}. {step}" for index, step in enumerate(clean_steps, start=1))
    if not clean_description:
        return numbered_steps
    return f"{clean_description}\n\n{numbered_steps}"
