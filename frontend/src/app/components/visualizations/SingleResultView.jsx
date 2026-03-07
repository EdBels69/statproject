import React, { Suspense } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import { formatP, formatNum } from './utils';
import Button from '../ui/Button';
import AnovaTable from './AnovaTable';
import RegressionTable from './RegressionTable';

export default function SingleResultView({ result, AnalyticsChart, chartFallback, onDownloadReport, onDownloadDocx, onDownloadHtml }) {
  const { t } = useTranslation();

  if (!result) return null;

  // Determine if we should show a specific table or the default summary cards
  const showAnovaTable = !!result.anova_table;
  const showRegressionTable = !!result.coefficients;

  return (
    <div className="space-y-6">

      {/* 1. Statistics Display (Cards or Table) */}
      {showAnovaTable ? (
        <div className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-4">
          <div className="mb-4 text-xs font-black uppercase tracking-tighter text-[color:var(--text-secondary)]">
            {t('anova_table_title') || 'ANOVA Table'}
          </div>
          <AnovaTable result={result} />
        </div>
      ) : showRegressionTable ? (
        <div className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-4">
          <div className="mb-4 text-xs font-black uppercase tracking-tighter text-[color:var(--text-secondary)]">
            {t('coefficients_table_title') || 'Model Coefficients'}
          </div>
          <RegressionTable result={result} />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
            <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">{t('p_value_label')}</span>
            <span className={`text-4xl font-mono font-black ${result.significant ? 'text-[color:var(--success)]' : 'text-[color:var(--text-primary)]'}`}>
              {formatP(result.p_value)}
            </span>
          </div>
          <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
            <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">{t('statistic_label')}</span>
            <span className="text-4xl font-mono font-black text-[color:var(--text-primary)]">
              {formatNum(result.stat_value, 2)}
            </span>
          </div>
          <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
            <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">{t('significance_label')}</span>
            <span className={`text-xl font-bold ${result.significant ? 'text-[color:var(--success)]' : 'text-[color:var(--text-muted)]'}`}>
              {result.significant ? t('significant_yes') : t('significant_no')}
            </span>
          </div>
        </div>
      )}

      {/* 2. Effect Size & Power (Only for card view or if not redundant) */}
      {!showAnovaTable && !showRegressionTable && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
            <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">{t('effect_size_label')}</span>
            <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
              {typeof result.effect_size === 'number'
                ? `${result.effect_size_name || t('effect_label')} ${formatNum(result.effect_size, 2)}`
                : '—'
              }
            </span>
            <div className="mt-2 text-xs text-[color:var(--text-secondary)] font-mono">
              {typeof result.effect_size_ci_lower === 'number' && typeof result.effect_size_ci_upper === 'number'
                ? t('confidence_interval_value', { range: `[${formatNum(result.effect_size_ci_lower, 2)}, ${formatNum(result.effect_size_ci_upper, 2)}]` })
                : result.ci_lower !== undefined ?
                  t('confidence_interval_value', { range: `[${formatNum(result.ci_lower, 2)}, ${formatNum(result.ci_upper, 2)}]` }) :
                  t('confidence_interval_unavailable')
              }
            </div>
            {/* Effect Size Interpretation Badge */}
            {result.effect_size_interpretation && (
              <div className={`mt-2 inline-block px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wide
                    ${['large', 'very_large'].includes(result.effect_size_interpretation) ? 'bg-purple-100 text-purple-800' :
                  ['medium'].includes(result.effect_size_interpretation) ? 'bg-blue-100 text-blue-800' :
                    ['small'].includes(result.effect_size_interpretation) ? 'bg-gray-100 text-gray-800' :
                      'bg-gray-50 text-gray-500'
                }`}>
                {t(`effect_size_interpretation.${result.effect_size_interpretation}`) || result.effect_size_interpretation}
              </div>
            )}
          </div>
          <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
            <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">{t('power_label')}</span>
            <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
              {formatNum(result.power, 2)}
            </span>
          </div>
          <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
            <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">BF10</span>
            <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
              {typeof result.bf10 === 'number' ? result.bf10.toPrecision(3) : '—'}
            </span>
            {typeof result.bf10 === 'number' && (
              <div className={`mt-2 text-xs px-2 py-0.5 rounded inline-block ${result.bf10 > 100 ? 'bg-green-100 text-green-800' :
                  result.bf10 > 10 ? 'bg-green-50 text-green-700' :
                    result.bf10 > 3 ? 'bg-yellow-50 text-yellow-700' :
                      result.bf10 > 1 ? 'bg-gray-100 text-gray-600' :
                        'bg-red-50 text-red-700'
                }`}>
                {result.bf10 > 100 ? 'очень сильные' :
                  result.bf10 > 10 ? 'сильные' :
                    result.bf10 > 3 ? 'умеренные' :
                      result.bf10 > 1 ? 'слабые' :
                        'против H₁'}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="bg-[color:var(--white)] p-8 rounded-[2px] border border-[color:var(--border-color)]">
        <Suspense fallback={chartFallback || <div>Loading chart...</div>}>
          {AnalyticsChart ? <AnalyticsChart result={result} /> : null}
        </Suspense>
      </div>

      <div className="flex justify-center mt-4 gap-3 flex-wrap">
        {onDownloadReport && (
          <Button variant="secondary" onClick={onDownloadReport} className="px-8">
            <span>📥</span> {t('download_report_pdf')}
          </Button>
        )}
        {onDownloadDocx && (
          <Button variant="ghost" onClick={onDownloadDocx} className="px-8">
            <span>⌁</span> {t('download_report_docx')}
          </Button>
        )}
        {onDownloadHtml && (
          <Button variant="ghost" onClick={onDownloadHtml} className="px-8">
            <span>🌐</span> {t('download_report_html')}
          </Button>
        )}
      </div>
    </div>
  );
}
