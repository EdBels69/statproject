# 🚀 Промпт для GPT Codex 5.2 — Clinimetria v6
>
> Дата: 2026-01-27

## 🎯 Статус проекта: Phase 4 COMPLETE (100%)

Clinimetria — клиническая статистика с AI-интерпретациями (Python FastAPI + React).

---

## ✅ Завершённые компоненты

### Backend (`/backend/app/`)

| Компонент | Путь | Статус |
|-----------|------|--------|
| Data Normalizer | `modules/data_normalizer.py` | ✅ |
| Study Detector | `modules/study_detector.py` | ✅ |
| LLM Adapters | `llm/adapters/{glm,deepseek,gemini}.py` | ✅ |
| LLM Prompts | `llm/prompts/*.py` (5 файлов) | ✅ |
| Word Generator | `generators/word_report.py` | ✅ |
| PDF Generator | `generators/pdf_report.py` | ✅ |
| HTML Generator | `generators/html_report.py` | ✅ |
| Export Endpoint | `api/analysis.py` → `/universal/export/{format}` | ✅ |

### Frontend (`/frontend/src/app/`)

| Компонент | Путь | Статус |
|-----------|------|--------|
| StudyDesignConfirmation | `components/StudyDesignConfirmation.jsx` | ✅ |
| ExportButtons | `components/ExportButtons.jsx` | ✅ |

---

## 🔧 Следующие задачи

### P0: Интеграция ExportButtons в UI

```
Файл: frontend/src/app/pages/AnalysisDesign.jsx
Действие: Добавить <ExportButtons datasetId={id} /> после результатов анализа
```

### P1: Рефакторинг монолитов

```
1. backend/app/modules/reporting.py (158KB) → разбить на модули
2. frontend/src/app/pages/ProtocolSorcerer.jsx (143KB) → на компоненты
```

### P2: E2E тестирование

```
1. Загрузить Excel через /datasets/upload
2. POST /analyze/universal/export/docx
3. Проверить AI-интерпретации
```

---

## 📁 Ключевые файлы

```
backend/app/
├── api/analysis.py              # API endpoints, /universal/export
├── generators/                  # Word/PDF/HTML генераторы
│   ├── word_report.py (191 lines)
│   ├── pdf_report.py (155 lines)
│   └── html_report.py (290 lines)
├── llm/adapters/                # glm, deepseek, gemini
├── llm/prompts/                 # 5 промптов AI
└── modules/study_detector.py    # Авто-детекция дизайна

frontend/src/app/
├── pages/AnalysisDesign.jsx     # Главная страница
├── components/StudyDesignConfirmation.jsx
└── components/ExportButtons.jsx
```

---

## ⚠️ Правила

1. **НЕ трогать**: `StatWiki.jsx`, `SampleSizeCalculator.jsx`
2. **LLM**: Приоритет бесплатным (DeepSeek, Gemini)
3. **Тесты**: 60+ тестов должны проходить
4. **Коммиты**: На русском (`feat:`, `fix:`, `chore:`)

---

## 🧪 Проверка

```bash
# Backend
cd backend && python3 -m pytest tests/ -v

# Frontend  
cd frontend && npm run build

# Generators
python3 -c "from app.generators import PDFReportGenerator; print('OK')"
```

---

## 📊 Метрики

- Тесты: 60 passed (14.67s)
- Frontend build: 3.57s
- Phase 1-4: 100% complete
