# Обзор архитектуры StatProject / StatWizard (текущее состояние)

Дата: 2026-01-25

Этот документ объясняет:

- что за приложение у тебя сейчас в репозитории;
- как оно работает как система (Frontend ↔ Backend ↔ файловое хранилище);
- какие функции реально рабочие (и какие подтверждены тестами);
- что уже выглядит как цельный workflow уровня Jamovi/JASP/GraphPad;
- что ещё «сырая идея» или не интегрировано в единый продукт.

Формат специально сделан так, чтобы ты мог ориентироваться без знания программирования: что где находится, что трогать, а что опасно трогать.

---

## 1) Что это за продукт (в 20 строк)

**StatWizard / StatProject** — веб-приложение для статистического анализа клинических данных.

Ключевая идея из [PRODUCT_VISION.md](file:///D:/statproject/PRODUCT_VISION.md):

- пользователь без навыков статистики загружает таблицу (CSV/XLSX),
- получает подсказки «какой тест выбрать и почему»,
- запускает анализ,
- видит результаты + графики + текстовые интерпретации,
- экспортирует отчёт (PDF/DOCX) для статьи.

Текущее состояние (по факту кода и внутренним документам):

- Backend близок к «движку продукта» (много методов, протоколы, отчёты, тесты).
- Frontend уже дает usable интерфейс, но архитектурно перегружен (главная страница анализа слишком большая и часть возможностей backend пока не показана).

---

## 2) Ментальная модель системы (самая важная часть)

Если упростить: продукт работает вокруг 3 сущностей.

### 2.1 Dataset (датасет)

**Dataset** = загруженный файл данных, которому присваивается `dataset_id`.

- Backend хранит этот dataset в файловой структуре (`workspace/datasets/<dataset_id>/...`).
- Frontend работает по URL с этим id: `/prep/:id`, `/design/:id`, `/results/:id`.

Код: [datasets.py](file:///D:/statproject/backend/app/api/datasets.py)

### 2.2 Protocol (протокол анализа)

**Protocol** = JSON-описание шагов анализа (что сравнивать, какие переменные, какие тесты, какие настройки).

Протокол создаётся двумя способами:

- руками в UI (выбор тестов + конфигурация);
- автоматически (шаблоны / «умный дизайнер» / AI-модуль).

Код: [analysis.py](file:///D:/statproject/backend/app/api/analysis.py), [protocol_engine.py](file:///D:/statproject/backend/app/core/protocol_engine.py)

### 2.3 Run (запуск)

**Run** = результат выполнения протокола. Он имеет `run_id` и сохраняется в:

`workspace/datasets/<dataset_id>/analysis/<run_id>/results.json`.

Frontend потом по `dataset_id + run_id` поднимает результаты и рисует UI.

Код: [pipeline.py](file:///D:/statproject/backend/app/core/pipeline.py), [analysis.py](file:///D:/statproject/backend/app/api/analysis.py)

---

## 3) Архитектура слоями (как устроен репозиторий)

### 3.1 Frontend (React + Vite)

Роутинг (основные страницы): [App.jsx](file:///D:/statproject/frontend/src/App.jsx)

- `/upload` — загрузка файлов
- `/datasets` — список датасетов
- `/prep/:id` и `/profile/:id` — просмотр/подготовка данных (профиль)
- `/study-setup/:id` — описание исследования (цели/гипотезы) (частично)
- `/design/:id` — конструктор протокола (главная рабочая страница продукта)
- `/results/:id` — результаты анализа
- `/graphs/:id` — результаты в режиме графиков
- `/report/:id` — результаты в режиме отчёта
- `/wiki` — стат-справка/вики
- `/settings` — настройки

Главный «комбайн» продукта на фронте сейчас — [AnalysisDesign.jsx](file:///D:/statproject/frontend/src/app/pages/AnalysisDesign.jsx)

### 3.2 Backend (FastAPI)

Точка входа: [main.py](file:///D:/statproject/backend/app/main.py)

API роутинг: [routes.py](file:///D:/statproject/backend/app/api/routes.py)

- `/api/v1/datasets/*` — загрузка, просмотр, подготовка датасета
- `/api/v1/analysis/*` — дизайн протокола, запуск, выдача результатов, отчёты
- `/api/v1/quality/*` — качество данных
- `/api/v1/wizard/*` — простой wizard «подбор теста + применение»
- `/api/v1/v2/*` — «v2» слой: расширенные методы/протоколы/knowledge

### 3.3 Файловое хранилище

Никакой базы данных сейчас нет. Всё хранится в файлах.

Pipeline папок создаёт и обслуживает: [pipeline.py](file:///D:/statproject/backend/app/core/pipeline.py)

Логика уровня «dataset → processed snapshot → run container» уже довольно зрелая:

- блокировки `.lock` на датасет,
- атомарные записи JSON,
- история processed-снимков (undo/rollback для подготовки данных).

---

## 4) Как работает «цельный workflow» (end-to-end)

Ниже — реальные потоки, которые уже можно считать «продуктом», а не набором скриптов.

### Workflow A: Upload → Design → Run → Results → Export (это “ядро продукта”)

1) **Загрузка файла** (CSV/XLSX)

- UI: `/upload`
- API: `POST /api/v1/datasets` (multipart)
- Backend делает:
  - парсинг,
  - оптимизацию типов,
  - сохранение processed parquet,
  - генерацию `scan_report.json`.

Код: [datasets.py](file:///D:/statproject/backend/app/api/datasets.py)

2) **Конструктор протокола**

- UI: `/design/:id`
- Внутри: выбор тестов + настройка переменных + сохранение протоколов в localStorage.

Ключевые компоненты:

- [TestSelectionPanel.jsx](file:///D:/statproject/frontend/src/app/components/analysis/TestSelectionPanel.jsx)
- [ProtocolBuilder.jsx](file:///D:/statproject/frontend/src/app/components/analysis/ProtocolBuilder.jsx)
- [TestConfigModal.jsx](file:///D:/statproject/frontend/src/app/components/TestConfigModal.jsx)

3) **Запуск протокола**

- API: `POST /api/v1/analysis/protocol/run`
- Backend:
  - читает dataframe,
  - создаёт run-контейнер,
  - выполняет шаги протокола,
  - сохраняет `results.json`, артефакты/файлы.

Код: [analysis.py](file:///D:/statproject/backend/app/api/analysis.py), [protocol_engine.py](file:///D:/statproject/backend/app/core/protocol_engine.py)

4) **Просмотр результатов**

- UI: `/results/:id?run=<run_id>` (или runId приходит через state)
- Фронт грузит результат run’а, отрисовывает таблицы/графики/интерпретации.

Код: [StepResults.jsx](file:///D:/statproject/frontend/src/app/pages/steps/StepResults.jsx)

5) **Экспорт отчёта**

- PDF отчёт: `POST /api/v1/analysis/report/pdf` (см. [README.md](file:///D:/statproject/README.md))
- DOCX результатов: `POST /api/v1/analysis/export/docx` (см. [analysis.py](file:///D:/statproject/backend/app/api/analysis.py))
- «Протокольные» отчёты по run_id: `/api/v1/analysis/protocol/report/{run_id}/*` (html/pdf/docx)

Это уже похоже на “готовый продукт”: пользователь реально может пройти от файла до отчёта.

Подтверждение тестами:

- E2E: [test_e2e_upload_analyze_export.py](file:///D:/statproject/backend/tests/test_e2e_upload_analyze_export.py)
- Полный поток: [test_full_flow.py](file:///D:/statproject/backend/tests/test_full_flow.py)

### Workflow B: Wizard “подбор теста → применение”

Это более «упрощённый Jamovi-style» поток.

- API рекомендация: `POST /api/v1/wizard/recommend`
- API применение: `POST /api/v1/wizard/apply`

Код: [wizard.py](file:///D:/statproject/backend/app/api/wizard.py)

Смысл: если пользователь не хочет собирать протокол руками, он отвечает на несколько вопросов и получает результат.

### Workflow C: AI “опиши исследование текстом → получи протокол”

Это «вишенка» продукта, но в текущем состоянии нужно относиться как к beta.

- API: `/api/v1/v2/ai/analyze-design` и `/api/v1/v2/ai/suggest-tests`
- Backend пытается:
  - собрать метаданные датасета,
  - превратить текст в набор шагов,
  - нормализовать шаги под формат протокола.

Код: [ai_module.py](file:///D:/statproject/backend/app/api/ai_module.py)

Проблема: на фронте «AI протокол» и «ручной протокол» должны жить в одном формате и UX, иначе ощущается как две разные фичи.

---

## 5) Что реально “работает” (по коду)

Ниже — функциональные подсистемы, которые выглядят зрелыми.

### 5.1 Статистический движок

Центр: [engine.py](file:///D:/statproject/backend/app/stats/engine.py)

Факты:

- есть единая функция `run_analysis(...)` как “dispatcher” на методы;
- есть авто-выбор метода (`method_id == "auto"`) и fallback при нарушениях допущений;
- для ряда тестов поднимаются effect size, CI, power, BF10 (через Pingouin, SciPy, statsmodels);
- есть пост-хок и поправки (Tukey/Games-Howell/Dunn + коррекции множественности).

Реестр методов: [registry.py](file:///D:/statproject/backend/app/stats/registry.py)

Важно: реестр уже содержит больше методов, чем может быть «прокликиваемо» в UI в текущей версии фронта.

### 5.2 Execution layer: протоколы и run-контейнеры

- хранение run’ов и атомарность — сильная сторона (см. [pipeline.py](file:///D:/statproject/backend/app/core/pipeline.py));
- протоколы выполняются шагами, каждому шагу соответствует результат или ошибка, всё сериализуется безопасно (NaN → null).

Код: [protocol_engine.py](file:///D:/statproject/backend/app/core/protocol_engine.py)

### 5.3 Загрузка данных и первичный скан

Backend не просто принимает файл: он строит первичный “scan_report” и оптимизирует типы.

Код: [datasets.py](file:///D:/statproject/backend/app/api/datasets.py)

### 5.4 Экспорт отчётов

Есть несколько путей экспорта:

- «пакетный» PDF отчёт анализа (endpoint в v1);
- DOCX генерация результатов;
- отдельные «protocol report» артефакты в run.

Код: [reporting.py](file:///D:/statproject/backend/app/modules/reporting.py)

### 5.5 Инфраструктура

- Docker окружение с лимитами ресурсов: [docker-compose.yml](file:///D:/statproject/docker-compose.yml)
- тесты backend (pytest) и frontend (vitest + playwright): [README.md](file:///D:/statproject/README.md)

---

## 6) Что “не работает” или работает частично (важно знать заранее)

### 6.1 Фронт не показывает часть возможностей backend

Backend поддерживает больше методов (например, agreement/reliability: ICC, Cohen’s kappa; dimension reduction: PCA/EFA; и др.), но UI-конструктор тестов не обязательно даёт доступ ко всему реестру.

Симптомы такого класса проблем:

- метод есть в [registry.py](file:///D:/statproject/backend/app/stats/registry.py), но его нельзя выбрать в [TestSelectionPanel.jsx](file:///D:/statproject/frontend/src/app/components/analysis/TestSelectionPanel.jsx);
- конфигурация метода не описана в [TestConfigModal.jsx](file:///D:/statproject/frontend/src/app/components/TestConfigModal.jsx).

### 6.2 Assumptions checks есть в API, но почти не surfaced в UI

Endpoint существует: `POST /api/v1/analysis/assumptions` (см. [analysis.py](file:///D:/statproject/backend/app/api/analysis.py)).

Но фронт (по текущей архитектуре) не делает эту проверку “прямо в момент выбора теста” как Jamovi/JASP.

Это влияет на «ощущение продукта»: без подсветки допущений пользователю сложнее доверять рекомендациям.

### 6.3 “Study Setup” слой выглядит незавершённым и потенциально сломанным путём хранения

Есть модуль `/api/v1/v1/study/...` (включается в router как prefix `/v1` поверх `/api/v1`, см. [routes.py](file:///D:/statproject/backend/app/api/routes.py)).

Но внутри [study.py](file:///D:/statproject/backend/app/api/study.py) жёстко указан путь:

- `DATASETS_DIR = Path("backend/workspace/datasets")`

При этом основной pipeline datasets использует `WORKSPACE_DIR = os.getenv("STATWIZARD_WORKSPACE_DIR", "workspace")` и `DATA_DIR = os.path.join(WORKSPACE_DIR, "datasets")` (см. [datasets.py](file:///D:/statproject/backend/app/api/datasets.py)).

Риск: конфиги исследования могут писать не туда, где реально лежат датасеты в production/Docker.

### 6.4 Архитектурный “узел” фронта: AnalysisDesign.jsx

В одном файле слишком много ответственности: состояние, API вызовы, UI-логика, протоколы, настройки.

Код: [AnalysisDesign.jsx](file:///D:/statproject/frontend/src/app/pages/AnalysisDesign.jsx)

Это не «не работает», но это ограничивает скорость развития: любая фича добавляет хаос.

### 6.5 Визуализации не доведены до “publication-ready”

По плану (см. [ROADMAP.md](file:///D:/statproject/ROADMAP.md)) должны быть:

- единый стиль графиков,
- экспорт графиков,
- «significance brackets» и т.п.

В текущем UI явно отмечено, что этого нет (см. [AI_CONTEXT.md](file:///D:/statproject/AI_CONTEXT.md)).

---

## 7) Насколько это сопоставимо с мировыми продуктами уже сейчас

Если сравнивать честно (без маркетинга), то:

### Уже сопоставимо (в сегменте “MVP/alpha продукта”)

- **Jamovi/JASP**: похоже по идее «выбор теста → результат + интерпретация», особенно если использовать wizard и шаблоны.
- **GraphPad Prism**: похоже по сценарию «загрузил → сравнил группы → получил графики → экспортировал», но пока не по polish.

Ключевой плюс по сравнению с ними:

- продукт web-based + потенциально русскоязычный «обучающий интерфейс» (концепция из vision).

### Пока явно уступает

- глубина и целостность UX: в Jamovi/JASP всё ощущается единым, тут часть вещей скрыта и есть несколько параллельных “режимов” (v1/v2/ai/wizard);
- “научный лоск”: публикационные графики, стандартизированная таблица результатов, строгое протоколирование;
- стабильность интерфейса: из-за монолитной страницы анализа сложнее развивать без регрессий.

---

## 8) Что ещё “не до конца осмысленно” (как продуктовая архитектура)

Это те зоны, где важнее сначала договориться о продуктовой модели, чем писать код.

### 8.1 Единая модель протокола (v1 vs v2 vs AI)

Сейчас в системе есть несколько форматов/подходов:

- v1 протокол: `protocol = { name, goal, steps: [...] }` (см. [analysis.py](file:///D:/statproject/backend/app/api/analysis.py))
- v2 протокол: чаще список шагов `{ id, method, config }` и отдельные v2 endpoints (см. [v2.py](file:///D:/statproject/backend/app/api/v2.py))
- AI протокол: приходит “как получится”, потом нормализуется (см. [ai_module.py](file:///D:/statproject/backend/app/api/ai_module.py))

Пока это выглядит как три ветки, которые нужно свести к одному UX:

- один “editor” протокола,
- один “runner” протокола,
- единый формат хранения run.

### 8.2 Где живёт “знание” продукта

Есть несколько источников:

- реестр методов (backend registry),
- wiki/education компоненты (frontend),
- knowledge API (v2 слой),
- текстовый генератор интерпретаций.

Чтобы продукт был целостным, “правда” о методе должна быть в одном месте, а UI и генераторы должны это использовать.

---

## 9) Практическая карта для дальнейшей доработки (без знания программирования)

Тут “как думать”, чтобы не утонуть.

### 9.1 Если цель — довести до стабильного MVP, который можно показывать миру

Фокус: один основной workflow (Upload → Design → Run → Results → Export).

Самые дорогие проблемы сейчас не в математике, а в целостности UX и согласованности API.

Приоритеты:

1) **Свести протоколы к одному стандарту** (чтобы не было v1/v2/ai как разных вселенных).
2) **Показать assumptions checks в UI** (минимум: предупреждения и рекомендация теста).
3) **Стабилизировать Study Setup** (исправить пути хранения и интеграцию с протоколом/отчётом).
4) **Разрезать AnalysisDesign.jsx на модули** (иначе каждая новая фича будет ломать старые).

### 9.2 Если цель — конкурент Jamovi/JASP (в долгую)

Фокус: “обучение через практику” и системность.

1) Knowledge base как единый источник правды.
2) Publication-ready графики + экспорт графиков.
3) Больше методов + строгая валидация входов.

### 9.3 Если цель — “AI-first продукт”

Фокус: сделать AI не отдельной кнопкой, а частью основного пути.

- AI предлагает протокол, пользователь редактирует в том же editor’е.
- AI объясняет “почему этот тест” прямо рядом с выбором.
- AI помогает сформировать «Methods» и «Results» секции для статьи.

---

## 10) Технический чеклист: где что находится

### Frontend

- Роутинг: [App.jsx](file:///D:/statproject/frontend/src/App.jsx)
- Главная страница анализа/конструктор: [AnalysisDesign.jsx](file:///D:/statproject/frontend/src/app/pages/AnalysisDesign.jsx)
- Сборка протокола: [ProtocolBuilder.jsx](file:///D:/statproject/frontend/src/app/components/analysis/ProtocolBuilder.jsx)
- Выбор тестов: [TestSelectionPanel.jsx](file:///D:/statproject/frontend/src/app/components/analysis/TestSelectionPanel.jsx)
- Настройка теста: [TestConfigModal.jsx](file:///D:/statproject/frontend/src/app/components/TestConfigModal.jsx)
- Результаты: [StepResults.jsx](file:///D:/statproject/frontend/src/app/pages/steps/StepResults.jsx)
- API клиент: [api.js](file:///D:/statproject/frontend/src/lib/api.js)

### Backend

- Entry: [main.py](file:///D:/statproject/backend/app/main.py)
- Роуты: [routes.py](file:///D:/statproject/backend/app/api/routes.py)
- Datasets: [datasets.py](file:///D:/statproject/backend/app/api/datasets.py)
- Analysis: [analysis.py](file:///D:/statproject/backend/app/api/analysis.py)
- Wizard: [wizard.py](file:///D:/statproject/backend/app/api/wizard.py)
- Stats engine: [engine.py](file:///D:/statproject/backend/app/stats/engine.py)
- Method registry: [registry.py](file:///D:/statproject/backend/app/stats/registry.py)
- Protocol execution: [protocol_engine.py](file:///D:/statproject/backend/app/core/protocol_engine.py)
- Storage pipeline: [pipeline.py](file:///D:/statproject/backend/app/core/pipeline.py)
- Reporting: [reporting.py](file:///D:/statproject/backend/app/modules/reporting.py)

---

## 11) Мой итог как архитектора

Сейчас это **реально работающий прототип продукта**, у которого:

- сильный backend-движок;
- уже есть end-to-end поток до отчёта;
- есть база для “обучающего интерфейса” (education components + vision);
- есть тестовая база, подтверждающая ключевые сценарии.

Главные риски для дальнейшего развития:

- параллельные “ветки” протоколов (v1/v2/ai) и отсутствие одной унифицированной модели;
- слишком монолитная страница анализа на фронте;
- недоинтегрированность допущений/проверок качества данных в UX;
- «Study Setup» хранит данные потенциально не туда, куда нужно в production.

Если закрыть эти 4 пункта, продукт станет восприниматься как цельная система, которую уже можно сопоставлять с мировыми конкурентами не только по идее, но и по ощущению.

