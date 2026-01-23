---
name: Codebase Map
description: Детальная карта кодовой базы StatProject для AI-агентов
---

# 📍 Codebase Map

> Для AI-агентов: используй этот документ для навигации по проекту

---

## 🗂️ Структура проекта

```
statproject/
├── .agent/                    # 🤖 AI-агент конфигурация
│   ├── docs/                  # Документация для агентов
│   │   ├── ARCHITECTURE.md    # Архитектура (читать первым!)
│   │   ├── CODEBASE.md        # Этот файл
│   │   ├── DEVELOPMENT.md     # Как разрабатывать
│   │   └── LLM_PROMPTS.md     # Шаблоны промптов
│   ├── skills/                # Навыки для сложных задач
│   │   └── clinical-trial-analysis/
│   └── workflows/             # Пошаговые инструкции
│       ├── add-stat-method.md
│       ├── analyze-clinical-trial.md
│       ├── deploy.md
│       ├── run-tests.md
│       └── start-project.md
│
├── backend/                   # 🐍 Python Backend
│   ├── app/
│   │   ├── api/               # FastAPI endpoints
│   │   ├── core/              # Конфигурация, пайплайн
│   │   ├── configs/           # [NEW] Study configs
│   │   ├── generators/        # [NEW] Report/Article generators
│   │   ├── llm/               # [NEW] LLM интеграция
│   │   ├── modules/           # Бизнес-логика
│   │   ├── schemas/           # Pydantic модели
│   │   ├── stats/             # Статистические методы
│   │   └── templates/         # Шаблоны документов
│   ├── scripts/               # CLI скрипты
│   ├── tests/                 # Pytest тесты
│   └── workspace/             # Данные пользователей
│
├── frontend/                  # ⚛️ React Frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── components/    # UI компоненты
│   │   │   ├── pages/         # Страницы
│   │   │   └── services/      # API клиенты
│   │   └── lib/               # Утилиты
│   └── public/
│
├── docs/                      # 📚 Примеры данных
│   ├── Первичка для анализа работа.xlsx  # DIAMAG dataset
│   └── Общая таблица Ковид19.xlsx        # COVID dataset
│
└── [Config files]
    ├── README.md
    ├── ROADMAP.md
    ├── RULES.md
    ├── SCIENTIFIC_STANDARDS.md
    ├── docker-compose.yml
    └── start.sh / stop.sh
```

---

## 🐍 Backend: Детальная структура

### app/api/ — API Endpoints

| Файл | Endpoints | Описание |
|------|-----------|----------|
| `datasets.py` | CRUD /datasets | Загрузка, список, удаление |
| `analysis.py` | /analysis/* | Запуск и статус анализа |
| `reports.py` | /reports/* | Генерация отчётов [NEW] |
| `study.py` | /study/* | Study Setup [NEW] |

### app/stats/ — Статистика

| Файл | Описание | Ключевые функции |
|------|----------|------------------|
| `engine.py` | 26 методов | `run_analysis()`, `select_test()` |
| `mixed_effects.py` | LMM | `MixedEffectsEngine.fit()` |
| `assumptions.py` | Допущения | `check_normality()`, `recommend_test()` |
| `clustered_correlation.py` | Корреляции | Кластерные методы |

### app/modules/ — Бизнес-логика

| Файл | Описание | Строк |
|------|----------|-------|
| `reporting.py` | HTML/Word отчёты | ~3300 |
| `smart_scanner.py` | Авто-типизация | ~400 |
| `text_generator.py` | AI интерпретации | ~500 |
| `parsers.py` | Excel/CSV парсинг | ~300 |
| `imputation.py` | Заполнение пропусков | ~200 |
| `plot_config.py` | Matplotlib config | ~100 |

### app/llm/ — LLM интеграция [NEW]

```
llm/
├── __init__.py       # LLMService класс
├── adapters/
│   ├── base.py       # AbstractLLMAdapter
│   ├── glm.py        # GLM-4.7 adapter
│   ├── deepseek.py   # DeepSeek adapter
│   └── openai.py     # OpenAI-compatible
└── prompts/
    ├── __init__.py
    ├── discussion.py   # DISCUSSION_PROMPT
    ├── conclusions.py  # CONCLUSIONS_PROMPT
    └── article.py      # INTRODUCTION_PROMPT, etc.
```

### app/generators/ — Генераторы документов [NEW]

```
generators/
├── __init__.py
├── base.py              # AbstractGenerator
├── word_report.py       # Научный отчёт
├── article_generator.py # IMRaD статья
└── templates/
    ├── report_gost.docx
    └── article_imrad.docx
```

### app/configs/ — Конфигурации [NEW]

```python
# study_config.py
class StudyType(str, Enum):
    RCT = "rct"
    OBSERVATIONAL = "observational"

class Hypothesis(BaseModel):
    h0: str
    h1: str
    primary: bool = False

class EndpointConfig(BaseModel):
    name: str
    short_name: str
    column_pattern: Dict[str, str]  # {"V2": "col_V2", ...}
    direction: Literal["lower_is_better", "higher_is_better"]
    primary: bool = False

class StudyConfig(BaseModel):
    title: str
    objective: str
    study_type: StudyType
    hypotheses: List[Hypothesis]
    endpoints: List[EndpointConfig]
    group_column: str
    subject_id_column: str
    visits: List[str]
```

---

## ⚛️ Frontend: Детальная структура

### pages/ — Страницы

| Файл | Route | Описание |
|------|-------|----------|
| `Home.jsx` | `/` | Landing + навигация |
| `DatasetList.jsx` | `/datasets` | Список датасетов |
| `Profile.jsx` | `/datasets/:id/profile` | Настройка переменных |
| `StudySetup.jsx` | `/datasets/:id/study-setup` | Цели/гипотезы [NEW] |
| `Analyze.jsx` | `/datasets/:id/analyze` | Дизайн анализа |
| `ReportPreview.jsx` | `/datasets/:id/report` | Просмотр отчёта [NEW] |

### components/ — Компоненты

| Компонент | Назначение |
|-----------|------------|
| `DataTable.jsx` | Таблица данных |
| `VariableConfigurator.jsx` | Настройка типов |
| `EndpointSelector.jsx` | Выбор endpoints [NEW] |
| `HypothesisEditor.jsx` | Редактор гипотез [NEW] |
| `ReportSection.jsx` | Секция отчёта [NEW] |

### services/ — API клиенты

```javascript
// api.js
export const datasetsApi = {
  upload: (file) => fetch('/api/datasets/upload', ...),
  list: () => fetch('/api/datasets'),
  ...
};

export const studyApi = {
  saveConfig: (id, config) => fetch(`/api/study/${id}/config`, ...),
  suggestHypotheses: (id) => fetch(`/api/study/${id}/suggest-hypotheses`),
};

export const reportsApi = {
  generate: (id, options) => fetch('/api/reports/generate', ...),
  download: (id) => fetch(`/api/reports/${id}/download`),
};
```

---

## 🔧 Ключевые файлы для типичных задач

### Добавить новый статистический метод

1. `backend/app/stats/engine.py` — добавить в `run_analysis()`
2. `backend/app/modules/reporting.py` — добавить визуализацию
3. `backend/tests/test_engine.py` — добавить тест

### Добавить новый LLM провайдер

1. Создать `backend/app/llm/adapters/new_provider.py`
2. Унаследовать от `AbstractLLMAdapter`
3. Зарегистрировать в `backend/app/llm/__init__.py`

### Добавить новый тип отчёта

1. Создать `backend/app/generators/new_report.py`
2. Унаследовать от `AbstractGenerator`
3. Добавить шаблон в `templates/`
4. Добавить endpoint в `backend/app/api/reports.py`

### Добавить новую страницу frontend

1. Создать `frontend/src/app/pages/NewPage.jsx`
2. Добавить route в `frontend/src/App.jsx`
3. Добавить navigation в соответствующем компоненте

---

## 📊 Статистика кодовой базы

| Модуль | Файлов | Строк (прибл.) |
|--------|--------|----------------|
| Backend API | 10 | ~2000 |
| Backend Stats | 5 | ~2500 |
| Backend Modules | 12 | ~6000 |
| Backend LLM | 8 | ~800 [NEW] |
| Frontend Pages | 8 | ~3000 |
| Frontend Components | 20 | ~4000 |
| Tests | 15 | ~1500 |

**Итого**: ~20,000 строк кода
