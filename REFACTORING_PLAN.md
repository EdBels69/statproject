# 🔧 Clinimetria — Refactoring Plan to Usable State

> **Goal:** Transform Clinimetria from "working backend + broken UX" to "fully usable app"

---

## 📊 Current State Analysis

### ✅ What Works

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | ✅ Working | 48 tests passing |
| Excel/CSV Upload | ✅ Fixed | With mixed-type handling |
| 24+ Statistical Methods | ✅ Working | pingouin + scipy |
| AI Recommendations | ✅ Working | GLM-based suggestions |
| Effect Size Interpretation | ✅ Added | Cohen's thresholds |
| Clustered Correlation | ✅ Working | Dendrogram + heatmap |

### 🔴 Critical UX Issues (Blocking)

| Issue | Description | Impact |
|-------|-------------|--------|
| **Dropdown Hell** | 119 variables in `<select>` | Unusable for real data |
| **Method ID Mismatch** | Frontend→Backend ID mismatch | Tests fail silently |
| **No Variable Search** | Can't find variables by name | Frustrating UX |
| **No Multi-Select** | Must pick one var at a time | Slow workflow |

### 🟡 Missing Features (Planned in ROADMAP)

- Variable Workspace with grouping
- ag-grid for data editing  
- Protocol Templates save/load
- Publication-ready plots

---

## 🎯 Refactoring Phases

### Phase 1: P0 Critical Fixes (1-2 days)

#### 1.1 Fix All Method ID Mappings

**Files:**

- [MODIFY] [TestSelectionPanel.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/analysis/TestSelectionPanel.jsx) ✅ Done
- [MODIFY] [TestConfigModal.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/TestConfigModal.jsx)
- [MODIFY] [ProtocolSorcerer.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/ProtocolSorcerer.jsx)

**Changes:**

```diff
- id: 'kruskal_wallis'  →  + id: 'kruskal'
- id: 't_test'          →  + id: 't_test_ind'
- id: 'welch_t_test'    →  + id: 't_test_welch'
- id: 'paired_t_test'   →  + id: 't_test_rel'
- id: 'mixed_effects'   →  + id: 'mixed_model'
- id: 'survival'        →  + id: 'survival_km'
```

---

#### 1.2 Add Search to Variable Dropdowns

**Files:**

- [MODIFY] [AnalysisDesign.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/AnalysisDesign.jsx)
- [MODIFY] [TestConfigModal.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/TestConfigModal.jsx)

**What to do:**
Replace `<select>` with searchable dropdown using existing pattern from VariableSelector.

```jsx
// Add search input above variable list
<input 
  type="text" 
  placeholder="Search variables..."
  onChange={(e) => setSearchFilter(e.target.value)}
/>
{filteredVariables.map(v => ...)}
```

---

#### 1.3 Replace Dropdowns with VariableSelector

**Files:**

- [MODIFY] [TestConfigModal.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/TestConfigModal.jsx)

**What to do:**
Use existing `VariableSelector` component (already has virtualization!) instead of `<select>`.

```jsx
import VariableSelector from './VariableSelector';

// Instead of dropdown
<VariableSelector 
  allColumns={variables}
  onRun={(targets, group) => setConfig({...config, target: targets[0], group})}
/>
```

---

### Phase 2: P1 UX Improvements (3-5 days)

#### 2.1 Variable Workspace Component

**Files:**

- [NEW] [VariableWorkspace.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/VariableWorkspace.jsx)

**Features:**

- Virtualized list (already have react-window)
- Fuzzy search with fuse.js
- Filter by type: Numeric / Categorical / DateTime
- Multi-select with checkboxes
- Drag-n-drop to reorder

**Dependencies:**

```bash
npm install fuse.js
```

---

#### 2.2 Improve Template Application

**Files:**

- [MODIFY] [AnalysisDesign.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/AnalysisDesign.jsx)

**What to do:**

- Auto-detect variable types when applying template
- Map template placeholders to actual variables
- Show preview before applying

---

#### 2.3 Better Error Messages

**Files:**

- [MODIFY] [AnalysisDesign.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/pages/AnalysisDesign.jsx)

**What to do:**

- Show which test failed and why
- Suggest fixes (e.g., "Need at least 2 groups")
- Color-code severity

---

### Phase 3: P2 Feature Completion (1 week)

#### 3.1 Publication-Ready Plots

**Files:**

- [NEW] [plot_config.py](file:///Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/plot_config.py)
- [MODIFY] [reporting.py](file:///Users/eduardbelskih/Проекты Github/statproject/backend/app/modules/reporting.py)

**What to do:**

- 300 DPI by default
- Colorblind-safe palette
- SVG/PDF export

---

#### 3.2 Protocol Templates Save/Load

**Files:**

- [MODIFY] [datasets.py](file:///Users/eduardbelskih/Проекты Github/statproject/backend/app/api/datasets.py)
- [NEW] [ProtocolTemplateManager.jsx](file:///Users/eduardbelskih/Проекты Github/statproject/frontend/src/app/components/ProtocolTemplateManager.jsx)

**Endpoints:**

```
POST /api/v1/protocols          # Save protocol
GET  /api/v1/protocols          # List all
GET  /api/v1/protocols/{name}   # Load specific
```

---

### Phase 4: P3 Polish (2+ weeks)

- ag-grid for data editing
- AI Chat consultant
- Dark mode
- Keyboard shortcuts
- Multi-dataset comparison

---

## ✅ Verification Plan

### Automated Tests

```bash
# Backend tests (already exist)
cd backend && python3 -m pytest tests/ -v

# Should all pass: 48 tests
```

### Manual E2E Tests

#### Test 1: Upload Excel with 100+ columns

1. Open <http://localhost:5173/>
2. Upload `Первичка для анализа работа.xlsx` (119 columns)
3. **Expected:** File uploads, shows 44 rows × 119 columns
4. **Pass criteria:** No errors in console, data visible

#### Test 2: Run Statistical Test

1. Navigate to "New Analysis"
2. Select dataset from step 1
3. Click "Kruskal-Wallis" in left panel
4. Select "САД V1" as Target, "Группа" as Group
5. Click "Run"
6. **Expected:** Results appear with p-value and effect size

#### Test 3: Variable Search (after Phase 1.2)

1. Open TestConfigModal
2. Type "САД" in search box
3. **Expected:** Only variables containing "САД" shown

#### Test 4: AI Recommendations

1. On AnalysisDesign page, click "AI Suggest"
2. **Expected:** 2-3 recommendations appear
3. Click "+" on one recommendation
4. **Expected:** Test added to protocol

---

## 📋 Immediate Next Steps

1. **Fix remaining method ID mismatches** in TestConfigModal and ProtocolSorcerer
2. **Add search input** to variable dropdowns (30 min)
3. **Create VariableWorkspace** component with search + filter (2-3 hours)
4. **E2E test** full flow after each change

---

## 🚨 User Review Required

> [!IMPORTANT]
> This plan focuses on **UX improvements to make the app usable**.
> Backend is stable with 48 passing tests.

**Questions for review:**

1. Should I start with Phase 1 (quick fixes) immediately?
2. Do you want to prioritize Variable Workspace (Phase 2.1) sooner?
3. Any specific features from ROADMAP you want to add?

---

*Generated: 2026-01-14*
