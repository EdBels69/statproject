import React, { useMemo, useState, useEffect, lazy, Suspense } from 'react';
import { getAnalysisResults } from '../../../lib/api';
import { useTranslation } from '../../../hooks/useTranslation';
import Button from '../../components/ui/Button';
import { useLanguage } from '../../../contexts/LanguageContext';
import {
    BeakerIcon,
    ArrowDownTrayIcon
} from '@heroicons/react/24/outline';

// Contextual Education Components
import { StatTooltip, EffectSizeExplainer, PowerExplainer } from '../../components/education';

const VisualizePlot = lazy(() => import('../../components/VisualizePlot'));
const ClusteredHeatmap = lazy(() => import('../../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../../components/InteractionPlot'));

/* --- SUB-COMPONENT: TABLE 1 (Descriptive) --- */
const Table1View = ({ data }) => {
    const { t } = useTranslation();
    if (!data || !data.data) return <div>{t('no_data')}</div>;
    const stats = data.data; // { "A": {mean, ...}, "B": {mean...}, "overall": {} }
    const groups = Object.keys(stats).filter(k => k !== 'overall');

    const rows = [
        'mean_sd',
        'median_q1_q3',
        'min_max',
        'ci_95'
    ];

    return (
        <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[color:var(--border-color)]">
                <thead className="bg-[color:var(--bg-secondary)]">
                    <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('metric')}</th>
                        {groups.map(g => (
                            <th key={g} className="px-6 py-3 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">
                                {t('group')} {g} ({t('n')}={stats[g]?.count || 0})
                            </th>
                        ))}
                        <th className="px-6 py-3 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider bg-[color:var(--bg-secondary)]">
                            {t('overall')} ({t('n')}={stats['overall']?.count || 0})
                        </th>
                    </tr>
                </thead>
                <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                    {rows.map((rowKey) => (
                        <tr key={rowKey}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-[color:var(--text-primary)]">{t(rowKey)}</td>
                            {groups.map(g => {
                                const s = stats[g];
                                let val = "";
                                if (rowKey === 'mean_sd') val = `${s.mean.toFixed(2)} (${s.std.toFixed(2)})`;
                                if (rowKey === 'median_q1_q3') val = `${s.median.toFixed(2)} [${s.q1.toFixed(2)}, ${s.q3.toFixed(2)}]`;
                                if (rowKey === 'min_max') val = `${s.min.toFixed(2)} - ${s.max.toFixed(2)}`;
                                if (rowKey === 'ci_95') val = `${s.ci_lower?.toFixed(2)} - ${s.ci_upper?.toFixed(2)}`;
                                return <td key={g} className="px-6 py-4 whitespace-nowrap text-sm text-[color:var(--text-secondary)]">{val}</td>
                            })}
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)]">
                                {rowKey === 'mean_sd' && stats?.overall?.mean != null ? `${stats.overall.mean.toFixed(2)}` : '-'}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

/* --- SUB-COMPONENT: HYPOTHESIS TEST --- */
const CompareView = ({ result, stepId }) => {
    const { t } = useTranslation();
    const { educationLevel } = useLanguage();
    const methodId = result?.method?.id || result?.type || result?.method;
    const assumptions = result?.assumption_checks || result?.assumptions;
    const methodRequested = result?.method_requested;
    const methodUsed = result?.method_used;
    const warnings = Array.isArray(result?.warnings) ? result.warnings : [];
    const roc = result?.roc;
    const coefficients = Array.isArray(result?.coefficients) ? result.coefficients : [];

    const chartFallback = useMemo(() => (
        <div className="animate-pulse" style={{
            height: 360,
            borderRadius: '2px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            fontSize: '12px'
        }}>
            {t('loading')}
        </div>
    ), [t]);

    const plot = (() => {
        if (methodId === 'clustered_correlation') {
            return (
                <Suspense fallback={chartFallback}>
                    <ClusteredHeatmap data={result} width={860} height={560} />
                </Suspense>
            );
        }

        if (methodId === 'mixed_effects') {
            return (
                <Suspense fallback={chartFallback}>
                    <InteractionPlot data={result} width={860} height={380} />
                </Suspense>
            );
        }

        return (
            <Suspense fallback={chartFallback}>
                <VisualizePlot
                    data={result.plot_data || []}
                    stats={result.plot_stats}
                    groups={result.groups}
                    comparisons={result?.comparisons || result?.pairwise_comparisons || result?.plot_comparisons}
                    exportScopeId={stepId}
                    exportKey="main"
                />
            </Suspense>
        );
    })();

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-4 p-4 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
                <div className={`p-2 rounded-[2px] border ${result.significant ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]' : 'bg-[color:var(--white)] text-[color:var(--text-primary)] border-[color:var(--border-color)]'}`}>
                    <BeakerIcon className="w-6 h-6" />
                </div>
                <div>
                    <h4 className="text-lg font-semibold text-[color:var(--text-primary)]">{result.method?.name || t('test_result')}</h4>
                    <p className="text-sm text-[color:var(--text-secondary)]">
                        {result.significant ? t('significant_difference_found') : t('no_significant_difference')}
                    </p>
                    {methodRequested && methodUsed && methodRequested !== methodUsed && (
                        <div className="mt-2 inline-flex items-center rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--white)] px-2 py-0.5 text-xs font-medium text-[color:var(--text-primary)]">
                            {t('auto_fallback_used', { from: methodRequested, to: methodUsed })}
                        </div>
                    )}
                </div>
                <div className="ml-auto text-right">
                    <StatTooltip term="p_value" level={educationLevel} position="left">
                        <div className="text-2xl font-bold text-[color:var(--accent)]">
                            {t('p_value_short', { value: typeof result?.p_value === 'number' ? result.p_value.toFixed(4) : t('not_available') })}
                        </div>
                        <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('p_value')}</div>
                    </StatTooltip>
                </div>
            </div>

            {(assumptions && (assumptions.normality || assumptions.homogeneity)) && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('assumption_checks')}</div>
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                        {assumptions?.normality && (
                            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
                                <div className="text-xs font-semibold text-[color:var(--text-primary)]">{t('normality')}</div>
                                <div className="mt-2 space-y-1">
                                    {Object.entries(assumptions.normality).map(([group, info]) => (
                                        <div key={group} className="flex items-center justify-between text-xs">
                                            <div className="text-[color:var(--text-secondary)]">{group}</div>
                                            <div className="font-mono text-[color:var(--text-primary)]">
                                                p={typeof info?.p_value === 'number' ? info.p_value.toFixed(4) : '-'}
                                                {' '}
                                                <span className={info?.passed ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--accent)]'}>
                                                    {info?.passed ? t('passed') : t('failed')}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {assumptions?.homogeneity && (
                            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
                                <div className="text-xs font-semibold text-[color:var(--text-primary)]">{t('homogeneity')}</div>
                                <div className="mt-2 flex items-center justify-between text-xs">
                                    <div className="text-[color:var(--text-secondary)]">Levene</div>
                                    <div className="font-mono text-[color:var(--text-primary)]">
                                        p={typeof assumptions.homogeneity?.p_value === 'number' ? assumptions.homogeneity.p_value.toFixed(4) : '-'}
                                        {' '}
                                        <span className={assumptions.homogeneity?.passed ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--accent)]'}>
                                            {assumptions.homogeneity?.passed ? t('passed') : t('failed')}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {warnings.length > 0 && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('warnings')}</div>
                    <div className="mt-2 space-y-1">
                        {warnings.map((w, idx) => (
                            <div key={idx} className="text-sm text-[color:var(--text-primary)]">
                                {String(w)}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {(result?.ai_interpretation || result?.conclusion) && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
                        {t('ai_interpretation')}
                    </div>
                    <div className="mt-3 border-l-2 border-[color:var(--accent)] pl-4 py-2 bg-[color:var(--bg-secondary)]">
                        <div className="text-sm text-[color:var(--text-primary)]">
                            {String(result?.ai_interpretation || result?.conclusion)}
                        </div>
                    </div>
                </div>
            )}

            {roc?.plot_data && Array.isArray(roc.plot_data) && roc.plot_data.length > 0 && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)] overflow-x-auto">
                    <div className="flex items-end justify-between gap-3">
                        <div>
                            <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('roc_curve')}</div>
                            {typeof roc?.auc === 'number' && (
                                <div className="mt-1 text-sm font-mono text-[color:var(--text-primary)]">{t('roc_auc', { value: roc.auc.toFixed(3) })}</div>
                            )}
                        </div>
                    </div>
                    <div className="mt-3">
                        <Suspense fallback={chartFallback}>
                            <VisualizePlot data={roc.plot_data} />
                        </Suspense>
                    </div>
                </div>
            )}

            {coefficients.length > 0 && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)] overflow-x-auto">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('coefficients')}</div>
                    <table className="mt-3 min-w-full divide-y divide-[color:var(--border-color)]">
                        <thead className="bg-[color:var(--bg-secondary)]">
                            <tr>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('variable')}</th>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('beta')}</th>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('p_value')}</th>
                                <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('confidence_interval')}</th>
                                {coefficients.some(c => typeof c?.odds_ratio === 'number') && (
                                    <th className="px-4 py-2 text-left text-xs font-medium text-[color:var(--text-secondary)] uppercase tracking-wider">{t('odds_ratio')}</th>
                                )}
                            </tr>
                        </thead>
                        <tbody className="bg-[color:var(--white)] divide-y divide-[color:var(--border-color)]">
                            {coefficients.map((c, idx) => {
                                const ciText = (typeof c?.ci_lower === 'number' && typeof c?.ci_upper === 'number')
                                    ? `[${c.ci_lower.toFixed(3)}, ${c.ci_upper.toFixed(3)}]`
                                    : '-';
                                const orText = (typeof c?.odds_ratio === 'number' && typeof c?.or_ci_lower === 'number' && typeof c?.or_ci_upper === 'number')
                                    ? `${c.odds_ratio.toFixed(3)} [${c.or_ci_lower.toFixed(3)}, ${c.or_ci_upper.toFixed(3)}]`
                                    : (typeof c?.odds_ratio === 'number' ? c.odds_ratio.toFixed(3) : '-');
                                return (
                                    <tr key={idx}>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-primary)] font-mono">{String(c?.variable ?? '')}</td>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{typeof c?.coefficient === 'number' ? c.coefficient.toFixed(3) : '-'}</td>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{typeof c?.p_value === 'number' ? c.p_value.toFixed(4) : '-'}</td>
                                        <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{ciText}</td>
                                        {coefficients.some(x => typeof x?.odds_ratio === 'number') && (
                                            <td className="px-4 py-2 text-sm text-[color:var(--text-secondary)] font-mono">{orText}</td>
                                        )}
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Effect Size with Visual Explainer */}
            {typeof result?.effect_size === 'number' && (
                <EffectSizeExplainer
                    type={result.effect_size_name === "Cohen's d" ? 'cohens_d' :
                        result.effect_size_name === 'η²' ? 'eta_squared' :
                            result.effect_size_name === 'r' ? 'r' : 'cohens_d'}
                    value={result.effect_size}
                    ci={typeof result.effect_size_ci_lower === 'number' && typeof result.effect_size_ci_upper === 'number'
                        ? [result.effect_size_ci_lower, result.effect_size_ci_upper]
                        : undefined}
                />
            )}

            {/* Power with Recommendations */}
            {typeof result?.power === 'number' && (
                <PowerExplainer
                    power={result.power}
                    effectSize={typeof result?.effect_size === 'number' ? result.effect_size : undefined}
                />
            )}

            {/* Additional Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Effect Size Compact (fallback if no visual explainer) */}
                {typeof result?.effect_size !== 'number' && (
                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                        <StatTooltip term="effect_size">
                            <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('effect_size')}</div>
                        </StatTooltip>
                        <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                            {t('not_available_short')}
                        </div>
                    </div>
                )}

                {/* Power Compact (fallback if no visual explainer) */}
                {typeof result?.power !== 'number' && (
                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                        <StatTooltip term="power">
                            <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('power')}</div>
                        </StatTooltip>
                        <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                            {t('not_available_short')}
                        </div>
                    </div>
                )}

                {/* BF10 */}
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                    <div className="text-xs text-[color:var(--text-secondary)] uppercase tracking-wide">{t('bf10')}</div>
                    <div className="mt-1 text-lg font-mono font-bold text-[color:var(--text-primary)]">
                        {typeof result?.bf10 === 'number' ? result.bf10.toPrecision(3) : t('not_available_short')}
                    </div>
                    {typeof result?.bf10 === 'number' && Number.isFinite(result.bf10) && (
                        <div className="flex items-center gap-2 mt-2">
                            <span className="text-sm text-[color:var(--text-secondary)]">Bayes Factor (BF₁₀):</span>
                            <span className="font-mono font-semibold">{Number(result.bf10).toFixed(2)}</span>
                            <span
                                className={`text-xs px-2 py-0.5 rounded ${
                                    result.bf10 > 100
                                        ? 'bg-green-100 text-green-800'
                                        : result.bf10 > 10
                                            ? 'bg-green-50 text-green-700'
                                            : result.bf10 > 3
                                                ? 'bg-yellow-50 text-yellow-700'
                                                : result.bf10 > 1
                                                    ? 'bg-gray-100 text-gray-600'
                                                    : 'bg-red-50 text-red-700'
                                }`}
                            >
                                {result.bf10 > 100
                                    ? 'очень сильные'
                                    : result.bf10 > 10
                                        ? 'сильные'
                                        : result.bf10 > 3
                                            ? 'умеренные'
                                            : result.bf10 > 1
                                                ? 'слабые'
                                                : 'против H₁'}
                                {' '}доказательства
                            </span>
                        </div>
                    )}
                </div>
            </div>

            <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)] overflow-x-auto">
                {plot}
            </div>
        </div>
    );
};

/* --- MAIN DASHBOARD --- */
const StepResults = ({ runId, datasetId }) => {
    const { t, hasTranslation } = useTranslation();
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState(0);
    const [sectionOrder, setSectionOrder] = useState([]);
    const [sectionEnabled, setSectionEnabled] = useState({});
    const [reportFormat, setReportFormat] = useState('docx');
    const [reportStyle, setReportStyle] = useState('apa7');

    useEffect(() => {
        if (!runId || !datasetId) return;
        let cancelled = false;

        queueMicrotask(() => {
            if (cancelled) return;
            setLoading(true);
        });

        getAnalysisResults(datasetId, runId)
            .then((data) => {
                if (cancelled) return;
                setResults(data);
            })
            .catch(console.error)
            .finally(() => {
                if (cancelled) return;
                setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [runId, datasetId]);

    const baseSteps = useMemo(() => {
        const map = results?.results && typeof results.results === 'object' ? results.results : {};
        return Object.keys(map).map((key) => {
            const i18nKey = `step_${key}`;
            const label = hasTranslation(i18nKey) ? t(i18nKey) : key.replace(/_/g, ' ').toUpperCase();
            return {
                id: key,
                data: map[key],
                label,
            };
        });
    }, [hasTranslation, results, t]);

    const baseStepIds = useMemo(() => baseSteps.map((s) => s.id), [baseSteps]);

    const mergedSectionOrder = useMemo(() => {
        const prevSafe = Array.isArray(sectionOrder) ? sectionOrder : [];
        const preserved = prevSafe.filter((id) => baseStepIds.includes(id));
        const appended = baseStepIds.filter((id) => !preserved.includes(id));
        return preserved.length || appended.length ? [...preserved, ...appended] : [];
    }, [baseStepIds, sectionOrder]);

    const mergedSectionEnabled = useMemo(() => {
        const src = (sectionEnabled && typeof sectionEnabled === 'object') ? sectionEnabled : {};
        const out = {};
        baseStepIds.forEach((id) => {
            const v = src[id];
            out[id] = typeof v === 'boolean' ? v : true;
        });
        return out;
    }, [baseStepIds, sectionEnabled]);

    const stepsById = useMemo(() => {
        const map = new Map();
        baseSteps.forEach((s) => map.set(s.id, s));
        return map;
    }, [baseSteps]);

    const orderedSteps = useMemo(() => {
        const order = mergedSectionOrder;
        const stitched = order.map((id) => stepsById.get(id)).filter(Boolean);
        const extras = baseSteps.filter((s) => !order.includes(s.id));
        return [...stitched, ...extras];
    }, [baseSteps, mergedSectionOrder, stepsById]);

    const visibleSteps = useMemo(() => {
        return orderedSteps.filter((s) => mergedSectionEnabled?.[s.id] !== false);
    }, [mergedSectionEnabled, orderedSteps]);

    const safeActiveTab = Math.max(0, Math.min(activeTab, Math.max(0, visibleSteps.length - 1)));
    const activeStep = visibleSteps[safeActiveTab];

    const apiBase = import.meta.env.VITE_API_URL || '/api/v1';
    const makeReportUrl = (format) => {
        const params = new URLSearchParams();
        params.set('dataset_id', String(datasetId));
        if (reportStyle) params.set('style', reportStyle);
        const enabledIds = visibleSteps.map((s) => s.id);
        if (enabledIds.length) params.set('sections', enabledIds.join(','));
        const orderIds = mergedSectionOrder;
        if (orderIds.length) params.set('order', orderIds.join(','));
        return `${apiBase}/analysis/protocol/report/${runId}/${format}?${params.toString()}`;
    };

    const moveSection = (id, direction) => {
        setSectionOrder((prev) => {
            const prevSafe = Array.isArray(prev) ? prev : [];
            const preserved = prevSafe.filter((k) => baseStepIds.includes(k));
            const appended = baseStepIds.filter((k) => !preserved.includes(k));
            const order = [...preserved, ...appended];
            const idx = order.indexOf(id);
            if (idx < 0) return prev;
            const nextIdx = idx + direction;
            if (nextIdx < 0 || nextIdx >= order.length) return prev;
            const tmp = order[idx];
            order[idx] = order[nextIdx];
            order[nextIdx] = tmp;
            return order;
        });
    };

    if (loading) return <div className="p-10 text-center animate-pulse text-[color:var(--text-secondary)]">{t('loading_results')}</div>;
    if (!results) return <div className="p-10 text-center text-[color:var(--error)]">{t('failed_to_load_results')}</div>;

    return (
        <div className="animate-fadeIn min-h-screen pb-20">
            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4 mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-[color:var(--text-primary)]">{results.protocol_name}</h2>
                    <p className="text-[color:var(--text-secondary)] text-sm">{t('run_id')}: {runId}</p>
                </div>
                <div className="w-full lg:w-[520px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                    <div className="px-4 py-3 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex flex-wrap items-center justify-between gap-3">
                        <div className="text-sm font-semibold text-[color:var(--text-primary)]">📄 Отчёт</div>
                        <div className="flex items-center gap-2">
                            <select
                                value={reportFormat}
                                onChange={(e) => setReportFormat(e.target.value)}
                                className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                aria-label="Формат отчёта"
                            >
                                <option value="docx">DOCX</option>
                                <option value="pdf">PDF</option>
                                <option value="html">HTML</option>
                            </select>
                            <select
                                value={reportStyle}
                                onChange={(e) => setReportStyle(e.target.value)}
                                className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                                aria-label="Стиль отчёта"
                            >
                                <option value="apa7">APA 7</option>
                                <option value="gost">ГОСТ</option>
                                <option value="simple">Простой</option>
                            </select>
                            <Button variant="ghost" size="sm" onClick={() => window.open(makeReportUrl('html'), '_blank')}>
                                👁 Превью
                            </Button>
                            <Button variant="secondary" size="sm" onClick={() => window.open(makeReportUrl(reportFormat), '_blank')}>
                                <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                                Скачать
                            </Button>
                        </div>
                    </div>

                    <div className="p-3">
                        <div className="grid grid-cols-1 gap-1">
                            {orderedSteps.map((s, idx) => (
                                <div key={s.id} className="flex items-center justify-between gap-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2">
                                    <label className="flex items-center gap-3 min-w-0 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={mergedSectionEnabled?.[s.id] !== false}
                                            onChange={() => setSectionEnabled((prev) => ({
                                                ...(prev && typeof prev === 'object' ? prev : {}),
                                                [s.id]: !(prev?.[s.id] !== false)
                                            }))}
                                            className="h-4 w-4 accent-[color:var(--accent)]"
                                        />
                                        <span className="text-sm text-[color:var(--text-primary)] truncate">{s.label}</span>
                                    </label>
                                    <div className="flex items-center gap-1">
                                        <button
                                            type="button"
                                            onClick={() => moveSection(s.id, -1)}
                                            disabled={idx === 0}
                                            className="h-7 w-7 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] disabled:opacity-40"
                                            aria-label="Поднять секцию"
                                        >
                                            ↑
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => moveSection(s.id, 1)}
                                            disabled={idx === orderedSteps.length - 1}
                                            className="h-7 w-7 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] disabled:opacity-40"
                                            aria-label="Опустить секцию"
                                        >
                                            ↓
                                        </button>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => {
                                                window.dispatchEvent(
                                                    new CustomEvent('statproject:export-plot', { detail: { scopeId: s.id, key: 'main' } })
                                                );
                                            }}
                                        >
                                            <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                                            {t('export_plot')}
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-[color:var(--border-color)] mb-6">
                <nav className="-mb-px flex space-x-8">
                    {visibleSteps.map((step, idx) => (
                        <button
                            key={step.id}
                            onClick={() => setActiveTab(idx)}
                            className={`
                                py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap transition-colors
                                ${safeActiveTab === idx
                                    ? 'border-[color:var(--accent)] text-[color:var(--accent)]'
                                    : 'border-transparent text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)]'}
                            `}
                        >
                            {step.label}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Content Body */}
            <div className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-6">
                {!activeStep ? (
                    <div className="text-sm text-[color:var(--text-secondary)]">Нет выбранных секций отчёта</div>
                ) : (
                    <>
                        {activeStep.data.type === 'table_1' && (
                            <Table1View data={activeStep.data} />
                        )}

                        {(activeStep.data.p_value !== undefined) && (
                            <CompareView result={activeStep.data} stepId={activeStep.id} />
                        )}

                        {activeStep.data.error && (
                            <div className="text-[color:var(--error)] p-4 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)]">
                                {t('analysis_error')}: {activeStep.data.error}
                            </div>
                        )}

                        {!['table_1'].includes(activeStep.data.type) && activeStep.data.p_value === undefined && (
                            <pre className="text-xs bg-[color:var(--bg-secondary)] p-4 rounded-[2px] border border-[color:var(--border-color)] overflow-auto max-h-96">
                                {JSON.stringify(activeStep.data, null, 2)}
                            </pre>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default StepResults;
