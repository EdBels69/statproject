import React from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import TestSelectionPanel from './TestSelectionPanel';

export default function TestCatalog({
  datasetId,
  onTestSelect,
  suggestedConfig,
  disabled = false
}) {
  const { t } = useTranslation();

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
      <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
        <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('tests')}</div>
      </div>
      <div className="h-[520px]">
        <TestSelectionPanel
          variant="compact"
          onTestSelect={onTestSelect}
          datasetId={datasetId}
          suggestedConfig={suggestedConfig}
          disabled={disabled}
        />
      </div>
    </div>
  );
}
