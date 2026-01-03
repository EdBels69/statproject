import { useState, useEffect } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import { runBatchAnalysis, getReportUrl, getDataset } from '../../lib/api';
import VariableSelector from '../components/VariableSelector';
import VisualizePlot from '../components/VisualizePlot';

export default function Analyze() {
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const [columns, setColumns] = useState([]);

    // Results
    const [loading, setLoading] = useState(false);
    const [batchResult, setBatchResult] = useState(null);
    const [error, setError] = useState(null);

    // Display
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
            <div className="overflow-x-auto mb-8 border border-slate-300">
                <table className="w-full text-xs text-left text-slate-700 font-mono">
                    <thead className="bg-slate-100/50 text-slate-900 border-b border-slate-300 uppercase tracking-wider">
                        <tr>
                            <th className="px-3 py-2 border-r border-slate-300">Переменная</th>
                            <th className="px-3 py-2 border-r border-slate-300">Группа</th>
                            <th className="px-3 py-2 border-r border-slate-300 text-right">N</th>
                            <th className="px-3 py-2 border-r border-slate-300 text-right">Среднее</th>
                            <th className="px-3 py-2 border-r border-slate-300 text-right">SD</th>
                            <th className="px-3 py-2 border-r border-slate-300 text-right">Медиана</th>
                            <th className="px-3 py-2 text-right">Норм. (P)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {batchResult.descriptives.map((row, idx) => (
                            <tr key={idx} className="bg-white hover:bg-slate-50">
                                <td className="px-3 py-1.5 border-r border-slate-200 font-semibold">{row.variable}</td>
                                <td className="px-3 py-1.5 border-r border-slate-200">{row.group}</td>
                                <td className="px-3 py-1.5 border-r border-slate-200 text-right">{row.count}</td>
                                <td className="px-3 py-1.5 border-r border-slate-200 text-right">{row.mean.toFixed(2)}</td>
                                <td className="px-3 py-1.5 border-r border-slate-200 text-right">{row.sd.toFixed(2)}</td>
                                <td className="px-3 py-1.5 border-r border-slate-200 text-right">{row.median.toFixed(2)}</td>
                                <td className={`px-3 py-1.5 text-right ${!row.is_normal ? 'text-red-600' : 'text-slate-500'}`}>
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
            <div className="overflow-x-auto border border-slate-300 mb-8">
                <table className="w-full text-xs text-left text-slate-700 font-mono">
                    <thead className="bg-slate-100/50 text-slate-900 border-b border-slate-300 uppercase tracking-wider">
                        <tr>
                            <th className="px-3 py-2 border-r border-slate-300">Переменная</th>
                            <th className="px-3 py-2 border-r border-slate-300">Метод</th>
                            <th className="px-3 py-2 border-r border-slate-300 text-right">Статистика</th>
                            <th className="px-3 py-2 border-r border-slate-300 text-right">P-Value</th>
                            <th className="px-3 py-2 text-center w-16">Знач.</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {Object.entries(batchResult.results).map(([varName, res]) => (
                            <tr
                                key={varName}
                                onClick={() => setSelectedVarDetail(varName)}
                                className={`cursor-pointer transition-colors ${selectedVarDetail === varName ? 'bg-indigo-50 text-indigo-900' : 'bg-white hover:bg-slate-50'}`}
                            >
                                <td className="px-3 py-2 border-r border-slate-200 font-semibold">{varName}</td>
                                <td className="px-3 py-2 border-r border-slate-200">{res.method.name}</td>
                                <td className="px-3 py-2 border-r border-slate-200 text-right">{res.stat_value.toFixed(2)}</td>
                                <td className={`px-3 py-2 border-r border-slate-200 text-right ${res.significant ? 'font-bold text-slate-900' : 'text-slate-500'}`}>
                                    {res.p_value < 0.001 ? '<.001' : res.p_value.toFixed(3)}
                                </td>
                                <td className="px-3 py-2 text-center">
                                    {res.significant ? <span className="text-slate-900 font-bold">ДА</span> : <span className="text-slate-300">НЕТ</span>}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    return (
        <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-white text-slate-900 font-sans">
            {/* Left Sidebar */}
            <aside className="w-[320px] flex-shrink-0 border-r border-slate-300 flex flex-col z-20 bg-slate-50/30">
                <VariableSelector
                    allColumns={columns}
                    onRun={handleRunBatch}
                    loading={loading}
                />
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto bg-white">
                <div className="max-w-[1200px] mx-auto p-8">

                    {/* Minimalist Header */}
                    <div className="flex items-center justify-between mb-8 pb-4 border-b border-slate-200">
                        <div className="flex items-center gap-4">
                            <button
                                onClick={() => navigate(`/profile/${id}`)}
                                className="w-6 h-6 flex items-center justify-center border border-slate-300 hover:bg-slate-100 hover:border-slate-400 text-slate-500 text-xs transition-colors"
                            >
                                ←
                            </button>
                            <h1 className="text-sm font-bold uppercase tracking-[0.2em] text-slate-900">
                                Результаты анализа
                            </h1>
                        </div>
                        {batchResult && selectedVarDetail && (
                            <a
                                href={getReportUrl(id, selectedVarDetail, activeGroupCol, 'auto')}
                                target="_blank"
                                className="text-[10px] font-bold uppercase tracking-widest border border-slate-900 px-3 py-1.5 hover:bg-slate-900 hover:text-white transition-colors"
                            >
                                Скачать PDF
                            </a>
                        )}
                    </div>

                    {/* Error Banner */}
                    {error && (
                        <div className="mb-6 border border-red-500 bg-red-50 p-4 text-xs font-mono text-red-700">
                            <strong>ОШИБКА:</strong> {error}
                        </div>
                    )}

                    {/* Empty State */}
                    {!batchResult && !loading && (
                        <div className="h-[400px] flex items-center justify-center border border-dashed border-slate-300 text-slate-400 font-mono text-xs uppercase tracking-widest">
                            Выберите переменные слева для начала анализа
                        </div>
                    )}

                    {/* Loading State */}
                    {loading && (
                        <div className="h-[400px] flex flex-col items-center justify-center font-mono text-xs text-slate-500 uppercase tracking-widest">
                            <span className="animate-pulse">Обработка данных...</span>
                        </div>
                    )}

                    {/* Results */}
                    {batchResult && (
                        <div className="animate-in fade-in duration-300">

                            {/* Descriptives */}
                            <section className="mb-8">
                                <h3 className="text-xs font-bold uppercase tracking-widest mb-3 text-slate-500">Описательная статистика</h3>
                                {renderDescriptives()}
                            </section>

                            {/* Hypothesis Tests */}
                            <section className="mb-8">
                                <h3 className="text-xs font-bold uppercase tracking-widest mb-3 text-slate-500">Проверка гипотез</h3>
                                {renderResultsTable()}
                            </section>

                            {/* Detail View */}
                            {selectedVarDetail && batchResult.results[selectedVarDetail] && (
                                <section className="border-t border-slate-200 pt-8 mt-8">
                                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                                        {/* AI Insight */}
                                        <div className="lg:col-span-1">
                                            <h4 className="text-[10px] font-bold uppercase tracking-widest mb-2 text-indigo-600">
                                                AI Интерпретация
                                            </h4>
                                            <p className="text-sm text-slate-800 leading-relaxed font-mono whitespace-pre-line border border-slate-200 p-4 bg-slate-50/50">
                                                {batchResult.results[selectedVarDetail].conclusion}
                                            </p>
                                        </div>

                                        {/* Plot */}
                                        <div className="lg:col-span-2 border border-slate-200 p-4 min-h-[350px] flex flex-col">
                                            <h4 className="text-[10px] font-bold uppercase tracking-widest mb-4 text-center text-slate-400">
                                                Графики распределения
                                            </h4>
                                            <div className="flex-1 relative">
                                                {batchResult.results[selectedVarDetail].plot_data ? (
                                                    <VisualizePlot
                                                        data={batchResult.results[selectedVarDetail].plot_data}
                                                        stats={batchResult.results[selectedVarDetail].plot_stats}
                                                        groups={batchResult.results[selectedVarDetail].groups}
                                                    />
                                                ) : (
                                                    <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-slate-300">
                                                        НЕТ ДАННЫХ
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </section>
                            )}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
