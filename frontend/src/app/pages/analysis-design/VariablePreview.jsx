import React, { useMemo } from 'react';

export default function VariablePreview({ t, targetVar, groupVar, groupLabel, statsByName }) {
  const payloadTarget = statsByName?.[targetVar] || null;
  const payloadGroup = statsByName?.[groupVar] || null;

  const targetStats = useMemo(() => {
    if (!targetVar || !payloadTarget || typeof payloadTarget !== 'object') return null;
    const total = Number(payloadTarget.total);
    const missing = Number(payloadTarget.missing_count);
    const n = (Number.isFinite(total) ? total : 0) - (Number.isFinite(missing) ? missing : 0);

    const warnings = [];
    if (Number.isFinite(n) && n > 0 && n < 30) warnings.push(`${t('sample_size_short')} n=${n}`);
    if (Number.isFinite(n) && n <= 1) warnings.push(t('no_variation_warning'));
    if (Number.isFinite(missing) && missing > 0) warnings.push(`${t('missing')}: ${missing}`);

    const mean = typeof payloadTarget.mean === 'number' ? payloadTarget.mean : null;
    const min = typeof payloadTarget.min === 'number' ? payloadTarget.min : null;
    const max = typeof payloadTarget.max === 'number' ? payloadTarget.max : null;
    const normalityP = payloadTarget?.normality?.p_value;

    return {
      n: Number.isFinite(n) ? n : null,
      mean,
      min,
      max,
      normalityP: typeof normalityP === 'number' ? normalityP : null,
      warnings,
    };
  }, [payloadTarget, t, targetVar]);

  const groupStats = useMemo(() => {
    if (!groupVar || !payloadGroup || typeof payloadGroup !== 'object') return null;
    const unique = typeof payloadGroup.unique_count === 'number' ? payloadGroup.unique_count : null;
    const missing = typeof payloadGroup.missing_count === 'number' ? payloadGroup.missing_count : null;
    const topValues = Array.isArray(payloadGroup.top_values) ? payloadGroup.top_values : [];

    const warnings = [];
    if (typeof unique === 'number' && unique < 2) warnings.push(t('groups_too_few_warning'));
    if (typeof unique === 'number' && unique > 20) warnings.push(t('groups_too_many_warning'));
    if (typeof missing === 'number' && missing > 0) warnings.push(`${t('missing')}: ${missing}`);

    return {
      unique,
      topValues,
      warnings,
    };
  }, [groupVar, payloadGroup, t]);

  if (!targetStats && !groupStats) return null;

  const warningLine = [...(targetStats?.warnings || []), ...(groupStats?.warnings || [])]
    .filter(Boolean)
    .slice(0, 4);

  return (
    <div className="px-6">
      <div className="max-w-7xl mx-auto">
        <div className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-[color:var(--text-muted)] font-semibold">
              {t('preview')}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
            {targetStats ? (
              <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--text-muted)] font-semibold">{t('target')}</div>
                <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{targetVar}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--text-secondary)]">
                  {typeof targetStats.n === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">n = </span><span className="font-mono font-semibold text-[color:var(--text-primary)]">{targetStats.n}</span></div>
                  ) : null}
                  {typeof targetStats.mean === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">M = </span><span className="font-mono font-semibold text-[color:var(--text-primary)]">{targetStats.mean.toFixed(2)}</span></div>
                  ) : null}
                  {typeof targetStats.min === 'number' && typeof targetStats.max === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">Range: </span><span className="font-mono">{targetStats.min.toFixed(2)}–{targetStats.max.toFixed(2)}</span></div>
                  ) : null}
                  {typeof targetStats.normalityP === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">{t('normality')} p = </span><span className="font-mono">{targetStats.normalityP < 0.001 ? '<0.001' : targetStats.normalityP.toFixed(3)}</span></div>
                  ) : null}
                </div>
              </div>
            ) : null}

            {groupStats ? (
              <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--text-muted)] font-semibold">{groupLabel}</div>
                <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{groupVar}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--text-secondary)]">
                  {typeof groupStats.unique === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">{t('groups')} = </span><span className="font-mono font-semibold text-[color:var(--text-primary)]">{groupStats.unique}</span></div>
                  ) : null}
                  {Array.isArray(groupStats.topValues) && groupStats.topValues.length > 0 ? (
                    <div className="min-w-0"><span className="text-[color:var(--text-muted)]">Top: </span><span className="font-mono">{groupStats.topValues.slice(0, 3).map((tv) => tv?.value).filter(Boolean).join(', ')}</span></div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          {warningLine.length > 0 ? (
            <div className="mt-3 text-xs text-[color:var(--text-secondary)]">
              <span className="text-[color:var(--accent)] font-semibold">{t('warnings')}:</span> {warningLine.join(' • ')}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
