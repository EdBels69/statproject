# AI Expert Module — план приближения к уровню `run_diamag_full.py`

Цель: чтобы модуль сам «нащупывал» статистическую обработку как эксперт‑аналитик/биостатист: предлагал дизайн, выбирал корректные процедуры и просил подтвердить критические допущения.

Этот документ описывает, что именно нужно добавить/перестроить в текущем контуре приложения, чтобы приблизиться по качеству и насыщенности отчёта к `backend/scripts/run_diamag_full.py`.

## 0) В чём принципиальная разница с `run_diamag_full.py`

`run_diamag_full.py` — это «монолитный экспертный сценарий»:
- заточен под один тип данных (DIAMAG),
- знает доменные эндпоинты и визиты,
- строит комплексную историю (executive summary → эндпоинты → pooled → post‑hoc → mixed effects → responders → discussion),
- генерирует тяжёлый DOCX с большим числом графиков/таблиц.

Текущий AI‑модуль в API (`/v2/ai/analyze-design`) — это «универсальный планировщик шагов»:
- видит только `dataset_meta` (урезанные метаданные колонок),
- возвращает короткий протокол (список шагов),
- не имеет устойчивого слоя “конфирмации” (вопросы пользователю),
- не имеет системы “скриптов/плагинов” с доменными сценариями,
- отчёт в основном строится как вывод по одному запуску/протоколу, а не как полноценная исследовательская история.

Если хотим приблизиться к уровню `run_diamag_full.py`, нужно не «улучшить промпт», а собрать правильную архитектуру: детерминированный прескан → планирование → подтверждение → исполнение → репортинг.

## 1) Мой ответ на «удалить всё и написать с нуля?»

Не удалять.

Почему:
- У вас уже есть рабочие компоненты движка: `run_analysis`, `run_batch_analysis`, `ProtocolEngine`, пайплайн артефактов, генерация отчётов.
- «С нуля» вы потеряете тесты/контракты/эндпоинты и получите большой регресс.

Правильнее:
- оставить текущие эндпоинты и движок,
- добавить новый слой “Expert Planner + Confirmation + Script Runner” как независимый контур,
- постепенно переносить ценность из `run_diamag_full.py` в переиспользуемые плагины.

## 2) Целевая архитектура (слои и контракты)

### 2.0 Где это уже есть в коде (и что можно переиспользовать)

- API автодизайна (LLM планировщик): `POST /api/v2/ai/analyze-design` → [ai_module.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/ai_module.py)
- Детерминированный детектор формы исследования: [StudyDetector](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/study_detector.py)
- Глубокий скан качества/метаданных (для UI sorcerer): [SmartScanner](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/smart_scanner.py)
- Исполнение v2 протокола (method/config список шагов): `POST /api/v2/analysis/execute` → [v2.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/v2.py)
- Исполнение «старого» протокола и часть v2-логики в ядре: [protocol_engine.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/core/protocol_engine.py)
- Базовая (не‑LLM) интерпретация результатов «как пишет статистик»: [text_generator.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/text_generator.py)
- LLM‑интерпретации для отчёта (таблицы/фигуры/summary) и промпты: [html_report.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/generators/html_report.py), [prompts](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/llm/prompts)

### 2.1 Deterministic Condenser (без LLM)

Задача: превратить датасет в компактный «паспорт» исследования, пригодный для автодизайна.

Вход:
- `dataset_id`.

Выход (артефакты в workspace/pipeline):
- `column_index.json`: колонки + тип (numeric/categorical/datetime), unique_count, missing, частотные признаки.
- `study_shape.json`: кандидаты group/time/subject, визиты/таймпоинты, семейства эндпоинтов.
- `endpoint_families.json`: группы показателей (baseline/follow, V1..Vn, пары/тройки по паттернам).

Что уже близко по смыслу в коде:
- [StudyDetector](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/modules/study_detector.py) умеет находить group/id кандидатов и группировать эндпоинты по визитам.
- `processed/scan_report.json` и `dtypes.json` уже существуют в пайплайне.

Нужно усилить:
- нормализовать “visit/timepoint” в отдельный канонический слой (map визитов: V1…Vn, baseline/follow),
- детерминированно построить «карту сравнения»: 4 группы vs pooled Active/Placebo, если паттерн виден.

### 2.2 Planner (LLM, но под жёсткими ограничениями)

Задача: предложить 2–4 кандидата исследовательского дизайна и черновик протокола.

Вход:
- текст пользователя (цели/гипотезы/популяция),
- `study_shape.json` + `endpoint_families.json` (не сырые данные),
- предпочтения (альфа, множественные сравнения, язык, стиль отчёта).

Выход:
- `draft_plan.json`:
  - `design_candidates[]` (каждый: кратко “что считаем”, “почему”, “риски”, “что нужно подтвердить”),
  - `proposed_protocol[]` (шаги выполнения),
  - `questions[]` (что нужно уточнить перед запуском).

Критично:
- Planner не должен решать всё “в один шаг”. Он должен выдавать вопросы.
- Модель должна быть ограничена по токенам и по числу шагов.

### 2.3 Confirmation UI (обязательная стадия “подтвердить/уточнить”)

Задача: превратить “вопросы” в конкретные переключатели/селекты, которые пользователь подтверждает.

Минимальный список того, что почти всегда надо спросить/подтвердить:
1) Колонка группировки (group_column) и уровни групп.
2) Колонка субъекта (subject_id) — если есть продольность.
3) Карта визитов/таймпоинтов (V1..Vn) или baseline/follow.
4) Первичные конечные точки (primary endpoints) и “семейства” вторичных.
5) Политика множественных сравнений:
   - FDR по всему массиву vs по семействам vs иерархия primary→secondary.
6) Набор графиков (спагетти, боксплоты, forest‑таблица эффектов).
7) Включать ли pooled сравнение (Active vs Placebo), если применимо.

### 2.4 Executor (Python, без LLM)

Задача: выполнить протокол/сценарий и сохранить артефакты (чтобы отчёт был тяжёлым, но воспроизводимым).

Две ветки исполнения:
- **Generic Protocol**: шаги из `ProtocolEngine` (что уже есть).
- **Script Plugins**: “экспертные” сценарии (как DIAMAG) в виде подключаемых модулей.

### 2.5 Reporter (DOCX/PDF/HTML)

Задача: сделать выход “как у DIAMAG”: оглавление, разделы, большие таблицы, фигуры, резюме.

Ключевое: отчёт должен собираться не из “одного результата”, а из *набора артефактов*:
- `tables/*.json` (таблица 1, сводки),
- `figures/*.png` (спагетти/box/pooled),
- `effects/*.json` (ES + CI),
- `multiplicity/*.json` (q-values),
- `narrative/*.json` (структурированные тезисы для LLM‑пояснений).

## 3) Плагины “экспертных сценариев”: как перенести ценность из `run_diamag_full.py`

Идея: не пытаться «универсализировать DIAMAG один в один», а вынести его как **плагин**.

### 3.1 Контракт плагина

Плагин — это объект со следующими частями:
- `id`, `name`
- `applicability(study_shape) -> score + reasons`
- `required_fields` (что нужно подтвердить)
- `build_plan(study_shape, confirmation) -> execution_plan`
- `run(execution_plan) -> artifacts`
- `report_template_id` или `report_blocks` (структура разделов)

### 3.2 Пример плагинов

1) `rct_longitudinal_4arm_with_pooled`
- обнаруживает 4 группы + визиты V3..V6 + пары по длительности,
- строит 4‑групповый анализ + pooled Active/Placebo,
- обязательно включает mixed effects и responders.

2) `rct_2arm_baseline_follow`
- 2 группы и baseline/follow пары исходов,
- primary: delta и сравнение delta,
- optional: mixed effects если есть subject_id и time.

3) `cross_sectional_multi_outcomes`
- один визит, много числовых исходов,
- “all numeric vs group” + FDR,
- top‑N по q‑value + forest таблица ES.

## 4) Что нужно доработать в текущем AI модуле (по существующему коду)

### 4.1 Сейчас

`/v2/ai/analyze-design`:
- строит `dataset_meta` только по первым 200 колонкам (простая эвристика kind=numeric/categorical),
- просит LLM вернуть `protocol[]` и `globals`,
- нормализует шаги (method/config) и отдаёт в UI.

Прямые точки расширения:
- `dataset_meta` сейчас строится в `_build_dataset_meta_for_ai(df)` → [ai_module.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/ai_module.py)
- LLM‑планирование сейчас делает `analyze_research_design(...)` → [app/llm/__init__.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/llm/__init__.py)
- Исполнение уже поддерживает “богатые” методы (mixed_effects, clustered_correlation) в v2 → [v2.py](file:///Users/eduardbelskih/%D0%9F%D1%80%D0%BE%D0%B5%D0%BA%D1%82%D1%8B%20Github/statproject/backend/app/api/v2.py)

### 4.2 Что добавить минимально, чтобы приблизиться к “экспертности”

1) **Расширить dataset_meta → study_shape**
- обязательно включить:
  - group candidates (ранжирование),
  - subject candidates,
  - timepoint detection,
  - endpoint families (V1..Vn, baseline/follow),
  - обнаружение “pooled” схемы (Active vs Placebo) по именам групп или конфигу.

2) **Сделать выход Planner двухфазным**
- не только `protocol[]`, но и:
  - `design_candidates[]`
  - `questions[]`
  - `risk_notes[]`

3) **Встроить Confirmation этап как обязательный**
- UI должен просить подтвердить group/time/subject/endpoints/multiplicity.

4) **Ввести Script Plugins и селектор сценариев**
- при совпадении паттерна — предлагать “режим DIAMAG‑подобного отчёта”.

5) **Стандартизировать артефакты**
- чтобы отчёт мог быть большим и богатым, но собирался из файлов (и кэшировался).

## 8) Минимальный контракт “Draft → Confirm → Run” (чтобы LLM стал экспертным)

### 8.1 Draft (план + вопросы)

Ответ Planner должен всегда возвращать не только `protocol`, но и вопросы к пользователю:

```json
{
  "status": "draft",
  "protocol_name": "…",
  "design_candidates": [
    {
      "id": "A",
      "title": "4 группы × визиты + post-hoc + mixed effects",
      "why": ["…"],
      "risks": ["…"],
      "requires_confirmation": ["group_column", "visits", "primary_endpoints", "multiplicity"]
    }
  ],
  "questions": [
    {
      "id": "group_column",
      "type": "select",
      "label": "Колонка группировки",
      "options": ["GROUP", "ARM", "…"],
      "default": "GROUP"
    }
  ],
  "proposed_protocol": [
    {"id": "t1", "method": "descriptive_compare", "config": {"target": "…", "group": "…"}}
  ]
}
```

### 8.2 Confirm (структурированное подтверждение)

Пользователь возвращает:

```json
{
  "design_id": "A",
  "confirmation": {
    "group_column": "GROUP",
    "subject_id": "PATIENT_ID",
    "visits": ["V3", "V4", "V5", "V6"],
    "primary_endpoints": ["UPDRS III", "…"],
    "multiplicity": {"policy": "fdr_by_family", "method": "bh"},
    "pooled": {"enabled": true, "map": {"Active": ["DrugA", "DrugB"], "Placebo": ["Placebo"]}}
  }
}
```

### 8.3 Run (исполнение + артефакты)

Исполнитель возвращает:
- `run_id`
- `artifacts_index.json` (что построено)
- ссылки на отчёты (DOCX/HTML/PDF)


## 5) Пример: как выглядел бы «экспертный диалог» (UX)

### 5.1 Draft (ИИ)

ИИ (после прескана) возвращает:
- «я вижу 4 группы, визиты V3–V6, много исходов по паттерну `*_V3..*_V6`»
- 2 варианта дизайна:
  - A) 4‑групповое сравнение по визитам + post‑hoc + mixed effects
  - B) pooled Active vs Placebo + фокус на мощности

### 5.2 Confirmation (пользователь)

Форма подтверждения:
- Group column: `GROUP`
- Subject id: `PATIENT_ID`
- Visits: `V3,V4,V5,V6` (извлечены)
- Primary endpoints: 5–12 пунктов (выбрать)
- Multiplicity: “FDR по всем исходам” или “FDR по семействам”
- Post-hoc: Dunn + BH

### 5.3 Execution

Система выполняет:
- table 1,
- 4‑group по визитам,
- pooled,
- post‑hoc,
- mixed effects,
- responders,
- итоговые ranked‑таблицы.

### 5.4 Report

DOCX:
- титул, оглавление,
- разделы 1..9 как в DIAMAG,
- графики и таблицы.

## 6) Предложение по дорожной карте (без “большого переписывания”)

Этап 1 (быстро, 1–2 недели):
- добавить `study_shape` прескан и подтверждение group/time/subject.
- сделать двухфазный output Planner (c questions).

Этап 2 (2–4 недели):
- реализовать “generic long RCT plugin” + артефакты + расширенный отчёт.

Этап 3 (4–8 недель):
- DIAMAG plugin: перенести логику из `run_diamag_full.py` в плагин, чтобы отчёт был почти идентичен.

## 7) Практический минимум, чтобы DIAMAG‑уровень стал системным

Если хотите максимально близко к DIAMAG‑результату в продукте, нужен:
- слой прескана (детерминированный) + сохранение “семейств эндпоинтов”,
- обязательный confirmation,
- plugin‑runner,
- отчётный “скелет” (разделы + оглавление) и подключаемые фигуры/таблицы.

Без этого LLM будет всегда давать «короткий протокол», а не большой отчёт.
