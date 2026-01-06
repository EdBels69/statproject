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
const VariableMapper = ({ columns, goal, variables, setVariables, batchMode, setBatchMode }) => {
    // Define required fields based on goal
    const getFields = () => {
        if (goal === 'compare_groups') {
            return batchMode
                ? [
                    { key: 'targets', label: 'Зависимые переменные (выберите несколько)', type: 'numeric', multiple: true },
                    { key: 'group', label: 'Группирующая переменная', type: 'categorical' },
                    { key: 'subgroup', label: 'Подгруппа (опционально)', type: 'categorical', optional: true },
                ]
                : [
                    { key: 'target', label: 'Зависимая переменная', type: 'numeric' },
                    { key: 'group', label: 'Группирующая переменная', type: 'categorical' },
                ];
        }

        if (goal === 'compare_paired') {
            return [
                { key: 'target1', label: 'Переменная 1 (до/условие А)', type: 'numeric' },
                { key: 'target2', label: 'Переменная 2 (после/условие Б)', type: 'numeric' }
            ];
        }

        if (goal === 'correlation') {
            return [
                { key: 'targets', label: 'Переменные для корреляции (выберите несколько)', type: 'numeric', multiple: true }
            ];
        }

        const fieldsByGoal = {
            relationship: [
                { key: 'target', label: 'Variable Y (Outcome)', type: 'numeric' },
                { key: 'predictor', label: 'Variable X (Predictor)', type: 'numeric' },
            ],
            prediction: [
                { key: 'target', label: 'Зависимая переменная (Target Y)', type: 'numeric' },
                { key: 'predictors', label: 'Предикторы (Predictors X)', type: 'numeric', multiple: true },
            ],
            survival: [
                { key: 'duration', label: 'Time to Event', type: 'numeric' },
                { key: 'event', label: 'Event Status (0/1)', type: 'binary' },
                { key: 'group', label: 'Group (Optional)', type: 'categorical' },
            ]
        };
        return fieldsByGoal[goal] || [];
    };

    const fields = getFields();

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
                        <div className="space-y-3">
                            {/* Select All / Deselect All buttons */}
                            <div className="flex space-x-2">
                                <button
                                    type="button"
                                    onClick={() => setVariables(prev => ({ ...prev, [field.key]: columns.join(',') }))}
                                    className="px-3 py-1.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
                                >
                                    Выбрать все
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setVariables(prev => ({ ...prev, [field.key]: '' }))}
                                    className="px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                                >
                                    Очистить
                                </button>
                                <span className="text-xs text-gray-500 self-center ml-2">
                                    Выбрано: {(variables[field.key] || '').split(',').filter(Boolean).length} из {columns.length}
                                </span>
                            </div>

                            {/* Wide grid of variables */}
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 p-4 bg-gray-50 rounded-lg border border-gray-200 max-h-80 overflow-y-auto">
                                {columns.map(col => {
                                    const isSelected = (variables[field.key] || '').split(',').includes(col);
                                    return (
                                        <button
                                            key={col}
                                            type="button"
                                            onClick={() => handleSelect(field.key, col, true)}
                                            className={`px-3 py-2 text-sm rounded-lg border transition-all text-left truncate ${isSelected
                                                ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                                                : 'bg-white text-gray-700 border-gray-200 hover:border-blue-300 hover:bg-blue-50'
                                                }`}
                                            title={col}
                                        >
                                            {col}
                                        </button>
                                    );
                                })}
                            </div>
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
    const [batchMode, setBatchMode] = useState(false);

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
                        {/* Batch Mode Toggle */}
                        {goal === 'compare_groups' && (
                            <div className="mb-6 flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-100">
                                <div>
                                    <h4 className="font-medium text-gray-900">Пакетный анализ</h4>
                                    <p className="text-sm text-gray-600">Сравнить несколько переменных сразу (с FDR-коррекцией)</p>
                                </div>
                                <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={batchMode}
                                        onChange={(e) => {
                                            setBatchMode(e.target.checked);
                                            setVariables({}); // Reset variables when toggling
                                        }}
                                        className="sr-only peer"
                                    />
                                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                                </label>
                            </div>
                        )}

                        <VariableMapper
                            columns={columns}
                            goal={goal}
                            variables={variables}
                            setVariables={setVariables}
                            batchMode={batchMode}
                            setBatchMode={setBatchMode}
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
