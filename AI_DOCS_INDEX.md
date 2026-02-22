# 📚 AI Documentation Index

> **Навигация по AI-документам для TRAE**  
> **Обновлено:** 15 января 2026

---

## 🎯 Выбери свой путь

### Я хочу начать ПРЯМО СЕЙЧАС ⚡

→ **[AI_QUICK_START.md](./AI_QUICK_START.md)**  
5 минут чтения, топ-3 приоритета, go!

### Я хочу полный контекст 📖

→ **[AI_CONTEXT.md](./AI_CONTEXT.md)**  
Comprehensive reference: архитектура, data flows, компоненты

### Я хочу пошаговый план 📋

→ **[AI_PROMPT_PRODUCTION.md](./AI_PROMPT_PRODUCTION.md)**  
Master prompt: 3 фазы, 11 дней, success criteria

### Я работаю над конкретной фазой 🎯

→ **AI_PROMPT_PHASE[2-7].md**  
Focused prompts для каждой фазы

---

## 📁 Структура документов

### Core Documents (основные)

| Файл | Размер | Назначение | Читать когда |
|------|--------|------------|--------------|
| **AI_QUICK_START.md** | 7.6KB | TL;DR + топ-3 задачи | Хочешь начать быстро |
| **AI_PROMPT_PRODUCTION.md** | 12KB | Master prompt для production | Начинаешь с нуля |
| **AI_CONTEXT.md** | 18KB | Полный контекст проекта | Нужен deep dive |

### Phase-Specific Prompts (по фазам)

| Файл | Фаза | Статус | Описание |
|------|------|--------|----------|
| AI_PROMPT_PHASE2.md | Variable Workspace | ✅ Done | Search, filters, stats |
| AI_PROMPT_PHASE3.md | Publication Plots | ✅ Done | Export PNG/SVG, settings |
| AI_PROMPT_PHASE4.md | Protocol Templates | ✅ Done | Save/load protocols |
| AI_PROMPT_PHASE5.md | Advanced Stats | ✅ Done | Mixed models, clustering |
| AI_PROMPT_PHASE6.md | Plots & AI | 🟡 Partial | Brackets, interpretations |
| AI_PROMPT_PHASE7.md | UX Overhaul | 🟡 Partial | StatTech-style UI |

### Supporting Documents (вспомогательные)

| Файл | Назначение |
|------|------------|
| **SCIENTIFIC_STANDARDS.md** | Python DS best practices (обязательно!) |
| **ROADMAP.md** | Task list, priorities |
| **AGENTS.md** | General AI agent guide |
| **CONTRIBUTING.md** | Contribution workflow |

### Artifacts (в .gemini/antigravity/brain/)

| Файл | Назначение |
|------|------------|
| **project_review.md** | Gap analysis, feature comparison |
| **implementation_plan.md** | 11-day step-by-step plan |
| **ui_ux_references.md** | UI patterns из 8 платформ |

---

## 🚀 Recommended Reading Order

### Вариант 1: Quick Start (для нетерпеливых)

```
1. AI_QUICK_START.md              (5 мин)
2. implementation_plan.md Day 1   (10 мин)
3. START CODING!                  (∞)
```

### Вариант 2: Thorough (рекомендуется)

```
1. AI_PROMPT_PRODUCTION.md        (15 мин) — Master prompt
2. SCIENTIFIC_STANDARDS.md        (20 мин) — Best practices
3. AI_CONTEXT.md                  (30 мин) — Deep dive
4. implementation_plan.md         (40 мин) — Step-by-step
5. ui_ux_references.md            (20 мин) — UI patterns
6. START PHASE 1                  (∞)
```

### Вариант 3: Phase-by-Phase

```
1. AI_PROMPT_PRODUCTION.md        — Общий контекст
2. AI_PROMPT_PHASE6.md            — Если работаешь над Phase 6
3. PHASE6_PLAN.md                 — Детальный план фазы
4. START PHASE 6                  
```

---

## 🎯 Где найти что

### Хочу понять архитектуру

→ `AI_CONTEXT.md` раздел "Архитектура"

### Хочу знать, какие методы есть

→ `AI_CONTEXT.md` раздел "Statistical Methods"

### Хочу примеры кода

→ `implementation_plan.md` — код-примеры по каждой задаче  
→ `ui_ux_references.md` — UI component code

### Хочу знать, что делать дальше

→ `implementation_plan.md` — пошаговый план  
→ `ROADMAP.md` — task list

### Хочу best practices

→ `SCIENTIFIC_STANDARDS.md` — Python/Pandas/Viz standards

### Хочу UI inspiration

→ `ui_ux_references.md` — паттерны из JASP, Stripe, Linear

---

## 📊 Document Map (визуально)

```
                    AI_QUICK_START.md
                           ↓
                    (5 мин чтения)
                           ↓
        ┌──────────────────┴──────────────────┐
        ↓                                     ↓
AI_PROMPT_PRODUCTION.md              AI_CONTEXT.md
(Master prompt)                      (Deep dive)
        ↓                                     ↓
        └──────────────────┬──────────────────┘
                           ↓
                implementation_plan.md
                    (Artifacts)
                           ↓
            ┌──────────────┼──────────────┐
            ↓              ↓              ↓
        Phase 1        Phase 2        Phase 3
    (Scientific)    (UX Transform)  (Polish)
```

---

## 🔧 Как использовать в TRAE

### Сценарий 1: Новый AI-агент начинает работу

```
1. Copy AI_PROMPT_PRODUCTION.md в TRAE chat
2. Агент читает referenced documents
3. Начинает с Phase 1, Day 1
```

### Сценарий 2: Продолжение работы

```
1. "Продолжи с Phase 2, Day 5"
2. Агент читает implementation_plan.md Day 5
3. Implement → Test → Commit
```

### Сценарий 3: Фокус на конкретной задаче

```
1. Copy AI_PROMPT_PHASE6.md
2. "Сделай Task 6.4 — significance brackets"
3. Агент читает PHASE6_PLAN.md Task 6.4
4. Implement
```

---

## 📋 Quick Reference

### Top 3 Priorities RIGHT NOW

1. **Pingouin integration** (CRITICAL)
   - `backend/requirements.txt` + `pingouin>=0.5.4`
   - `backend/app/stats/engine.py` — replace scipy with pg

2. **CSV → Parquet** (CRITICAL)
   - `pyarrow>=14.0.0`
   - `backend/app/modules/parsers.py` — to_parquet()

3. **Design System** (HIGH)
   - `frontend/src/index.css` — унифицировать палитру
   - Kicker labels, monospace numbers

### Testing Commands

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm run lint
```

### Commit Format

```
feat: add Pingouin for t-tests

- Replaced scipy.stats.ttest_ind with pg.ttest()
- Now returns Cohen's d, CI, BF10
- Updated tests

Files: backend/app/stats/engine.py

[x] pytest pass
[x] lint clean
```

---

## ❓ FAQ

**Q: С чего начать?**  
A: Читай `AI_QUICK_START.md` → `implementation_plan.md` Day 1 → GO

**Q: Где полный контекст?**  
A: `AI_CONTEXT.md` — все о проекте

**Q: Где код-примеры?**  
A: `implementation_plan.md` + `ui_ux_references.md`

**Q: Где UI паттерны?**  
A: `ui_ux_references.md` — 50+ patterns с кодом

**Q: Как тестировать?**  
A: `pytest tests/ -v` (backend) + `npm run lint` (frontend)

**Q: Когда спрашивать юзера?**  
A: Если stuck > 30 мин, breaking changes, или непонятные требования

---

## 🎨 Visual Cheatsheet

### File Size Reference

```
Tiny:    AI_PROMPT_PHASE*.md    (2-5KB)   — focused prompts
Small:   AI_QUICK_START.md      (7KB)     — quick reference
Medium:  AI_PROMPT_PRODUCTION   (12KB)    — master prompt
Large:   AI_CONTEXT.md          (18KB)    — comprehensive
Huge:    SCIENTIFIC_STANDARDS   (16KB)    — best practices
```

### Reading Time

```
⚡ Quick:     AI_QUICK_START.md         5 мин
📖 Medium:    AI_PROMPT_PRODUCTION.md   15 мин
🏗️ Deep:      AI_CONTEXT.md             30 мин
📚 Complete:  All documents              2 часа
```

---

## 🚦 Status Legend

- ✅ **Done** — полностью завершено
- 🟡 **Partial** — частично сделано
- ❌ **Todo** — не начато
- 🔴 **Critical** — высокий приоритет
- 🟡 **High** — важно
- 🟢 **Medium** — можно отложить

---

## 📞 Support

**Если застрял:**

1. Поищи в `AI_CONTEXT.md` FAQ section
2. Проверь `implementation_plan.md` для своей задачи
3. Читай `SCIENTIFIC_STANDARDS.md` для best practices
4. Спроси юзера

---

*Happy coding!* 🚀

*Версия: 1.0*  
*Обновлено: 15 января 2026*
