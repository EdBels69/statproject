import { useEffect, useMemo, useState, lazy, Suspense } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import {
    runBatchAnalysis,
    getDataset,
    getVariableMapping,
    exportDocx,
    exportReport,
    getDatasetDesignReview,
    confirmDatasetDesignReview,
    revokeDatasetDesignReview,
} from '../../lib/api';
import VariableSelector from '../components/VariableSelector';
import ResearchFlowNav from '../components/ResearchFlowNav';
import SearchableSelect from '../components/SearchableSelect';
import { useTranslation } from '../../hooks/useTranslation';
import { EffectSizeExplainer, StatTooltip } from '../components/education';
import { getEffectSizeInterpretation } from '../components/education/EffectSizeExplainer';
import VariableSelectorModal from './analyze/VariableSelectorModal';
import ChartFallback from './analyze/ChartFallback';
import { buildAnalyzeFlowStepData, deriveAnalyzeMode, downloadBlob } from './analyze/analyzePageUtils';

const VisualizePlot = lazy(() => import('../components/VisualizePlot'));
const ClusteredHeatmap = lazy(() => import('../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../components/InteractionPlot'));

export default function Analyze({ modeOverride } = {}) {
    const { t } = useTranslation();
    const na = t('not_available_short');
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [columns, setColumns] = useState([]);
    const [variableMapping, setVariableMapping] = useState(location.state?.variableMapping || null);

    const [loading, setLoading] = useState(false);
    const [batchResult, setBatchResult] = useState(() => location.state?.batchResult || null);
    const [error, setError] = useState(null);
    const [selectedVarDetail, setSelectedVarDetail] = useState(() => location.state?.selectedVarDetail || null);
    const [activeGroupCol, setActiveGroupCol] = useState(() => location.state?.activeGroupCol || null);
    const [exportingDocx, setExportingDocx] = useState(false);
    const [exportingPdf, setExportingPdf] = useState(false);
    const [isConfigOpen, setIsConfigOpen] = useState(false);
    const [designReviewConfirmed, setDesignReviewConfirmed] = useState(Boolean(location.state?.designReviewConfirmed));
    const [designReviewLoading, setDesignReviewLoading] = useState(true);
    const [designReviewUpdating, setDesignReviewUpdating] = useState(false);
    const [designReviewError, setDesignReviewError] = useState(null);

    const mode = deriveAnalyzeMode(location.pathname, modeOverride);

    const activeStep = mode;

    const designBasePath = location.state?.origin === 'ai' ? '/ai' : '/design';

    const flowStepData = useMemo(
        () => buildAnalyzeFlowStepData({ designReviewConfirmed, batchResult }),
        [batchResult, designReviewConfirmed],
    );

    const chartFallback = useMemo(() => <ChartFallback label={t('loading')} />, [t]);

    useEffect(() => {
        const loadColumns = async () => {
            if (location.state?.columns?.length > 0) {
                setColumns(location.state.columns);
            } else {
                try {
                    const profile = await getDataset(id);
                    if (profile?.columns) setColumns(profile.columns);
                } catch (e) { console.error(e); }
            }
        };

        loadColumns();
    }, [id, location.state]);

    useEffect(() => {
        if (!batchResult) return;
        const currentState = location.state || {};
        if (
            currentState.batchResult === batchResult &&
            currentState.selectedVarDetail === selectedVarDetail &&
            currentState.activeGroupCol === activeGroupCol &&
            currentState.columns === columns &&
            currentState.variableMapping === variableMapping
        ) {
            return;
        }
        navigate(location.pathname, {
            replace: true,
            state: {
                ...currentState,
                batchResult,
                selectedVarDetail,
                activeGroupCol,
                columns,
                variableMapping,
            }
        });
    }, [activeGroupCol, batchResult, columns, location.pathname, location.state, navigate, selectedVarDetail, variableMapping]);

    useEffect(() => {
        const loadMapping = async () => {
            if (location.state?.variableMapping && typeof location.state.variableMapping === 'object') {
                setVariableMapping(location.state.variableMapping);
                return;
            }

            try {
                const res = await getVariableMapping(id);
                setVariableMapping(res?.mapping && typeof res.mapping === 'object' ? res.mapping : {});
            } catch {
                setVariableMapping({});
            }
        };

        loadMapping();
    }, [id, location.state]);

    useEffect(() => {
        let cancelled = false;
        const loadDesignReview = async () => {
            setDesignReviewLoading(true);
            setDesignReviewError(null);
            try {
                const status = await getDatasetDesignReview(id);
                if (cancelled) return;
                setDesignReviewConfirmed(Boolean(status?.confirmed));
            } catch (e) {
                if (cancelled) return;
                setDesignReviewError(e?.message || 'Не удалось загрузить статус Design Review');
            } finally {
                if (!cancelled) setDesignReviewLoading(false);
            }
        };
        loadDesignReview();
        return () => {
            cancelled = true;
        };
    }, [id]);

    const toggleDesignReview = async (nextConfirmed) => {
        if (designReviewUpdating) return;
        setDesignReviewUpdating(true);
        setDesignReviewError(null);
        try {
            if (nextConfirmed) {
                await confirmDatasetDesignReview(id, { actor: 'analyze_page', source: 'analyze_ui' });
                setDesignReviewConfirmed(true);
            } else {
                await revokeDatasetDesignReview(id, { actor: 'analyze_page', reason: 'manual_reset' });
                setDesignReviewConfirmed(false);
            }
        } catch (e) {
            setDesignReviewError(e?.message || 'Не удалось обновить Design Review');
        } finally {
            setDesignReviewUpdating(false);
        }
    };

    const suggestedDefaults = useMemo(() => {
        const mapping = variableMapping && typeof variableMapping === 'object' ? variableMapping : {};
        const hasMapping = Object.keys(mapping).length > 0;
        if (!hasMapping || !Array.isArray(columns) || columns.length === 0) {
            return { groupName: null, targetNames: [] };
        }

        const groupName =
            columns.find((c) => mapping?.[c?.name]?.group_var)?.name ||
            columns.find((c) => mapping?.[c?.name]?.role === 'Group')?.name ||
            null;

        const outcomeTargets = columns
            .filter((c) => mapping?.[c?.name]?.role === 'Outcome')
            .filter((c) => mapping?.[c?.name]?.include_comparison !== false)
            .filter((c) => c?.name && c.name !== groupName)
            .map((c) => c.name);

        const fallbackTargets = columns
            .filter((c) => mapping?.[c?.name]?.include_comparison !== false)
            .filter((c) => mapping?.[c?.name]?.role !== 'Exclude')
            .filter((c) => c?.type === 'numeric')
            .filter((c) => c?.name && c.name !== groupName)
            .map((c) => c.name);

        const targetNames = (outcomeTargets.length > 0 ? outcomeTargets : fallbackTargets).slice(0, 5);

        return {
            groupName,
            targetNames,
        };
    }, [columns, variableMapping]);

    const handleRunBatch = async (targets, group) => {
        if (!designReviewConfirmed) {
            setError('Перед запуском подтвердите Design Review');
            return;
        }
        setLoading(true);
        setError(null);
        setBatchResult(null);
        setSelectedVarDetail(null);
        setActiveGroupCol(group);

        try {
            const res = await runBatchAnalysis(id, targets, group, { designConfirmed: designReviewConfirmed });
            setBatchResult(res);
            if (res.results && targets.length > 0 && res.results[targets[0]]) {
                setSelectedVarDetail(targets[0]);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleExportDocx = async () => {
        if (!batchResult?.results) return;
        setExportingDocx(true);
        try {
            const blob = await exportDocx({
                dataset_id: id,
                dataset_name: id,
                filename: `batch_${id}.docx`,
                results: {
                    protocol_name: 'Пакетный анализ',
                    results: batchResult.results
                }
            });

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `batch_${id}.docx`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError(err?.message || 'Не удалось экспортировать DOCX');
        } finally {
            setExportingDocx(false);
        }
    };

    const handleExportPdf = async () => {
        if (!batchResult?.results) return;
        setExportingPdf(true);
        try {
            const selected = selectedVarDetail && batchResult.results[selectedVarDetail]
                ? { key: selectedVarDetail, result: batchResult.results[selectedVarDetail] }
                : null;

            const payload = selected
                ? {
                    dataset_id: id,
                    variables: { target: selected.key, group: activeGroupCol || 'Group' },
                    results: {
                        p_value: selected.result.p_value ?? 0,
                        stat_value: selected.result.stat_value ?? 0,
                        significant: selected.result.significant ?? false,
                        method: selected.result.method?.name || 'Статистический тест',
                        conclusion: selected.result.conclusion || '',
                        groups: Array.isArray(selected.result.groups) ? selected.result.groups : [],
                        plot_stats: selected.result.plot_stats && typeof selected.result.plot_stats === 'object' ? selected.result.plot_stats : {},
                        comparisons: Array.isArray(selected.result.comparisons)
                            ? selected.result.comparisons
                            : (Array.isArray(selected.result.pairwise_comparisons) ? selected.result.pairwise_comparisons : [])
                    }
                }
                : {
                    dataset_id: id,
                    variables: { target: 'Несколько', group: activeGroupCol || 'Group' },
                    results: {
                        protocol_name: 'Пакетный анализ',
                        results: batchResult.results,
                        descriptives: Array.isArray(batchResult.descriptives) ? batchResult.descriptives : []
                    }
                };

            const blob = await exportReport(payload);
            const safeTarget = selected ? selected.key : 'batch';
            downloadBlob(blob, `${safeTarget}_${id}.pdf`);
        } catch (err) {
            setError(err?.message || 'Не удалось экспортировать PDF');
        } finally {
            setExportingPdf(false);
        }
    };

    const renderDescriptives = () => {
        if (!batchResult?.descriptives) return null;
        const fmt = (v, digits = 2) => (typeof v === 'number' ? v.toFixed(digits) : na);
        return (
            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th>{t('variable')}</th>
                            <th>{t('group')}</th>
                            <th style={{ textAlign: 'right' }}>{t('n')}</th>
                            <th style={{ textAlign: 'right' }}>{t('missing')}</th>
                            <th style={{ textAlign: 'right' }}>{t('mean')}</th>
                            <th style={{ textAlign: 'right' }}>{t('sd')}</th>
                            <th style={{ textAlign: 'right' }}>{t('se')}</th>
                            <th style={{ textAlign: 'right' }}>{t('median')}</th>
                            <th style={{ textAlign: 'right' }}>{t('mode')}</th>
                            <th style={{ textAlign: 'right' }}>{t('iqr')}</th>
                            <th style={{ textAlign: 'right' }}>{t('skew')}</th>
                            <th style={{ textAlign: 'right' }}>{t('kurt')}</th>
                            <th style={{ textAlign: 'right' }}>{t('norm_p')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {batchResult.descriptives.map((row, idx) => (
                            <tr key={idx}>
                                <td style={{ fontWeight: '500' }}>{row.variable}</td>
                                <td>{row.group}</td>
                                <td style={{ textAlign: 'right' }}>{typeof row.count === 'number' ? row.count : na}</td>
                                <td style={{ textAlign: 'right' }}>{typeof row.missing === 'number' ? row.missing : na}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.mean)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.sd)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.se)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.median)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.mode)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.iqr)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.skewness, 3)}</td>
                                <td style={{ textAlign: 'right' }}>{fmt(row.kurtosis, 3)}</td>
                                <td style={{
                                    textAlign: 'right',
                                    color: !row.is_normal ? 'var(--error)' : 'var(--text-muted)'
                                }}>
                                    {typeof row.shapiro_p === 'number' ? row.shapiro_p.toFixed(3) : na}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    const renderResultsTable = () => {
        if (!batchResult?.results) return null;

        const normalizeEffectType = (name) => {
            if (!name) return 'cohens_d';
            const normalized = String(name).toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
            if (['cohen_d', 'cohens_d', 'hedges_g', 'glass_delta', 'd'].includes(normalized)) return 'cohens_d';
            if (['eta2', 'eta_sq', 'eta_squared', 'epsilon_squared', 'eps_sq'].includes(normalized)) return 'eta_squared';
            if (['partial_eta2', 'partial_eta_squared', 'np2'].includes(normalized)) return 'partial_eta_squared';
            if (['r', 'pearson', 'spearman'].includes(normalized)) return 'r';
            if (['rbc', 'rank_biserial', 'rank_biserial_correlation'].includes(normalized)) return 'rank_biserial';
            if (['cramers_v', 'cramer_v'].includes(normalized)) return 'cramers_v';
            if (['odds_ratio', 'or'].includes(normalized)) return 'odds_ratio';
            return normalized;
        };

        const renderEffect = (res) => {
            if (typeof res?.effect_size !== 'number') return na;
            const type = normalizeEffectType(res?.effect_size_name);
            return <EffectSizeExplainer type={type} value={res.effect_size} compact />;
        };

        const interpretationToneMap = {
            yellow: {
                background: 'rgba(250, 204, 21, 0.14)',
                color: '#a16207',
                border: 'rgba(250, 204, 21, 0.5)'
            },
            orange: {
                background: 'rgba(251, 146, 60, 0.14)',
                color: '#c2410c',
                border: 'rgba(251, 146, 60, 0.5)'
            },
            green: {
                background: 'rgba(34, 197, 94, 0.14)',
                color: '#166534',
                border: 'rgba(34, 197, 94, 0.5)'
            }
        };

        const getInterpretationTone = (key) => {
            if (key === 'large' || key === 'strong') return 'green';
            if (key === 'medium' || key === 'moderate') return 'orange';
            return 'yellow';
        };

        const renderInterpretation = (res) => {
            if (typeof res?.effect_size !== 'number') return na;
            const type = normalizeEffectType(res?.effect_size_name);
            const interpretation = getEffectSizeInterpretation(type, res.effect_size);
            if (!interpretation?.label) return na;
            const tone = interpretationToneMap[getInterpretationTone(interpretation.key)] || interpretationToneMap.yellow;

            return (
                <span
                    style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '4px 10px',
                        borderRadius: '2px',
                        fontSize: '10px',
                        fontWeight: '600',
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                        background: tone.background,
                        color: tone.color,
                        border: `1px solid ${tone.border}`
                    }}
                >
                    {interpretation.label}
                </span>
            );
        };

        return (
            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th>{t('variable')}</th>
                            <th>{t('method')}</th>
                            <th style={{ textAlign: 'right' }}>{t('statistic')}</th>
                            <th style={{ textAlign: 'right' }}>{t('p_value')}</th>
                            <th style={{ textAlign: 'right' }}>{t('effect_size')}</th>
                            <th style={{ textAlign: 'center' }}>
                                <StatTooltip term="effect_size" level="junior" position="top">
                                    <span>{t('interpretation')}</span>
                                </StatTooltip>
                            </th>
                            <th style={{ textAlign: 'center', width: '80px' }}>{t('sig')}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {Object.entries(batchResult.results).map(([varName, res]) => (
                            <tr
                                key={varName}
                                onClick={() => setSelectedVarDetail(varName)}
                                style={{
                                    cursor: 'pointer',
                                    background: selectedVarDetail === varName ? 'rgba(249,115,22,0.1)' : undefined
                                }}
                            >
                                <td style={{ fontWeight: '500' }}>{varName}</td>
                                <td style={{ color: 'var(--text-secondary)' }}>{res.method?.name}</td>
                                <td style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                                    {typeof res.stat_value === 'number' ? res.stat_value.toFixed(2) : na}
                                </td>
                                <td style={{
                                    textAlign: 'right',
                                    fontFamily: 'monospace',
                                    fontWeight: res.significant ? '600' : '400',
                                    color: res.significant ? 'var(--accent)' : 'var(--text-muted)'
                                }}>
                                    {typeof res.p_value === 'number'
                                        ? (res.p_value < 0.001 ? '<.001' : res.p_value.toFixed(3))
                                        : na
                                    }
                                </td>
                                <td style={{ textAlign: 'right', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                                    {renderEffect(res)}
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    {renderInterpretation(res)}
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    {res.significant ? (
                                        <span style={{ color: 'var(--success)', fontWeight: '600' }}>{t('yes')}</span>
                                    ) : (
                                        <span style={{ color: 'var(--text-muted)' }}>{t('no')}</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    const renderDetailPlot = (detail) => {
        const methodId = detail?.method?.id || detail?.type || detail?.method;

        if (methodId === 'mixed_effects') {
            return (
                <Suspense fallback={chartFallback}>
                    <InteractionPlot data={detail} width={760} height={380} />
                </Suspense>
            );
        }

        if (methodId === 'clustered_correlation') {
            return (
                <Suspense fallback={chartFallback}>
                    <ClusteredHeatmap data={detail} width={760} height={560} />
                </Suspense>
            );
        }

        if (detail?.plot_data) {
            const comparisons = detail?.comparisons || detail?.pairwise_comparisons || detail?.plot_comparisons;
            return (
                <Suspense fallback={chartFallback}>
                    <VisualizePlot
                        data={detail.plot_data}
                        stats={detail.plot_stats}
                        groups={detail.groups}
                        comparisons={comparisons}
                    />
                </Suspense>
            );
        }

        return null;
    };

    const renderDetailStats = (detail) => {
        if (!detail) return null;
        const fmtNum = (v, digits = 3) => (typeof v === 'number' ? v.toFixed(digits) : na);
        const fmtP = (v) => (typeof v === 'number' ? (v < 0.001 ? '<.001' : v.toFixed(3)) : na);
        const fmtEffectName = (name) => (typeof name === 'string' && name ? name : na);
        const ci =
            typeof detail.effect_size_ci_lower === 'number' && typeof detail.effect_size_ci_upper === 'number'
                ? `[${detail.effect_size_ci_lower.toFixed(2)}, ${detail.effect_size_ci_upper.toFixed(2)}]`
                : na;
        const bf10 = typeof detail.bf10 === 'number' ? (Number.isFinite(detail.bf10) ? detail.bf10.toPrecision(3) : String(detail.bf10)) : na;
        const power = typeof detail.power === 'number' ? detail.power.toFixed(2) : na;

        return (
            <div style={{
                background: 'var(--bg-tertiary)',
                borderRadius: '2px',
                padding: '14px 16px',
                border: '1px solid var(--border-color)',
                marginBottom: '12px'
            }}>
                <div style={{
                    fontSize: '11px',
                    fontWeight: '600',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text-muted)',
                    marginBottom: '10px'
                }}>
                    {t('results')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', rowGap: '8px', columnGap: '12px', fontSize: '13px' }}>
                    <div style={{ color: 'var(--text-muted)' }}>{t('p_value')}</div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{fmtP(detail.p_value)}</div>

                    <div style={{ color: 'var(--text-muted)' }}>{t('statistic')}</div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{fmtNum(detail.stat_value, 2)}</div>

                    <div style={{ color: 'var(--text-muted)' }}>{t('effect_size')}</div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                        {fmtEffectName(detail.effect_size_name)} {fmtNum(detail.effect_size, 2)}
                    </div>

                    <div style={{ color: 'var(--text-muted)' }}>{t('confidence_interval')}</div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{ci}</div>

                    <div style={{ color: 'var(--text-muted)' }}>{t('power')}</div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{power}</div>

                    <div style={{ color: 'var(--text-muted)' }}>{t('bf10')}</div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>{bf10}</div>
                </div>
            </div>
        );
    };

    const hasColumns = Array.isArray(columns) && columns.length > 0;
    const canConfigure = hasColumns && variableMapping !== null;
    const resultKeys = useMemo(() => batchResult?.results ? Object.keys(batchResult.results) : [], [batchResult?.results]);

    useEffect(() => {
        if (!batchResult?.results) return;
        if (selectedVarDetail && batchResult.results[selectedVarDetail]) return;
        const first = Object.keys(batchResult.results)[0];
        if (first) setSelectedVarDetail(first);
    }, [batchResult, selectedVarDetail]);

    const title = mode === 'results'
        ? t('results')
        : mode === 'graphs'
            ? t('plot')
            : t('report');

    const selectedDetail = selectedVarDetail && batchResult?.results?.[selectedVarDetail]
        ? batchResult.results[selectedVarDetail]
        : null;

    const selectionLabel = selectedVarDetail
        ? String(selectedVarDetail)
        : (resultKeys[0] || '');

    return (
        <div className="-mx-6 -my-6 min-h-[calc(100vh-56px)] bg-[color:var(--bg-secondary)] animate-fadeIn">
            <VariableSelectorModal
                isOpen={isConfigOpen}
                onClose={() => setIsConfigOpen(false)}
                title={t('analysis')}
            >
                {canConfigure ? (
                    <VariableSelector
                        allColumns={columns}
                        initialGroupName={suggestedDefaults.groupName}
                        initialTargetNames={suggestedDefaults.targetNames}
                        onRun={(targets, group) => {
                            setIsConfigOpen(false);
                            handleRunBatch(targets, group);
                        }}
                        loading={loading}
                    />
                ) : (
                    <div className="h-full flex items-center justify-center text-[color:var(--text-muted)] text-sm">{t('loading')}</div>
                )}
            </VariableSelectorModal>

            <div className="bg-[color:var(--white)] border-b border-[color:var(--border-color)] px-6 py-5">
                <div className="max-w-7xl mx-auto">
                    <div className="flex items-center justify-between gap-4">
                        <div className="min-w-0 flex items-center gap-3">
                            <button
                                type="button"
                                onClick={() => navigate(`${designBasePath}/${id}`, { state: location.state })}
                                className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-xs font-semibold text-[color:var(--text-secondary)] hover:border-black hover:text-black active:scale-[0.98]"
                            >
                                ← {t('back')}
                            </button>
                            <div className="min-w-0">
                                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('analysis')}</div>
                                <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">{title}</div>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setIsConfigOpen(true)}
                                disabled={!hasColumns}
                                className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Выбор переменных
                            </button>

                            {mode === 'report' && batchResult ? (
                                <>
                                    <button
                                        onClick={handleExportPdf}
                                        className="btn-primary"
                                        disabled={exportingPdf}
                                        style={{ fontSize: '12px', padding: '8px 16px' }}
                                    >
                                        {t('export_pdf')}
                                    </button>
                                    <button
                                        onClick={handleExportDocx}
                                        className="btn-secondary"
                                        disabled={exportingDocx}
                                        style={{ fontSize: '12px', padding: '8px 16px' }}
                                    >
                                        {t('export_docx')}
                                    </button>
                                </>
                            ) : null}
                        </div>
                    </div>

                    <ResearchFlowNav
                        active={activeStep}
                        datasetId={id}
                        className="mt-4"
                        showMenu={false}
                        stepData={flowStepData}
                        designBasePath={designBasePath}
                    />

                    <div className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] px-4 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Design Review</div>
                                <div className={`mt-1 text-xs font-semibold ${designReviewConfirmed ? 'text-[color:var(--success)]' : 'text-[color:var(--error)]'}`}>
                                    {designReviewLoading
                                        ? t('loading')
                                        : (designReviewConfirmed ? 'Подтверждено в backend-артефакте' : 'Не подтверждено')}
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <label className="inline-flex items-center gap-2 text-xs text-[color:var(--text-secondary)] cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={Boolean(designReviewConfirmed)}
                                        disabled={designReviewLoading || designReviewUpdating}
                                        onChange={(e) => toggleDesignReview(Boolean(e.target.checked))}
                                    />
                                    Подтверждаю Design Review
                                </label>
                                <button
                                    type="button"
                                    onClick={() => navigate(`${designBasePath}/${id}`, { state: location.state })}
                                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-secondary)] hover:border-black hover:text-black"
                                >
                                    Открыть Design Review
                                </button>
                            </div>
                        </div>
                        {designReviewError ? (
                            <div className="mt-2 text-xs text-[color:var(--error)]">{designReviewError}</div>
                        ) : null}
                    </div>

                    {mode !== 'results' ? (
                        <div className="mt-4 grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
                            <div>
                                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Переменная</div>
                                <div className="mt-1">
                                    <SearchableSelect
                                        value={selectionLabel}
                                        onChange={(next) => setSelectedVarDetail(next)}
                                        options={resultKeys}
                                        placeholder="Выберите переменную"
                                        disabled={!batchResult || resultKeys.length === 0}
                                        countLabel="переменных"
                                    />
                                </div>
                            </div>
                            <div className="flex items-center gap-2 justify-end">
                                <button
                                    type="button"
                                    onClick={() => navigate(`/results/${id}`, { state: location.state })}
                                    className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                                >
                                    {t('results')}
                                </button>
                            </div>
                        </div>
                    ) : null}
                </div>
            </div>

            <main className="px-6 py-6">
                <div className="max-w-7xl mx-auto">
                    {/* Error */}
                    {error && (
                        <div className="bg-error" style={{
                            padding: '12px 16px',
                            borderRadius: '2px',
                            marginBottom: '24px',
                            fontSize: '14px'
                        }}>
                            <strong>{t('error')}:</strong> {error}
                        </div>
                    )}

                    {!batchResult && !loading ? (
                        <div className="rounded-[2px] border border-dashed border-[color:var(--border-color)] bg-[color:var(--white)] p-10 text-center">
                            <div className="text-sm text-[color:var(--text-secondary)]">{t('select_variables_to_begin')}</div>
                            <div className="mt-5 flex items-center justify-center">
                                <button
                                    type="button"
                                    onClick={() => setIsConfigOpen(true)}
                                    disabled={!hasColumns}
                                    className="h-10 px-6 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    Выбрать переменные
                                </button>
                            </div>
                        </div>
                    ) : null}

                    {loading ? (
                        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-10 flex flex-col items-center justify-center text-[color:var(--text-muted)]">
                            <div style={{
                                width: '32px',
                                height: '32px',
                                border: '3px solid var(--border-color)',
                                borderTopColor: 'var(--accent)',
                                borderRadius: '50%',
                                animation: 'spin 1s linear infinite',
                                marginBottom: '12px'
                            }} />
                            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                            <span style={{ fontSize: '14px' }}>{t('processing_data')}</span>
                        </div>
                    ) : null}

                    {batchResult ? (
                        <div className="animate-slideUp">
                            {(mode === 'results' || mode === 'report') ? (
                                <>
                                    <section className="card" style={{ marginBottom: '24px', padding: '20px' }}>
                                        <h3 style={{
                                            fontSize: '12px',
                                            fontWeight: '600',
                                            textTransform: 'uppercase',
                                            letterSpacing: '0.05em',
                                            color: 'var(--text-muted)',
                                            marginBottom: '16px'
                                        }}>
                                            {t('descriptive_statistics')}
                                        </h3>
                                        {renderDescriptives()}
                                    </section>

                                    <section className="card" style={{ marginBottom: '24px', padding: '20px' }}>
                                        <h3 style={{
                                            fontSize: '12px',
                                            fontWeight: '600',
                                            textTransform: 'uppercase',
                                            letterSpacing: '0.05em',
                                            color: 'var(--text-muted)',
                                            marginBottom: '16px'
                                        }}>
                                            {t('hypothesis_tests')}
                                        </h3>
                                        {renderResultsTable()}
                                    </section>
                                </>
                            ) : null}

                            {mode === 'graphs' ? (
                                <section className="card" style={{ padding: '20px' }}>
                                    {!selectedDetail ? (
                                        <div className="text-sm text-[color:var(--text-secondary)]">{t('select_variables_to_begin')}</div>
                                    ) : (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                                            <div>
                                                {renderDetailStats(selectedDetail)}
                                                <h4 style={{
                                                    fontSize: '11px',
                                                    fontWeight: '600',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.05em',
                                                    color: 'var(--accent)',
                                                    marginBottom: '12px'
                                                }}>
                                                    {t('ai_interpretation')}
                                                </h4>
                                                <p style={{
                                                    fontSize: '13px',
                                                    lineHeight: '1.6',
                                                    color: 'var(--text-secondary)',
                                                    fontFamily: 'monospace',
                                                    whiteSpace: 'pre-line',
                                                    background: 'var(--bg-tertiary)',
                                                    padding: '16px',
                                                    borderRadius: '2px'
                                                }}>
                                                    {selectedDetail.conclusion || t('no_interpretation_available')}
                                                </p>
                                            </div>

                                            <div style={{
                                                border: '1px solid var(--border-color)',
                                                borderRadius: '2px',
                                                padding: '16px',
                                                minHeight: '300px'
                                            }}>
                                                <h4 style={{
                                                    fontSize: '11px',
                                                    fontWeight: '600',
                                                    textTransform: 'uppercase',
                                                    letterSpacing: '0.05em',
                                                    color: 'var(--text-muted)',
                                                    marginBottom: '12px',
                                                    textAlign: 'center'
                                                }}>
                                                    {t('distribution_plot')}
                                                </h4>
                                                {(() => {
                                                    const plot = renderDetailPlot(selectedDetail);
                                                    if (plot) return plot;

                                                    return (
                                                        <div style={{
                                                            height: '200px',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            color: 'var(--text-muted)',
                                                            fontSize: '12px'
                                                        }}>
                                                            {t('no_plot_data')}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        </div>
                                    )}
                                </section>
                            ) : null}

                            {mode === 'report' ? (
                                <section className="card" style={{ marginTop: '24px', padding: '20px' }}>
                                    <h3 style={{
                                        fontSize: '12px',
                                        fontWeight: '600',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.05em',
                                        color: 'var(--text-muted)',
                                        marginBottom: '16px'
                                    }}>
                                        {t('ai_interpretation')}
                                    </h3>
                                    <div style={{ display: 'grid', gap: '12px' }}>
                                        {Object.entries(batchResult.results).map(([varName, res]) => (
                                            <button
                                                key={varName}
                                                type="button"
                                                onClick={() => setSelectedVarDetail(varName)}
                                                className="card"
                                                style={{
                                                    textAlign: 'left',
                                                    padding: '16px',
                                                    border: selectedVarDetail === varName ? '1px solid var(--accent)' : '1px solid var(--border-color)',
                                                    background: 'var(--bg-secondary)'
                                                }}
                                            >
                                                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px' }}>
                                                    <div style={{ fontSize: '14px', fontWeight: '650', color: 'var(--text-primary)' }}>{varName}</div>
                                                    <div style={{
                                                        fontSize: '11px',
                                                        fontWeight: '650',
                                                        letterSpacing: '0.08em',
                                                        textTransform: 'uppercase',
                                                        color: res?.significant ? 'var(--accent)' : 'var(--text-muted)'
                                                    }}>
                                                        p {typeof res?.p_value === 'number' ? (res.p_value < 0.001 ? '<.001' : res.p_value.toFixed(3)) : na}
                                                    </div>
                                                </div>
                                                <div style={{
                                                    marginTop: '10px',
                                                    fontFamily: 'monospace',
                                                    fontSize: '13px',
                                                    lineHeight: 1.6,
                                                    color: 'var(--text-secondary)',
                                                    whiteSpace: 'pre-line',
                                                    background: 'var(--bg-tertiary)',
                                                    border: '1px solid var(--border-color)',
                                                    borderRadius: '2px',
                                                    padding: '12px 14px'
                                                }}>
                                                    {res?.conclusion || t('no_interpretation_available')}
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                </section>
                            ) : null}
                        </div>
                    ) : null}
                </div>
            </main>
        </div>
    );
}
