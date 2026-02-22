# Архитектурный план доработки Clinimetria (2026-02-07, reworked)

## 1. Формулировка идеи приложения

Clinimetria — это исследовательская AI-платформа для клинических и биомедицинских данных, где:
1. пользователь загружает «грязную» таблицу;
2. система делает воспроизводимую подготовку данных;
3. система строит и показывает формализованный дизайн исследования;
4. пользователь подтверждает или правит дизайн;
5. детерминированный статистический движок (Python или R) исполняет протокол;
6. AI формирует интерпретацию и публикационный отчёт по результатам.

Ключевая идея: AI отвечает за планирование и интерпретацию, а вычисления выполняются контролируемым engine с повторяемым результатом.

## 2. Обзор кода: текущее состояние

### 2.1 Что уже хорошо работает

- Есть pipeline артефактов `source -> processed -> analysis`.
- Есть автоматическая очистка, `scan_report`, `semantics`, `study_design`.
- Есть LLM-планирование (`/api/v2/analysis/plan`) и execution (`/api/v2/analysis/execute`).
- Есть блок Design Review в Copilot и enforcement подтверждения дизайна.
- Есть dual-engine подход (Python/R) и базовый выбор engine в UI.
- Есть база знаний (upload/catalog/search/route) и тесты на критичные модули.

### 2.2 Найденные архитектурные проблемы (актуально)

- `P1`: в системе по-прежнему несколько параллельных API-путей для дизайна/планирования.
  - `backend/app/api/v2.py`
  - `backend/app/api/ai_module.py`
  - `backend/app/api/analysis.py`
- `P1`: фронт одновременно поддерживает canonical Copilot и legacy AnalysisDesign/ProtocolSorcerer, что повышает вероятность регрессий.
  - `frontend/src/app/pages/AnalysisDesign.jsx`
  - `frontend/src/lib/api.js`
- `P1`: матрица parity Python/R уже зафиксирована, но покрытие и единый контракт результата ещё не доведены до целевого уровня на всех сценариях.
- `P2`: knowledge ingestion должен быть защищён не только page-limit, но и по объёму extraction/трассировке причин truncation.
  - `backend/app/modules/knowledge_store.py`
- `P2`: отчётный слой пока неоднороден и не валидирует полноту секции Design/Methods как жесткий quality-gate.

### 2.3 Что уже закрыто из предыдущих рисков

- Исправлен баг `unique_ratio` в `study_design`.
- Убраны дубли пересборки design при ingest.
- Добавлен enforcement `design_confirmed` перед execute с конфигом `CLINIMETRIA_REQUIRE_DESIGN_REVIEW`.
- Добавлена deprecation telemetry для legacy endpoint’ов и защищённый endpoint снимка telemetry.

## 3. Целевая архитектура (golden path)

Единый поддерживаемый workflow:
1. `Upload` -> `Clean/Scan` -> `dataset_semantics.json` -> `study_design.json`.
2. `Design Review` (обязательное подтверждение).
3. `Plan` (`POST /api/v2/analysis/plan`).
4. `Execute` (`POST /api/v2/analysis/execute`, `engine=python|r`).
5. `Report` (единый генератор + экспорты).

Принципы:
- LLM не исполняет вычисления напрямую.
- Протокол и результаты всегда сохраняются как артефакты запуска.
- Все legacy пути либо адаптируются к canonical service, либо удаляются по telemetry.

## 4. Контракты, которые нужно зафиксировать

### 4.1 StudyDesignV2

Обязательные поля:
- `design_type`
- `roles` (`group`, `time`, `subject`)
- `outcomes` / `categorical_outcomes`
- `endpoint_groups`
- `analysis_policy`
- `confidence`, `warnings`, `source`

### 4.2 ProtocolPlanV2

Обязательные поля:
- `protocol_name`
- `globals`
- `protocol[]`
- `notes[]`
- `quality`

### 4.3 AnalysisResultV2

Обязательные поля:
- `method_id`
- `engine`
- `stat_value`, `p_value`
- `effect_size`
- `diagnostics`
- `warnings`
- `plots[]` (если метод визуализируемый)

## 5. LLM-политика по умолчанию

- Дефолтная модель для всех ролей: `google/gemini-2.5-flash`.
- Любой role override должен явно показываться в UI и логироваться в run metadata.
- Планировщик получает метаданные/агрегаты/семантику, но не сырые персональные строки по умолчанию.

## 6. Дорожная карта доработки

## Фаза A. Consolidate API and UX (P1)

Цель: убрать дубли веток и оставить один рабочий путь.

Задачи:
1. Перевести фронт на canonical методы `analysisPlan + executeProtocolV2` во всех новых экранах.
2. В legacy страницах заменить прямые `fetch` на adapter из `frontend/src/lib/api.js`.
3. Все deprecated endpoint’ы оставить как shim-слой c записью telemetry.
4. Ввести release-правило удаления legacy: 0 вызовов за 2 релизных цикла.

DoD:
- нет прямых вызовов legacy API из active UI;
- deprecated роуты не содержат уникальной бизнес-логики.

## Фаза B. Design-first enforcement (P1)

Цель: сделать дизайн исследования обязательным артефактом до вычислений.

Задачи:
1. Валидировать, что execute получает подтверждённый Design Review или явный bypass в advanced режиме.
2. Добавить в отчёт обязательный раздел `Design` с source-of-truth из `study_design.json`.
3. Добавить warning/error, если секция дизайна не заполнена.
4. Сохранить timestamp подтверждения дизайна и actor в metadata.

DoD:
- запуск без design confirmation невозможен в стандартном режиме;
- каждый отчёт содержит заполненную секцию Design.

## Фаза C. Knowledge safety and scalability (P2)

Цель: безопасная индексация больших документов.

Задачи:
1. Ограничить extraction по страницам/байтам/символам и фиксировать причину truncation.
2. Логировать extraction metrics (`pages_read`, `chars_extracted`, `truncated_reason`).
3. Добавить тесты stress-профиля для `MAX_PDF_PAGES=0`.
4. Подготовить этап 2: offline-индексация в компактные markdown/summary карточки.

DoD:
- ingestion не приводит к неограниченному росту памяти;
- по каждому документу есть диагностика extraction.

## Фаза D. Python/R parity program (P1 -> P2)

Цель: функционально равные движки.

Задачи:
1. Зафиксировать `Method Coverage Matrix` (один источник истины).
2. Сделать единый adapter результатов и типизацию выходного payload.
3. Для каждого метода иметь engine-specific тесты + cross-engine consistency тест.
4. Закрыть пробелы parity до 100% по матрице.

DoD:
- смена engine не ломает контракт результата;
- покрытие методов подтверждено тестами.

## Фаза E. Publication-grade reporting (P2)

Цель: отчёты уровня «вставить в статью».

Задачи:
1. Унифицировать таблицы (описательные + инференциальные + множественные сравнения).
2. Добавить экспорт финального аналитического датасета, который реально использовался в расчёте.
3. Ввести quality-gate отчёта перед DOCX/PDF export.
4. Доработать графики до публикационного стиля единообразно для Python и R.

DoD:
- отчёт структурно стабилен для manuscript workflow;
- таблицы и графики соответствуют единому формату.

## 7. Тестовая стратегия

Обязательные наборы:
1. `ingest -> clean -> scan -> semantics -> design` e2e.
2. Design override round-trip.
3. Plan regression (rules + LLM constraints).
4. Execute parity Python/R.
5. Report generation (html/docx/pdf).
6. Knowledge ingestion stress (large PDF, limits).

Обязательные датасеты:
- COVID (реальный);
- repeated measures (long);
- repeated measures (wide);
- высокоразмерный numeric для data-mining шагов.

## 8. KPI

Продуктовые:
- `time_to_first_report`;
- доля запусков без ручной правки протокола;
- доля протоколов с quality выше целевого порога.

Инженерные:
- crash-free rate;
- p95 latency `plan` и `execute`;
- memory ceiling ingestion/reporting;
- Python/R parity score.

## 9. Исполняемый бэклог (следующий спринт)

1. Удалить неиспользуемые legacy-ветки UI после перехода `ProtocolSorcerer` на canonical v2.
2. Довести parity-gap минимум по топ-10 методам, используемым в COVID сценарии.
3. Добавить в отчёт экспорт финального расчётного датасета (`xlsx` + `parquet`) как артефакты run.
4. Запустить e2e smoke на COVID: ingest -> design -> plan -> execute(py/r) -> report.

## 10. Статус на текущий момент (после обновления)

Сделано:
1. Design confirmation enforcement и metadata в execute.
2. Legacy telemetry (с token protection) для контролируемого удаления устаревших веток.
3. Базовые тесты Design Review и telemetry.
4. Safety-лимиты knowledge ingestion + метрики extraction для PDF.
5. `AnalysisDesign` переведён с прямых `fetch` на canonical `lib/api` (`analysisPlan`, `executeProtocolV2`, `getAnalysisTemplates`, `designAnalysisFromTemplate`).
6. Добавлен report quality-gate на уровне генератора: HTML/DOCX всегда показывают секцию Design и warning при отсутствии/повреждении `study_design.json`.
7. Добавлены тесты на quality-gate отчёта: `backend/tests/test_reporting_design_quality.py`.
8. Добавлен hard-cap для PDF ingestion даже при отключенных soft-лимитах (`CLINIMETRIA_KB_PDF_HARD_MAX_CHARS_PER_FILE`) + тест на unbounded-сценарий.
9. Удалены остатки legacy-термина старого мастера из активного кода и маршрутов; каноничное имя пользовательского потока: `Sorcerer`.
10. `ProtocolSorcerer` переведён на единый путь выполнения через `executeProtocolV2`; legacy `/sorcerer/apply` убран из активного сценария этого экрана.
11. Включён hard-gate экспорта по дизайну (`CLINIMETRIA_REPORT_HARD_GATE_DESIGN`): при отсутствии/поломке `study_design.json` экспорт DOCX/PDF блокируется.
12. Добавлена и зафиксирована `Method Coverage Matrix` (`docs/METHOD_COVERAGE_MATRIX.md` + `backend/app/stats/method_coverage.py`) и runtime-валидация совместимости `method x engine` в `v2/analysis/execute`.
13. Добавлены тесты: `backend/tests/test_report_design_gate.py`, `backend/tests/test_engine_coverage_validation.py`, `backend/tests/test_v2_method_aliases.py`.
14. Из `ProtocolSorcerer` удалён мёртвый локальный путь визуализации/экспорта; экран оставлен в run-based формате (launch -> `run_id` -> `/results`).
15. Добавлены parity-тесты top-10 методов (`backend/tests/test_engine_parity_top10.py`): базовый контракт Python + cross-engine проверка Python/R с auto-skip при недоступном R.
16. В `ProtocolSorcerer` добавлен явный шаг `Design Review` перед запуском: переход на `/design/:id`, ручное подтверждение и передача `design_confirmed` в execution globals только после подтверждения.
17. Закрыт parity-gap для `clustered_correlation` в R: добавлен расчёт в `r_engine.R`, payload-plumbing в `r_engine.py`, и включён runtime-routing `engine=r` в `POST /api/v1/v2/protocol` и `POST /api/v1/v2/analysis/execute`.
18. Укреплён единый контракт `AnalysisResultV2`: приоритет canonical `method_id`, alias-нормализация method-id, расширенный inference `plots[]` (image/heatmap/matrix/roc/dendrogram), гарантированное заполнение `method.name`.
19. Расширены контрактные тесты результата для веток `v2`: `mixed-effects`, `clustered-correlation`, `protocol`, плюс execute/run/reporting regression.
20. Добавлен parity-регресс для advanced batch-веток в `analysis/execute` с `engine=r`: `batch_analysis`, `timepoint_batch_analysis`, `delta_batch_analysis`, `paired_wide` (`backend/tests/test_engine_parity_advanced_batch_modes.py`).
21. Экран `Analyze` переведён на canonical execution path: `runBatchAnalysis` теперь использует `POST /api/v2/analysis/execute` (step `batch_analysis`) через adapter-совместимый ответ; прямой вызов legacy `/analysis/batch` убран из active UI.
22. В `Analyze` добавлен backend-backed `Design Review` gate (status + confirm/revoke + блокировка запуска без подтверждения).
23. Добавлен метод `responders` в `v2` (`/protocol` и `/analysis/execute`) с нормализованным `AnalysisResultV2` payload и покрыт тестами; в coverage matrix зафиксировано `responders: python=yes, r=yes`.
24. Legacy UI-route `/auto-analyst` выведен из active-пути: добавлен redirect на canonical `/copilot` (без поддержки параллельного legacy execution flow в основном маршруте).
25. Унифицирован `AnalysisResultV2`-контракт на legacy result/reporting ветках: `POST /api/v1/analysis/run` и `POST /api/v1/analysis/batch` теперь возвращают обязательные поля (`method_id`, `engine`, `diagnostics`, `warnings`, `plots`) через единый normalizer; protocol report (`html/pdf/docx`) нормализует `run.results` перед рендером. Добавлены регрессионные тесты `backend/tests/test_analysis_result_v2_contract.py` для legacy `run`/`batch`.
26. Проведена финальная ревизия secondary UI-потоков по Design Review gate: подтверждён guard перед execute в `ProtocolSorcerer`, `AnalysisDesign`, `Copilot`, `Analyze`; добавлен frontend regression-тест `frontend/src/app/pages/Analyze.test.jsx` (блокировка запуска без подтверждения + передача `designConfirmed=true` при подтверждённом дизайне).
27. Расширена parity-программа для long-tail сценариев: добавлен `backend/tests/test_engine_parity_long_tail.py` с cross-engine проверками для `t_test_rel`, `wilcoxon` и execute-потока `responders` (Python vs R, проверка значимости и допустимого дрейфа p-value).
28. Добавлены финальные parity-регрессы на уровне комплексных сценариев: `backend/tests/test_engine_parity_complex_protocol_e2e.py` (многошаговый execute-протокол) и py/r drift-check для COVID smoke в `backend/tests/test_covid_smoke_v2_flow.py` (`test_covid_smoke_v2_python_r_metric_drift`).
29. Начата P2-унификация publication-reporting таблиц: для `batch_analysis` и `timepoint_batch_analysis` введён единый inferential table contract (столбцы `target`, `p`, `p(adj)`, `sig`, `test`, + group stats при наличии) в HTML/DOCX/PDF; добавлен регрессионный тест `backend/tests/test_reporting_batch_tables.py`.
30. Усилен report hard-gate по полноте Methods: добавлен backend-check перед HTML/PDF/DOCX export (`CLINIMETRIA_REPORT_HARD_GATE_METHODS`) с валидацией inferential шагов из run results, включая fallback для описательных шагов без явного method-id; покрыто тестами `backend/tests/test_report_design_gate.py` и e2e `backend/tests/test_e2e_upload_analyze_export.py`.
31. Доведён единый publication plot preset в report renderer: `_render_plot_png_bytes` переведён на централизованную тему (`_report_plot_theme`) без разрозненных hardcoded цветов для ROC/boxplot/scatter/survival/bar/heatmap веток; добавлены регрессионные тесты `backend/tests/test_reporting_plot_preset.py`.
32. В протокольном отчёте (HTML/DOCX/PDF) добавлены явные manuscript-секции `Methods`, `Results`, `Limitations` с единым источником данных из run artifacts (`_extract_report_methods`, `_build_report_limitations`); добавлены регрессионные тесты `backend/tests/test_reporting_manuscript_sections.py`.
33. Зафиксирован manuscript-ready smoke gate на COVID e2e: в `backend/tests/test_covid_smoke_v2_flow.py` добавлена проверка секций `Methods/Results/Limitations` и наличия export-артефактов `protocol_report.(html|pdf|docx)` + `analysis_dataset.(parquet|xlsx|meta)` в run artifacts.
34. Добавлен финальный release-hardening checklist endpoint: `GET /api/v1/analysis/protocol/report/{run_id}/quality` (оценка Design/Methods/sections/артефактов/экспортов), плюс тесты `backend/tests/test_report_quality_checklist.py`; COVID smoke дополнен обязательной проверкой `status=pass`.
35. Добавлен publication workflow contract на уровне `v2`: `POST /api/v1/v2/analysis/plan` теперь всегда возвращает структурированные секции `cleaning_plan`/`cohort_plan`/`report_spec`, а `POST /api/v1/v2/analysis/execute` получил strict publication-gate (обязательный backend Design Review + обязательный fixed cohort `analysis_set` + fingerprint check). Добавлены регрессионные тесты `backend/tests/test_design_review_soft_check.py` для этих сценариев.
36. Доведен frontend publication workflow в `CopilotPage`: добавлен режим `Publication / Manuscript`, auto-freeze fixed cohort по `cohort_plan` перед execute и автоматическая передача `analysis_set_id`/`analysis_set_strict` в `executeProtocolV2`; в UI добавлены явные блоки `cleaning_plan`/`cohort_plan`/`report_spec` в review-экране. Добавлены тесты `frontend/src/features/copilot/CopilotPage.test.jsx` и backend e2e `backend/tests/test_publication_workflow.py`.

Осталось критично:
1. Критичных блокеров по ARCHITECTURE_REWORK_PLAN не осталось: golden path закрыт, manuscript-ready QA и release-hardening проверки внедрены.

## 11. Детализированный план реализации (следующие 3 спринта)

### Спринт 1 — Golden Path only (1 неделя)

Цель: оставить один поддерживаемый путь и убрать дубли.

Задачи:
1. Перевести `ProtocolSorcerer` на canonical API (`/api/v2/analysis/plan` + `/api/v2/analysis/execute`) без legacy вызовов.
2. Для устаревших маршрутов оставить только shim-слой + telemetry, без бизнес-логики.
3. В UI явно показывать этапы: `Ingest -> Design Review -> Plan -> Execute -> Report`.

Критерии приёмки:
1. Нет прямых вызовов legacy API в активных экранах.
2. Любой запуск анализа проходит через единый `run_id` в `analysis/{run_id}`.
3. Smoke-тест COVID проходит end-to-end без ручных правок API payload.

### Спринт 2 — Design-first и engine parity (1 неделя)

Цель: сделать дизайн обязательным и выровнять Python/R контракты.

Задачи:
1. Добавить `Method Coverage Matrix` (`method_id x engine`) как источник истины.
2. На execute проверять совместимость метода с выбранным engine до запуска.
3. Ввести обязательные поля результата (`method_id`, `engine`, `p_value`, `effect_size`, `diagnostics`, `warnings`, `plots`).
4. Для top-10 методов COVID добавить cross-engine consistency тесты.

Критерии приёмки:
1. Переключение Python/R не ломает формат результата.
2. Методы вне parity-модуля блокируются с понятной ошибкой.
3. Все top-10 методов покрыты тестами для двух engine.

### Спринт 3 — Publication-quality output (1 неделя)

Цель: отчёт и артефакты уровня manuscript-ready.

Задачи:
1. Ввести hard-gate экспорта: если Design/Methods неполны, DOCX/PDF не генерируется.
2. Добавить экспорт финального расчётного датасета (`analysis_dataset.xlsx` + `analysis_dataset.parquet`) в `analysis/{run_id}`.
3. В отчёте стандартизировать таблицы: descriptive, inferential, multiplicity.
4. Ввести единый графический preset (Python/R) с публикационными параметрами.

Критерии приёмки:
1. Каждый отчёт содержит заполненные Design + Methods + Results + Discussion + Limitations.
2. Для каждого отчёта доступен воспроизводимый датасет расчёта.
3. QA-чеклист manuscript-ready проходит на COVID-сценарии.
