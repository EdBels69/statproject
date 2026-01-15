import { useEffect, useMemo, useState, lazy, Suspense } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { runBatchAnalysis, getDataset, getVariableMapping, exportDocx, exportReport } from '../../lib/api';
import VariableSelector from '../components/VariableSelector';
import ResearchFlowNav from '../components/ResearchFlowNav';
import { useTranslation } from '../../hooks/useTranslation';

const VisualizePlot = lazy(() => import('../components/VisualizePlot'));
const ClusteredHeatmap = lazy(() => import('../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../components/InteractionPlot'));

export default function Analyze() {
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

    const activeStep = location.pathname.startsWith('/report') ? 'report' : 'analyze';

    const chartFallback = useMemo(() => (
        <div style={{
            height: 360,
            borderRadius: '2px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-tertiary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            fontSize: '12px'
        }} className="animate-pulse">
            {t('loading')}
        </div>
    ), [t]);

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
        setLoading(true);
        setError(null);
        setBatchResult(null);
        setSelectedVarDetail(null);
        setActiveGroupCol(group);

        try {
            const res = await runBatchAnalysis(id, targets, group);
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
                dataset_name: id,
                filename: `batch_${id}.docx`,
                results: {
                    protocol_name: 'Batch analysis',
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
            setError(err?.message || 'Failed to export DOCX');
        } finally {
            setExportingDocx(false);
        }
    };

    const downloadBlob = (blob, filename) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
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
                        method: selected.result.method?.name || 'Statistical Test',
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
                    variables: { target: 'Multiple', group: activeGroupCol || 'Group' },
                    results: {
                        protocol_name: 'Batch analysis',
                        results: batchResult.results,
                        descriptives: Array.isArray(batchResult.descriptives) ? batchResult.descriptives : []
                    }
                };

            const blob = await exportReport(payload);
            const safeTarget = selected ? selected.key : 'batch';
            downloadBlob(blob, `${safeTarget}_${id}.pdf`);
        } catch (err) {
            setError(err?.message || 'Failed to export PDF');
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

        const fmtEffect = (res) => {
            if (typeof res?.effect_size !== 'number') return na;
            const name = typeof res?.effect_size_name === 'string' ? res.effect_size_name : '';
            const val = res.effect_size.toFixed(2);
            return name ? `${name}: ${val}` : val;
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
                                    {fmtEffect(res)}
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

    return (
        <div style={{ display: 'flex', height: 'calc(100vh - 120px)' }} className="animate-fadeIn">
            {/* Sidebar */}
            <aside style={{
                width: '300px',
                flexShrink: 0,
                borderRight: '1px solid var(--border-color)',
                background: 'var(--bg-secondary)',
                overflowY: 'auto',
                padding: '16px'
            }}>
                {Array.isArray(columns) && columns.length > 0 && variableMapping !== null ? (
                    <VariableSelector
                        allColumns={columns}
                        initialGroupName={suggestedDefaults.groupName}
                        initialTargetNames={suggestedDefaults.targetNames}
                        onRun={handleRunBatch}
                        loading={loading}
                    />
                ) : (
                    <div style={{
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-muted)',
                        fontSize: '12px',
                        padding: '24px',
                        textAlign: 'center'
                    }}>
                        {t('loading')}
                    </div>
                )}
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
                <ResearchFlowNav active={activeStep} datasetId={id} className="mb-6" />
                {/* Header */}
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '24px',
                    paddingBottom: '16px',
                    borderBottom: '1px solid var(--border-color)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <button
                            onClick={() => navigate(`/profile/${id}`)}
                            className="btn-secondary"
                            style={{ padding: '6px 12px', fontSize: '12px' }}
                        >
                            ← {t('back')}
                        </button>
                        <h1 style={{
                            fontSize: '18px',
                            fontWeight: '600',
                            color: 'var(--text-primary)'
                        }}>
                            {t('analysis_results')}
                        </h1>
                    </div>
                    {batchResult && (
                        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
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
                        </div>
                    )}
                </div>

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

                {/* Empty State */}
                {!batchResult && !loading && (
                    <div style={{
                        height: '300px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '2px dashed var(--border-color)',
                        borderRadius: '2px',
                        color: 'var(--text-muted)',
                        fontSize: '14px'
                    }}>
                        {t('select_variables_to_begin')}
                    </div>
                )}

                {/* Loading */}
                {loading && (
                    <div style={{
                        height: '300px',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--text-muted)'
                    }}>
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
                )}

                {/* Results */}
                {batchResult && (
                    <div className="animate-slideUp">
                        {/* Descriptives */}
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

                        {/* Hypothesis Tests */}
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

                        {/* Detail View */}
                        {selectedVarDetail && batchResult.results[selectedVarDetail] && (
                            <section className="card" style={{ padding: '20px' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                                    {/* AI Insight */}
                                    <div>
                                        {renderDetailStats(batchResult.results[selectedVarDetail])}
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
                                            {batchResult.results[selectedVarDetail].conclusion || t('no_interpretation_available')}
                                        </p>
                                    </div>

                                    {/* Plot */}
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
                                            const plot = renderDetailPlot(batchResult.results[selectedVarDetail]);
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
                            </section>
                        )}

                        {activeStep === 'report' && (
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
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
