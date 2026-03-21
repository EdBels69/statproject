# OmniReport: план доработки «экспертный исчерпывающий отчёт по дизайну»

Дата: 2026-01-25

## 0) Что мы строим (в одном абзаце)

Нужен генератор итогового клинического/научного отчёта уровня [run_diamag_full.py](file:///d:/statproject/backend/scripts/run_diamag_full.py) — с методологией, описанием дизайна, структурированными показателями, графиками и выводами — но обобщённый: чтобы он работал для любого загруженного датасета и автоматически включал **все статистически подходящие** методы/проверки/сенситивити‑анализы под распознанный дизайн. Этот формат отчёта будем называть **OmniReport** (абстрактно, без привязки к DIAMAG).

Ключевой принцип: **ничего не ломаем** — текущий скрипт и существующие API остаются, мы делаем новый слой поверх существующего движка.

## 1) Наблюдения по текущему репозиторию (точки опоры)

- Есть эталонная структура отчёта и графиков: [run_diamag_full.py](file:///d:/statproject/backend/scripts/run_diamag_full.py).
- Есть движок выполнения методов и уже реализовано много тестов: [engine.py](file:///d:/statproject/backend/app/stats/engine.py), реестр методов: [registry.py](file:///d:/statproject/backend/app/stats/registry.py).
- Есть протокольный движок, который умеет исполнять несколько шагов: [ProtocolEngine](file:///d:/statproject/backend/app/core/protocol_engine.py).
- Есть генератор отчёта по протоколу (HTML/PDF/DOCX): [reporting.py](file:///d:/statproject/backend/app/modules/reporting.py).
- Есть текстовый вход (описание дизайна) через AI endpoint: [ai/analyze-design](file:///d:/statproject/backend/app/api/ai_module.py#L231-L276).
- Есть зачаток rule-based дизайнера: [StudyDesignEngine](file:///d:/statproject/backend/app/core/study_designer.py) — пока не исчерпывающий.

## 2) Требования (в явном виде)

### 2.1 Функциональные

1. Пользователь загружает таблицу (CSV/XLSX) → получает распознанный **DesignSpec** (дизайн исследования).
2. Пользователь может уточнить/построить дизайн **текстом** (и это не ломает авто‑детект).
3. Система строит **исчерпывающий экспертный план анализов** (Protocol) из DesignSpec:
   - confirmatory (основные) анализы
   - проверки допущений
   - альтернативы/robustness (sensitivity)
   - множественность и корректировки
   - стандартные клинические блоки (baseline, attrition, responders, time×group и т.п.)
4. Движок исполняет протокол и выдаёт результат.
5. Генерируется OmniReport (DOCX/PDF/HTML) с секциями, аналогичными DIAMAG‑стилю.

### 2.2 Нефункциональные

- Не ломать существующий API и сценарии.
- Детерминированность там, где важно: список «что будет посчитано» должен быть воспроизводим.
- Безопасность: строгая валидация конфигов шагов до запуска.
- Производительность: большие датасеты не должны валить UI/бэкенд.

## 3) Архитектура решения (3 слоя)

### 3.1 DesignSpec (описание дизайна)

Единая структура, независимая от конкретных тестов. Минимальный состав:

- dataset_id
- subject_id (колонка)
- group (колонка) + уровни + опциональные merge rules (active/placebo, duration buckets)
- time:
  - формат wide (набор визитов и маппинг visit→колонка)
  - или формат long (time column + outcome column)
- endpoints:
  - ключ, название
  - направление улучшения (increase/decrease)
  - primary/secondary
  - визит baseline
- правила множественности:
  - по визитам внутри endpoint
  - по endpoints
- responders правила (threshold, direction)

DesignSpec должен быть валидируемым (Pydantic) и сериализуемым.

### 3.2 Planner (DesignSpec → Protocol)

Rule-based экспертный планировщик, который строит протокол шагов. Важная цель: не «все методы реестра», а **все подходящие категории анализа**.

Блоки протокола (минимальный “DIAMAG‑core”, обобщённый):

1) Data integrity
- missingness/attrition по визитам
- описание групп и распределений

2) Baseline balance
- сравнение групп на baseline (Table 1)

3) Per-visit between-group comparisons
- для каждого endpoint и визита: сравнение групп
- автоматический выбор param/nonparam + обязательные sensitivity
- post-hoc и коррекции

4) Within-group changes
- baseline → follow-up по визитам, коррекции

5) Global longitudinal model
- LMM (Time×Group) при наличии repeated measures
- fallback/альтернативы: RM-ANOVA/Friedman (в зависимости от формата)

6) Responders
- доли responders по группам и визитам
- χ²/Fisher при необходимости

7) Secondary/exploratory (опционально)
- корреляции, ROC и т.п. только при явной применимости

Planner должен возвращать:
- protocol_name
- protocol_goal
- steps: [{id, method, config, meta}] где meta содержит “зачем” (для отчёта)

### 3.3 Report Composer (Protocol results → OmniReport)

Используем существующий генератор протокольных отчётов (DOCX/PDF/HTML) как базу и добавляем:

- единый порядок секций
- “методология” и “описание дизайна” из DesignSpec
- группировку результатов по endpoint/визитам
- таблицы и графики по шаблонам из run_diamag_full
- обсуждение/выводы (rule-based + optional AI)

## 4) Пошаговый план внедрения (без риска)

### Фаза 1 — Ввести DesignSpec и авто‑детект (без AI)

Цель: из загруженного датасета получить DesignSpec, чтобы можно было прогнать полный отчёт вообще без текста.

Шаги:
1. Добавить Pydantic модели DesignSpec.
2. Добавить авто‑детектор wide‑формата (V2..V6) и endpoints:
   - распознавание визитов по регуляркам (V\d+, Visit\s*\d+, и т.п.)
   - группировка колонок в endpoints по общему префиксу/шаблону
3. Новый API endpoint: /api/v2/omnireport/design/suggest
   - вход: dataset_id
   - выход: designSpec + confidence + список “что не удалось распознать”.

Готовность:
- на тестовом датасете DIAMAG design создаётся автоматически.
- для произвольной таблицы хотя бы базовые поля (group/time/subject/endpoints) либо понятные ошибки.

### Фаза 2 — Planner v1: DIAMAG-core как универсальный протокол

Цель: из DesignSpec собрать “DIAMAG-core” протокол, чтобы он выполнялся через существующий движок.

Шаги:
1. Реализовать OmniPlanner, который строит steps для:
   - baseline descriptives
   - per-visit comparisons
   - within-group changes
   - mixed effects (если применимо)
   - responders (если применимо)
2. Добавить строгую валидацию протокола (до запуска).
3. Новый API endpoint: /api/v2/omnireport/protocol/build
   - вход: dataset_id + designSpec
   - выход: protocol (steps + meta)

Готовность:
- протокол строится и исполняется на DIAMAG.
- на другом датасете строится “разумный” протокол или понятный отказ.

### Фаза 3 — OmniReport v1: отчёт на существующем reporting.py + спец‑секции

Цель: получить DOCX/PDF/HTML с нужной структурой.

Шаги:
1. Добавить сборку run_data: protocol_name + step_meta + results.
2. Расширить ProtocolReport/генератор DOCX:
   - добавить секции “Методология” и “Дизайн” из DesignSpec
   - упорядочить шаги по endpoint/визитам
3. Новый API endpoint: /api/v2/omnireport/run
   - вход: dataset_id + (text optional) + options
   - выход: run_id + ссылки на exports

Готовность:
- отчёт по DIAMAG близок по структуре к run_diamag_full.

### Фаза 4 — Текстовый конструктор дизайна (LLM только для DesignSpec)

Цель: пользователь описывает дизайн текстом и получает корректный DesignSpec.

Шаги:
1. Изменить AI задачу: возвращать DesignSpec (и mapping колонок), а не произвольный protocol.
2. Нормализовать/валидировать LLM-выход: если LLM “галлюцинирует” колонку — отклоняем.
3. UI: текстовое поле + превью DesignSpec + “построить отчёт”.

Готовность:
- текст может уточнить baseline, responders threshold, групповые маппинги, primary endpoint/time.

### Фаза 5 — Экспертная исчерпываемость (coverage)

Цель: расширить Planner до “экспертного исчерпывающего” набора (confirmatory + sensitivity).

Добавления:
- множественность по endpoints (FDR/BH/BKY)
- альтернативы при нарушениях допущений
- robustness checks (winsorization/trimmed mean — если добавим в engine)
- missingness сценарии (если возможно)

## 5) Риски и как их контролировать

- Риск: «исчерпывающе» превращается в “слишком много мусора”.
  - Контроль: разделить отчёт на confirmatory/sensitivity/exploratory; по умолчанию показывать core.

- Риск: LLM ломает стабильность.
  - Контроль: LLM выдаёт только DesignSpec, строго валидируемый по реальным колонкам.

- Риск: производительность на больших данных.
  - Контроль: ограничение plot_data, семплинг, кэширование по (dataset, designHash).

## 6) Критерии готовности (DoD)

- Добавление нового метода в engine не требует правок OmniPlanner, если он не участвует в core.
- OmniPlanner детерминированен: один и тот же DesignSpec → одинаковый протокол.
- OmniReport воспроизводим по run_id.
- Тесты: unit на детектор/планировщик + интеграционный прогон 1 датасета.

