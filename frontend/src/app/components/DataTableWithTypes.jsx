import React, { useMemo, useState } from 'react';
import { Cog6ToothIcon } from '@heroicons/react/24/outline';

const TYPE_OPTIONS = [
  { value: '', label: 'Не определено' },
  { value: 'id', label: 'Идентификатор' },
  { value: 'numeric', label: 'Количественная' },
  { value: 'categorical', label: 'Категориальная' },
  { value: 'date', label: 'Дата' }
];

export default function DataTableWithTypes({
  columns,
  rows,
  onTypeChange,
  onOpenSettings,
  limit = 12
}) {
  const safeColumns = useMemo(() => (Array.isArray(columns) ? columns : []), [columns]);
  const safeRows = Array.isArray(rows) ? rows : [];

  const totalCols = safeColumns.length;
  const colLimit = totalCols > 80 ? 24 : totalCols;
  const [colOffset, setColOffset] = useState(0);

  const safeColOffset = Math.min(Math.max(0, colOffset), Math.max(0, totalCols - 1));

  const visibleColumns = useMemo(() => {
    if (!totalCols) return [];
    return safeColumns.slice(safeColOffset, safeColOffset + colLimit);
  }, [colLimit, safeColOffset, safeColumns, totalCols]);

  return (
    <div className="rounded-[2px] border border-[color:var(--border-color)] overflow-hidden bg-[color:var(--white)]">
      {totalCols > colLimit ? (
        <div className="px-4 py-3 border-b border-[color:var(--border-color)] bg-[color:var(--white)] flex items-center justify-between gap-3">
          <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
            Колонки {safeColOffset + 1}–{Math.min(totalCols, safeColOffset + colLimit)} / {totalCols}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setColOffset((v) => Math.max(0, v - colLimit))}
              disabled={safeColOffset <= 0}
              className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
            >
              ◀︎
            </button>
            <button
              type="button"
              onClick={() => setColOffset((v) => Math.min(Math.max(0, totalCols - 1), v + colLimit))}
              disabled={safeColOffset + colLimit >= totalCols}
              className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
            >
              ▶︎
            </button>
            <input
              type="number"
              min={1}
              max={Math.max(1, totalCols)}
              value={Math.max(1, safeColOffset + 1)}
              onChange={(e) => {
                const raw = Number(e.target.value);
                if (!Number.isFinite(raw)) return;
                const next = Math.max(1, Math.min(totalCols || 1, raw));
                setColOffset(next - 1);
              }}
              className="h-8 w-20 px-2 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
            />
          </div>
        </div>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr>
              {visibleColumns.map((col) => (
                <th
                  key={col.name}
                  className="p-0 align-bottom border-b border-[color:var(--border-color)]"
                >
                  <div className="px-4 pt-4 pb-2 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[12px] font-semibold tracking-[0.14em] uppercase text-[color:var(--text-secondary)] truncate">
                        {col.name}
                      </div>
                      {col.example !== undefined && col.example !== null && String(col.example).trim() ? (
                        <div className="mt-1 text-xs text-[color:var(--text-muted)] truncate">
                          {String(col.example)}
                        </div>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenSettings?.(col.name)}
                      className="shrink-0 p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                      aria-label={`Настройки: ${col.name}`}
                    >
                      <Cog6ToothIcon className="w-4 h-4" aria-hidden="true" />
                    </button>
                  </div>

                  <div className="px-4 pb-4">
                    <select
                      value={col.uiType ?? ''}
                      onChange={(e) => onTypeChange?.(col.name, e.target.value)}
                      className="w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-2 py-1 text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-primary)]"
                      aria-label={`Тип переменной: ${col.name}`}
                    >
                      {TYPE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {safeRows.slice(0, limit).map((row, idx) => (
              <tr key={idx} className="hover:bg-[color:var(--bg-secondary)]">
                {visibleColumns.map((col) => (
                  <td
                    key={col.name}
                    className="px-4 py-2 text-sm border-b border-[color:var(--border-color)] text-[color:var(--text-primary)]"
                  >
                    {row?.[col.name] === null || row?.[col.name] === undefined
                      ? ''
                      : String(row[col.name])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
