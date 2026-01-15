# AI Agent Prompt — Phase 7: UX Overhaul

> **Цель:** Сделать UI интуитивным как StatTech.ru

---

## CONTEXT

**Problem:** Current UI is cluttered. User wants StatTech-style interface where:

1. Data table shows type selector under each column header
2. Variables become a vertical list with role assignment
3. More whitespace, less visual noise

**Design:** White (#FFF), Black (#0A0A0A), Orange (#FF6B00)

---

## TASK 7.1: Data Table with Inline Type Selectors

### Create `frontend/src/app/components/DataTableWithTypes.jsx`

```jsx
import { useState } from 'react';

const TYPE_OPTIONS = [
  { value: '', label: 'Не определено', color: 'var(--text-muted)' },
  { value: 'id', label: 'Идентификатор', color: 'var(--text-muted)' },
  { value: 'numeric', label: 'Количественная', color: 'var(--accent)' },
  { value: 'categorical', label: 'Категориальная', color: 'var(--black)' },
  { value: 'date', label: 'Дата', color: 'var(--text-secondary)' }
];

export default function DataTableWithTypes({ columns, rows, onTypeChange }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.name} className="text-left p-0 border-b border-[color:var(--border-color)]">
                <div className="px-4 pt-3 pb-1">
                  <div className="text-sm font-semibold text-[color:var(--text-primary)]">
                    {col.name}
                  </div>
                </div>
                <div className="px-4 pb-3">
                  <select
                    value={col.type || ''}
                    onChange={e => onTypeChange(col.name, e.target.value)}
                    className="w-full text-[10px] uppercase tracking-wider font-semibold 
                               bg-[color:var(--bg-secondary)] border-none px-2 py-1 rounded-[2px]"
                  >
                    {TYPE_OPTIONS.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 10).map((row, idx) => (
            <tr key={idx} className="hover:bg-[color:var(--bg-secondary)]">
              {columns.map(col => (
                <td key={col.name} className="px-4 py-2 text-sm border-b border-[color:var(--border-color)]">
                  {row[col.name]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## TASK 7.2: Variable List View

### Create `frontend/src/app/components/VariableListView.jsx`

Each variable as a card with:

- Name
- Type selector
- Role selector (Target / Factor / Covariate / Ignore)
- Quick stats (n, M, SD or categories)

---

## TASK 7.3: Column Settings Modal

### Create `frontend/src/app/components/ColumnSettingsModal.jsx`

Gear icon on column → Modal with tabs:

- **Общие** — Type, Label
- **Зависимости** — Check dependent variables

---

## TASK 7.4: Fresh Design Updates

### Update `index.css`

```css
/* More breathing room */
.content-area {
  padding: 24px 32px;
}

/* Variable card - minimal borders */
.variable-card {
  background: var(--white);
  border: 1px solid transparent;
  padding: 16px 20px;
  transition: border-color 0.15s, background 0.15s;
}

.variable-card:hover {
  border-color: var(--border-color);
  background: var(--bg-secondary);
}

/* Type badge */
.type-badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 2px;
}

.type-badge--numeric { background: rgba(255,107,0,0.1); color: var(--accent); }
.type-badge--categorical { background: var(--gray-100); color: var(--black); }
```

---

## VERIFICATION

```bash
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run lint
cd /Users/eduardbelskih/Проекты\ Github/statproject/frontend && npm run dev
```

---

## SUCCESS CRITERIA

- [ ] DataTableWithTypes shows type dropdown under each header
- [ ] VariableListView shows cards with role assignment
- [ ] Modal has tabs (Общие, Зависимости)
- [ ] More whitespace, cards expand on hover
- [ ] Flow works: Upload → Table → Variables → Analyze

---

## START

```
view_file /Users/eduardbelskih/Проекты\ Github/statproject/PHASE7_PLAN.md
```

Implement 7.1 first. **GO!**
