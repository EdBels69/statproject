---
name: Project Architecture
description: Глобальная архитектура StatProject для AI-агентов
---

# 🏗️ StatProject Architecture

> **Версия**: 2.0  
> **Последнее обновление**: 2026-01-23  
> **Для**: GPT-5.2, GLM-4.7, DeepSeek, Claude

---

## 📋 Назначение проекта

**StatProject** — SaaS-приложение для статистического анализа клинических исследований с генерацией:

- Научных отчётов (Word/PDF)
- Научных статей (IMRaD формат)

### Целевая аудитория

- Врачи-исследователи
- Клинические биостатистики
- Медицинские аналитики

---

## 🏛️ Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React 18 + Vite + TailwindCSS                              │
│                                                              │
│  Pages:                                                      │
│  / (Home)                                                    │
│  ├── /datasets (список датасетов)                           │
│  ├── /datasets/:id/profile (настройка переменных)           │
│  ├── /datasets/:id/study-setup (цели/гипотезы) [NEW]        │
│  ├── /datasets/:id/analysis (запуск анализа)                │
│  └── /datasets/:id/report (просмотр/экспорт) [NEW]          │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/REST
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         BACKEND                              │
│  FastAPI + Python 3.11 + Uvicorn                            │
│                                                              │
│  Модули:                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │   api/   │ │  stats/  │ │   llm/   │ │  generators/   │  │
│  │ endpoints│ │ 26 tests │ │ adapters │ │ Word/Article   │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│  │ configs/ │ │ modules/ │ │ schemas/ │                     │
│  │ study    │ │ parsing  │ │ pydantic │                     │
│  └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       FILE STORAGE                           │
│  backend/workspace/datasets/{uuid}/                          │
│    ├── raw.xlsx                                             │
│    ├── processed.parquet                                    │
│    ├── profile.json         # типы переменных               │
│    ├── study_config.json    # цели/гипотезы [NEW]           │
│    └── analysis/{run_id}/                                   │
│        ├── results.json                                     │
│        ├── figures/                                         │
│        └── artifacts/report.docx                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Ключевые модули Backend

### 1. stats/ — Статистический движок

| Файл | Назначение | Строк |
|------|------------|-------|
| `engine.py` | 26 статистических методов | ~1800 |
| `mixed_effects.py` | LMM для повторных измерений | ~200 |
| `assumptions.py` | Проверка допущений | ~150 |

**Методы**: t-test, ANOVA, Kruskal-Wallis, Mann-Whitney, Chi-square, Pearson/Spearman, Linear/Logistic Regression, ROC, Survival, Mixed Effects

### 2. llm/ — LLM интеграция [NEW]

```
llm/
├── __init__.py          # LLMService class
├── adapters/
│   ├── base.py          # AbstractAdapter
│   ├── glm.py           # GLM-4.7 (BigModel)
│   ├── deepseek.py      # DeepSeek API
│   └── openai.py        # OpenAI/compatible
└── prompts/
    ├── discussion.py    # Раздел "Обсуждение"
    ├── conclusions.py   # Раздел "Выводы"
    └── article.py       # IMRaD генерация
```

### 3. generators/ — Генерация документов [NEW]

```
generators/
├── base.py              # AbstractGenerator
├── word_report.py       # Научный отчёт (Word)
├── article_generator.py # Статья IMRaD
├── html_report.py       # Интерактивный HTML
└── templates/
    └── *.docx, *.jinja2
```

### 4. configs/ — Конфигурации [NEW]

```python
# study_config.py
class StudyConfig(BaseModel):
    title: str
    objective: str
    hypotheses: List[Hypothesis]
    endpoints: List[EndpointConfig]
    group_column: str
    visits: List[str]
```

---

## 🔀 Data Flow

```
1. UPLOAD
   User uploads Excel → POST /api/datasets/upload
   → SmartScanner auto-detects types
   → Saved to workspace/{id}/

2. PROFILE
   User configures variables → PUT /api/datasets/{id}/profile
   → Types, roles, missing handling

3. STUDY SETUP [NEW]
   User enters objectives → POST /api/study/{id}/config
   → Hypotheses, endpoints, groups

4. ANALYSIS
   User triggers analysis → POST /api/analysis/run
   → engine.py executes tests
   → Results saved to analysis/{run_id}/

5. REPORT GENERATION
   User requests report → POST /api/reports/generate
   → generators/ creates Word/Article
   → LLM generates interpretations
```

---

## 🔌 API Endpoints

### Datasets

```
POST   /api/datasets/upload
GET    /api/datasets
GET    /api/datasets/{id}
DELETE /api/datasets/{id}
PUT    /api/datasets/{id}/profile
```

### Study Setup [NEW]

```
POST   /api/study/{id}/config
GET    /api/study/{id}/config
POST   /api/study/{id}/suggest-hypotheses  # AI
POST   /api/study/{id}/detect-endpoints    # Auto
```

### Analysis

```
POST   /api/analysis/run
GET    /api/analysis/{run_id}/status
GET    /api/analysis/{run_id}/results
```

### Reports [NEW]

```
POST   /api/reports/generate
GET    /api/reports/{id}/download
GET    /api/reports/{id}/preview
```

---

## 🛠️ Технологический стек

| Слой | Технологии |
|------|------------|
| Frontend | React 18, Vite, TailwindCSS, React Router |
| Backend | FastAPI, Python 3.11, Uvicorn |
| Statistics | Pandas, NumPy, SciPy, Pingouin, Statsmodels |
| Documents | python-docx, FPDF, Jinja2 |
| Plots | Matplotlib, Seaborn (300 DPI) |
| LLM | GLM-4.7, DeepSeek, OpenAI API |
| Storage | File system (Parquet + JSON) |

---

## ⚙️ Конфигурация

### Environment Variables (backend/.env)

```
GLM_ENABLED=true
GLM_API_KEY=your_key
GLM_API_URL=https://open.bigmodel.cn/api/paas/v4
GLM_MODEL=glm-4.7

OPENROUTER_API_KEY=your_key  # Alternative
DEEPSEEK_API_KEY=your_key    # Alternative
```

---

## 📁 Соглашения о файлах

### Naming

- Python: `snake_case.py`
- React: `PascalCase.jsx`
- API routes: `/api/resource/{id}/action`

### Imports

```python
# Стандартные
import os
from typing import Dict, List

# Third-party
import pandas as pd
from fastapi import APIRouter

# Локальные
from app.stats.engine import run_analysis
from app.configs.study_config import StudyConfig
```

---

## 🎯 Для AI-агентов: Quick Reference

### Где искать

| Задача | Файл |
|--------|------|
| Добавить стат. метод | `backend/app/stats/engine.py` |
| Изменить отчёт | `backend/app/modules/reporting.py` |
| Новый LLM адаптер | `backend/app/llm/adapters/` |
| Новый endpoint API | `backend/app/api/` |
| Frontend страница | `frontend/src/app/pages/` |
| Тесты | `backend/tests/` |

### Как запустить

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

### Как тестировать

```bash
cd backend && python -m pytest tests/ -v
```
