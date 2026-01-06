import { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { runBatchAnalysis, getPDFExportUrl, getDataset, runCorrelationMatrix } from '../../lib/api';
import VariableSelector from '../components/VariableSelector';
import VisualizePlot from '../components/VisualizePlot';

export default function Analyze() {
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [columns, setColumns] = useState([]);

    // UI State
    const [loading, setLoading] = useState(false);
    const [analysisMode, setAnalysisMode] = useState('batch'); // 'batch', 'matrix'
    const [batchResult, setBatchResult] = useState(null);
    const [matrixResult, setMatrixResult] = useState(null);
    const [error, setError] = useState(null);
    const [selectedVarDetail, setSelectedVarDetail] = useState(null);
    const [activeGroupCol, setActiveGroupCol] = useState(null);
    const [showStats, setShowStats] = useState(false);

    // Analysis Options
    const [showSettings, setShowSettings] = useState(false);
    const [analysisOptions, setAnalysisOptions] = useState({
        correction: "none", // none, bonferroni, fdr_bh
        conf_level: 0.95,
        method: "pearson",
        cluster_variables: false
    });
    const [plotType, setPlotType] = useState('dist'); // 'dist' or 'qq' 

    // Report Preview State
    const [showReportPreview, setShowReportPreview] = useState(false);
    const [reportHtml, setReportHtml] = useState(null);
    const [generatingReport, setGeneratingReport] = useState(false);

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
        setPlotType('dist'); // Reset plot type

        try {
            const res = await runBatchAnalysis(id, targets, group, analysisOptions);
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

    const handleRunMatrix = async (features) => {
        setLoading(true);
        setError(null);
        setMatrixResult(null);

        try {
            const res = await runCorrelationMatrix(
                id,
                features,
                analysisOptions.method || "pearson",
                analysisOptions.cluster_variables || false
            );
            setMatrixResult(res);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleViewReport = async () => {
        setGeneratingReport(true);
        try {
            const { getReportHtmlPreview } = await import('../../lib/api');
            const html = await getReportHtmlPreview(id, batchResult, selectedVarDetail);
            setReportHtml(html);
            setShowReportPreview(true);
        } catch (e) {
            setError("Failed to generate report preview: " + e.message);
        } finally {
            setGeneratingReport(false);
        }
    };

    // Helper to format "Mean ± SD"
    const fmtStat = (d) => {
        if (!d) return '-';
        return `${d.mean?.toFixed(2)} ± ${d.sd?.toFixed(2)}`;
    };

    const renderUnifiedTable = () => {
        if (!batchResult?.descriptives) return null;
        const groups = [...new Set(batchResult.descriptives.map(d => d.group))].sort();
        const dataMap = {};
        batchResult.descriptives.forEach(d => {
            if (!dataMap[d.variable]) dataMap[d.variable] = { groups: {}, result: null };
            dataMap[d.variable].groups[d.group] = d;
        });
        if (batchResult.results) {
            Object.entries(batchResult.results).forEach(([v, res]) => {
                if (dataMap[v]) dataMap[v].result = res;
            });
        }

        return (
            <div className="overflow-x-auto border-t border-gray-200">
                <table className="w-full text-sm text-left border-collapse">
                    <thead>
                        <tr>
                            <th className="py-2">Variable</th>
                            {groups.map(g => (
                                <th key={g} className="py-2 text-right">
                                    {g} <span className="font-normal text-gray-500 text-xs">(M±SD)</span>
                                </th>
                            ))}
                            <th className="py-2 text-right">Test</th>
                            <th className="py-2 text-right">P-Value</th>
                            {analysisOptions.correction !== 'none' && (
                                <th className="py-2 text-right">Adj. P</th>
                            )}
                        </tr>
                    </thead>
                    <tbody>
                        {Object.entries(dataMap).map(([variable, data]) => {
                            const res = data.result;
                            const isSig = res?.significant;
                            const pVal = res?.p_value;
                            const adjP = res?.adjusted_p_value;
                            const isSigAdj = res?.significant_adj;
                            const isSelected = selectedVarDetail === variable;

                            return (
                                <tr
                                    key={variable}
                                    onClick={() => setSelectedVarDetail(variable)}
                                    className={`
                                        cursor-pointer transition-colors
                                        ${isSelected ? 'bg-gray-100 font-medium' : 'hover:bg-gray-50'}
                                    `}
                                >
                                    <td className="py-2 font-mono text-xs text-gray-900 border-r border-gray-100">
                                        {variable}
                                    </td>
                                    {groups.map(g => (
                                        <td key={g} className="py-2 text-right tabular-nums text-gray-700">
                                            {fmtStat(data.groups[g])}
                                        </td>
                                    ))}
                                    <td className="py-2 text-right text-xs text-gray-400">
                                        {res?.method?.name || '-'}
                                    </td>
                                    <td className={`py-2 text-right tabular-nums font-mono
                                        ${isSig ? 'text-black font-bold' : 'text-gray-500'}
                                    `}>
                                        {pVal !== undefined ? (pVal < 0.001 ? '<.001' : pVal.toFixed(3)) : '-'}
                                    </td>
                                    {analysisOptions.correction !== 'none' && (
                                        <td className={`py-2 text-right tabular-nums font-mono
                                            ${isSigAdj ? 'text-emerald-600 font-bold' : 'text-gray-400'}
                                        `}>
                                            {adjP !== undefined && adjP !== null ? (adjP < 0.001 ? '<.001' : adjP.toFixed(3)) : '-'}
                                        </td>
                                    )}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        );
    };

    return (
        <div className="flex h-[calc(100vh-60px)] animate-fadeIn font-sans relative">
            {/* Sidebar */}
            <aside className="w-[320px] shrink-0 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto">
                <VariableSelector
                    allColumns={columns}
                    mode={analysisMode}
                    onRun={analysisMode === 'matrix' ? handleRunMatrix : handleRunBatch}
                    loading={loading}
                />
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto p-6 bg-white">
                {/* Header */}
                <div className="flex items-center justify-between mb-6 pb-4 border-b border-gray-200">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => navigate(`/profile/${id}`)}
                            className="text-gray-500 hover:text-black transition-colors"
                        >
                            ← Back
                        </button>
                        <h1 className="text-lg font-semibold text-black tracking-tight border-r border-gray-300 pr-4 mr-4">
                            Analysis Results
                        </h1>

                        {/* Mode Toggle */}
                        <div className="flex bg-gray-100 rounded p-1">
                            <button
                                onClick={() => { setAnalysisMode('batch'); setMatrixResult(null); }}
                                className={`px-3 py-1 text-xs font-medium rounded transition-all ${analysisMode === 'batch' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-700'}`}
                            >
                                Target Analysis
                            </button>
                            <button
                                onClick={() => { setAnalysisMode('matrix'); setBatchResult(null); }}
                                className={`px-3 py-1 text-xs font-medium rounded transition-all ${analysisMode === 'matrix' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-700'}`}
                            >
                                Correlation Matrix
                            </button>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => setShowSettings(true)}
                            className="btn-secondary flex items-center gap-2"
                        >
                            <span>⚙️ Options</span>
                            {analysisOptions.correction !== "none" && (
                                <span className="bg-emerald-100 text-emerald-700 text-[10px] px-1.5 rounded-full">Active</span>
                            )}
                        </button>

                        {batchResult && (
                            <>
                                <button
                                    onClick={handleViewReport}
                                    disabled={generatingReport}
                                    className="btn-secondary"
                                >
                                    {generatingReport ? '...' : 'View Report'}
                                </button>

                                <a
                                    href={getPDFExportUrl(id, selectedVarDetail || 'Multiple', activeGroupCol || 'Group')}
                                    className="btn-primary no-underline"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    Export .docx
                                </a>
                            </>
                        )}
                    </div>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6 text-sm">
                        {error}
                    </div>
                )}

                {!batchResult && !loading && (
                    <div className="h-64 flex items-center justify-center border-2 border-dashed border-gray-200 rounded text-gray-400 text-sm font-mono">
                        Select variables to begin analysis
                    </div>
                )}

                {loading && (
                    <div className="h-64 flex flex-col items-center justify-center text-gray-400">
                        <div className="w-6 h-6 border-2 border-gray-200 border-t-black rounded-full animate-spin mb-3" />
                        <span className="text-xs font-mono uppercase tracking-widest">Processing...</span>
                    </div>
                )}

                {batchResult && (
                    <div className="animate-slideUp">
                        <section className="mb-8">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">Summary Table</h3>
                            {renderUnifiedTable()}
                        </section>

                        {selectedVarDetail && batchResult.results[selectedVarDetail] && (
                            <section className="grid grid-cols-[1fr_2fr] gap-8 border-t border-gray-100 pt-8">
                                <div>
                                    <h4 className="text-xs font-bold uppercase tracking-widest text-emerald-600 mb-3">
                                        Interpretation
                                    </h4>
                                    <p className="text-sm leading-relaxed text-gray-800 font-mono whitespace-pre-line bg-gray-50 p-4 border border-gray-100 rounded">
                                        {batchResult.results[selectedVarDetail].conclusion || 'No interpretation available.'}
                                    </p>
                                </div>

                                <div>
                                    <div className="flex items-center justify-between mb-3">
                                        <h4 className="text-xs font-bold uppercase tracking-widest text-gray-400">
                                            Visualization
                                        </h4>
                                        {batchResult.results[selectedVarDetail].qq_data && batchResult.results[selectedVarDetail].qq_data.length > 0 && (
                                            <div className="flex bg-gray-100 rounded p-0.5">
                                                <button
                                                    onClick={() => setPlotType('dist')}
                                                    className={`px-3 py-1 text-[10px] font-medium rounded transition-all ${plotType === 'dist' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-700'}`}
                                                >
                                                    Dist
                                                </button>
                                                <button
                                                    onClick={() => setPlotType('qq')}
                                                    className={`px-3 py-1 text-[10px] font-medium rounded transition-all ${plotType === 'qq' ? 'bg-white shadow-sm text-black' : 'text-gray-500 hover:text-gray-700'}`}
                                                >
                                                    Q-Q
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                    <div className="border border-gray-200 rounded p-4 min-h-[300px]">
                                        {batchResult.results[selectedVarDetail].plot_data ? (
                                            <VisualizePlot
                                                data={batchResult.results[selectedVarDetail].plot_data}
                                                stats={batchResult.results[selectedVarDetail].plot_stats}
                                                groups={batchResult.results[selectedVarDetail].groups}
                                                qqData={batchResult.results[selectedVarDetail].qq_data}
                                                type={plotType}
                                            />
                                        ) : (
                                            <div className="flex items-center justify-center h-48 text-gray-300 text-xs uppercase font-mono">
                                                No visualization data
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </section>
                        )}
                    </div>
                )}

                {/* Matrix Analysis Results */}
                {matrixResult && (
                    <div className="animate-slideUp">
                        {/* Heatmap Section */}
                        {matrixResult.plot_image && (
                            <section className="mb-8">
                                <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">
                                    correlation Heatmap {matrixResult.clustered ? "(Clustered)" : ""}
                                </h3>
                                <div className="border border-gray-200 rounded p-4 flex justify-center bg-white">
                                    <img
                                        src={`data:image/png;base64,${matrixResult.plot_image}`}
                                        alt="Correlation Matrix"
                                        className="max-w-full max-h-[600px] object-contain"
                                    />
                                </div>
                            </section>
                        )}

                        {/* Tables */}
                        <div className="grid grid-cols-2 gap-8">
                            {/* Coefficients */}
                            <section>
                                <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">Correlation Coefficients</h3>
                                <div className="overflow-x-auto border border-gray-200 rounded">
                                    <table className="w-full text-xs">
                                        <thead className="bg-gray-50 text-gray-500 font-medium border-b border-gray-200">
                                            <tr>
                                                <th className="p-2 text-left bg-gray-50 sticky left-0 border-r border-gray-200">Variable</th>
                                                {matrixResult.variables.map(v => (
                                                    <th key={v} className="p-2 text-center whitespace-nowrap">{v}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {matrixResult.variables.map(rowVar => (
                                                <tr key={rowVar} className="hover:bg-gray-50">
                                                    <td className="p-2 font-medium text-gray-700 bg-gray-50 sticky left-0 border-r border-gray-200">{rowVar}</td>
                                                    {matrixResult.variables.map(colVar => (
                                                        <td key={colVar} className="p-2 text-center font-mono text-gray-600">
                                                            {matrixResult.corr_matrix[colVar][rowVar]?.toFixed(3)}
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>

                            {/* P-Values */}
                            <section>
                                <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">P-Values</h3>
                                <div className="overflow-x-auto border border-gray-200 rounded">
                                    <table className="w-full text-xs">
                                        <thead className="bg-gray-50 text-gray-500 font-medium border-b border-gray-200">
                                            <tr>
                                                <th className="p-2 text-left bg-gray-50 sticky left-0 border-r border-gray-200">Variable</th>
                                                {matrixResult.variables.map(v => (
                                                    <th key={v} className="p-2 text-center whitespace-nowrap">{v}</th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-100">
                                            {matrixResult.variables.map(rowVar => (
                                                <tr key={rowVar} className="hover:bg-gray-50">
                                                    <td className="p-2 font-medium text-gray-700 bg-gray-50 sticky left-0 border-r border-gray-200">{rowVar}</td>
                                                    {matrixResult.variables.map(colVar => {
                                                        const p = matrixResult.p_values[colVar][rowVar];
                                                        const isSig = p < 0.05;
                                                        return (
                                                            <td key={colVar} className={`p-2 text-center font-mono ${isSig ? "text-emerald-600 font-bold" : "text-gray-400"}`}>
                                                                {p < 0.001 ? "<.001" : p?.toFixed(3)}
                                                            </td>
                                                        );
                                                    })}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </section>
                        </div>
                    </div>
                )}
            </main>

            {/* Settings Modal */}
            {showSettings && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-white w-[400px] rounded shadow-2xl p-6">
                        <h2 className="font-semibold text-lg mb-4">Analysis Options</h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Multiple Comparison Correction</label>
                                <select
                                    value={analysisOptions.correction}
                                    onChange={(e) => setAnalysisOptions({ ...analysisOptions, correction: e.target.value })}
                                    className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                >
                                    <option value="none">None</option>
                                    <option value="bonferroni">Bonferroni</option>
                                    <option value="sidak">Sidak</option>
                                    <option value="holm">Holm-Sidak</option>
                                    <option value="holm-sidak">Holm-Sidak (Step-down)</option>
                                    <option value="simes-hochberg">Simes-Hochberg</option>
                                    <option value="hommel">Hommel</option>
                                    <option value="fdr_bh">Benjamini-Hochberg (FDR)</option>
                                    <option value="fdr_by">Benjamini-Yekutieli (FDR)</option>
                                    <option value="fdr_tsbky">Benjamini-Krieger-Yekutieli (BKY)</option>
                                </select>
                                <p className="text-xs text-gray-500 mt-1">Adjust P-values for multiple independent tests.</p>
                            </div>

                            {/* T-Test Specific Options */}
                            <div className="border-t border-gray-100 pt-4 mt-2">
                                <h4 className="text-xs font-semibold uppercase text-gray-400 mb-3 tracking-wider">T-Test Options</h4>
                                <div className="space-y-3">
                                    {/* Alternative */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Alternative Hypothesis</label>
                                        <select
                                            value={analysisOptions.alternative || "two-sided"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, alternative: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="two-sided">Two-Sided (≠)</option>
                                            <option value="less">Less (Left-tailed)</option>
                                            <option value="greater">Greater (Right-tailed)</option>
                                        </select>
                                    </div>

                                    {/* Method Force */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Method Selection</label>
                                        <select
                                            value={analysisOptions.method_force || "auto"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, method_force: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="auto">Auto (Levene's Test Decision)</option>
                                            <option value="student">Force Student's T-Test</option>
                                            <option value="welch">Force Welch's T-Test</option>
                                        </select>
                                    </div>

                                    <div className="flex items-center space-x-4">
                                        {/* Permutation */}
                                        <div className="flex items-center">
                                            <input
                                                id="perm_chk"
                                                type="checkbox"
                                                checked={analysisOptions.use_permutation || false}
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, use_permutation: e.target.checked })}
                                                className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                            />
                                            <label htmlFor="perm_chk" className="ml-2 text-xs text-gray-700">Permutation Test (Exact P)</label>
                                        </div>

                                        {/* Bootstrap */}
                                        <div className="flex items-center">
                                            <input
                                                id="boot_chk"
                                                type="checkbox"
                                                checked={analysisOptions.use_bootstrap || false}
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, use_bootstrap: e.target.checked })}
                                                className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                            />
                                            <label htmlFor="boot_chk" className="ml-2 text-xs text-gray-700">Bootstrap CI</label>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Mann-Whitney Specific Options */}
                            <div className="border-t border-gray-100 pt-4 mt-2">
                                <h4 className="text-xs font-semibold uppercase text-gray-400 mb-3 tracking-wider">Mann-Whitney Options</h4>
                                <div className="space-y-3">
                                    {/* Alternative */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Alternative Hypothesis</label>
                                        <select
                                            value={analysisOptions.alternative || "two-sided"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, alternative: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="two-sided">Two-Sided (≠)</option>
                                            <option value="less">Less (Left-tailed)</option>
                                            <option value="greater">Greater (Right-tailed)</option>
                                        </select>
                                    </div>

                                    <div className="flex items-center space-x-4">
                                        {/* Exact Method */}
                                        <div className="flex items-center">
                                            <input
                                                id="mw_exact"
                                                type="checkbox"
                                                checked={analysisOptions.method_exact || false}
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, method_exact: e.target.checked })}
                                                className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                            />
                                            <label htmlFor="mw_exact" className="ml-2 text-xs text-gray-700">Exact P-Value (Small N)</label>
                                        </div>

                                        {/* Continuity */}
                                        <div className="flex items-center">
                                            <input
                                                id="mw_cont"
                                                type="checkbox"
                                                checked={analysisOptions.use_continuity !== false} // Default true
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, use_continuity: e.target.checked })}
                                                className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                            />
                                            <label htmlFor="mw_cont" className="ml-2 text-xs text-gray-700">Continuity Correction</label>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Paired T-Test Specific Options */}
                            <div className="border-t border-gray-100 pt-4 mt-2">
                                <h4 className="text-xs font-semibold uppercase text-gray-400 mb-3 tracking-wider">Paired T-Test Options</h4>
                                <div className="space-y-3">
                                    {/* Alternative */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Alternative Hypothesis</label>
                                        <select
                                            value={analysisOptions.alternative || "two-sided"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, alternative: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="two-sided">Two-Sided (≠)</option>
                                            <option value="less">Less (Left-tailed)</option>
                                            <option value="greater">Greater (Right-tailed)</option>
                                        </select>
                                    </div>

                                    {/* Permutation */}
                                    <div className="flex items-center">
                                        <input
                                            id="pt_perm"
                                            type="checkbox"
                                            checked={analysisOptions.use_permutation || false}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, use_permutation: e.target.checked })}
                                            className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                        />
                                        <label htmlFor="pt_perm" className="ml-2 text-xs text-gray-700">Permutation Test (Exact P)</label>
                                    </div>
                                </div>
                            </div>

                            {/* Wilcoxon Specific Options */}
                            <div className="border-t border-gray-100 pt-4 mt-2">
                                <h4 className="text-xs font-semibold uppercase text-gray-400 mb-3 tracking-wider">Wilcoxon Options</h4>
                                <div className="space-y-3">
                                    {/* Alternative */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Alternative Hypothesis</label>
                                        <select
                                            value={analysisOptions.alternative || "two-sided"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, alternative: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="two-sided">Two-Sided (≠)</option>
                                            <option value="less">Less (Left-tailed)</option>
                                            <option value="greater">Greater (Right-tailed)</option>
                                        </select>
                                    </div>

                                    {/* Zero Method */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Zero Method (Diff handling)</label>
                                        <select
                                            value={analysisOptions.zero_method || "wilcox"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, zero_method: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="wilcox">Wilcox (Discard zeros)</option>
                                            <option value="pratt">Pratt (Include in ranking)</option>
                                            <option value="zsplit">Z-Split (Split between +/-)</option>
                                        </select>
                                    </div>

                                    {/* Mode & Continuity */}
                                    <div className="flex items-center space-x-4">
                                        <div className="flex items-center">
                                            <input
                                                id="wc_cont"
                                                type="checkbox"
                                                checked={analysisOptions.correction !== false} // Default True
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, correction: e.target.checked })}
                                                className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                            />
                                            <label htmlFor="wc_cont" className="ml-2 text-xs text-gray-700">Continuity Cor.</label>
                                        </div>
                                        <div className="flex items-center">
                                            <label className="mr-2 text-xs text-gray-700">Mode:</label>
                                            <select
                                                value={analysisOptions.mode || "auto"}
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, mode: e.target.value })}
                                                className="text-xs border border-gray-300 rounded p-1 focus:border-black focus:ring-0"
                                            >
                                                <option value="auto">Auto</option>
                                                <option value="approx">Approx</option>
                                                <option value="exact">Exact</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* ANOVA Specific Options */}
                            <div className="border-t border-gray-100 pt-4 mt-2">
                                <h4 className="text-xs font-semibold uppercase text-gray-400 mb-3 tracking-wider">ANOVA Options</h4>
                                <div className="space-y-3">
                                    {/* Method Selection */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Method Selection</label>
                                        <select
                                            value={analysisOptions.method_force || "auto"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, method_force: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="auto">Auto (Check Homogeneity)</option>
                                            <option value="anova">Classic ANOVA</option>
                                            <option value="welch">Welch ANOVA</option>
                                        </select>
                                    </div>

                                    {/* Post-Hoc */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Post-Hoc Test</label>
                                        <select
                                            value={analysisOptions.post_hoc || "tukey"}
                                            onChange={(e) => setAnalysisOptions({ ...analysisOptions, post_hoc: e.target.value })}
                                            className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                        >
                                            <option value="tukey">Tukey HSD (Parametric)</option>
                                            <option value="bonferroni">Bonferroni</option>
                                            <option value="holm">Holm</option>
                                            <option value="sidak">Sidak</option>
                                            <option value="fdr_bh">Benjamini-Hochberg (FDR)</option>
                                            <option value="fdr_tsbky">Benjamini-Krieger-Yekutieli (Two-Stage FDR)</option>
                                        </select>
                                    </div>

                                    {/* Effect Size & Homogeneity */}
                                    <div className="flex space-x-4">
                                        <div className="flex-1">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">Effect Size</label>
                                            <select
                                                value={analysisOptions.effect_size_type || "eta_sq"}
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, effect_size_type: e.target.value })}
                                                className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                            >
                                                <option value="eta_sq">Eta-Squared (η²)</option>
                                                <option value="omega_sq">Omega-Squared (ω²)</option>
                                            </select>
                                        </div>
                                        <div className="flex-1">
                                            <label className="block text-sm font-medium text-gray-700 mb-1">Homogeneity Test</label>
                                            <select
                                                value={analysisOptions.homogeneity_test || "levene"}
                                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, homogeneity_test: e.target.value })}
                                                className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                            >
                                                <option value="levene">Levene (Robust)</option>
                                                <option value="bartlett">Bartlett (Sensitive)</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>

                        </div>

                        {/* Correlation Specific Options */}
                        <div className="border-t border-gray-100 pt-4 mt-2">
                            <h4 className="text-xs font-semibold uppercase text-gray-400 mb-3 tracking-wider">Correlation Options</h4>
                            <div className="space-y-3">
                                {/* Method Selection */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Method Base</label>
                                    <select
                                        value={analysisOptions.method || "pearson"}
                                        onChange={(e) => setAnalysisOptions({ ...analysisOptions, method: e.target.value })}
                                        className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                    >
                                        <option value="pearson">Pearson (Linear)</option>
                                        <option value="spearman">Spearman (Rank)</option>
                                        <option value="kendall">Kendall's Tau (Rank)</option>
                                    </select>
                                </div>

                                {/* Alternative */}
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Alternative Hypothesis</label>
                                    <select
                                        value={analysisOptions.alternative || "two-sided"}
                                        onChange={(e) => setAnalysisOptions({ ...analysisOptions, alternative: e.target.value })}
                                        className="w-full text-xs border border-gray-300 rounded p-1.5 focus:border-black focus:ring-0 sans-serif"
                                    >
                                        <option value="two-sided">Two-Sided (≠)</option>
                                        <option value="less">Less (Negative Correlation)</option>
                                        <option value="greater">Greater (Positive Correlation)</option>
                                    </select>
                                </div>
                                {/* Cluster Option */}
                                <div className="flex items-center">
                                    <input
                                        id="cluster_chk"
                                        type="checkbox"
                                        checked={analysisOptions.cluster_variables || false}
                                        onChange={(e) => setAnalysisOptions({ ...analysisOptions, cluster_variables: e.target.checked })}
                                        className="h-4 w-4 text-black focus:ring-0 border-gray-300 rounded"
                                    />
                                    <label htmlFor="cluster_chk" className="ml-2 text-xs text-gray-700">Cluster Variables (Heatmap + Dendrogram)</label>
                                </div>
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Confidence Level</label>
                            <select
                                className="w-full"
                                value={analysisOptions.conf_level}
                                onChange={(e) => setAnalysisOptions({ ...analysisOptions, conf_level: parseFloat(e.target.value) })}
                            >
                                <option value={0.95}>95% (alpha = 0.05)</option>
                                <option value={0.99}>99% (alpha = 0.01)</option>
                            </select>
                        </div>
                    </div>

                    <div className="mt-6 flex justify-end gap-2">
                        <button
                            onClick={() => setShowSettings(false)}
                            className="btn-secondary"
                        >
                            Close
                        </button>
                    </div>
                </div>
            )}

            {/* Report Modal */}
            {showReportPreview && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
                    <div className="bg-white w-[90vw] h-[90vh] rounded shadow-2xl flex flex-col overflow-hidden">
                        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-gray-50">
                            <h2 className="font-semibold text-lg">Report Preview (HTML)</h2>
                            <button
                                onClick={() => setShowReportPreview(false)}
                                className="text-gray-500 hover:text-black"
                            >
                                Close
                            </button>
                        </div>
                        <div className="flex-1 overflow-auto p-0">
                            <iframe
                                srcDoc={reportHtml}
                                className="w-full h-full border-0"
                                title="Report Preview"
                            />
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
