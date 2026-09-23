# Проверка первого блока перехода

Ветка: `codex/mealy-agentic-only`, основание `f810bdbd844cfb082e108893996e1809afd8e4ab`.
Работа выполнялась в отдельном worktree. Commits/push/deploy не выполнялись. Production application code, frontend и миграции не изменены.

|Проверка|Результат|
|---|---|
|Offline full, fixed Hypothesis seed20260923|221 passed,4deselected,6.71s|
|Fresh pgvector upgrade + storage/vector checks|Upgrade PASS,3passed,0.59s|
|Ruff новых scripts/tests|PASS|
|Format check новых6 Python files|PASS|
|Общий Ruff app/tests|Прежние4 diagnostics, новых нет|
|git diff --check|PASS|
|Исходная baseline-ветка|HEAD f810bdb прежний, прежние untracked audit/Office files|
|Production containers|backend/worker/db/redis running, не перезапускались|
|Одноразовые containers|Созданные runner Redis/PostgreSQL остановлены и удалены; synthetic данные discarded|

Локальные raw evidence (temporary OS storage; не production данные):

- Offline: `/var/folders/th/9hm5fbkd2wscr_kv0pykttg80000gn/T/mealy-agentic-characterization-oc2kxfls/` — run.json, pytest.log, pytest.xml.
- DB: `/var/folders/th/9hm5fbkd2wscr_kv0pykttg80000gn/T/mealy-agentic-characterization-lq_rrgel/` — те же файлы и alembic-upgrade.log.

Не полагаться на бессрочное хранение temp: повторяемые команды и сами tests находятся в Git worktree. Артефакты не включают production secrets. Результаты обновлять после изменения runtime или tests.

Этап1: целевая спецификация и реестр20 контрактов/расхождений подготовлены. Этап2: добавлено25 offline cases и2 реальных DB cases; 150 compatibility combinations выполняются внутри5 параметризованных cases. Это не247 отдельных новых тестов.

Пять safety gaps воспроизведены без исправления production кода: anonymous cached read, nutrients tampering, publish-before-run, cache-after-commit failure, metadata loss on DB readback. Internal invalid mode fallthrough также зафиксирован. Следующий блок — этап3; этапы4–7 не выполнены, agentic-only production ещё нет.
