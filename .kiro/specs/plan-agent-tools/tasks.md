# Implementation Plan: plan-agent-tools

## Проверено 2026-09-19

- Реализованы инструменты, Agentic Loop, guards, лимиты и подключение к Celery/CLI.
- Публичная сигнатура `generate_day_plan` сохранена: DB-сессия открывается внутри tool-using ветки. Полученные рецепты передаются CLI через `GeneratedDayResult.collected_recipes`.
- Проверки свойств и интеграции сгруппированы в `backend/tests/agent/`; добавлен Hypothesis.
- Проверка: `uv run pytest -q --tb=short` — **196 passed, 2 skipped** (внешние интеграционные тесты). Ruff для изменённых модулей и новых тестов — без ошибок.
- Реальные вызовы OpenRouter не выполнялись. Режим включается через `AGENT_TOOL_USE_ENABLED=true`; по умолчанию остаётся `false`.

## Overview

Добавляем tool-using режим в `orchestrator.py` с полным набором серверных гарантий:
Session State guard, hash check, Recipe Provenance guard, единый Deterministic Validator.
Pipeline-режим (текущий код) остаётся без изменений — полная обратная совместимость.

---

## Tasks

- [x] 1. Расширить конфигурацию и базовые типы
  - [x] 1.1 Добавить новые поля в `Settings` (`config.py`)
    - `AGENT_TOOL_USE_ENABLED: bool = False`
    - `AGENT_MAX_LLM_CALLS: int = 10` (единственный счётчик LLM-вызовов)
    - `AGENT_MAX_SEARCH_CALLS: int = 5` (диапазон 1–20, попытки включая неуспешные)
    - _Requirements: 10.1, 11.4_

  - [x] 1.2 Добавить новые исключения и `AgentSessionState`
    - `AgentLimitError(llm_calls: int, pending_tool_call_ids: list[str])` — заменяет `AgentIterationLimitError`
    - `AgentConfigurationError(message: str)`
    - `@dataclass AgentSessionState(profile_fetched, recipes_fetched, last_validated_hash)` с методами `ready_for_final()` и `missing_steps()`
    - Разместить в `orchestrator.py` или в `backend/app/core/agent/exceptions.py`
    - _Requirements: 7.3, 10.6_

  - [x] 1.3 Расширить `GeneratedDayResult` полем `tool_call_trace`
    - Добавить `tool_call_trace: list[dict] = field(default_factory=list)` в dataclass
    - Формат каждой записи: `{"tool": str, "llm_call": int, "args_summary": str}`
    - В pipeline-режиме поле остаётся пустым списком
    - _Requirements: 12.3_

  - [x]* 1.4 Unit-тесты для новых типов
    - `AgentLimitError` содержит `llm_calls` и `pending_tool_call_ids` в атрибутах и `str()`
    - `AgentSessionState.ready_for_final()` — все комбинации флагов
    - `AgentSessionState.missing_steps()` — корректные метки недостающих шагов
    - `GeneratedDayResult` с пустым `tool_call_trace` по умолчанию

- [x] 2. Реализовать `_tool_error`, `_compute_plan_hash` и `_build_tool_definitions`
  - [x] 2.1 Реализовать вспомогательные функции в `orchestrator.py`
    - `_tool_error(code: str, message: str) -> dict` → `{"ok": False, "error": {"code": code, "message": message}}`
    - `_compute_plan_hash(plan_data: Any) -> str` → `sha256(json.dumps(plan_data, sort_keys=True))`
    - `_build_args_summary(args: dict) -> str` → `str(args)[:200]` без `user_id` и полей профиля
    - _Requirements: (вспомогательные)_

  - [x] 2.2 Реализовать `_build_tool_definitions() -> list[dict]`
    - Ровно 3 дескриптора: `get_user_profile`, `search_recipes`, `validate_day_plan`
    - `search_recipes`: `query` (required), `meal_type` (enum 5 значений), `limit` (int, min 1, max 20)
    - `validate_day_plan`: `plan` (object, required)
    - Ни один дескриптор не содержит `user_id` в `properties`
    - _Requirements: 1.1, 1.5, 11.1_

  - [x]* 2.3 Тест Property 1: JSON Schema инструментов
    - Файл `backend/tests/agent/test_tool_definitions.py`
    - Для каждого из 3 инструментов: наличие `name`, `description`, `parameters.type == "object"`, `parameters.properties`; отсутствие `user_id` в любом месте схемы
    - **Property 1 | Validates: Req 1.5, 11.1**

- [x] 3. Реализовать `_call_llm_with_tools`
  - [x] 3.1 Реализовать `_call_llm_with_tools(messages, tools, *, expect_final) -> dict`
    - `expect_final` передаётся снаружи — определяется `session_state.last_validated_hash is not None`
    - При `expect_final=True` — добавляет `response_format: {"type": "json_object"}`
    - Всегда включает `tools` и `tool_choice: "auto"`
    - Возвращает `choices[0]` целиком (не только `content`)
    - _Requirements: 1.1, 1.4, 1.6_

  - [x]* 3.2 Unit-тесты `_call_llm_with_tools`
    - Mock `httpx.AsyncClient.post`; проверить payload содержит `tools`, `tool_choice: "auto"`
    - При `expect_final=True` payload содержит `response_format`; при `False` — нет
    - _Requirements: 1.1, 1.4, 1.6_

- [x] 4. Реализовать `ToolExecutor` с тремя исполнителями
  - [x] 4.1 Создать `@dataclass ToolExecutor` в `orchestrator.py`
    - Поля: `user_profile`, `db_session`, `session_state: AgentSessionState`, `search_call_count: int = 0`, `collected_recipes: dict[str, dict] = {}`
    - Метод `async dispatch(tool_name, arguments) -> dict`; fallback → `_tool_error("UNKNOWN_TOOL", ...)`
    - _Requirements: 7.1, 11.3_

  - [x] 4.2 Реализовать `_execute_get_user_profile(self) -> dict`
    - `user_profile is None` → `_tool_error("PROFILE_UNAVAILABLE", ...)`
    - Иначе: `session_state.profile_fetched = True`; вернуть projection из 7 полей без SQL
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x]* 4.3 Тест Property 3: `get_user_profile` возвращает все поля
    - Файл `backend/tests/agent/test_tool_executor.py`
    - Hypothesis: произвольный `user_profile` с `target_calories > 0`, списками строк
    - Все 7 ключей присутствуют; `target_calories` — int > 0; списки — `list`; `session_state.profile_fetched = True`
    - **Property 3 | Validates: Req 2.1**

  - [x] 4.4 Реализовать `_execute_search_recipes(self, arguments: dict) -> dict`
    - Порядок проверок: (1) валидация `query`, (2) валидация `meal_type`, (3) rate limit → `_tool_error`
    - `search_call_count += 1` ПОСЛЕ валидации аргументов и ДО вызова retriever
    - Safety Filters из `self.user_profile` (аллергены, нелюбимые, заболевания) — не из аргументов LLM
    - Исключение retriever → `logger.exception` + `_tool_error("SEARCH_UNAVAILABLE", "temporarily unavailable")`; `repr(exc)` только в logs
    - Успешный поиск: `session_state.recipes_fetched = True`; рецепты в `collected_recipes`; clamp limit
    - _Requirements: 3.1–3.11, 11.2, 11.4, 11.5_

  - [x]* 4.5 Тесты Properties 4, 5A, 6, 7, 16 для `search_recipes`
    - Файл `backend/tests/agent/test_tool_executor.py`
    - **P4**: Hypothesis whitespace query → Tool Error `INVALID_QUERY`; retriever не вызывается; counter не растёт
    - **P5A**: Hypothesis — executor передаёт allergies/dislikes/diseases из `self.user_profile` в retriever независимо от аргументов LLM (mock retriever, проверить переданные kwargs)
    - **P6**: Mock retriever возвращает смешанные `meal_type`; все результаты совместимы с запрошенным
    - **P7**: Hypothesis `limit > 20` → `len(recipes) <= 20` и `message == "limit clamped to 20"`
    - **P16**: После `AGENT_MAX_SEARCH_CALLS` попыток (включая упавшие) → Tool Error `SEARCH_LIMIT_REACHED`; retriever не вызывается
    - **Properties 4, 5A, 6, 7, 16 | Validates: Req 3.2, 3.7, 3.10, 11.2, 11.4, 11.5**

  - [x] 4.6 Реализовать `_execute_validate_day_plan(self, arguments: dict) -> dict`
    - Схема-валидация `DayPlan.model_validate`; ошибка → `{"is_valid": false, "errors": [...], "message": null}`; `last_validated_hash = None`
    - Вызов `validate_day_plan` из `skills.validator` (единственный Deterministic Validator)
    - При успехе: `last_validated_hash = _compute_plan_hash(plan_data)`
    - При неуспехе: `last_validated_hash = None`
    - Всегда возвращать `errors` (пустой или непустой); инвариант `is_valid == (errors == [])`
    - _Requirements: 4.1–4.9_

  - [x]* 4.7 Тесты Properties 8, 9 для `validate_day_plan`
    - Файл `backend/tests/agent/test_tool_executor.py`
    - **P8**: Параметризованные примеры (валидный план, невалидный, некорректная схема) — `is_valid == (errors == [])` без исключений; поле `errors` всегда присутствует
    - **P9**: При успехе `session_state.last_validated_hash == _compute_plan_hash(plan_data)`; при неуспехе `== None`
    - **Properties 8, 9 | Validates: Req 4.3, 4.8, 4.9**

- [x] 5. Checkpoint — базовые компоненты
  - Запустить `pytest backend/tests/agent/ -v`; все тесты зелёные

- [x] 6. Добавить системный промпт `system_tool_use`
  - [x] 6.1 Добавить ключ `system_tool_use` в `meal_plan.yml`
    - Содержит явный обязательный порядок (5 шагов включая хэш-верификацию перед финальным ответом)
    - Содержит ограничение: только `recipe_id` из текущей сессии
    - Не содержит: список рецептов, поля профиля
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 6.2 Реализовать `_build_agentic_system_prompt() -> str`
    - Загружает `system_tool_use` из `meal_plan.yml`; рендерит без переменных профиля
    - _Requirements: 9.1, 9.3_

  - [x]* 6.3 Тест Property 2: системный промпт не содержит данные профиля
    - Файл `backend/tests/agent/test_tool_definitions.py`
    - Hypothesis: генерировать случайные значения полей профиля; проверить их отсутствие в строке промпта
    - **Property 2 | Validates: Req 2.5, 9.3**

- [x] 7. Реализовать `_run_agentic_loop`
  - [x] 7.1 Реализовать основной цикл `_run_agentic_loop`
    - Проверка `AGENT_TOOL_USE_ENABLED` → `AgentConfigurationError`
    - `while llm_call_count < AGENT_MAX_LLM_CALLS:` — единственный счётчик
    - `expect_final = executor.session_state.last_validated_hash is not None`
    - При `tool_calls` пуст: Session State Guard → Hash Guard → Recipe Provenance Guard → Deterministic Backend Validation → enrich → return
    - Feedback messages для каждого guard: Session State, hash mismatch, unknown recipe_id
    - При `tool_calls` непуст: append assistant + dispatch all + append tool results
    - По исчерпании лимита: `raise AgentLimitError(...)`
    - DEBUG-логирование каждого tool call/result; INFO-сводка при завершении
    - _Requirements: 5.1–5.6, 6.1–6.4, 7.1–7.7, 8.1–8.5, 12.1, 12.2, 12.4_

  - [x]* 7.2 Тесты Properties 10, 11, 12, 18: guards и порядок messages
    - Файл `backend/tests/agent/test_agentic_loop.py`
    - **P10**: Session State неполный → feedback добавлен в messages; `GeneratedDayResult` не возвращается
    - **P11**: Hash mismatch → feedback + `last_validated_hash = None`; loop продолжается
    - **P12**: Unknown `recipe_id` в финальном плане → feedback; loop продолжается
    - **P18**: Hypothesis N tool_calls → в messages: assistant с tool_calls предшествует N tool results в том же порядке
    - **Properties 10, 11, 12, 18 | Validates: Req 5.1, 5.3, 5.4, 6.1, 6.2, 7.1, 7.4, 7.5**

  - [x]* 7.3 Unit edge-case тесты Agentic Loop
    - Файл `backend/tests/agent/test_agentic_loop.py`
    - `test_llm_call_limit_raises`: после `AGENT_MAX_LLM_CALLS` → `AgentLimitError`
    - `test_zero_tool_calls_rejected_by_session_guard`: LLM сразу финал без инструментов → feedback, не принимается
    - `test_full_happy_path`: mock LLM: get_user_profile → search → validate (success) → final JSON с тем же hash → `GeneratedDayResult` с `quality_status="valid"`
    - `test_tool_exception_error_format`: исключение в `dispatch` → Tool Error с `code: "TOOL_EXECUTION_ERROR"`
    - `test_mode_logged`: `generate_day_plan` логирует `"mode=tool_use"` или `"mode=pipeline"`
    - `test_agentic_loop_disabled_raises`: `_run_agentic_loop` при `AGENT_TOOL_USE_ENABLED=False` → `AgentConfigurationError`
    - `test_summary_log_on_completion`: INFO-лог содержит число LLM-вызовов и счётчики инструментов

- [x] 8. Рефакторинг `generate_day_plan`
  - [x] 8.1 Выделить текущий pipeline в `_run_pipeline` и обновить `generate_day_plan`
    - Перенести тело `generate_day_plan` в `_run_pipeline` без изменений логики
    - Добавить в `generate_day_plan` параметр `db_session` (только для tool-using ветки — проверить как Celery-задача вызывает оркестратор)
    - Ветвление: `if settings.AGENT_TOOL_USE_ENABLED: return await _run_agentic_loop(...)` иначе `return await _run_pipeline(...)`
    - Логировать INFO с `"mode=tool_use"` / `"mode=pipeline"` до ветвления
    - Сигнатура `generate_day_plan` и тип `GeneratedDayResult` — без изменений
    - _Requirements: 10.1–10.6_

  - [x]* 8.2 Тест Property 15: обратная совместимость pipeline
    - Файл `backend/tests/agent/test_orchestrator_compat.py`
    - Hypothesis: произвольные `user_profile`, `recipes`, `day_number`
    - `AGENT_TOOL_USE_ENABLED=False`: mock LLM; `ToolExecutor` не создаётся; payload не содержит `"tools"`
    - **Property 15 | Validates: Req 10.2, 10.4**

- [x] 9. Вспомогательные property-тесты (независимые)
  - [x]* 9.1 Тест Property 13: `_normalize_day_totals`
    - Файл `backend/tests/skills/test_normalize.py`
    - Hypothesis: произвольный `DayPlan`; после вызова `plan.total_calories == round(sum(...))`
    - **Property 13 | Validates: Req 8.3**

  - [x]* 9.2 Тест Property 14: round-trip `MealPlanOutput`
    - Файл `backend/tests/schemas/test_round_trip.py`
    - Hypothesis: произвольный валидный `MealPlanOutput`; round-trip через `model_dump_json` / `json.loads` / `model_validate`
    - **Property 14 | Validates: Req 8.1**

  - [x]* 9.3 Тест Property 5B: retriever Safety Filters
    - Файл `backend/tests/agent/test_retriever_safety.py`
    - Hypothesis: непустой список аллергенов; mock retriever вкладывает рецепты с `allergens`; ни один запрещённый аллерген не в результате
    - **Property 5B | Validates: Req 3.4**

  - [x]* 9.4 Тест Property 17: `tool_call_trace` полноценно отражает вызовы
    - Файл `backend/tests/agent/test_tool_executor.py`
    - Hypothesis: N случайных вызовов (1–10); `len(trace) == N`; все поля корректны; `args_summary` ≤ 200 символов
    - **Property 17 | Validates: Req 12.3**

- [x] 10. Checkpoint финальный
  - Запустить `pytest backend/tests/ -v --tb=short`
  - Убедиться что существующие тесты не сломаны (обратная совместимость)
  - Проверить `AGENT_TOOL_USE_ENABLED=False` по умолчанию

---

## Notes

- Задачи `*` — опциональные тесты; их реализация нужна, но не блокирует MVP
- `_assess_quality` — **удалена**; единственный источник `quality_status` — `skills.validator.validate_day_plan` в финальной backend-проверке
- `expect_final` → `session_state.last_validated_hash is not None`; не `iteration > 0`
- `AgentIterationLimitError` → `AgentLimitError`; единственный счётчик `llm_call_count`
- `search_call_count` считает попытки ДО retriever, не успехи
- Все Tool errors → `_tool_error(code, message)`; `repr(exc)` только в server logs
- `validate_day_plan` всегда возвращает `errors: list` (пустой или непустой)

## Task Dependency Graph

```json
{
  "waves": [
    {"id": 0, "tasks": ["1.1", "1.2", "1.3"]},
    {"id": 1, "tasks": ["1.4", "2.1"]},
    {"id": 2, "tasks": ["2.2", "3.1"]},
    {"id": 3, "tasks": ["2.3", "3.2", "4.1"]},
    {"id": 4, "tasks": ["4.2", "4.4", "4.6"]},
    {"id": 5, "tasks": ["4.3", "4.5", "4.7", "6.1"]},
    {"id": 6, "tasks": ["6.2", "9.1", "9.2"]},
    {"id": 7, "tasks": ["6.3", "7.1"]},
    {"id": 8, "tasks": ["7.2", "7.3", "8.1"]},
    {"id": 9, "tasks": ["8.2", "9.3", "9.4"]}
  ]
}
```
