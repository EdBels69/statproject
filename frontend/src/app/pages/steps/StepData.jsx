import React, { useEffect, useMemo, useState } from 'react';
import {
    cleanColumn,
    getDataset,
    getDatasets,
    getScanReport,
    getVariableMapping,
    imputeMice,
    modifyDataset,
    putVariableMapping
} from '@/lib/api';
import { DocumentIcon, ExclamationTriangleIcon, SparklesIcon } from '@heroicons/react/24/outline';
import ColumnSettingsModal from '../../components/ColumnSettingsModal';
import DataTableWithTypes from '../../components/DataTableWithTypes';
import Button from '../../components/ui/Button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/Tabs';
import VariableListView from '../../components/VariableListView';

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
        <div className="mb-6 bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] p-4 animate-fadeIn">
            <div className="flex items-start">
                <ExclamationTriangleIcon className="w-5 h-5 text-[color:var(--accent)] mt-0.5 mr-3" />
                <div className="flex-1">
                    <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">Data Preparation</h3>

                    {hasMissing && (
                        <div className="mt-3">
                            <div className="flex items-center justify-between gap-3">
                                <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">Missing Values</div>
                                <button
                                    type="button"
                                    onClick={() => {
                                        const cols = missingByColumn
                                            .map(m => m?.column)
                                            .filter(Boolean)
                                            .filter(isNumericColumn);
                                        if (cols.length > 0) onMice(cols);
                                    }}
                                    className="px-2 py-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                                >
                                    MICE
                                </button>
                            </div>
                            <div className="mt-2 space-y-2">
                                {missingByColumn.slice(0, 8).map((m) => (
                                    <div key={m.column} className="flex items-center justify-between gap-3 text-sm text-[color:var(--text-primary)] bg-[color:var(--white)] p-2 rounded-[2px] border border-[color:var(--border-color)]">
                                        <div className="min-w-0">
                                            <div className="truncate font-semibold">{m.column}</div>
                                            <div className="text-xs text-[color:var(--text-secondary)]">{m.missing_count} missing ({m.missing_percent}%)</div>
                                        </div>

                                        <div className="flex items-center gap-1.5 shrink-0">
                                            {isNumericColumn(m.column) && (
                                                <>
                                                    <button
                                                        onClick={() => onFix(m.column, 'fill_mean')}
                                                        className="px-2 py-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                                                    >
                                                        Mean
                                                    </button>
                                                    <button
                                                        onClick={() => onFix(m.column, 'fill_median')}
                                                        className="px-2 py-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                                                    >
                                                        Median
                                                    </button>
                                                </>
                                            )}
                                            <button
                                                onClick={() => onFix(m.column, 'fill_locf')}
                                                className="px-2 py-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                                            >
                                                LOCF
                                            </button>
                                            <button
                                                onClick={() => onFix(m.column, 'fill_nocb')}
                                                className="px-2 py-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
                                            >
                                                NOCB
                                            </button>
                                            <button
                                                onClick={() => onFix(m.column, 'drop_na')}
                                                className="px-2 py-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[11px] font-semibold text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
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
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">Type Issues</div>
                            <div className="mt-2 space-y-2">
                                {issues.filter(i => i?.type === 'mixed_type').slice(0, 8).map((issue, idx) => (
                                    <div key={`${issue.column}-${idx}`} className="flex items-center justify-between text-sm text-[color:var(--text-primary)] bg-[color:var(--white)] p-2 rounded-[2px] border border-[color:var(--border-color)]">
                                        <span>
                                            <strong>{issue.column}</strong>: {issue.details}
                                        </span>
                                        <button
                                            onClick={() => onFix(issue.column, "to_numeric")}
                                            className="ml-4 flex items-center px-3 py-1 rounded-[2px] text-xs font-medium text-[color:var(--white)] bg-[color:var(--accent)] border border-[color:var(--accent)] hover:bg-[color:var(--accent-hover)] hover:border-[color:var(--accent-hover)] transition-colors"
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
                    <label className="block text-sm font-medium text-[color:var(--text-primary)]">
                        {field.label}
                    </label>

                    {field.multiple ? (
                        <div className="border border-[color:var(--border-color)] rounded-[2px] p-3 max-h-60 overflow-y-auto bg-[color:var(--bg-secondary)]">
                            {columns.map(col => {
                                const isSelected = (variables[field.key] || '').split(',').includes(col);
                                return (
                                    <label key={col} className="flex items-center space-x-3 p-2 hover:bg-[color:var(--white)] rounded-[2px] cursor-pointer transition-colors">
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => handleSelect(field.key, col, true)}
                                            className="w-4 h-4 rounded-[2px] border-[color:var(--border-color)] accent-[color:var(--accent)]"
                                        />
                                        <span className={`text-sm ${isSelected ? 'text-[color:var(--accent)] font-medium' : 'text-[color:var(--text-secondary)]'}`}>
                                            {col}
                                        </span>
                                    </label>
                                );
                            })}
                        </div>
                    ) : (
                        <select
                            className="w-full p-2.5 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm text-[color:var(--text-primary)] outline-none"
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
    const [profile, setProfile] = useState(null);
    const [uiColumns, setUiColumns] = useState([]);
    const [variables, setVariables] = useState({});
    const [loading, setLoading] = useState(true);
    const [scanReport, setScanReport] = useState(null);
    const [activeTab, setActiveTab] = useState('prepare');
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [activeColumnName, setActiveColumnName] = useState('');
    const [mapping, setMapping] = useState({});

    // Load datasets on mount
    useEffect(() => {
        getDatasets()
            .then(setDatasets)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const usePhase7Flow = goal === 'compare_groups' || goal === 'relationship';

    function safeString(value) {
        return String(value ?? '').trim();
    }

    function backendTypeFromUiType(uiType) {
        if (uiType === 'numeric') return 'numeric';
        if (uiType === 'categorical') return 'categorical';
        if (uiType === 'date') return 'datetime';
        if (uiType === 'id') return 'text';
        return '';
    }

    function uiTypeFromBackendType(dataType) {
        if (dataType === 'numeric') return 'numeric';
        if (dataType === 'categorical') return 'categorical';
        if (dataType === 'datetime') return 'date';
        return '';
    }

    // Load profile + scan report + mapping when dataset selected
    useEffect(() => {
        if (!selectedDataset) return;

        let cancelled = false;
        (async () => {
            try {
                const [p, sr, vm] = await Promise.all([
                    getDataset(selectedDataset, 1, 60),
                    getScanReport(selectedDataset),
                    getVariableMapping(selectedDataset)
                ]);
                if (cancelled) return;

                setProfile(p);
                setScanReport(sr);
                const nextMapping = vm?.mapping && typeof vm.mapping === 'object' ? vm.mapping : {};
                setMapping(nextMapping);

                const colInfos = Array.isArray(p?.columns) ? p.columns : [];
                const nextUiCols = colInfos.map((c) => {
                    const name = typeof c === 'string' ? c : c?.name;
                    const mapEntry = name ? nextMapping[name] : null;
                    const dataType = safeString(mapEntry?.data_type) || safeString(typeof c === 'string' ? '' : c?.type);
                    const role = safeString(mapEntry?.role);
                    return {
                        name: safeString(name),
                        uiType: uiTypeFromBackendType(dataType),
                        role,
                        example: typeof c === 'string' ? '' : c?.example
                    };
                });
                setUiColumns(nextUiCols.filter((c) => c.name));
            } catch (e) {
                if (!cancelled) console.error(e);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [selectedDataset]);

    const handleClean = async (column, action) => {
        try {
            // Apply fix
            const newProfile = await cleanColumn(selectedDataset, column, action);
            setProfile(newProfile);
            const newReport = await getScanReport(selectedDataset);
            setScanReport(newReport);
        } catch (e) {
            alert("Fix failed: " + e.message);
        }
    };

    const handleMice = async (cols) => {
        try {
            const newProfile = await imputeMice(selectedDataset, cols);
            setProfile(newProfile);
            const newReport = await getScanReport(selectedDataset);
            setScanReport(newReport);
        } catch (e) {
            alert("MICE failed: " + e.message);
        }
    };

    const derivedVariables = useMemo(() => {
        if (!usePhase7Flow) return variables;
        const cols = Array.isArray(uiColumns) ? uiColumns : [];
        const target = cols.find((c) => c?.role === 'target')?.name;
        const factor =
            cols.find((c) => c?.role === 'factor')?.name ||
            cols.find((c) => Boolean(mapping?.[c?.name]?.group_var))?.name;
        const covariates = cols.filter((c) => c?.role === 'covariate').map((c) => c.name);

        if (goal === 'compare_groups') {
            return {
                target: safeString(target),
                group: safeString(factor)
            };
        }

        if (goal === 'relationship') {
            return {
                target: safeString(target),
                predictor: safeString(covariates[0] || factor)
            };
        }

        return variables;
    }, [goal, mapping, uiColumns, usePhase7Flow, variables]);

    const canProceed = useMemo(() => {
        if (!selectedDataset) return false;
        if (!usePhase7Flow) return Object.keys(variables || {}).length > 0;
        if (goal === 'compare_groups') return Boolean(derivedVariables?.target && derivedVariables?.group);
        if (goal === 'relationship') return Boolean(derivedVariables?.target && derivedVariables?.predictor);
        return false;
    }, [derivedVariables, goal, selectedDataset, usePhase7Flow, variables]);

    // Notify parent when valid configuration is ready
    useEffect(() => {
        onDataReady({ datasetId: selectedDataset, variables: derivedVariables });
    }, [derivedVariables, onDataReady, selectedDataset]);

    if (loading) return <div>Loading...</div>;

    const rows = Array.isArray(profile?.head) ? profile.head : [];

    const persistMapping = async (datasetId, nextMapping) => {
        try {
            if (!datasetId) return;
            const res = await putVariableMapping(datasetId, nextMapping);
            if (datasetId !== selectedDataset) return;
            setMapping(res?.mapping && typeof res.mapping === 'object' ? res.mapping : nextMapping);
        } catch (e) {
            console.error(e);
        }
    };

    const handleTypeChange = async (columnName, uiType) => {
        const name = safeString(columnName);
        if (!name) return;
        const nextUiType = safeString(uiType);

        const datasetId = selectedDataset;
        const backendType = backendTypeFromUiType(nextUiType);

        setUiColumns((prev) =>
            (Array.isArray(prev) ? prev : []).map((c) => (c.name === name ? { ...c, uiType: nextUiType } : c))
        );

        let nextMapping;
        setMapping((prev) => {
            const base = prev && typeof prev === 'object' ? prev : {};
            nextMapping = {
                ...base,
                [name]: {
                    ...(base?.[name] || {}),
                    data_type: backendType || undefined,
                    role: nextUiType === 'id' ? 'ignore' : base?.[name]?.role
                }
            };
            return nextMapping;
        });
        await persistMapping(datasetId, nextMapping);

        if (backendType && datasetId && (nextUiType === 'numeric' || nextUiType === 'categorical' || nextUiType === 'date')) {
            try {
                const newProfile = await modifyDataset(datasetId, [
                    { type: 'change_type', column: name, new_type: backendType }
                ]);
                setProfile(newProfile);
                const newReport = await getScanReport(datasetId);
                setScanReport(newReport);
            } catch (e) {
                console.error(e);
            }
        }
    };

    const handleRoleChange = async (columnName, role) => {
        const name = safeString(columnName);
        if (!name) return;
        const nextRole = safeString(role);

        const datasetId = selectedDataset;

        setUiColumns((prev) =>
            (Array.isArray(prev) ? prev : []).map((c) => (c.name === name ? { ...c, role: nextRole } : c))
        );

        let nextMapping;
        setMapping((prev) => {
            const base = prev && typeof prev === 'object' ? prev : {};
            nextMapping = {
                ...base,
                [name]: {
                    ...(base?.[name] || {}),
                    role: nextRole || undefined
                }
            };
            return nextMapping;
        });
        await persistMapping(datasetId, nextMapping);
    };

    const openSettings = (columnName) => {
        const name = safeString(columnName);
        if (!name) return;
        setActiveColumnName(name);
        setSettingsOpen(true);
    };

    const activeMappingEntry = activeColumnName ? mapping?.[activeColumnName] : null;

    return (
        <div className="stepdata grid grid-cols-1 lg:grid-cols-3 gap-8">
            <div className="lg:col-span-1 pr-0 lg:pr-8 lg:border-r lg:border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">Dataset</div>
                <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)]">Выбери таблицу</div>
                <div className="mt-4 space-y-2">
                    {datasets.map((ds) => (
                        <button
                            key={ds.id}
                            type="button"
                            onClick={() => {
                                setSelectedDataset(ds.id);
                            setProfile(null);
                            setUiColumns([]);
                            setScanReport(null);
                            setMapping({});
                                setActiveTab('prepare');
                            }}
                            className={`w-full text-left rounded-[2px] border px-4 py-3 transition-colors flex items-center gap-3 ${selectedDataset === ds.id
                                ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)]'
                                : 'border-[color:var(--border-color)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)]'
                                }`}
                        >
                            <DocumentIcon className={`w-5 h-5 ${selectedDataset === ds.id ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-muted)]'}`} />
                            <div className="min-w-0">
                                <div className="truncate text-sm font-semibold text-[color:var(--text-primary)]">{ds.filename}</div>
                                <div className="mt-0.5 text-xs text-[color:var(--text-secondary)] truncate">{ds.id}</div>
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            <div className="lg:col-span-2">
                <CleaningWizardAlert report={scanReport} onFix={handleClean} onMice={handleMice} />

                {!selectedDataset ? (
                    <div className="rounded-[2px] border border-dashed border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-10 text-center">
                        <div className="text-sm font-semibold text-[color:var(--text-primary)]">Выбери dataset слева</div>
                        <div className="mt-1 text-sm text-[color:var(--text-secondary)]">Дальше появится таблица и список переменных</div>
                    </div>
                ) : usePhase7Flow ? (
                    <>
                        <Tabs value={activeTab} onValueChange={setActiveTab}>
                            <TabsList>
                                <TabsTrigger value="prepare">Prepare</TabsTrigger>
                                <TabsTrigger value="design">Design</TabsTrigger>
                            </TabsList>

                            <TabsContent value="prepare" className="pt-5">
                                <DataTableWithTypes
                                    columns={uiColumns}
                                    rows={rows}
                                    onTypeChange={handleTypeChange}
                                    onOpenSettings={openSettings}
                                />
                            </TabsContent>

                            <TabsContent value="design" className="pt-5">
                                <VariableListView
                                    columns={uiColumns}
                                    scanReport={scanReport}
                                    onTypeChange={handleTypeChange}
                                    onRoleChange={handleRoleChange}
                                    onOpenSettings={openSettings}
                                />
                            </TabsContent>
                        </Tabs>

                        <div className="mt-8 flex items-center justify-end gap-2">
                            <Button type="button" variant="primary" disabled={!canProceed} onClick={onNext}>
                                Review Protocol →
                            </Button>
                        </div>
                    </>
                ) : (
                    <>
                        <VariableMapper
                            columns={(Array.isArray(profile?.columns) ? profile.columns : []).map((c) => (typeof c === 'string' ? c : c?.name)).filter(Boolean)}
                            goal={goal}
                            variables={variables}
                            setVariables={setVariables}
                        />

                        <div className="mt-8 flex items-center justify-end gap-2">
                            <Button type="button" variant="primary" disabled={!canProceed} onClick={onNext}>
                                Review Protocol →
                            </Button>
                        </div>
                    </>
                )}
            </div>

            <ColumnSettingsModal
                key={`${activeColumnName || 'none'}-${settingsOpen ? 'open' : 'closed'}`}
                isOpen={settingsOpen}
                columnName={activeColumnName}
                columns={uiColumns}
                value={activeMappingEntry}
                onClose={() => setSettingsOpen(false)}
                onSave={async (entry) => {
                    if (!activeColumnName) return;
                    const name = safeString(activeColumnName);

                    const datasetId = selectedDataset;
                    let nextMapping;
                    setMapping((prev) => {
                        const base = prev && typeof prev === 'object' ? prev : {};
                        nextMapping = {
                            ...base,
                            [name]: {
                                ...(base?.[name] || {}),
                                ...(entry || {})
                            }
                        };
                        return nextMapping;
                    });
                    await persistMapping(datasetId, nextMapping);

                    if (entry?.role !== undefined) {
                        setUiColumns((prev) =>
                            (Array.isArray(prev) ? prev : []).map((c) => (c.name === name ? { ...c, role: entry.role || '' } : c))
                        );
                    }
                    setSettingsOpen(false);
                }}
            />
        </div>
    );
};

export default StepData;
