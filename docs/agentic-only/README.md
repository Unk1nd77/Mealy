# Переход Mealy на agentic-only

Статус: в этой ветке код API/Celery/frontend переведён на единый agentic use case; legacy generation, demo и CLI wrappers удалены. Это изменение репозитория, **не deployment**; известные safety gaps и реальные broker/DB/live-LLM проверки не закрыты. Исторические отчёты ниже описывают состояние до удаления.

- [Целевое поведение](TARGET_SPEC.md)
- [Контракты, baseline и расхождения](CONTRACTS_AND_GAPS.md)
- [Этапы и критерии перехода](DELIVERY_PLAN.md)
- [Characterization и ограничения доказательств](CHARACTERIZATION.md)
- [Результаты проверок 2026-09-23](VALIDATION_2026-09-23.md)
- [Выделение runtime: diff, консолидация и границы удаления](RUNTIME_EXTRACTION.md)
- [Переключение API/worker/frontend и совместимость очереди](PRODUCTION_CUTOVER.md)

В целевом исполняемом коде остались один runtime и один use case; `generate_meal_plan` выполняет только agentic. Отчёт PRODUCTION_CUTOVER.md ниже фиксирует исторический промежуточный этап; его описание временных aliases больше не является текущим контрактом. Все старые generation workers и старые сообщения должны быть обработаны **до** развёртывания новой версии.

Baseline приложения: `77c6abfb6c44a25e7469fdb63f5d65bbb0976490`.
Основание этой ветки: `f810bdbd844cfb082e108893996e1809afd8e4ab`, добавляющее только исторический `MEALY_BASELINE_HANDOFF.md`. Отдельная ветка разработки: `codex/mealy-agentic-only`. Baseline-ветка и PR #1 не являются веткой очистки.

Исторические `.kiro/specs/plan-agent-tools/{requirements,design,tasks}.md` описывают двухрежимный baseline. [TARGET_SPEC.md](TARGET_SPEC.md) задаёт цель перехода. В production use case Requirement 10 (flag OFF → pipeline) больше не действует; старые adapters и переключатель удалены. Deployment требует отдельного release gate и согласованного обновления workers до API/frontend.

Локальное доказательство исходного аудита: `MEALY_FINAL_AUDIT_HANDOFF.zip`, сформированный 2026-09-23. Не содержит production secrets. Существенная поправка к старому handoff: Git index encrypted backup отличается от старого manifest; project files/Git objects проверены, но полная byte-exact идентичность и восстановление внешней PostgreSQL не подтверждены. Этот архив не является dependency для выполнения тестов.
