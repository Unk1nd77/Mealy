"""Generate new recipes via LLM catalog agent and admit them to the DB.

Usage (inside backend container):
    uv run python scripts/generate_catalog_batch.py --count 100

The script sends seed prompts to the research+verification LLM pipeline.
Each seed describes a recipe category/style; the LLM produces a full
structured recipe which is then validated and admitted.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.catalog_agent_runtime import run_catalog_agent_pipeline
from app.core.catalog_agents import build_research_agent, build_verification_agent
from app.db.models import Recipe
from app.db.session import async_session, engine

# Seed prompts — each becomes one LLM call to generate a unique recipe.
# Covers all meal types with emphasis on higher-calorie options to support
# users with targets above 2000 kcal/day.
SEED_PROMPTS = [
    # ── BREAKFAST (завтрак) ──────────────────────────────────────────────
    "Высококалорийная овсяная каша с арахисовым маслом, бананом и орехами пекан. Завтрак, ~550 ккал.",
    "Омлет с тремя яйцами, сыром чеддер, шпинатом и помидорами. Завтрак, ~420 ккал.",
    "Французские тосты из цельнозернового хлеба с яйцом, молоком и корицей. Завтрак, ~480 ккал.",
    "Творожные сырники со сметаной и вареньем. Завтрак, ~460 ккал.",
    "Гречневая каша с молоком и сливочным маслом. Завтрак, ~400 ккал.",
    "Яичница-болтунья с беконом и тостом. Завтрак, ~520 ккал.",
    "Блины на кефире с мёдом и сметаной. Завтрак, ~500 ккал.",
    "Мюсли с греческим йогуртом, мёдом и свежими ягодами. Завтрак, ~380 ккал.",
    "Авокадо-тост с яйцом пашот и микрозеленью. Завтрак, ~440 ккал.",
    "Манная каша на молоке со сливочным маслом и джемом. Завтрак, ~420 ккал.",
    "Рисовая каша на молоке с изюмом и корицей. Завтрак, ~390 ккал.",
    "Панкейки с кленовым сиропом и свежей клубникой. Завтрак, ~510 ккал.",
    "Яйца бенедикт с ветчиной и голландским соусом. Завтрак, ~560 ккал.",
    "Творог с мёдом, грецкими орехами и бананом. Завтрак, ~430 ккал.",
    "Каша из полбы с тыквой и корицей. Завтрак, ~370 ккал.",

    # ── LUNCH (обед) ────────────────────────────────────────────────────
    "Борщ со свининой, сметаной и чёрным хлебом. Обед, ~520 ккал.",
    "Куриный суп с лапшой и овощами. Обед, ~380 ккал.",
    "Плов с бараниной, морковью и луком. Обед, ~620 ккал.",
    "Котлеты по-киевски с картофельным пюре. Обед, ~680 ккал.",
    "Солянка мясная сборная со сметаной. Обед, ~450 ккал.",
    "Гречка с тушёной говядиной и луком. Обед, ~580 ккал.",
    "Рис с курицей карри и кокосовым молоком. Обед, ~560 ккал.",
    "Макароны с мясным соусом болоньезе. Обед, ~600 ккал.",
    "Щи из свежей капусты со свининой. Обед, ~420 ккал.",
    "Лазанья с говяжьим фаршем и соусом бешамель. Обед, ~650 ккал.",
    "Пельмени домашние со сметаной. Обед, ~580 ккал.",
    "Рассольник с перловкой и говядиной. Обед, ~400 ккал.",
    "Тефтели в томатном соусе с рисом. Обед, ~520 ккал.",
    "Куриная грудка с гречкой и тушёными овощами. Обед, ~490 ккал.",
    "Суп-пюре из тыквы со сливками и гренками. Обед, ~360 ккал.",

    # ── DINNER (ужин) ────────────────────────────────────────────────────
    "Запечённый лосось с лимоном, спаржей и картофелем. Ужин, ~580 ккал.",
    "Стейк из говядины с жареным картофелем и салатом. Ужин, ~720 ккал.",
    "Куриные бёдра в духовке с розмарином и чесноком. Ужин, ~520 ккал.",
    "Паста карбонара с беконом, яйцом и пармезаном. Ужин, ~640 ккал.",
    "Свиные рёбра барбекю с кукурузой и капустным салатом. Ужин, ~750 ккал.",
    "Треска запечённая с овощами и оливковым маслом. Ужин, ~380 ккал.",
    "Говяжий стейк с соусом из красного вина и пюре. Ужин, ~680 ккал.",
    "Курица в сливочном соусе с грибами и рисом. Ужин, ~560 ккал.",
    "Запечённая утка с яблоками и картофелем. Ужин, ~700 ккал.",
    "Рыба в кляре с картофелем фри и соусом тартар. Ужин, ~620 ккал.",
    "Баранина тушёная с нутом и томатами. Ужин, ~580 ккал.",
    "Куриный шашлык с овощами гриль и лавашом. Ужин, ~540 ккал.",
    "Свинина с квашеной капустой и картофелем. Ужин, ~600 ккал.",
    "Запечённая семга с соусом терияки и рисом. Ужин, ~560 ккал.",
    "Говяжьи котлеты с луковым соусом и гречкой. Ужин, ~580 ккал.",

    # ── LUNCH/DINNER (обед или ужин) ─────────────────────────────────────
    "Греческий салат с фетой, оливками и курицей гриль. Обед/ужин, ~420 ккал.",
    "Ризотто с грибами, пармезаном и белым вином. Обед/ужин, ~540 ккал.",
    "Тайский суп том-ям с креветками и кокосовым молоком. Обед/ужин, ~380 ккал.",
    "Шаурма с курицей, овощами и соусом. Обед/ужин, ~580 ккал.",
    "Бургер с говяжьей котлетой, сыром и картофелем фри. Обед/ужин, ~750 ккал.",
    "Пицца маргарита с моцареллой и базиликом. Обед/ужин, ~620 ккал.",
    "Суши-ролл с лососем, авокадо и огурцом. Обед/ужин, ~420 ккал.",
    "Цезарь с курицей гриль, пармезаном и гренками. Обед/ужин, ~480 ккал.",
    "Паэлья с морепродуктами, рисом и шафраном. Обед/ужин, ~560 ккал.",
    "Фалафель с хумусом, питой и овощами. Обед/ужин, ~520 ккал.",
    "Тако с говяжьим фаршем, сыром и сальсой. Обед/ужин, ~540 ккал.",
    "Карбонара из цукини с беконом и яйцом. Обед/ужин, ~480 ккал.",
    "Куриный буррито с рисом, фасолью и авокадо. Обед/ужин, ~620 ккал.",
    "Стир-фрай с говядиной, брокколи и соевым соусом. Обед/ужин, ~460 ккал.",
    "Запечённые баклажаны с фаршем и сыром. Обед/ужин, ~480 ккал.",

    # ── SNACK (перекус) — высококалорийные ──────────────────────────────
    "Протеиновый смузи с молоком, бананом, овсянкой и какао. Перекус, ~380 ккал.",
    "Тост с авокадо и яйцом пашот. Перекус, ~320 ккал.",
    "Греческий йогурт с гранолой и мёдом. Перекус, ~300 ккал.",
    "Творог с бананом и мёдом. Перекус, ~280 ккал.",
    "Хлебцы с сыром и помидором. Перекус, ~260 ккал.",
    "Финики с миндальной пастой. Перекус, ~300 ккал.",
    "Рисовые шарики онигири с лососем. Перекус, ~320 ккал.",
    "Хумус с питой и овощными палочками. Перекус, ~280 ккал.",
    "Сырники маленькие со сметаной. Перекус, ~300 ккал.",
    "Банановый хлеб с грецкими орехами. Перекус, ~350 ккал.",

    # ── Дополнительные высококалорийные блюда ───────────────────────────
    "Паста с тунцом, оливками и томатным соусом. Обед/ужин, ~560 ккал.",
    "Жареный рис с яйцом, овощами и соевым соусом. Обед/ужин, ~520 ккал.",
    "Куриный рулет с сыром и шпинатом. Обед/ужин, ~500 ккал.",
    "Говяжий гуляш с картофелем и паприкой. Обед/ужин, ~580 ккал.",
    "Запечённая картошка с беконом и сметаной. Обед/ужин, ~560 ккал.",
    "Омлет с ветчиной, сыром и грибами. Завтрак/обед, ~480 ккал.",
    "Куриный суп с рисом и яйцом. Обед, ~400 ккал.",
    "Свиная отбивная с картофельным пюре и соусом. Ужин, ~640 ккал.",
    "Запечённая грудка индейки с овощами. Ужин, ~460 ккал.",
    "Паста с курицей в сливочно-грибном соусе. Обед/ужин, ~620 ккал.",
    "Рыбный суп уха с картофелем и зеленью. Обед, ~360 ккал.",
    "Котлеты из индейки с гречкой и салатом. Обед/ужин, ~500 ккал.",
    "Запечённые куриные крылышки с соусом барбекю. Ужин, ~520 ккал.",
    "Говяжий суп харчо с рисом и томатами. Обед, ~440 ккал.",
    "Паста с морепродуктами в томатном соусе. Обед/ужин, ~540 ккал.",
    "Куриный рулет с грибами и сыром. Обед/ужин, ~520 ккал.",
    "Запечённая свинина с яблоками и горчицей. Ужин, ~600 ккал.",
    "Рис с тушёными овощами и нутом. Обед/ужин, ~440 ккал.",
    "Куриный шницель с картофелем и капустным салатом. Обед/ужин, ~580 ккал.",
    "Запечённая форель с лимоном и зеленью. Ужин, ~420 ккал.",
]


async def main(count: int, start_from: int) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    research_agent = build_research_agent()
    verification_agent = build_verification_agent()

    seeds = SEED_PROMPTS[start_from : start_from + count]
    summary = {"accepted": 0, "review": 0, "rejected": 0, "failed": 0, "duplicate": 0}

    async with async_session() as session:
        before = (await session.execute(select(func.count()).select_from(Recipe))).scalar_one()
        print(f"Recipes in DB before: {before}")

    for idx, prompt in enumerate(seeds, start=1):
        seed_input = {
            "raw_text": (
                prompt + "\n\n"
                "Верни JSON с полями: title, description (шаги приготовления), "
                "ingredients (список объектов {name: str, amount: float, unit: 'g'|'ml'|'piece'|'tbsp'|'tsp'}), "
                "calories (число), protein (число), fat (число), carbs (число), "
                "meal_type ('breakfast'|'lunch'|'dinner'|'snack'|'lunch/dinner'), "
                "tags (список русских тегов), allergens (список: 'gluten','milk','eggs','nuts','peanuts','fish','soy','honey'), "
                "ingredients_short (строка через запятую), prep_time_min (число), category (строка)."
            ),
            "source_type": "llm_generated",
            "provenance": {
                "trust_level": "internal_curated_seed",
                "generator": "generate_catalog_batch.py",
                "prompt_index": start_from + idx - 1,
            },
        }
        async with async_session() as session:
            try:
                result = await run_catalog_agent_pipeline(
                    session,
                    seed_input=seed_input,
                    research_agent=research_agent,
                    verification_agent=verification_agent,
                )
                status_key = result.status.lower() if result.status else "failed"
                if status_key not in summary:
                    status_key = "failed"
                summary[status_key] = summary.get(status_key, 0) + 1
                icon = "✓" if result.status == "accepted" else ("~" if result.status == "review" else "✗")
                print(
                    f"[{idx:3}/{len(seeds)}] {icon} {result.status:10} | "
                    f"recipe_id={result.recipe_id or '-':36} | {prompt[:60]}"
                )
                if result.error:
                    print(f"           error: {result.error}")
            except Exception as exc:
                summary["failed"] += 1
                print(f"[{idx:3}/{len(seeds)}] ✗ EXCEPTION | {prompt[:60]}")
                print(f"           {exc}")
                await session.rollback()

    async with async_session() as session:
        after = (await session.execute(select(func.count()).select_from(Recipe))).scalar_one()
        print(f"\nRecipes in DB after:  {after}  (+{after - before})")
        print(f"Summary: {summary}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate recipes via LLM catalog agent")
    parser.add_argument("--count", type=int, default=50, help="Number of recipes to generate")
    parser.add_argument("--start-from", type=int, default=0, help="Start index in SEED_PROMPTS")
    args = parser.parse_args()
    asyncio.run(main(args.count, args.start_from))
