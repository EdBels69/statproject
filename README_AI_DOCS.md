# 📖 README — AI Documentation Suite

> **Навигация по AI-документам для StatWizard**  
> **Версия:** 1.0  
> **Дата:** 15 января 2026

---

## 🎯 Что это?

Comprehensive набор документов для автономной работы AI-агентов над проектом StatWizard.

**Цель:** Довести проект до production-ready состояния за 11-15 дней с помощью AI-агента в TRAE.

---

## 📁 Структура документов

### 🚀 Для быстрого старта (читай первым)

1. **[HOW_TO_USE_AI_DOCS.md](./HOW_TO_USE_AI_DOCS.md)** ⭐ **НАЧНИ ЗДЕСЬ**
   - Пошаговая инструкция как запустить AI-агента
   - Monitoring и checkpoints
   - Troubleshooting
   - Примеры сессий
   - **Время чтения:** 10 минут

2. **[AI_DOCS_INDEX.md](./AI_DOCS_INDEX.md)**
   - Навигация по всем документам
   - Где что найти
   - Quick reference
   - **Время чтения:** 5 минут

### 📚 Core AI Documentation

1. **[AI_PROMPT_PRODUCTION.md](./AI_PROMPT_PRODUCTION.md)**
   - **Master prompt** для TRAE
   - 3-фазный план (11 дней)
   - Execution rules
   - Code standards
   - Success criteria
   - **Скопируй это в TRAE для старта!**

2. **[AI_CONTEXT.md](./AI_CONTEXT.md)**
   - Полный контекст проекта
   - Архитектура (backend + frontend)
   - Data flows с примерами
   - 20+ statistical methods
   - Testing, deployment
   - FAQ для AI-агентов

3. **[AI_QUICK_START.md](./AI_QUICK_START.md)**
   - TL;DR для нетерпеливых
   - Топ-3 приоритета СЕЙЧАС
   - Frequently touched files
   - Quick design rules
   - Emergency procedures

### 🎯 Phase-Specific Prompts

1. **AI_PROMPT_PHASE2.md** — Variable Workspace (✅ Done)
2. **AI_PROMPT_PHASE3.md** — Publication Plots (✅ Done)
3. **AI_PROMPT_PHASE4.md** — Protocol Templates (✅ Done)
4. **AI_PROMPT_PHASE5.md** — Advanced Stats (✅ Done)
5. **AI_PROMPT_PHASE6.md** — Plots & AI (🟡 Partial)
6. **AI_PROMPT_PHASE7.md** — UX Overhaul (🟡 Partial)

### 📋 Supporting Documentation

1. **[SCIENTIFIC_STANDARDS.md](./SCIENTIFIC_STANDARDS.md)** ⭐ **ОБЯЗАТЕЛЕН**
    - Python Data Science best practices
    - Pandas, NumPy, SciPy guidelines
    - Visualization standards (300 DPI, colorblind)
    - Effect sizes, statistical methods

2. **[ROADMAP.md](./ROADMAP.md)**
    - Детальный task list
    - Priorities и statuses
    - Version planning

3. **[AGENTS.md](./AGENTS.md)**
    - General AI agent guide
    - Project conventions
    - Workflows

4. **[CONTRIBUTING.md](./CONTRIBUTING.md)**
    - Git workflow
    - Code review process
    - Release procedures

### 📊 Artifacts (в `.gemini/antigravity/brain/`)

1. **project_review.md**
    - Gap analysis (Backend 85%, Frontend 60%)
    - Feature comparison with StatTech/Jamovi
    - Technical debt assessment
    - Success criteria

2. **implementation_plan.md** ⭐ **PLAN**
    - 11-day step-by-step plan
    - File-by-file changes
    - Code examples
    - Verification commands
    - Day 1-11 detailed tasks

3. **ui_ux_references.md**
    - UI patterns from JASP, Stripe, Linear, Observable
    - Component code examples
    - Color palettes, typography
    - 50+ actionable patterns

4. **verification_report.md**
    - Confirmation всех файлов
    - Content check
    - Cross-reference validation

5. **task.md**
    - Task checklist
    - Completed items
    - Next steps

---

## ⚡ Быстрый старт (3 шага)

### 1. Прочитай инструкцию

```
open HOW_TO_USE_AI_DOCS.md
```

### 2. Скопируй Master Prompt

```
cat AI_PROMPT_PRODUCTION.md | pbcopy
```

### 3. Paste в TRAE и запусти

```
В TRAE:
1. Paste (Cmd+V)
2. Отправь
3. Напиши: "Начинай работу!"
```

**Готово!** AI-агент начнёт работать автономно.

---

## 📊 Статистика

| Метрика | Значение |
|---------|----------|
| **Всего документов** | 20 файлов |
| **Core AI docs** | 4 файла |
| **Phase prompts** | 6 файлов |
| **Supporting docs** | 5 файлов |
| **Artifacts** | 5 файлов |
| **Общий объём** | ~3,500 строк |
| **Размер** | ~90KB |
| **Время чтения (всё)** | ~2.5 часа |
| **Quick start** | ~15 минут |

---

## 🎯 Рекомендуемый порядок чтения

### Вариант 1: Хочу запустить ПРЯМО СЕЙЧАС (15 минут)

```
1. HOW_TO_USE_AI_DOCS.md         (10 мин) — КАК запустить
2. AI_PROMPT_PRODUCTION.md       (3 мин)  — СКОПИРУЙ в TRAE
3. GO!                           (∞)      — Запусти агента
```

### Вариант 2: Хочу понять контекст (1 час)

```
1. HOW_TO_USE_AI_DOCS.md         (10 мин)
2. AI_DOCS_INDEX.md              (5 мин)
3. AI_CONTEXT.md                 (30 мин)
4. implementation_plan.md        (15 мин)
5. START                         (∞)
```

### Вариант 3: Полное погружение (2.5 часа)

```
1. HOW_TO_USE_AI_DOCS.md         (10 мин)
2. AI_PROMPT_PRODUCTION.md       (15 мин)
3. SCIENTIFIC_STANDARDS.md       (30 мин)
4. AI_CONTEXT.md                 (30 мин)
5. implementation_plan.md        (40 мин)
6. ui_ux_references.md           (25 мин)
7. START                         (∞)
```

---

## 🔑 Key Documents Matrix

| Вопрос | Документ | Время |
|--------|----------|-------|
| Как запустить AI-агента? | HOW_TO_USE_AI_DOCS.md | 10 мин |
| Что скопировать в TRAE? | AI_PROMPT_PRODUCTION.md | Copy |
| Где полный контекст? | AI_CONTEXT.md | 30 мин |
| Где пошаговый план? | implementation_plan.md | 40 мин |
| Где UI паттерны? | ui_ux_references.md | 25 мин |
| Где best practices? | SCIENTIFIC_STANDARDS.md | 30 мин |
| Что делать дальше? | ROADMAP.md | 15 мин |

---

## ✅ Success Path

```
1. Читай HOW_TO_USE_AI_DOCS.md
        ↓
2. Скопируй AI_PROMPT_PRODUCTION.md в TRAE
        ↓
3. Запусти агента: "Начинай работу!"
        ↓
4. Monitor прогресс (git log, pytest)
        ↓
5. Checkpoints после каждого дня
        ↓
6. Phase 1 → Phase 2 → Phase 3
        ↓
7. Production-ready! 🎉
```

---

## 🚨 Important Notes

### ⚠️ ПЕРЕД началом

- [x] Backend dev server работает
- [x] Frontend dev server работает
- [x] Tests проходят (current baseline)
- [x] Git чистый (`git status`)

### ⚠️ ВО ВРЕМЯ работы

- Проверяй commits каждый час
- Запускай tests после каждой фазы
- Читай summary от агента
- Не прерывай агента середине задачи

### ⚠️ ПОСЛЕ каждой фазы

- All tests must pass
- App must run without errors
- Review git diff
- Check completion criteria

---

## 📞 Support

**Если что-то непонятно:**

1. Читай `AI_DOCS_INDEX.md` → "Где найти что"
2. Читай `HOW_TO_USE_AI_DOCS.md` → Troubleshooting
3. Читай `AI_CONTEXT.md` → FAQ
4. Спроси AI-агента в TRAE

**Если AI-агент застрял:**

```
"Покажи текущий статус"
"Что не получается?"
"Пропусти эту задачу и переходи к следующей"
```

---

## 🎯 Goals

**Phase 1 (3 дня):**

- ✅ Pingouin integration
- ✅ CSV → Parquet
- ✅ Effect size interpretations
- ✅ Matplotlib publication config

**Phase 2 (5 дней):**

- ✅ Design system overhaul
- ✅ Phase 7 UI integration
- ✅ JASP-style test config
- ✅ AnalysisDesign refactor

**Phase 3 (3 дней):**

- ✅ Significance brackets
- ✅ AI interpretations
- ✅ PDF/DOCX export
- ✅ E2E testing

**RESULT:** Production-ready StatWizard!

---

## 🔗 Quick Links

**Документы:**

- [HOW_TO_USE_AI_DOCS.md](./HOW_TO_USE_AI_DOCS.md) ⭐ **START HERE**
- [AI_PROMPT_PRODUCTION.md](./AI_PROMPT_PRODUCTION.md) ⭐ **COPY TO TRAE**
- [AI_DOCS_INDEX.md](./AI_DOCS_INDEX.md)
- [AI_CONTEXT.md](./AI_CONTEXT.md)
- [AI_QUICK_START.md](./AI_QUICK_START.md)

**Artifacts:**

- [implementation_plan.md](.gemini/antigravity/brain/.../implementation_plan.md) ⭐ **PLAN**
- [ui_ux_references.md](.gemini/antigravity/brain/.../ui_ux_references.md)
- [project_review.md](.gemini/antigravity/brain/.../project_review.md)

**Project:**

- [SCIENTIFIC_STANDARDS.md](./SCIENTIFIC_STANDARDS.md) ⭐ **MUST READ**
- [ROADMAP.md](./ROADMAP.md)
- [AGENTS.md](./AGENTS.md)

---

**Ready to start?** → Open `HOW_TO_USE_AI_DOCS.md` 🚀

---

*Версия: 1.0*  
*Создано: 15 января 2026*  
*Для: StatWizard Production Ready*
