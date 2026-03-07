import React from 'react';
import Button from '../../components/ui/Button';
import GlobalSettingsPanel from './GlobalSettingsPanel';

export default function VibeDesignModal({
  isOpen,
  onClose,
  value,
  onValueChange,
  globalSettings,
  onGlobalSettingsChange,
  onGenerate,
  onGenerateAndRun,
  isLoading,
  error,
  preview,
  onApply,
}) {
  if (!isOpen) return null;

  const steps = Array.isArray(preview?.protocol) ? preview.protocol : [];
  const notes = Array.isArray(preview?.notes) ? preview.notes : [];

  return (
    <div className="fixed inset-0 z-[70]">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 p-4 md:p-8 flex items-start justify-center overflow-y-auto">
        <div className="w-full max-w-4xl bg-[color:var(--white)] border border-black rounded-[2px] shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
          <div className="px-4 py-3 border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Vibe</div>
              <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">Текст → протокол</div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black"
            >
              Закрыть
            </button>
          </div>

          <div className="p-4 grid grid-cols-1 lg:grid-cols-[1.2fr,0.8fr] gap-4">
            <div className="space-y-3">
              <div className="bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] p-3">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Описание</div>
                <textarea
                  value={value}
                  onChange={(e) => onValueChange?.(e.target.value)}
                  className="mt-2 w-full min-h-[180px] p-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm leading-relaxed"
                  placeholder="Вставь сюда абзац из протокола/статьи: дизайн, группы, исходы, ковариаты, время…"
                />
                {error ? (
                  <div className="mt-2 text-xs text-[color:var(--accent)] font-semibold">{error}</div>
                ) : null}
                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="text-xs text-[color:var(--text-secondary)]">ИИ вернёт черновик шагов; ты редактируешь как обычно.</div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      onClick={onGenerateAndRun}
                      disabled={isLoading || String(value || '').trim().length < 12}
                      variant="ghost"
                      size="sm"
                    >
                      {isLoading ? 'Собираю…' : 'Сразу отчёт'}
                    </Button>
                    <Button
                      type="button"
                      onClick={onGenerate}
                      disabled={isLoading || String(value || '').trim().length < 12}
                      variant="primary"
                      size="sm"
                    >
                      {isLoading ? 'Собираю…' : 'Собрать протокол'}
                    </Button>
                  </div>
                </div>
              </div>

              {steps.length > 0 ? (
                <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                  <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-2">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Превью</div>
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{steps.length} шаг(ов)</div>
                  </div>
                  <div className="divide-y divide-[color:var(--border-color)]">
                    {steps.slice(0, 20).map((s, idx) => (
                      <div key={`${s?.id || idx}`} className="px-3 py-2">
                        <div className="text-xs text-[color:var(--text-secondary)]">{String(s?.name || s?.method || '').trim() || `Шаг ${idx + 1}`}</div>
                        <div className="mt-1 text-xs font-mono text-[color:var(--text-primary)]">{String(s?.method || '')}</div>
                      </div>
                    ))}
                  </div>
                  <div className="p-3 border-t border-[color:var(--border-color)]">
                    <Button type="button" onClick={onApply} variant="ghost" className="w-full" disabled={steps.length === 0}>
                      Применить в конструктор
                    </Button>
                  </div>
                </div>
              ) : null}

              {notes.length > 0 ? (
                <div className="text-xs text-[color:var(--text-secondary)]">
                  {notes.slice(0, 4).map((n, i) => (
                    <div key={i}>{String(n)}</div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="space-y-3">
              <GlobalSettingsPanel value={globalSettings} onChange={onGlobalSettingsChange} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
