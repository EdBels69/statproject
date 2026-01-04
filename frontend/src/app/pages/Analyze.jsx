import { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { runBatchAnalysis, getPDFExportUrl, getDataset } from '../../lib/api';
import VariableSelector from '../components/VariableSelector';
import VisualizePlot from '../components/VisualizePlot';

export default function Analyze() {
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [columns, setColumns] = useState([]);

    const [loading, setLoading] = useState(false);
    const [batchResult, setBatchResult] = useState(null);
    const [error, setError] = useState(null);
    const [selectedVarDetail, setSelectedVarDetail] = useState(null);
    const [activeGroupCol, setActiveGroupCol] = useState(null);

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

    const renderDescriptives = () => {
        if (!batchResult?.descriptives) return null;
        return (
            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th>Variable</th>
                            <th>Group</th>
                            <th style={{ textAlign: 'right' }}>N</th>
                            <th style={{ textAlign: 'right' }}>Mean</th>
                            <th style={{ textAlign: 'right' }}>SD</th>
                            <th style={{ textAlign: 'right' }}>Median</th>
                            <th style={{ textAlign: 'right' }}>Norm (P)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {batchResult.descriptives.map((row, idx) => (
                            <tr key={idx}>
                                <td style={{ fontWeight: '500' }}>{row.variable}</td>
                                <td>{row.group}</td>
                                <td style={{ textAlign: 'right' }}>{row.count}</td>
                                <td style={{ textAlign: 'right' }}>{row.mean?.toFixed(2)}</td>
                                <td style={{ textAlign: 'right' }}>{row.sd?.toFixed(2)}</td>
                                <td style={{ textAlign: 'right' }}>{row.median?.toFixed(2)}</td>
                                <td style={{
                                    textAlign: 'right',
                                    color: !row.is_normal ? 'var(--error)' : 'var(--text-muted)'
                                }}>
                                    {row.shapiro_p ? row.shapiro_p.toFixed(3) : '-'}
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
        return (
            <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: '13px' }}>
                    <thead>
                        <tr>
                            <th>Variable</th>
                            <th>Method</th>
                            <th style={{ textAlign: 'right' }}>Statistic</th>
                            <th style={{ textAlign: 'right' }}>P-Value</th>
                            <th style={{ textAlign: 'center', width: '80px' }}>Sig.</th>
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
                                    {res.stat_value?.toFixed(2)}
                                </td>
                                <td style={{
                                    textAlign: 'right',
                                    fontFamily: 'monospace',
                                    fontWeight: res.significant ? '600' : '400',
                                    color: res.significant ? 'var(--accent)' : 'var(--text-muted)'
                                }}>
                                    {res.p_value < 0.001 ? '<.001' : res.p_value?.toFixed(3)}
                                </td>
                                <td style={{ textAlign: 'center' }}>
                                    {res.significant ? (
                                        <span style={{ color: 'var(--success)', fontWeight: '600' }}>YES</span>
                                    ) : (
                                        <span style={{ color: 'var(--text-muted)' }}>NO</span>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
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
                <VariableSelector
                    allColumns={columns}
                    onRun={handleRunBatch}
                    loading={loading}
                />
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
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
                            ← Back
                        </button>
                        <h1 style={{
                            fontSize: '18px',
                            fontWeight: '600',
                            color: 'var(--text-primary)'
                        }}>
                            Analysis Results
                        </h1>
                    </div>
                    {batchResult && (
                        <a
                            href={getPDFExportUrl(id, selectedVarDetail || 'Multiple', activeGroupCol || 'Group')}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-primary"
                            style={{ fontSize: '12px', padding: '8px 16px', textDecoration: 'none', display: 'inline-block' }}
                        >
                            Export PDF
                        </a>
                    )}
                </div>

                {/* Error */}
                {error && (
                    <div className="bg-error" style={{
                        padding: '12px 16px',
                        borderRadius: '8px',
                        marginBottom: '24px',
                        fontSize: '14px'
                    }}>
                        <strong>Error:</strong> {error}
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
                        borderRadius: '8px',
                        color: 'var(--text-muted)',
                        fontSize: '14px'
                    }}>
                        Select variables from the left panel to begin analysis
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
                        <span style={{ fontSize: '14px' }}>Processing data...</span>
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
                                Descriptive Statistics
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
                                Hypothesis Tests
                            </h3>
                            {renderResultsTable()}
                        </section>

                        {/* Detail View */}
                        {selectedVarDetail && batchResult.results[selectedVarDetail] && (
                            <section className="card" style={{ padding: '20px' }}>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
                                    {/* AI Insight */}
                                    <div>
                                        <h4 style={{
                                            fontSize: '11px',
                                            fontWeight: '600',
                                            textTransform: 'uppercase',
                                            letterSpacing: '0.05em',
                                            color: 'var(--accent)',
                                            marginBottom: '12px'
                                        }}>
                                            AI Interpretation
                                        </h4>
                                        <p style={{
                                            fontSize: '13px',
                                            lineHeight: '1.6',
                                            color: 'var(--text-secondary)',
                                            fontFamily: 'monospace',
                                            whiteSpace: 'pre-line',
                                            background: 'var(--bg-tertiary)',
                                            padding: '16px',
                                            borderRadius: '6px'
                                        }}>
                                            {batchResult.results[selectedVarDetail].conclusion || 'No interpretation available.'}
                                        </p>
                                    </div>

                                    {/* Plot */}
                                    <div style={{
                                        border: '1px solid var(--border-color)',
                                        borderRadius: '6px',
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
                                            Distribution Plot
                                        </h4>
                                        {batchResult.results[selectedVarDetail].plot_data ? (
                                            <VisualizePlot
                                                data={batchResult.results[selectedVarDetail].plot_data}
                                                stats={batchResult.results[selectedVarDetail].plot_stats}
                                                groups={batchResult.results[selectedVarDetail].groups}
                                            />
                                        ) : (
                                            <div style={{
                                                height: '200px',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                color: 'var(--text-muted)',
                                                fontSize: '12px'
                                            }}>
                                                No plot data
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </section>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}
