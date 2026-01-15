import React, { useEffect, useRef } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import Button from './ui/Button';

export default function KeyboardShortcutsHelp({ isOpen, onClose }) {
  const dialogRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const root = dialogRef.current;
    if (!root) return;
    const focusable = root.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])');
    const first = focusable?.[0];
    if (first && typeof first.focus === 'function') first.focus();
  }, [isOpen]);

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Горячие клавиши"
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
        className={`w-full max-w-lg bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}
      >
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[color:var(--border-color)]">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Навигация</div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Горячие клавиши</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] active:scale-[0.98]"
            aria-label="Закрыть"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="px-5 py-4">
          <div className="grid grid-cols-1 gap-2">
            {[
              { key: 'Ctrl/Cmd + Enter', action: 'Выполнить протокол' },
              { key: 'Ctrl/Cmd + S', action: 'Сохранить протокол' },
              { key: 'Ctrl/Cmd + O', action: 'Открыть “Мои протоколы”' },
              { key: 'Ctrl/Cmd + Z', action: 'Отменить' },
              { key: 'Ctrl/Cmd + Shift + Z', action: 'Повторить' },
              { key: 'Esc', action: 'Закрыть активное окно' },
              { key: '?', action: 'Показать эту подсказку' }
            ].map((row) => (
              <div key={row.key} className="flex items-center justify-between gap-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-4 py-3">
                <div className="text-sm font-semibold text-[color:var(--text-primary)]">{row.action}</div>
                <div className="text-xs font-mono text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] px-2 py-1 tabular-nums">
                  {row.key}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 text-xs text-[color:var(--text-secondary)]">
            Подсказка: сочетания работают в любом месте страницы, кроме полей ввода.
          </div>
        </div>

        <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-end">
          <Button type="button" variant="secondary" onClick={onClose}>
            Понятно
          </Button>
        </div>
      </div>
    </div>
  );
}
