import React, { Suspense } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import { formatP, formatNum } from './utils';
import Button from '../ui/Button';

export default function SingleResultView({ result, AnalyticsChart, chartFallback, onDownloadReport, onDownloadDocx, onDownloadHtml }) {
  const { t } = useTranslation();

  if (!result) return null;

  return (
    <div className="space-y-6">
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
              : t('confidence_interval_unavailable')
            }
          </div>
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
        </div>
      </div>

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
