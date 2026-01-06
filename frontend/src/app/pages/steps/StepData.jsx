import React, { useState, useEffect } from 'react';
import { getDatasets, getDataset, scanDataset as getScanReport, cleanColumn } from '@/lib/api';
import { DocumentIcon, ArrowPathIcon, ExclamationTriangleIcon, SparklesIcon } from '@heroicons/react/24/outline';

/* -- HELPER: Cleaning Alert -- */
const CleaningWizardAlert = ({ report, onFix }) => {
    if (!report || !report.issues || report.issues.length === 0) return null;

    return (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4 animate-fadeIn">
            <div className="flex items-start">
                <ExclamationTriangleIcon className="w-5 h-5 text-amber-500 mt-0.5 mr-3" />
                <div className="flex-1">
                    <h3 className="text-sm font-semibold text-amber-900">
                        Data Quality Issues Detected
                    </h3>
                    <div className="mt-2 space-y-2">
                        {report.issues.map((issue, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm text-amber-800 bg-amber-100 p-2 rounded">
                                <span>
                                    <strong>{issue.column}</strong>: {issue.details}
                                </span>
                                <button
                                    onClick={() => onFix(issue.column, "to_numeric")}
                                    className="ml-4 flex items-center px-3 py-1 bg-white border border-amber-300 rounded hover:bg-amber-50 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 transition-colors"
                                >
                                    <SparklesIcon className="w-3 h-3 mr-1.5 inline" />
                                    Auto-Fix
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

/* -- HELPER: Variable Mapper -- */
const VariableMapper = ({ columns, goal, variables, setVariables }) => {
    // Define required fields based on goal
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
        } else {
            setColumns([]);
            setScanReport(null);
        }
    }, [selectedDataset]);

    const handleClean = async (column, action) => {
        try {
            // Apply fix
            const newProfile = await cleanColumn(selectedDataset, column, action);
            // Refresh columns and report
            setColumns(newProfile.columns || []);
            const newReport = await getScanReport(selectedDataset);
            setScanReport(newReport);
        } catch (e) {
            alert("Fix failed: " + e.message);
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

                <CleaningWizardAlert report={scanReport} onFix={handleClean} />

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
