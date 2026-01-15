# 🧠 AI_CONTEXT.md — Полный контекст проекта для AI-агентов

> **Назначение:** Comprehensive reference для AI coding assistants  
> **Читай:** Когда нужен глубокий контекст проекта  
> **Обновлено:** 15 января 2026

---

## 📖 Что это за проект?

**StatWizard** — web-платформа для статистического анализа клинических данных.

**Целевая аудитория:**

- Медицинские исследователи
- Клинические психологи
- Биостатистики
- PhD students

**Цель:**
Сделать статистический анализ **доступным** без знания R/Python/SPSS.

**Философия:**

- ✅ Интуитивный UI (как Jamovi/JASP)
- ✅ Научная строгость (как SciPy/Statsmodels)
- ✅ AI-помощь (подсказки, интерпретации)
- ✅ Production-ready (CI/CD, Docker, тесты)

---

## 🎯 Текущий статус

### Что работает ✅

**Backend (85% готов):**

- 20+ статистических методов
- Upload/Parse CSV/Excel
- Auto-classification переменных (SmartScanner)
- Protocol execution engine
- Results generation with plots
- API endpoints (FastAPI)

**Frontend (60% готов):**

- Upload flow
- Variable workspace с виртуализацией
- Protocol builder (drag-n-drop)
- Test configuration modal
- Results display
- Template system
- Keyboard shortcuts

**Infrastructure:**

- Docker setup
- CI/CD (pytest + ESLint)
- Git workflow

### Что НЕ работает ❌

**Backend:**

- ❌ Pingouin не установлен (нет готовых effect sizes)
- ❌ CSV вместо Parquet (медленно)
- ❌ Нет AI interpretations engine
- ❌ Нет PDF/DOCX export

**Frontend:**

- ❌ Design system разнородный
- ❌ AnalysisDesign.jsx слишком большой (1155 строк)
- ❌ Phase 7 компоненты не интегрированы
- ❌ Нет significance brackets на графиках
- ❌ Assumptions checks не видны в UI

---

## 🏗️ Архитектура

### High-Level Flow

```
User uploads CSV
    ↓
Backend parses + SmartScanner auto-classifies variables
    ↓
User selects analysis goal (comparison / relationship / descriptive)
    ↓
System suggests protocol template
    ↓
User customizes protocol (drag tests, configure)
    ↓
Backend executes protocol (stats engine)
    ↓
Results returned with plots + AI interpretations
    ↓
User exports PDF/DOCX
```

### Backend Architecture

```
FastAPI (app/main.py)
    ↓
API Endpoints (app/api/)
├── datasets.py      # Upload, list, get
├── analysis.py      # Design, execute protocol
├── quality.py       # Data quality scan
└── ...
    ↓
Core Pipeline (app/core/)
├── pipeline.py      # Data processing flow
├── protocol_engine.py  # Protocol execution
└── study_designer.py   # Protocol suggestions
    ↓
Stats Engine (app/stats/)
├── engine.py        # MAIN — 47KB, all 20+ methods
├── async_engine.py  # Async execution
├── clustered_correlation.py
├── mixed_effects.py
└── registry.py      # Method registry
    ↓
Modules (app/modules/)
├── parsers.py       # CSV/Excel parsing
├── smart_scanner.py # Auto-classification
├── text_generator.py # AI interpretations (template-based)
└── reporting.py     # Plot generation
```

### Frontend Architecture

```
React App (src/app/)
    ↓
Pages (pages/)
├── Upload.jsx       # File upload
├── DatasetList.jsx  # List datasets
├── AnalysisDesign.jsx  # MAIN PAGE (1155 строк!)
├── Analyze.jsx      # Legacy?
└── Settings.jsx
    ↓
Components (components/)
├── VariableWorkspace.jsx    # Variable selection (virtualized)
├── TestConfigModal.jsx      # Test configuration
├── PlotCustomizer.jsx       # Plot settings
├── ClusteredHeatmap.jsx     # Heatmap viz
├── InteractionPlot.jsx      # Interaction viz
└── analysis/
    ├── ProtocolBuilder.jsx      # Protocol steps UI
    ├── ProtocolTemplateSelector.jsx
    └── AIRecommendationsPanel.jsx
    ↓
State Management
├── Local state (useState, useCallback)
├── Context (LanguageContext)
└── localStorage (protocols, settings)
```

---

## 📊 Data Flow Examples

### Example 1: Upload → Scan → Prepare

```javascript
// Frontend
const handleUpload = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('/api/v1/datasets', {
    method: 'POST',
    body: formData
  });
  
  const { id } = await response.json();
  
  // Get scan report
  const scan = await getScanReport(id);
  // scan.columns[0] = { name: 'age', type: 'numeric', mean: 45.2, ... }
};
```

```python
# Backend (api/datasets.py)
@router.post("/")
async def upload_dataset(file: UploadFile):
    # Parse file
    df = parse_file(file)
    
    # Auto-classify variables
    scan_result = smart_scan(df)
    
    # Save
    dataset_id = save_dataset(df, scan_result)
    
    return {"id": dataset_id, "columns": scan_result}
```

### Example 2: Design Protocol → Execute

```javascript
// Frontend
const handleApplyTemplate = async () => {
  const response = await fetch('/api/v2/analysis/design', {
    method: 'POST',
    body: JSON.stringify({
      dataset_id: datasetId,
      goal: 'comparison',  // or 'relationship'
      template_id: 'independent_t_test',
      variables: { target: 'outcome', group: 'treatment' }
    })
  });
  
  const { protocol } = await response.json();
  // protocol = [{ method: 't_test_ind', config: {...} }]
  setProtocol(protocol);
};
```

```python
# Backend (api/analysis.py)
@router.post("/design")
async def design_protocol(request: ProtocolDesignRequest):
    # Load dataset profile
    profile = get_dataset(request.dataset_id)
    
    # Suggest protocol
    protocol = study_designer.suggest_protocol(
        goal=request.goal,
        variables=request.variables,
        column_types=profile['columns']
    )
    
    return {"protocol": protocol}
```

### Example 3: Execute Protocol → Results

```javascript
// Frontend
const handleExecute = async () => {
  const response = await fetch('/api/v2/analysis/execute', {
    method: 'POST',
    body: JSON.stringify({
      dataset_id: datasetId,
      alpha: 0.05,
      protocol: [
        { method: 't_test_ind', config: { outcome: 'age', group: 'treatment' } }
      ]
    })
  });
  
  const results = await response.json();
  // results.results[0] = { 
  //   method: 't_test_ind',
  //   p_value: 0.001,
  //   stat_value: 3.42,
  //   effect_size: 0.89,
  //   effect_size_interpretation: "большой эффект",
  //   ai_interpretation: "Выявлены статистически значимые различия...",
  //   plot_data: [...]
  // }
};
```

```python
# Backend (stats/engine.py)
def compute_t_test_ind(df, config):
    group_col = config['group']
    outcome_col = config['outcome']
    
    group1 = df[df[group_col] == df[group_col].unique()[0]][outcome_col]
    group2 = df[df[group_col] == df[group_col].unique()[1]][outcome_col]
    
    # With Pingouin (future)
    result = pg.ttest(group1, group2, correction='auto')
    
    return {
        'stat_value': result['T'].iloc[0],
        'p_value': result['p-val'].iloc[0],
        'effect_size': result['cohen-d'].iloc[0],
        'effect_size_interpretation': interpret_effect_size('cohens_d', result['cohen-d'].iloc[0]),
        'ci_lower': result['CI95%'].iloc[0][0],
        'ci_upper': result['CI95%'].iloc[0][1]
    }
```

---

## 🧩 Ключевые компоненты

### 1. SmartScanner (auto-classification)

**Файл:** `backend/app/modules/smart_scanner.py`

**Что делает:**

- Определяет тип переменной (numeric, categorical, datetime, text)
- Считает descriptive stats (mean, sd, median, etc.)
- Детектирует выбросы
- Histogram для числовых
- Top values для категориальных

**Пример вывода:**

```python
{
  "age": {
    "type": "numeric",
    "mean": 45.2,
    "sd": 12.3,
    "min": 18,
    "max": 85,
    "missing_count": 3,
    "unique_count": 67,
    "histogram": { "bins": [2, 5, 10, 15, 8, 3], "edges": [...] }
  },
  "group": {
    "type": "categorical",
    "categories": ["A", "B"],
    "top_values": [{"value": "A", "count": 75}, {"value": "B", "count": 75}],
    "unique_count": 2,
    "missing_count": 0
  }
}
```

### 2. ProtocolEngine (execution)

**Файл:** `backend/app/core/protocol_engine.py`

**Что делает:**

- Принимает протокол (список шагов)
- Валидирует каждый шаг
- Передает в stats/engine.py
- Собирает результаты
- Обрабатывает ошибки

**Пример:**

```python
protocol = [
    {"method": "descriptive_compare", "config": {"outcome": "age", "group": "treatment"}},
    {"method": "t_test_ind", "config": {"outcome": "age", "group": "treatment"}},
]

results = execute_protocol(dataset_id, protocol, alpha=0.05)
# results = { "status": "success", "results": [...] }
```

### 3. VariableWorkspace (UI)

**Файл:** `frontend/src/app/components/VariableWorkspace.jsx`

**Что делает:**

- Отображает список переменных (virtualized для 100+ vars)
- Поиск (fuzzy)
- Фильтры (по типу, роли)
- Drag-n-drop в роли (Target, Group, Covariates)
- Preview stats

**Размер:** 525 строк (хорошо структурирован)

**Ключевые features:**

- `react-window` для виртуализации
- Drag-n-drop для ролей
- Search с debounce
- Type badges (Numeric, Categorical, etc.)

### 4. TestConfigModal

**Файл:** `frontend/src/app/components/TestConfigModal.jsx`

**Что делает:**

- Конфигурация параметров теста
- Выбор переменных (outcome, group, covariates)
- Alpha level (сейчас глобальный)
- Confidence interval toggle (planned)

**TODO:**

- Tabs (Hypothesis, Options, Post-hoc) — как в JASP
- Alpha slider per-test
- Effect size type dropdown

---

## 📦 Dependencies

### Backend (`requirements.txt`)

```
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
pandas>=2.1.3
numpy>=1.26.2
scipy>=1.11.4
statsmodels>=0.14.0
matplotlib>=3.8.2
seaborn>=0.13.0
openpyxl>=3.1.2
lifelines>=0.27.8
scikit-learn>=1.3.2

# TODO: Add these
# pingouin>=0.5.4
# pyarrow>=14.0.0
```

### Frontend (`package.json`)

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^6.20.1",
    "@heroicons/react": "^2.1.0",
    "react-window": "^1.8.10",
    "react-virtualized-auto-sizer": "^1.0.24"
  },
  "devDependencies": {
    "vite": "^5.0.8",
    "tailwindcss": "^3.4.0",
    "eslint": "^8.55.0"
  }
}
```

---

## 🎨 UI/UX Philosophy

### Влияния

1. **JASP** — split-screen, drag-and-drop, dynamic updates
2. **StatTech.ru** — table-centric, inline type selectors, minimalism
3. **Stripe** — kicker labels, monospace numbers, hover states
4. **Linear** — keyboard-first, command palette, subtle animations

### Design Principles

1. **Clarity over complexity** — понятно > функционально
2. **Progressive disclosure** — сложность on demand
3. **Semantic color** — цвет для смысла, не для красоты
4. **Keyboard-first** — все доступно с клавиатуры
5. **Minimalism** — меньше визуального шума

### Current Issues

- ⚠️ Design system разнородный (разные spacing, colors)
- ⚠️ Слишком много borders
- ⚠️ Недостаточно whitespace
- ⚠️ Кое-где inline styles вместо classes

**Fix:** См. `ui_ux_references.md` в artifacts

---

## 🔬 Statistical Methods

### Comparison Tests (2 groups)

| Method | When to use | Effect size |
|--------|-------------|-------------|
| `t_test_ind` | Normal distribution, equal variance | Cohen's d |
| `welch_t_test` | Normal distribution, unequal variance | Cohen's d |
| `mann_whitney` | Non-normal distribution | r (rank-biserial) |
| `paired_t_test` | Paired samples, normal | Cohen's d |
| `wilcoxon` | Paired samples, non-normal | r |

### Multi-Group Tests (3+ groups)

| Method | When to use | Effect size |
|--------|-------------|-------------|
| `anova` | Normal, equal variance | η² (eta-squared) |
| `welch_anova` | Normal, unequal variance | ω² (omega-squared) |
| `kruskal_wallis` | Non-normal | ε² (epsilon-squared) |
| `rm_anova` | Repeated measures | Partial η² |
| `friedman` | Repeated, non-normal | Kendall's W |

### Categorical Tests

| Method | When to use | Effect size |
|--------|-------------|-------------|
| `chi_square` | Frequency table, n > 5 | Cramér's V |
| `fisher_exact` | Small samples, 2x2 table | Odds Ratio |

### Correlation

| Method | When to use | Effect size |
|--------|-------------|-------------|
| `pearson` | Linear relationship, normal | r |
| `spearman` | Monotonic, non-normal | ρ (rho) |

### Advanced

| Method | Description |
|--------|-------------|
| `linear_regression` | Predict continuous outcome |
| `logistic_regression` | Predict binary outcome |
| `mixed_effects` | Repeated measures with random effects |
| `kaplan_meier` | Survival analysis |
| `roc_analysis` | Classifier performance |
| `clustered_correlation` | Correlation matrix with clustering |

---

## 🧪 Testing Strategy

### Backend Tests

**Location:** `backend/tests/`

**Types:**

1. **Unit tests** — отдельные функции
2. **Integration tests** — API endpoints
3. **E2E tests** — полный flow (upload → analyze → export)

**Run:**

```bash
cd backend
python -m pytest tests/ -v
python -m pytest tests/test_engine.py -v -k "ttest"
```

### Frontend Tests

**Currently:** ESLint only

**Planned:**

- Vitest unit tests
- Playwright E2E tests

**Run:**

```bash
cd frontend
npm run lint
npm run test:run  # Future
```

---

## 🚀 Deployment

### Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

### Production

```bash
# Docker Compose
docker-compose up -d

# Or deploy script
./deploy.sh
```

**Environment variables:**

```env
# Backend (.env)
ENVIRONMENT=production
DATABASE_URL=sqlite:///./statproject.db

# Frontend (auto-configured by Vite)
VITE_API_URL=https://api.statproject.com
```

---

## 📝 Coding Conventions

### Python

```python
# Imports
import standard_lib
import third_party
from local_module import function

# Functions
def snake_case_function(param: str) -> dict:
    """Docstring with description.
    
    Args:
        param: Description
        
    Returns:
        dict with keys...
    """
    result = {}
    return result

# Classes
class PascalCaseClass:
    """Class docstring."""
    
    def __init__(self, value: int):
        self.value = value
```

### JavaScript/React

```javascript
// Imports
import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import ComponentName from './ComponentName';

// Component
export default function PascalCaseComponent({ propName, onAction }) {
  const [state, setState] = useState(initialValue);
  
  const handleAction = useCallback(() => {
    // Logic
    onAction?.();
  }, [onAction]);
  
  return (
    <div className="tailwind-classes">
      {/* JSX */}
    </div>
  );
}
```

### CSS (TailwindCSS)

```jsx
// ✅ Prefer Tailwind classes
<div className="p-5 bg-white border border-gray-200 rounded-sm">

// ⚠️ Use CSS vars for custom colors
<div className="bg-[color:var(--color-white)]">

// ❌ Avoid inline styles
<div style={{ padding: '20px' }}>  // BAD
```

---

## 🔗 Useful Links

**Documentation:**

- [SCIENTIFIC_STANDARDS.md](./SCIENTIFIC_STANDARDS.md) — Python DS Handbook best practices
- [ROADMAP.md](./ROADMAP.md) — Task list
- [AGENTS.md](./AGENTS.md) — AI agent guide
- [CONTRIBUTING.md](./CONTRIBUTING.md) — Contribution guide

**Artifacts:**

- [project_review.md](.gemini/antigravity/brain/.../project_review.md)
- [implementation_plan.md](.gemini/antigravity/brain/.../implementation_plan.md)
- [ui_ux_references.md](.gemini/antigravity/brain/.../ui_ux_references.md)

**External:**

- [Pingouin docs](https://pingouin-stats.org/)
- [JASP interface](https://jasp-stats.org/)
- [Tailwind docs](https://tailwindcss.com/docs)

---

## ❓ FAQ for AI Agents

**Q: Где начать?**
A: Читай `AI_PROMPT_PRODUCTION.md` → `implementation_plan.md` → начинай с Phase 1

**Q: Как выбрать задачу?**
A: Следуй порядку в `implementation_plan.md` Day 1 → Day 2 → ...

**Q: Что делать если тесты не проходят?**
A: 1) Читай ошибку, 2) Изолируй проблему, 3) Фикс, 4) Re-run

**Q: Можно ли менять архитектуру?**
A: Только если это явно в плане. Иначе — спроси юзера.

**Q: Русский или английский?**
A: UI — русский. Code, comments, docs — английский.

**Q: Что делать с большими файлами?**
A: Рефакторить постепенно. См. `AnalysisDesign.jsx` refactoring plan.

**Q: Pingouin vs SciPy?**
A: Pingouin предпочтительнее — готовые effect sizes, CI, BF10.

**Q: CSV vs Parquet?**
A: Parquet — 5-10x быстрее. Миграция в Phase 1.

---

*Версия: 1.0*  
*Обновлено: 15 января 2026*  
*Для: TRAE AI Agents*
