import { useState, useEffect, useRef, useCallback, lazy, Suspense, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { reparseDataset, modifyDataset, getDataset, getSheets, getDatasets, getVariableMapping, putVariableMapping } from '../../lib/api';

const EditableDataGrid = lazy(() => import('../components/EditableDataGrid'));

export default function Profile() {
    const { id } = useParams();
    const location = useLocation();

    // Data State
    const [profile, setProfile] = useState(location.state?.profile || null);
    const [filename, setFilename] = useState(location.state?.filename || "Unknown file");
    const [sheets, setSheets] = useState([]);
    const [selectedSheet, setSelectedSheet] = useState(null);

    const PAGE_SIZE = 500;
    const [page, setPage] = useState(1);

    // UI State
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeMenu, setActiveMenu] = useState(null);

    const [workspaceView, setWorkspaceView] = useState('data');
    const [variableMapping, setVariableMapping] = useState({});
    const [mappingLoading, setMappingLoading] = useState(false);
    const [mappingSaving, setMappingSaving] = useState(false);
    const [mappingError, setMappingError] = useState(null);
    const [mappingFilter, setMappingFilter] = useState('');
    const [bulkSubgroup, setBulkSubgroup] = useState('');
    const [bulkTimepoint, setBulkTimepoint] = useState('');
    const mappingSaveTimerRef = useRef(null);
    const variableGridApiRef = useRef(null);


    const gridFallback = useMemo(() => (
        <div className="animate-pulse" style={{
            minHeight: 320,
            borderRadius: '2px',
            border: '1px solid var(--border-color)',
            background: 'var(--bg-tertiary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-muted)',
            fontSize: '12px'
        }}>
            Loading grid…
        </div>
    ), []);

    // Click outside to close menu
    const menuRef = useRef(null);
    useEffect(() => {
        function handleClickOutside(event) {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setActiveMenu(null);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const checkSheets = useCallback(async () => {
        try {
            const s = await getSheets(id);
            if (s && s.length > 0) {
                setSheets(s);
            }
        } catch (e) {
            console.error("Failed to load sheets", e);
        }
    }, [id]);

    const loadProfile = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getDataset(id, page, PAGE_SIZE);
            setProfile(data);
        } catch (e) {
            console.error(e);
            setError("Не удалось загрузить данные. Возможно, файл удален или поврежден.");
        } finally {
            setLoading(false);
        }
    }, [id, page]);

    const loadVariableMapping = useCallback(async () => {
        setMappingLoading(true);
        setMappingError(null);
        try {
            const res = await getVariableMapping(id);
            setVariableMapping(res?.mapping && typeof res.mapping === 'object' ? res.mapping : {});
        } catch (e) {
            setVariableMapping({});
            setMappingError(e.message || 'Не удалось загрузить mapping');
        } finally {
            setMappingLoading(false);
        }
    }, [id]);

    // Initial Load
    useEffect(() => {
        loadProfile();
    }, [loadProfile]);

    useEffect(() => {
        loadVariableMapping();
    }, [loadVariableMapping]);

    useEffect(() => {
        let cancelled = false;

        const loadName = async () => {
            if (filename && filename !== 'Unknown file') return;
            try {
                const list = await getDatasets();
                if (cancelled) return;
                const hit = Array.isArray(list) ? list.find((d) => d?.id === id) : null;
                if (hit?.filename) setFilename(hit.filename);
            } catch {
                if (!cancelled) setFilename((prev) => prev || 'Unknown file');
            }
        };

        loadName();

        return () => {
            cancelled = true;
        };
    }, [id, filename]);

    // Sheets check
    useEffect(() => {
        checkSheets();
    }, [checkSheets]);

    const handleSheetChange = async (sheetName) => {
        if (sheetName === selectedSheet) return;
        setLoading(true);
        setError(null);
        try {
            const newProfile = await reparseDataset(id, 0, sheetName, { page: 1, limit: PAGE_SIZE });
            setProfile(newProfile);
            setSelectedSheet(sheetName);
            setPage(1);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleAction = async (action) => {
        setLoading(true);
        setError(null);
        setActiveMenu(null);
        try {
            const updatedProfile = await modifyDataset(id, [action], { page, limit: PAGE_SIZE });
            setProfile(updatedProfile);
            if (typeof updatedProfile?.page === 'number' && updatedProfile.page !== page) {
                setPage(updatedProfile.page);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleHeaderMenu = useCallback(({ colName, x, y }) => {
        setActiveMenu({ colName, x, y });
    }, []);

    const baseRowIndex = (Math.max(1, profile?.page || 1) - 1) * PAGE_SIZE;

    const columnNameByIndex = useMemo(() => (profile?.columns || []).map((c) => c?.name).filter(Boolean), [profile]);

    const workspaceRows = useMemo(() => {
        const cols = profile?.columns || [];
        return cols.map((c) => {
            const name = c?.name;
            const mapped = name && variableMapping && typeof variableMapping === 'object' ? variableMapping[name] : null;
            const missingPct = profile?.row_count ? (Number(c?.missing_count || 0) / Number(profile.row_count)) * 100 : 0;

            return {
                original_name: name,
                role: mapped?.role ?? '',
                group_var: Boolean(mapped?.group_var ?? false),
                subgroup: mapped?.subgroup ?? '',
                timepoint: mapped?.timepoint ?? '',
                display_name: mapped?.display_name ?? '',
                data_type: mapped?.data_type ?? c?.type ?? 'text',
                include_descriptive: Boolean(mapped?.include_descriptive ?? true),
                include_comparison: Boolean(mapped?.include_comparison ?? true),
                missing_pct: Number.isFinite(missingPct) ? Math.round(missingPct) : 0,
                unique_count: Number(c?.unique_count ?? 0),
            };
        });
    }, [profile, variableMapping]);

    const workspaceColumnDefs = useMemo(() => {
        const roleValues = ['', 'ID', 'Группа', 'Подгруппа', 'Ковариата', 'Исход', 'Исключить'];
        const typeValues = ['число', 'категория', 'дата', 'текст'];

        return [
            {
                headerName: 'Переменная',
                field: 'original_name',
                pinned: 'left',
                lockPinned: true,
                editable: false,
                width: 220,
                cellClass: 'font-mono text-xs text-[color:var(--text-primary)] border-r border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]',
            },
            {
                headerName: 'Роль',
                field: 'role',
                editable: true,
                width: 160,
                cellEditor: 'agSelectCellEditor',
                cellEditorParams: { values: roleValues },
            },
            {
                headerName: 'Тип',
                field: 'data_type',
                editable: true,
                width: 150,
                cellEditor: 'agSelectCellEditor',
                cellEditorParams: { values: typeValues },
                cellClass: 'font-mono text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Группа',
                field: 'group_var',
                editable: true,
                width: 110,
                cellRenderer: 'agCheckboxCellRenderer',
                cellEditor: 'agCheckboxCellEditor',
                cellClass: 'border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Подгруппа',
                field: 'subgroup',
                editable: true,
                width: 180,
                cellClass: 'text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Точка времени',
                field: 'timepoint',
                editable: true,
                width: 140,
                cellClass: 'font-mono text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Отображение',
                field: 'display_name',
                editable: true,
                minWidth: 220,
                flex: 1,
                cellClass: 'text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Описательная',
                field: 'include_descriptive',
                editable: true,
                width: 100,
                cellRenderer: 'agCheckboxCellRenderer',
                cellEditor: 'agCheckboxCellEditor',
                cellClass: 'border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Сравнение',
                field: 'include_comparison',
                editable: true,
                width: 120,
                cellRenderer: 'agCheckboxCellRenderer',
                cellEditor: 'agCheckboxCellEditor',
                cellClass: 'border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Пропуски%',
                field: 'missing_pct',
                editable: false,
                width: 120,
                cellClass: 'font-mono text-xs text-[color:var(--text-muted)]',
            },
            {
                headerName: 'Уникальных',
                field: 'unique_count',
                editable: false,
                width: 110,
                cellClass: 'font-mono text-xs text-[color:var(--text-muted)]',
            },
        ];
    }, []);

    const scheduleSaveMapping = useCallback(
        (nextMapping) => {
            if (mappingSaveTimerRef.current) {
                clearTimeout(mappingSaveTimerRef.current);
            }

            mappingSaveTimerRef.current = setTimeout(async () => {
                setMappingSaving(true);
                setMappingError(null);
                try {
                    const res = await putVariableMapping(id, nextMapping);
                    setVariableMapping(res?.mapping && typeof res.mapping === 'object' ? res.mapping : nextMapping);
                } catch (e) {
                    setMappingError(e.message || 'Не удалось сохранить mapping');
                } finally {
                    setMappingSaving(false);
                }
            }, 450);
        },
        [id]
    );

    const handleWorkspaceUpdateCell = useCallback(
        ({ rowIndex, colName, value }) => {
            const columnName = columnNameByIndex[rowIndex];
            if (!columnName) return;

            setVariableMapping((prev) => {
                const safePrev = prev && typeof prev === 'object' ? prev : {};
                const next = { ...safePrev };
                const current = next[columnName] && typeof next[columnName] === 'object' ? next[columnName] : {};
                const entry = { ...current, [colName]: value };
                next[columnName] = entry;
                scheduleSaveMapping(next);
                return next;
            });
        },
        [columnNameByIndex, scheduleSaveMapping]
    );

    const subgroupSuggestions = useMemo(() => {
        const values = new Set();
        if (variableMapping && typeof variableMapping === 'object') {
            Object.values(variableMapping).forEach((v) => {
                const s = v?.subgroup;
                if (typeof s === 'string' && s.trim()) values.add(s.trim());
            });
        }
        return Array.from(values).sort((a, b) => a.localeCompare(b));
    }, [variableMapping]);

    const timepointSuggestions = useMemo(() => {
        const values = new Set();
        if (variableMapping && typeof variableMapping === 'object') {
            Object.values(variableMapping).forEach((v) => {
                const s = v?.timepoint;
                if (typeof s === 'string' && s.trim()) values.add(s.trim());
            });
        }
        return Array.from(values).sort((a, b) => a.localeCompare(b));
    }, [variableMapping]);

    const applyBulkMappingField = useCallback(
        (field, rawValue) => {
            const value = typeof rawValue === 'string' ? rawValue.trim() : '';
            if (!value) return;

            const api = variableGridApiRef.current;
            const keys = [];

            if (api && typeof api.forEachNodeAfterFilterAndSort === 'function') {
                api.forEachNodeAfterFilterAndSort((node) => {
                    const name = node?.data?.original_name;
                    if (typeof name === 'string' && name) keys.push(name);
                });
            } else {
                const f = (mappingFilter || '').trim().toLowerCase();
                (workspaceRows || []).forEach((r) => {
                    const name = r?.original_name;
                    if (!name) return;
                    if (!f || String(name).toLowerCase().includes(f)) keys.push(name);
                });
            }

            if (keys.length === 0) return;

            setVariableMapping((prev) => {
                const safePrev = prev && typeof prev === 'object' ? prev : {};
                const next = { ...safePrev };

                keys.forEach((k) => {
                    const current = next[k] && typeof next[k] === 'object' ? next[k] : {};
                    next[k] = { ...current, [field]: value };
                });

                scheduleSaveMapping(next);
                return next;
            });
        },
        [mappingFilter, scheduleSaveMapping, workspaceRows]
    );

    if (!profile) {
        return (
            <div className="flex items-center justify-center h-screen bg-[color:var(--bg-secondary)]">
                <div className="text-center">
                    <div className="text-4xl mb-4 animate-spin">🌀</div>
                    <p className="text-[color:var(--text-secondary)] font-semibold">Загрузка данных...</p>
                    {error && <p className="text-[color:var(--text-primary)] mt-2">{error}</p>}
                </div>
            </div>
        );
    }

    function TypeIcon({ type }) {
        switch (type) {
            case 'numeric': return <span className="text-[10px] font-bold text-[color:var(--text-primary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-black">#</span>;
            case 'categorical': return <span className="text-[10px] font-bold text-[color:var(--text-primary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-[color:var(--accent)]">Ab</span>;
            case 'datetime': return <span className="text-[10px] font-bold text-[color:var(--text-primary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-[color:var(--border-color)]">⏱</span>;
            default: return <span className="text-[10px] font-bold text-[color:var(--text-secondary)] bg-[color:var(--white)] px-1 py-0.5 rounded-[2px] border border-[color:var(--border-color)]">T</span>;
        }
    }

    const ColumnMenu = () => {
        if (!activeMenu) return null;
        return (
            <div
                ref={menuRef}
                className="absolute bg-[color:var(--white)] rounded-[2px] border border-black w-48 z-50 text-sm overflow-hidden"
                style={{ top: activeMenu.y, left: activeMenu.x }}
            >
                <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)] font-semibold text-[color:var(--text-primary)] truncate">
                    {activeMenu.colName}
                </div>
                <div className="p-1 space-y-0.5">
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'numeric' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-[color:var(--text-primary)]">#</span> Number
                    </button>
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'text' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-[color:var(--text-secondary)]">T</span> Text
                    </button>
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'categorical' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-[color:var(--accent)]">Ab</span> Category
                    </button>
                </div>
                <div className="border-t border-[color:var(--border-color)] p-1">
                    <button
                        onClick={() => {
                            const newName = prompt("Rename column:", activeMenu.colName);
                            if (newName && newName !== activeMenu.colName) handleAction({ type: 'rename_col', column: activeMenu.colName, new_name: newName });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] transition-colors"
                    >
                        Rename
                    </button>
                    <button
                        onClick={() => {
                            if (confirm(`Delete column "${activeMenu.colName}"?`)) handleAction({ type: 'drop_col', column: activeMenu.colName });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--accent)] rounded-[2px] transition-colors"
                    >
                        Delete
                    </button>
                </div>
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)] font-sans" onClick={() => setActiveMenu(null)}>

            {/* Simple Header */}
            <div className="bg-white border-b border-[color:var(--border-color)] px-6 py-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-lg font-bold text-[color:var(--text-primary)]">{filename}</h1>
                        <div className="text-xs text-[color:var(--text-secondary)]">
                            {profile.row_count} строк • {profile.col_count} столбцов
                        </div>
                    </div>
                    {sheets.length > 0 && (
                        <select
                            className="bg-white border border-[color:var(--border-color)] text-sm rounded px-3 py-1.5"
                            onChange={(e) => handleSheetChange(e.target.value)}
                            value={selectedSheet || sheets[0] || ""}
                        >
                            {sheets.map(sheet => (
                                <option key={sheet} value={sheet}>{sheet}</option>
                            ))}
                        </select>
                    )}
                </div>
            </div>

            <main className="max-w-full p-4">\n
                {/* Main Data Grid */}
                <div className="bg-white rounded border border-[color:var(--border-color)] flex flex-col overflow-hidden min-h-[500px]">
                    {loading && (
                        <div className="absolute inset-0 bg-[color:var(--white)]/80 z-20 flex items-center justify-center">
                            <div className="bg-[color:var(--white)] p-4 rounded-[2px] border border-[color:var(--border-color)] flex items-center gap-3">
                                <div className="w-4 h-4 border-2 border-[color:var(--accent)] border-t-transparent rounded-[2px] animate-spin"></div>
                                <span className="text-sm font-semibold text-[color:var(--text-primary)]">Checking data...</span>
                            </div>
                        </div>
                    )}

                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 px-4 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setWorkspaceView('data')}
                                className={`px-3 py-1.5 rounded-[2px] text-xs font-bold uppercase tracking-wide border transition-colors ${workspaceView === 'data'
                                    ? 'bg-[color:var(--black)] text-[color:var(--white)] border-[color:var(--black)]'
                                    : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                    }`}
                            >
                                ДАННЫЕ
                            </button>
                            <button
                                type="button"
                                onClick={() => setWorkspaceView('variables')}
                                className={`px-3 py-1.5 rounded-[2px] text-xs font-bold uppercase tracking-wide border transition-colors ${workspaceView === 'variables'
                                    ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]'
                                    : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                    }`}
                            >
                                ПЕРЕМЕННЫЕ
                            </button>
                            {workspaceView === 'variables' && (
                                <div className="flex items-center gap-2 ml-2">
                                    <input
                                        value={mappingFilter}
                                        onChange={(e) => setMappingFilter(e.target.value)}
                                        placeholder="Поиск…"
                                        className="h-9 w-56 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                                    />
                                    <div className="hidden lg:flex items-center gap-2">
                                        <input
                                            value={bulkSubgroup}
                                            onChange={(e) => setBulkSubgroup(e.target.value)}
                                            list="subgroup-suggestions"
                                            placeholder="Подгруппа"
                                            className="h-9 w-44 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                                        />
                                        <datalist id="subgroup-suggestions">
                                            {subgroupSuggestions.map((v) => (
                                                <option key={v} value={v} />
                                            ))}
                                        </datalist>
                                        <button
                                            type="button"
                                            onClick={() => applyBulkMappingField('subgroup', bulkSubgroup)}
                                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                                        >
                                            Применить
                                        </button>

                                        <input
                                            value={bulkTimepoint}
                                            onChange={(e) => setBulkTimepoint(e.target.value)}
                                            list="timepoint-suggestions"
                                            placeholder="Точка времени"
                                            className="h-9 w-44 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                                        />
                                        <datalist id="timepoint-suggestions">
                                            {timepointSuggestions.map((v) => (
                                                <option key={v} value={v} />
                                            ))}
                                        </datalist>
                                        <button
                                            type="button"
                                            onClick={() => applyBulkMappingField('timepoint', bulkTimepoint)}
                                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                                        >
                                            Применить
                                        </button>
                                    </div>
                                    <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">
                                        {mappingLoading ? 'Загрузка' : mappingSaving ? 'Сохранение' : mappingError ? 'Ошибка' : 'Сохранено'}
                                    </div>
                                </div>
                            )}
                        </div>

                        {workspaceView === 'data' ? (
                            <div className="flex items-center gap-2">
                                <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                    Страница {profile.page} / {profile.total_pages}
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    disabled={loading || (profile.page || 1) <= 1}
                                    className="px-3 py-1.5 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                                >
                                    Назад
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setPage((p) => Math.min(profile.total_pages || p + 1, p + 1))}
                                    disabled={loading || (profile.page || 1) >= (profile.total_pages || 1)}
                                    className="px-3 py-1.5 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                                >
                                    Далее
                                </button>
                            </div>
                        ) : (
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                {workspaceRows.length} переменных
                            </div>
                        )}
                    </div>

                    <div className="flex-1 overflow-auto custom-scrollbar max-h-[800px]">
                        <ColumnMenu />
                        <Suspense fallback={gridFallback}>
                            {workspaceView === 'data' ? (
                                <EditableDataGrid
                                    columns={profile.columns}
                                    rows={profile.head}
                                    loading={loading}
                                    onHeaderMenu={handleHeaderMenu}
                                    onDropRow={(rowIndex) => handleAction({ type: 'drop_row', row_index: baseRowIndex + rowIndex })}
                                    onUpdateCell={({ rowIndex, colName, value }) => handleAction({ type: 'update_cell', row_index: baseRowIndex + rowIndex, column: colName, value })}
                                />
                            ) : (
                                <EditableDataGrid
                                    columns={[]}
                                    rows={workspaceRows}
                                    columnDefsOverride={workspaceColumnDefs}
                                    quickFilterText={mappingFilter}
                                    loading={mappingLoading}
                                    onUpdateCell={handleWorkspaceUpdateCell}
                                    onGridReady={(params) => {
                                        variableGridApiRef.current = params?.api || null;
                                    }}
                                />
                            )}
                        </Suspense>
                    </div>
                </div>
            </main>
        </div>
    );
}
