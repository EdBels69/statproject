# AI Agent Prompt — Phase 5 Tasks 5.2 & 5.3

> **Status:** Task 5.1 ✅ Complete  
> **Remaining:** 5.2 Assumption Checks, 5.3 DOCX Export

---

## CONTEXT

StatWizard project. Logistic regression is done. Now implement:

1. **5.2** Assumption checks (Shapiro-Wilk, Levene) + auto-fallback
2. **5.3** DOCX export for Word documents

---

## TASK 5.2: Assumption Checks

### Create `backend/app/stats/assumptions.py`

```python
from scipy import stats
import numpy as np

def check_normality(data, alpha=0.05):
    clean = [x for x in data if x is not None and np.isfinite(x)]
    n = len(clean)
    if n < 3 or n > 5000:
        return {"test": "shapiro", "passed": None, "n": n}
    stat, p = stats.shapiro(clean)
    return {"test": "shapiro", "stat": round(stat, 4), "p": round(p, 4), "passed": p > alpha}

def check_homogeneity(groups, alpha=0.05):
    clean = [[x for x in g if x is not None and np.isfinite(x)] for g in groups]
    if any(len(g) < 2 for g in clean):
        return {"test": "levene", "passed": None}
    stat, p = stats.levene(*clean)
    return {"test": "levene", "stat": round(stat, 4), "p": round(p, 4), "passed": p > alpha}

def recommend_test(n_groups, paired, norm_ok, homo_ok):
    if n_groups == 2:
        if paired:
            return "wilcoxon" if not norm_ok else "t_test_rel"
        if norm_ok and homo_ok:
            return "t_test_ind"
        return "mann_whitney" if not norm_ok else "t_test_welch"
    if paired:
        return "friedman" if not norm_ok else "rm_anova"
    return "kruskal" if not norm_ok else "anova"
```

### Integrate in `engine.py`

- Call checks before group comparison tests
- Add `assumption_warning` to result dict
- Display warning in frontend

---

## TASK 5.3: DOCX Export

### Install dependency

```bash
pip install python-docx
# Add to requirements.txt
```

### Create `backend/app/modules/docx_generator.py`

- `create_results_document(results, dataset_name)` → returns BytesIO
- Add tables for descriptive stats
- Add test results with p-values
- Add interpretation text

### Add endpoint in `analysis_router.py`

```python
@router.post("/export/docx")
async def export_docx(request):
    buffer = create_results_document(request.results)
    return StreamingResponse(buffer, media_type="application/vnd.openxml...")
```

### Frontend: Add "📄 Скачать Word" button in results header

---

## VERIFICATION

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend && pip install python-docx
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
```

---

## START

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/PHASE5_PLAN.md
```

Implement 5.2 first, then 5.3. **GO!**
