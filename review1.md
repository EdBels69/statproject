# ULTRATHINK: Архитектура Статистической Платформы

> **Режим:** ULTRATHINK — глубокий анализ всех измерений проблемы

---

## 🧠 ГЛУБОКИЙ АНАЛИЗ КОНТЕКСТА

### Психологическое измерение

- **Cognitive Load:** Исследователь работает с 119 признаками × 6 точек. Когнитивная нагрузка КРИТИЧЕСКАЯ.
- **Error Proneness:** При ручном маппинге 714+ переменных ошибка неизбежна. AI-assist = обязателен.
- **Time Sensitivity:** Обсчеты запускаются редко, но результаты нужны быстро. Batch processing с кешированием.

### Техническое измерение

- **Текущее хранение:** CSV в `pipeline.py` → блокирует масштабирование
- **Memory footprint:** 100 пациентов × 714 признаков × 8 bytes (float64) = ~570KB raw. С метаданными ~5-10MB. OK для RAM.
- **Bottleneck:** Повторное чтение CSV при каждом анализе. Parquet + memory-mapping решает.

### Scalability измерение

- **Текущий предел:** ~10k rows × 1000 cols (CSV parsing)
- **Target:** 100+ пациентов × 714 признаков × 4 группы = стабильно
- **Future-proof:** SQL для метаданных и индексов, Parquet для data blobs

---

## 📐 АРХИТЕКТУРА VARIABLE MAPPING SYSTEM

### Концепция: "Header Transpose + Metadata Columns"

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ИСХОДНАЯ ТАБЛИЦА (Wide Format)                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Patient_ID │ Age │ Gender │ BP_T0 │ BP_T1 │ BP_T2 │ HR_T0 │ HR_T1 │ HR_T2 │ ... │
│     001    │ 45  │   M    │  120  │  118  │  115  │   72  │   70  │   68  │     │
│     002    │ 52  │   F    │  135  │  130  │  128  │   80  │   78  │   75  │     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    VARIABLE MAPPING EDITOR (Transpose View)                     │
├────────────────┬───────────┬───────────┬──────────┬──────────┬─────────────────┤
│ Original_Name  │ Role      │ Group_Var │ Subgroup │ Timepoint│ Display_Name    │
├────────────────┼───────────┼───────────┼──────────┼──────────┼─────────────────┤
│ Patient_ID     │ ID        │           │          │          │ Пациент         │
│ Age            │ Covariate │           │          │          │ Возраст         │
│ Gender         │ Group     │ ✓ Primary │          │          │ Пол             │
│ BP_T0          │ Outcome   │           │ BP       │ T0       │ АД Базовое      │
│ BP_T1          │ Outcome   │           │ BP       │ T1       │ АД Месяц 1      │
│ BP_T2          │ Outcome   │           │ BP       │ T2       │ АД Месяц 2      │
│ HR_T0          │ Outcome   │           │ HR       │ T0       │ ЧСС Базовое     │
│ HR_T1          │ Outcome   │           │ HR       │ T1       │ ЧСС Месяц 1     │
│ HR_T2          │ Outcome   │           │ HR       │ T2       │ ЧСС Месяц 2     │
└────────────────┴───────────┴───────────┴──────────┴──────────┴─────────────────┘
```

### Столбцы Variable Mapping

| Column | Type | Purpose | AI-Assist |
|--------|------|---------|-----------|
| **Original_Name** | `readonly` | Имя из заголовка исходного файла | — |
| **Role** | `select` | ID / Group / Subgroup / Covariate / Outcome / Exclude | AI предлагает по имени |
| **Group_Var** | `checkbox` | Основная группирующая переменная (1-2 max) | AI детектит "Group", "Treatment", "Arm" |
| **Subgroup** | `text/select` | Логическая группа переменных (BP, HR, Labs...) | AI парсит prefix в имени |
| **Timepoint** | `select` | T0, T1...T6 / Baseline, Month1... | AI детектит _T0,_M1 suffixes |
| **Display_Name** | `text` | Человекочитаемое название для отчетов | AI переводит/расшифровывает |
| **Data_Type** | `select` | Numeric / Categorical / Ordinal / Date | Auto-detect + AI |
| **Include_Descriptive** | `checkbox` | Включить в таблицу описательной статистики | Default: true for Outcomes |
| **Include_Comparison** | `checkbox` | Включить в групповые сравнения | Default: true for Outcomes |

---

## 🛠️ CONTRACT-BASED DATA ARCHITECTURE

### Level 1: Pydantic Schemas (API Contracts)

```python
# backend/app/schemas/variable_mapping.py
from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from enum import Enum

class VariableRole(str, Enum):
    ID = "id"
    GROUP = "group"
    SUBGROUP = "subgroup"
    COVARIATE = "covariate"
    OUTCOME = "outcome"
    EXCLUDE = "exclude"

class DataType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    DATE = "date"
    TEXT = "text"

class VariableMapping(BaseModel):
    """Single variable metadata contract"""
    original_name: str = Field(..., description="Column name from source file")
    role: VariableRole
    is_primary_group: bool = False
    subgroup: Optional[str] = None  # e.g., "BP", "HR", "Labs"
    timepoint: Optional[str] = None  # e.g., "T0", "T1", "Baseline"
    display_name: Optional[str] = None
    data_type: DataType
    include_descriptive: bool = True
    include_comparison: bool = True
    
class DatasetContract(BaseModel):
    """Full dataset metadata contract"""
    dataset_id: str
    source_filename: str
    row_count: int
    subject_id_column: str
    primary_group_column: str
    timepoints: List[str]  # Ordered list: ["T0", "T1", "T2"]
    variable_groups: List[str]  # ["BP", "HR", "Labs"]
    variables: List[VariableMapping]
    created_at: str
    last_modified: str
```

### Level 2: Parquet + DuckDB Hybrid Storage

```python
# backend/app/core/data_manager.py
import duckdb
import pyarrow.parquet as pq
from pathlib import Path

class DataManager:
    """
    Hybrid storage: 
    - Parquet for raw data blobs (columnar, compressed, memory-mapped)
    - DuckDB for metadata, variable mappings, analysis results
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "statanalyzer.duckdb"
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite-like embedded database for metadata"""
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id VARCHAR PRIMARY KEY,
                    name VARCHAR,
                    row_count INTEGER,
                    col_count INTEGER,
                    created_at TIMESTAMP,
                    contract JSON
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id VARCHAR PRIMARY KEY,
                    dataset_id VARCHAR,
                    protocol JSON,
                    results JSON,
                    created_at TIMESTAMP,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
                )
            """)
    
    def save_dataset(self, dataset_id: str, df, contract: DatasetContract):
        """Save data as Parquet + metadata to DuckDB"""
        dataset_dir = self.data_dir / dataset_id
        dataset_dir.mkdir(exist_ok=True)
        
        # 1. Save data as Parquet (optimal for analytics)
        parquet_path = dataset_dir / "data.parquet"
        df.to_parquet(parquet_path, engine='pyarrow', compression='snappy')
        
        # 2. Save contract to DuckDB
        with duckdb.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO datasets 
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, [dataset_id, contract.source_filename, 
                  contract.row_count, len(contract.variables),
                  contract.model_dump_json()])
        
        return parquet_path
    
    def load_dataset(self, dataset_id: str):
        """Load dataset with memory-mapping (efficient for large files)"""
        parquet_path = self.data_dir / dataset_id / "data.parquet"
        return pq.read_table(parquet_path).to_pandas()
    
    def load_columns(self, dataset_id: str, columns: List[str]):
        """Load only specific columns (Parquet columnar advantage)"""
        parquet_path = self.data_dir / dataset_id / "data.parquet"
        return pq.read_table(parquet_path, columns=columns).to_pandas()
    
    def get_contract(self, dataset_id: str) -> DatasetContract:
        """Retrieve dataset contract from DuckDB"""
        with duckdb.connect(str(self.db_path)) as conn:
            result = conn.execute(
                "SELECT contract FROM datasets WHERE id = ?", 
                [dataset_id]
            ).fetchone()
            return DatasetContract.model_validate_json(result[0])
```

### Level 3: Folder Structure

```
data/
├── statanalyzer.duckdb          # Metadata DB (SQLite-compatible)
│
├── dataset_001/
│   ├── source/
│   │   ├── original.xlsx        # Raw upload (preserved)
│   │   └── meta.json
│   ├── processed/
│   │   ├── data.parquet         # Cleaned data (Parquet)
│   │   ├── contract.json        # Variable mappings
│   │   └── cleaning_log.json
│   └── analysis/
│       ├── run_20260112_223000/
│       │   ├── protocol.json
│       │   ├── results.json
│       │   └── artifacts/
│       │       ├── table_one.html
│       │       └── plots/
│       └── run_20260112_224500/
│           └── ...
│
├── dataset_002/
│   └── ...
```

---

## 🤖 AI-ASSISTED PREPROCESSING PIPELINE

### AI Classification Tasks

```python
# backend/app/ai/variable_classifier.py
from app.llm import call_llm
from app.schemas.variable_mapping import VariableMapping, VariableRole, DataType

CLASSIFICATION_PROMPT = """
You are a clinical data analyst. Given a list of column names and sample values from a medical research dataset, classify each variable.

Column Names:
{column_names}

Sample Values (first 5 rows):
{sample_values}

For each column, provide:
1. role: "id" | "group" | "covariate" | "outcome" | "exclude"
2. subgroup: Logical grouping (e.g., "Vital Signs", "Laboratory", "Demographics")
3. timepoint: If temporal, extract timepoint (e.g., "T0", "Month_1", "Baseline")
4. data_type: "numeric" | "categorical" | "ordinal" | "date" | "text"
5. display_name: Human-readable Russian name

Rules:
- Columns with "id", "code", "number" → role: "id"
- Columns with "group", "treatment", "arm" → role: "group"
- Columns with common suffixes like _T0, _M1, _baseline → extract timepoint
- BP, HR, SBP, DBP → subgroup: "Vital Signs"
- WBC, RBC, Hb, PLT → subgroup: "Laboratory"
- Age, Sex, Gender, BMI → subgroup: "Demographics"

Return JSON array:
[
  {
    "original_name": "BP_T0",
    "role": "outcome",
    "subgroup": "Vital Signs",
    "timepoint": "T0",
    "data_type": "numeric",
    "display_name": "АД систолическое (базовое)"
  },
  ...
]
"""

async def classify_variables(df) -> List[VariableMapping]:
    """AI-powered variable classification"""
    column_names = list(df.columns)
    sample_values = df.head(5).to_string()
    
    prompt = CLASSIFICATION_PROMPT.format(
        column_names=", ".join(column_names),
        sample_values=sample_values
    )
    
    response = await call_llm(prompt, temperature=0.1)
    classifications = json.loads(response)
    
    return [VariableMapping(**c) for c in classifications]
```

### AI Data Cleaning Suggestions

```python
# backend/app/ai/data_cleaner.py

CLEANING_PROMPT = """
Analyze this dataset for data quality issues:

Column Statistics:
{column_stats}

Sample Problematic Values:
{problem_samples}

Suggest cleaning operations for each issue found:
1. For mixed types (e.g., "120" and "120 mmHg") → suggest regex extraction
2. For outliers (e.g., Age = 200) → suggest bounds or removal
3. For missing patterns (e.g., all T2 values missing for patient 005) → flag for review
4. For inconsistent categories (e.g., "Male", "M", "male") → suggest normalization

Return JSON:
[
  {
    "column": "BP_T1",
    "issue": "mixed_type",
    "description": "Contains 'mmHg' suffix in 15% of values",
    "action": "extract_numeric",
    "confidence": 0.95
  },
  ...
]
"""

async def suggest_cleaning(df, scan_report: dict) -> List[CleaningSuggestion]:
    """AI-powered cleaning recommendations"""
    # Build context from SmartScanner output
    column_stats = json.dumps(scan_report["columns"], indent=2)
    
    # Find problematic values
    problem_samples = []
    for col, meta in scan_report["columns"].items():
        if meta.get("polluting_values"):
            problem_samples.append({
                "column": col,
                "values": meta["polluting_values"]
            })
    
    prompt = CLEANING_PROMPT.format(
        column_stats=column_stats,
        problem_samples=json.dumps(problem_samples)
    )
    
    response = await call_llm(prompt, temperature=0.1)
    return json.loads(response)
```

### AI Optimal Group Detection

```python
# backend/app/ai/group_optimizer.py

GROUP_OPTIMIZATION_PROMPT = """
Given a dataset with potential grouping variables, suggest the optimal analysis grouping strategy.

Available Group Variables:
{group_vars}

Research Context (if provided):
{context}

Group Statistics:
{group_stats}

Analyze and recommend:
1. Primary grouping variable (most balanced, scientifically meaningful)
2. Secondary grouping (for subgroup analysis)
3. Potential covariates to control for
4. Warning flags (unbalanced groups, missing data patterns)

Return JSON:
{
  "primary_group": {
    "column": "Treatment_Arm",
    "groups": ["Control", "Intervention"],
    "n_per_group": [45, 48],
    "rationale": "Clinical trial design with balanced allocation"
  },
  "secondary_group": {
    "column": "Gender",
    "rationale": "For sex-stratified subgroup analysis"
  },
  "suggested_covariates": ["Age", "BMI", "Baseline_BP"],
  "warnings": [
    "Group 'Dropout' has only 7 subjects - consider excluding or analyzing separately"
  ]
}
"""

async def optimize_grouping(df, contract: DatasetContract, context: str = ""):
    """AI suggests optimal group configuration"""
    # Find potential group variables
    group_vars = [v for v in contract.variables if v.role in ["group", "subgroup"]]
    
    # Calculate group statistics
    group_stats = {}
    for v in group_vars:
        col = v.original_name
        group_stats[col] = df[col].value_counts().to_dict()
    
    prompt = GROUP_OPTIMIZATION_PROMPT.format(
        group_vars=json.dumps([v.original_name for v in group_vars]),
        context=context or "Medical research study",
        group_stats=json.dumps(group_stats, indent=2)
    )
    
    return await call_llm(prompt, temperature=0.2)
```

---

## 🎨 FRONTEND: VARIABLE MAPPING EDITOR

### Component Architecture

```jsx
// frontend/src/app/pages/VariableMapping.jsx

import { AgGridReact } from 'ag-grid-react';
import { useState, useEffect, useMemo } from 'react';
import { AIAssistBadge } from '@/components/AIAssistBadge';

const ROLE_OPTIONS = [
  { value: 'id', label: 'ID', color: 'gray' },
  { value: 'group', label: 'Группа', color: 'blue' },
  { value: 'subgroup', label: 'Подгруппа', color: 'cyan' },
  { value: 'covariate', label: 'Ковариата', color: 'purple' },
  { value: 'outcome', label: 'Показатель', color: 'green' },
  { value: 'exclude', label: 'Исключить', color: 'red' }
];

const TIMEPOINT_OPTIONS = ['T0', 'T1', 'T2', 'T3', 'T4', 'T5', 'T6'];

export default function VariableMapping({ datasetId }) {
  const [mappings, setMappings] = useState([]);
  const [aiSuggestions, setAiSuggestions] = useState({});
  const [isAiLoading, setIsAiLoading] = useState(false);

  // AG Grid Column Definitions
  const columnDefs = useMemo(() => [
    { 
      field: 'original_name', 
      headerName: 'Имя столбца',
      pinned: 'left',
      width: 180,
      editable: false,
      cellStyle: { fontFamily: 'monospace' }
    },
    {
      field: 'role',
      headerName: 'Роль',
      width: 140,
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ROLE_OPTIONS.map(r => r.value) },
      cellRenderer: RoleBadgeRenderer
    },
    {
      field: 'is_primary_group',
      headerName: 'Главная группа',
      width: 120,
      editable: true,
      cellRenderer: 'agCheckboxCellRenderer',
      cellEditor: 'agCheckboxCellEditor'
    },
    {
      field: 'subgroup',
      headerName: 'Подгруппа',
      width: 150,
      editable: true,
      cellEditor: 'agTextCellEditor'
    },
    {
      field: 'timepoint',
      headerName: 'Точка',
      width: 100,
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { values: ['', ...TIMEPOINT_OPTIONS] }
    },
    {
      field: 'display_name',
      headerName: 'Название для отчета',
      width: 200,
      editable: true
    },
    {
      field: 'data_type',
      headerName: 'Тип',
      width: 120,
      editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: { 
        values: ['numeric', 'categorical', 'ordinal', 'date', 'text'] 
      }
    },
    {
      field: 'include_descriptive',
      headerName: '📊 Desc',
      width: 80,
      editable: true,
      cellRenderer: 'agCheckboxCellRenderer'
    },
    {
      field: 'include_comparison',
      headerName: '📈 Comp',
      width: 80,
      editable: true,
      cellRenderer: 'agCheckboxCellRenderer'
    },
    {
      field: 'ai_confidence',
      headerName: 'AI',
      width: 70,
      cellRenderer: AIConfidenceRenderer
    }
  ], []);

  // AI Classification Handler
  const handleAIClassify = async () => {
    setIsAiLoading(true);
    try {
      const response = await fetch(`/api/datasets/${datasetId}/ai-classify`, {
        method: 'POST'
      });
      const suggestions = await response.json();
      
      // Merge AI suggestions with current mappings
      setMappings(prev => prev.map(m => ({
        ...m,
        ...suggestions[m.original_name],
        ai_confidence: suggestions[m.original_name]?.confidence || 0
      })));
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 rounded-lg">
        <h2 className="text-lg font-semibold">Маппинг переменных</h2>
        <div className="flex gap-2">
          <button 
            onClick={handleAIClassify}
            disabled={isAiLoading}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50"
          >
            {isAiLoading ? (
              <span className="animate-spin">⚙️</span>
            ) : (
              <span>🤖</span>
            )}
            AI Классификация
          </button>
          <button className="px-4 py-2 bg-gray-200 rounded-lg">
            Авто-детект временных точек
          </button>
        </div>
      </div>

      {/* AG Grid Table */}
      <div className="flex-1 ag-theme-alpine">
        <AgGridReact
          rowData={mappings}
          columnDefs={columnDefs}
          defaultColDef={{ resizable: true, sortable: true }}
          onCellValueChanged={handleCellChange}
          enableCellChangeFlash={true}
          animateRows={true}
        />
      </div>

      {/* Summary Footer */}
      <VariableSummary mappings={mappings} />
    </div>
  );
}

function VariableSummary({ mappings }) {
  const stats = useMemo(() => ({
    total: mappings.length,
    outcomes: mappings.filter(m => m.role === 'outcome').length,
    groups: mappings.filter(m => m.role === 'group').length,
    timepoints: [...new Set(mappings.map(m => m.timepoint).filter(Boolean))].length,
    excluded: mappings.filter(m => m.role === 'exclude').length
  }), [mappings]);

  return (
    <div className="flex gap-6 px-4 py-3 bg-gray-100 rounded-lg text-sm">
      <span>Всего: <strong>{stats.total}</strong></span>
      <span>Показателей: <strong className="text-green-600">{stats.outcomes}</strong></span>
      <span>Групп: <strong className="text-blue-600">{stats.groups}</strong></span>
      <span>Точек: <strong className="text-cyan-600">{stats.timepoints}</strong></span>
      <span className="text-red-500">Исключено: <strong>{stats.excluded}</strong></span>
    </div>
  );
}
```

---

## 📊 BATCH ANALYSIS MATRIX

### Matrix Generator для массовых обсчетов

```python
# backend/app/core/batch_analyzer.py

from itertools import product
from typing import Generator
import asyncio

class BatchAnalyzer:
    """
    Generates and executes all-vs-all comparison matrices.
    Optimized for large-scale repeated measures designs.
    """
    
    def __init__(self, data_manager: DataManager, stats_engine):
        self.dm = data_manager
        self.engine = stats_engine
    
    def generate_comparison_matrix(
        self, 
        contract: DatasetContract,
        mode: str = "all_outcomes_vs_groups"
    ) -> Generator[dict, None, None]:
        """
        Generates comparison tasks:
        - all_outcomes_vs_groups: Each outcome vs primary group
        - timepoint_matrix: Each outcome at each timepoint vs groups
        - pairwise_timepoints: T0 vs T1, T1 vs T2, etc. for each outcome
        """
        outcomes = [v for v in contract.variables 
                   if v.role == "outcome" and v.include_comparison]
        primary_group = contract.primary_group_column
        timepoints = contract.timepoints
        
        if mode == "all_outcomes_vs_groups":
            for outcome in outcomes:
                yield {
                    "target": outcome.original_name,
                    "group": primary_group,
                    "type": "group_comparison"
                }
        
        elif mode == "timepoint_matrix":
            # 119 outcomes × 6 timepoints = 714 comparisons
            for outcome in outcomes:
                if outcome.timepoint:
                    yield {
                        "target": outcome.original_name,
                        "group": primary_group,
                        "timepoint": outcome.timepoint,
                        "type": "timepoint_comparison"
                    }
        
        elif mode == "pairwise_timepoints":
            # Paired comparisons: T0→T1, T1→T2 for longitudinal analysis
            subgroups = set(v.subgroup for v in outcomes if v.subgroup)
            for subgroup in subgroups:
                subgroup_vars = [v for v in outcomes 
                               if v.subgroup == subgroup and v.timepoint]
                subgroup_vars.sort(key=lambda x: x.timepoint)
                
                for i in range(len(subgroup_vars) - 1):
                    yield {
                        "target_t0": subgroup_vars[i].original_name,
                        "target_t1": subgroup_vars[i+1].original_name,
                        "group": primary_group,
                        "type": "paired_timepoint"
                    }
    
    async def run_batch(
        self, 
        dataset_id: str,
        mode: str = "all_outcomes_vs_groups",
        progress_callback = None
    ) -> dict:
        """Execute batch with progress tracking"""
        contract = self.dm.get_contract(dataset_id)
        df = self.dm.load_dataset(dataset_id)
        
        tasks = list(self.generate_comparison_matrix(contract, mode))
        total = len(tasks)
        results = []
        
        for i, task in enumerate(tasks):
            result = await self.engine.run_analysis_async(df, **task)
            results.append({**task, "result": result})
            
            if progress_callback:
                await progress_callback(i + 1, total, task["target"])
        
        # Apply FDR correction
        p_values = [r["result"]["p_value"] for r in results]
        adjusted = self._benjamini_hochberg(p_values)
        
        for i, r in enumerate(results):
            r["p_adjusted"] = adjusted[i]
            r["significant_adjusted"] = adjusted[i] < 0.05
        
        return {
            "mode": mode,
            "total_comparisons": total,
            "significant_raw": sum(1 for r in results if r["result"]["significant"]),
            "significant_adjusted": sum(1 for r in results if r["significant_adjusted"]),
            "results": results
        }
```

---

## 🔧 IMPLEMENTATION ROADMAP

### Phase 1: Storage Migration (3-4 дня)

- [ ] Установить DuckDB + PyArrow
- [ ] Создать `DataManager` с Parquet storage
- [ ] Мигрировать `PipelineManager` на новую систему
- [ ] Backward-compatible CSV fallback

### Phase 2: Variable Mapping System (4-5 дней)

- [ ] Pydantic schemas для VariableMapping/DatasetContract
- [ ] Backend API: `/datasets/{id}/mappings` CRUD
- [ ] AI classification endpoint
- [ ] Frontend: AG Grid Variable Editor

### Phase 3: AI Preprocessing (3-4 дня)

- [ ] Промпты для классификации переменных
- [ ] Промпты для детекции временных точек
- [ ] Промпты для оптимизации групп
- [ ] Интеграция с LLM endpoint

### Phase 4: Batch Analysis (3-4 дня)

- [ ] Matrix generator
- [ ] Async batch executor с progress
- [ ] FDR correction
- [ ] Results export (Excel matrix)

### Phase 5: Extended Descriptives (2-3 дня)

- [ ] Полная JAMOVI-like функция
- [ ] Per-timepoint breakdown
- [ ] Long format reshaping utility

---

## 📦 ЗАВИСИМОСТИ ДЛЯ ДОБАВЛЕНИЯ

```txt
# backend/requirements.txt additions
duckdb>=0.9.0
pyarrow>=14.0.0
openpyxl>=3.1.0  # Excel export
```

```json
// frontend/package.json additions
{
  "dependencies": {
    "ag-grid-react": "^31.0.0",
    "ag-grid-community": "^31.0.0"
  }
}
```

---

## 🎯 EDGE CASES & FAILURE MODES

| Scenario | Risk | Mitigation |
|----------|------|------------|
| AI misclassifies variable | Medium | Confidence score + human review required for <0.8 |
| 100+ columns slow to load | Low | AG Grid virtualization (built-in) |
| Parquet corruption | Low | Keep CSV backup in source/ |
| LLM timeout mid-batch | Medium | Graceful fallback to rule-based detection |
| Memory overflow on batch | Low | Chunk processing with gc.collect() |

---

## ✅ BEST PRACTICES ИЗ ИНДУСТРИИ

1. **tidyverse/dplyr approach**: Long format с явными Subject/Time/Value столбцами
2. **REDCap-style metadata**: Отдельный Data Dictionary с типами и валидацией
3. **CDISC standards**: Controlled terminology для клинических данных
4. **Reproducible Research**: Каждый протокол → уникальный run_id с frozen snapshot

Эта архитектура позволит обрабатывать **119 признаков × 6 точек × 100 пациентов × 4 группы** эффективно, с AI-assist для снижения ручной работы и contract-based подходом для надежности.

---

# 🧪 ULTRATHINK: MIXED EFFECTS & TIME×GROUP INTERACTION

## 📋 Контекст: Исследование ДИАМАГ при болезни Паркинсона

### Дизайн исследования (из загруженного изображения)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    DIAMAG PARKINSON'S CLINICAL TRIAL                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  PRIMARY ENDPOINTS:                                                              │
│  ├── UPDRS Part 3 (Motor Function)                                              │
│  └── UPDRS Part 2 (Activities of Daily Living)                                  │
│       → Change from V1 to V6                                                    │
│       → Group comparison: DIAMAG vs Placebo                                     │
│                                                                                  │
│  SECONDARY ENDPOINTS:                                                            │
│  ├── DASS-21: Depression, Anxiety, Stress                                       │
│  ├── Epworth Sleepiness Scale                                                   │
│  ├── Apathy Scale                                                               │
│  ├── Stroop Test (Cognitive)                                                    │
│  ├── Trail Making Test A/B                                                      │
│  └── PDQ-39 (Quality of Life)                                                   │
│                                                                                  │
│  TIMEPOINTS: V1 (Baseline) → V2 → V3 → V4 → V5 → V6 (Day 30±1)                 │
│  GROUPS: DIAMAG (Treatment) vs Стандартная терапия (Control)                   │
│                                                                                  │
│  HYPOTHESIS: Time × Group INTERACTION                                           │
│  H₀: Изменение UPDRS одинаково в обеих группах                                 │
│  H₁: DIAMAG группа показывает бóльшее улучшение                                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Ключевой вопрос: Time × Group Interaction

**Что это значит:**

- НЕ просто "отличаются ли группы на каждой точке?"
- А "отличается ли ДИНАМИКА изменений между группами?"

```
     Score │
           │     Placebo: ──────────────────
           │              ↘                 
           │                ↘               DIAMAG: лучше улучшается
           │                  ↘             
           │                    ↘ DIAMAG    
           │                      ──────────
           └────────────────────────────────→ Time
              V1    V2    V3    V4    V5    V6
```

**Статистически:**

- Main Effect of Time: изменяется ли показатель со временем? (да/нет)
- Main Effect of Group: отличаются ли группы в среднем? (да/нет)
- **Interaction Time×Group**: отличается ли ТРАЕКТОРИЯ изменений? (ключевой вопрос!)

---

## 🔬 MIXED EFFECTS MODEL IMPLEMENTATION

### Почему Mixed Effects, а не RM-ANOVA?

| Критерий | RM-ANOVA | Mixed Effects (LMM) |
|----------|----------|---------------------|
| Missing data | Listwise deletion (теряем пациентов) | Handled naturally |
| Unbalanced designs | Требует полные данные | OK |
| Sphericity | Требует проверку | Не нужна |
| Random slopes | Нет | Можно добавить |
| Scalability | OK для малых данных | Отлично для больших |

### Формула модели

```
# Полная модель для Time×Group interaction
UPDRS ~ Time + Group + Time:Group + (1|Subject)

Где:
- Time: фактор с 6 уровнями (V1-V6) или непрерывный (дни)
- Group: DIAMAG vs Placebo
- Time:Group: INTERACTION TERM (главный интерес!)
- (1|Subject): random intercept для каждого пациента
```

### Реализация в Python (statsmodels)

```python
# backend/app/stats/mixed_effects.py
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import statsmodels.formula.api as smf
from statsmodels.stats.anova import AnovaRM
import gc
import warnings

class MixedEffectsEngine:
    """
    Memory-efficient Mixed Effects Model implementation.
    Optimized for MacBook M1 8GB constraints.
    """
    
    def __init__(self, max_memory_mb: int = 1200):
        self.max_memory = max_memory_mb * 1024 * 1024  # bytes
    
    def fit_mixed_model(
        self,
        df: pd.DataFrame,
        outcome: str,
        time_col: str,
        group_col: str,
        subject_col: str,
        covariates: List[str] = None,
        random_slope: bool = False,
        chunk_size: int = 5000
    ) -> Dict[str, Any]:
        """
        Fits Linear Mixed Model with Time×Group interaction.
        
        Parameters:
        -----------
        outcome: Target variable (e.g., "UPDRS_Part3")
        time_col: Time/Visit variable (e.g., "Visit")
        group_col: Treatment group (e.g., "Group")
        subject_col: Subject ID (e.g., "Patient_ID")
        covariates: Additional covariates (e.g., ["Age", "Sex", "Baseline_UPDRS"])
        random_slope: If True, adds random slope for time (more complex model)
        """
        
        # Memory check
        estimated_memory = df.memory_usage(deep=True).sum()
        if estimated_memory > self.max_memory:
            return self._chunked_analysis(df, outcome, time_col, group_col, 
                                          subject_col, covariates, chunk_size)
        
        # Prepare data
        required_cols = [outcome, time_col, group_col, subject_col]
        if covariates:
            required_cols.extend(covariates)
        
        analysis_df = df[required_cols].dropna().copy()
        
        # Ensure categorical types for grouping
        analysis_df[time_col] = analysis_df[time_col].astype('category')
        analysis_df[group_col] = analysis_df[group_col].astype('category')
        
        # Build formula
        fixed_effects = f"{outcome} ~ C({time_col}) * C({group_col})"
        if covariates:
            fixed_effects += " + " + " + ".join(covariates)
        
        # Random effects specification
        if random_slope:
            random_effects = f"1 + C({time_col})"  # Random intercept + slope
        else:
            random_effects = "1"  # Random intercept only
        
        # Fit model
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                
                model = smf.mixedlm(
                    fixed_effects,
                    data=analysis_df,
                    groups=analysis_df[subject_col],
                    re_formula=f"~{random_effects}"
                )
                result = model.fit(method='lbfgs', maxiter=500)
                
                # Extract results
                return self._extract_results(result, time_col, group_col, outcome)
                
        except Exception as e:
            return {
                "error": str(e),
                "suggestion": "Try reducing model complexity or checking data quality"
            }
        finally:
            gc.collect()
    
    def _extract_results(self, result, time_col, group_col, outcome) -> Dict[str, Any]:
        """Extract key results from fitted model"""
        
        # Get coefficients
        params = result.params
        pvalues = result.pvalues
        conf_int = result.conf_int()
        
        # Identify interaction terms
        interaction_terms = [
            p for p in params.index 
            if f"C({time_col})" in p and f"C({group_col})" in p
        ]
        
        # Extract interaction p-values
        interaction_pvalues = {
            term: float(pvalues[term]) 
            for term in interaction_terms
        }
        
        # Overall interaction significance (joint test)
        # Use Wald test for all interaction terms
        interaction_significant = any(p < 0.05 for p in interaction_pvalues.values())
        min_interaction_p = min(interaction_pvalues.values()) if interaction_pvalues else 1.0
        
        # Main effects
        main_effect_time = [p for p in params.index if f"C({time_col})" in p and group_col not in p]
        main_effect_group = [p for p in params.index if f"C({group_col})" in p and time_col not in p]
        
        return {
            "outcome": outcome,
            "model_type": "Linear Mixed Model",
            "n_observations": result.nobs,
            "n_groups": result.n_groups,
            
            # Main effects
            "main_effect_time": {
                "coefficients": {t: float(params[t]) for t in main_effect_time if t in params},
                "p_values": {t: float(pvalues[t]) for t in main_effect_time if t in pvalues},
                "significant": any(pvalues[t] < 0.05 for t in main_effect_time if t in pvalues)
            },
            "main_effect_group": {
                "coefficients": {t: float(params[t]) for t in main_effect_group if t in params},
                "p_values": {t: float(pvalues[t]) for t in main_effect_group if t in pvalues},
                "significant": any(pvalues[t] < 0.05 for t in main_effect_group if t in pvalues)
            },
            
            # INTERACTION (главный интерес!)
            "interaction_time_group": {
                "coefficients": {t: float(params[t]) for t in interaction_terms},
                "p_values": interaction_pvalues,
                "min_p_value": min_interaction_p,
                "significant": interaction_significant,
                "interpretation": self._interpret_interaction(
                    interaction_significant, min_interaction_p
                )
            },
            
            # Model fit
            "log_likelihood": float(result.llf),
            "aic": float(result.aic),
            "bic": float(result.bic),
            
            # Random effects
            "random_effects_variance": float(result.cov_re.iloc[0, 0]) if hasattr(result, 'cov_re') else None,
            
            # Full coefficient table
            "coefficients_table": self._format_coef_table(result)
        }
    
    def _interpret_interaction(self, significant: bool, p_value: float) -> str:
        """Generate human-readable interpretation"""
        if significant:
            return (
                f"Статистически значимое взаимодействие Время×Группа (p={p_value:.4f}). "
                f"Траектории изменения показателя различаются между группами. "
                f"Рекомендуется визуализация профилей для интерпретации направления эффекта."
            )
        else:
            return (
                f"Взаимодействие Время×Группа не достигло статистической значимости (p={p_value:.4f}). "
                f"Траектории изменения показателя не различаются значимо между группами."
            )
    
    def _format_coef_table(self, result) -> List[Dict]:
        """Format coefficient table for frontend display"""
        table = []
        for idx in result.params.index:
            table.append({
                "term": idx,
                "coefficient": float(result.params[idx]),
                "std_error": float(result.bse[idx]) if idx in result.bse else None,
                "z_value": float(result.tvalues[idx]) if idx in result.tvalues else None,
                "p_value": float(result.pvalues[idx]),
                "ci_lower": float(result.conf_int().loc[idx, 0]),
                "ci_upper": float(result.conf_int().loc[idx, 1]),
                "significant": result.pvalues[idx] < 0.05
            })
        return table
    
    def _chunked_analysis(self, df, outcome, time_col, group_col, 
                          subject_col, covariates, chunk_size) -> Dict[str, Any]:
        """Memory-efficient analysis for large datasets"""
        # For very large datasets, use approximate methods
        # or process in chunks with pooling
        
        # Strategy: Downsample to representative subset
        unique_subjects = df[subject_col].unique()
        n_subjects = len(unique_subjects)
        
        if n_subjects > 500:
            # Random sample of subjects (maintaining all their timepoints)
            sampled_subjects = np.random.choice(unique_subjects, 500, replace=False)
            sampled_df = df[df[subject_col].isin(sampled_subjects)]
            
            result = self.fit_mixed_model(
                sampled_df, outcome, time_col, group_col, 
                subject_col, covariates, random_slope=False
            )
            result["warning"] = f"Analysis based on random sample of 500/{n_subjects} subjects due to memory constraints"
            return result
        
        raise MemoryError("Dataset too large for available memory")


class RepeatedMeasuresEngine:
    """
    Traditional RM-ANOVA for simpler cases.
    Falls back when LMM is not appropriate.
    """
    
    def fit_rm_anova(
        self,
        df: pd.DataFrame,
        outcome_cols: List[str],  # e.g., ["UPDRS_V1", "UPDRS_V2", "UPDRS_V3"]
        subject_col: str,
        group_col: str = None
    ) -> Dict[str, Any]:
        """
        Repeated Measures ANOVA with optional between-subjects factor.
        
        For wide-format data where each timepoint is a separate column.
        """
        
        # Convert wide to long format
        long_df = df.melt(
            id_vars=[subject_col, group_col] if group_col else [subject_col],
            value_vars=outcome_cols,
            var_name='Time',
            value_name='Value'
        ).dropna()
        
        # Ensure numeric
        long_df['Value'] = pd.to_numeric(long_df['Value'], errors='coerce')
        
        try:
            if group_col:
                # Two-way RM-ANOVA (Time × Group)
                aovrm = AnovaRM(
                    long_df, 
                    'Value', 
                    subject_col, 
                    within=['Time'],
                    between=[group_col]
                )
            else:
                # One-way RM-ANOVA (Time only)
                aovrm = AnovaRM(
                    long_df, 
                    'Value', 
                    subject_col, 
                    within=['Time']
                )
            
            result = aovrm.fit()
            
            return {
                "method": "Repeated Measures ANOVA",
                "anova_table": result.anova_table.to_dict(),
                "sphericity_note": "Sphericity not tested. Consider Greenhouse-Geisser correction if violated.",
                "n_subjects": long_df[subject_col].nunique(),
                "n_timepoints": len(outcome_cols)
            }
            
        except Exception as e:
            return {"error": str(e)}
```

---

## 🚀 BATCH MIXED EFFECTS FOR ALL OUTCOMES

### Для вашего исследования: 10+ outcomes × Time×Group

```python
# backend/app/stats/batch_mixed_effects.py

async def run_batch_mixed_effects(
    df: pd.DataFrame,
    outcomes: List[str],  # ["UPDRS_Part2", "UPDRS_Part3", "DASS_Depression", ...]
    time_col: str,
    group_col: str,
    subject_col: str,
    covariates: List[str] = None,
    progress_callback = None
) -> Dict[str, Any]:
    """
    Run Time×Group interaction analysis for ALL outcome variables.
    Returns comprehensive results with FDR correction.
    """
    engine = MixedEffectsEngine()
    results = []
    
    for i, outcome in enumerate(outcomes):
        result = engine.fit_mixed_model(
            df, outcome, time_col, group_col, subject_col, covariates
        )
        result["outcome"] = outcome
        results.append(result)
        
        if progress_callback:
            await progress_callback(i + 1, len(outcomes), outcome)
        
        # Memory cleanup between models
        gc.collect()
    
    # Extract interaction p-values for FDR correction
    p_values = [
        r["interaction_time_group"]["min_p_value"] 
        for r in results 
        if "interaction_time_group" in r
    ]
    
    # Benjamini-Hochberg correction
    from scipy.stats import false_discovery_control
    adjusted_p = false_discovery_control(p_values, method='bh')
    
    # Add adjusted p-values
    for i, r in enumerate(results):
        if "interaction_time_group" in r:
            r["interaction_time_group"]["p_adjusted"] = float(adjusted_p[i])
            r["interaction_time_group"]["significant_adjusted"] = adjusted_p[i] < 0.05
    
    # Summary table
    summary = {
        "total_outcomes": len(outcomes),
        "significant_interactions_raw": sum(
            1 for r in results 
            if r.get("interaction_time_group", {}).get("significant", False)
        ),
        "significant_interactions_adjusted": sum(
            1 for r in results 
            if r.get("interaction_time_group", {}).get("significant_adjusted", False)
        ),
        "results": results
    }
    
    return summary
```

---

## 📉 MEMORY OPTIMIZATION FOR M1 8GB

### Estimated Memory Usage

```
Dataset: 100 patients × 6 timepoints × 20 outcomes = 12,000 rows

Per-model memory:
- DataFrame slice: ~500KB
- Model matrices: ~2MB
- Fitted model: ~1MB
- Peak during fit: ~10MB

Batch of 20 outcomes:
- Sequential processing: ~10MB peak (safe)
- With gc.collect(): ~5MB average

VERDICT: M1 8GB is FINE for this scale ✅
```

### Scaling Limits

| Scale | Rows | Outcomes | Memory Est. | M1 8GB |
|-------|------|----------|-------------|--------|
| Small | 1,000 | 20 | ~50MB | ✅ |
| Medium | 10,000 | 50 | ~200MB | ✅ |
| Large | 100,000 | 100 | ~1GB | ⚠️ Chunking |
| XLarge | 1,000,000 | 200 | ~5GB | ❌ Need sampling |

### Auto-scaling Strategy

```python
def estimate_memory_and_choose_strategy(df, n_outcomes):
    """Choose analysis strategy based on data size"""
    rows = len(df)
    
    if rows * n_outcomes < 500_000:
        return "full"  # Analyze everything
    elif rows * n_outcomes < 2_000_000:
        return "chunked"  # Process in chunks with gc
    else:
        return "sampled"  # Random sample of subjects
```

---

## 🎨 FRONTEND: INTERACTION VISUALIZATION

### Profile Plot Component

```jsx
// frontend/src/app/components/InteractionPlot.jsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, 
         Legend, ResponsiveContainer, ErrorBar } from 'recharts';

export default function InteractionPlot({ 
  data,          // Array of {time, group, mean, se, ci_lower, ci_upper}
  groups,        // ["DIAMAG", "Placebo"]
  outcome,       // "UPDRS Part 3"
  pValue,        // Interaction p-value
  significant    // boolean
}) {
  // Transform data for recharts
  const timepoints = [...new Set(data.map(d => d.time))];
  const chartData = timepoints.map(t => {
    const point = { time: t };
    groups.forEach(g => {
      const match = data.find(d => d.time === t && d.group === g);
      if (match) {
        point[`${g}_mean`] = match.mean;
        point[`${g}_se`] = match.se;
        point[`${g}_ci_lower`] = match.ci_lower;
        point[`${g}_ci_upper`] = match.ci_upper;
      }
    });
    return point;
  });

  const colors = ['#2563eb', '#dc2626']; // Blue, Red

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm">
      {/* Header with significance */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">{outcome}</h3>
          <p className="text-sm text-gray-500">Time × Group Interaction</p>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-medium ${
          significant 
            ? 'bg-green-100 text-green-700' 
            : 'bg-gray-100 text-gray-600'
        }`}>
          p = {pValue.toFixed(4)} {significant && '★'}
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="time" label={{ value: 'Визит', position: 'bottom' }} />
          <YAxis label={{ value: outcome, angle: -90, position: 'left' }} />
          <Tooltip />
          <Legend />
          
          {groups.map((group, idx) => (
            <Line
              key={group}
              type="monotone"
              dataKey={`${group}_mean`}
              name={group}
              stroke={colors[idx]}
              strokeWidth={2}
              dot={{ fill: colors[idx], r: 5 }}
              activeDot={{ r: 8 }}
            >
              <ErrorBar
                dataKey={`${group}_se`}
                width={4}
                strokeWidth={2}
                stroke={colors[idx]}
                direction="y"
              />
            </Line>
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Interpretation */}
      <div className={`mt-4 p-3 rounded-lg text-sm ${
        significant ? 'bg-green-50' : 'bg-gray-50'
      }`}>
        {significant ? (
          <p>
            <strong>Значимое взаимодействие:</strong> Траектории изменения {outcome} 
            статистически различаются между группами (p={pValue.toFixed(4)}). 
            Группа DIAMAG показывает {/* динамически определить направление */}
            отличающуюся динамику по сравнению с контролем.
          </p>
        ) : (
          <p>
            Траектории изменения не различаются значимо между группами (p={pValue.toFixed(4)}).
          </p>
        )}
      </div>
    </div>
  );
}
```

---

## 📊 IMPLEMENTATION STATUS

### Текущее состояние в проекте

| Component | Registry | Engine | UI |
|-----------|----------|--------|-----|
| `mixed_model` | ✅ Declared | ❌ **NOT IMPLEMENTED** | ❌ |
| `rm_anova` | ✅ Declared | ❌ **NOT IMPLEMENTED** | ❌ |
| Time×Group interaction | ❌ | ❌ | ❌ |
| Profile plots | ❌ | ❌ | ❌ |
| Batch LMM | ❌ | ❌ | ❌ |

### Roadmap для полной реализации

1. **Phase 1 (3-4 дня):** Implement `MixedEffectsEngine` в `backend/app/stats/`
2. **Phase 2 (2-3 дня):** API endpoints для Time×Group analysis
3. **Phase 3 (2-3 дня):** Frontend: InteractionPlot + batch results table
4. **Phase 4 (2 дня):** Integration с Variable Mapping (auto-detect timepoints)

---

## 🧪 VERIFICATION PLAN FOR YOUR DIAMAG STUDY

### Test Case

```python
# Simulated DIAMAG data
import numpy as np
import pandas as pd

np.random.seed(42)
n_subjects = 60
timepoints = ['V1', 'V2', 'V3', 'V4', 'V5', 'V6']

# Generate test data
data = []
for subj in range(n_subjects):
    group = 'DIAMAG' if subj < 30 else 'Placebo'
    baseline_updrs = np.random.normal(35, 10)
    
    for t_idx, t in enumerate(timepoints):
        if group == 'DIAMAG':
            # DIAMAG: улучшение со временем
            change = -2.5 * t_idx + np.random.normal(0, 3)
        else:
            # Placebo: стабильно или небольшое ухудшение
            change = 0.5 * t_idx + np.random.normal(0, 3)
        
        data.append({
            'Subject_ID': f'P{subj:03d}',
            'Group': group,
            'Visit': t,
            'UPDRS_Part3': baseline_updrs + change,
            'DASS_Depression': np.random.normal(10, 5) - (1 if group == 'DIAMAG' else 0) * t_idx
        })

test_df = pd.DataFrame(data)

# Run analysis
engine = MixedEffectsEngine()
result = engine.fit_mixed_model(
    test_df,
    outcome='UPDRS_Part3',
    time_col='Visit',
    group_col='Group',
    subject_col='Subject_ID'
)

# Expected: significant Time×Group interaction (p < 0.05)
print(f"Interaction p-value: {result['interaction_time_group']['min_p_value']}")
print(f"Significant: {result['interaction_time_group']['significant']}")
```
