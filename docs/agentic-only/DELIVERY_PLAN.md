# Семь этапов и контрольные точки

|Этап|Deliverable|Условие выхода|Текущий статус|
|---|---|---|---|
|1 baseline/docs|Target spec + contract/gap register + защищённый исходный SHA|Текущее отделено от цели, Req10 transition explicit|Документы подготовлены|
|2 characterization|Offline day/week/provider/tools/persistence contract tests + DB checks|Воспроизводимое observed behavior; known failures отдельно от желаемого поведения|Offline и DB наборы готовы; реальный broker crash/redelivery — обязательный gate этапа3|
|3 safety|Authorization, canonical nutrients, atomic persistence/idempotent enqueue|Negative two-user/tamper/commit-publish/redelivery/readback tests PASS|Не начат|
|4 experiment|Boundaries + изолированный candidate + одинаковый scenario corpus|Decision record с correctness, effort, latency, calls/tokens/cost limits|Не начат; runtime не выбран|
|5 production path|Выбранный runtime + один day/week worker/API|Roundtrip/failure/rollout tests; согласованные legacy client migration|Не начат|
|6 legacy cleanup|Точные deleted paths/symbols/route/task manifest|Нет consumers/pending incompatible jobs; regression PASS|Не начат|
|7 DoD|Backend/frontend/migrations/E2E/dependency map/cost/docs report|Нет скрытых блокеров; live checks либо выполнены с бюджетом, либо явно BLOCKED|Не начат|

Каждый этап — отдельно проверяемая порция изменений. Baseline commit и PR#1 не переписывать. Изменения остаются в отдельном worktree; без push/deploy до отдельного указания. Никаких production DB/secrets в тестах.

Эксперимент этапа4 не требует заранее LangGraph: кандидат выбирается после описания boundaries и измеримых требований. Внешнюю библиотеку оценивать по актуальной официальной документации, version pin, dependency/security footprint и compatibility. Provider fixtures одинаковы, реальные domain services одинаковы; сравнивать invalid acceptance, deterministic reproducibility, recovery/idempotency, trace completeness, LLM/search/tool count, tokens/cost (если available), latency и added abstraction surface. Реальный paid experiment не запускать без согласованного бюджета.

Переключение production и удаление возможны только после safety gate и runtime decision. Провал gate не является поводом скрыть error, отключить validation или объявить baseline тест ненужным.
