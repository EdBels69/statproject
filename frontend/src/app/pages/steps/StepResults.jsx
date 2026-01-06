import React, { useState, useEffect } from 'react';
import { getAnalysisResults } from '../../../lib/api';
import VisualizePlot from '../../components/VisualizePlot';
import {
    TableCellsIcon,
    ChartBarIcon,
    BeakerIcon,
    ArrowDownTrayIcon
} from '@heroicons/react/24/outline';

/* --- SUB-COMPONENT: TABLE 1 (Descriptive) --- */
const Table1View = ({ data }) => {
    if (!data || !data.data) return <div>No Data</div>;
    const stats = data.data; // { "A": {mean, ...}, "B": {mean...}, "overall": {} }
    const groups = Object.keys(stats).filter(k => k !== 'overall');

    return (
        <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                    <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Metric</th>
                        {groups.map(g => (
                            <th key={g} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Group {g} (n={stats[g]?.count || 0})
                            </th>
                        ))}
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-100">
                            Overall (n={stats['overall']?.count || 0})
                        </th>
                    </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                    {['Mean (SD)', 'Median [Q1, Q3]', 'Min - Max', '95% CI'].map((rowLabel) => (
                        <tr key={rowLabel}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{rowLabel}</td>
                            {groups.map(g => {
                                const s = stats[g];
                                let val = "";
                                if (rowLabel === 'Mean (SD)') val = `${s.mean.toFixed(2)} (${s.std.toFixed(2)})`;
                                if (rowLabel === 'Median [Q1, Q3]') val = `${s.median.toFixed(2)} [${s.q1.toFixed(2)}, ${s.q3.toFixed(2)}]`;
                                if (rowLabel === 'Min - Max') val = `${s.min.toFixed(2)} - ${s.max.toFixed(2)}`;
                                if (rowLabel === '95% CI') val = `${s.ci_lower?.toFixed(2)} - ${s.ci_upper?.toFixed(2)}`;
                                return <td key={g} className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{val}</td>
                            })}
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 bg-gray-50">
                                {rowLabel === 'Mean (SD)' ? `${stats.overall.mean.toFixed(2)}` : '-'}
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

/* --- SUB-COMPONENT: HYPOTHESIS TEST --- */
const CompareView = ({ result }) => {
    return (
        <div className="space-y-6">
            <div className="flex items-center space-x-4 p-4 bg-gray-50 rounded-lg">
                <div className={`p-2 rounded-full ${result.significant ? 'bg-green-100 text-green-700' : 'bg-gray-200 text-gray-600'}`}>
                    <BeakerIcon className="w-6 h-6" />
                </div>
                <div>
                    <h4 className="text-lg font-semibold text-gray-900">{result.method?.name || "Test Result"}</h4>
                    <p className="text-sm text-gray-500">
                        {result.significant ? "Statistically Significant Difference found." : "No significant difference detected."}
                    </p>
                </div>
                <div className="ml-auto text-right">
                    <div className="text-2xl font-bold text-indigo-600">p = {result.p_value?.toFixed(4) || "N/A"}</div>
                    <div className="text-xs text-gray-400 uppercase tracking-wide">P-Value</div>
                </div>
            </div>

            <div className="h-80 border rounded-lg p-4 bg-white">
                <VisualizePlot
                    data={result.plot_data || []}
                    type={result.method?.type === 'parametric' ? 'bar' : 'box'} // dynamic
                    stats={result.groups}
                />
            </div>
        </div>
    );
};

/* --- MAIN DASHBOARD --- */
const StepResults = ({ runId, datasetId, goal }) => {
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState(0);

    useEffect(() => {
        if (runId && datasetId) {
            getAnalysisResults(datasetId, runId)
                .then(setResults)
                .catch(console.error)
                .finally(() => setLoading(false));
        }
    }, [runId, datasetId]);

    if (loading) return <div className="p-10 text-center animate-pulse">Loading Results...</div>;
    if (!results) return <div className="p-10 text-center text-red-500">Failed to load results.</div>;

    // Convert results map to array for tabs
    // Expected keys: "desc_stats", "hypothesis_test", etc.
    const steps = Object.keys(results.results).map(key => ({
        id: key,
        data: results.results[key],
        label: key.replace(/_/g, ' ').toUpperCase()
    }));

    const activeStep = steps[activeTab];

    return (
        <div className="animate-fadeIn min-h-screen pb-20">
            {/* Header */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900">{results.protocol_name}</h2>
                    <p className="text-gray-500 text-sm">run_id: {runId}</p>
                </div>
                <button
                    onClick={() => window.open(`http://localhost:8000/api/v1/analysis/report/${runId}/html?dataset_id=${datasetId}`, '_blank')}
                    className="flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                    <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                    Export Report
                </button>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200 mb-6">
                <nav className="-mb-px flex space-x-8">
                    {steps.map((step, idx) => (
                        <button
                            key={step.id}
                            onClick={() => setActiveTab(idx)}
                            className={`
                                py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap transition-colors
                                ${activeTab === idx
                                    ? 'border-indigo-500 text-indigo-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}
                            `}
                        >
                            {step.label}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Content Body */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                {activeStep.data.type === 'table_1' && (
                    <Table1View data={activeStep.data} />
                )}

                {(activeStep.data.p_value !== undefined) && (
                    <CompareView result={activeStep.data} />
                )}

                {activeStep.data.error && (
                    <div className="text-red-500 p-4 bg-red-50 rounded">
                        Analysis Error: {activeStep.data.error}
                    </div>
                )}

                {/* Fallback JSON view for debugging or unknown types */}
                {!['table_1'].includes(activeStep.data.type) && activeStep.data.p_value === undefined && (
                    <pre className="text-xs bg-gray-50 p-4 rounded overflow-auto max-h-96">
                        {JSON.stringify(activeStep.data, null, 2)}
                    </pre>
                )}
            </div>
        </div>
    );
};

export default StepResults;
