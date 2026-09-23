# Characterization текущего агента

Результат этапа 2 на 2026-09-23: воспроизводимый offline-набор и отдельный disposable PostgreSQL run. Эти проверки фиксируют наблюдаемое поведение baseline, включая дефекты; они не означают, что safety gate пройден.

После [production cutover](PRODUCTION_CUTOVER.md) существующие mode/day-week/error сценарии обновлены под единый use case: aliases возвращают `agentic`, context загружается один раз, неизвестный mode отвергается. Таблицы baseline и прежние 221/3 результаты ниже — исторические evidence, а не описание сегодняшних wrapper expectations. Unsafe witnesses C03/C05/C10/C11 сохраняются. Новые тестовые файлы при cutover не добавлялись.

## Запуск

Из secret-free worktree без корневого `.env`, с уже подготовленной backend Python environment:

```bash
cd backend
python -B scripts/check_agentic_baseline.py
python -B scripts/check_agentic_baseline.py --full
python -B scripts/check_agentic_baseline.py --database
```

Первый режим выполняет `tests/agent` без внешних сервисов. `--full` запускает собственный ephemeral Redis из уже локально имеющегося `redis:7-alpine`, затем все non-integration/non-live_source tests. `--database` запускает собственную pgvector PostgreSQL из уже локального `pgvector/pgvector:pg16`, применяет Alembic upgrade и выполняет storage/pgvector integration tests. Docker images не скачиваются, пакеты не устанавливаются. Production containers, volumes, DB и queues не используются.

Runner очищает env, задаёт synthetic credentials, отключает bytecode/cacheprovider и использует фиксированный Hypothesis seed 20260923. Socket guard разрешает только адрес принадлежащего runner сервиса. HTTPX ASGI transport работает без сети. Артефакты `pytest.xml`, `pytest.log`, `run.json`, а в DB режиме `alembic-upgrade.log` создаются в отдельном temp-каталоге 0700; путь печатается. Контейнер останавливается в finally и удаляется Docker `--rm`. Не запускать тесты, подставляя production URL вручную.

Необычные условия (неподготовленная среда, отсутствующий локальный image, startup failure) должны давать ошибку, не автоматический fallback к production Redis/DB.

## Что действительно исполняется

|Набор|Выполняется|Подменено / граница|
|---|---|---|
|`test_transition_characterization.py`, days1/7/14×2 modes|Реальные wrappers, agentic loop, ToolExecutor, validators, enrichment, totals, shopping|LLM protocol scripted, retrieval pools synthetic, persistence boundary captured|
|Provider failure/retry|Настоящие retry/call counters и wrapper error handling|HTTP provider reply/exception|
|Executor isolation|Два экземпляра с разными profiles и interleaved calls|SQL retrieval; не concurrent DB race|
|`test_baseline_safety_boundaries.py`|ASGI route/cache path; enqueue order; commit/cache order; 150 compatibility helper calls|Cache/DB/broker boundaries, не реальный Celery redelivery|
|`test_plan_storage_characterization.py`|Настоящие migrations, normalized writes/reads, unique constraint, rollback|Только cache write; PostgreSQL реальный disposable|
|Существующие `tests/agent`|Tools schemas, guards, provenance, hash, profile projection, search/call limits, errors, traces, legacy flag|Существующие unit fixtures и provider mocks|
|Существующие tests demo/catalog/source|Их текущие unit/runtime contracts|Внешние sources/provider и часть DB stubs|

Generation на7 и14 дней здесь действительно проходит цикл по всем дням с отдельными tool sessions и синтетическими рецептами, а не копирует один сохранённый UI fixture. Каждому дню соответствует 3 LLM replies, 1 retrieval и trace трёх tools. Test corpus даёт уникальные recipe IDs по дням; не доказывает, что реальный каталог всегда достаточен или что LLM соблюдает разнообразие.

## Зафиксированные различия и defects

|Контракт|Наблюдение|Действие этапа3/4|
|---|---|---|
|C03 owner authorization|Anonymous ASGI GET получает cached чужой plan, DB не читается|Negative two-user/cache/export/task matrix; guard до cache|
|C05 nutrition trust|LLM plan2000 kcal принимается valid при recipe pool с суммой4 kcal и теми же IDs|Canonical materialization, затем final validation; изменить witness на rejection/assert canonical nutrients|
|C10 queue durability|send_task успевает до failed DB write|Durable job/outbox, claim/idempotency, failure/retry tests|
|C11 cache after commit|Caller получает cache exception после успешного DB commit|Не перезаписывать durable READY как failed; define post-commit failure semantics|
|C11 metadata readback|Настоящая БД возвращает meals/ingredients, но generation_meta={}|Хранение и roundtrip version/provenance/trace/quality|
|C02 API vs worker|API отвергает unknown mode, внутренний `_generate_by_mode` переводит его в direct|Worker-side validation; единый согласованный runtime contract|
|C07 wrappers|CLI загружает context2×days и raises на budget failure; direct создаёт plan и возвращает FAILED|Один use case с единым state/error contract|
|C08 meal compatibility|Helpers расходятся по snack/second_snack/universal|Не объединять без утверждённой truth table|

Тесты с именами `test_baseline_*` специально утверждают **текущее небезопасное поведение**. При исправлении соответствующего C-ID необходимо заменить assertion на целевой контракт и сохранить сам сценарий, а не удалить тест или добавить xfail. До этого green characterization suite не является green safety suite.

## Результаты этой ветки

- Offline full: **221 passed, 4 deselected** после добавления двух gated DB tests. Из них25 новых offline cases к исходным196.
- Disposable DB: **3 passed** — два новых storage tests плюс существующий pgvector HNSW test. Fresh migration upgrade PASS.
- Ruff новых scripts/tests: PASS. Общий baseline Ruff по старым app/tests остаётся4 diagnostics; production code не исправлялся.
- Frontend, provider live costs, cloud, настоящий Celery redelivery/crash/concurrency в этом этапе не проверялись повторно. Прежние frontend84 TS errors и schema drift53 не объявляются устранёнными.

Первый полный run до добавления DB-файла:221passed/2deselected. После добавления DB-файла два новых integration cases также исключены обычным offline marker filter — поэтому4deselected не regression.

## Что ещё нужно для safety gate

Two-user authorization для всех routes и exports; canonical portion/recipe tampering; real outbox/broker redelivery; kill-after-commit/retry; concurrent claim; cancellation/deadline; malformed provider batch cardinality; API/cache roundtrip metadata; frontend compatibility после смены контракта. Они относятся к целевым regression tests этапа3, а не подменяются текущими успешными mock tests.
