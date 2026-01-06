import React, { useState, useEffect } from 'react';
import { getAnalysisResults } from '../../../lib/api';
import BatchResultsTable from '../../components/BatchResultsTable';
import {
    ChartBarIcon,
    BeakerIcon,
    ArrowDownTrayIcon,
    ListBulletIcon,
    ArrowTrendingUpIcon
} from '@heroicons/react/24/outline';
import PostHocTable from '../../components/PostHocTable';
import RegressionResults from '../../components/RegressionResults';
import SkeletonResults from '../../components/SkeletonResults';
import InterpretationCard from '../../components/InterpretationCard';
import HelpTooltip from '../../components/HelpTooltip';
import ChartCustomizer from '../../components/ChartCustomizer';

/* --- MAIN RESULTS COMPONENT --- */
const StepResults = ({ runId, datasetId, goal }) => {
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(true);
    const [viewMode, setViewMode] = useState('summary'); // 'summary' or 'detail'

    useEffect(() => {
        if (runId && datasetId) {
            getAnalysisResults(datasetId, runId)
                .then(setResults)
                .catch(console.error)
                .finally(() => setLoading(false));
        }
    }, [runId, datasetId]);

    if (loading) return <SkeletonResults />;
    if (!results) return (
        <div className="p-8 text-center bg-red-50 rounded-xl border border-red-100">
            <h3 className="text-lg font-bold text-red-800 mb-2">Ошибка загрузки результатов</h3>
            <p className="text-red-600">Не удалось получить данные анализа. Попробуйте обновить страницу.</p>
        </div>
    );

    // Detect batch mode: multiple test_ keys
    const resultKeys = Object.keys(results.results || {});
    const testKeys = resultKeys.filter(k => k.startsWith('test_'));
    const isBatchMode = testKeys.length > 1;

    const handleDownloadWord = async () => {
        try {
            const url = `http://localhost:8000/api/v1/analysis/report/${runId}/word?dataset_id=${datasetId}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Download failed');

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = `report_${runId.substring(0, 8)}.docx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(downloadUrl);
        } catch (err) {
            console.error('Word download error:', err);
            alert('Ошибка скачивания отчёта');
        }
    };

    return (
        <div className="animate-fadeIn min-h-screen pb-20">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">{results.protocol_name}</h2>
                    <p className="text-gray-500 text-sm">
                        {isBatchMode ? `${testKeys.length} переменных` : 'Одиночный анализ'} | run: {runId?.slice(0, 12)}...
                    </p>
                </div>
                <div className="flex items-center space-x-3">
                    {/* View Mode Toggle */}
                    {isBatchMode && (
                        <div className="flex border rounded-lg overflow-hidden">
                            <button
                                onClick={() => setViewMode('summary')}
                                className={`px-3 py-1.5 text-sm flex items-center gap-1.5 ${viewMode === 'summary'
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-white text-gray-600 hover:bg-gray-50'
                                    }`}
                            >
                                <ListBulletIcon className="w-4 h-4" />
                                Сводка
                            </button>
                            <button
                                onClick={() => setViewMode('detail')}
                                className={`px-3 py-1.5 text-sm flex items-center gap-1.5 border-l ${viewMode === 'detail'
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-white text-gray-600 hover:bg-gray-50'
                                    }`}
                            >
                                <ChartBarIcon className="w-4 h-4" />
                                Детали
                            </button>
                        </div>
                    )}

                    <button
                        onClick={handleDownloadWord}
                        className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow-sm"
                    >
                        <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                        Скачать Word
                    </button>
                    <button
                        onClick={() => window.open(`http://localhost:8000/api/v1/analysis/report/${runId}/html?dataset_id=${datasetId}`, '_blank')}
                        className="flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                        <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                        HTML
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                {isBatchMode && viewMode === 'summary' ? (
                    <BatchResultsTable
                        results={results.results}
                        onExportSelection={async (selectedRows, settings) => {
                            try {
                                // Build request body with selected variables
                                const selectedVariables = selectedRows.map(r => r.variable);
                                const url = `http://localhost:8000/api/v1/analysis/report/${runId}/word/selective?dataset_id=${datasetId}`;

                                const response = await fetch(url, {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        variables: selectedVariables,
                                        show_mean: settings.showMean,
                                        show_median: settings.showMedian,
                                        show_quartiles: settings.showQuartiles
                                    })
                                });

                                if (!response.ok) throw new Error('Export failed');

                                const blob = await response.blob();
                                const downloadUrl = window.URL.createObjectURL(blob);
                                const link = document.createElement('a');
                                link.href = downloadUrl;
                                link.download = `report_selected_${runId.substring(0, 8)}.docx`;
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                                window.URL.revokeObjectURL(downloadUrl);
                            } catch (err) {
                                console.error('Selective export error:', err);
                                alert('Ошибка генерации отчёта');
                            }
                        }}
                    />
                ) : (
                    <DetailView results={results} />
                )}
            </div>
        </div>
    );
};

/* --- DETAIL VIEW (Original tabs) --- */
const DetailView = ({ results }) => {
    const [activeTab, setActiveTab] = useState(0);

    const steps = Object.keys(results.results).map(key => ({
        id: key,
        data: results.results[key],
        label: key.replace(/_/g, ' ').replace('desc ', '📊 ').replace('test ', '🧪 ')
    }));

    const activeStep = steps[activeTab] || steps[0];
    if (!activeStep) return <div>Нет данных</div>;

    return (
        <>
            <div className="border-b border-gray-200 mb-6 overflow-x-auto">
                <nav className="-mb-px flex space-x-4">
                    {steps.map((step, idx) => (
                        <button
                            key={step.id}
                            onClick={() => setActiveTab(idx)}
                            className={`py-3 px-2 border-b-2 font-medium text-xs whitespace-nowrap transition-colors ${activeTab === idx
                                ? 'border-indigo-500 text-indigo-600'
                                : 'border-transparent text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            {step.label}
                        </button>
                    ))}
                </nav>
            </div>

            <div>
                {activeStep.data.type === 'table_1' && (
                    <SimpleTable data={activeStep.data.data} />
                )}

                {activeStep.data.p_value !== undefined && (
                    <TestResult data={activeStep.data} />
                )}

                {activeStep.data.error && (
                    <div className="text-red-500 p-4 bg-red-50 rounded">
                        ⚠️ {activeStep.data.error}
                    </div>
                )}
                {activeStep.data.mean_diff !== undefined && (
                    <div className="p-5 bg-white border rounded-xl shadow-sm">
                        <h4 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                            <ArrowTrendingUpIcon className="w-5 h-5 text-blue-600" />
                            Различия (Paired Differences)
                        </h4>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="p-3 bg-gray-50 rounded-lg text-center">
                                <div className="text-xs text-gray-500 uppercase font-semibold mb-1">Mean Difference</div>
                                <div className="text-lg font-bold text-gray-900">
                                    {activeStep.data.mean_diff.toFixed(2)}
                                    <span className="text-sm font-normal text-gray-500 ml-1">± {activeStep.data.std_diff.toFixed(2)}</span>
                                </div>
                            </div>
                            <div className="p-3 bg-gray-50 rounded-lg text-center">
                                <div className="text-xs text-gray-500 uppercase font-semibold mb-1">Range (Min - Max)</div>
                                <div className="text-lg font-medium text-gray-900">
                                    {activeStep.data.min_diff.toFixed(2)} <span className="text-gray-400 mx-1">/</span> {activeStep.data.max_diff.toFixed(2)}
                                </div>
                            </div>
                        </div>
                        <p className="mt-3 text-sm text-gray-500 text-center">
                            n = {activeStep.data.n} pairs
                        </p>
                    </div>
                )}
                {/* Correlation Matrix Heatmap */}
                {activeStep.data.plot_image && (
                    <div className="p-5 bg-white border rounded-xl shadow-sm mt-6">
                        <h4 className="font-semibold text-gray-900 mb-4 text-center">Correlation Heatmap</h4>
                        <div className="flex justify-center">
                            <img
                                src={`data:image/png;base64,${activeStep.data.plot_image}`}
                                alt="Correlation Heatmap"
                                className="max-w-full rounded-lg shadow-md border"
                            />
                        </div>
                        <p className="text-center text-xs text-gray-500 mt-2">
                            Pearson methods used by default.
                        </p>
                    </div>
                )}

                {/* Regression Results */}
                {activeStep.type === 'regression' && (
                    <RegressionResults
                        data={activeStep.data}
                        runId={runId}
                        datasetId={datasetId}
                        stepId={activeStep.id}
                        onUpdate={(newImg) => {
                            const newRes = { ...results };
                            newRes.results[activeStep.id].plot_image = newImg;
                            setResults(newRes);
                        }}
                    />
                )}

                {/* Survival Analysis Results */}
                {activeStep.type === 'survival' && (
                    <div className="space-y-6">
                        {/* Survival Plot */}
                        {activeStep.data.plot_image && (
                            <div className="bg-white p-5 rounded-xl border shadow-sm flex flex-col items-center relative group">
                                <ChartCustomizer
                                    runId={runId}
                                    datasetId={datasetId}
                                    stepId={activeStep.id}
                                    currentImage={activeStep.data.plot_image}
                                    onUpdate={(newImg) => {
                                        // Update local state is tricky here without re-fetch or deep mutation
                                        // For MVP, we can trigger a refetch or simple forceUpdate simulation?
                                        // Better: Update results state
                                        const newRes = { ...results };
                                        newRes.results[activeStep.id].plot_image = newImg;
                                        setResults(newRes);
                                    }}
                                />
                                <h4 className="text-lg font-bold text-gray-900 mb-4">Kaplan-Meier Survival Curve</h4>
                                <img
                                    src={`data:image/png;base64,${activeStep.data.plot_image}`}
                                    alt="Survival Curve"
                                    className="max-w-full rounded-lg border shadow-sm"
                                />
                            </div>
                        )}

                        {/* Interpretation */}
                        {!isBatchMode && activeStep.p_value !== undefined && (
                            <InterpretationCard
                                pValue={activeStep.p_value}
                                methodId={activeStep.method}
                                effectSize={activeStep.effect_size}
                            />
                        )}

                        {/* Main Results Table */}
                        <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
                            <div className="px-5 py-3 border-b bg-gray-50 flex justify-between items-center">
                                <h4 className="text-sm font-semibold text-gray-700">Survival Statistics</h4>
                                {activeStep.data.p_value !== null && (
                                    <span className={`text-sm font-medium px-2 py-1 rounded ${activeStep.data.p_value < 0.05 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                                        Log-Rank P: {activeStep.data.p_value.toFixed(4)}
                                    </span>
                                )}
                            </div>
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Group</th>
                                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Median Survival Time</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {Object.entries(activeStep.data.median_survival || {}).map(([grp, time], idx) => (
                                        <tr key={idx}>
                                            <td className="px-6 py-4 text-sm font-medium text-gray-900">{grp}</td>
                                            <td className="px-6 py-4 text-sm text-right text-gray-500">{time}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

            </div>
        </>
    );
};

/* --- Simple Table for descriptive stats --- */
const SimpleTable = ({ data }) => {
    if (!data) return <div>Нет данных</div>;
    const groups = Object.keys(data).filter(k => k !== 'overall');

    return (
        <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                    <tr>
                        <th className="px-4 py-2 text-left font-medium text-gray-600">Группа</th>
                        <th className="px-4 py-2 text-center font-medium text-gray-600">n</th>
                        <th className="px-4 py-2 text-center font-medium text-gray-600">Mean±SD</th>
                        <th className="px-4 py-2 text-center font-medium text-gray-600">Median</th>
                        <th className="px-4 py-2 text-center font-medium text-gray-600">Min-Max</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                    {groups.map(g => {
                        const s = data[g] || {};
                        return (
                            <tr key={g}>
                                <td className="px-4 py-2 font-medium">{g}</td>
                                <td className="px-4 py-2 text-center">{s.count || '—'}</td>
                                <td className="px-4 py-2 text-center">
                                    {s.mean?.toFixed(1) || '—'}±{s.std?.toFixed(1) || '—'}
                                </td>
                                <td className="px-4 py-2 text-center">{s.median?.toFixed(1) || '—'}</td>
                                <td className="px-4 py-2 text-center">
                                    {s.min?.toFixed(1) || '—'} – {s.max?.toFixed(1) || '—'}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
};

/* --- Test Result display --- */
const TestResult = ({ data }) => {
    const formatP = (p) => {
        if (p < 0.001) return '<0.001';
        if (p < 0.01) return p.toFixed(3);
        return p.toFixed(2);
    };

    return (
        <div className="flex items-center space-x-6 p-4 bg-gray-50 rounded-lg">
            <div className={`p-3 rounded-full ${data.significant ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>
                <BeakerIcon className="w-6 h-6" />
            </div>
            <div>
                <h4 className="font-semibold text-gray-900">{data.method?.name || "Test"}</h4>
                <p className="text-sm text-gray-500">
                    {data.significant ? "Статистически значимо" : "Различий не выявлено"}
                </p>
            </div>
            <div className="ml-auto text-right">
                <div className={`text-2xl font-bold ${data.significant ? 'text-green-600' : 'text-gray-600'}`}>
                    p = {formatP(data.p_value)}
                </div>
            </div>
        </div>
    );
};

export default StepResults;
