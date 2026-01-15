# AI Agent Remaining Tasks — StatWizard

> **Дата:** 16 января 2026  
> **Статус:** ~75% Phase 8 выполнено, осталось 5 конкретных задач

---

## ✅ УЖЕ СДЕЛАНО (НЕ ТРОГАТЬ)

- ✅ Keyboard Navigation (типы): N/C/D/I/Delete — `VariableListView.jsx`
- ✅ Drag-and-Drop — `VariableWorkspace.jsx`
- ✅ WhyThisTest в TestSelectionPanel — импорт и рендер
- ✅ Report Customization — секции, формат, стиль
- ✅ Education компоненты — StatTooltip, EffectSizeExplainer, etc.

---

## 📋 ОСТАВШИЕСЯ ЗАДАЧИ

---

### TASK A: Добавить T/G клавиши для ролей

**Файл:** `frontend/src/app/components/VariableListView.jsx`

**Что сделать:** В функцию `handleKeyDown` (строка 93) добавить обработку T и G:

```jsx
// ДОБАВИТЬ после строки 148 (перед закрывающей скобкой handleKeyDown):

    if (key === 't') {
      e.preventDefault();
      onRoleChange?.(name, 'target');
      return;
    }
    if (key === 'g') {
      e.preventDefault();
      onRoleChange?.(name, 'factor');
      return;
    }
    if (key === 'x') {
      e.preventDefault();
      onRoleChange?.(name, 'ignore');
      return;
    }
    if (key === 'r') {
      e.preventDefault();
      onRoleChange?.(name, '');
      return;
    }
```

**Verification:**

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
```

---

### TASK B: Добавить Keyboard Hints

**Файл:** `frontend/src/app/components/VariableListView.jsx`

**Что сделать:** В конце JSX (перед закрывающим `</div>` на строке 265) добавить:

```jsx
      {/* Keyboard hints */}
      <div className="mt-4 pt-3 border-t border-[color:var(--border-color)] text-xs text-[color:var(--text-muted)]">
        <span className="font-semibold">Горячие клавиши:</span>
        {' '}↑↓ навигация • N numeric • C categorical • D date • I id
        {' '}• T target • G factor • X ignore • R убрать роль • Enter настройки
      </div>
```

---

### TASK C: GraphPad-Quality Plot Config

**Файл:** `frontend/src/app/components/VisualizePlot.jsx`

**Что сделать:** Добавить в начало файла после импортов:

```jsx
// GraphPad-style configuration
const GRAPHPAD_STYLE = {
  // Typography
  fontFamily: "'Arial', 'Helvetica Neue', sans-serif",
  fontSize: {
    title: 16,
    axisLabel: 13,
    tickLabel: 11,
    legend: 11
  },
  fontWeight: {
    title: 600,
    axisLabel: 500,
    tickLabel: 400
  },
  
  // Colors (colorblind-safe, publication-ready)
  colors: {
    primary: '#2E86AB',
    secondary: '#A23B72', 
    tertiary: '#F18F01',
    quaternary: '#C73E1D',
    text: '#1a1a1a',
    axis: '#4a4a4a',
    grid: '#e8e8e8'
  },
  palette: ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#6B8E23'],
  
  // Layout
  margin: { top: 25, right: 30, bottom: 55, left: 65 },
  
  // Axis styling (минимализм как GraphPad)
  axis: {
    strokeWidth: 1.2,
    tickSize: 5,
    tickWidth: 1
  },
  
  // Error bars
  errorBar: {
    strokeWidth: 1.5,
    capWidth: 6
  },
  
  // Grid (еле видимая как в GraphPad)
  grid: {
    stroke: '#f0f0f0',
    strokeDasharray: 'none',
    vertical: false
  }
};

// Apply to Recharts components:
// <XAxis 
//   tick={{ fontSize: GRAPHPAD_STYLE.fontSize.tickLabel, fontFamily: GRAPHPAD_STYLE.fontFamily }}
//   axisLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.strokeWidth }}
//   tickLine={{ stroke: GRAPHPAD_STYLE.colors.axis }}
// />
```

---

### TASK D: FDR Education в Knowledge Base

**Файл:** `backend/app/modules/stat_knowledge.py`

**Что сделать:** Добавить в `STAT_TERMS` после последнего термина:

```python
    "multiple_comparison": {
        "term": "Multiple Comparison Correction",
        "term_ru": "Коррекция на множественные сравнения",
        "definition": {
            "junior": "Когда делаешь много тестов, шанс ложной находки растёт. Коррекция это исправляет.",
            "mid": "При 20 тестах с α=0.05 ожидается 1 ложноположительный. FDR контролирует долю ложных среди значимых.",
            "senior": "FWER vs FDR. Bonferroni: α/n, очень консервативен. BH: step-up, контролирует E[V/R]. BY: для зависимых тестов."
        },
        "methods": {
            "bonferroni": {
                "name": "Bonferroni",
                "formula": "α_adj = α / n",
                "description_ru": "Самый строгий. Делит α на число тестов.",
                "when_to_use": "Когда ложноположительный результат недопустим"
            },
            "holm": {
                "name": "Holm-Bonferroni", 
                "description_ru": "Чуть мягче Bonferroni. Step-down процедура.",
                "when_to_use": "Когда Bonferroni слишком консервативен"
            },
            "bh": {
                "name": "Benjamini-Hochberg",
                "description_ru": "FDR контроль. Контролирует долю ложных находок.",
                "when_to_use": "Исследовательский анализ, много тестов"
            },
            "by": {
                "name": "Benjamini-Yekutieli",
                "description_ru": "FDR для зависимых тестов.",
                "when_to_use": "Когда тесты коррелируют между собой"
            }
        },
        "recommendation": "Для исследовательского анализа: BH-FDR. Для подтверждающего: Bonferroni или Holm.",
        "common_mistakes": [
            "Не корректировать при множественных сравнениях",
            "Использовать Bonferroni когда BH достаточно",
            "Путать FWER и FDR"
        ],
        "emoji": "🔢"
    },
```

---

### TASK E: BF10 с интерпретацией

**Файл:** `frontend/src/app/pages/steps/StepResults.jsx` или `CompareView.jsx`

**Что сделать:** Где показывается BF10, добавить интерпретацию:

```jsx
// Найти где рендерится bf10 и заменить на:
{result.bf10 !== undefined && result.bf10 !== null && (
  <div className="flex items-center gap-2 mt-2">
    <span className="text-sm text-[color:var(--text-secondary)]">Bayes Factor (BF₁₀):</span>
    <span className="font-mono font-semibold">{Number(result.bf10).toFixed(2)}</span>
    <span className={`text-xs px-2 py-0.5 rounded ${
      result.bf10 > 100 ? 'bg-green-100 text-green-800' :
      result.bf10 > 10 ? 'bg-green-50 text-green-700' :
      result.bf10 > 3 ? 'bg-yellow-50 text-yellow-700' :
      result.bf10 > 1 ? 'bg-gray-100 text-gray-600' :
      'bg-red-50 text-red-700'
    }`}>
      {result.bf10 > 100 ? 'очень сильные' :
       result.bf10 > 10 ? 'сильные' :
       result.bf10 > 3 ? 'умеренные' :
       result.bf10 > 1 ? 'слабые' :
       'против H₁'}
      {' '}доказательства
    </span>
  </div>
)}
```

---

## 🔍 VERIFICATION

После каждой задачи:

```bash
# Frontend lint
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint

# Backend import check
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend && python3 -c "from app.modules.stat_knowledge import STAT_TERMS; print('OK')"
```

---

## 🚀 ПОРЯДОК ВЫПОЛНЕНИЯ

1. **TASK A** — T/G клавиши (5 минут)
2. **TASK B** — Keyboard hints (2 минуты)
3. **TASK C** — GraphPad config (10 минут)
4. **TASK D** — FDR в knowledge base (5 минут)
5. **TASK E** — BF10 интерпретация (5 минут)

**Общее время: ~30 минут**

---

## START

```bash
view_file /Users/eduardbelskih/Проекты\ Github/statproject/frontend/src/app/components/VariableListView.jsx 140 160
```

Начни с TASK A. После — lint.

**GO!**
