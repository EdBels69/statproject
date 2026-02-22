import React, { useMemo } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import SearchableSelect from '../SearchableSelect';

export default function VariableSelector({
  columns = [],
  roles = { target: '', group: '', covariates: [] },
  onRolesChange,
  disabled = false,
  className = ''
}) {
  const { t } = useTranslation();

  const columnNames = useMemo(() => {
    return Array.isArray(columns)
      ? columns
        .map((c) => {
          if (!c) return null;
          if (typeof c === 'string') return c;
          return c.name || c.column || c.id || null;
        })
        .filter(Boolean)
      : [];
  }, [columns]);

  const handleTargetChange = (next) => {
    const base = { ...roles };
    base.target = next || '';
    onRolesChange?.(base);
  };

  const handleGroupChange = (next) => {
    const base = { ...roles };
    base.group = next || '';
    onRolesChange?.(base);
  };

  return (
    <div className={`${className}`.trim()}>
      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
        <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)]">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('variables')}</div>
        </div>

        <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-[color:var(--text-muted)] mb-1">{t('target')}</label>
            <SearchableSelect
              value={roles?.target || ''}
              onChange={handleTargetChange}
              options={columnNames}
              placeholder={t('select_variable')}
              disabled={disabled}
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-[color:var(--text-muted)] mb-1">{t('group')}</label>
            <SearchableSelect
              value={roles?.group || ''}
              onChange={handleGroupChange}
              options={columnNames}
              placeholder={t('select_variable')}
              disabled={disabled}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

