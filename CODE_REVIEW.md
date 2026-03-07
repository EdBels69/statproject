# Code Review (StatProject)

## TL;DR

- ML методы в проекте есть и выполняются в backend, но они не входят в единый каталог методов (`registry.py`), поэтому UI/вики могут быть неполными и несогласованными.
- Основная системная проблема — дрейф `method_id` и дублирование “справки” между слоями (UI/engine/knowledge/registry), из-за чего часть функций «как будто есть», но недоступна из конкретного UI/endpoint.

## Структура репозитория

- `frontend/` — React (Vite), UI и сборка протоколов анализа.
- `backend/` — FastAPI, вычислительное ядро статистики/ML, генерация отчётов.

### Frontend: ключевые точки

- Роутинг: [App.jsx](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/frontend/src/App.jsx)
  - `/design/:id` — конструктор протоколов (основной UI).
  - `/sorcerer` / `/protocol` — мастер подбора.
  - `/results/:id`, `/graphs/:id`, `/report/:id` — просмотр результатов запуска протокола.
  - `/wiki` — StatWiki.
- Конфиг модалка теста/шага: [TestConfigModal.jsx](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/frontend/src/app/components/TestConfigModal.jsx)

### Backend: ключевые точки

- API роуты knowledge: [knowledge.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/knowledge.py)
- Knowledge-контент (термины/объяснения): [stat_knowledge.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/stat_knowledge.py)
- Исполнение методов анализа (в т.ч. ML): [engine.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/engine.py#L643-L853)
- Реестр доступных методов (каталог): [registry.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/registry.py)

## Функционал приложения (как оно работает)

1) Пользователь загружает/выбирает датасет.
2) В конструкторе протокола добавляет шаги (stat/ML методы) и настраивает колонки.
3) Протокол запускается, backend исполняет шаги и отдаёт результаты.
4) Пользователь смотрит результаты/графики/отчёт.
5) Вики (`/wiki`) — справочник терминов и методов на базе knowledge API.

### Backend: ключевые API слои

- Dataset / ingest:
  - `/api/v1/datasets/*` — загрузка, переработка, профилирование, окно данных. См. [datasets.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/datasets.py) + [parsers.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/parsers.py).
- Protocol design:
  - `/api/v1/analysis/design` — сборка протокола из шаблона/цели. См. [analysis.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/analysis.py#L223-L247).
  - `/api/v1/v2/analysis/design` — конвертация «шаблонного» протокола в v2 шаги (JAMOVI‑style). См. [v2.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/v2.py#L158-L240).
- Protocol execution:
  - `/api/v1/analysis/run` — выполнение одного метода (через `run_analysis`). См. [analysis.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/analysis.py#L773-L836).
  - `/api/v1/v2/*` — часть «тяжёлых» методов вынесена в v2 (mixed effects, clustered correlation и др.). См. [v2.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/v2.py).
  - `/api/v1/stream/analysis` — стриминговое выполнение (NDJSON). См. [streaming.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/streaming.py#L125-L158).
- Knowledge:
  - `/api/v1/v2/knowledge/*` — справочник терминов и тестов для StatWiki. См. [knowledge.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/knowledge.py).

### Данные и пайплайн

- Workspace: по умолчанию `backend/workspace/datasets/<dataset_id>/`.
- Структура: `source/` (raw+meta) → `processed/` (parquet/csv + scan_report) → `analysis/` (запуски и артефакты).
- Ключевой менеджер структуры/снэпшотов: [PipelineManager](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/core/pipeline.py).

## Где ML методы

### 1) Исполнение (backend)

ML ветка явно реализована в [engine.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/engine.py#L643-L853):

- `random_forest`
- `gradient_boosting`
- `knn`
- `svm`

Плюс отдельные “model-ish” методы:

- `roc_analysis` (ROC/AUC)
- `linear_regression`, `logistic_regression` (есть в реестре)
- `mixed_model` / `mixed_effects` (есть разные ветки в коде)

### 2) Почему их не было видно в вики

StatWiki строится от knowledge endpoints (`/v2/knowledge/tests`). Раньше список `TEST_KNOWLEDGE` в [stat_knowledge.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/stat_knowledge.py) не содержал ML/регрессий/ROC, поэтому “вики по тестам” не могла их показать.

### 3) Почему ML методы до сих пор «выпадают» из каталога

`engine.py` поддерживает ML (`random_forest/gradient_boosting/knn/svm`), но они отсутствуют в [registry.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/registry.py). Это ломает идею «единого списка доступных методов» и провоцирует рассинхрон: UI/шаблоны ориентируются на одно, движок умеет другое.

## Проблемы (подсветка)

### 1) Дрейф идентификаторов методов между слоями (высокий риск 404/несостыковок)

Примеры из кода:

- Frontend использует `fisher`, backend в `engine.py` оперирует `fisher_exact` (и может подменять `chi_square` на `fisher_exact`). См. [engine.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/engine.py#L1182-L1221) и [TestConfigModal.jsx](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/frontend/src/app/components/TestConfigModal.jsx#L1967-L1994).
- В “семействе Welch/Kruskal” встречаются разные ключи: `welch_t_test` vs `t_test_welch`, `kruskal_wallis` vs `kruskal`, `welch_anova` vs `anova_welch`.
- Для mixed models есть и `mixed_model`, и `mixed_effects` (оба фигурируют в [registry.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/registry.py)).

Следствие: UI/вики/отчёты могут ссылаться на разные id одного и того же метода.

### 2) Каталог методов (`registry.py`) не совпадает с реальной исполняемостью (`engine.py`)

Методы есть в реестре, но не имеют handler в `run_analysis` и фактически недоступны через `/analysis/run`:

- assumption: `shapiro_wilk`, `levene`
- agreement/reliability: `bland_altman`, `icc`, `cohens_kappa`
- categorical paired: `mcnemar`, `cochran_q`
- advanced: `ancova`
- dimension reduction / reliability / clustering: `pca`, `efa`, `cronbach_alpha`, `kmeans`, `hierarchical_clustering`
- correlation add-ons: `point_biserial`, `partial_correlation`

Подтверждение: dispatcher `run_analysis` в [engine.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/engine.py#L624-L664) падает в `ValueError` для этих `method_id`.

### 3) Knowledge слой покрывает часть «алиасов», но не покрывает расширенный реестр

- В [stat_knowledge.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/stat_knowledge.py#L506-L1035) есть статьи про `fisher_exact`, `welch_t_test`, `kruskal_wallis`, ML (`random_forest`, `gradient_boosting`, `knn`, `svm`).
- Но в knowledge нет статей для методов из расширенного реестра: `ancova`, `pca`, `efa`, `cronbach_alpha`, `kmeans`, `hierarchical_clustering`, `point_biserial`, `partial_correlation`, `icc`, `cohens_kappa`, `bland_altman`, `shapiro_wilk`, `levene`.

Это объясняет ощущение «вики явно не полная»: часть методов заявлена в реестре, но (а) не исполняется, (б) не описана, (в) не попадает в UI.

### 4) Knowledge слой ≠ каталог методов

`stat_knowledge.py` — отдельный справочник, который должен покрывать то, что реально доступно. Если его не синхронизировать с `registry.py`/`engine.py`, вики будет неполной, а подсказки — с 404.

### 3) Дублирование справки на фронте

В проекте есть локальные “knowledge базы” на фронте (например, в [WhyThisTest.jsx](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/frontend/src/app/components/education/WhyThisTest.jsx) и [StatTooltip.jsx](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/frontend/src/app/components/education/StatTooltip.jsx)), параллельно backend knowledge. Это почти гарантирует рассинхрон.

### 4) Реестр содержит методы, которые неочевидно реализованы в engine

В [registry.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/registry.py#L215-L236) есть `mcnemar` и `cochran_q`, но в [engine.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/engine.py) нет явной ветки обработки этих `method_id` (это нужно подтвердить/добавить реализацию или убрать из реестра/UI).

### 5) Проблемные «серые зоны» v1/v2

- `mixed_effects` есть в [registry.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/stats/registry.py), но исполняется не через `engine.run_analysis`, а через v2 endpoint (см. [v2.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/v2.py#L231-L339)). Если UI отправит `mixed_effects` в `/analysis/run`, это закончится `Method mixed_effects not implemented`.

## Рекомендации по оздоровлению

- Ввести единый источник истины для `method_id` (лучше `registry.py`), а UI/knowledge/engine подстроить.
- Сделать явный слой алиасов `method_id` (и использовать его в UI + knowledge + engine).
- Убрать локальные “knowledge базы” на фронте или перевести их на backend knowledge как единственный источник.
- Автотест на покрытие: “каждый method_id из реестра имеет handler (v1 или v2) и статью в knowledge (или явно помечен как hidden/experimental)”.
