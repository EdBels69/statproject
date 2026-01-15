import React, { useEffect, useMemo, useRef, useState } from 'react';
import { XMarkIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline';
import { getExportSizePresets, resolveExportSize } from '../utils/exportPlot';
import Button from './ui/Button';

export default function ExportSettingsModal({
  isOpen,
  onClose,
  onConfirm,
  defaultTitle = ''
}) {
  const dialogRef = useRef(null);
  const presets = useMemo(() => getExportSizePresets(), []);
  const [format, setFormat] = useState('png');
  const [sizePresetId, setSizePresetId] = useState('journal');
  const [dpi, setDpi] = useState(300);
  const [fontSizePt, setFontSizePt] = useState(10);
  const [background, setBackground] = useState('white');
  const [title, setTitle] = useState(defaultTitle);
  const [style, setStyle] = useState('publication');
  const [customWidthIn, setCustomWidthIn] = useState(7);
  const [customHeightIn, setCustomHeightIn] = useState(5);

  const effectiveSize = useMemo(() => {
    return resolveExportSize(sizePresetId, customWidthIn, customHeightIn);
  }, [customHeightIn, customWidthIn, sizePresetId]);

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
      aria-label="Экспорт графика"
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
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Экспорт</div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Экспорт графика</div>
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

        <div className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Формат</label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="png">PNG</option>
                <option value="svg">SVG</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Пресет размера</label>
              <select
                value={sizePresetId}
                onChange={(e) => setSizePresetId(e.target.value)}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                {presets.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Ширина (дюймы)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    value={sizePresetId === 'custom' ? customWidthIn : effectiveSize.widthIn}
                    onChange={(e) => setCustomWidthIn(e.target.value)}
                    disabled={sizePresetId !== 'custom'}
                    className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm disabled:bg-[color:var(--bg-secondary)] disabled:text-[color:var(--text-secondary)] focus:outline-none focus:border-[color:var(--accent)]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Высота (дюймы)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="1"
                    value={sizePresetId === 'custom' ? customHeightIn : effectiveSize.heightIn}
                    onChange={(e) => setCustomHeightIn(e.target.value)}
                    disabled={sizePresetId !== 'custom'}
                    className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm disabled:bg-[color:var(--bg-secondary)] disabled:text-[color:var(--text-secondary)] focus:outline-none focus:border-[color:var(--accent)]"
                  />
                </div>
              </div>
              <div className="mt-2 text-[11px] text-[color:var(--text-secondary)] font-mono">
                Итог: {effectiveSize.widthIn}" × {effectiveSize.heightIn}"
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">DPI</label>
              <select
                value={dpi}
                onChange={(e) => setDpi(Number(e.target.value))}
                disabled={format !== 'png'}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm disabled:bg-[color:var(--bg-secondary)] disabled:text-[color:var(--text-secondary)] focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value={150}>150</option>
                <option value={300}>300</option>
                <option value={600}>600</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Размер шрифта</label>
              <select
                value={fontSizePt}
                onChange={(e) => setFontSizePt(Number(e.target.value))}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value={8}>8 pt</option>
                <option value={10}>10 pt</option>
                <option value={12}>12 pt</option>
                <option value={14}>14 pt</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Фон</label>
              <select
                value={background}
                onChange={(e) => setBackground(e.target.value)}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="white">Белый</option>
                <option value="transparent">Прозрачный</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Заголовок (опционально)</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Без заголовка"
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Стиль</label>
              <select
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="publication">Публикация</option>
                <option value="web">Веб</option>
              </select>
            </div>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              onConfirm?.({
                format,
                sizePresetId,
                widthIn: effectiveSize.widthIn,
                heightIn: effectiveSize.heightIn,
                dpi,
                fontSizePt,
                background,
                title,
                style
              });
            }}
          >
            <ArrowDownTrayIcon className="w-4 h-4" />
            Экспортировать
          </Button>
        </div>
      </div>
    </div>
  );
}
