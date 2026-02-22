# План доведения StatProject до экспертного уровня анализа и отчетности

Дата: 2026-02-21
Статус: active execution
Контекст: текущая ветка `/Users/eduardbelskih/Проекты Github/statproject_desktop_test`

## 0) Прогресс по этапам (единый источник правды)

- Этап A: `done` (API `PUT /study_design`, optimistic lock, auto-revoke Design Review, frontend editor, тесты зелёные).
- Этап B: `done` (coverage pass + `coverage_report`, адаптивные лимиты planner, обязательные clinical ветки comorbidity/treatment/dynamics, тесты зелёные).
- Этап C: `done` (введён `cleaning_run` artifact с before/after missingness + fingerprint; `publication execute` требует валидный `cleaning_run`).
- Этап D: `done` (interpretation_contract теперь прикрепляется в execute и рендерится в HTML/DOCX/PDF для inferential/batch/responder блоков).
- Этап E: `done` (figure-pack gate оценивает фактические figure-сигналы из payload + artifacts; captions с ключевыми метриками добавлены в HTML/DOCX/PDF).
- Этап F: `done` (quality gates coverage/interpretation/figure/reproducibility закрыты тестами, включая publication сценарии).
- Этап G: `done` (введён режим `expert_comprehensive`: корректная нормализация mode, расширенные budgets planner, ML-бенчмарк шаги, strict reproducibility/quality gates как для publication).
- Этап P2 (advanced data mining): `done` (итерация 1 + итерация 2 + итерация 3 выполнены: structured report artifacts, frontend controls, e2e-like flow, полный backend regression suite + frontend tests + frontend lint).

Checkpoint для закрытия этапа B:
- Тесты: `backend/tests/test_protocol_rules.py`, `backend/tests/test_prompt_brief.py`, `backend/tests/test_plan_coverage_report.py`, `backend/tests/test_publication_workflow.py`, `backend/tests/test_covid_smoke_v2_flow.py` — passed.
- Фактический ковид-sanity: `publication` planner на датасетах `covid_*` в workspace показал coverage `131/131 (1.0)`.

Checkpoint для закрытия этапа C:
- Новый модуль: `backend/app/modules/cleaning_run.py` (artifact contract + fingerprint + validation).
- Артефакт пишется автоматически из `PipelineManager.create_processed_snapshot(...)`.
- `execute` в publication режиме блокируется без валидного `processed/cleaning_run.json`.
- Тесты: `backend/tests/test_cleaning_run_artifact.py`, `backend/tests/test_publication_workflow.py` — passed.

Checkpoint закрытия этапов D/E/F:
- `v2 execute` теперь гарантированно добавляет `interpretation_contract` в `results_map` и синхронизирует его в list-response.
- Report rendering:
  - HTML: структурный блок интерпретации (`claim/evidence/clinical_meaning/limitations/actionable_next_step`) после каждого аналитического блока.
  - DOCX/PDF: те же поля интерпретации, fallback только при отсутствии контракта.
  - Подписи к графикам с ключевыми числами (`N`, `p`, `effect`, `AUC`, `sig/total`) в HTML/DOCX/PDF.
- Report quality gates:
  - Interpretation gate в publication требует полный `interpretation_contract` (fallback-conclusion недостаточен).
  - Figure gate учитывает не только имена файлов, но и фактические figure-сигналы в payload (`plot_data`, `plot_stats`, `roc`, `correlation_matrix`, `estimated_means`, `by_visit`, и т.д.).
- Тесты:
  - `backend/tests/test_publication_workflow.py` — проверка присутствия полного interpretation_contract в execute.
  - `backend/tests/test_report_quality_checklist.py` — добавлены кейсы на обязательность interpretation_contract и payload-based figure detection.
  - `backend/tests/test_reporting_manuscript_sections.py` — проверка рендера interpretation contract + figure captions в HTML/DOCX.
  - Расширенный прогон: 35 passed.

Checkpoint закрытия этапа G:
- `analysis_mode` теперь корректно поддерживает `comprehensive` и `expert_comprehensive` (раньше `comprehensive` в `v2` нормализовался в `exploratory`).
- Для `expert_comprehensive` включены:
  - усиленные `safe_plan_constraints` и адаптивные лимиты planner;
  - ML-бенчмарк шаги (`random_forest`, `gradient_boosting`) в rules-based протоколе;
  - исполнение ML-методов в `v2 execute` с `task` (classification/regression) и `predictors`;
  - strict gating (design/cleaning/cohort/report quality) на уровне publication-like режима.
- Дополнен `report_spec` для expert: `style=expert`, strict interpretations, расширенные figure/table requirements.
- Тесты:
  - `backend/tests/test_prompt_brief.py` (expert constraints),
  - `backend/tests/test_protocol_rules.py` (ML-бенчмарк и budget expansion),
  - `backend/tests/test_design_review_soft_check.py` (expert mode contract),
  - `backend/tests/test_report_quality_checklist.py` (strict quality для expert),
  - Расширенный прогон: 39 passed.

Checkpoint P2 (итерация 1):
- Добавлены новые методы движка:
  - `bootstrap_pipeline` (устойчивость эффекта и CI через bootstrap),
  - `cluster_profiles` (patient-level clustering + профили кластеров),
  - `external_validation` (оценка модели на внешнем dataset).
- Интеграция в контур:
  - `v2` canonical aliases + execute/protocol routing,
  - rules-based planner (expert) теперь автоматически добавляет P2 steps (включая external validation при явном `external_validation_dataset_id`),
  - обновлён `method_coverage` (python only для новых P2 методов) и `METHOD_COVERAGE_MATRIX`.
- Тесты:
  - `backend/tests/test_advanced_data_mining_p2.py`,
  - `backend/tests/test_protocol_rules.py` (expert P2 step injection),
  - `backend/tests/test_engine_coverage_validation.py` (engine support matrix).

Checkpoint P2 (итерация 2):
- Reporting:
  - HTML: новые P2 шаги (`bootstrap_pipeline`, `cluster_profiles`, `external_validation`) маршрутизируются в полноценные структурные секции (не fallback raw JSON).
  - DOCX/PDF: добавлены отдельные блоки метрик и интерпретации для bootstrap stability, cluster profiles, external validation.
  - Plot rendering: добавлен scatter по `embedding` для `cluster_profiles`; для `external_validation` добавлен fallback calibration plot (если ROC plot отсутствует).
- Frontend:
  - `ProtocolSorcerer`: добавлены UI-контролы
    - `Deep mining` -> `preferences.allow_data_mining`
    - `External validation dataset` -> `preferences.external_validation_dataset_id`
  - Добавлена валидация контрактов chat-протокола для новых методов (`bootstrap_pipeline`, `cluster_profiles`, `external_validation`).
  - Сохранение/восстановление этих параметров через session storage.
- Тесты:
  - backend:
    - `backend/tests/test_reporting_manuscript_sections.py` (P2 structured sections в HTML/DOCX),
    - `backend/tests/test_advanced_data_mining_p2.py` (новый e2e-like plan→execute flow с `external_validation_dataset_id`).
  - frontend:
    - `frontend/src/app/pages/ProtocolSorcerer.test.jsx` (проверка прокидывания deep mining + external validation preferences в `/analysis/plan`).

Checkpoint P2 (итерация 3):
- Stability/QA:
  - Прогнан полный backend regression suite: `238 passed, 6 skipped`.
  - Прогнан полный frontend test suite: `27 passed`.
  - Прогнан frontend lint: `eslint .` без ошибок.
- UX polish:
  - `ProtocolSorcerer`:
    - исправлена блокировка кнопки «Собрать протокол» в `data_prep` режиме (текст теперь не обязателен для перехода в prep),
    - добавлены явные `id/htmlFor/aria-label` для external validation dataset control и deep mining toggle.
  - Убраны неиспользуемые/мёртвые фрагменты в `ProtocolSorcerer.jsx`, влияющие на lint и сопровождение.

Checkpoint P2 (итерация 4):
- Design editor hardening:
  - `ProtocolSorcerer` теперь загружает полный каталог колонок через `GET /datasets/{id}/columns` (с offset/limit) и не зависит только от auto-типизации в profile.
  - В selectors `Numeric outcomes`/`Categorical outcomes` добавлены:
    - полный список переменных (включая вне auto-типизации),
    - фильтр по имени колонки,
    - индикация доступного количества (`filtered / total`).
- Frontend tests:
  - `frontend/src/app/pages/ProtocolSorcerer.test.jsx` дополнен кейсом на загрузку полного column catalog в design selectors.

Checkpoint P2 (итерация 5):
- `/design/:id` и `/ai/:id` (`AnalysisDesign` legacy + AI mode):
  - в оба режима добавлена загрузка полного column catalog через `GET /datasets/{id}/columns` с пагинацией,
  - в legacy mode `columns` теперь мержится с full catalog (fallback metadata), чтобы `VariableWorkspace` и role-selectors видели полный список,
  - в AI mode role-selectors и manual outcome selection используют полный список колонок; в режиме `selected` outcome picker охватывает полный пул переменных + поиск по имени.
- Frontend tests:
  - добавлен `frontend/src/app/pages/AnalysisDesign.test.jsx` (проверка full catalog в AI mode и legacy `/design`),
  - обновлён regression snapshot frontend suite: `29 passed`.

## 1) Почему сейчас результат «неэкспертный»

Ниже не абстрактные тезисы, а конкретные системные причины в текущем коде.

1. Сужение охвата переменных до входа в планирование.
- `SmartScanner` при `total_cols > 500` сканирует случайные 500 колонок (`backend/app/modules/smart_scanner.py:81`).
- AI-контекст дополнительно ограничен `MAX_AI_COLUMNS_DEFAULT = 200` (`backend/app/modules/ai_context.py:11`).
- В prompt brief и design summary есть top-срезы (`outcomes[:20]`, `categorical[:12/15]`, `endpoint_groups[:8/12]`) (`backend/app/modules/ai_context.py:332`, `backend/app/modules/reporting.py:1991`).

2. Планировщик протокола намеренно «режет» ширину анализа.
- Жесткие лимиты `max_steps` (обычно 20), `max_targets` (обычно 60), `max_batch_chunks` (4/8), подгруппы до 30 (`backend/app/modules/protocol_rules.py:450`, `backend/app/modules/protocol_rules.py:451`, `backend/app/modules/protocol_rules.py:459`, `backend/app/modules/protocol_rules.py:698`).
- После генерации шаги еще раз режутся `_dedupe_protocol(..., max_steps)` (`backend/app/modules/protocol_rules.py:313`, `backend/app/modules/protocol_rules.py:920`).

3. Дизайн исследования в основном auto-generated, ручная правка ограничена.
- Есть `GET /datasets/{id}/study_design`, но нет полноценного `PATCH/PUT` контракта редактирования design-артефакта (`backend/app/api/datasets.py:1540`).
- По UI реализован backend-gate confirm/revoke Design Review, но не полноценный «конструктор дизайна» с сохранением полного design-spec.

4. Очистка и пропуски: базовый enforce включен, но политика ещё не полностью publication-grade.
- `execute(publication)` уже требует валидный `cleaning_run` artifact, однако не все ветки очистки унифицированы в единый contract по decision-log.
- Автоочистка есть, но правиловая и ограниченная (median/mode/MICE по порогам) (`backend/app/services/upload_service.py:31`).
- В `analysis_set` только `complete_case` и `simple_impute` (`backend/app/modules/analysis_set.py:273`).

5. Интерпретации в ядре часто шаблонные и неглубокие.
- `TextGenerator` rule-based, с общей фразеологией и ограниченной предметной глубиной (`backend/app/modules/text_generator.py:1`).
- На execute часто срабатывает fallback `_maybe_add_conclusion(...)` вместо расширенного экспертного narrative (`backend/app/api/v2.py:66`, `backend/app/api/v2.py:2542`).
- Discussion/Conclusions агрегируются из коротких step-level блоков (`backend/app/modules/reporting.py:221`).

6. Визуализация неполная для публикационного сценария.
- Рендер в отчете покрывает базовые типы графиков, но не системный набор diagnostics для моделей/динамики (`backend/app/modules/reporting.py:1011`).
- Frontend visualization factory ограничен 3 режимами (`frontend/src/app/components/visualizations/VisualizationFactory.jsx:6`).

7. Quality gate проверяет структуру, а не научную глубину.
- Текущий checklist валидирует наличие секций/файлов, но не качество интерпретации, полноту охвата, обязательные диагностические графики (`backend/app/api/analysis.py:675`).

8. Разрыв между доступными методами и auto-планированием.
- В `stats/engine` есть ML-обработчики (`random_forest`, `gradient_boosting`, `knn`, `svm`) (`backend/app/stats/engine.py:661`), но они не встроены в method coverage matrix и стабильный planning/reporting contract (`backend/app/stats/method_coverage.py:4`).


## 2) Целевое состояние (что считаем «экспертным уровнем»)

1. Coverage: в exploratory/publication анализируется >=95% релевантных outcome-переменных (если пользователь явно не ограничил scope).
2. Reproducibility: фиксированный cohort + cleaning artifact + design artifact обязательны для publication режима.
3. Interpretability: у каждой таблицы и каждой фигуры есть блок интерпретации (stat claim + clinical meaning + ограничение).
4. Visualization: обязательный figure-pack по типу метода (сравнения, корреляции, регрессии, динамика, survival).
5. Manuscript readiness: DOCX/PDF содержит связную data-driven story, а не разрозненные фрагменты.


## 3) План доработки (по этапам)

### Этап A. Контракт дизайна и ручное редактирование design-spec (P0)

Цель: пользователь должен управлять дизайном, а не только подтверждать auto-вариант.

Сделать:
1. Ввести `PUT /api/v1/datasets/{id}/study_design` с валидацией schema-version.
2. Поддержать редактор полей: `design_type`, `group_column`, `time_column`, `subject_column`, `outcomes[]`, `categorical_outcomes[]`, `endpoint_groups[]`, `analysis_policy`.
3. Сохранять change-log для design edit в `delta_log`.
4. Добавить optimistic-lock (`design_version` / `etag`) чтобы не терять правки.
5. На frontend: полноценная форма редактирования design + просмотр coverage до/после.

DoD:
- Из UI можно выбрать/исключить переменные и сохранить.
- `study_design.json` меняется только через валидный API.
- Есть backend+frontend тесты на create/edit/reload/revoke Design Review после edit.


### Этап B. Расширение охвата планировщика (P0)

Цель: убрать системное недопокрытие переменных и методов.

Сделать:
1. Разделить режимы планирования:
- `focused` (лимиты жесткие),
- `comprehensive` (лимиты адаптивные),
- `publication` (высокая полнота + строгие артефакты),
- `expert_comprehensive` (максимальная полнота + ML-бенчмарк + строгие артефакты).
2. Заменить fixed caps на адаптивные от `N cols`, `N outcomes`, `compute budget`.
3. Добавить coverage planner pass: если coverage < target, автоматически добираем недоохваченные outcomes дополнительными пакетами шагов.
4. Вынести «обязательные ветки» для clinical сценариев: comorbidity/treatment/outcomes/dynamics.
5. Согласовать `method_coverage.py` с реальным engine (включая ML/advanced, если они остаются поддерживаемыми).

DoD:
- Для тестового ковид-датасета planner покрывает >=95% целевых outcomes.
- В логах есть явный `coverage_report` по плану.


### Этап C. Cleaning/Cohort pipeline как обязательный артефакт (P0)

Цель: исключить «тихий» анализ грязных данных и дрейф N.

Сделать:
1. Ввести `cleaning_run` artifact (операции, параметры, до/после missingness, fingerprint).
2. В `execute(publication)` требовать:
- confirmed Design Review,
- valid Analysis Set,
- applied Cleaning artifact.
3. Добавить missingness policy по умолчанию:
- high missing non-critical -> исключение из моделей,
- moderate -> imputations,
- low -> локальная простая иммутация,
- все решения логируются.
4. Для динамики: фиксировать правила построения дельт и long/wide преобразований как отдельный artifact.

DoD:
- Без cleaning artifact publication execute отклоняется 4xx.
- В отчете есть таблица Data Quality & Missingness Decision Log.


### Этап D. Экспертные интерпретации и связный narrative (P1)

Цель: каждая таблица/фигура объясняется клинически и статистически.

Сделать:
1. Ввести `interpretation_contract`:
- `claim` (что найдено),
- `evidence` (метрики/CI/p_adj),
- `clinical_meaning`,
- `limitations`,
- `actionable_next_step`.
2. Убрать зависимость от generic fallback conclusion для publication; вместо этого требовать block-level interpretation.
3. Собирать Discussion не как список фраз, а как «исследовательский сюжет»: question -> evidence -> mechanism hypotheses -> implications.
4. Для ковида: шаблонные доменные блоки (исходы, гликемия, коморбидность, терапия, динамика).

DoD:
- В report quality появляются проверки на заполненность interpretation_contract.
- В DOCX/PDF после каждого statistical block есть интерпретация.


### Этап E. Визуализация уровня публикации (P1)

Цель: отчеты содержат обязательный набор информативных графиков.

Сделать:
1. Figure-pack по методам:
- Group comparisons: distribution + pairwise forest/CI.
- Correlation: matrix + network/cluster view.
- Logistic/ML: ROC + calibration + confusion matrix + feature importance.
- Regression: coefficient plot + residual diagnostics.
- Repeated measures: trajectory + delta waterfall/forest.
- Survival: KM + risk table.
2. Включить figure requirements в report gate как обязательные в publication.
3. Добавить подписи к фигурам (caption) с ключевыми числами.

DoD:
- В publication report нет «пустых» визуальных разделов.
- Для каждого ключевого метода есть минимум 1 диагностический график + 1 summary график.


### Этап F. Quality gates и тестирование «по смыслу» (P0)

Цель: перестать принимать формально «полный», но слабый отчет.

Сделать:
1. Расширить `report quality`:
- coverage gate,
- interpretation completeness gate,
- figure completeness gate,
- reproducibility gate (design+cleaning+cohort fingerprints).
2. Добавить e2e golden tests на «ковид-гликемия» сценарий.
3. Ввести минимальные метрики качества:
- outcome coverage,
- доля блоков с интерпретацией,
- доля обязательных figures,
- consistency checks (N, p_adj, CI).

DoD:
- E2E публикационный сценарий стабильно проходит.
- Regression suite ловит деградации интерпретаций/визуализации/coverage.


## 4) Приоритеты внедрения

1. P0 (обязательно до «деплоя по назначению»): Этапы A, B, C, F.
2. P1 (сильно повышает ценность): Этапы D, E.
3. P2: расширение advanced data mining (bootstrap pipelines, clustering profiles, external validation datasets).


## 5) Рекомендуемый порядок спринтов

Спринт 1:
1. API редактирования study_design + frontend editor (Этап A).
2. Базовый coverage report в planner (часть Этапа B).

Спринт 2:
1. Адаптивный planner + coverage completion pass (Этап B).
2. Cleaning artifact + publication enforce (Этап C).

Спринт 3:
1. Новый interpretation_contract + report assembly (Этап D).
2. Figure-pack для приоритетных методов (Этап E, core набор).

Спринт 4:
1. Расширенный report quality gate + e2e golden tests (Этап F).
2. Полировка UX и стабильности для desktop/web.


## 5.1) Анти-циклический протокол исполнения (чтобы не ходить по кругу)

1. Единый источник правды по прогрессу.
- Использовать только этот файл как master-plan.
- У каждого этапа один статус: `pending | in_progress | done | blocked`.

2. WIP limit = 1 этап.
- Одновременно в `in_progress` может быть только один этап (например, только A).
- Переход к следующему этапу только после формального `DoD` текущего.

3. Жесткие exit criteria.
- Этап считается завершенным только при выполнении всех `DoD` + прохождении тестов этапа.
- Формулировки «почти готово», «частично» не дают права двигаться дальше.

4. Запрет на rework без триггера.
- Возврат к уже закрытому этапу только если:
  - найден регрессионный баг, или
  - не пройден quality gate, или
  - изменился продуктовый requirement.
- Любой возврат фиксируется как отдельный defect/task с причиной.

5. Gate-review в конце каждого этапа.
- Короткий checkpoint-отчет: что сделано, какие тесты пройдены, какие файлы/эндпоинты изменены.
- Без checkpoint этап не закрывается.

6. Никаких «архитектурных перепрыгов».
- Нельзя начинать D/E (интерпретации/визуализация), пока не закрыты A/B/C/F(P0-часть).
- Это убирает бесконечные косметические улучшения поверх нестабильного ядра.

7. Контроль покрытия как число, а не ощущение.
- На каждом запуске фиксировать: `coverage_outcomes`, `n_required_figures`, `n_interpreted_blocks`, `reproducibility_pass`.
- Решения принимаются только по этим метрикам.


## 6) Риски и как их снять

1. Риск: рост времени расчета при comprehensive coverage.
- Митигировать: budget-aware chunking + прогресс + background execution + resume.

2. Риск: «слишком длинные» отчеты.
- Митигировать: dual output: full appendix + concise manuscript body.

3. Риск: LLM нестабилен по стилю.
- Митигировать: строгий JSON contract для интерпретации + deterministic post-processor.

4. Риск: конфликт между ручным и авто-дизайном.
- Митигировать: приоритет manual design; auto только как draft + diff preview.


## 7) Минимальный критерий готовности к деплою «по назначению»

1. Publication workflow не стартует без 3 артефактов: Design Review + Cleaning Run + Analysis Set.
2. Coverage >=95% по целевым outcomes (или явное user-ограничение зафиксировано).
3. У каждой обязательной таблицы/фигуры есть интерпретация.
4. Отчет проходит расширенный quality gate (не только структурный).
5. Есть стабильный e2e тест на ковид-сценарий с логистическими моделями исходов (ОРИТ/смерть/новый СД при наличии endpoint).


## 8) Исполнительный режим на ближайшие шаги (без зацикливания)

1. Сразу стартуем Этап A (API редактирования `study_design` + UI).
2. После merge Этапа A — сразу Этап B (coverage planner + completion pass).
3. После merge Этапа B — сразу Этап C (cleaning artifact enforce).
4. После C выполняется этапный gate-review; если pass — переходим к F (quality gates).
5. Только после закрытия A+B+C+F начинаем D и E.
