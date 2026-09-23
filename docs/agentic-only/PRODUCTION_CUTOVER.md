# API / Celery / frontend: единый agentic use case (исторический отчёт до удаления legacy)

**Примечание к актуальной ветке:** описанные ниже алиасы `agent_cli` / `llm_direct` и wire-значение `agent_cli` удалены последующим cleanup. Новая версия принимает только `agentic`. Перед deployment старые workers и несовместимые сообщения должны быть выведены из очереди контролируемо; purge broker не выполнялся. Документ сохранён как историческое evidence.

Дата: 2026-09-23. Ветка: `codex/mealy-agentic-only`. Основание этой порции: `db33c12`.

Переключён **код в рабочей ветке**, не работающие контейнеры. Push, deployment, очистка очереди, смена production configuration и изменения исторического baseline не выполнялись. Это не закрытие safety gate.

## Production-цепочка

`frontend → POST /api/generate-plan → generate_meal_plan (Celery) → agent/use_case.generate_meal_plan → agent/generation.generate_days → agent/runtime.generate_day_plan → final validation/repair → save`

HTTP сохраняет асинхронный контракт: возвращает task_id, а use case исполняется worker. API не запускает LLM второй раз внутри HTTP-запроса. API и worker используют общее имя задачи и нормализацию mode из `agent/contracts.py`; выбора двух разных generation wrappers больше нет.

|Изменение|Файл относительно backend/app/|
|---|---|
|Единый production use case|`core/agent/use_case.py`|
|Общий внутренний day/week loop|`core/agent/generation.py` — используется без второго цикла|
|Финальная validation и deterministic repair перенесены, не скопированы|`core/agent/validation.py`; старый CLI adapter также делегирует сюда|
|Общие progress callback/emit helpers|`core/generation_meta.py`|
|API нормализует mode и публикует одну задачу|`api/routes/plans.py`|
|Worker вызывает только production use case|`worker/tasks.py::_generate_by_mode`|
|Observability consumer импортирует новый модуль напрямую|`api/routes/plans.py → core/agent/observability.py`|

В production сохраняются история titles/avoid IDs, per-day ToolExecutor, поиск только через tools, provenance/hash/schema/day-target guards, финальная проверка слотов и повторов, deterministic repair и повторная validation исправленного дня. Осталась прежняя явно отмечаемая в warnings политика ослабления week uniqueness до previous-day uniqueness при repair; новый алгоритм повторов не вводился.

Профиль загружается один раз, `include_recipes=False`, затем копируется как server-owned snapshot. Не выполняются два context load на день или eager candidate retrieval. Каждый ToolExecutor по-прежнему копирует профиль. Ошибки use case поднимаются в Celery adapter, который формирует прежний FAILED payload и финализирует GenerationRun. Сохранение выбрано по более строгому прежнему CLI-контракту: после финальных проверок всей недели; прежняя direct-ветка с ранней записью plan больше не вызывается production dispatch.

`AGENT_TOOL_USE_ENABLED` не выбирает production runtime и не блокирует agentic loop. Переменная временно остаётся только для старых adapters; это пояснено в config и `.env.example`. Fallback в старый pipeline из нового use case отсутствует.

## Совместимость ранее поставленных задач

Имя зарегистрированной задачи остаётся **`generate_meal_plan`**, порядок аргументов **`user_id, days=7, mode="agentic"`** для нового worker. При публикации API временно передаёт совместимое wire-значение **`agent_cli`**; новый worker нормализует его обратно в `agentic`. Старые сообщения с двумя positional args или соответствующими kwargs также принимаются. Task IDs, очереди и результаты не переписываются.

|Вход mode|Поведение нового API/worker|
|---|---|
|Пропущен|`agentic`|
|`agentic`|Единый use case|
|`agent_cli`|Совместимый alias того же use case|
|`llm_direct`|Совместимый alias того же use case, не старый direct wrapper|
|Любой другой|API validation error; прямой worker-вызов завершается FAILED, без fallback|

Новые запросы API публикуются с wire mode `agent_cli`, а создаваемые API `GenerationRun`, результаты/progress/generation_meta нового worker имеют нормализованный mode `agentic`. Ранее записанный `GenerationRun.mode` может сохранять исходное старое имя; исторические строки БД не мигрировались. Уже готовые старые результаты продолжают читаться существующим task polling API. Совместимость означает принятие старого формата сообщения, **не сохранение старого алгоритма `llm_direct`**.

Проверена совместимость контракта в коде/существующих сценариях; отдельный regression test проверяет wire `agent_cli` и persisted `agentic`; фактический backlog production broker не исследовался и не переисполнялся. Проверка signature/registered task name не является испытанием реальной доставки, retry или redelivery.

### Порядок внедрения — обязательно

1. Перед реальным release закрыть или отдельно принять существующие safety blockers; текущие результаты не являются разрешением на deployment.
2. На время смены версии контролируемо приостановить новую генерацию; дать активным старым задачам завершиться. Не делать purge очереди, не очищать broker и не пересоздавать Redis/DB.
3. Обновить **всех** generation workers, проверить версии и наличие `generate_meal_plan`. Оставшиеся старые сообщения принимаются как aliases. Catalog task names и обработчики остаются прежними.
4. Только затем обновить API и frontend и возобновить отправку задач.
5. Сохранить поддержку aliases до подтверждённого отсутствия старых producers и queued/reserved/scheduled сообщений этого формата.

Смешанный rollout по-прежнему опасен: wire alias `agent_cli` не уходит в direct fallback старого worker, **но его реализация использует настоящий агентный loop только при `AGENT_TOOL_USE_ENABLED=True`**; при выключенном флаге она вызывает старый pipeline. Поэтому обновление всех generation workers до нового runtime и контролируемая смена producer/consumer по-прежнему обязательны. При rollback остановить новую генерацию и согласованно возвращать совместимые версии. Не отправлять `agentic` как wire mode старым workers. Автоматического fallback в новом production use case нет.

## Frontend и demo

Frontend уже использовал production endpoints до этой порции. Теперь `client.ts` явно отправляет `mode: "agentic"` в `/api/generate-plan` и опрашивает `/api/tasks/{task_id}`. Убраны два endpoint wrappers из `api.ts`, которые могли скрывать выбор маршрута; task_id кодируется в URL. В исходниках frontend обращений к `/demo/` нет. Observability URL остался `/api/plans/{id}/observability`, backend consumer переведён на выделенный модуль.

Backend demo routes пока сохранены для отдельного физического удаления и возможных старых клиентов/сохранённых ссылок. Новый frontend и основной production dispatch их не вызывают. Старые demo task IDs не являются Celery task IDs и автоматически в новый polling contract не преобразуются; их backend read endpoint пока остаётся доступным.

## Что намеренно не исправлялось

Ownership/cache, доверие к КБЖУ модели, publish-before-durable-run/outbox, idempotency, post-commit cache failure, потеря metadata при DB readback, общенедельные budgets остаются известными ограничениями. Старый `partially_valid` quality label при repair также сохраняется. Ни один из этих дефектов не исправлялся под видом переключения маршрута. Финальные проверки по-прежнему не доказывают canonical nutrition trust. Инфраструктура каталога, миграции и внешние зависимости не менялись.

## Проверки

Все проверки выполнены после реализации. Новых тестовых файлов/функций не добавлено. Существующие day/week, provider/save failure и API dispatch сценарии переиспользованы; добавлены значения `agentic` к их параметрам, проверены aliases, signature зарегистрированной задачи, отсутствие зависимости production от legacy flag и отклонение неизвестного mode. Monkeypatch targets обновлены вслед за переносом validation. Старые unsafe witnesses не скрыты и не объявлены исправленными.

- **115 passed**, 4.25 s: `tests/agent`, `test_agent_cli_runtime.py`, `test_day_plan_repair.py`, `test_plan_routes.py`, `test_observability.py`, `test_catalog_worker.py`, `test_source_discovery_worker.py`, `test_orchestrator.py`.
- Ruff по затронутому backend/agent/test коду: PASS. `git diff --check`: PASS.
- Biome lint двух изменённых frontend файлов: PASS. Первый вызов из корня репозитория остановился на nested config; корректный вызов из `frontend` с `--config-path=biome.json` прошёл без изменения конфигурации.
- Astro frontend build: PASS, 1 page, в отдельной временной копии с копией имеющихся node_modules. Пакеты не устанавливались; исходный node_modules и production secrets не использовались как writable build workspace.
- Full backend, migrations/DB, live LLM, реальный broker/redelivery, browser E2E и полный TypeScript typecheck не запускались. Старый TS debt не объявляется устранённым. Frontend test runner в package scripts не задан.

Evidence: `/tmp/mealy-cutover-check.XrbqKi/pytest.xml`; build `/tmp/mealy-frontend-cutover.wPsFoE/dist`. Это временные локальные артефакты, не часть Git и не новая резервная копия. Тестовый env очищен, provider key пустой, DB/Redis — заблокированные synthetic loopback endpoints, socket guard включён, Hypothesis seed `20260923`.

## Commits и следующий шаг

- `be48c43` — production use case, общая validation, API/worker dispatch, task compatibility и observability import.
- `bb2c0ea` — frontend явно использует новый API contract.

Следом отдельный documentation commit сохраняет этот отчёт. Push и deployment не выполнялись.

После этого переключения готовы к следующей cleanup-порции: старый `tasks._generate`, `agent_cli_runtime.run_agent_cli_pipeline`, dispatcher/legacy функции `agent/orchestrator.py`, его re-export observability, demo routes/DTO/runtime после проверки оставшихся внешних consumers. **Не удалять** вместе с ними `agent/validation.py`, `day_plan_repair`, `recipe_usage`, `canonical_pipeline` profile/storage helpers и `cli_contract` validation/save helpers: новый use case их использует. Старые алиасы mode и зарегистрированное Celery task name пока сохранять для совместимости очереди.
