"""RAG Retriever — поиск рецептов с фильтрацией по аллергенам, предпочтениям и заболеваниям.

Сначала PostgreSQL/pgvector ранжирует рецепты по смысловой близости, затем строгие
детерминированные фильтры исключают аллергены, противопоказания и нелюбимые продукты.
"""

from __future__ import annotations

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core import cache
from app.core.embeddings import EmbeddingServiceError, embed_search_query
from app.core.meal_compatibility import recipe_type_matches
from app.core.relational_store import load_recipes_from_rows, recipe_to_dict
from app.db.models import Recipe

CACHE_KEY = "recipes:all"
CACHE_TTL = 86400  # 24 hours

# Maps Russian allergen names (as users enter them) to the English codes
# stored in the recipe_allergens table.
# Values are sets so one Russian word can map to multiple English codes
# (e.g. "орехи" excludes both "nuts" AND "peanuts" — peanut butter is nut-adjacent).
_RU_ALLERGEN_MAP: dict[str, set[str]] = {
    # tree nuts + peanuts (арахис — тоже орех для большинства аллергиков)
    "орехи": {"nuts", "peanuts"},
    "орех": {"nuts", "peanuts"},
    "грецкие орехи": {"nuts", "peanuts"},
    "миндаль": {"nuts"},
    "кешью": {"nuts"},
    "фундук": {"nuts"},
    # peanuts
    "арахис": {"peanuts"},
    "арахисовая паста": {"peanuts"},
    # dairy
    "молоко": {"milk"},
    "молочные продукты": {"milk"},
    "лактоза": {"lactose"},
    # gluten
    "глютен": {"gluten"},
    "пшеница": {"gluten"},
    # eggs
    "яйца": {"eggs"},
    "яйцо": {"eggs"},
    # fish & seafood
    "рыба": {"fish"},
    "морепродукты": {"fish"},
    # soy
    "соя": {"soy"},
    # honey
    "мёд": {"honey"},
    "мед": {"honey"},
}


def _normalize_allergen(allergen: str) -> set[str]:
    """Return a set of allergen codes to match against recipe_allergens.

    Handles both English codes (pass-through) and Russian names (mapped to codes).
    Always includes the original lowercased value for substring matching as a fallback.
    """
    lower = allergen.lower().strip()
    codes: set[str] = {lower}  # keep original for substring fallback
    if lower in _RU_ALLERGEN_MAP:
        codes.update(_RU_ALLERGEN_MAP[lower])
    else:
        # partial match: e.g. "грецкие орехи" → {"nuts", "peanuts"}
        for ru_key, en_codes in _RU_ALLERGEN_MAP.items():
            if ru_key in lower or lower in ru_key:
                codes.update(en_codes)
    return codes


_TAG_TO_MEAL_TYPE = {
    "завтрак": "breakfast",
    "обед": "lunch",
    "ужин": "dinner",
    "перекус": "snack",
}

_DISEASE_RULES: dict[str, dict[str, list[str]]] = {
    "diabetes": {
        "exclude_keywords": ["сахар", "мёд", "мед", "сироп", "гранола", "батончик", "слад"],
        "preferred_tags": ["низкоуглеводный"],
    },
    "insulin_resistance": {
        "exclude_keywords": ["сахар", "мёд", "мед", "сироп", "слад"],
        "preferred_tags": ["низкоуглеводный"],
    },
    "celiac": {
        "exclude_keywords": ["глютен", "пшениц", "мука", "лапша", "хлеб", "паста"],
        "preferred_tags": ["без глютена"],
    },
    "hypertension": {
        "exclude_keywords": ["соевый соус", "солен", "соль"],
        "preferred_tags": [],
    },
    "gastritis": {
        "exclude_keywords": ["остр", "жарен", "уксус", "чили"],
        "preferred_tags": [],
    },
}


def _infer_meal_type(tags: list[str] | None, meal_type: str | None) -> str:
    if meal_type and meal_type.strip():
        return meal_type.strip().lower()

    normalized_tags = [tag.lower().strip() for tag in (tags or []) if tag.strip()]
    detected = [_TAG_TO_MEAL_TYPE[tag] for tag in normalized_tags if tag in _TAG_TO_MEAL_TYPE]

    if not detected:
        return "universal"
    if len(detected) == 1:
        return detected[0]
    if "lunch" in detected and "dinner" in detected:
        return "lunch/dinner"
    if "breakfast" in detected and "snack" in detected:
        return "breakfast"
    return detected[0]


async def _load_all_recipes(session: AsyncSession) -> list[dict]:
    """Load all recipes from DB and cache them."""
    recipe_dicts = [
        {
            **recipe,
            "meal_type": _infer_meal_type(recipe.get("tags") or [], recipe.get("meal_type")),
        }
        for recipe in await load_recipes_from_rows(session)
    ]

    await cache.set_json(CACHE_KEY, recipe_dicts, ttl=CACHE_TTL)
    logger.debug("Cached {} recipes in Redis", len(recipe_dicts))
    return recipe_dicts


def _normalize_cached_recipe(recipe: dict) -> dict:
    normalized = dict(recipe)
    normalized["meal_type"] = _infer_meal_type(
        normalized.get("tags") or [],
        normalized.get("meal_type"),
    )
    return normalized


def _is_cache_healthy(recipes: list[dict]) -> bool:
    if not recipes:
        return True
    return all(bool((recipe.get("meal_type") or "").strip()) for recipe in recipes)


async def _get_all_recipes(session: AsyncSession) -> list[dict]:
    """Get all recipes from cache, falling back to DB."""
    cached = await cache.get_json(CACHE_KEY)
    if cached:
        normalized_cached = [_normalize_cached_recipe(recipe) for recipe in cached]
        if _is_cache_healthy(normalized_cached):
            return normalized_cached
        logger.warning("Recipe cache is stale or incomplete; rebuilding from database")
        await cache.delete(CACHE_KEY)
    return await _load_all_recipes(session)


async def _load_vector_ranked_recipes(
    session: AsyncSession,
    *,
    semantic_query: str,
) -> list[dict]:
    query_embedding = await embed_search_query(semantic_query)
    distance = Recipe.embedding.cosine_distance(query_embedding).label("semantic_distance")
    stmt = (
        select(Recipe, distance)
        .where(Recipe.embedding.is_not(None))
        .options(
            selectinload(Recipe.normalized_ingredients),
            selectinload(Recipe.normalized_tags),
            selectinload(Recipe.normalized_allergens),
        )
        .order_by(distance)
        .limit(settings.RAG_VECTOR_CANDIDATE_LIMIT)
    )
    rows = (await session.execute(stmt)).all()
    ranked: list[dict] = []
    for recipe, semantic_distance in rows:
        item = recipe_to_dict(recipe)
        item["_semantic_similarity"] = max(0.0, 1.0 - float(semantic_distance))
        ranked.append(item)
    return ranked


async def _get_hybrid_recipe_order(
    session: AsyncSession,
    *,
    semantic_query: str | None,
) -> tuple[list[dict], bool]:
    all_recipes = await _get_all_recipes(session)
    if not semantic_query:
        return all_recipes, False
    try:
        vector_ranked = await _load_vector_ranked_recipes(
            session,
            semantic_query=semantic_query,
        )
    except (EmbeddingServiceError, httpx.HTTPError, ValueError) as exc:
        logger.warning("Vector retrieval unavailable, using deterministic fallback: {}", exc)
        return all_recipes, False

    seen = {recipe["id"] for recipe in vector_ranked}
    vector_ranked.extend(recipe for recipe in all_recipes if recipe["id"] not in seen)
    logger.debug("RAG: vector-ranked {} embedded recipes", len(seen))
    return vector_ranked, bool(seen)


def _expand_disease_rules(diseases: list[str]) -> tuple[list[str], list[str]]:
    exclude_keywords: list[str] = []
    preferred_tags: list[str] = []
    for disease in diseases:
        key = disease.lower().strip()
        rule = _DISEASE_RULES.get(key)
        if not rule:
            continue
        exclude_keywords.extend(rule["exclude_keywords"])
        preferred_tags.extend(rule["preferred_tags"])
    return list(dict.fromkeys(exclude_keywords)), list(dict.fromkeys(preferred_tags))


def _recipe_matches_keyword(recipe: dict, keyword: str) -> bool:
    """Check if a recipe contains a keyword in ingredients or title."""
    kw = keyword.lower()
    if kw in recipe["title"].lower():
        return True
    return kw in recipe.get("ingredients_short", "").lower()


def _matches_preferred_tags(recipe: dict, preferred_tags: list[str]) -> bool:
    recipe_tags = {tag.strip() for tag in (recipe.get("tags") or []) if tag.strip()}
    return any(tag in recipe_tags for tag in preferred_tags)


async def search_recipes(
    session: AsyncSession,
    allergies: list[str] | None = None,
    dislikes: list[str] | None = None,
    preferred_tags: list[str] | None = None,
    diseases: list[str] | None = None,
    semantic_query: str | None = None,
    limit: int = 30,
    meal_type: str | None = None,
    exclude_recipe_ids: set[str] | None = None,
) -> list[dict]:
    """Поиск рецептов с in-memory фильтрацией по кешированным данным.

    Использует обогащённое поле `allergens` для точной фильтрации аллергенов,
    и `ingredients_short` для фильтрации нелюбимых ингредиентов.
    """
    all_recipes, vector_ranking_active = await _get_hybrid_recipe_order(
        session,
        semantic_query=semantic_query,
    )

    # --- Hard exclusion: allergens ---
    # Normalize Russian allergen names to English codes used in recipe_allergens table.
    # "орехи" → {"nuts", "peanuts"} so peanut butter is also excluded.
    user_allergen_codes: set[str] = set()
    if allergies:
        for a in allergies:
            user_allergen_codes.update(_normalize_allergen(a))

    # --- Hard exclusion: disease rules ---
    disease_exclude_keywords: list[str] = []
    disease_preferred_tags: list[str] = []
    if diseases:
        disease_exclude_keywords, disease_preferred_tags = _expand_disease_rules(diseases)

    # --- Hard exclusion: dislikes ---
    dislike_keywords = [d.lower().strip() for d in (dislikes or []) if d.strip()]

    # Apply hard filters
    safe_recipes: list[dict] = []
    for r in all_recipes:
        if (
            exclude_recipe_ids
            and str(r.get("base_recipe_id") or r["id"]).split("::", 1)[0] in exclude_recipe_ids
        ):
            continue
        if meal_type and not meal_type_matches(r, meal_type):
            continue
        # Filter by allergens: check if any recipe allergen code matches user's codes.
        # Uses both exact match and substring fallback for cross-language robustness.
        recipe_allergens = {a.lower().strip() for a in (r.get("allergens", []) or [])}
        allergen_hit = False
        for recipe_a in recipe_allergens:
            if recipe_a in user_allergen_codes:
                allergen_hit = True
                break
            # substring fallback: catches cases where codes partially overlap
            for user_a in user_allergen_codes:
                if user_a in recipe_a or recipe_a in user_a:
                    allergen_hit = True
                    break
            if allergen_hit:
                break
        if allergen_hit:
            continue

        # Filter by disease-excluded keywords
        if any(_recipe_matches_keyword(r, kw) for kw in disease_exclude_keywords):
            continue

        # Filter by dislikes
        if any(_recipe_matches_keyword(r, kw) for kw in dislike_keywords):
            continue

        safe_recipes.append(r)

    # --- Soft filter: prefer recipes with matching tags ---
    all_preferred_tags = list(
        dict.fromkeys(
            [
                *[t.strip() for t in (preferred_tags or []) if t.strip()],
                *disease_preferred_tags,
            ]
        )
    )

    if vector_ranking_active:
        ranked = sorted(
            enumerate(safe_recipes),
            key=lambda pair: (
                -(
                    settings.RAG_VECTOR_WEIGHT * float(pair[1].get("_semantic_similarity", -1.0))
                    + settings.RAG_PREFERENCE_WEIGHT
                    * float(_matches_preferred_tags(pair[1], all_preferred_tags))
                )
            ),
        )
        return [recipe for _, recipe in ranked[:limit]]

    if all_preferred_tags:
        preferred = [r for r in safe_recipes if _matches_preferred_tags(r, all_preferred_tags)]
        if preferred:
            fallback = [
                r for r in safe_recipes if not _matches_preferred_tags(r, all_preferred_tags)
            ]
            logger.debug(
                "RAG: {} recipes match preferred_tags {}, adding {} fallback recipes for coverage",
                len(preferred),
                all_preferred_tags,
                min(len(fallback), max(limit - len(preferred), 0)),
            )
            return [*preferred, *fallback][:limit]
        logger.debug("RAG: no preferred tag matches, using all {} safe recipes", len(safe_recipes))

    logger.debug(
        "RAG: {} recipes after filtering (allergies={}, dislikes={}, diseases={})",
        len(safe_recipes),
        allergies,
        dislikes,
        diseases,
    )
    return safe_recipes[:limit]


def meal_type_matches(recipe: dict, meal_type: str) -> bool:
    recipe_type = _infer_meal_type(recipe.get("tags"), recipe.get("meal_type"))
    return recipe_type_matches(recipe_type, meal_type, policy="retrieval")
