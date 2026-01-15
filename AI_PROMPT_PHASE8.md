# AI Agent Master Prompt — StatWizard Completion

> **КОНТЕКСТ:** ~80% первоначального плана выполнено. Осталось довести UX до Jamovi-уровня.  
> **ВРЕМЯ:** 16 января 2026  
> **ЦЕЛЬ:** Сделать StatWizard гибким как Jamovi, красивым как FlowingData, умным как StatTech.

---

## 🎯 MISSION

Превратить StatWizard из "пошагового wizard" в **гибкий аналитический workspace** где:

1. Переменные назначаются **drag-and-drop** (как Jamovi)
2. Результаты обновляются **мгновенно** при изменениях
3. **Умные подсказки** объясняют каждый шаг (уже есть компоненты!)
4. **Визуализации минималистичные**, но информативные

---

## ✅ ЧТО УЖЕ СДЕЛАНО (НЕ ТРОГАТЬ!)

### Backend

- ✅ Pingouin 0.5.5 — все t-tests, ANOVA с effect sizes
- ✅ Parquet — быстрое сохранение/чтение данных
- ✅ Effect sizes — Cohen's d, η², r, BF10
- ✅ plot_config.py (223 строки) — FlowingData стиль
- ✅ stat_knowledge.py (~900 строк) — Knowledge base + академические ссылки + APA templates
- ✅ knowledge.py — API `/v2/knowledge/*`

### Frontend — Education

- ✅ `StatTooltip.jsx` — hover explanations
- ✅ `EffectSizeExplainer.jsx` — visual scale
- ✅ `PowerExplainer.jsx` — recommendations
- ✅ `WhyThisTest.jsx` — test rationale

### Frontend — UI Components

- ✅ Badge, Button, Card, Input, Table, Tabs
- ✅ VariableWorkspace.jsx — поиск, фильтры, virtualised list
- ✅ DataTableWithTypes.jsx — inline type selectors
- ✅ VariableListView.jsx — variable cards

### Frontend — Protocol System (УЖЕ ПОЛНОСТЬЮ ГОТОВО!)

- ✅ `SaveProtocolModal.jsx` (430 строк) — сохранение, загрузка, экспорт JSON
- ✅ `ProtocolLibraryModal` — библиотека протоколов
- ✅ `ProtocolBuilder.jsx` (318 строк) — редактирование, перемещение тестов
- ✅ `ProtocolTemplateSelector.jsx` (263 строк) — выбор шаблонов, auto-suggestions

### Frontend — UX Features (УЖЕ ГОТОВО!)

- ✅ `ResearchFlowNav.jsx` — визуальный pipeline 📁→📊→🧪→📄
- ✅ `useUndoRedo` hook — Undo/Redo
- ✅ `KeyboardShortcutsHelp.jsx` — справка по горячим клавишам
- ✅ `educationLevel` в LanguageContext

---

## 📋 ЗАДАЧИ ДЛЯ ВЫПОЛНЕНИЯ

---

### TASK 1: Drag-and-Drop Variables (PRIORITY: HIGH)

**Файл:** `frontend/src/app/components/VariableWorkspace.jsx`

**Что сделать:**

1. Добавить `draggable={true}` к variable cards
2. Создать drop zones для Target, Group, Covariates
3. Visual feedback при drag over
4. Обновлять state при drop

**Код для добавления:**

```jsx
// 1. Сделать карточки draggable
const VariableCard = ({ variable, onAssign }) => (
  <div
    draggable={true}
    onDragStart={(e) => {
      e.dataTransfer.setData('application/json', JSON.stringify({
        name: variable.name,
        type: variable.type
      }));
      e.dataTransfer.effectAllowed = 'move';
      e.currentTarget.classList.add('dragging');
    }}
    onDragEnd={(e) => {
      e.currentTarget.classList.remove('dragging');
    }}
    className="variable-card cursor-grab active:cursor-grabbing"
  >
    <div className="flex items-center gap-2">
      <span className="font-medium">{variable.name}</span>
      <span className="type-badge">{variable.type}</span>
    </div>
  </div>
);

// 2. Drop zone для ролей
const RoleDropZone = ({ role, label, icon, variable, onDrop, onRemove }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragOver(false);
        const data = JSON.parse(e.dataTransfer.getData('application/json'));
        onDrop(role, data.name);
      }}
      className={`role-dropzone ${isDragOver ? 'drag-over' : ''} ${variable ? 'has-variable' : ''}`}
    >
      {variable ? (
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <span>{icon}</span>
            <span className="font-medium">{variable}</span>
          </div>
          <button onClick={() => onRemove(role)} className="text-gray-400 hover:text-red-500">
            ✕
          </button>
        </div>
      ) : (
        <div className="text-gray-400 text-sm">
          {icon} {label}
        </div>
      )}
    </div>
  );
};
```

**CSS (добавить в `frontend/src/index.css`):**

```css
/* Drag and Drop */
.variable-card.dragging {
  opacity: 0.5;
  transform: scale(0.95);
}

.role-dropzone {
  min-height: 52px;
  border: 2px dashed var(--border-color);
  border-radius: 6px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  transition: all 0.15s ease;
  background: var(--white);
}

.role-dropzone.drag-over {
  border-color: var(--accent);
  background: rgba(255, 107, 0, 0.05);
  border-style: solid;
}

.role-dropzone.has-variable {
  border-style: solid;
  border-color: var(--border-color);
}

.role-dropzone.has-variable.target {
  border-left: 3px solid var(--accent);
}

.role-dropzone.has-variable.group {
  border-left: 3px solid var(--black);
}
```

**Verification:**

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
```

**Success criteria:**

- [ ] Карточки переменных можно перетаскивать
- [ ] Drop zones визуально реагируют на drag over
- [ ] После drop назначается роль
- [ ] Можно удалить назначенную переменную

---

### TASK 2: WhyThisTest в TestSelectionPanel (PRIORITY: HIGH)

**Файл:** `frontend/src/app/components/analysis/TestSelectionPanel.jsx`

**Что сделать:**

Импортировать и показывать `WhyThisTest` когда тест выбран.

**Код:**

```jsx
// Добавить import в начало файла
import { WhyThisTest } from '../education';
import { useLanguage } from '../../contexts/LanguageContext';

// Внутри компонента
const { educationLevel } = useLanguage();

// После списка тестов, когда один выбран
{selectedTest && (
  <div className="mt-6">
    <WhyThisTest 
      testId={selectedTest.id}
      dataProfile={{
        shapiro_p: dataContext?.normality?.p_value,
        levene_p: dataContext?.homogeneity?.p_value,
        independence: true
      }}
      level={educationLevel || 'junior'}
      defaultExpanded={true}
    />
  </div>
)}
```

**Success criteria:**

- [ ] При выборе теста показывается WhyThisTest
- [ ] Объяснение соответствует выбранному уровню
- [ ] Если есть assumption_checks — показывает статус

---

### TASK 3: Live Preview при изменении переменных (PRIORITY: MEDIUM)

**Файл:** `frontend/src/app/pages/AnalysisDesign.jsx`

**Что сделать:**

Показывать preview когда Target или Group выбраны.

**Код:**

```jsx
// Новый компонент VariablePreview
const VariablePreview = ({ targetVar, groupVar, data }) => {
  const { t } = useTranslation();
  
  const stats = useMemo(() => {
    if (!targetVar || !data) return null;
    
    const values = data.map(row => parseFloat(row[targetVar])).filter(v => !isNaN(v));
    if (values.length === 0) return null;
    
    const n = values.length;
    const mean = values.reduce((a, b) => a + b, 0) / n;
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (n - 1);
    const sd = Math.sqrt(variance);
    const min = Math.min(...values);
    const max = Math.max(...values);
    
    // Check for issues
    const warnings = [];
    if (n < 30) warnings.push(`Малая выборка (n=${n})`);
    if (sd === 0) warnings.push('Нет вариации в данных');
    
    return { n, mean, sd, min, max, warnings };
  }, [targetVar, data]);
  
  if (!stats) return null;
  
  return (
    <div className="variable-preview bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-lg p-4 mt-4">
      <div className="text-[10px] uppercase tracking-wider text-[color:var(--text-muted)] font-semibold mb-2">
        {t('preview')}
      </div>
      <div className="flex flex-wrap gap-4 text-sm">
        <div>
          <span className="text-[color:var(--text-secondary)]">n = </span>
          <span className="font-mono font-semibold">{stats.n}</span>
        </div>
        <div>
          <span className="text-[color:var(--text-secondary)]">M = </span>
          <span className="font-mono font-semibold">{stats.mean.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[color:var(--text-secondary)]">SD = </span>
          <span className="font-mono font-semibold">{stats.sd.toFixed(2)}</span>
        </div>
        <div>
          <span className="text-[color:var(--text-secondary)]">Range: </span>
          <span className="font-mono">{stats.min.toFixed(1)} – {stats.max.toFixed(1)}</span>
        </div>
      </div>
      {stats.warnings.length > 0 && (
        <div className="mt-2 text-amber-600 text-sm">
          ⚠️ {stats.warnings.join(' • ')}
        </div>
      )}
    </div>
  );
};

// В основном компоненте, после выбора переменных
{(protocol.target || protocol.group) && (
  <VariablePreview 
    targetVar={protocol.target}
    groupVar={protocol.group}
    data={dataRows}
  />
)}
```

**Success criteria:**

- [ ] При выборе Target показываются базовые статистики
- [ ] Показываются warnings при проблемах
- [ ] Обновляется мгновенно при изменении

---

### TASK 4: FlowingData стиль для VisualizePlot (PRIORITY: MEDIUM)

**Файл:** `frontend/src/app/components/VisualizePlot.jsx`

**Что сделать:**

Применить минималистичный стиль из VISUALIZATION_STYLE_GUIDE.md:

1. Убрать верхнюю/правую оси
2. Легкие gridlines (alpha 0.2)
3. Colorblind-safe палитра
4. Larger font для labels

**Код (обновить константы в начале файла):**

```jsx
// FlowingData color palette (colorblind-safe)
const COLORS = {
  primary: '#0f172a',     // Slate 900
  secondary: '#64748b',   // Slate 500
  accent: '#8b5cf6',      // Purple 500
  positive: '#10b981',    // Emerald 500
  negative: '#ef4444',    // Red 500
  groups: [
    '#4269d0',  // Blue
    '#ef9154',  // Orange
    '#4ca858',  // Green
    '#db4949',  // Red
    '#9d69a3',  // Purple
    '#d3a642',  // Gold
  ]
};

// Chart configuration
const CHART_CONFIG = {
  grid: {
    strokeDasharray: 'none',
    stroke: '#e2e8f0',
    strokeOpacity: 0.5
  },
  axis: {
    stroke: '#94a3b8',
    strokeWidth: 0.5,
    tickLine: false
  },
  fontSize: {
    title: 16,
    label: 12,
    tick: 11
  },
  margin: {
    top: 20,
    right: 20,
    bottom: 40,
    left: 60
  }
};

// В Recharts компонентах использовать:
<XAxis 
  dataKey="group"
  axisLine={{ stroke: CHART_CONFIG.axis.stroke, strokeWidth: CHART_CONFIG.axis.strokeWidth }}
  tickLine={false}
  tick={{ fontSize: CHART_CONFIG.fontSize.tick, fill: COLORS.secondary }}
/>
<YAxis 
  axisLine={{ stroke: CHART_CONFIG.axis.stroke }}
  tickLine={false}
  tick={{ fontSize: CHART_CONFIG.fontSize.tick, fill: COLORS.secondary }}
/>
<CartesianGrid 
  strokeDasharray="none" 
  stroke={CHART_CONFIG.grid.stroke} 
  strokeOpacity={CHART_CONFIG.grid.strokeOpacity}
  vertical={false}
/>
```

**Success criteria:**

- [ ] Графики минималистичные (нет верхней/правой оси)
- [ ] Цвета colorblind-safe
- [ ] Gridlines еле видны

---

### TASK 5: Education Level в Settings (PRIORITY: LOW)

**Файл:** `frontend/src/app/pages/Settings.jsx`

**Что сделать:**

Добавить UI для выбора уровня объяснений.

**Код:**

```jsx
// Импорт
import { useLanguage } from '../../contexts/LanguageContext';

// В компоненте
const { educationLevel, setEducationLevel } = useLanguage();

// В JSX (добавить секцию)
<div className="settings-section">
  <h3 className="settings-section-title">{t('education_settings')}</h3>
  
  <div className="setting-row">
    <div className="setting-info">
      <label className="setting-label">{t('explanation_level')}</label>
      <p className="setting-description">{t('explanation_level_desc')}</p>
    </div>
    <select 
      value={educationLevel || 'junior'}
      onChange={(e) => setEducationLevel(e.target.value)}
      className="setting-select"
    >
      <option value="junior">{t('level_junior')}</option>
      <option value="mid">{t('level_mid')}</option>
      <option value="senior">{t('level_senior')}</option>
    </select>
  </div>
</div>
```

**Файл:** `frontend/src/lib/i18n.js` — добавить переводы:

```js
// В русский объект
education_settings: 'Образование',
explanation_level: 'Уровень объяснений',
explanation_level_desc: 'Влияет на сложность подсказок и объяснений статистики',
level_junior: 'Базовый — простые объяснения',
level_mid: 'Средний — формулы и связи',
level_senior: 'Продвинутый — граничные случаи',
```

**Success criteria:**

- [ ] В Settings есть секция выбора уровня
- [ ] Выбор сохраняется
- [ ] Влияет на StatTooltip и WhyThisTest

---

### TASK 6: Keyboard Navigation (PRIORITY: LOW)

**Файл:** `frontend/src/app/components/VariableWorkspace.jsx`

**Что сделать:**

Добавить навигацию клавиатурой:

- ↑/↓ — перемещение по списку
- Enter — выбор переменной
- T/G/C — быстрое назначение роли (Target/Group/Covariate)

**Код:**

```jsx
// Добавить state и ref
const [focusedIndex, setFocusedIndex] = useState(-1);
const listRef = useRef(null);

// Keyboard handler
useEffect(() => {
  const handleKeyDown = (e) => {
    if (!listRef.current?.contains(document.activeElement)) return;
    
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => Math.min(prev + 1, filteredVariables.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => Math.max(prev - 1, 0));
        break;
      case 'Enter':
        if (focusedIndex >= 0) {
          // Toggle selection
          const varName = filteredVariables[focusedIndex].name;
          onSelect?.(varName);
        }
        break;
      case 't':
      case 'T':
        if (focusedIndex >= 0) {
          onAssignRole?.(filteredVariables[focusedIndex].name, 'target');
        }
        break;
      case 'g':
      case 'G':
        if (focusedIndex >= 0) {
          onAssignRole?.(filteredVariables[focusedIndex].name, 'group');
        }
        break;
    }
  };
  
  document.addEventListener('keydown', handleKeyDown);
  return () => document.removeEventListener('keydown', handleKeyDown);
}, [focusedIndex, filteredVariables, onSelect, onAssignRole]);

// Добавить focus ring к карточкам
className={`variable-card ${index === focusedIndex ? 'ring-2 ring-[color:var(--accent)]' : ''}`}
```

**Success criteria:**

- [ ] ↑/↓ перемещает фокус
- [ ] Enter выбирает
- [ ] T/G/C назначает роль
- [ ] Работает с поиском

---

### ~~TASK 7: Visual Flow Pipeline~~ ✅ УЖЕ ГОТОВО

> **ResearchFlowNav.jsx уже существует и интегрирован в AnalysisDesign.jsx!**
> Пропускай этот task.

**Файл:** `frontend/src/app/components/ResearchFlowNav.jsx` — уже создан

**Что сделать:**

Добавить визуальный pipeline сверху страницы, показывающий текущий шаг и прогресс.

**Дизайн:**

```
📁 Данные  →  📊 Переменные  →  🧪 Анализ  →  📄 Результат
   ✅            ✅               🔄              ○
 150 rows     Age, Group      Welch t         ожидает
```

**Код:**

```jsx
import React from 'react';

const STEPS = [
  { id: 'data', icon: '📁', label: 'Данные', key: 'dataLoaded' },
  { id: 'variables', icon: '📊', label: 'Переменные', key: 'variablesSet' },
  { id: 'analysis', icon: '🧪', label: 'Анализ', key: 'analysisRunning' },
  { id: 'results', icon: '📄', label: 'Результат', key: 'resultsReady' }
];

export default function ResearchFlowNav({ 
  currentStep, 
  stepData = {},
  onStepClick 
}) {
  return (
    <nav className="research-flow-nav flex items-center justify-center gap-2 py-4 px-6 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)]">
      {STEPS.map((step, idx) => {
        const isActive = step.id === currentStep;
        const isComplete = stepData[step.key];
        
        return (
          <React.Fragment key={step.id}>
            {idx > 0 && (
              <div className={`w-8 h-0.5 ${isComplete ? 'bg-[color:var(--accent)]' : 'bg-[color:var(--border-color)]'}`} />
            )}
            <button
              onClick={() => onStepClick?.(step.id)}
              className={`
                flex flex-col items-center gap-1 px-4 py-2 rounded-lg transition-all
                ${isActive ? 'bg-[color:var(--white)] shadow-sm' : 'hover:bg-[color:var(--white)]'}
              `}
            >
              <span className="text-xl">{step.icon}</span>
              <span className={`text-xs font-medium ${isActive ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-secondary)]'}`}>
                {step.label}
              </span>
              {stepData[step.id + '_summary'] && (
                <span className="text-[10px] text-[color:var(--text-muted)] font-mono">
                  {stepData[step.id + '_summary']}
                </span>
              )}
              {/* Status indicator */}
              <span className={`text-xs ${isComplete ? 'text-green-500' : isActive ? 'text-amber-500' : 'text-gray-300'}`}>
                {isComplete ? '✅' : isActive ? '🔄' : '○'}
              </span>
            </button>
          </React.Fragment>
        );
      })}
    </nav>
  );
}
```

**Интеграция в `AnalysisDesign.jsx`:**

```jsx
import ResearchFlowNav from '../components/ResearchFlowNav';

// В JSX перед основным контентом
<ResearchFlowNav
  currentStep={currentStep}
  stepData={{
    dataLoaded: !!dataRows?.length,
    variablesSet: !!(protocol.target && protocol.group),
    analysisRunning: isAnalyzing,
    resultsReady: !!results,
    data_summary: dataRows?.length ? `${dataRows.length} rows` : '',
    variables_summary: protocol.target ? `${protocol.target}, ${protocol.group}` : ''
  }}
  onStepClick={handleStepClick}
/>
```

**Success criteria:**

- [ ] Visual pipeline показывает все шаги
- [ ] Текущий шаг highlighted
- [ ] Completed шаги с галочкой
- [ ] Summary под каждым шагом (опционально)

---

### TASK 8: Step-by-Step Preview Panel (PRIORITY: HIGH) — NEW

**Файл:** `frontend/src/app/components/StepPreviewPanel.jsx` (новый)

**Что сделать:**

Боковая или inline панель, показывающая превью данных после каждой операции.

**Дизайн:**

```
┌─────────────────────────────────────┐
│  📊 PREVIEW                         │
├─────────────────────────────────────┤
│  После загрузки:                    │
│  n = 150 • 8 columns                │
│  Age: numeric • Treatment: category │
├─────────────────────────────────────┤
│  После выбора переменных:           │
│  Target: Age (M=45.2, SD=12.3)      │
│  Group: Treatment (A: 75, B: 75)    │
│  ⚠️ n < 30 per group                │
├─────────────────────────────────────┤
│  После анализа:                     │
│  t(148) = 2.45, p = .015            │
│  d = 0.71 [средний эффект]          │
└─────────────────────────────────────┘
```

**Код:**

```jsx
import React from 'react';

export default function StepPreviewPanel({ steps = [] }) {
  if (steps.length === 0) return null;
  
  return (
    <div className="step-preview-panel border border-[color:var(--border-color)] rounded-lg bg-[color:var(--white)] overflow-hidden">
      <div className="px-4 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)]">
        <span className="text-xs font-semibold uppercase tracking-wider text-[color:var(--text-muted)]">
          📊 Preview
        </span>
      </div>
      
      <div className="divide-y divide-[color:var(--border-color)]">
        {steps.map((step, idx) => (
          <div key={idx} className="px-4 py-3">
            <div className="text-xs text-[color:var(--text-secondary)] mb-1">
              {step.label}
            </div>
            <div className="text-sm text-[color:var(--text-primary)] font-mono">
              {step.summary}
            </div>
            {step.warning && (
              <div className="text-xs text-amber-600 mt-1">
                ⚠️ {step.warning}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Использование:**

```jsx
<StepPreviewPanel
  steps={[
    { label: 'После загрузки', summary: 'n = 150 • 8 columns' },
    { 
      label: 'После выбора переменных', 
      summary: 'Target: Age (M=45.2, SD=12.3)',
      warning: 'n < 30 per group'
    },
    { label: 'После анализа', summary: 't(148) = 2.45, p = .015' }
  ]}
/>
```

**Success criteria:**

- [ ] Панель показывает историю операций
- [ ] Каждый шаг с summary
- [ ] Warnings выделены
- [ ] Обновляется при каждом действии

---

### TASK 9: Report Customization (PRIORITY: HIGH) — NEW

**Файл:** `frontend/src/app/components/ReportBuilder.jsx` (новый)

**Что сделать:**

UI для кастомизации отчёта — выбор секций, порядок, формат.

**Дизайн:**

```
┌─────────────────────────────────────────────────────────────┐
│  📄 ОТЧЁТ                                     [Скачать ▼]   │
├─────────────────────────────────────────────────────────────┤
│  ☑ Описательные статистики                                 │
│  ☑ Проверка допущений                                       │
│  ☑ Основной тест                                            │
│  ☐ Post-hoc сравнения                                       │
│  ☑ Effect size + CI                                         │
│  ☐ Bayes Factor                                             │
│  ☑ График                                                   │
│  ☐ AI-интерпретация                                         │
│  ☑ Методология (для статьи)                                 │
├─────────────────────────────────────────────────────────────┤
│  📝 Формат:  [DOCX ▼]  [Язык: RU ▼]  [APA 7 ▼]             │
│                                                             │
│  [👁 Превью]  [⬇ Скачать]                                   │
└─────────────────────────────────────────────────────────────┘
```

**Код:**

```jsx
import React, { useState } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';

const REPORT_SECTIONS = [
  { id: 'descriptives', label: 'Описательные статистики', default: true },
  { id: 'assumptions', label: 'Проверка допущений', default: true },
  { id: 'main_test', label: 'Основной тест', default: true },
  { id: 'post_hoc', label: 'Post-hoc сравнения', default: false },
  { id: 'effect_size', label: 'Effect size + CI', default: true },
  { id: 'bayes', label: 'Bayes Factor', default: false },
  { id: 'plot', label: 'График', default: true },
  { id: 'ai_interpretation', label: 'AI-интерпретация', default: false },
  { id: 'methodology', label: 'Методология (для статьи)', default: true }
];

const FORMATS = [
  { value: 'docx', label: 'DOCX' },
  { value: 'pdf', label: 'PDF' },
  { value: 'html', label: 'HTML' }
];

const STYLES = [
  { value: 'apa7', label: 'APA 7' },
  { value: 'gost', label: 'ГОСТ' },
  { value: 'simple', label: 'Простой' }
];

export default function ReportBuilder({ 
  onExport, 
  onPreview,
  isExporting = false 
}) {
  const { t } = useTranslation();
  const [sections, setSections] = useState(
    REPORT_SECTIONS.reduce((acc, s) => ({ ...acc, [s.id]: s.default }), {})
  );
  const [format, setFormat] = useState('docx');
  const [style, setStyle] = useState('apa7');
  
  const toggleSection = (id) => {
    setSections(prev => ({ ...prev, [id]: !prev[id] }));
  };
  
  const handleExport = () => {
    const enabledSections = Object.entries(sections)
      .filter(([_, enabled]) => enabled)
      .map(([id]) => id);
    onExport?.({ sections: enabledSections, format, style });
  };
  
  return (
    <div className="report-builder border border-[color:var(--border-color)] rounded-lg bg-[color:var(--white)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--border-color)]">
        <span className="font-semibold text-[color:var(--text-primary)]">📄 Отчёт</span>
      </div>
      
      {/* Sections */}
      <div className="p-4 space-y-2">
        {REPORT_SECTIONS.map(section => (
          <label key={section.id} className="flex items-center gap-3 cursor-pointer hover:bg-[color:var(--bg-secondary)] p-2 rounded">
            <input
              type="checkbox"
              checked={sections[section.id]}
              onChange={() => toggleSection(section.id)}
              className="w-4 h-4 accent-[color:var(--accent)]"
            />
            <span className="text-sm text-[color:var(--text-primary)]">{section.label}</span>
          </label>
        ))}
      </div>
      
      {/* Options */}
      <div className="px-4 py-3 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
        <div className="flex items-center gap-4 text-sm">
          <span className="text-[color:var(--text-muted)]">📝 Формат:</span>
          <select 
            value={format} 
            onChange={e => setFormat(e.target.value)}
            className="px-2 py-1 rounded border border-[color:var(--border-color)] bg-[color:var(--white)]"
          >
            {FORMATS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
          <select 
            value={style} 
            onChange={e => setStyle(e.target.value)}
            className="px-2 py-1 rounded border border-[color:var(--border-color)] bg-[color:var(--white)]"
          >
            {STYLES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex items-center gap-3 px-4 py-3 border-t border-[color:var(--border-color)]">
        <button
          onClick={onPreview}
          className="px-4 py-2 text-sm border border-[color:var(--border-color)] rounded hover:bg-[color:var(--bg-secondary)]"
        >
          👁 Превью
        </button>
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="px-4 py-2 text-sm bg-[color:var(--accent)] text-white rounded hover:opacity-90 disabled:opacity-50"
        >
          {isExporting ? '⏳ Генерация...' : '⬇ Скачать'}
        </button>
      </div>
    </div>
  );
}
```

**Интеграция в StepResults.jsx:**

```jsx
import ReportBuilder from '../../components/ReportBuilder';

// Заменить простые кнопки экспорта на:
<ReportBuilder
  onExport={(config) => handleExport(config)}
  onPreview={() => setShowPreview(true)}
  isExporting={isExporting}
/>
```

**Success criteria:**

- [ ] Чекбоксы для выбора секций
- [ ] Выбор формата (DOCX/PDF/HTML)
- [ ] Выбор стиля (APA/ГОСТ)
- [ ] Превью перед скачиванием
- [ ] Кнопка скачивания с loading state

---

## 🔍 VERIFICATION

После каждой задачи выполнять:

```bash
# 1. Lint
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint

# 2. Проверить что dev server запускается
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run dev

# 3. Backend tests (не должны упасть)
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend && python -m pytest tests/ -x -q
```

---

## 📚 ВАЖНЫЕ ФАЙЛЫ ДЛЯ ПОНИМАНИЯ КОНТЕКСТА

| Файл | Что там |
|------|---------|
| `SCIENTIFIC_STANDARDS.md` | Научные стандарты проекта |
| `VISUALIZATION_STYLE_GUIDE.md` | FlowingData принципы |
| `frontend/src/app/components/education/` | Education компоненты (уже готовы!) |
| `frontend/src/contexts/LanguageContext.jsx` | Здесь educationLevel |
| `backend/app/modules/stat_knowledge.py` | Knowledge base |
| `backend/app/stats/engine.py` | Статистический движок |

---

## 🎨 DESIGN PRINCIPLES

1. **Минимализм** — меньше borders, больше whitespace
2. **Мгновенный feedback** — каждое действие → visual response
3. **Умные defaults** — система сама предлагает лучший вариант
4. **Progressive disclosure** — базовое видно сразу, детали по запросу
5. **Accessibility** — keyboard navigation, colorblind-safe
6. **Visual Flow** — пользователь всегда видит где он в процессе
7. **Customization** — возможность настроить под себя

---

## ⚠️ ОГРАНИЧЕНИЯ

1. **НЕ менять backend API** — фронтенд должен работать с текущим API
2. **НЕ удалять существующие компоненты** — только расширять
3. **Lint должен проходить** — `npm run lint` без ошибок
4. **Русский UI** — все тексты на русском
5. **Код на английском** — переменные, функции, комментарии

---

## 🚀 ПОРЯДОК ВЫПОЛНЕНИЯ

### Phase A: Core UX (HIGH priority)

1. **TASK 1** — Drag-and-Drop (самое важное для UX)
2. ~~TASK 7~~ — ✅ УЖЕ ГОТОВО (ResearchFlowNav)
3. **TASK 8** — Step Preview Panel (фидбек)
4. **TASK 9** — Report Customization (экспорт)

### Phase B: Education Integration

1. **TASK 2** — WhyThisTest интеграция
2. **TASK 3** — Live Preview при выборе переменных
3. **TASK 5** — Settings UI

### Phase C: Polish

1. **TASK 4** — FlowingData стиль
2. **TASK 6** — Keyboard navigation

---

## START

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/frontend/src/app/components/VariableWorkspace.jsx
```

Начни с TASK 1 (Drag-and-Drop). После завершения каждого task — запусти lint.

**GO!**
