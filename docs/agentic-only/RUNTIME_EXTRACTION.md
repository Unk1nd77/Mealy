# Выделение runtime: выполненные изменения и граница следующего этапа

Основание: `8890616` в `codex/mealy-agentic-only`. Исторический baseline `77c6abf` и handoff `f810bdb` не изменяются. Это реализация согласованного узкого рефакторинга, не новый аудит и не закрытие safety gate.

Источники решений: существующие Astra `DEPENDENCY_EDGES.csv`, `LEGACY_CANDIDATES.csv`, `MEALY_AUDIT_REPORT.md` (разделы mode × flag и compatibility), `TARGET_SPEC.md`, C01–C20 из `CONTRACTS_AND_GAPS.md`, существующие characterization tests. Сохраняется вывод Astra: pipeline и demo достижимы, отсутствие обычного импорта не доказывает dead code.

## 1. Границы кода

Все пути ниже относительно `backend/app/core/`, кроме явно указанных.

|Ответственность|Файл после выделения|Что здесь не должно находиться|
|Agentic loop и provider protocol|`agent/runtime.py`|Pipeline fallback, CLI, Celery, запись плана, demo|
|ToolExecutor, allowlist, tool schema, server profile projection, поиск|`agent/tools.py`|Произвольный user_id от модели, orchestration недели, сохранение|
|Readiness, exact-draft hash, redaction аргументов trace|`agent/guards.py`|Provider и persistence|
|Result DTO и ошибки limit/configuration|`agent/contracts.py`|Импорты реализации runtime|
|Обогащение ингредиентами, пересчёт сумм|`agent/plan_output.py`|Решение о READY или canonical nutrition trust|
|Последовательная генерация 1/N дней|`agent/generation.py`|Выбор API mode, DB transaction, Celery state, repair policy|
|Recipe identity, slot и cross-day guards|`recipe_usage.py`|LLM вызовы, retrieval, persistence|
|Общие compatibility policies|`meal_compatibility.py`|Изменение правил без явного требования|
|Загрузка шаблонов|`agent/prompt_loader.py`|Смешивание prompt instructions с server-enforced guards|
|Диагностика сохранённого плана|`agent/observability.py`|Запуск генерации|

Обязательные schema/hash/provenance/day-target проверки остаются в том же порядке в loop. Tool validation и финальная backend validation используют один существующий `skills.validator`; их логика не переписана. `runtime.generate_day_plan` владеет read session. Состояние ToolExecutor по-прежнему создаётся заново для каждого дня; профиль и avoid IDs копируются.

Нужные общие сервисы **не legacy**: `skills.validator`, `skills.aggregator`, `day_plan_repair`, `canonical_pipeline` (profile/context selection/create/finalize), `relational_store`, `recipe_catalog` (scaling), `rag.retriever`. Нельзя удалить их вслед за pipeline по названию файла. Admission/discovery каталога, его инфраструктура, БД и миграции не меняются. В retriever изменён только вызов compatibility predicate.

## 2. Что перенесено из orchestrator.py

|Символы|Назначение|
|`_run_agentic_loop`, `_call_llm_with_tools`, `_build_agentic_system_prompt`|`agent/runtime.py`|
|`ToolExecutor`, `_build_tool_definitions`, `_tool_error`, `_MEAL_TYPES`|`agent/tools.py`|
|`AgentSessionState`, `_compute_plan_hash`, `_build_args_summary`, `_PROFILE_FIELDS`|`agent/guards.py`|
|`GeneratedDayResult`, `AgentLimitError`, `AgentConfigurationError`|`agent/contracts.py`|
|`_enrich_day_plan`, `_normalize_day_totals`|`agent/plan_output.py` — нужны обоим путям|
|`_load_prompt`, `PROMPTS_DIR`|`agent/prompt_loader.py`|
|`build_plan_observability`, `_sanitize_observability_step`, observability constants|`agent/observability.py`|

`orchestrator.generate_day_plan` сохраняет прежнюю сигнатуру и mode logging. Flag ON делегирует в runtime; OFF вызывает прежний `_run_pipeline`. Старые imports `GeneratedDayResult` и `build_plan_observability` сохранены как прямые re-exports для существующих потребителей. Private test seams перенаправлены на новые модули, без сохранения скрытых runtime → orchestrator зависимостей ради monkeypatch.

`_run_pipeline`, `_build_system_prompt`, `_call_llm`, `_append_retry_feedback`, `_parse_response`, `MAX_RETRIES` остаются вместе в `orchestrator.py`: это исключительно старый structured-output путь. Agentic runtime больше не импортирует их модуль. Обратное направление остаётся только у переходной оболочки: orchestrator → runtime.

## 3. Карта консолидации compatibility

Пять мест вызова теперь используют одну реализацию. Три наблюдаемые политики сохранены явно, а не объявлены эквивалентными.

|Потребитель|Общая политика|Сохранённые особенности|
|`canonical_pipeline`|`generation`|snack ↔ second_snack; universal для lunch/dinner; split comma/slash|
|`day_plan_repair`|`generation`|Та же матрица; deterministic repair сохранён|
|`agent_cli_runtime` через `recipe_usage`|`generation`, `allow_universal=tool_use`|При flag ON universal разрешён дополнительно для всех slots|
|`demo_pipeline`|`demo`|second_snack не принимает snack; два коротких forwarding helpers сохраняют старые имена|
|`rag.retriever`|`retrieval`|universal для любого slot, без snack aliases; exact inferred type, без split comma/slash|

Нормализация и проверка пересечения типов больше не скопированы в четыре модуля. Идентичные `_recipe_base_id`, `_meal_base_id`, `_meal_base_id_from_recipes` вынесены из CLI/repair в `recipe_usage`; туда же перенесены `_collect_used_recipe_base_ids` и `_validate_day_recipe_usage`.

## 4. Два wrappers → один внутренний day/week интерфейс

Оба adapters вызывают:

```python
await generate_days(
    days,
    load_context=load_context,
    generate_day=generate_day_plan,
    use_collected_recipes=...,
    carry_history=...,
    draft=GeneratedPlanDraft(...),
)
```

Один день — тот же цикл с `days=1`; неделя — `days=7`. Едиными стали нумерация дней, вызов day generator, сериализация результатов, day metadata, quality aggregation и warnings. Draft request-local; предупреждения, накопленные до ошибки следующего дня, остаются доступны adapter. Это промежуточный результат, **не доказательство безопасного READY**. Shared engine не перехватывает ошибки и не записывает результат.

`_empty_steps` и `_set_step` также объединены в `generation_meta.py`. Форматы step/status/messages и порядок событий adapters сохранены.

|Различие|CLI adapter|Direct adapter|Почему оставлено|
|Контекст|Предварительный проход + загрузка на каждый день|Единый профиль/recipe pool|Сохранить существующее наблюдаемое поведение|
|История недели|Передаёт titles и avoid IDs, сортирует context|Независимые дни, history kwargs не передаются|Не вводить новое правило уникальности скрытым рефакторингом|
|Recipe pool|В tool mode берёт collected recipes|Не использует pool для отдельного week guard|Не добавлять новую политику проверки в direct|
|Validation/repair|Повторная CLI validation, usage guards, deterministic repair|Day-result quality|Не ослаблять CLI и не менять direct contract|
|Сохранение|После проверки всей недели|Создаёт запись до generation, затем finalize|Транзакционный redesign — отдельный этап|
|Ошибка|Публикует failed progress и raises|Финализирует FAILED и возвращает объект|Существующий API/worker contract|

Таким образом, duplication цикла устранён, но **полное слияние внешних adapters намеренно не выполнено**. Оно требует выбора одного error/persistence/history контракта при следующем переключении API/worker. Новая стратегия runtime, framework, LangGraph и универсальный plugin/fallback layer не добавлены.

## 5. Legacy-кандидаты и условия удаления

|Кандидат|Готовность|Что ещё удерживает|
|Legacy symbols в `orchestrator.py`, prompt keys `system`/`retry`|Изолированы от актуального runtime|Flag OFF, старые adapters, pipeline tests; удалять после cutover|
|`orchestrator.py` целиком|Пока нельзя|API import observability; adapters import dispatcher; DTO compatibility import|
|`demo_pipeline.py`, demo API routes|Граница известна; поведения не меняли|Frontend demo consumers и зарегистрированные FastAPI routes; мигрировать их прежде удаления|
|`run_agent_cli_pipeline` и `tasks._generate` оболочки|Общий loop вынесен; два разных adapter contracts остаются|Выбор production contract и перенос обязательной validation/repair/persistence логики|
|Compatibility aliases в старых модулях|Можно убрать вместе с consumers|Существующие private imports/test seams; это forwards, не независимые реализации|
|Shared services из раздела 1|Не кандидаты на удаление целиком|Agentic generation, CLI, repair, catalog и сохранение|

Celery task names, API modes, defaults, frontend, flag defaults, prompt content, внешние payloads и каталог не переключены. Физического удаления старого pipeline/demo в этой порции нет.

## 6. Неисправленные известные ограничения

C03 ownership/cache, C05 доверие к КБЖУ, C09 whole-week budgets, C10 publish-before-durable-run, C11 post-commit cache/metadata и остальные safety gaps остаются открытыми. Ни один из них не блокировал механическое выделение runtime; массовый багфикс не выполнялся. Green characterization означает сохранение baseline, а не устранение этих проблем.

## 7. Проверки и commits

Проверки выполнены только в конце этой порции, существующим адресным набором. Новых тестовых сценариев нет; в семи существующих test/fixture файлах изменены только import/patch targets и вызов выделенной внутренней точки входа. Assertions сохранены.

Адресный набор: `tests/agent`, `test_orchestrator.py`, `test_agent_cli_runtime.py`, `test_day_plan_repair.py`, `test_demo_pipeline.py`, `test_retriever.py`, `test_observability.py`, `test_canonical_pipeline.py`, `test_catalog_worker.py`, `test_source_discovery_worker.py`.

- Первый запуск этого набора: **119 passed, 2 failed**. Обе ошибки — существующие demo tests обращаются к Redis, а socket guard запрещает сеть. Остальные затронутые пути прошли.
- Повторены **только эти два** demo tests с отдельным Redis: **2 passed**. Использован локальный `redis:7-alpine` с `--pull=never --rm`, без volumes, на случайном loopback port. После проверки контейнер остановлен и удалён; четыре исходных контейнера Mealy оставлены работающими.
- Итого **121 существующий сценарий прошёл**; это не результат полного backend suite и не live LLM/E2E проверка. Нельзя интерпретировать как закрытие известных safety defects.
- Ruff по изменённым production-модулям и `tests/agent`: новых diagnostics нет. Сохраняются прежние `UP037` и `RET504` в demo. Они не исправлялись. `git diff --check`: PASS.
- Не запускались повторно frontend, migrations/DB, весь backend, live provider или внешние сервисы каталога. Пакеты и контейнерные images не устанавливались.

Запуски выполнялись с очищенным env, synthetic DB URL на `127.0.0.1:1`, пустым provider key, blocked provider URL, `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider -p tests.characterization.network_guard --hypothesis-seed=20260923`. В Redis-повторе разрешён только endpoint временного контейнера. До адресного запуска одна команда завершилась до collection из-за ошибочного имени `tests/test_cli.py`; в ней **no tests ran**, она не считается проверкой.

Локальные временные evidence (не входят в Git, могут быть удалены ОС):

- `/tmp/mealy-runtime-check.TnUKHa/pytest.xml` — 119 PASS и два Redis environment failures.
- `/var/folders/th/9hm5fbkd2wscr_kv0pykttg80000gn/T/mealy-runtime-demo-i5ckjqsx/pytest.xml` — два успешных повтора.

Коммиты текущей ветки:

|Commit|Содержание|
|---|---|
|`8890616`|Сохранён ранее подготовленный baseline спецификаций и characterization; создан до этой порции рефакторинга|
|`1ce5d2c`|Выделены runtime/tools/guards/result/output/prompt/observability; перенаправлены существующие test seams|
|`6e4877d`|Объединены compatibility, recipe guards, progress helpers и day/week loop двух adapters|

Эти два refactor commits последовательно применимы поверх `8890616`; проверки выполнялись на их совокупном результате, без повторного suite на каждом промежуточном commit. Последующий documentation commit содержит этот отчёт и ссылки на него. Push, deploy и изменения baseline ref в этой порции не выполнялись.

## 8. Конкретный размер diff и следующий шаг

Кодовый diff `8890616..6e4877d`: **25 файлов, +1105 / −1042 строки** (включая переносы и перенаправление старых тестов). Это разделение ответственности, а не заявление о большом сокращении LOC: суммарно +63 строки, десять новых узких модулей, без новых сторонних зависимостей.

|Метрика|До|После|
|---|---:|---:|
|Смешанный `agent/orchestrator.py`|977 строк|273 строки|
|CLI adapter `agent_cli_runtime.py`|482 строки|343 строки|
|`worker/tasks.py`|573 строки|549 строк|
|Дублирующиеся loops generation в CLI/direct|2|1 общий `generate_days`|
|Места с собственной compatibility-логикой|5|1 общий модуль, 3 явные политики|
|Новые тестовые сценарии этой порции|—|0|

Устранены зависимости актуального loop и ToolExecutor от смешанного orchestrator; recipe usage guards от CLI wrapper; observability от генератора; repair/CLI от собственных копий recipe identity и compatibility. Не устранены намеренно: adapters → переходный dispatcher и API → re-export observability. До переключения это рабочие consumers, не dead code.

Следующий этап: выбрать единый внешний error/persistence/history contract; перенести обязательные CLI final validation/repair/usage checks в выбранный use case; направить API/worker на него с учётом старых queued task arguments; перевести observability consumer на новый модуль; согласованно убрать demo consumers/routes. Только после этого удалить dispatcher/legacy pipeline и старые prompt keys, сохранив agentic prompt и общие domain services. Известные safety gaps остаются условиями production release, но не расширяют эту завершённую порцию в массовый багфикс.
