import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Badge from './ui/Badge';

const TYPE_OPTIONS = [
  { value: '', label: 'Не определено' },
  { value: 'id', label: 'Идентификатор' },
  { value: 'numeric', label: 'Количественная' },
  { value: 'categorical', label: 'Категориальная' },
  { value: 'date', label: 'Дата' }
];

const ROLE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'target', label: 'Target' },
  { value: 'factor', label: 'Factor' },
  { value: 'covariate', label: 'Covariate' },
  { value: 'ignore', label: 'Не использовать' }
];

function roleVariant(role) {
  if (role === 'target') return 'accent';
  if (role === 'ignore') return 'neutral';
  if (role === 'factor') return 'neutral';
  if (role === 'covariate') return 'neutral';
  return 'neutral';
}

function formatStatLine(colStats, uiType) {
  if (!colStats) return '';
  if (uiType === 'numeric') {
    const mean = colStats.mean;
    const min = colStats.min;
    const max = colStats.max;
    const parts = [];
    if (typeof mean === 'number') parts.push(`M=${mean.toFixed(3)}`);
    if (typeof min === 'number') parts.push(`min=${min.toFixed(3)}`);
    if (typeof max === 'number') parts.push(`max=${max.toFixed(3)}`);
    return parts.join(' • ');
  }

  if (uiType === 'categorical') {
    const cats = Array.isArray(colStats.categories) ? colStats.categories : [];
    const top = Array.isArray(colStats.top_values) ? colStats.top_values : [];
    const head = cats.length ? `${cats.length} категорий` : 'Категории';
    const topStr = top
      .slice(0, 3)
      .map((t) => `${t?.value}(${t?.count})`)
      .filter(Boolean)
      .join(', ');
    return topStr ? `${head}: ${topStr}` : head;
  }

  return '';
}

export default function VariableListView({
  columns,
  scanReport,
  onTypeChange,
  onRoleChange,
  onOpenSettings
}) {
  const [query, setQuery] = useState('');
  const [focusedIndex, setFocusedIndex] = useState(0);
  const rootRef = useRef(null);
  const itemRefs = useRef([]);
  const safeColumns = useMemo(() => (Array.isArray(columns) ? columns : []), [columns]);
  const statsByCol = scanReport?.columns || {};

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return safeColumns;
    return safeColumns.filter((c) => String(c?.name || '').toLowerCase().includes(q));
  }, [query, safeColumns]);

  const safeFocusedIndex = visible.length > 0
    ? Math.max(0, Math.min(focusedIndex, visible.length - 1))
    : 0;

  const focusItem = useCallback((nextIndex) => {
    if (visible.length === 0) return;
    const safe = Math.max(0, Math.min(nextIndex, visible.length - 1));
    setFocusedIndex(safe);
  }, [visible.length]);

  useEffect(() => {
    const el = itemRefs.current?.[safeFocusedIndex];
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'nearest' });
    }
  }, [safeFocusedIndex, visible]);

  const handleKeyDown = useCallback((e) => {
    if (e.defaultPrevented) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    const tag = String(e.target?.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.target?.isContentEditable) return;

    if (visible.length === 0) return;

    const key = String(e.key || '').toLowerCase();
    if (key === 'arrowdown') {
      e.preventDefault();
      focusItem(safeFocusedIndex + 1);
      return;
    }
    if (key === 'arrowup') {
      e.preventDefault();
      focusItem(safeFocusedIndex - 1);
      return;
    }

    const col = visible[safeFocusedIndex];
    const name = col?.name;
    if (!name) return;

    if (key === 'enter') {
      e.preventDefault();
      onOpenSettings?.(name);
      return;
    }

    if (key === 'n') {
      e.preventDefault();
      onTypeChange?.(name, 'numeric');
      return;
    }
    if (key === 'c') {
      e.preventDefault();
      onTypeChange?.(name, 'categorical');
      return;
    }
    if (key === 'd') {
      e.preventDefault();
      onTypeChange?.(name, 'date');
      return;
    }
    if (key === 'i') {
      e.preventDefault();
      onTypeChange?.(name, 'id');
      return;
    }
    if (key === '0' || key === 'backspace' || key === 'delete') {
      e.preventDefault();
      onTypeChange?.(name, '');
      return;
    }

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
  }, [focusItem, onOpenSettings, onRoleChange, onTypeChange, safeFocusedIndex, visible]);

  return (
    <div
      ref={rootRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className="space-y-4"
      aria-label="Переменные"
    >
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
            Переменные
          </div>
          <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)]">
            Назначь роли
          </div>
        </div>
        <div className="w-full max-w-xs">
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setFocusedIndex(0);
            }}
            placeholder="Поиск по имени…"
            className="w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2 text-sm text-[color:var(--text-primary)]"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {visible.map((col, idx) => {
          const role = col.role ?? '';
          const uiType = col.uiType ?? '';
          const colStats = statsByCol?.[col.name];
          const statLine = formatStatLine(colStats, uiType);
          const isFocused = idx === safeFocusedIndex;

          return (
            <div
              key={col.name}
              ref={(el) => {
                itemRefs.current[idx] = el;
              }}
              className={`variable-card rounded-[2px] border border-transparent bg-[color:var(--white)] px-5 py-4 ${isFocused ? 'ring-1 ring-[color:var(--accent)] ring-inset' : ''}`}
              onMouseEnter={() => setFocusedIndex(idx)}
              onMouseDown={() => {
                const root = rootRef.current;
                if (root && typeof root.focus === 'function') root.focus();
              }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="truncate text-base font-semibold text-[color:var(--text-primary)]">
                      {col.name}
                    </div>
                    {role ? <Badge variant={roleVariant(role)}>{role}</Badge> : null}
                  </div>
                  {statLine ? (
                    <div className="mt-1 text-xs text-[color:var(--text-secondary)] tabular-nums">
                      {statLine}
                    </div>
                  ) : null}
                </div>

                <button
                  type="button"
                  onClick={() => onOpenSettings?.(col.name)}
                  className="shrink-0 rounded-[2px] border border-[color:var(--border-color)] bg-transparent px-3 py-2 text-xs font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                >
                  ⚙︎
                </button>
              </div>

              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-2">
                  <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
                    Тип
                  </div>
                  <select
                    value={uiType}
                    onChange={(e) => onTypeChange?.(col.name, e.target.value)}
                    className="mt-1 w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 py-2 text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--text-primary)]"
                  >
                    {TYPE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-2">
                  <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
                    Роль
                  </div>
                  <select
                    value={role}
                    onChange={(e) => onRoleChange?.(col.name, e.target.value)}
                    className="mt-1 w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 py-2 text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--text-primary)]"
                  >
                    {ROLE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-[color:var(--border-color)] text-xs text-[color:var(--text-muted)]">
        <span className="font-semibold">Горячие клавиши:</span>
        {' '}↑↓ навигация • N numeric • C categorical • D date • I id
        {' '}• T target • G factor • X ignore • R убрать роль • Enter настройки
      </div>
    </div>
  );
}
