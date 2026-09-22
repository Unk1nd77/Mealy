# Mealy: backup and reproducible audit baseline handoff

Дата фиксации: 2026-09-22 (Asia/Yerevan).

Этот документ описывает фактически проверенное состояние. Он не является заключением о корректности приложения и не разрешает удалять legacy-код или иные файлы.

## 1. Исходная точка

Перед операциями записи были повторно проверены Git, файловая система и запущенные контейнеры.

| Параметр | Фактическое значение |
|---|---|
| Исходный каталог | `/Users/dmitriy/Downloads/Диплом` |
| Исходная ветка | `audit/mealy` |
| Исходный HEAD | `649493dd1accb3b34dde71b1a8501bfc321280d0` |
| Working tree до backup/snapshot | 40 modified, 6 deleted, 60 untracked, 0 staged (106 путей) |
| Размер каталога | около 2.2 GiB, включая `.git` около 157 MiB |
| Свободное место перед backup | около 15 GiB |
| FileVault | выключен; поэтому backup создан как отдельно зашифрованный disk image |

Предварительное утверждение о `main` не подтвердилось. На момент фиксации default remote ref — `origin/HEAD -> origin/master`; `origin/main` отсутствует. Важные refs:

- `origin/master` -> `a9f57f594d2aecf558892571b047227a4f584fbe`;
- `origin/audit/mealy` -> `649493dd1accb3b34dde71b1a8501bfc321280d0`;
- локальная `master` -> `dea86e3c3079b6acc5186bcbbaa96a72fb4b8c00` и отстаёт от `origin/master` на 19 commits;
- локальная `wip/agent-cli-catalog-runtime` -> `649493dd1accb3b34dde71b1a8501bfc321280d0`;
- `origin/wip/agent-cli-catalog-runtime` -> `b50372c82552cff477e1c2cd8650a9de8ae9008d`;
- отдельный remote-tracking ref `mealy-private/master` -> `aeb6f45196aca677a90a5c828de04058ce448826`.

Незавершённых merge, rebase или cherry-pick перед snapshot не было.

## 2. Независимый защищённый backup

Полная копия исходного состояния находится вне рабочего репозитория:

`/Users/dmitriy/Documents/MealySecureBackup-2026-09-22.sparsebundle`

Свойства backup:

- sparsebundle защищён AES-256 на уровне disk-image wrapper;
- пароль не записан в репозиторий и не выводился в журналы; он сохранён в login Keychain под service `MealySecureBackup-2026-09-22T153656+0400`;
- внешний каталог sparsebundle принадлежит текущему пользователю и имеет mode `0700`;
- занимаемый размер после завершения — около 2.4 GiB;
- образ после проверки размонтирован;
- `mealy-backend-1` и `mealy-celery_worker-1` были остановлены только на время консистентного копирования и после проверки возвращены в состояние `Up`; `mealy-db-1` и `mealy-redis-1` не удалялись и не пересоздавались.

Внутренняя структура образа:

- `Mealy-pre-astra-20260922T153656+0400/repository` — полная копия каталога;
- `Mealy-pre-astra-20260922T153656+0400/verification` — inventories и результаты проверок;
- `Mealy-pre-astra-20260922T153656+0400/mealy-reachable-refs.bundle` — дополнительный Git bundle достижимых refs.

### Доказательства целостности

`BACKUP_VERIFIED=true` был записан только после завершения проверок, в `2026-09-22T16:19:12+04:00`.

- SHA-256 inventory совпал для 28,218 сравнимых объектов.
- Типы файлов, размеры, modes, uid/gid, timestamps и symlink targets совпали.
- Начальный и финальный inventories источника совпали: источник не менялся во время копирования.
- Списки HEAD, refs, Git status и unreachable Git objects источника и копии совпали.
- В копии успешно выполнен `git fsck --full --no-reflogs --unreachable`.
- Созданный bundle успешно прошёл `git bundle verify` и содержит complete history для включённых достижимых refs.
- Все 930 исходных extended attributes, кроме системного provenance-класса, совпали по именам и значениям.
- Реальные ACL entries отсутствовали и в источнике, и в копии.

Документированные исключения, не являющиеся потерей проектных данных:

1. `.git/fsmonitor--daemon.ipc` — runtime Unix socket Git daemon — намеренно не копировался как переносимый файл. Он пересоздаётся Git и исключён из обоих checksum inventories.
2. APFS автоматически добавил 39 атрибутов `com.apple.provenance` в копии. Все исходные содержательные xattrs при этом присутствуют и совпадают.
3. Встроенный в macOS старый `rsync` с `-E` создавал AppleDouble sidecars и потому был отвергнут как checksum-verifier. Итоговое сравнение выполнено без этого режима, а xattrs проверены отдельным inventory.
4. В APFS volume, смонтированном с `noowners`, служебное изменение owner/group одного verification-файла вернуло `Operation not permitted`; сам файл был записан, а uid/gid исходных проектных объектов уже были независимо сравнены и совпали.

Полный backup отражает состояние **до** создания snapshot commit. Сам snapshot commit не нужен для восстановления содержимого: те же tracked, untracked и ignored файлы находятся в полной копии, а Git history до исходного HEAD и unreachable checkpoint objects сохранены.

## 3. Git snapshot

Уникальный старый commit защищён локальным ref:

`codex/archive/origin-master-a9f57f5` -> `a9f57f594d2aecf558892571b047227a4f584fbe`

Создана ветка:

`codex/wip/mealy-audit-baseline-2026-09-22`

Snapshot текущей разработки:

`77c6abfb6c44a25e7469fdb63f5d65bbb0976490` — `chore: capture pre-Astra audit baseline`

Parent snapshot-коммита: `649493dd1accb3b34dde71b1a8501bfc321280d0`. В commit вошёл 101 путь: 40 modified, 55 added, 6 deleted; 5,925 insertions и 2,571 deletions. Push не выполнялся.

Перед commit staged content был проверен на высокосигнальные шаблоны секретов: совпадений не найдено. `.env`, `tfstate`, `tfplan`, реальные `tfvars`, приватные конфиги, caches и Office lock-файлы не добавлялись.

### Включённые категории

| Категория | Путей | Содержание |
|---|---:|---|
| Backend | 55 | API, config, agent/legacy pipelines, catalog/RAG/embeddings, worker, DB models/session, Alembic, scripts и tests |
| Terraform | 32 | bootstrap, dev environment, ECR/ECS maintenance/ElastiCache/network/RDS/secrets modules и lockfiles |
| Agent specification | 4 | `.kiro/specs/plan-agent-tools` |
| Root config/docs | 4 | `.env.example`, `.gitignore`, `README.md`, `docker-compose.yml` |
| Намеренные удаления | 6 | старые PDF/PPTX, перечисленные ниже |

Полный воспроизводимый manifest включённых путей получается командой:

```bash
git -c core.quotepath=false diff-tree --no-commit-id --name-status -r 77c6abfb6c44a25e7469fdb63f5d65bbb0976490
```

Особенно важные ранее untracked additions: новые Alembic migrations для pgvector/embedding index, `catalog_agent_tools.py`, `embeddings.py`, catalog import/export/backfill/verification scripts, agent/runtime/catalog/embedding/integration tests, Terraform tree и agent-tool specs.

### Намеренные удаления

Пользователь отдельно подтвердил, что все шесть удалений сделаны намеренно и должны войти в snapshot:

- `Mealy_Презентация5.pdf`;
- `Mealy_Презентация5.pptx`;
- `Агарунов_Презентация (4).pdf`;
- `Агарунов_Презентация.pptx`;
- `Диплом (2).pdf`;
- `Диплом (2).pptx`.

Их версии до удаления остаются в parent commit и в полной backup-копии.

### Исключённые из snapshot файлы

Следующие пять untracked paths остались в working tree и не входят в snapshot:

- `audit-results/backend-pytest.xml`;
- `audit-results/static-analysis.md`;
- `audit-results/summary.md`;
- `~$Mealy_Презентация6.pptx`;
- `~$Шахов Д.А. презентация ВКР.pptx`.

Первые три являются результатами предыдущего аудита с неустановленной актуальностью. Последние два — Office lock-файлы. Они сохранены в полной backup-копии и не удалены из исходного каталога.

## 4. Baseline verification

Проверки выполнялись не в рабочем дереве, а в checkout, полученном через `git archive` именно из commit `77c6abf`, по пути `/tmp/mealy-baseline-verification.cMNjF9`. В checkout не переносились `.env`, ignored secrets и production state. Пакеты не устанавливались. Для frontend временно использовался существующий `node_modules` через symlink внутри изолированного checkout; для backend — существующий `.venv`, но working directory и исходники были из snapshot checkout.

| Проверка | Результат | Детали |
|---|---|---|
| Backend pytest | PASS | 196 passed, 2 deselected; `integration` и `live_source` исключены; отдельный ephemeral Redis без volume |
| Backend Ruff | FAIL | 4 diagnostics: `UP037`, `RET504`, два `I001` |
| Frontend lint | PASS | exit 0 |
| Frontend format check | FAIL | 19 файлов требуют форматирования; fixes не применялись |
| Frontend TypeScript | FAIL | 84 `TS` errors в 15 файлах |
| Frontend Astro build | PASS | 1 static page собрана успешно |
| Alembic heads | PASS | единственный head `e8f9a0b1c2d3` |
| Alembic fresh upgrade | PASS | вся цепочка применена к новой ephemeral `pgvector/pgvector:pg16` базе |
| Alembic current | PASS | база достигла `e8f9a0b1c2d3 (head)` |
| Alembic schema check | FAIL | model/schema drift: 19 `modify_nullable`, 23 `remove_index`, 11 `remove_constraint` operations |

Первая пробная pytest-команда использовала намеренно недоступный Redis endpoint и дала 2 failures в `tests/test_demo_pipeline.py` при cache writes. Повтор с отдельным ephemeral Redis прошёл полностью (196 passed), поэтому эти два первоначальных падения не считаются подтверждёнными дефектами кода.

Ruff diagnostics:

- `backend/app/core/demo_pipeline.py:619` — `UP037`;
- `backend/app/core/demo_pipeline.py:648` — `RET504`;
- `backend/app/core/skills/aggregator.py:3` — `I001`;
- `backend/tests/test_auth_api.py:3` — `I001`.

Файлы, отмеченные frontend formatter:

- `src/components/mealy/BottomNav.tsx`;
- `src/components/mealy/controller/useMealyCommands.ts`;
- `src/components/mealy/controller/useMealyController.ts`;
- `src/components/mealy/formatters.ts`;
- `src/components/mealy/observabilityFormatters.ts`;
- `src/components/mealy/screens/GeneratingScreen.tsx`;
- `src/components/mealy/screens/HomeScreen.tsx`;
- `src/components/mealy/screens/OnboardingScreen.tsx`;
- `src/components/mealy/screens/ProfileScreen.tsx`;
- `src/components/mealy/screens/RecipeScreen.tsx`;
- `src/components/mealy/screens/ShoppingScreen.tsx`;
- `src/components/mealy/screens/WeeklyScreen.tsx`;
- `src/components/mealy/screens/onboardingSteps.tsx`;
- `src/components/mealy/text.ts`;
- `src/components/mealy/ui/Charts.tsx`;
- `src/components/mealy/ui/feedbackWidgets.tsx`;
- `src/styles/mealy/08-meals.css`;
- `src/styles/mealy/09-detail.css`;
- `src/styles/mealy/15-shell.css`.

TypeScript errors распределены по 15 файлам; наибольшие группы: `onboardingSteps.tsx` (23), `useMealyCommands.ts` (13), `ProfileScreen.tsx` (12), `useMealyController.ts` (12), `BottomNav.tsx` (5). Это baseline-наблюдения, не исправления.

Fresh-database migration test подтверждает исполнимость migration chain, но провал `alembic check` означает, что metadata моделей не полностью описывает схему, созданную migrations. Astra должна анализировать drift до любых предложений удалить indexes/constraints или генерировать новую migration.

Не выполнялись:

- live-source и внешние LLM/network integration tests;
- проверки с production credentials;
- destructive downgrade/upgrade cycles на существующей БД;
- Terraform `plan/apply` и cloud validation;
- push веток или commits.

## 5. Оставшиеся неопределённости и ограничения

Подтверждённые факты отделены от выводов:

- **Факт:** snapshot воспроизводит содержимое текущей разработки и содержит важные ранее untracked production modules, migrations, tests и infrastructure.
- **Факт:** полный pre-snapshot working tree, ignored data и Git objects сохранены в проверенном encrypted backup.
- **Факт:** backend unit/test suite в выбранном безопасном профиле проходит, frontend build проходит, но статические проверки не все зелёные.
- **Факт:** Alembic upgrade новой БД проходит, но schema drift check не проходит.
- **Неизвестно:** являются ли все 84 TypeScript errors следствием одного общего contract mismatch или несколькими независимыми дефектами.
- **Неизвестно:** соответствует ли live-source/LLM поведение ожидаемым внешним API, поскольку secrets и сеть для таких тестов не использовались.
- **Неизвестно:** являются ли три файла в `audit-results/` ценными исходными свидетельствами или устаревшими generated reports; до решения их нельзя удалять.
- **Ограничение:** локальные refs и snapshot не отправлены на remote. Защита от потери машины обеспечена encrypted sparsebundle вне repo, но не off-device копией.

## 6. Инструкция для Astra

Основная точка аудита кода:

`77c6abfb6c44a25e7469fdb63f5d65bbb0976490`

Ветка-указатель:

`codex/wip/mealy-audit-baseline-2026-09-22`

Astra должна:

1. Аудировать именно дерево snapshot commit `77c6abf`; последующий commit с этим handoff-документом, если он присутствует, меняет только документацию.
2. Сравнивать intended behavior с `README.md`, `.kiro/specs/plan-agent-tools/*`, backend contracts и migrations в этом commit, не с произвольной локальной `master`.
3. Учитывать оба generation paths, feature flags, agent runtime, catalog/RAG/embedding path, Celery, API/frontend contracts и Terraform, не считая untested code автоматически dead.
4. Считать `alembic check` drift и 84 TypeScript errors известными baseline-сигналами, требующими анализа, а не разрешением на автоматическое исправление.
5. Не удалять до отдельного решения пользователя: legacy pipeline, три untracked `audit-results/*`, ignored scripts/outputs, sensitive config/state, old checkpoint objects и ref `codex/archive/origin-master-a9f57f5`.
6. Не использовать содержимое encrypted backup как обычный рабочий checkout и не публиковать `.env`, Terraform state/plans/tfvars или приватные конфиги.
7. При необходимости сверки pre-snapshot состояния сначала монтировать sparsebundle с паролем из указанной Keychain service и читать `verification/`; не считать образ непроверенным только из-за того, что он сейчас размонтирован.

## 7. Текущее безопасное состояние

На момент подготовки handoff:

- исходные backend, Celery, DB и Redis containers возвращены в рабочее состояние;
- encrypted backup размонтирован;
- ephemeral Redis/PostgreSQL verification containers удалены;
- source code после snapshot не исправлялся и не форматировался;
- push не выполнялся;
- в working tree остаются только пять перечисленных исключённых untracked files плюс этот handoff-документ до его отдельной фиксации.
