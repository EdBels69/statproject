import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  XMarkIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  TrashIcon,
  CheckIcon
} from '@heroicons/react/24/outline';
import Badge from './ui/Badge';
import Button from './ui/Button';

function downloadJson(payload, filename) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function safeString(value) {
  return String(value ?? '').trim();
}

function formatDate(value) {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    return d.toLocaleString('ru-RU', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function SaveProtocolModal({
  isOpen,
  onClose,
  onSave,
  defaultName = '',
  defaultDescription = ''
}) {
  const [name, setName] = useState(defaultName);
  const [description, setDescription] = useState(defaultDescription);
  const [tags, setTags] = useState('');
  const dialogRef = useRef(null);

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

  const nameTrimmed = safeString(name);

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Сохранить протокол"
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
        className={`w-full max-w-xl bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}
      >
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[color:var(--border-color)]">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Протокол</div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Сохранить протокол</div>
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

        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Название</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Например: Анализ эффективности лечения"
              className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
            />
            {!nameTrimmed ? (
              <div className="mt-1 text-xs text-[color:var(--error)]">Название обязательно</div>
            ) : null}
          </div>

          <div>
            <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Описание</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Коротко: что делает этот протокол и для каких данных"
              rows={3}
              className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)] resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Теги (опционально)</label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="через запятую: oncology, baseline, q1"
              className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
            />
          </div>
        </div>

        <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            type="button"
            variant="primary"
            disabled={!nameTrimmed}
            onClick={() => {
              if (!nameTrimmed) return;
              const tagList = tags
                .split(',')
                .map((t) => safeString(t))
                .filter(Boolean);
              onSave?.({ name: nameTrimmed, description: safeString(description), tags: tagList });
            }}
          >
            <CheckIcon className="w-4 h-4" />
            Сохранить
          </Button>
        </div>
      </div>
    </div>
  );
}

export function ProtocolLibraryModal({
  isOpen,
  onClose,
  protocols,
  onLoad,
  onDelete,
  onImport,
  onExport
}) {
  const fileInputRef = useRef(null);
  const dialogRef = useRef(null);
  const [activeId, setActiveId] = useState(null);

  const list = useMemo(() => (Array.isArray(protocols) ? protocols : []), [protocols]);
  const active = useMemo(() => list.find((p) => p?.id === activeId) || list[0] || null, [activeId, list]);

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

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Мои протоколы"
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
        className={`w-full max-w-4xl bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}
      >
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[color:var(--border-color)]">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Протоколы</div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Мои протоколы</div>
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
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm text-[color:var(--text-secondary)]">
              {list.length > 0 ? `Сохранено: ${list.length}` : 'Пока нет сохранённых протоколов'}
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept="application/json"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  e.target.value = '';
                  if (!file) return;
                  try {
                    const text = await file.text();
                    const parsed = JSON.parse(text);
                    onImport?.(parsed);
                  } catch {
                    window.alert('Не удалось импортировать JSON протокола');
                  }
                }}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-3 py-2 rounded-[2px] text-sm font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] flex items-center gap-2"
              >
                <ArrowUpTrayIcon className="w-4 h-4" />
                Импорт
              </button>
              <button
                type="button"
                onClick={() => {
                  if (!active) return;
                  onExport?.(active);
                }}
                disabled={!active}
                className="px-3 py-2 rounded-[2px] text-sm font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <ArrowDownTrayIcon className="w-4 h-4" />
                Экспорт
              </button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-1">
              <div className="border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] text-xs font-semibold tracking-[0.18em] text-[color:var(--text-secondary)] uppercase">Список</div>
                <div className="max-h-[52vh] overflow-y-auto">
                  {list.map((p) => {
                    const isActive = p?.id === active?.id;
                    return (
                      <button
                        key={p?.id}
                        type="button"
                        onClick={() => setActiveId(p?.id)}
                        className={`w-full text-left px-3 py-3 border-b border-[color:var(--border-color)] hover:bg-[color:var(--bg-secondary)] ${isActive ? 'bg-[color:var(--black)] text-[color:var(--white)] hover:bg-[color:var(--black)]' : 'text-[color:var(--text-primary)]'}`}
                      >
                        <div className="text-sm font-semibold truncate">{p?.name || 'Без названия'}</div>
                        <div className={`mt-1 text-xs truncate ${isActive ? 'text-[color:var(--white)]' : 'text-[color:var(--text-secondary)]'}`}>{formatDate(p?.created_at) || ''}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="lg:col-span-2">
              <div className="border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-secondary)] uppercase">Просмотр</div>
                    <div className="mt-0.5 text-sm font-bold text-[color:var(--text-primary)] truncate">{active?.name || '—'}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        if (!active) return;
                        const ok = window.confirm('Удалить этот протокол?');
                        if (!ok) return;
                        onDelete?.(active.id);
                        setActiveId(null);
                      }}
                      disabled={!active}
                      className="p-2 rounded-[2px] text-[color:var(--text-secondary)] hover:text-[color:var(--error)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-40 disabled:cursor-not-allowed"
                      aria-label="Удалить"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        if (!active) return;
                        onLoad?.(active);
                      }}
                      disabled={!active}
                      className="h-9 px-3"
                    >
                      Применить
                    </Button>
                  </div>
                </div>

                <div className="p-4 space-y-4">
                  {active?.description ? (
                    <div className="text-sm text-[color:var(--text-primary)] whitespace-pre-wrap">{active.description}</div>
                  ) : (
                    <div className="text-sm text-[color:var(--text-secondary)]">Описание не задано</div>
                  )}

                  {Array.isArray(active?.tags) && active.tags.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {active.tags.map((tag) => (
                        <Badge key={tag} variant="neutral">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  ) : null}

                  <div>
                    <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-secondary)] uppercase">Шаги</div>
                    <div className="mt-2 border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                      {Array.isArray(active?.steps) && active.steps.length > 0 ? (
                        active.steps.map((s, idx) => (
                          <div key={`${s?.method || 'step'}_${idx}`} className="px-3 py-2 border-b border-[color:var(--border-color)] last:border-b-0">
                            <div className="flex items-baseline justify-between gap-3">
                              <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">{idx + 1}. {s?.method || '—'}</div>
                              <div className="text-[10px] text-[color:var(--text-secondary)] font-mono truncate">{s?.config ? 'config' : ''}</div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="px-3 py-3 text-sm text-[color:var(--text-secondary)]">Нет шагов</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function exportProtocolAsJsonFile(protocol) {
  const id = safeString(protocol?.id) || 'protocol';
  downloadJson(protocol, `${id}.json`);
}
