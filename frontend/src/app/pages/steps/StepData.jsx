import React, { useState, useEffect } from 'react';
import { getDatasets, getDataset, getScanReport, cleanColumn, imputeMice } from '@/lib/api';
import { DocumentIcon, ExclamationTriangleIcon, SparklesIcon } from '@heroicons/react/24/outline';

/* -- HELPER: Cleaning Alert -- */
const CleaningWizardAlert = ({ report, onFix, onMice }) => {
    if (!report) return null;

    const issues = Array.isArray(report.issues) ? report.issues : [];
    const hasIssues = issues.length > 0;
    const missingReport = report.missing_report;
    const missingByColumn = Array.isArray(missingReport?.by_column) ? missingReport.by_column : [];
    const hasMissing = missingByColumn.length > 0;

    if (!hasIssues && !hasMissing) return null;

    const isNumericColumn = (columnName) => {
        const col = report?.columns?.[columnName];
        const t = String(col?.type || '').toLowerCase();
        return t.includes('int') || t.includes('float');
    };

    return (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4 animate-fadeIn">
            <div className="flex items-start">
                <ExclamationTriangleIcon className="w-5 h-5 text-amber-500 mt-0.5 mr-3" />
                <div className="flex-1">
                    <h3 className="text-sm font-semibold text-amber-900">Data Preparation</h3>

                    {hasMissing && (
                        <div className="mt-3">
                            <div className="flex items-center justify-between gap-3">
                                <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-amber-700/80">Missing Values</div>
                                <button
                                    type="button"
                                    onClick={() => {
                                        const cols = missingByColumn
                                            .map(m => m?.column)
                                            .filter(Boolean)
                                            .filter(isNumericColumn);
                                        if (cols.length > 0) onMice(cols);
                                    }}
                                    className="px-2 py-1 rounded border border-amber-300 bg-white text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
                                >
                                    MICE
                                </button>
                            </div>
                            <div className="mt-2 space-y-2">
                                {missingByColumn.slice(0, 8).map((m) => (
                                    <div key={m.column} className="flex items-center justify-between gap-3 text-sm text-amber-900 bg-amber-100/70 p-2 rounded">
                                        <div className="min-w-0">
                                            <div className="truncate font-semibold">{m.column}</div>
                                            <div className="text-xs text-amber-800/80">{m.missing_count} missing ({m.missing_percent}%)</div>
                                        </div>

                                        <div className="flex items-center gap-1.5 shrink-0">
                                            {isNumericColumn(m.column) && (
                                                <>
                                                    <button
                                                        onClick={() => onFix(m.column, 'fill_mean')}
                                                        className="px-2 py-1 rounded border border-amber-300 bg-white text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
                                                    >
                                                        Mean
                                                    </button>
                                                    <button
                                                        onClick={() => onFix(m.column, 'fill_median')}
                                                        className="px-2 py-1 rounded border border-amber-300 bg-white text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
                                                    >
                                                        Median
                                                    </button>
                                                </>
                                            )}
                                            <button
                                                onClick={() => onFix(m.column, 'fill_locf')}
                                                className="px-2 py-1 rounded border border-amber-300 bg-white text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
                                            >
                                                LOCF
                                            </button>
                                            <button
                                                onClick={() => onFix(m.column, 'fill_nocb')}
                                                className="px-2 py-1 rounded border border-amber-300 bg-white text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
                                            >
                                                NOCB
                                            </button>
                                            <button
                                                onClick={() => onFix(m.column, 'drop_na')}
                                                className="px-2 py-1 rounded border border-amber-300 bg-white text-[11px] font-semibold text-amber-900 hover:bg-amber-50"
                                            >
                                                Drop
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {hasIssues && (
                        <div className="mt-4">
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-amber-700/80">Type Issues</div>
                            <div className="mt-2 space-y-2">
                                {issues.filter(i => i?.type === 'mixed_type').slice(0, 8).map((issue, idx) => (
                                    <div key={`${issue.column}-${idx}`} className="flex items-center justify-between text-sm text-amber-800 bg-amber-100 p-2 rounded">
                                        <span>
                                            <strong>{issue.column}</strong>: {issue.details}
                                        </span>
                                        <button
                                            onClick={() => onFix(issue.column, "to_numeric")}
                                            className="ml-4 flex items-center px-3 py-1 rounded text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
                                        >
                                            <SparklesIcon className="w-3 h-3 mr-1.5 inline" />
                                            To Numeric
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

/* -- HELPER: Variable Mapper -- */
const VariableMapper = ({ columns, goal, variables, setVariables }) => {
    const fields = {
        compare_groups: [
            { key: 'target', label: 'Dependent Variable (Outcome)', type: 'numeric' },
            { key: 'group', label: 'Grouping Factor', type: 'categorical' },
        ],
        relationship: [
            { key: 'target', label: 'Variable Y (Outcome)', type: 'numeric' },
            { key: 'predictor', label: 'Variable X (Predictor)', type: 'numeric' },
        ],
        prediction: [
            { key: 'target', label: 'Outcome to Predict', type: 'numeric' },
            { key: 'predictors', label: 'Predictors (Select Multiple)', type: 'mixed', multiple: true },
        ],
        survival: [
            { key: 'duration', label: 'Time to Event', type: 'numeric' },
            { key: 'event', label: 'Event Status (0/1)', type: 'binary' },
            { key: 'group', label: 'Group (Optional)', type: 'categorical' },
        ],
        repeated_measures: [
            { key: 'target', label: 'Dependent Variable (Outcome)', type: 'numeric' },
            { key: 'time', label: 'Timepoint / Condition', type: 'categorical' },
            { key: 'subject', label: 'Subject ID (Repeated Measures)', type: 'categorical' },
        ]
    }[goal] || [];

    const handleSelect = (key, value, isMultiple = false) => {
        if (isMultiple) {
            // value passed here is just the clicked item
            setVariables(prev => {
                const current = prev[key] ? prev[key].split(',').filter(Boolean) : [];
                let next;
                if (current.includes(value)) {
                    next = current.filter(v => v !== value);
                } else {
                    next = [...current, value];
                }
                return { ...prev, [key]: next.join(',') };
            });
        } else {
            setVariables(prev => ({ ...prev, [key]: value }));
        }
    };

    return (
        <div className="space-y-6 animate-fadeIn">
            {fields.map((field) => (
                <div key={field.key} className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                        {field.label}
                    </label>

                    {field.multiple ? (
                        <div className="border border-gray-200 rounded-lg p-3 max-h-60 overflow-y-auto bg-gray-50">
                            {columns.map(col => {
                                const isSelected = (variables[field.key] || '').split(',').includes(col);
                                return (
                                    <label key={col} className="flex items-center space-x-3 p-2 hover:bg-white rounded cursor-pointer transition-colors">
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => handleSelect(field.key, col, true)}
                                            className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                                        />
                                        <span className={`text-sm ${isSelected ? 'text-blue-700 font-medium' : 'text-gray-600'}`}>
                                            {col}
                                        </span>
                                    </label>
                                );
                            })}
                        </div>
                    ) : (
                        <select
                            className="w-full p-2.5 bg-white border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow"
                            value={variables[field.key] || ''}
                            onChange={(e) => handleSelect(field.key, e.target.value)}
                        >
                            <option value="">Select a variable...</option>
                            {columns.map(col => (
                                <option key={col} value={col}>{col}</option>
                            ))}
                        </select>
                    )}
                </div>
            ))}
        </div>
    );
};

/* -- STEP 2 CONTAINER -- */
const StepData = ({ goal, onDataReady, onNext }) => {
    const [datasets, setDatasets] = useState([]);
    const [selectedDataset, setSelectedDataset] = useState(null);
    const [columns, setColumns] = useState([]);
    const [variables, setVariables] = useState({});
    const [loading, setLoading] = useState(true);
    const [scanReport, setScanReport] = useState(null);

    // Load datasets on mount
    useEffect(() => {
        getDatasets()
            .then(setDatasets)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    // Load columns and scan report when dataset is selected
    useEffect(() => {
        if (selectedDataset) {
            getDataset(selectedDataset)
                .then(profile => {
                    // Handle both string[] and {name: string}[] formats
                    const cols = (profile.columns || []).map(c =>
                        typeof c === 'string' ? c : c.name
                    );
                    setColumns(cols);
                })
                .catch(console.error);

            getScanReport(selectedDataset)
                .then(setScanReport)
                .catch(err => console.error("Scan report load failed", err));
        }
    }, [selectedDataset]);

    const handleClean = async (column, action) => {
        try {
            // Apply fix
            const newProfile = await cleanColumn(selectedDataset, column, action);
            // Refresh columns and report
            const cols = (newProfile.columns || []).map(c => (typeof c === 'string' ? c : c.name));
            setColumns(cols);
            const newReport = await getScanReport(selectedDataset);
            setScanReport(newReport);
        } catch (e) {
            alert("Fix failed: " + e.message);
        }
    };

    const handleMice = async (cols) => {
        try {
            const newProfile = await imputeMice(selectedDataset, cols);
            const nextCols = (newProfile.columns || []).map(c => (typeof c === 'string' ? c : c.name));
            setColumns(nextCols);
            const newReport = await getScanReport(selectedDataset);
            setScanReport(newReport);
        } catch (e) {
            alert("MICE failed: " + e.message);
        }
    };

    // Notify parent when valid configuration is ready
    useEffect(() => {
        onDataReady({ datasetId: selectedDataset, variables });
    }, [selectedDataset, variables, onDataReady]);

    if (loading) return <div>Loading...</div>;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* LEFT: Dataset Selection */}
            <div className="lg:col-span-1 border-r border-gray-100 pr-8">
                <h3 className="text-lg font-semibold mb-4">1. Select Dataset</h3>
                <div className="space-y-3">
                    {datasets.map(ds => (
                        <div
                            key={ds.id}
                            onClick={() => setSelectedDataset(ds.id)}
                            className={`p-4 rounded-lg border cursor-pointer flex items-center space-x-3 transition-colors ${selectedDataset === ds.id
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 hover:bg-gray-50'
                                }`}
                        >
                            <DocumentIcon className={`w-5 h-5 ${selectedDataset === ds.id ? 'text-blue-600' : 'text-gray-400'}`} />
                            <div className="truncate text-sm font-medium">{ds.filename}</div>
                        </div>
                    ))}
                </div>
            </div>

            {/* RIGHT: Variable Mapping */}
            <div className="lg:col-span-2 pl-4 flex flex-col h-full">
                <h3 className="text-lg font-semibold mb-4">2. Map Variables</h3>

                <CleaningWizardAlert report={scanReport} onFix={handleClean} onMice={handleMice} />

                {!selectedDataset ? (
                    <div className="text-gray-400 text-sm italic py-10 bg-gray-50 rounded-lg text-center border border-dashed border-gray-200">
                        Please select a dataset to continue
                    </div>
                ) : (
                    <>
                        <VariableMapper
                            columns={columns}
                            goal={goal}
                            variables={variables}
                            setVariables={setVariables}
                        />

                        <div className="mt-8 flex justify-end">
                            <button
                                onClick={onNext}
                                disabled={Object.keys(variables).length === 0} // Simple check
                                className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            >
                                Review Protocol →
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default StepData;
