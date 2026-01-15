# 🎯 HOW_TO_USE_AI_DOCS.md — Инструкция по использованию

> **Как запустить AI-агента в TRAE и начать работу**  
> **Обновлено:** 15 января 2026

---

## 🚀 Быстрый старт (5 минут)

### Шаг 1: Открой TRAE

1. Запусти TRAE
2. Создай новую conversation
3. Выбери модель: **GPT 5.2**

### Шаг 2: Скопируй Master Prompt

```bash
# Открой файл
open /Users/eduardbelskih/Проекты\ Github/statproject/AI_PROMPT_PRODUCTION.md
```

**Или через терминал:**

```bash
cat AI_PROMPT_PRODUCTION.md | pbcopy
```

### Шаг 3: Вставь в TRAE

1. Paste (Cmd+V) в TRAE chat
2. Отправь сообщение
3. AI-агент начнёт читать документацию

### Шаг 4: Дай команду

**Пример команды:**

```
Начни с Phase 1, Day 1. 
Установи Pingouin и проверь, что всё работает.
Отчитайся о результате.
```

**Или просто:**

```
Начинай работу по плану!
```

---

## 📋 Что AI-агент будет делать

### Автоматический workflow

1. **Читает документы** (5-10 минут)
   - SCIENTIFIC_STANDARDS.md
   - ROADMAP.md
   - implementation_plan.md (из artifacts)
   - ui_ux_references.md (из artifacts)

2. **Начинает Phase 1, Day 1**
   - Устанавливает Pingouin
   - Добавляет pyarrow
   - Проверяет работу
   - Коммитит

3. **Переходит к Day 2**
   - Интегрирует Pingouin в engine.py
   - Заменяет t-tests
   - Запускает pytest
   - Коммитит

4. **Продолжает по плану...**

### Что он будет делать после каждой задачи

```
✅ Implement changes
✅ Run tests (pytest + lint)
✅ Commit with clear message
✅ Report progress
✅ Move to next task
```

---

## 💬 Как общаться с AI-агентом

### Хорошие команды

```
✅ "Продолжай с Day 3"
✅ "Сделай Task 2.1 из Phase 2"
✅ "Отчитайся о текущем прогрессе"
✅ "Что осталось сделать в Phase 1?"
✅ "Запусти все тесты и покажи результаты"
```

### Плохие команды

```
❌ "Сделай всё" (слишком расплывчато)
❌ "Улучши UI" (без конкретики)
❌ "Исправь баги" (какие именно?)
```

### Если агент застрял

```
"Пропусти эту задачу и переходи к следующей"
"Объясни, в чём проблема"
"Покажи ошибку полностью"
```

---

## 📊 Monitoring прогресса

### Проверяй регулярно

**1. Git commits:**

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject
git log --oneline -10
```

**2. Tests status:**

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm run lint
```

**3. Файлы изменения:**

```bash
git status
git diff
```

---

## ⏱️ Timeline

### Примерное время на каждую фазу

| Phase | Дни | Задачи | Когда проверять |
|-------|-----|--------|-----------------|
| Phase 1 | 3 | 4 задачи | После Day 1, Day 2, Day 3 |
| Phase 2 | 5 | 4 задачи | После Day 4, 6, 8 |
| Phase 3 | 3 | 4 задачи | После Day 9, 10, 11 |

### Ожидаемые результаты по дням

**Day 1:**

- ✅ Pingouin установлен
- ✅ Parquet работает
- ✅ 1-2 commits

**Day 2:**

- ✅ T-tests используют Pingouin
- ✅ Effect sizes возвращаются
- ✅ Pytest проходит

**Day 3:**

- ✅ ANOVA на Pingouin
- ✅ Effect size интерпретация работает
- ✅ Matplotlib config настроен

**Day 4-8:**

- ✅ Design system унифицирован
- ✅ AnalysisDesign.jsx рефакторен
- ✅ TestConfigModal с tabs
- ✅ Phase 7 компоненты интегрированы

**Day 9-11:**

- ✅ Significance brackets на графиках
- ✅ AI интерпретации
- ✅ PDF/DOCX export
- ✅ E2E тесты проходят

---

## 🔍 Checkpoints

### После каждого дня проверяй

**1. Tests pass:**

```bash
cd backend && python -m pytest tests/ -v
cd frontend && npm run lint
```

**2. App runs:**

```bash
# Backend
cd backend && uvicorn app.main:app --reload

# Frontend  
cd frontend && npm run dev
```

**3. No console errors:**

- Открой <http://localhost:5173>
- Check browser console (F12)
- Should be error-free

---

## 🚨 Troubleshooting

### Проблема: AI-агент не видит artifacts

**Решение:**

```
Скажи агенту:
"Прочитай файл по absolute path:
/Users/eduardbelskih/.gemini/antigravity/brain/9d77dbb5-b2d5-4a54-859f-44324293c1b8/implementation_plan.md"
```

### Проблема: Tests не проходят

**Решение:**

```
"Покажи полный traceback ошибки"
"Запусти только failed test с verbose"
"Откатись на последний working commit"
```

### Проблема: Агент просит подтверждения

**Если это:**

- Breaking changes → Review и approve
- Обычный рефакторинг → "Продолжай автономно"
- Непонятно что делать → Уточни задачу

### Проблема: Агент остановился

**Команды для продолжения:**

```
"Продолжай с того места, где остановился"
"Покажи текущий статус Phase [N]"
"Что осталось сделать?"
```

---

## 📝 Примеры сессий

### Пример 1: Полная Phase 1 за одну сессию

```
USER:
Начни с Phase 1. Делай все 3 дня подряд.
После каждого дня — summary. GO!

AI:
[читает документы]
✅ Day 1: Pingouin installed...
✅ Day 2: T-tests migrated...
✅ Day 3: ANOVA + effect sizes...
Phase 1 COMPLETE! Tests: 100% pass.

USER:
Отлично! Начинай Phase 2.
```

### Пример 2: По частям с проверками

```
USER:
Сделай Day 1, Task 1.1 — установи Pingouin.

AI:
✅ Added pingouin>=0.5.4 to requirements.txt
✅ pip install successful
✅ import pingouin works
Commit: "feat: add Pingouin dependency"

USER:
Хорошо. Теперь Task 1.2 — Parquet.

AI:
✅ Added pyarrow>=14.0.0
✅ Modified parsers.py to use to_parquet()
✅ Tests pass
Commit: "feat: migrate to Parquet format"

USER:
Продолжай с Day 2.
```

### Пример 3: Troubleshooting

```
USER:
Начни Day 2 — интеграция Pingouin в engine.py

AI:
❌ Error: Test failed in test_engine.py::test_ttest_ind
TypeError: 'DataFrame' object is not callable

USER:
Покажи полный traceback

AI:
[показывает ошибку]

USER:
Фикс: используй .iloc[0] для извлечения значения

AI:
✅ Fixed: result['cohen-d'].iloc[0]
✅ Tests now pass
Commit: "fix: extract cohen-d value correctly"
```

---

## 🎯 Success Indicators

### Phase 1 успешна, если

```bash
# 1. Pingouin работает
python -c "import pingouin as pg; print(pg.ttest([1,2,3], [4,5,6]))"

# 2. Parquet файлы создаются
ls backend/workspace/*.parquet

# 3. All tests pass
cd backend && python -m pytest tests/ -v
# Expected: PASSED, 0 failed

# 4. Effect sizes в результатах
curl localhost:8000/api/v2/analysis/execute -X POST -d '{...}'
# Response должен содержать: effect_size, effect_size_interpretation
```

### Phase 2 успешна, если

```bash
# 1. Design system унифицирован
grep "color-black" frontend/src/index.css
grep "kicker" frontend/src/index.css

# 2. AnalysisDesign < 500 строк
wc -l frontend/src/app/pages/AnalysisDesign.jsx
# Expected: < 500

# 3. Lint clean
cd frontend && npm run lint
# Expected: 0 errors

# 4. TestConfigModal tabs работают
# Визуально проверить в браузере
```

### Phase 3 успешна, если

```bash
# 1. Significance brackets на графиках
# Визуально проверить — должны быть *, **, ***

# 2. AI интерпретации
curl localhost:8000/api/v2/analysis/execute -X POST -d '{...}'
# Response: "ai_interpretation": "Выявлены статистически значимые..."

# 3. PDF export работает
# Кнопка "Скачать PDF" должна давать файл

# 4. E2E test
cd backend && python -m pytest tests/test_e2e_full_workflow.py -v
# Expected: PASSED
```

---

## 📚 Дополнительные ресурсы

### Если нужна помощь

**Документация:**

- `AI_CONTEXT.md` — полный контекст проекта
- `AI_QUICK_START.md` — быстрые ответы
- `SCIENTIFIC_STANDARDS.md` — best practices
- `ROADMAP.md` — what's next

**Artifacts:**

- `project_review.md` — gap analysis
- `implementation_plan.md` — пошаговый план
- `ui_ux_references.md` — UI patterns

**Если совсем застряли:**

```
В TRAE напиши:
"Прочитай AI_CONTEXT.md раздел [название] и объясни"
"Покажи пример кода для [задача]"
"Как проверить [что-то]?"
```

---

## ✅ Final Checklist

### Перед началом работы

- [ ] TRAE запущен
- [ ] GPT 5.2 выбрана
- [ ] AI_PROMPT_PRODUCTION.md скопирован
- [ ] Backend dev server работает (`uvicorn app.main:app --reload`)
- [ ] Frontend dev server работает (`npm run dev`)

### Во время работы

- [ ] Проверяю commits каждый час (`git log`)
- [ ] Запускаю tests после каждой фазы
- [ ] Проверяю app в браузере периодически
- [ ] Читаю summary от агента

### После каждой фазы

- [ ] All tests pass (pytest + lint)
- [ ] App runs without errors
- [ ] Git commits clean
- [ ] Phase completion criteria met (см. AI_PROMPT_PRODUCTION.md)

---

## 🎬 Готов начать?

**Финальная команда для AI-агента:**

```
Прочитай все referenced documents и начинай работу с Phase 1, Day 1.
Работай автономно, но:
- Отчитывайся после каждого дня
- Спрашивай только если stuck > 30 минут
- Коммить с clear messages

GO! 🚀
```

---

**Happy automating!** 🤖

*Версия: 1.0*  
*Создано: 15 января 2026*  
*Для: StatWizard Project*
