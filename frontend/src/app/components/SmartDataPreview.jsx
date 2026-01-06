import React, { useState, useEffect } from 'react';
import {
    ExclamationTriangleIcon,
    ShieldCheckIcon,
    TableCellsIcon,
    ArrowPathIcon,
    CheckCircleIcon
} from '@heroicons/react/24/outline';
import { analyzeDatasetPrep, applyDatasetPrep } from '../../lib/api';

const SmartDataPreview = ({ datasetId, onComplete }) => {
    const [analysis, setAnalysis] = useState(null);
    const [loading, setLoading] = useState(true);
    const [processing, setProcessing] = useState(false);
    const [message, setMessage] = useState(null);

    useEffect(() => {
        loadAnalysis();
    }, [datasetId]);

    const loadAnalysis = async () => {
        try {
            const data = await analyzeDatasetPrep(datasetId);
            setAnalysis(data);

            // Auto-complete if clean? 
            // Maybe not, let user see preview.
            if (data.pii_columns.length === 0 && data.structure_suggestion.type === 'clean') {
                // onComplete(); // Uncomment to auto-skip if clean
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleAction = async (action, params = {}) => {
        setProcessing(true);
        setMessage(null);
        try {
            await applyDatasetPrep(datasetId, action, params);
            setMessage({ type: 'success', text: 'Action applied successfully!' });
            // Reload analysis to see next state
            await loadAnalysis();
        } catch (err) {
            setMessage({ type: 'error', text: 'Action failed: ' + err.message });
        } finally {
            setProcessing(false);
        }
    };

    if (loading) return <div className="p-6 text-center text-gray-500">Analyzing dataset structure...</div>;
    if (!analysis) return null;

    const { pii_columns, structure_suggestion, preview_rows } = analysis;
    const hasPii = pii_columns.length > 0;
    const isWide = structure_suggestion.type === 'wide';

    if (!hasPii && !isWide) {
        return (
            <div className="text-center p-6 space-y-4">
                <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto">
                    <CheckCircleIcon className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-gray-900">Dataset Looks Good!</h3>
                <p className="text-sm text-gray-500">No PII or structural issues detected.</p>
                <button
                    onClick={onComplete}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                >
                    Continue to Analysis
                </button>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-xl shadow-sm border p-6 space-y-6 animate-fadeIn">
            <h2 className="text-xl font-bold flex items-center gap-2">
                <span className="text-2xl">🪄</span> Smart Data Import
            </h2>

            {/* PII SECTION */}
            {hasPii && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <ExclamationTriangleIcon className="w-6 h-6 text-red-600 mt-0.5" />
                        <div className="flex-1">
                            <h3 className="font-bold text-red-900">PII Detected</h3>
                            <p className="text-sm text-red-700 mt-1">
                                We found personal data columns: <b>{pii_columns.join(', ')}</b>.
                            </p>
                            <div className="mt-3 flex gap-3">
                                <button
                                    onClick={() => handleAction('sanitize')}
                                    disabled={processing}
                                    className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 flex items-center gap-2"
                                >
                                    <ShieldCheckIcon className="w-4 h-4" />
                                    Mask Data (Recommended)
                                </button>
                                <button
                                    onClick={() => setAnalysis({ ...analysis, pii_columns: [] })} // Ignore locally
                                    className="px-4 py-2 text-red-700 hover:bg-red-100 rounded-md text-sm"
                                >
                                    Ignore
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* STRUCTURE SECTION */}
            {isWide && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <TableCellsIcon className="w-6 h-6 text-blue-600 mt-0.5" />
                        <div className="flex-1">
                            <h3 className="font-bold text-blue-900">Wide Format Detected</h3>
                            <p className="text-sm text-blue-700 mt-1">
                                It looks like you have measurements in columns (e.g., T1, T2).
                                For statistical analysis, we recommend transforming this to Long Format.
                            </p>
                            <div className="mt-2 text-sm text-blue-800 bg-blue-100 p-2 rounded">
                                <strong>Suggestion:</strong> Melt
                                {structure_suggestion.melt_candidates.map(g =>
                                    ` "${g.prefix}" (${g.cols.length} cols)`
                                ).join(', ')}
                            </div>
                            <div className="mt-3 flex gap-3">
                                <button
                                    onClick={() => handleAction('melt', {
                                        groups: structure_suggestion.melt_candidates,
                                        value_vars: structure_suggestion.melt_candidates[0].cols // MVP: Handle first group
                                    })}
                                    disabled={processing}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 flex items-center gap-2"
                                >
                                    <ArrowPathIcon className="w-4 h-4" />
                                    Fix Structure
                                </button>
                                <button
                                    onClick={() => setAnalysis({ ...analysis, structure_suggestion: { type: 'clean' } })}
                                    className="px-4 py-2 text-blue-700 hover:bg-blue-100 rounded-md text-sm"
                                >
                                    Keep as is
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* PREVIEW SECTION */}
            <div>
                <h4 className="font-semibold text-gray-700 mb-2 text-sm uppercase">Data Preview</h4>
                <div className="overflow-x-auto border rounded-lg">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                        <thead className="bg-gray-50">
                            <tr>
                                {Object.keys(preview_rows[0] || {}).map(col => (
                                    <th key={col} className="px-4 py-2 text-left font-medium text-gray-500 whitespace-nowrap">
                                        {col}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 bg-white">
                            {preview_rows.map((row, i) => (
                                <tr key={i}>
                                    {Object.values(row).map((val, j) => (
                                        <td key={j} className="px-4 py-2 whitespace-nowrap text-gray-700">
                                            {String(val)}
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Continue Button (If issues resolved or ignored) */}
            {(!hasPii && !isWide) && (
                <div className="flex justify-end pt-4">
                    <button
                        onClick={onComplete}
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                    >
                        Continue to Analysis
                    </button>
                </div>
            )}
        </div>
    );
};

export default SmartDataPreview;
