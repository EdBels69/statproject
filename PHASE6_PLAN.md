# Phase 6.4-6.5: Plots & AI — Implementation Plan

> **Status:** 6.1-6.3 ✅ Complete  
> **Remaining:** 6.4 Plots with Brackets, 6.5 AI Interpretations

---

## Task 6.4: Customizable Plots with Significance Brackets

### Goal

Add GraphPad-style significance brackets to comparison plots.

### Backend: `backend/app/modules/plot_with_brackets.py`

```python
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

def add_significance_bracket(ax, x1, x2, y, p_value, h=0.02, lw=1.2):
    """Draw significance bracket between two positions.
    
    Args:
        ax: matplotlib axes
        x1, x2: x positions of groups
        y: y position for bracket (top of data)
        p_value: p-value for annotation
        h: bracket height as fraction of y range
    """
    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    bar_h = h * y_range
    
    # Draw bracket
    ax.plot([x1, x1, x2, x2], [y, y + bar_h, y + bar_h, y], 
            color='black', lw=lw, clip_on=False)
    
    # Format p-value text
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

def create_comparison_plot(data, plot_type='bar', comparisons=None, **kwargs):
    """Create plot with optional significance brackets.
    
    Args:
        data: list of dicts with 'group', 'values', 'mean', 'sem'
        plot_type: 'bar', 'box', 'violin'
        comparisons: list of {'group1', 'group2', 'p_value'}
    """
    fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
    
    groups = [d['group'] for d in data]
    x_pos = np.arange(len(groups))
    
    if plot_type == 'bar':
        means = [d['mean'] for d in data]
        sems = [d.get('sem', 0) for d in data]
        bars = ax.bar(x_pos, means, color='#0A0A0A', edgecolor='#0A0A0A', width=0.6)
        ax.errorbar(x_pos, means, yerr=sems, fmt='none', color='#FF6B00', capsize=4, lw=2)
    
    elif plot_type == 'box':
        box_data = [d['values'] for d in data]
        bp = ax.boxplot(box_data, positions=x_pos, widths=0.5, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('#E4E4E7')
            patch.set_edgecolor('#0A0A0A')
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels(groups)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add brackets
    if comparisons:
        y_max = ax.get_ylim()[1]
        offset = 0
        for comp in comparisons:
            i1 = groups.index(comp['group1'])
            i2 = groups.index(comp['group2'])
            add_significance_bracket(ax, i1, i2, y_max + offset, comp['p_value'])
            offset += y_max * 0.08
        ax.set_ylim(top=y_max + offset + y_max * 0.05)
    
    plt.tight_layout()
    return fig
```

### Frontend: PlotCustomizer Component

**File:** `frontend/src/app/components/PlotCustomizer.jsx`

```jsx
import { useState } from 'react';

export default function PlotCustomizer({ onUpdate, initialSettings = {} }) {
  const [settings, setSettings] = useState({
    type: 'bar',
    errorBars: 'sem',
    showPoints: false,
    showBrackets: true,
    colorPrimary: '#0A0A0A',
    colorAccent: '#FF6B00',
    ...initialSettings
  });

  const update = (key, value) => {
    const next = { ...settings, [key]: value };
    setSettings(next);
    onUpdate?.(next);
  };

  return (
    <div className="space-y-4 p-4 border border-[color:var(--border-color)] rounded-[2px]">
      <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
        Plot Options
      </div>
      
      {/* Type */}
      <div className="flex gap-2">
        {['bar', 'box', 'violin'].map(t => (
          <button key={t} onClick={() => update('type', t)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-[2px] border ${
              settings.type === t 
                ? 'border-black text-black' 
                : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)]'
            }`}>
            {t.toUpperCase()}
          </button>
        ))}
      </div>
      
      {/* Error Bars */}
      <div>
        <label className="text-xs text-[color:var(--text-secondary)]">Error Bars</label>
        <select value={settings.errorBars} onChange={e => update('errorBars', e.target.value)}
          className="mt-1 w-full">
          <option value="none">None</option>
          <option value="sd">SD</option>
          <option value="sem">SEM</option>
          <option value="ci95">95% CI</option>
        </select>
      </div>
      
      {/* Brackets */}
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={settings.showBrackets} 
          onChange={e => update('showBrackets', e.target.checked)} />
        <span className="text-sm">Show significance brackets</span>
      </label>
    </div>
  );
}
```

---

## Task 6.5: AI Interpretations + Export

### Per-Result Interpretation Block

**In results rendering (AnalysisDesign.jsx):**

```jsx
{step.ai_interpretation && (
  <div className="mt-4 border-l-4 border-[color:var(--accent)] pl-4 py-3 bg-[color:var(--bg-secondary)] rounded-r-[2px]">
    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
      ✨ AI Interpretation
    </div>
    <div className="mt-2 text-sm text-[color:var(--text-primary)] leading-relaxed">
      {step.ai_interpretation}
    </div>
  </div>
)}
```

### Backend AI Generator

**File:** `backend/app/modules/ai_interpreter.py`

```python
def generate_interpretation(result: dict, method: str) -> str:
    """Generate Russian interpretation for statistical result."""
    
    p = result.get('p_value')
    stat = result.get('stat_value')
    effect = result.get('effect_size')
    
    sig = p < 0.05 if p else False
    
    templates = {
        't_test_ind': {
            True: f"Выявлены статистически значимые различия между группами (t = {stat:.2f}, p = {p:.3f}). " +
                  f"Размер эффекта Cohen's d = {effect:.2f}.",
            False: f"Статистически значимых различий не обнаружено (t = {stat:.2f}, p = {p:.3f})."
        },
        'anova': {
            True: f"Обнаружены значимые различия между группами (F = {stat:.2f}, p = {p:.3f}). " +
                  f"η² = {effect:.3f}.",
            False: f"Различия между группами не достигают статистической значимости (F = {stat:.2f}, p = {p:.3f})."
        }
    }
    
    return templates.get(method, {}).get(sig, "Интерпретация недоступна.")
```

### Enhanced Export Button

**Add to results header:**

```jsx
<div className="flex gap-2">
  <button onClick={handleExportPDF} className="btn-secondary text-xs px-3 py-1.5">
    📄 PDF
  </button>
  <button onClick={handleExportDocx} className="btn-secondary text-xs px-3 py-1.5">
    📝 Word
  </button>
  <button onClick={handleExportPlots} className="btn-primary text-xs px-3 py-1.5">
    📊 Plots
  </button>
</div>
```

---

## Verification

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
cd /Users/eduardbelskih/Проекты\ Github/statproject/backend && python3 -m pytest tests/ -v
```

---

## Success Criteria

- [ ] Plots have significance brackets (*, **, ***)
- [ ] PlotCustomizer allows type/error bars/brackets toggle
- [ ] AI interpretation block under each result
- [ ] Export buttons for PDF/DOCX/Plots
