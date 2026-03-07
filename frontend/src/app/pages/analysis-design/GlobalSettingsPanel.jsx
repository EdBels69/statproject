import React from 'react';
import { normalizeGlobalSettings } from './analysisDesignUtils';

export default function GlobalSettingsPanel({ value, onChange }) {
  const v = value && typeof value === 'object' ? value : normalizeGlobalSettings(null);

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
      <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)]">
        <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Глобальные настройки</div>
      </div>
      <div className="p-3 grid grid-cols-1 gap-3">
        <label className="grid gap-1">
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Альтернатива</div>
          <select
            value={v.alternative}
            onChange={(e) => onChange?.({ ...v, alternative: e.target.value })}
            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
          >
            <option value="two-sided">Двусторонняя</option>
            <option value="less">Односторонняя: меньше</option>
            <option value="greater">Односторонняя: больше</option>
          </select>
        </label>

        <label className="grid gap-1">
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Пост-хок</div>
          <select
            value={v.post_hoc}
            onChange={(e) => onChange?.({ ...v, post_hoc: e.target.value })}
            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
          >
            <option value="none">Нет</option>
            <option value="tukey">Tukey</option>
            <option value="dunn">Dunn</option>
          </select>
        </label>

        <label className="grid gap-1">
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Поправка</div>
          <select
            value={v.post_hoc_correction}
            onChange={(e) => onChange?.({ ...v, post_hoc_correction: e.target.value })}
            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
          >
            <option value="none">Нет</option>
            <option value="bh">BH (FDR)</option>
            <option value="bky">BKY</option>
          </select>
        </label>
      </div>
    </div>
  );
}
