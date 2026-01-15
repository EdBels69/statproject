# Phase 5: StatTech Parity — Implementation Plan

> **Status:** Task 5.1 ✅ Done, Tasks 5.2-5.3 remaining  
> **Time estimate:** ~3 days

---

## ✅ Task 5.1: Logistic Regression — COMPLETE

- Backend: `engine.py`, `registry.py` — `logistic_regression` method
- Frontend: `TestConfigModal.jsx` — template with outcome, predictors, covariates
- Normalization: `normalizeStepForBackend()` in `AnalysisDesign.jsx`

---

## Task 5.2: Assumption Checks + Auto-Fallback

### Goal

Automatically check normality/homogeneity and fallback to non-parametric tests.

### Backend Implementation

**Create file:** `backend/app/stats/assumptions.py`

```python
from scipy import stats
import numpy as np

def check_normality(data, alpha=0.05):
    """Shapiro-Wilk test for normality."""
    clean = [x for x in data if x is not None and np.isfinite(x)]
    n = len(clean)
    if n < 3:
        return {"test": "shapiro", "passed": None, "reason": "too_few", "n": n}
    if n > 5000:
        return {"test": "shapiro", "passed": None, "reason": "too_many", "n": n}
    stat, p = stats.shapiro(clean)
    return {"test": "shapiro", "stat": round(stat, 4), "p": round(p, 4), "passed": p > alpha}

def check_homogeneity(groups, alpha=0.05):
    """Levene's test for homogeneity of variances."""
    clean_groups = [[x for x in g if x is not None and np.isfinite(x)] for g in groups]
    if any(len(g) < 2 for g in clean_groups):
        return {"test": "levene", "passed": None, "reason": "too_few"}
    stat, p = stats.levene(*clean_groups)
    return {"test": "levene", "stat": round(stat, 4), "p": round(p, 4), "passed": p > alpha}

def recommend_test(group_count, paired, normality_ok, homogeneity_ok):
    """Auto-select appropriate test based on assumptions."""
    if group_count == 2:
        if paired:
            return "wilcoxon" if not normality_ok else "t_test_rel"
        if normality_ok and homogeneity_ok:
            return "t_test_ind"
        if normality_ok:
            return "t_test_welch"
        return "mann_whitney"
    else:
        if paired:
            return "friedman" if not normality_ok else "rm_anova"
        return "kruskal" if not normality_ok else "anova"
```

### Integration in engine.py

```python
from .assumptions import check_normality, check_homogeneity, recommend_test

# In run_analysis or similar:
if config.get("auto_check_assumptions", True):
    norm_check = check_normality(target_data)
    homo_check = check_homogeneity(group_data_list)
    
    if not norm_check.get("passed") or not homo_check.get("passed"):
        recommended = recommend_test(...)
        # Add warning to result
        result["assumption_warning"] = {
            "normality": norm_check,
            "homogeneity": homo_check,
            "recommended_method": recommended,
            "message_ru": f"Рекомендуется использовать {recommended}"
        }
```

### Frontend Display

In `AnalysisDesign.jsx` results section, add:

```jsx
{step.assumption_warning && (
  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
    <div className="font-semibold text-amber-900">⚠️ Проверка предпосылок</div>
    <div className="text-amber-800 mt-1">
      {step.assumption_warning.message_ru}
    </div>
  </div>
)}
```

---

## Task 5.3: DOCX Export

### Goal

Generate publication-ready Word document.

### Dependencies

```bash
pip install python-docx
# Add to requirements.txt: python-docx>=0.8.11
```

### Backend Implementation

**Create file:** `backend/app/modules/docx_generator.py`

```python
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import io

def create_results_document(analysis_results, dataset_name=None):
    """Generate DOCX with analysis results."""
    doc = Document()
    
    # Title
    title = doc.add_heading("Результаты статистического анализа", 0)
    if dataset_name:
        doc.add_paragraph(f"Датасет: {dataset_name}")
    
    # Loop through results
    for step in analysis_results.get("results", []):
        method = step.get("method", "Неизвестный метод")
        doc.add_heading(method, level=2)
        
        # Descriptive stats table
        if step.get("descriptive"):
            add_descriptive_table(doc, step["descriptive"])
        
        # Test result
        if step.get("statistic") is not None:
            p = step.get("p_value")
            p_str = f"p < 0.001" if p and p < 0.001 else f"p = {p:.3f}" if p else "N/A"
            doc.add_paragraph(f"Статистика: {step['statistic']:.3f}, {p_str}")
        
        # Interpretation
        if step.get("interpretation"):
            doc.add_paragraph(step["interpretation"])
    
    # Save to buffer
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

def add_descriptive_table(doc, data):
    """Add descriptive statistics table."""
    if not data:
        return
    
    # Determine columns based on data structure
    if isinstance(data, dict) and "groups" in data:
        groups = data["groups"]
        table = doc.add_table(rows=1 + len(groups), cols=5)
        table.style = "Table Grid"
        
        headers = ["Группа", "N", "M", "SD", "Me"]
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h
        
        for idx, g in enumerate(groups):
            row = table.rows[idx + 1]
            row.cells[0].text = str(g.get("name", ""))
            row.cells[1].text = str(g.get("n", ""))
            row.cells[2].text = f"{g.get('mean', 0):.2f}"
            row.cells[3].text = f"{g.get('std', 0):.2f}"
            row.cells[4].text = f"{g.get('median', 0):.2f}"
```

### API Endpoint

**Add to:** `backend/app/routers/analysis_router.py`

```python
from fastapi.responses import StreamingResponse
from ..modules.docx_generator import create_results_document

@router.post("/export/docx")
async def export_docx(request: ExportRequest):
    buffer = create_results_document(
        request.results,
        dataset_name=request.dataset_name
    )
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=analysis_results.docx"}
    )
```

### Frontend Button

**In `AnalysisDesign.jsx` results header:**

```jsx
<button
  onClick={handleExportDocx}
  className="px-3 py-1.5 text-xs font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700"
>
  📄 Скачать Word
</button>
```

```javascript
const handleExportDocx = async () => {
  const response = await fetch(`${API_URL}/v2/analysis/export/docx`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      results: results,
      dataset_name: datasetName
    })
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'analysis_results.docx';
  a.click();
};
```

---

## Verification

```bash
# Backend tests
cd backend && python3 -m pytest tests/ -v -k "assumption or docx"

# Frontend lint
cd frontend && npm run lint
```

---

## Success Criteria

- [x] 5.1 Logistic regression works
- [ ] 5.2 `assumptions.py` exists with check_normality, check_homogeneity
- [ ] 5.2 Assumption warnings display in UI
- [ ] 5.3 DOCX export generates valid Word file
- [ ] 5.3 "Скачать Word" button works
