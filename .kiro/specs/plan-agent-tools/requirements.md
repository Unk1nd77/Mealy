# Requirements Document

> Baseline specification: описывает существующий двухрежимный контракт.
> Цель agentic-only и условия замены Requirement 10 заданы в
> [TARGET_SPEC.md](../../../docs/agentic-only/TARGET_SPEC.md).
> До safety gate и cutover прежнее поведение сохраняется.

## Introduction

Фича переводит агент генерации плана питания с pipeline-архитектуры на полноценный tool-using режим.
LLM самостоятельно вызывает инструменты через OpenAI-style function calling: профиль пользователя,
список рецептов и валидация плана доступны только через инструменты. Оркестратор отслеживает
состояние сессии и принимает финальный ответ только после подтверждённой валидации.

Минимальный набор инструментов: `search_recipes`, `validate_day_plan`, `get_user_profile`.

Текущий стек: FastAPI + PostgreSQL + pgvector + Redis + Celery + OpenRouter LLM API. Язык кода — Python.

---

## Glossary

- **Plan Agent** — агент на базе LLM, генерирующий план питания на 1 день путём вызова инструментов.
- **Tool** — функция, зарегистрированная в API-запросе к LLM (OpenAI-style `tools` поле).
- **Tool Call** — намерение LLM вызвать инструмент с указанными аргументами (поле `tool_calls` в ответе).
- **Tool Result** — JSON-ответ, возвращаемый LLM в роли `tool` после выполнения вызова.
- **Agentic Loop** — цикл: LLM → Tool Call → исполнение → Tool Result → LLM, до финального ответа или лимита.
- **Final Response** — последнее сообщение LLM без `tool_calls`, содержащее готовый план дня в JSON.
- **Session State** — состояние текущего Agentic Loop: `profile_fetched`, `recipes_fetched`, `last_validated_hash`.
- **Orchestration Guard** — серверная проверка Session State перед принятием Final Response.
- **DayPlan** — структура плана на один день (day_number, meals, total_calories, КБЖУ).
- **MealItem** — один приём пищи внутри DayPlan (type, time, recipe_id, title, КБЖУ).
- **User Profile** — профиль пользователя: целевой калораж, расписание, аллергены, предпочтения, заболевания.
- **Safety Filters** — детерминированные фильтры по аллергенам, нелюбимым продуктам и заболеваниям.
- **Deterministic Validator** — функция `validate_day_plan` из `app.core.skills.validator` — единственный авторитетный источник валидации.
- **Recipe Provenance Guard** — backend-инвариант: в финальном плане допустимы только `recipe_id`, возвращённые через `search_recipes` в текущей сессии.
- **Tool Error** — структурированный ответ об ошибке: `{"ok": false, "error": {"code": str, "message": str}}`.
- **AGENT_MAX_LLM_CALLS** — лимит обращений к LLM API в рамках одного Agentic Loop.
- **AGENT_MAX_SEARCH_CALLS** — лимит попыток вызова `search_recipes` (включая неуспешные) за сессию.
- **OpenRouter** — LLM-провайдер, используемый через OpenAI-совместимый API.
- **Orchestrator** — модуль `app/core/agent/orchestrator.py`, содержащий логику генерации плана.
- **Skills** — модули в `app/core/skills/`, содержащие Python-реализации бизнес-логики.

---

## Requirements

### Requirement 1: Регистрация инструментов в запросе к LLM

**User Story:** Как бэкенд, я хочу передавать описания инструментов в поле `tools` API-запроса к OpenRouter,
чтобы LLM мог вызывать функции поиска рецептов, валидации и получения профиля вместо получения всего в промпте.

#### Acceptance Criteria

1. WHILE Plan_Agent работает в tool-using режиме (`AGENT_TOOL_USE_ENABLED = True`), THE Plan_Agent SHALL передавать список инструментов в поле `tools` каждого HTTP-запроса к OpenRouter в формате OpenAI function calling.
2. IF при инициализации tool-using режима ни один инструмент не удалось зарегистрировать, THEN THE Plan_Agent SHALL выбросить `AgentConfigurationError` и не начинать Agentic Loop.
3. IF при инициализации tool-using режима часть инструментов не удалось зарегистрировать (но хотя бы один успешно), THEN THE Plan_Agent SHALL запускаться с доступными инструментами и логировать имена недоступных на уровне `WARNING`.
4. WHILE Plan_Agent работает в tool-using режиме, THE Plan_Agent SHALL задавать `tool_choice: "auto"` в каждом запросе к LLM.
5. THE Plan_Agent SHALL включать в JSON Schema каждого инструмента поля `name`, `description`, `parameters` (с `type: "object"` и `properties`) в соответствии со спецификацией OpenAI function calling.
6. WHILE Plan_Agent работает в tool-using режиме, THE Plan_Agent SHALL включать `response_format: {"type": "json_object"}` только когда `Session State` содержит `last_validated_hash != None` (т.е. ожидается финальный ответ после успешной валидации); в остальных обращениях к LLM `response_format` не передаётся.

---

### Requirement 2: Инструмент `get_user_profile`

**User Story:** Как LLM, я хочу запросить профиль пользователя через инструмент, чтобы получить целевой
калораж, расписание приёмов пищи и ограничения без необходимости получать всё это в системном промпте.

#### Acceptance Criteria

1. WHEN LLM вызывает `get_user_profile`, THE Plan_Agent SHALL вернуть Tool Result с ненулевыми полями: `target_calories` (int), `meal_schedule` (array), `allergies` (array, может быть пустым), `disliked_ingredients` (array, может быть пустым), `diseases` (array, может быть пустым), `preferences` (array, может быть пустым), `goal` (string).
2. WHEN LLM вызывает `get_user_profile`, THE Plan_Agent SHALL установить `Session State.profile_fetched = True`.
3. WHEN LLM вызывает `get_user_profile`, THE Plan_Agent SHALL формировать ответ из объекта `user_profile`, загруженного в память до начала Agentic Loop, без выполнения SQL-запросов.
4. IF объект `user_profile` отсутствует или равен `None` на момент вызова `get_user_profile`, THEN THE Plan_Agent SHALL вернуть Tool Error с `code: "PROFILE_UNAVAILABLE"` и `message: "User profile is not available"`.
5. WHILE Plan_Agent работает в tool-using режиме, THE Plan_Agent SHALL NOT включать в системный промпт поля `target_calories`, `meal_schedule`, `allergies`, `disliked_ingredients`, `diseases`, `preferences`, `goal` — эти данные доступны только через инструмент `get_user_profile`.

---

### Requirement 3: Инструмент `search_recipes`

**User Story:** Как LLM, я хочу искать рецепты по семантическому запросу с указанием типа приёма пищи,
чтобы самостоятельно расширять контекст при нехватке подходящих вариантов.

#### Acceptance Criteria

1. WHEN LLM вызывает `search_recipes`, THE Plan_Agent SHALL принять параметры: `query` (string, обязательный, непустой), `meal_type` (string, опциональный, одно из: `breakfast`, `lunch`, `dinner`, `snack`, `universal`), `limit` (int, опциональный, по умолчанию 10, допустимый диапазон 1–20).
2. IF LLM передаёт пустую строку или строку только из пробелов в параметр `query`, THEN THE Plan_Agent SHALL вернуть Tool Error с `code: "INVALID_QUERY"` и `message: "query must not be empty"` без выполнения поиска; счётчик попыток `search_call_count` не инкрементируется.
3. THE Plan_Agent SHALL инкрементировать счётчик `search_call_count` немедленно после прохождения валидации аргументов и ДО обращения к retriever, независимо от успеха поиска.
4. THE Plan_Agent SHALL применять Safety Filters (аллергены, нелюбимые ингредиенты, заболевания) из профиля текущего пользователя — параметры, переданные executor'у при инициализации — к каждому вызову retriever, независимо от аргументов LLM.
5. IF retriever выбрасывает исключение, THEN THE Plan_Agent SHALL вернуть Tool Error с `code: "SEARCH_UNAVAILABLE"` и `message: "Recipe search is temporarily unavailable"`; реальный `repr(exc)` SHALL быть записан в server log, но не передан LLM.
6. THE Plan_Agent SHALL возвращать список рецептов в поле `recipes`, каждый из которых содержит поля: `id` (string), `title` (string), `meal_type` (string), `calories` (number), `protein` (number), `fat` (number), `carbs` (number), `tags` (array of string).
7. IF `meal_type` передан и является одним из допустимых значений, THEN THE Plan_Agent SHALL фильтровать результаты так, чтобы каждый возвращённый рецепт имел совместимый `meal_type` (с учётом правила `lunch/dinner`).
8. IF `meal_type` передан и не является одним из допустимых значений, THEN THE Plan_Agent SHALL вернуть Tool Error с `code: "INVALID_MEAL_TYPE"` и `message` описывающим допустимые значения, без выполнения поиска; счётчик попыток не инкрементируется.
9. IF результирующий список пуст после применения всех фильтров, THEN THE Plan_Agent SHALL вернуть `{"recipes": [], "message": "No recipes found matching the given criteria and safety filters"}`.
10. WHEN LLM передаёт `limit` больше 20, THE Plan_Agent SHALL выполнить поиск с `limit = 20` и включить в ответ поле `message: "limit clamped to 20"`.
11. WHEN поиск успешен и возвращает рецепты, THE Plan_Agent SHALL установить `Session State.recipes_fetched = True`.

---

### Requirement 4: Инструмент `validate_day_plan`

**User Story:** Как LLM, я хочу проверять черновик плана дня на валидность КБЖУ и соответствие расписанию,
чтобы самостоятельно корректировать план без внешнего retry loop.

#### Acceptance Criteria

1. WHEN LLM вызывает `validate_day_plan`, THE Plan_Agent SHALL принять параметр `plan` (object) в формате схемы `DayPlan`, и использовать `target_calories` и `meal_schedule` из `user_profile` — LLM не передаёт эти параметры явно.
2. THE Plan_Agent SHALL вызывать функцию `validate_day_plan` из `app.core.skills.validator` — единственный Deterministic Validator — передавая `plan`, `target_calories` и `meal_schedule` из `user_profile`.
3. THE Plan_Agent SHALL всегда возвращать Tool Result с полями `is_valid` (bool) и `errors` (list of string); поле `errors` обязательно присутствует в обоих случаях: при успехе — пустой список, при ошибке — непустой. Инвариант: `is_valid == (len(errors) == 0)`.
4. WHEN план валиден (`is_valid: true`), THE Plan_Agent SHALL включать в Tool Result поле `message: "План соответствует всем требованиям"` и `errors: []`.
5. WHEN план невалиден (`is_valid: false`), THE Plan_Agent SHALL включать в `errors` все обнаруженные нарушения и устанавливать `is_valid: false`.
6. IF параметр `plan` является некорректным JSON или не соответствует схеме `DayPlan`, THEN THE Plan_Agent SHALL вернуть `{"is_valid": false, "errors": ["Schema validation error: <description>"], "message": null}`.
7. IF `validate_day_plan` из `skills.validator` выбрасывает неожиданное исключение, THEN THE Plan_Agent SHALL вернуть `{"is_valid": false, "errors": ["Internal validation error: <exc message>"], "message": null}`; `repr(exc)` записывается в server log.
8. WHEN `validate_day_plan` возвращает `is_valid: true`, THE Plan_Agent SHALL вычислить `plan_hash = sha256(json.dumps(plan_data, sort_keys=True))` и установить `Session State.last_validated_hash = plan_hash`.
9. WHEN `validate_day_plan` возвращает `is_valid: false`, THE Plan_Agent SHALL установить `Session State.last_validated_hash = None`.

---

### Requirement 5: Orchestration Guard — серверные гарантии перед принятием финального ответа

**User Story:** Как бэкенд, я хочу гарантировать, что финальный план всегда прошёл обязательные шаги
вне зависимости от того, какой порядок вызовов выбрал LLM.

#### Acceptance Criteria

1. WHEN LLM возвращает ответ без `tool_calls` (попытка вернуть Final Response), THE Plan_Agent SHALL проверить Session State: `profile_fetched == True AND recipes_fetched == True AND last_validated_hash != None`. IF любое из условий не выполнено, THE Plan_Agent SHALL добавить feedback message вместо принятия ответа (не вызывая `AgentLimitError`) и продолжить Agentic Loop.
2. THE feedback message для незавершённого Session State SHALL содержать явное указание на недостающие шаги, например: `"You must call get_user_profile, search_recipes, and validate_day_plan before returning the final plan."`.
3. WHEN Session State прошёл проверку и LLM вернул финальный JSON, THE Plan_Agent SHALL вычислить `response_hash = sha256(json.dumps(plan_data, sort_keys=True))` финального плана и сравнить с `Session State.last_validated_hash`.
4. IF `response_hash != last_validated_hash`, THEN THE Plan_Agent SHALL добавить feedback message: `"The returned plan differs from the last validated version. Please validate the exact plan you intend to submit."` и продолжить Agentic Loop.
5. AFTER Session State guard и hash check прошли, THE Plan_Agent SHALL выполнить финальную серверную проверку через Deterministic Validator (`validate_day_plan` из `skills.validator`) как последний защитный уровень; результат этой проверки является авторитетным для `quality_status`.
6. THE Plan_Agent SHALL использовать результат финальной серверной проверки (п. 5) как единственный источник `quality_status` и `validation_error` в `GeneratedDayResult`; `_assess_quality` как отдельная функция не существует.

---

### Requirement 6: Recipe Provenance Guard

**User Story:** Как бэкенд, я хочу гарантировать, что LLM не может использовать в плане рецепты,
которые не были получены через `search_recipes` в текущей сессии.

#### Acceptance Criteria

1. WHEN Session State guard прошёл и Plan_Agent готов принять финальный ответ, THE Plan_Agent SHALL проверить: все `recipe_id` в `plan.meals` содержатся в `executor.collected_recipes.keys()`.
2. IF найден хотя бы один `recipe_id`, отсутствующий в `collected_recipes`, THEN THE Plan_Agent SHALL добавить feedback message: `"Plan contains recipe IDs not returned by search_recipes in this session: {unknown_ids}. Use only recipes from search results."` и продолжить Agentic Loop.
3. THE Plan_Agent SHALL выполнять проверку provenance ДО финальной серверной валидации (п. Req 5.5).
4. WHEN Recipe Provenance Guard прошёл, THE Plan_Agent SHALL использовать `list(executor.collected_recipes.values())` как единственный источник данных для `_enrich_day_plan`.

---

### Requirement 7: Agentic Loop — цикл исполнения инструментов

**User Story:** Как бэкенд, я хочу поддерживать многоитерационный цикл обработки tool calls,
чтобы LLM мог совершать несколько последовательных вызовов инструментов перед финальным ответом.

#### Acceptance Criteria

1. WHEN LLM возвращает ответ с непустым `tool_calls`, THE Plan_Agent SHALL исполнять все запрошенные вызовы, добавлять сообщение `role: "assistant"` с `tool_calls` в `messages`, затем добавлять Tool Results в виде сообщений `role: "tool"` с соответствующим `tool_call_id`.
2. WHEN LLM возвращает ответ без `tool_calls`, THE Plan_Agent SHALL проверить Session State (Req 5.1) перед принятием как финального ответа.
3. IF количество обращений к LLM API достигло `settings.AGENT_MAX_LLM_CALLS` (по умолчанию 10), THEN THE Plan_Agent SHALL выбросить `AgentLimitError`, содержащее номер последнего вызова и список незавершённых `tool_call_id`.
4. THE Plan_Agent SHALL добавлять сообщение `role: "assistant"` с `tool_calls` в историю `messages` перед добавлением соответствующих Tool Results.
5. WHEN LLM возвращает несколько `tool_calls` в одном ответе, THE Plan_Agent SHALL исполнить все и добавить все Tool Results в `messages` перед следующим обращением к LLM; порядок Tool Results SHALL соответствовать порядку `tool_calls`.
6. IF исполнение инструмента выбрасывает неперехваченное исключение, THEN THE Plan_Agent SHALL добавить Tool Error с `code: "TOOL_EXECUTION_ERROR"` и `message: str(exc)` и продолжить Loop.
7. WHEN LLM сразу возвращает ответ без `tool_calls` (0 tool calls), THE Plan_Agent SHALL применить Session State guard (Req 5.1); поскольку `profile_fetched = False`, SHALL добавить feedback message и продолжить Loop.

---

### Requirement 8: Постобработка финального ответа

**User Story:** Как бэкенд, я хочу получать из Agentic Loop готовый DayPlan, прошедший все серверные
проверки, и обогащать его ингредиентами из БД без изменения формата API-ответа.

#### Acceptance Criteria

1. WHEN Agentic Loop завершается принятым финальным ответом (все guards пройдены), THE Plan_Agent SHALL сначала десериализовать строку ответа как JSON, затем валидировать через схему `MealPlanOutput`; ошибки JSON decode и схемы обрабатываются отдельно.
2. THE Plan_Agent SHALL обогащать финальный план ингредиентами через `_enrich_day_plan(plan, list(executor.collected_recipes.values()))`.
3. THE Plan_Agent SHALL пересчитывать итоговые макросы дня через `_normalize_day_totals` после обогащения.
4. THE Plan_Agent SHALL возвращать `GeneratedDayResult` с полями: `plan` (DayPlanFull), `quality_status` (одно из: `"valid"`, `"partially_valid"`), `attempts_used` (int, общее число обращений к LLM API), `validation_error` (str или None), `tool_call_trace` (list).
5. WHEN финальный ответ не проходит JSON decode или схему `MealPlanOutput`, THE Plan_Agent SHALL добавить feedback message и продолжить Loop, если `AGENT_MAX_LLM_CALLS` не исчерпан; если исчерпан — выбросить `AgentLimitError`.

---

### Requirement 9: Системный промпт в tool-using режиме

**User Story:** Как разработчик, я хочу иметь отдельный системный промпт для tool-using режима,
чтобы LLM знал, какие инструменты доступны и в каком порядке их вызывать.

#### Acceptance Criteria

1. WHILE Plan_Agent работает в tool-using режиме, THE Plan_Agent SHALL загружать системный промпт из ключа `system_tool_use` в файле `meal_plan.yml`; ключ `system` (pipeline-режим) при этом не используется.
2. WHILE Plan_Agent работает в tool-using режиме, системный промпт SHALL содержать явный обязательный порядок: (1) `get_user_profile`, (2) `search_recipes` для каждого типа приёма пищи, (3) сформировать черновик, (4) `validate_day_plan`, (5) вернуть план только если валидация успешна.
3. WHILE Plan_Agent работает в tool-using режиме, THE Plan_Agent SHALL NOT включать в системный промпт: список рецептов, значения `target_calories`, `meal_schedule`, `allergies`, `disliked_ingredients`, `diseases`, `preferences`, `goal`.
4. WHILE Plan_Agent работает в tool-using режиме, системный промпт SHALL содержать явное ограничение: использовать только `recipe_id`, полученные через `search_recipes` в текущей сессии.

---

### Requirement 10: Обратная совместимость и конфигурация режима

**User Story:** Как разработчик, я хочу переключаться между pipeline-режимом и tool-using режимом через
конфигурацию, чтобы при необходимости откатиться без изменений кода.

#### Acceptance Criteria

1. THE Plan_Agent SHALL читать конфигурационный флаг `settings.AGENT_TOOL_USE_ENABLED` (bool, по умолчанию `False`) при каждом вызове `generate_day_plan`.
2. IF `AGENT_TOOL_USE_ENABLED` равен `False`, THEN THE Plan_Agent SHALL использовать текущий pipeline без изменений.
3. IF `AGENT_TOOL_USE_ENABLED` равен `True`, THEN THE Plan_Agent SHALL использовать Agentic Loop с инструментами.
4. THE Plan_Agent SHALL сохранять неизменной сигнатуру функции `generate_day_plan(user_profile, recipes, day_number, *, previous_day_titles, avoid_recipe_ids)` и тип возвращаемого значения `GeneratedDayResult`.
5. WHEN `generate_day_plan` вызывается, THE Plan_Agent SHALL логировать на уровне `INFO`: `"mode=tool_use"` или `"mode=pipeline"`.
6. IF код Agentic Loop достигнут при `AGENT_TOOL_USE_ENABLED = False`, THEN THE Plan_Agent SHALL выбросить `AgentConfigurationError` с сообщением `"Agentic loop entered with AGENT_TOOL_USE_ENABLED=False"`.

---

### Requirement 11: Безопасность и ограничения инструментов

**User Story:** Как бэкенд, я хочу гарантировать, что LLM не может получить данные других пользователей
или обойти Safety Filters через вызовы инструментов.

#### Acceptance Criteria

1. THE Plan_Agent SHALL NOT включать параметр `user_id` в JSON Schema ни одного инструмента.
2. THE Plan_Agent SHALL передавать Safety Filters из `user_profile` (загруженного до Agentic Loop) в `search_recipes`; аргументы LLM не могут переопределить или отключить эти фильтры.
3. IF LLM передаёт неизвестное имя инструмента, THEN THE Plan_Agent SHALL вернуть Tool Error с `code: "UNKNOWN_TOOL"` и продолжить Loop.
4. THE Plan_Agent SHALL инкрементировать счётчик `search_call_count` при каждой попытке вызова `search_recipes` (после валидации аргументов, до обращения к retriever), считая как успешные, так и неуспешные обращения к retriever.
5. IF `search_call_count` достигло `settings.AGENT_MAX_SEARCH_CALLS` (по умолчанию 5, диапазон 1–20) до начала обработки нового вызова, THEN THE Plan_Agent SHALL вернуть Tool Error с `code: "SEARCH_LIMIT_REACHED"` и `message: "Recipe search call limit reached for this session"` без обращения к retriever.

---

### Requirement 12: Наблюдаемость Agentic Loop

**User Story:** Как разработчик, я хочу видеть трассировку tool calls при отладке,
чтобы понимать, какие инструменты и сколько раз вызывал агент при генерации плана.

#### Acceptance Criteria

1. WHEN Plan_Agent исполняет Tool Call, THE Plan_Agent SHALL записать лог на уровне `DEBUG`: имя инструмента, аргументы (усечённые до 200 символов, без `user_id` и полей из `user_profile`), номер LLM-вызова.
2. WHEN Plan_Agent получает Tool Result, THE Plan_Agent SHALL записать лог на уровне `DEBUG`: имя инструмента, первые 200 символов строкового представления результата, номер LLM-вызова.
3. THE Plan_Agent SHALL сохранять в `GeneratedDayResult` поле `tool_call_trace` — список записей `{tool: str, llm_call: int, args_summary: str}` для каждого выполненного вызова; `args_summary` усекается до 200 символов без `user_id` и полей профиля. Поле присутствует при любом завершении Loop.
4. WHEN генерация дня завершается, THE Plan_Agent SHALL логировать на уровне `INFO`: общее число LLM-вызовов, число попыток каждого инструмента (включая нулевые), `quality_status` или тип ошибки.
