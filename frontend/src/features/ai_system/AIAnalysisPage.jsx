import React, { useState, useEffect, lazy, Suspense } from 'react';
import { getDatasets, deleteDataset } from '../../lib/api';
import { Link } from 'react-router-dom';
import VariableManager from './VariableManager';

const VisualizePlot = lazy(() => import('../../app/components/VisualizePlot'));
const ClusteredHeatmap = lazy(() => import('../../app/components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../../app/components/InteractionPlot'));

const API_BASE = "http://localhost:8000/api/v2/ai_system";

export default function AIAnalysisPage() {
    const [datasets, setDatasets] = useState([]);
    const [datasetId, setDatasetId] = useState("");

    // Steps: 'select' -> 'manager' -> 'review' -> 'results'
    const [step, setStep] = useState("select");

    const [analysisData, setAnalysisData] = useState(null); // { draft_config, all_columns, variable_manifest, ... }
    const [filteredManifest, setFilteredManifest] = useState(null); // Result of Manager

    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        loadDatasets();
    }, []);

    const loadDatasets = async () => {
        try {
            const data = await getDatasets();
            setDatasets(data);
        } catch (e) {
            setError("Ошибка загрузки данных: " + e.message);
        }
    };

    const handleDeleteDataset = async (e, id, name) => {
        e.stopPropagation();
        if (!confirm(`Удалить файл "${name}"?`)) return;
        try {
            await deleteDataset(id);
            await loadDatasets();
            if (datasetId === id) setDatasetId("");
        } catch (err) {
            alert(err.message);
        }
    };

    const handleSelectDataset = (id) => {
        setDatasetId(id);
    };

    // Step 1 -> 2: Analyze Structure & Get Variables
    const handleAnalyze = async () => {
        if (!datasetId) return;
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/analyze`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ dataset_id: datasetId })
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();

            // Check if backend returned an error
            if (data.error) {
                setError(data.error);
                return;
            }

            setAnalysisData(data);
            setStep("manager"); // Go to Manager first
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    // Step 2 -> 3: Manager Confirm
    const handleManagerConfirm = (selectedVars) => {
        setFilteredManifest(selectedVars);
        setStep("review");
    };

    // Step 3 -> 4: Run Analysis
    const handleRun = async () => {
        setLoading(true);
        setError(null);
        try {
            // Pass the selected variables to the config
            const selectedColumns = filteredManifest ? filteredManifest.map(v => v.name) : null;
            const res = await fetch(`${API_BASE}/run`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    dataset_id: datasetId,
                    config: analysisData.draft_config,
                    selected_columns: selectedColumns  // Pass user's selection
                })
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            setResults(data);
            setStep("results");
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const updateConfig = (field, value) => {
        setAnalysisData(prev => ({
            ...prev,
            draft_config: {
                ...prev.draft_config,
                [field]: value
            }
        }));
    };

    // Download DOCX report
    const handleDownloadReport = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/download-report`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    dataset_id: datasetId,
                    results: results,
                    config: analysisData.draft_config
                })
            });
            if (!res.ok) throw new Error(await res.text());

            // Download file
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `analysis_report_${datasetId.substring(0, 8)}.docx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (e) {
            setError(`Ошибка скачивания: ${e.message}`);
        } finally {
            setLoading(false);
        }
    };

    // Render Helpers
    const renderSelectStep = () => (
        <div className="animate-fadeIn">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">1. Выбор данных</h2>
                    <p className="text-gray-500">Выберите набор данных для авто-анализа</p>
                </div>
                <Link to="/upload" className="bg-indigo-50 text-indigo-700 px-4 py-2 rounded-lg font-medium hover:bg-indigo-100 transition">
                    + Загрузить новый файл
                </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[500px] overflow-y-auto pr-2 mb-6">
                {datasets.map(ds => (
                    <div
                        key={ds.id}
                        onClick={() => handleSelectDataset(ds.id)}
                        className={`relative p-5 border rounded-xl cursor-pointer transition-all shadow-sm group ${datasetId === ds.id
                            ? 'border-indigo-600 bg-indigo-50 ring-2 ring-indigo-200'
                            : 'hover:border-indigo-300 hover:shadow-md bg-white'
                            }`}
                    >
                        <button
                            onClick={(e) => handleDeleteDataset(e, ds.id, ds.filename)}
                            className="absolute top-2 right-2 p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded bg-white opacity-0 group-hover:opacity-100 transition-opacity z-10"
                            title="Удалить файл"
                        >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                        </button>

                        <div className="font-bold text-lg mb-1 truncate pr-8" title={ds.filename}>{ds.filename}</div>
                        <div className="text-xs text-gray-400 font-mono truncate mb-2">{ds.id}</div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span className="bg-gray-100 px-2 py-1 rounded">Excel/CSV</span>
                            <span>{ds.uploaded_at ? (isNaN(new Date(ds.uploaded_at).getTime()) ? '—' : new Date(ds.uploaded_at).toLocaleDateString('ru-RU')) : '—'}</span>
                        </div>
                    </div>
                ))}
            </div>

            <div className="flex justify-end pt-4 border-t">
                <button
                    onClick={handleAnalyze}
                    disabled={loading || !datasetId}
                    className="bg-indigo-600 text-white px-8 py-3 rounded-lg font-bold shadow-lg hover:bg-indigo-700 disabled:opacity-50 disabled:shadow-none transition-all flex items-center gap-2"
                >
                    {loading ? (
                        <>
                            <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                            Анализ структуры...
                        </>
                    ) : "Далее: Выбор переменных →"}
                </button>
            </div>
        </div>
    );

    const renderManagerStep = () => (
        <VariableManager
            manifest={analysisData.variable_manifest || []}
            onConfirm={handleManagerConfirm}
            onCancel={() => setStep("select")}
        />
    );

    const renderReviewStep = () => {
        const config = analysisData?.draft_config;
        // Use filtered columns if available, else all found
        const columns = analysisData?.all_columns || [];

        return (
            <div className="animate-fadeIn">
                <div className="mb-6">
                    <button onClick={() => setStep("manager")} className="text-sm text-gray-500 hover:text-gray-900 mb-2">← Назад к переменным</button>
                    <h2 className="text-2xl font-bold text-gray-800">3. Согласование протокола</h2>
                    <p className="text-gray-500">ИИ определил структуру "Группы/Время". Выбранные переменные будут проанализированы в этом разрезе.</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                    {/* Left Col: Config */}
                    <div className="col-span-1 space-y-6">
                        <div className="bg-white p-5 rounded-xl border shadow-sm">
                            <label className="block text-sm font-bold text-gray-700 mb-2">Группирующая переменная</label>
                            <select
                                value={config.group_col || ""}
                                onChange={(e) => updateConfig('group_col', e.target.value)}
                                className="block w-full border border-gray-300 p-2.5 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
                            >
                                <option value="">-- Не выбрано --</option>
                                {/* Use categorical_columns if available, otherwise fall back to all columns */}
                                {(analysisData?.categorical_columns?.length > 0 ? analysisData.categorical_columns : columns).map(col => (
                                    <option key={col} value={col}>{col}</option>
                                ))}
                            </select>
                            <p className="text-xs text-gray-500 mt-2">Основной фактор сравнения (Группа, Терапия и т.д.)</p>
                        </div>

                        <div className="bg-white p-5 rounded-xl border shadow-sm">
                            <label className="block text-sm font-bold text-gray-700 mb-2">Визиты / Точки времени</label>
                            <div className="flex flex-wrap gap-2 mb-2">
                                {(config.visits || []).map(v => (
                                    <span key={v} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm font-medium border border-blue-200">{v}</span>
                                ))}
                            </div>
                            {(!config.visits || config.visits.length === 0) && (
                                <div className="text-sm text-gray-400 italic bg-gray-50 p-2 rounded">Визиты не обнаружены (возможно, cross-sectional)</div>
                            )}
                        </div>
                    </div>

                    {/* Right Col: Endpoints */}
                    <div className="col-span-2">
                        <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
                            <div className="bg-gray-50 px-6 py-4 border-b flex justify-between items-center">
                                <h3 className="font-bold text-gray-800">Выборка переменных</h3>
                                <span className="text-xs text-gray-500">
                                    {filteredManifest ? `Выбрано: ${filteredManifest.length}` : 'Все доступные'}
                                </span>
                            </div>
                            <div className="p-6 space-y-4 max-h-[600px] overflow-y-auto">
                                {/* Show Categorical/Numeric breakdown from filteredManifest */}
                                {filteredManifest ? (
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="border p-4 rounded-lg">
                                            <div className="font-bold text-indigo-700 mb-2 border-b pb-1">Количественные ({filteredManifest.filter(m => m.type === 'numeric').length})</div>
                                            <ul className="text-xs space-y-1 text-gray-600 max-h-40 overflow-y-auto">
                                                {filteredManifest.filter(m => m.type === 'numeric').map(m => <li key={m.name}>• {m.name}</li>)}
                                            </ul>
                                        </div>
                                        <div className="border p-4 rounded-lg">
                                            <div className="font-bold text-purple-700 mb-2 border-b pb-1">Качественные ({filteredManifest.filter(m => m.type === 'categorical').length})</div>
                                            <ul className="text-xs space-y-1 text-gray-600 max-h-40 overflow-y-auto">
                                                {filteredManifest.filter(m => m.type === 'categorical').map(m => <li key={m.name}>• {m.name}</li>)}
                                            </ul>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="text-gray-500 text-sm">Переменные не были отфильтрованы (обрабатываются все).</div>
                                )}

                                <h4 className="font-bold mt-4 pt-4 border-t text-gray-700">Определенные семейства (Longitudinal)</h4>
                                {config.endpoints?.map((fam, idx) => (
                                    <div key={idx} className="flex justify-between items-center p-2 border-b last:border-0 border-gray-100 bg-gray-50 rounded mb-1">
                                        <span className="font-semibold text-gray-700">{fam.family_name}</span>
                                        <div className="flex gap-1">
                                            {Object.keys(fam.columns).map(v => <span key={v} className="text-[10px] bg-white border px-1 rounded">{v}</span>)}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex justify-end pt-6 border-t">
                    <button
                        onClick={handleRun}
                        disabled={loading}
                        className="bg-green-600 text-white px-8 py-3 rounded-lg font-bold shadow-lg hover:bg-green-700 disabled:opacity-50 transition-all flex items-center gap-2"
                    >
                        {loading ? "Выполнение расчетов..." : "✓ Подтвердить и Запустить"}
                    </button>
                </div>
            </div>
        );
    };

    const renderResultsStep = () => {
        let totalTests = 0;
        if (results?.endpoints) {
            Object.values(results.endpoints).forEach(fam => {
                totalTests += Object.keys(fam.tests || {}).length;
            });
        }
        if (results?.single_variables) {
            totalTests += Object.keys(results.single_variables).length;
        }

        const singleVars = results?.single_variables || {};
        const sigVars = Object.entries(singleVars).filter(([, v]) => v.test?.significant);
        const nonSigVars = Object.entries(singleVars).filter(([, v]) => !v.test?.significant);

        return (
            <div className="animate-fadeIn">
                <div className="flex justify-between items-end mb-8 border-b pb-4">
                    <div>
                        <button onClick={() => setStep("review")} className="text-sm text-gray-500 hover:text-gray-900 mb-1">← Назад к параметрам</button>
                        <h2 className="text-3xl font-bold text-gray-800">Результаты анализа</h2>
                        <p className="text-green-600 font-medium">Выполнено {totalTests} статистических тестов. Значимых: {sigVars.length}</p>
                    </div>
                    <button
                        onClick={handleDownloadReport}
                        disabled={loading}
                        className="bg-gray-800 text-white px-5 py-2.5 rounded-lg shadow hover:bg-black transition text-sm font-bold flex items-center gap-2 disabled:opacity-50"
                    >
                        <span>📄</span> Скачать отчет (DOCX)
                    </button>
                </div>

                {/* Single Variables Table (Main Results) */}
                {Object.keys(singleVars).length > 0 && (
                    <div className="bg-white border rounded-xl shadow-sm overflow-hidden mb-8">
                        <div className="bg-green-50 px-6 py-4 border-b">
                            <h3 className="text-xl font-bold text-green-900">Общая таблица результатов</h3>
                            <p className="text-sm text-green-700">Все переменные с результатами тестов</p>
                        </div>
                        <div className="p-0 overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-gray-50">
                                    <tr className="text-gray-600 border-b">
                                        <th className="p-3 text-left font-semibold">Переменная</th>
                                        <th className="p-3 text-left font-semibold">Тип</th>
                                        <th className="p-3 text-left font-semibold">Метод</th>
                                        <th className="p-3 text-left font-semibold">P-Value</th>
                                        <th className="p-3 text-left font-semibold">Значимость</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {/* Significant first */}
                                    {sigVars.map(([varName, varData]) => (
                                        <tr key={varName} className="border-b bg-green-50 hover:bg-green-100">
                                            <td className="p-3 font-semibold text-gray-800">{varName}</td>
                                            <td className="p-3">
                                                <span className={`px-2 py-0.5 rounded text-xs ${varData.type === 'numeric' ? 'bg-indigo-100 text-indigo-700' : 'bg-purple-100 text-purple-700'}`}>
                                                    {varData.type === 'numeric' ? 'Колич.' : 'Катег.'}
                                                </span>
                                            </td>
                                            <td className="p-3 text-gray-600">{varData.test?.method || '-'}</td>
                                            <td className="p-3">
                                                <span className="px-2 py-1 rounded text-xs font-mono font-bold bg-green-200 text-green-800">
                                                    {varData.test?.p_value < 0.001 ? "< 0.001" : varData.test?.p_value?.toFixed(4)}
                                                </span>
                                            </td>
                                            <td className="p-3">
                                                <span className="text-green-700 font-bold">✓ Значимо</span>
                                            </td>
                                        </tr>
                                    ))}
                                    {/* Non-significant */}
                                    {nonSigVars.map(([varName, varData]) => (
                                        <tr key={varName} className="border-b hover:bg-gray-50">
                                            <td className="p-3 text-gray-700">{varName}</td>
                                            <td className="p-3">
                                                <span className={`px-2 py-0.5 rounded text-xs ${varData.type === 'numeric' ? 'bg-indigo-100 text-indigo-700' : 'bg-purple-100 text-purple-700'}`}>
                                                    {varData.type === 'numeric' ? 'Колич.' : 'Катег.'}
                                                </span>
                                            </td>
                                            <td className="p-3 text-gray-500">{varData.test?.method || '-'}</td>
                                            <td className="p-3">
                                                <span className="px-2 py-1 rounded text-xs font-mono bg-gray-100 text-gray-500">
                                                    {varData.test?.p_value?.toFixed(4) || '-'}
                                                </span>
                                            </td>
                                            <td className="p-3 text-gray-400">—</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Longitudinal Families */}
                <div className="space-y-8">
                    {results?.endpoints && Object.keys(results.endpoints).map(famName => {
                        const fam = results.endpoints[famName];
                        return (
                            <div key={famName} className="bg-white border rounded-xl shadow-sm overflow-hidden">
                                <div className="bg-indigo-50 px-6 py-4 border-b flex justify-between items-center">
                                    <h3 className="text-xl font-bold text-indigo-900 uppercase tracking-wide">{famName}</h3>
                                    <span className="text-xs font-bold bg-white text-indigo-600 px-3 py-1 rounded-full border border-indigo-100">Longitudinal Analysis</span>
                                </div>

                                <div className="p-6">
                                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                                        {/* Table */}
                                        <div>
                                            <h4 className="font-bold text-gray-700 mb-4 border-b pb-2">Статистическая значимость</h4>
                                            <table className="w-full text-sm">
                                                <thead>
                                                    <tr className="text-gray-500 border-b">
                                                        <th className="pb-2 text-left font-medium">Визит</th>
                                                        <th className="pb-2 text-left font-medium">Метод</th>
                                                        <th className="pb-2 text-left font-medium">P-Value</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {fam.tests && Object.keys(fam.tests).map(visit => {
                                                        const t = fam.tests[visit];
                                                        const isSig = t.significant;
                                                        return (
                                                            <tr key={visit} className="border-b last:border-0 hover:bg-gray-50">
                                                                <td className="py-3 font-semibold text-gray-800">{visit}</td>
                                                                <td className="py-3 text-gray-600">{t.method}</td>
                                                                <td className="py-3">
                                                                    <span className={`px-2 py-1 rounded text-xs font-mono font-bold ${isSig ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-400'}`}>
                                                                        {t.p_value < 0.001 ? "< 0.001" : t.p_value?.toFixed(4)}
                                                                    </span>
                                                                </td>
                                                            </tr>
                                                        );
                                                    })}
                                                </tbody>
                                            </table>
                                        </div>

                                        {/* Plots - Interactive */}
                                        <div className="flex flex-col items-center justify-center bg-gray-50 rounded-xl p-4 border border-dashed min-h-[300px]">
                                            <Suspense fallback={<div className="animate-pulse text-gray-400">Загрузка графика...</div>}>
                                                {/* Iterate over main results to find plots associated with this family/variable */}
                                                {Object.entries(results).map(([key, item]) => {
                                                    // Check if item is a plot and vaguely matches the family name or variables
                                                    if (item?.type === 'plot' && item?.data) {
                                                        // Simple check: if key contains family name
                                                        if (key.toLowerCase().includes(famName.toLowerCase())) {
                                                            return (
                                                                <div key={key} className="w-full mb-4">
                                                                    <div className="text-sm font-bold text-gray-500 mb-2 text-center">{key}</div>
                                                                    <VisualizePlot
                                                                        data={item.data}
                                                                        layout={item.layout}
                                                                    />
                                                                </div>
                                                            );
                                                        }
                                                    }
                                                    if (item?.type === 'clustered_heatmap' && item?.data) {
                                                        return (
                                                            <div key={key} className="w-full">
                                                                <ClusteredHeatmap data={item.data} />
                                                            </div>
                                                        );
                                                    }
                                                    return null;
                                                })}

                                                {/* Legacy Image Fallback */}
                                                {results.generated_plots?.filter(p => p.name === famName).map((plot, idx) => (
                                                    <div key={idx} className="w-full">
                                                        <img
                                                            src={`data:image/png;base64,${plot.image_base64}`}
                                                            alt={plot.name}
                                                            className="w-full h-auto rounded mix-blend-multiply"
                                                        />
                                                    </div>
                                                ))}
                                            </Suspense>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-white">
            <div className="max-w-7xl mx-auto px-6 py-8">
                <header className="mb-8 border-b pb-4 flex justify-between items-center">
                    <div className="flex items-center gap-3">
                        <span className="bg-indigo-600 text-white rounded-lg p-2">
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                        </span>
                        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Auto-Analyst <span className="text-indigo-600">AI</span></h1>
                    </div>
                </header>

                {error && (
                    <div className="mb-6 bg-red-50 border-l-4 border-red-500 p-4 rounded text-red-700 shadow-sm flex justify-between items-center">
                        <div>
                            <strong className="block font-bold">Ошибка</strong>
                            <span className="text-sm">{error}</span>
                        </div>
                        <button onClick={() => setError(null)}>✕</button>
                    </div>
                )}

                {step === "select" && renderSelectStep()}
                {step === "manager" && renderManagerStep()}
                {step === "review" && renderReviewStep()}
                {step === "results" && renderResultsStep()}
            </div>
        </div>
    );
}
