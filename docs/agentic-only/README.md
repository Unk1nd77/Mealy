# Agentic-only: действующий контур

Пользовательский план: FastAPI `/api/generate-plan` → Celery `generate_meal_plan` → `app/core/agent/use_case.py` → `agent/runtime.py` с тремя allowlisted tools (`get_user_profile`, `search_recipes`, `validate_day_plan`) → детерминированная проверка → PostgreSQL. Предварительная выдача рецептов в prompt и pipeline fallback удалены.

Каталог — **отдельная** административная функция: `/api/catalog/source-ingest-jobs` → Celery → `source_discovery_runtime.py` → `catalog_agent_runtime.py` (research → candidate → verify → admit). Текущий `source_harvester.py` обнаруживает URL программно по allowlist/sitemap/HTML; это ещё не полностью LLM-управляемый поиск. Агент не должен придумывать рецепты без подтверждённого внешнего источника. Пустую БД нужно наполнить через этот workflow до генерации планов.

Целевая политика и незакрытые release gates: [TARGET_SPEC.md](TARGET_SPEC.md). Статический рефакторинг не равен проверенному production deployment: остаются тесты реальной очереди/БД/LLM, проверка миграций, ownership, canonical nutrients и атомарного сохранения.

Исторические документы доступны в Git до очистки; в рабочем дереве не поддерживаются параллельные версии спецификации.
