"""Export the normalized recipe catalog without credentials or user data."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.relational_store import load_recipes_from_rows
from app.db.session import async_session


async def export_catalog(output_path: Path) -> None:
    async with async_session() as session:
        recipes = await load_recipes_from_rows(session)
    clean_recipes = [
        {key: value for key, value in recipe.items() if key not in {"id", "embedding"}}
        for recipe in recipes
    ]
    output_path.write_text(
        json.dumps(clean_recipes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(clean_recipes)} recipes to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(export_catalog(args.output))


if __name__ == "__main__":
    main()
