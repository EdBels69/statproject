import { lazy, Suspense } from 'react';

const ClusteredHeatmap = lazy(() => import('../../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../../components/InteractionPlot'));
const VisualizePlot = lazy(() => import('../../components/VisualizePlot'));

export default function StepResultRenderer({ step, t, formatMethodName }) {
  const payload = step?.results;
  const method = step?.method;

  const chartFallback = (
    <div className="animate-pulse h-[360px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-center text-[color:var(--text-muted)] text-xs">
      {t('loading')}
    </div>
  );

  if (method === 'mixed_effects') {
    return (
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
          <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('interaction')}</div>
          <div className="mt-2 flex items-baseline gap-3">
            <div className="text-2xl font-black text-[color:var(--text-primary)] font-mono">
              {typeof payload?.interaction_p_value === 'number'
                ? payload.interaction_p_value < 0.001
                  ? '< 0.001'
                  : payload.interaction_p_value.toFixed(4)
                : t('not_available_short')}
            </div>
            <div className="text-xs text-[color:var(--text-secondary)]">{t('time_group_p_value')}</div>
          </div>
        </div>

        <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
          <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('interaction_plot')}</div>
          <div className="mt-3 overflow-x-auto">
            <Suspense fallback={chartFallback}>
              <InteractionPlot data={payload} width={640} height={380} />
            </Suspense>
          </div>
        </div>
      </div>
    );
  }

  if (method === 'clustered_correlation') {
    return (
      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
        <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('clustered_heatmap')}</div>
        <div className="mt-3 overflow-x-auto">
          <Suspense fallback={chartFallback}>
            <ClusteredHeatmap data={payload} width={760} height={560} />
          </Suspense>
        </div>
      </div>
    );
  }

  if (Array.isArray(payload?.plot_data) && payload.plot_data.length > 0) {
    const comparisons = payload?.comparisons || payload?.pairwise_comparisons || payload?.plot_comparisons;
    return (
      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
        <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('plot')}</div>
        <div className="mt-3">
          <Suspense fallback={chartFallback}>
            <VisualizePlot data={payload.plot_data} stats={payload.plot_stats} groups={payload.groups} comparisons={comparisons} />
          </Suspense>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('p_value')}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--text-primary)]">
            {typeof payload?.p_value === 'number'
              ? payload.p_value < 0.001
                ? '< 0.001'
                : payload.p_value.toFixed(4)
              : t('not_available_short')}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('statistic')}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--text-primary)]">
            {typeof payload?.stat_value === 'number' ? payload.stat_value.toFixed(3) : t('not_available_short')}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('statistical_significance')}</div>
          <div className={`mt-1 text-sm font-semibold ${payload?.significant ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-secondary)]'}`}>
            {payload?.significant ? t('yes') : t('no')}
          </div>
        </div>
        <div>
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('method')}</div>
          <div className="mt-1 text-sm text-[color:var(--text-secondary)] truncate">
            {formatMethodName(method)}
          </div>
        </div>
      </div>
    </div>
  );
}
