import React, { useState } from 'react';
import { ArrowDownTrayIcon, CheckIcon, XMarkIcon, InformationCircleIcon, DocumentTextIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

/**
 * BatchResultsTable - Summary table for batch analysis results
 * Shows all variables in one compact table with toggleable columns
 */
const BatchResultsTable = ({ results, onExportSelection }) => {
    // Toggle states for columns
    const [showMean, setShowMean] = useState(true);
    const [showMedian, setShowMedian] = useState(false);
    const [showQuartiles, setShowQuartiles] = useState(false);

    // Selected rows for export
    const [selectedRows, setSelectedRows] = useState(new Set());

    // Extract all results into flat array
    const rows = [];
    const resultEntries = Object.entries(results || {});

    for (const [stepId, stepData] of resultEntries) {
        // Only process test results (not descriptive)
        if (stepId.startsWith('test_') && stepData) {
            const varName = stepId.replace('test_', '');

            // Find corresponding descriptive stats
            const descKey = `desc_${varName}`;
            const descData = results[descKey]?.data || {};

            // Get groups
            const groups = Object.keys(descData).filter(k => k !== 'overall');

            // Calculate differences if 2 groups
            let deltaPercent = null;
            let deltaAbs = null;
            let groupAStats = null;
            let groupBStats = null;

            if (groups.length >= 2) {
                groupAStats = descData[groups[0]];
                groupBStats = descData[groups[1]];

                if (groupAStats?.mean && groupBStats?.mean) {
                    deltaAbs = groupBStats.mean - groupAStats.mean;
                    deltaPercent = ((groupBStats.mean - groupAStats.mean) / groupAStats.mean) * 100;
                }
            }

            rows.push({
                id: stepId,
                variable: varName,
                groups: groups,
                groupAStats,
                groupBStats,
                pValue: stepData.p_value,
                significant: stepData.significant,
                method: stepData.method?.name || 'Auto',
                deltaPercent,
                deltaAbs,
                conclusion: stepData.conclusion,
                error: stepData.error,
                warnings: stepData.warnings || [],
                subgroup: stepData.subgroup
            });
        }
    }

    const hasSubgroups = rows.some(r => r.subgroup);

    // Format p-value (APA style)
    const formatP = (p) => {
        if (p === null || p === undefined) return '—';
        if (p < 0.001) return '<0.001';
        if (p < 0.01) return p.toFixed(3);
        return p.toFixed(2);
    };

    // Format number
    const formatNum = (n, decimals = 1) => {
        if (n === null || n === undefined) return '—';
        return n.toFixed(decimals);
    };

    // Toggle row selection
    const toggleRow = (id) => {
        const newSelected = new Set(selectedRows);
        if (newSelected.has(id)) {
            newSelected.delete(id);
        } else {
            newSelected.add(id);
        }
        setSelectedRows(newSelected);
    };

    // Select/deselect all
    const selectAll = () => setSelectedRows(new Set(rows.map(r => r.id)));
    const deselectAll = () => setSelectedRows(new Set());

    if (rows.length === 0) {
        return <div className="text-center text-gray-500 py-10">Нет данных для отображения</div>;
    }

    return (
        <div className="space-y-4">
            {/* Controls */}
            <div className="flex flex-wrap items-center gap-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">Показать:</span>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={showMean}
                            onChange={(e) => setShowMean(e.target.checked)}
                            className="rounded text-blue-600"
                        />
                        <span className="text-sm">Mean±SD</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={showMedian}
                            onChange={(e) => setShowMedian(e.target.checked)}
                            className="rounded text-blue-600"
                        />
                        <span className="text-sm">Median</span>
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={showQuartiles}
                            onChange={(e) => setShowQuartiles(e.target.checked)}
                            className="rounded text-blue-600"
                        />
                        <span className="text-sm">Q1-Q3</span>
                    </label>
                </div>

                <div className="flex items-center gap-2 ml-auto">
                    <button onClick={selectAll} className="text-xs text-blue-600 hover:underline">
                        Выбрать все
                    </button>
                    <button onClick={deselectAll} className="text-xs text-gray-500 hover:underline">
                        Очистить
                    </button>
                    <span className="text-xs text-gray-400">
                        В отчёт: {selectedRows.size} / {rows.length}
                    </span>
                </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto border rounded-lg">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-3 py-3 text-left text-xs font-semibold text-gray-600 uppercase">Переменная</th>
                            {hasSubgroups && <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">Подгруппа</th>}
                            <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">n</th>
                            {rows[0]?.groups.slice(0, 2).map((g, i) => (
                                <th key={g} className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase max-w-[150px] truncate" title={g}>
                                    {g.length > 20 ? g.substring(0, 18) + '...' : g}
                                </th>
                            ))}
                            <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">Δ%</th>
                            <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">Δабс</th>
                            <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">p</th>
                            <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">AI</th>
                            <th className="px-3 py-3 text-center text-xs font-semibold text-gray-600 uppercase">✓</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-100">
                        {rows.map((row) => {
                            const isSignificant = row.pValue !== null && row.pValue < 0.05;

                            return (
                                <tr
                                    key={row.id}
                                    className={`hover:bg-gray-50 ${row.error ? 'bg-red-50' : ''}`}
                                    title={row.conclusion || row.error || ''}
                                >
                                    <td className="px-3 py-2 text-sm font-medium text-gray-900 max-w-[200px] truncate">
                                        {row.variable}
                                    </td>
                                    {hasSubgroups && (
                                        <td className="px-3 py-2 text-sm text-center font-medium text-blue-600">
                                            {row.subgroup || '—'}
                                        </td>
                                    )}
                                    <td className="px-3 py-2 text-sm text-center text-gray-500">
                                        {row.groupAStats?.count || '—'}
                                    </td>

                                    {/* Group A */}
                                    <td className="px-3 py-2 text-sm text-center text-gray-700">
                                        {row.groupAStats ? (
                                            <div className="space-y-0.5">
                                                {showMean && <div>{formatNum(row.groupAStats.mean)}±{formatNum(row.groupAStats.std)}</div>}
                                                {showMedian && <div className="text-gray-500">{formatNum(row.groupAStats.median)}</div>}
                                                {showQuartiles && <div className="text-xs text-gray-400">[{formatNum(row.groupAStats.q1)}-{formatNum(row.groupAStats.q3)}]</div>}
                                            </div>
                                        ) : '—'}
                                    </td>

                                    {/* Group B */}
                                    <td className="px-3 py-2 text-sm text-center text-gray-700">
                                        {row.groupBStats ? (
                                            <div className="space-y-0.5">
                                                {showMean && <div>{formatNum(row.groupBStats.mean)}±{formatNum(row.groupBStats.std)}</div>}
                                                {showMedian && <div className="text-gray-500">{formatNum(row.groupBStats.median)}</div>}
                                                {showQuartiles && <div className="text-xs text-gray-400">[{formatNum(row.groupBStats.q1)}-{formatNum(row.groupBStats.q3)}]</div>}
                                            </div>
                                        ) : '—'}
                                    </td>

                                    {/* Delta % */}
                                    <td className={`px-3 py-2 text-sm text-center font-medium ${row.deltaPercent > 0 ? 'text-green-600' : row.deltaPercent < 0 ? 'text-red-600' : 'text-gray-500'
                                        }`}>
                                        {row.deltaPercent !== null ? `${row.deltaPercent > 0 ? '+' : ''}${formatNum(row.deltaPercent)}%` : '—'}
                                    </td>

                                    {/* Delta Abs */}
                                    <td className={`px-3 py-2 text-sm text-center ${row.deltaAbs > 0 ? 'text-green-600' : row.deltaAbs < 0 ? 'text-red-600' : 'text-gray-500'
                                        }`}>
                                        {row.deltaAbs !== null ? `${row.deltaAbs > 0 ? '+' : ''}${formatNum(row.deltaAbs, 2)}` : '—'}
                                    </td>

                                    {/* P-value */}
                                    <td className={`px-3 py-2 text-sm text-center font-medium ${isSignificant ? 'text-green-700 bg-green-50' : 'text-gray-600'
                                        }`}>
                                        {row.error ? <span className="text-red-500">err</span> : formatP(row.pValue)}
                                    </td>

                                    {/* AI Comment & Warnings */}
                                    <td className="px-3 py-2 text-center">
                                        <div className="flex justify-center items-center gap-2">
                                            {/* AI */}
                                            {row.conclusion && (
                                                <div className="relative group">
                                                    <InformationCircleIcon className="w-5 h-5 text-blue-500 cursor-help" />
                                                    <div className="absolute z-50 hidden group-hover:block bg-gray-900 text-white text-xs rounded-lg p-3 w-64 -left-28 bottom-8 shadow-xl">
                                                        <div className="font-medium mb-1">💡 AI Интерпретация:</div>
                                                        {row.conclusion}
                                                        <div className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-2 h-2 bg-gray-900 rotate-45"></div>
                                                    </div>
                                                </div>
                                            )}

                                            {/* Warnings */}
                                            {row.warnings && row.warnings.length > 0 && (
                                                <div className="relative group">
                                                    <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500 cursor-help" />
                                                    <div className="absolute z-50 hidden group-hover:block bg-yellow-50 text-yellow-800 border border-yellow-200 text-xs rounded-lg p-3 w-64 -left-28 bottom-8 shadow-xl">
                                                        <div className="font-medium mb-1">⚠️ Обратите внимание:</div>
                                                        <ul className="list-disc pl-4 space-y-1">
                                                            {row.warnings.map((w, i) => <li key={i}>{w}</li>)}
                                                        </ul>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </td>

                                    {/* Checkbox */}
                                    <td className="px-3 py-2 text-center">
                                        <button
                                            onClick={() => toggleRow(row.id)}
                                            className={`w-6 h-6 rounded flex items-center justify-center transition-colors ${selectedRows.has(row.id)
                                                ? 'bg-blue-600 text-white'
                                                : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                                                }`}
                                        >
                                            {selectedRows.has(row.id) && <CheckIcon className="w-4 h-4" />}
                                        </button>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {/* Summary + Action */}
            <div className="flex justify-between items-center">
                <div className="text-sm text-gray-600">
                    Всего: {rows.length} переменных |
                    Значимых (p&lt;0.05): {rows.filter(r => r.pValue < 0.05).length}
                </div>

                {selectedRows.size > 0 && (
                    <button
                        onClick={() => onExportSelection && onExportSelection(
                            rows.filter(r => selectedRows.has(r.id)),
                            { showMean, showMedian, showQuartiles }
                        )}
                        className="flex items-center px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors shadow-sm"
                    >
                        <DocumentTextIcon className="w-4 h-4 mr-2" />
                        Сформировать отчёт ({selectedRows.size})
                    </button>
                )}
            </div>
        </div>
    );
};

export default BatchResultsTable;
