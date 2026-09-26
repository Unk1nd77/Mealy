# Целевая спецификация agentic-only v1

Статус: нормативная цель, не описание уже выпущенного поведения. Основание — утверждённый владельцем семиэтапный план. Выбор framework пока OPEN; установка LangGraph не является архитектурным решением сама по себе.

## Область

Один production-путь генерации питания на день и неделю. Запрос на 1 день — частный случай того же use case, а не отдельная реализация. Текущий диапазон API 1–14 дней сохраняется до отдельного обоснованного изменения. Acceptance matrix обязательно включает 1, 7, 14 и недопустимые 0/15.

Каталог остаётся самостоятельной ответственностью: discovery → candidate → review → admission. Генерация читает допущенный каталог и не публикует новые рецепты. Общие domain services можно разделять; отдельные процессы/очереди каталога добавляются только при доказанной необходимости изоляции нагрузки или прав.

## Контракты безопасности

1. Principal устанавливается серверной аутентификацией. Любой plan/task/profile read, mutation и export проверяет владельца **до** возврата cache/broker/DB данных. Переданный `user_id` не является полномочием. Owner mismatch не раскрывает содержимое чужого объекта. Admin catalog permission не даёт неявного доступа к чужому health profile.
2. Profile передаётся executor как server-owned snapshot. LLM не получает идентификатор другого пользователя и не может изменить owner, allergies, diseases или safety filters. State и recipe provenance изолированы по generation run и дню.
3. Выбор recipe ID моделью недостаточен для доверия к КБЖУ. Итоговые nutrients, ingredients, units и порции формируются из серверных данных допущенного recipe/version и разрешённого portion factor. LLM не может подменить числа, оставив тот же ID. Отсутствующие/неполные canonical данные означают отказ, а не нулевые питательные значения.
4. Final deterministic validation выполняется **после** canonical materialization и normalization. Сохраняется именно этот проверенный объект. Hash guard исключает подмену последнего проверенного черновика, но не заменяет canonical nutrition check.
5. Недопустимый/неполный план нельзя маркировать READY/valid. Ошибки provider, лимиты и невозможный каталог завершаются типизированным failure. Не допускается скрытое переключение на pipeline/demo или генерация фиктивного успешного результата. Существующий partially_valid — наблюдаемый legacy contract, не одобренный safety bypass.

## Runtime / tools / guards

- Runtime владеет loop, budget, cancellation, provider protocol и transitions, но не реализует отдельно business validation, recipe scaling или persistence.
- ToolExecutor диспетчеризует allowlisted tools и передаёт server context в domain services. Минимальные tools: `get_user_profile`, `search_recipes`, `validate_day_plan`. Произвольный SQL, shell и client-selected user identity не разрешены.
- Guards: schema; session readiness; exact-draft hash; recipe provenance; requested day/target; canonical nutrition; schedule/safety; day/week consistency.
- Одинаковые guards и domain services обязательны для текущего runtime и экспериментального кандидата. Эксперимент не вправе улучшать метрики отключением проверок.
- LLM requests, search attempts, tool calls, tokens и wall-clock deadline имеют явные budgets. Failed provider/search attempts тоже учитываются. Ограничение LLM rounds само по себе не ограничивает размер tool-call batch. Численные whole-week/tool/token budgets выбираются по измерениям этапа 4; до этого нельзя утверждать, что cost gate закрыт.
- Errors и telemetry не раскрывают JWT, provider keys, DB strings или health profile. Сохраняются correlation/run IDs, runtime/version, prompt/tool schema version, provider/model, usage и sanitized error code.

## День и неделя

Use case загружает единый profile snapshot и формирует упорядоченные дни. У дня свой executor state/search budget/provenance; у недели общий budget и политика повторов. Один только prompt «не повторяй» не является enforced rule.

Необходимо явно проверить существующие правила совместимости `snack`, `second_snack`, `universal`, `lunch/dinner`. Их текущие различия сохраняются в characterization; целевая единая truth table и политика повторов фиксируются до замены helpers. Если каталог не позволяет строго уникальную неделю, нельзя незаметно ослаблять правило: требуется явная политика с machine-readable outcome.

## Persistence и Celery

- Job ownership/run record должен быть durable до публикации job. DB commit и Redis publish не являются общей транзакцией: нужен проверяемый механизм восстановления разрыва (например transactional outbox), а не просто перестановка двух строк.
- Stable idempotency key/run ID; duplicate HTTP retry и Celery redelivery не создают второй успешный plan. Worker проверяет право claim run и не повторяет уже финализированный результат.
- Atomic finalization: normalized days/meals/ingredients, status и generation metadata согласованы. Ошибка записи вызывает rollback, а не частичный READY. Отдельно обрабатываются failure после commit и до cache invalidation/ACK.
- GET после сохранения восстанавливает эквивалентные данные, включая portion/provenance/trace/quality, а не только визуально похожий план. Cache не является источником ownership или единственной копией metadata.
- Один production task contract генерации. Старые task names/arguments и pending queues инвентаризируются перед removal; не оставлять неисполняемые сообщения после deployment.

## Публичный контракт и переход

API должен иметь один agreed request/status/result contract. Текущие consumers используют `agent_cli`, `llm_direct`, demo endpoints и task polling. Их изменение проводится вместе с frontend и negative tests; не удалять поля/маршруты по отсутствию статических imports.

После release gate Requirement 10 исторической спецификации (false → pipeline) заменяется agentic-only dispatch. Rollback означает возврат проверенного предыдущего deployment/commit, а не автоматический fallback на менее защищённый режим внутри запроса. До этого gate конфигурация production не меняется.

## Acceptance gate

Доказаны two-user authorization (включая тёплый cache, task poll, exports и mutations), tampered nutrients, isolation, day/week/boundary days, malformed provider replies, exhausted budgets, duplicate delivery, publish/commit failures, DB rollback/readback и metadata preservation. Backend/frontend suites, build, Ruff и migration checks проходят либо имеют явно изолированный согласованный baseline debt; старые 84 TS errors не объявляются новым PASS. Live LLM cost/quality experiment требует отдельного бюджета; deterministic mock run измеряет correctness, но не реальную стоимость/качество модели.
