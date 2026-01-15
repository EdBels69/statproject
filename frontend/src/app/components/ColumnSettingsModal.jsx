import React, { useEffect, useMemo, useRef, useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import Button from './ui/Button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/Tabs';

const ROLE_OPTIONS = [
  { value: '', label: '—' },
  { value: 'target', label: 'Target' },
  { value: 'factor', label: 'Factor' },
  { value: 'covariate', label: 'Covariate' },
  { value: 'ignore', label: 'Не использовать' }
];

function safeString(value) {
  return String(value ?? '').trim();
}

export default function ColumnSettingsModal({
  isOpen,
  columnName,
  columns,
  value,
  onClose,
  onSave
}) {
  const dialogRef = useRef(null);
  const [tab, setTab] = useState('general');
  const [draft, setDraft] = useState(() => value || {});

  useEffect(() => {
    if (!isOpen) return;
    const root = dialogRef.current;
    if (!root) return;
    const focusable = root.querySelectorAll(
      'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
    );
    const first = focusable?.[0];
    if (first && typeof first.focus === 'function') first.focus();
  }, [isOpen]);

  const categoricalCandidates = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .filter((c) => c?.uiType === 'categorical')
      .map((c) => c.name)
      .filter(Boolean);
  }, [columns]);

  const title = safeString(columnName);

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label={title ? `Настройки: ${title}` : 'Настройки колонки'}
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
          return;
        }
        if (e.key !== 'Tab') return;
        const root = dialogRef.current;
        if (!root) return;
        const focusable = Array.from(
          root.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')
        ).filter((el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true');
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement;
        if (e.shiftKey) {
          if (active === first || !root.contains(active)) {
            e.preventDefault();
            last.focus();
          }
          return;
        }
        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={`w-full max-w-2xl bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}
      >
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[color:var(--border-color)]">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
              Настройки
            </div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">{title || 'Колонка'}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
            aria-label="Закрыть"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList>
              <TabsTrigger value="general">Общие</TabsTrigger>
              <TabsTrigger value="deps">Зависимости</TabsTrigger>
            </TabsList>

            <TabsContent value="general" className="pt-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
                    Название
                  </div>
                  <input
                    value={draft?.display_name ?? ''}
                    onChange={(e) => setDraft((p) => ({ ...p, display_name: e.target.value }))}
                    placeholder={title || 'Например: Систолическое АД'}
                    className="mt-1 w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2 text-sm text-[color:var(--text-primary)]"
                  />
                </div>

                <div>
                  <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
                    Роль
                  </div>
                  <select
                    value={draft?.role ?? ''}
                    onChange={(e) => setDraft((p) => ({ ...p, role: e.target.value }))}
                    className="mt-1 w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2 text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--text-primary)]"
                  >
                    {ROLE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-3">
                <label className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-3 flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={Boolean(draft?.include_descriptive ?? true)}
                    onChange={(e) => setDraft((p) => ({ ...p, include_descriptive: e.target.checked }))}
                    className="mt-1 w-4 h-4 rounded-[2px] border-[color:var(--border-color)] accent-[color:var(--accent)]"
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-[color:var(--text-primary)]">Descriptive</div>
                    <div className="mt-0.5 text-xs text-[color:var(--text-secondary)]">Показывать в описательной статистике</div>
                  </div>
                </label>

                <label className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-3 flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={Boolean(draft?.include_comparison ?? true)}
                    onChange={(e) => setDraft((p) => ({ ...p, include_comparison: e.target.checked }))}
                    className="mt-1 w-4 h-4 rounded-[2px] border-[color:var(--border-color)] accent-[color:var(--accent)]"
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-[color:var(--text-primary)]">Comparison</div>
                    <div className="mt-0.5 text-xs text-[color:var(--text-secondary)]">Разрешить для сравнений/моделей</div>
                  </div>
                </label>

                <label className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-3 flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={Boolean(draft?.group_var)}
                    onChange={(e) => setDraft((p) => ({ ...p, group_var: e.target.checked }))}
                    className="mt-1 w-4 h-4 rounded-[2px] border-[color:var(--border-color)] accent-[color:var(--accent)]"
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold text-[color:var(--text-primary)]">Group var</div>
                    <div className="mt-0.5 text-xs text-[color:var(--text-secondary)]">Помечать как переменную группировки</div>
                  </div>
                </label>
              </div>
            </TabsContent>

            <TabsContent value="deps" className="pt-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
                    Subgroup
                  </div>
                  <select
                    value={draft?.subgroup ?? ''}
                    onChange={(e) => setDraft((p) => ({ ...p, subgroup: e.target.value }))}
                    className="mt-1 w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2 text-sm text-[color:var(--text-primary)]"
                  >
                    <option value="">—</option>
                    {categoricalCandidates.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <div className="mt-1 text-xs text-[color:var(--text-secondary)]">Использовать как подгруппу (если нужно)</div>
                </div>

                <div>
                  <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">
                    Timepoint
                  </div>
                  <select
                    value={draft?.timepoint ?? ''}
                    onChange={(e) => setDraft((p) => ({ ...p, timepoint: e.target.value }))}
                    className="mt-1 w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2 text-sm text-[color:var(--text-primary)]"
                  >
                    <option value="">—</option>
                    {categoricalCandidates.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <div className="mt-1 text-xs text-[color:var(--text-secondary)]">Переменная времени/условия</div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              onSave?.({
                role: safeString(draft?.role),
                group_var: Boolean(draft?.group_var),
                subgroup: safeString(draft?.subgroup),
                timepoint: safeString(draft?.timepoint),
                display_name: safeString(draft?.display_name),
                include_descriptive: Boolean(draft?.include_descriptive ?? true),
                include_comparison: Boolean(draft?.include_comparison ?? true)
              });
            }}
          >
            Сохранить
          </Button>
        </div>
      </div>
    </div>
  );
}
