import React from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import ExportButtons from '../ExportButtons';
import VisualizationFactory from '../visualizations/VisualizationFactory';

export default function ResultsViewer({
  results,
  formatMethodName,
  datasetId,
  AnalyticsChart,
  chartFallback,
  onDownloadReport,
  onDownloadDocx,
  onDownloadHtml
}) {
  const { t } = useTranslation();

  if (!results) return null;

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
      <div className="px-4 py-3 border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase truncate">
            {t('analysis_results')}
          </div>
          <div className="text-xs text-[color:var(--text-secondary)] truncate">
            {results?.status || t('not_available_short')} · {results?.completed_steps ?? 0}/{results?.total_steps ?? 0}
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {Array.isArray(results?.errors) && results.errors.length > 0 ? (
          <div className="bg-[color:var(--bg-secondary)] border border-[color:var(--error)] rounded-[2px] p-4 text-sm text-[color:var(--error)]">
            <div className="text-[10px] font-semibold tracking-[0.18em] uppercase">{t('errors')}</div>
            <div className="mt-2 space-y-2">
              {results.errors.map((e, idx) => (
                <div key={`${e?.step_id || 'step'}_${idx}`} className="rounded-[2px] bg-[color:var(--white)] border border-[color:var(--border-color)] p-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">
                      {e?.method || t('unknown')}
                    </div>
                    <div className="text-[10px] text-[color:var(--text-secondary)] font-mono truncate">
                      {e?.error || t('unknown_error')}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {Array.isArray(results?.results) && results.results.length > 0 ? (
          results.results.map((step, idx) => (
            <div key={step?.step_id || `${step?.method || 'step'}_${idx}`} className="space-y-3">
              <div className="flex items-baseline justify-between">
                <div className="text-sm font-bold text-[color:var(--text-primary)] truncate">
                  {formatMethodName?.(step?.method) || step?.method}
                </div>
                <div className="text-xs text-[color:var(--text-secondary)] font-mono">
                  {step?.status || t('not_available_short')}
                </div>
              </div>
              <VisualizationFactory
                result={step}
                AnalyticsChart={AnalyticsChart}
                chartFallback={chartFallback}
                onDownloadReport={onDownloadReport}
                onDownloadDocx={onDownloadDocx}
                onDownloadHtml={onDownloadHtml}
              />
            </div>
          ))
        ) : (
          <div className="text-sm text-[color:var(--text-secondary)]">{t('no_results_yet')}</div>
        )}

        <div className="pt-1">
          <ExportButtons datasetId={datasetId} />
        </div>
      </div>
    </div>
  );
}
