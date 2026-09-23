# Переход Mealy на agentic-only

Статус: этап 1 подготовлен, для этапа 2 выполнены offline и DB characterization; safety gate ещё не пройден, production не переключён. Решение владельца от 2026-09-23: agentic-only — целевая архитектура. Это не утверждение, что текущий код уже соответствует цели.

- [Целевое поведение](TARGET_SPEC.md)
- [Контракты, baseline и расхождения](CONTRACTS_AND_GAPS.md)
- [Этапы и критерии перехода](DELIVERY_PLAN.md)
- [Characterization и ограничения доказательств](CHARACTERIZATION.md)
- [Результаты проверок 2026-09-23](VALIDATION_2026-09-23.md)
- [Выделение runtime: diff, консолидация и границы удаления](RUNTIME_EXTRACTION.md)

В отдельной порции после characterization выделены runtime/tools/guards и общий day/week loop. Это структурная подготовка: production contract и feature flag не переключены, pipeline/demo ещё достижимы. Проверки и точные commits указаны в отчёте выше.

Baseline приложения: `77c6abfb6c44a25e7469fdb63f5d65bbb0976490`.
Основание этой ветки: `f810bdbd844cfb082e108893996e1809afd8e4ab`, добавляющее только исторический `MEALY_BASELINE_HANDOFF.md`. Отдельная ветка разработки: `codex/mealy-agentic-only`. Baseline-ветка и PR #1 не являются веткой очистки.

Исторические `.kiro/specs/plan-agent-tools/{requirements,design,tasks}.md` описывают двухрежимный baseline. Новая спецификация [TARGET_SPEC.md](TARGET_SPEC.md) задаёт цель перехода и явно заменяет Requirement 10 только для будущего agentic-only production. До прохождения gates сохраняется старое поведение, включая flag OFF, legacy wrappers и demo.

Локальное доказательство исходного аудита: `MEALY_FINAL_AUDIT_HANDOFF.zip`, сформированный 2026-09-23. Не содержит production secrets. Существенная поправка к старому handoff: Git index encrypted backup отличается от старого manifest; project files/Git objects проверены, но полная byte-exact идентичность и восстановление внешней PostgreSQL не подтверждены. Этот архив не является dependency для выполнения тестов.
