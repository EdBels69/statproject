# AI Agent Prompt — Phase 6.4 & 6.5

> **Status:** 6.1-6.3 ✅ Complete  
> **Focus:** Plots with Brackets + AI Interpretations

---

## CONTEXT

**Project:** StatWizard  
**Stack:** React 19 + TailwindCSS / Python FastAPI + matplotlib  
**Design:** White (#FFFFFF), Black (#0A0A0A), Orange (#FF6B00)

**Already Done:**

- CSS design system in `index.css`
- ui/ components (Button, Card, etc)
- ResearchFlowNav 4-step flow
- JASP-style TestConfigModal with live preview

---

## TASK 6.4: Plots with Brackets

### Backend: Create `backend/app/modules/plot_with_brackets.py`

```python
import matplotlib.pyplot as plt
import numpy as np

def add_significance_bracket(ax, x1, x2, y, p_value, h=0.02, lw=1.2):
    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    bar_h = h * y_range
    ax.plot([x1, x1, x2, x2], [y, y + bar_h, y + bar_h, y], 
            color='black', lw=lw, clip_on=False)
    
    if p_value < 0.001:
        p_text = "***"
    elif p_value < 0.01:
        p_text = "**"
    elif p_value < 0.05:
        p_text = "*"
    else:
        p_text = "ns"
    
    ax.text((x1 + x2) / 2, y + bar_h, p_text, 
            ha='center', va='bottom', fontsize=10, fontweight='bold')
```

### Frontend: Create `frontend/src/app/components/PlotCustomizer.jsx`

Options: type (bar/box/violin), error bars (SD/SEM/CI), show brackets toggle.

### Integrate in VisualizePlot.jsx

Pass `comparisons` prop with p-values, render brackets.

---

## TASK 6.5: AI Interpretations

### Add interpretation block to results

```jsx
{step.ai_interpretation && (
  <div className="mt-4 border-l-4 border-[color:var(--accent)] pl-4 py-3 bg-[color:var(--bg-secondary)]">
    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
      ✨ AI Interpretation
    </div>
    <div className="mt-2 text-sm">{step.ai_interpretation}</div>
  </div>
)}
```

### Backend: `backend/app/modules/ai_interpreter.py`

Generate Russian text based on p-value, effect size, method.

### Export buttons

Add PDF/DOCX/Plots buttons to results header.

---

## VERIFICATION

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend && python3 -m pytest tests/ -v
```

---

## COMPLETION CRITERIA

- [ ] `plot_with_brackets.py` exists
- [ ] `PlotCustomizer.jsx` component works
- [ ] Brackets appear on comparison plots
- [ ] AI interpretation block renders
- [ ] Export buttons functional

---

## START

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/PHASE6_PLAN.md
```

Implement 6.4 first (brackets), then 6.5 (AI). **GO!**
