# Переход Mealy на agentic-only

Статус: в этой ветке API/Celery/frontend переведены на единый agentic use case; изменения ещё не развёрнуты. Safety gate не пройден, физическое удаление legacy не выполнено. Решение владельца от 2026-09-23: agentic-only — целевая архитектура. Это не утверждение, что выполнены все требования безопасности и release gates.

- [Целевое поведение](TARGET_SPEC.md)
- [Контракты, baseline и расхождения](CONTRACTS_AND_GAPS.md)
- [Этапы и критерии перехода](DELIVERY_PLAN.md)
- [Characterization и ограничения доказательств](CHARACTERIZATION.md)
- [Результаты проверок 2026-09-23](VALIDATION_2026-09-23.md)
- [Выделение runtime: diff, консолидация и границы удаления](RUNTIME_EXTRACTION.md)
- [Переключение API/worker/frontend и совместимость очереди](PRODUCTION_CUTOVER.md)

После выделения runtime/tools/guards и общего day/week loop выполнена отдельная порция переключения production dispatch. Pipeline/demo остаются в коде, но основной API/worker больше не выбирает старые wrappers. Проверки, точные commits и обязательный порядок rollout указаны в последнем отчёте.

Baseline приложения: `77c6abfb6c44a25e7469fdb63f5d65bbb0976490`.
Основание этой ветки: `f810bdbd844cfb082e108893996e1809afd8e4ab`, добавляющее только исторический `MEALY_BASELINE_HANDOFF.md`. Отдельная ветка разработки: `codex/mealy-agentic-only`. Baseline-ветка и PR #1 не являются веткой очистки.

Исторические `.kiro/specs/plan-agent-tools/{requirements,design,tasks}.md` описывают двухрежимный baseline. [TARGET_SPEC.md](TARGET_SPEC.md) задаёт цель перехода. В production use case этой ветки Requirement 10 (flag OFF → pipeline) больше не действует; он сохранён только в старых adapters. Deployment требует отдельного release gate и согласованного обновления workers до API/frontend.

Локальное доказательство исходного аудита: `MEALY_FINAL_AUDIT_HANDOFF.zip`, сформированный 2026-09-23. Не содержит production secrets. Существенная поправка к старому handoff: Git index encrypted backup отличается от старого manifest; project files/Git objects проверены, но полная byte-exact идентичность и восстановление внешней PostgreSQL не подтверждены. Этот архив не является dependency для выполнения тестов.
