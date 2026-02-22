# 🚀 AI_QUICK_START.md — Быстрый старт для AI-агентов

> **TL;DR:** Что нужно знать, чтобы начать прямо сейчас  
> **Время чтения:** 5 минут  
> **Для:** Нетерпеливых AI-агентов 😄

---

## ⚡ 30-Second Overview

**Проект:** Clinimetria — веб-платформа для статистического анализа  
**Стек:** React + FastAPI + Python stats libs  
**Статус:** 85% backend готов, 60% frontend готов  
**Цель:** Довести до production за 11-15 дней  

---

## 🎯 Топ-3 приоритета СЕЙЧАС

### 1. 🔴 CRITICAL: Установить Pingouin

**Почему:** Сейчас вручную считаем effect sizes. Pingouin даёт всё готовое.

**Что делать:**

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend
echo "pingouin>=0.5.4" >> requirements.txt
pip install pingouin
```

**Проверка:**

```python
python -c "import pingouin as pg; print(pg.__version__)"
```

**Где менять:**

- `backend/app/stats/engine.py` — заменить `scipy.stats.ttest_ind` на `pg.ttest()`

---

### 2. 🔴 CRITICAL: CSV → Parquet

**Почему:** Parquet в 5-10x быстрее, меньше места.

**Что делать:**

```bash
echo "pyarrow>=14.0.0" >> requirements.txt
pip install pyarrow
```

**Где менять:**

- `backend/app/modules/parsers.py`

  ```python
  # Было
  df.to_csv(path)
  
  # Стало
  df.to_parquet(path.replace('.csv', '.parquet'), engine='pyarrow')
  ```

---

### 3. 🟡 HIGH: Унифицировать Design System

**Почему:** Сейчас разнородные стили, сложно поддерживать.

**Что делать:**

**Файл:** `frontend/src/index.css`

```css
:root {
  /* Унифицированная палитра */
  --color-black: #0A0A0A;
  --color-white: #FFFFFF;
  --color-orange: #FF6B00;
  --color-gray-100: #F4F4F5;
  --color-gray-200: #E3E8EF;
  --color-gray-400: #A1A1AA;
  --color-gray-600: #71717A;
}

/* Kicker labels (везде) */
.kicker {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-gray-400);
}

/* Monospace для чисел */
.metric, .p-value, .stat {
  font-family: 'SF Mono', 'Consolas', monospace;
}
```

---

## 📁 Файлы, которые ты будешь часто трогать

### Backend

```
backend/app/stats/engine.py          # MAIN — все 20+ методов здесь
backend/app/modules/parsers.py       # CSV/Excel парсинг
backend/app/modules/text_generator.py # AI интерпретации
backend/requirements.txt             # Dependencies
```

### Frontend

```
frontend/src/app/pages/AnalysisDesign.jsx    # MAIN PAGE (1155 строк!)
frontend/src/app/components/VariableWorkspace.jsx  # Variable UI
frontend/src/app/components/TestConfigModal.jsx    # Test config
frontend/src/index.css                        # Design system
```

---

## 🧪 Как тестировать

### После каждого изменения

```bash
# Backend
cd backend
python -m pytest tests/ -v

# Frontend
cd frontend
npm run lint  # MUST pass with 0 errors
```

### Если тесты не проходят

1. Читай ошибку полностью
2. Изолируй проблему (тестируй по частям)
3. Добавь `print()` для дебага
4. Фикс
5. Re-run

---

## 🎨 Quick Design Rules

### Colors

```jsx
// ✅ ПРАВИЛЬНО
<div className="bg-[color:var(--color-white)] text-[color:var(--color-black)]">

// ❌ НЕПРАВИЛЬНО
<div className="bg-white text-black">  // Хардкод
```

### Typography

```jsx
// ✅ Kicker (uppercase label)
<div className="kicker">P-VALUE</div>

// ✅ Metric (monospace число)
<div className="metric font-mono">< 0.001</div>

// ✅ Regular text
<div className="text-sm text-[color:var(--color-gray-600)]">Description</div>
```

### Spacing

```jsx
// ✅ Используй 8pt grid
<div className="p-5">        {/* 20px */}
<div className="gap-4">      {/* 16px */}
<div className="mb-8">       {/* 32px section gap */}

// ❌ Не используй нестандартные значения
<div className="p-[13px]">   {/* BAD */}
```

---

## 📖 Где искать ответы

### Вопрос: "Как работает X?"

**Ответ:** `AI_CONTEXT.md` — comprehensive reference

### Вопрос: "Что делать дальше?"

**Ответ:** `implementation_plan.md` (в artifacts) — пошаговый план

### Вопрос: "Какой UI паттерн использовать?"

**Ответ:** `ui_ux_references.md` (в artifacts) — примеры кода

### Вопрос: "Какие стандарты Python/Pandas?"

**Ответ:** `SCIENTIFIC_STANDARDS.md` — best practices

### Вопрос: "Какие задачи в backlog?"

**Ответ:** `ROADMAP.md` — task list

---

## ⚠️ Что НЕ ломать

### Осторожно с этими файлами

```
backend/app/stats/engine.py          # 47KB — ядро системы
frontend/src/app/pages/AnalysisDesign.jsx  # 1155 строк — main page
backend/tests/                       # Тесты — не удалять!
```

### Правило: Рефакторить постепенно

```
❌ НЕ делай:
- Переписать engine.py целиком
- Удалить AnalysisDesign.jsx и создать с нуля

✅ ДЕЛАЙ:
- Extract функции из engine.py по одной
- Extract компоненты из AnalysisDesign.jsx по одному
```

---

## ✅ Чеклист перед коммитом

```bash
# Must ALL pass
cd backend && python -m pytest tests/ -v
cd frontend && npm run lint
git status  # Проверь, что коммитишь нужное
```

---

## 🚦 Workflow в одной картинке

```
1. Выбери задачу из implementation_plan.md
        ↓
2. Прочитай related docs (SCIENTIFIC_STANDARDS.md, etc.)
        ↓
3. Implement changes
        ↓
4. Test (pytest + lint)
        ↓
5. Commit with clear message
        ↓
6. Move to next task
```

---

## 💬 Когда спрашивать юзера

**Спроси, если:**

- Непонятные требования
- Breaking API changes
- Stuck > 30 минут
- Нужен выбор между вариантами

**НЕ спрашивай, если:**

- Можно найти в документации
- Стандартный рефакторинг
- Баг-фикс
- Добавление тестов

---

## 🎬 Start NOW

**Step 1:** Прочитай implementation_plan.md Day 1

```bash
view_file /Users/eduardbelskih/.gemini/antigravity/brain/9d77dbb5-b2d5-4a54-859f-44324293c1b8/implementation_plan.md
```

**Step 2:** Начни с Task 1.1 (Pingouin)

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend
echo "pingouin>=0.5.4" >> requirements.txt
pip install pingouin
```

**Step 3:** Тестируй

```bash
python -c "import pingouin; print('✅ OK')"
```

**Go!** 🚀

---

## 📞 Emergency Contacts

**Если всё сломалось:**

1. `git status` — что изменилось?
2. `git diff` — что именно?
3. `git checkout -- file.py` — откат файла
4. `git reset --hard HEAD` — полный откат (осторожно!)

**Если не понимаешь ошибку:**

1. Copy full traceback
2. Читай с конца
3. Google "error message python/react"
4. Спроси юзера

---

*Версия: 1.0*  
*Для нетерпеливых AI-агентов* 😄
