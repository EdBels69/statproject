import React, { useMemo, useState } from 'react';
import Button from '../../components/ui/Button';

// Helper functions
function baseKey(raw) {
  const s = String(raw || '').trim();
  return s.replace(/\s+/g, ' ').replace(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?\d+)$/i, '').replace(/[_\-\s]+$/g, '').trim() || s;
}
function timeIndex(raw) {
  const s = String(raw || '').trim();
  const m = s.match(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?)(\d+)$/i);
  if (!m) return null;
  const n = Number.parseInt(m[1], 10);
  return Number.isFinite(n) ? n : null;
}

export default function MassDynamicsModal({
  isOpen,
  onClose,
  columns,
  statsByName,
  defaultGroupCol,
  defaultSubjectCol,
  formatMethodName,
  onAppendSteps,
}) {
  const normalizedCols = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .map((c) => {
        if (typeof c === 'string') return { name: c, type: '' };
        return { name: String(c?.name || ''), type: String(c?.type || '') };
      })
      .filter((c) => c.name);
  }, [columns]);

  const [method, setMethod] = useState(() => 'rm_anova');
  const [groupCol, setGroupCol] = useState(() => defaultGroupCol || '');
  const [groupValues, setGroupValues] = useState(() => []);
  const [subjectCol, setSubjectCol] = useState(() => defaultSubjectCol || '');
  const [timeMin, setTimeMin] = useState(() => '1');
  const [timeMax, setTimeMax] = useState(() => '6');

  const groupColOptions = useMemo(() => {
    return normalizedCols
      .filter((c) => c.type === 'categorical' || c.type === 'text' || c.type === 'datetime' || !c.type)
      .map((c) => c.name);
  }, [normalizedCols]);

  const subjectColOptions = useMemo(() => {
    const names = normalizedCols.map((c) => c.name);
    const byHeuristic = names.filter((n) => /(^id$|_id$|\bid\b)/i.test(n));
    return byHeuristic.length > 0 ? byHeuristic : names;
  }, [normalizedCols]);

  const groupValueOptions = useMemo(() => {
    if (!groupCol) return [];
    const payload = statsByName?.[groupCol];
    if (!payload || typeof payload !== 'object') return [];
    const cats = Array.isArray(payload.categories) ? payload.categories : [];
    if (cats.length > 0) return cats;
    const top = Array.isArray(payload.top_values) ? payload.top_values : [];
    return top.map((tv) => String(tv?.value ?? '')).filter(Boolean);
  }, [groupCol, statsByName]);

  const numericCandidates = useMemo(() => {
    return normalizedCols
      .filter((c) => c.type === 'numeric' || !c.type)
      .map((c) => c.name);
  }, [normalizedCols]);

  const minNeeded = method === 'friedman' ? 3 : 2;

  const groupedByBase = useMemo(() => {
    const groups = new Map();
    for (const n of numericCandidates) {
      const k = baseKey(n);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(n);
    }
    const minN = Number.parseInt(timeMin, 10);
    const maxN = Number.parseInt(timeMax, 10);
    const hasMin = Number.isFinite(minN);
    const hasMax = Number.isFinite(maxN);

    const out = [];
    for (const [k, names] of groups.entries()) {
      const sorted = [...names].sort((a, b) => {
        const ia = timeIndex(a);
        const ib = timeIndex(b);
        if (ia == null && ib == null) return String(a).localeCompare(String(b), 'ru');
        if (ia == null) return 1;
        if (ib == null) return -1;
        return ia - ib;
      });

      const inRange = sorted.filter((n) => {
        const idx = timeIndex(n);
        if (idx == null) return !(hasMin || hasMax);
        if (hasMin && idx < minN) return false;
        if (hasMax && idx > maxN) return false;
        return true;
      });

      const effective = inRange.length >= minNeeded ? inRange : sorted;
      if (effective.length < minNeeded) continue;

      out.push({ key: k, cols: effective });
    }

    out.sort((a, b) => a.key.localeCompare(b.key, 'ru'));
    return out;
  }, [minNeeded, numericCandidates, timeMax, timeMin]);

  const stepPreview = useMemo(() => {
    const bases = groupedByBase.length;
    const groupCount = groupValues.length > 0 ? groupValues.length : (groupCol ? 1 : 1);
    const steps = bases * groupCount;
    return { bases, steps };
  }, [groupCol, groupValues.length, groupedByBase.length]);

  const canGenerate = groupedByBase.length > 0
    && (method !== 'rm_anova' || Boolean(subjectCol));

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Массовая динамика"
      aria-hidden={!isOpen}
      onMouseDown={(e) => {
        if (!isOpen) return;
        if (e.target === e.currentTarget) onClose?.();
      }}
      onKeyDown={(e) => {
        if (!isOpen) return;
        if (e.key === 'Escape') {
          e.stopPropagation();
          onClose?.();
        }
      }}
    >
      <div className={`w-full max-w-2xl bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}>
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[color:var(--border-color)]">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Конструктор</div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Массовая динамика</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Метод</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="rm_anova">{formatMethodName?.('rm_anova') || 'RM ANOVA'}</option>
                <option value="friedman">{formatMethodName?.('friedman') || 'Friedman'}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Субъект (ID){method === 'rm_anova' ? '' : ' (опц.)'}</label>
              <select
                value={subjectCol}
                onChange={(e) => setSubjectCol(e.target.value)}
                disabled={method !== 'rm_anova'}
                className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)] disabled:bg-[color:var(--bg-secondary)]"
              >
                <option value="">—</option>
                {subjectColOptions.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
              {method === 'rm_anova' && !subjectCol ? (
                <div className="mt-1 text-xs text-[color:var(--accent)]">Нужен ID для rm_anova</div>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Группа (фильтр)</label>
              <select
                value={groupCol}
                onChange={(e) => {
                  setGroupCol(e.target.value);
                  setGroupValues([]);
                }}
                className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="">—</option>
                {groupColOptions.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Точки от</label>
                <input
                  value={timeMin}
                  onChange={(e) => setTimeMin(e.target.value)}
                  inputMode="numeric"
                  className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">до</label>
                <input
                  value={timeMax}
                  onChange={(e) => setTimeMax(e.target.value)}
                  inputMode="numeric"
                  className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
                />
              </div>
            </div>
          </div>

          {groupCol ? (
            <div className="rounded-[2px] border border-[color:var(--border-color)] overflow-hidden">
              <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Значения</div>
                <div className="text-xs text-[color:var(--text-muted)] font-mono">{groupValueOptions.length}</div>
              </div>
              <div className="max-h-[240px] overflow-y-auto">
                {groupValueOptions.length > 0 ? groupValueOptions.map((v) => {
                  const checked = groupValues.includes(v);
                  return (
                    <label key={v} className={`flex items-center gap-3 px-3 py-2 border-b border-[color:var(--border-color)] cursor-pointer ${checked ? 'bg-[color:var(--bg-secondary)]' : 'hover:bg-[color:var(--bg-secondary)]'}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setGroupValues((prev) => {
                            const arr = Array.isArray(prev) ? prev : [];
                            return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
                          });
                        }}
                        className="text-[color:var(--accent)] rounded-[2px]"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm truncate text-[color:var(--text-primary)]">{v}</div>
                      </div>
                    </label>
                  );
                }) : (
                  <div className="p-4 text-sm text-[color:var(--text-muted)]">Нет доступных значений (для {groupCol})</div>
                )}
              </div>
              <div className="px-3 py-2 bg-[color:var(--white)] flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setGroupValues(groupValueOptions)}
                  className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                  disabled={groupValueOptions.length === 0}
                >
                  Выбрать все
                </button>
                <button
                  type="button"
                  onClick={() => setGroupValues([])}
                  className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                  disabled={groupValues.length === 0}
                >
                  Очистить
                </button>
              </div>
            </div>
          ) : null}

          <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
            <div className="flex items-baseline justify-between gap-4">
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Объём</div>
              <div className="text-xs text-[color:var(--text-primary)] font-mono">{stepPreview.bases} переменных · ~{stepPreview.steps} шаг(ов)</div>
            </div>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
          <Button
            type="button"
            variant="primary"
            disabled={!canGenerate}
            onClick={() => {
              if (!canGenerate) return;

              const now = Date.now();
              const groups = groupCol && groupValues.length > 0 ? groupValues : [null];
              const steps = [];
              let idx = 0;

              for (const g of groups) {
                for (const item of groupedByBase) {
                  const outcome_cols = Array.isArray(item?.cols) ? item.cols : [];
                  if (method === 'friedman' && outcome_cols.length < 3) continue;
                  if (method === 'rm_anova' && outcome_cols.length < 2) continue;

                  const config = {
                    outcome_cols,
                    ...(method === 'rm_anova' ? { subject_col: subjectCol, group_col: '' } : {}),
                  };

                  if (groupCol && g != null) {
                    config.filter = { col: groupCol, value: g };
                  }

                  const baseLabel = baseKey(outcome_cols[0]);
                  const label = groupCol && g != null
                    ? `${formatMethodName?.(method) || method} · ${baseLabel} · ${groupCol}=${g}`
                    : `${formatMethodName?.(method) || method} · ${baseLabel}`;

                  steps.push({
                    id: `mass_${now}_${idx++}`,
                    method,
                    name: label,
                    config,
                  });
                }
              }

              if (steps.length > 0) onAppendSteps?.(steps);
              onClose?.();
            }}
          >
            Добавить шаги
          </Button>
        </div>
      </div>
    </div>
  );
}
