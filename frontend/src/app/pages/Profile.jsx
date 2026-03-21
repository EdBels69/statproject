import { useState, useEffect, useRef, useCallback, lazy, Suspense, useMemo } from 'react';
import { useParams, useLocation, Link, useNavigate } from 'react-router-dom';
import { reparseDataset, modifyDataset, getDataset, getDatasetContent, getSheets, getDatasets, getVariableMapping, putVariableMapping, cleanColumn, imputeMice, getScanReport, cloneDatasetForPreparation, computeDatasetColumn, getPrepareHistory, undoPrepare } from '../../lib/api';

const EditableDataGrid = lazy(() => import('../components/EditableDataGrid'));

const MISSING_MOSTLY_EMPTY_THRESHOLD_PCT = 99.5;
const isMostlyEmptyMissingPct = (pct) => Number(pct) >= MISSING_MOSTLY_EMPTY_THRESHOLD_PCT;

export default function Profile() {
    const { id } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const isPrepareMode = Boolean(location?.pathname?.startsWith('/prepare/'));

    // Data State
    const [profile, setProfile] = useState(location.state?.profile || null);
    const [filename, setFilename] = useState(location.state?.filename || "Неизвестный файл");
    const [sheets, setSheets] = useState([]);
    const [selectedSheet, setSelectedSheet] = useState(null);

    const PAGE_SIZE = 500;
    const [page, setPage] = useState(1);

    const [dataColOffset, setDataColOffset] = useState(0);
    const dataColLimit = useMemo(() => {
        const totalCols = Number(profile?.col_count ?? 0);
        if (!Number.isFinite(totalCols) || totalCols <= 0) return 24;
        if (totalCols > 80) return 24;
        if (totalCols > 40) return 40;
        return totalCols;
    }, [profile?.col_count]);

    const maxDataColOffset = useMemo(() => {
        const totalCols = Number(profile?.col_count ?? 0);
        if (!Number.isFinite(totalCols) || totalCols <= 0) return 0;
        return Math.max(0, totalCols - Math.max(1, dataColLimit));
    }, [dataColLimit, profile?.col_count]);
    const [dataRows, setDataRows] = useState([]);
    const [dataColNames, setDataColNames] = useState([]);
    const [dataLoading, setDataLoading] = useState(false);
    const [dataFilter, setDataFilter] = useState('');
    const [dataReloadKey, setDataReloadKey] = useState(0);

    // UI State
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeMenu, setActiveMenu] = useState(null);

    const [workspaceView, setWorkspaceView] = useState(() => (
        location?.pathname?.startsWith('/prep/') ? 'variables' : 'data'
    ));
    const [variableMapping, setVariableMapping] = useState({});
    const [mappingLoading, setMappingLoading] = useState(false);
    const [mappingSaving, setMappingSaving] = useState(false);
    const [mappingError, setMappingError] = useState(null);
    const [mappingFilter, setMappingFilter] = useState('');
    const [bulkSubgroup, setBulkSubgroup] = useState('');
    const [bulkTimepoint, setBulkTimepoint] = useState('');
    const [qualityOpen, setQualityOpen] = useState(false);
    const mappingSaveTimerRef = useRef(null);
    const variableGridApiRef = useRef(null);

    const [scanReport, setScanReport] = useState(null);
    const [scanLoading, setScanLoading] = useState(false);

    const [prepHistoryCount, setPrepHistoryCount] = useState(0);
    const [prepUndoLoading, setPrepUndoLoading] = useState(false);

    const PREP_STEPS = useMemo(
        () => [
            { id: 'overview', label: 'Обзор' },
            { id: 'cleanup', label: 'Очистка' },
            { id: 'missing', label: 'Пропуски' },
            { id: 'derived', label: 'Новые колонки' },
            { id: 'done', label: 'Готово' },
        ],
        []
    );
    const [prepStepIndex, setPrepStepIndex] = useState(0);
    const prepStepMaxIndex = PREP_STEPS.length > 0 ? PREP_STEPS.length - 1 : 0;
    const safePrepStepIndex = Math.max(0, Math.min(prepStepMaxIndex, prepStepIndex));
    const activePrepStep = PREP_STEPS[safePrepStepIndex];

    const prepStepIndexById = useMemo(() => {
        const map = {};
        PREP_STEPS.forEach((s, idx) => {
            map[s.id] = idx;
        });
        return map;
    }, [PREP_STEPS]);

    const goToPrepStep = useCallback((stepId) => {
        const idx = prepStepIndexById?.[stepId];
        if (typeof idx !== 'number') return;
        setPrepStepIndex(idx);
    }, [prepStepIndexById]);

    const [derivedOp, setDerivedOp] = useState('difference');
    const [derivedName, setDerivedName] = useState('');
    const [derivedA, setDerivedA] = useState('');
    const [derivedB, setDerivedB] = useState('');
    const [derivedSource, setDerivedSource] = useState('');
    const [derivedThreshold, setDerivedThreshold] = useState('');

    const loadScan = useCallback(async () => {
        if (!id) return;
        setScanLoading(true);
        try {
            const res = await getScanReport(id);
            setScanReport(res && typeof res === 'object' ? res : null);
        } catch {
            setScanReport(null);
        } finally {
            setScanLoading(false);
        }
    }, [id]);

    const refreshPrepHistory = useCallback(async () => {
        if (!isPrepareMode) return;
        if (!id) return;
        try {
            const res = await getPrepareHistory(id);
            const n = Number(res?.count ?? 0);
            setPrepHistoryCount(Number.isFinite(n) ? n : 0);
        } catch {
            setPrepHistoryCount(0);
        }
    }, [id, isPrepareMode]);

    const handleUndoPrepare = useCallback(async () => {
        if (!isPrepareMode) return;
        if (!id) return;
        if (prepUndoLoading) return;
        if (!confirm('Откатить последнее изменение?')) return;

        setPrepUndoLoading(true);
        setLoading(true);
        setError(null);
        try {
            const fresh = await undoPrepare(id, { page: 1, limit: PAGE_SIZE });
            setProfile(fresh);
            setPage(1);
            setDataReloadKey((v) => v + 1);
            await loadScan();
            await refreshPrepHistory();
        } catch (e) {
            setError(e?.message || 'Не удалось откатить изменение');
        } finally {
            setLoading(false);
            setPrepUndoLoading(false);
        }
    }, [PAGE_SIZE, id, isPrepareMode, loadScan, prepUndoLoading, refreshPrepHistory]);

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

    const handleAction = useCallback(
        async (action) => {
            setLoading(true);
            setError(null);
            setActiveMenu(null);
            try {
                const updatedProfile = await modifyDataset(id, [action], { page, limit: PAGE_SIZE });
                setProfile(updatedProfile);
                setDataReloadKey((v) => v + 1);
                if (typeof updatedProfile?.page === 'number' && updatedProfile.page !== page) {
                    setPage(updatedProfile.page);
                }
                if (isPrepareMode) {
                    await loadScan();
                    await refreshPrepHistory();
                }
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        },
        [PAGE_SIZE, id, isPrepareMode, loadScan, page, refreshPrepHistory]
    );

    const handleDeleteDatasetColumn = useCallback(
        async (colName) => {
            if (!colName) return;
            if (!confirm(`Удалить столбец "${colName}"?`)) return;
            await handleAction({ type: 'drop_col', column: colName });
            setVariableMapping((prev) => {
                const safePrev = prev && typeof prev === 'object' ? prev : {};
                if (!Object.prototype.hasOwnProperty.call(safePrev, colName)) return prev;
                const next = { ...safePrev };
                delete next[colName];
                scheduleSaveMapping(next);
                return next;
            });
        },
        [handleAction, scheduleSaveMapping]
    );


    useEffect(() => {
        if (location?.pathname?.startsWith('/prep/')) {
            setWorkspaceView('variables');
        }
    }, [location?.pathname]);

    useEffect(() => {
        if (!isPrepareMode) return;
        setWorkspaceView('data');
    }, [isPrepareMode]);

    useEffect(() => {
        if (!isPrepareMode) return;
        refreshPrepHistory();
    }, [id, isPrepareMode, refreshPrepHistory]);

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
            Загружаю таблицу…
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

    useEffect(() => {
        setDataColOffset((prev) => Math.min(Math.max(0, prev), maxDataColOffset));
    }, [maxDataColOffset]);

    useEffect(() => {
        if (!id) return;
        if (workspaceView !== 'data') return;
        let cancelled = false;

        (async () => {
            setDataLoading(true);
            try {
                const res = await getDatasetContent(id, {
                    page,
                    limit: PAGE_SIZE,
                    colOffset: dataColOffset,
                    colLimit: dataColLimit,
                    sheet: selectedSheet || undefined,
                });
                if (cancelled) return;
                setDataRows(Array.isArray(res?.data) ? res.data : []);
                setDataColNames(Array.isArray(res?.columns) ? res.columns : []);
            } catch (e) {
                if (!cancelled) console.error(e);
            } finally {
                if (!cancelled) setDataLoading(false);
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [PAGE_SIZE, dataColLimit, dataColOffset, dataReloadKey, id, page, selectedSheet, workspaceView]);

    const loadVariableMapping = useCallback(async () => {
        setMappingLoading(true);
        setMappingError(null);
        try {
            const res = await getVariableMapping(id);
            setVariableMapping(res?.mapping && typeof res.mapping === 'object' ? res.mapping : {});
        } catch (e) {
            setVariableMapping({});
            setMappingError(e.message || 'Не удалось загрузить сопоставление переменных');
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
        if (!isPrepareMode) return;
        loadScan();
    }, [isPrepareMode, loadScan]);

    useEffect(() => {
        let cancelled = false;

        const loadName = async () => {
            if (filename && filename !== 'Неизвестный файл') return;
            try {
                const list = await getDatasets();
                if (cancelled) return;
                const hit = Array.isArray(list) ? list.find((d) => d?.id === id) : null;
                if (hit?.filename) setFilename(hit.filename);
            } catch {
                if (!cancelled) setFilename((prev) => prev || 'Неизвестный файл');
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
            setDataReloadKey((v) => v + 1);
            if (isPrepareMode) await loadScan();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleStartPreparation = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const res = await cloneDatasetForPreparation(id);
            const nextId = res?.id;
            const nextFilename = res?.filename;
            const nextProfile = res?.profile;
            if (!nextId) throw new Error('Не удалось создать подготовленную копию');
            navigate(`/prepare/${nextId}`, { state: { profile: nextProfile || null, filename: nextFilename || nextId } });
        } catch (e) {
            setError(e?.message || 'Не удалось открыть подготовку данных');
        } finally {
            setLoading(false);
        }
    }, [id, navigate]);

    const handleHeaderMenu = useCallback(({ colName, x, y }) => {
        setActiveMenu({ colName, x, y });
    }, []);

    const baseRowIndex = (Math.max(1, profile?.page || 1) - 1) * PAGE_SIZE;

    const profileColumnsByName = useMemo(() => {
        const map = new Map();
        const cols = Array.isArray(profile?.columns) ? profile.columns : [];
        cols.forEach((c) => {
            if (c?.name) map.set(c.name, c);
        });
        return map;
    }, [profile]);

    const dataColumns = useMemo(() => {
        return (Array.isArray(dataColNames) ? dataColNames : []).map((name) => {
            const hit = profileColumnsByName.get(name);
            return hit || { name, type: 'text', missing_count: 0, unique_count: 0 };
        });
    }, [dataColNames, profileColumnsByName]);

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
                minWidth: 340,
                flex: 1,
                wrapText: true,
                autoHeight: true,
                tooltipField: 'original_name',
                cellClass: 'font-mono text-xs text-[color:var(--text-primary)] border-r border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]',
            },
            {
                headerName: 'Роль (анализ)',
                headerTooltip: 'Как использовать: ID — идентификатор; Группа/Подгруппа — разбиение; Ковариата — контрольная; Исход — целевая; Исключить — не использовать.',
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
                headerName: 'Фактор',
                headerTooltip: 'Отметь, если переменная задаёт группировку для описания и сравнения.',
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
                headerTooltip: 'Используется для повторных измерений и динамики (например: baseline/1m/3m).',
                field: 'timepoint',
                editable: true,
                width: 140,
                cellClass: 'font-mono text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Название (отчёт)',
                headerTooltip: 'Как показывать переменную в интерфейсе и отчёте (если пусто — используется исходное имя).',
                field: 'display_name',
                editable: true,
                minWidth: 220,
                flex: 1,
                wrapText: true,
                autoHeight: true,
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
                headerTooltip: 'Доля пропусков в столбце.',
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
            {
                headerName: 'Действия',
                field: '__actions__',
                editable: false,
                width: 130,
                sortable: false,
                filter: false,
                resizable: false,
                suppressMovable: true,
                cellRenderer: (p) => {
                    const name = p?.data?.original_name;
                    if (!name) return null;
                    return (
                        <button
                            type="button"
                            onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                handleDeleteDatasetColumn(name);
                            }}
                            className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                        >
                            Удалить
                        </button>
                    );
                },
            },
        ];
    }, [handleDeleteDatasetColumn]);

    const profileTypeByName = useMemo(() => {
        const map = {};
        (profile?.columns || []).forEach((c) => {
            if (c?.name) map[c.name] = c?.type;
        });
        return map;
    }, [profile]);

    const missingColumns = useMemo(() => {
        return (workspaceRows || [])
            .filter((r) => Number(r?.missing_pct || 0) > 0)
            .slice()
            .sort((a, b) => Number(b?.missing_pct || 0) - Number(a?.missing_pct || 0));
    }, [workspaceRows]);

    const missingPctByName = useMemo(() => {
        const map = {};
        (missingColumns || []).forEach((r) => {
            const name = r?.original_name;
            if (!name) return;
            map[name] = Number(r?.missing_pct || 0);
        });
        return map;
    }, [missingColumns]);

    const applyQualityAction = useCallback(
        async ({ column, action, mice = false } = {}) => {
            setLoading(true);
            setError(null);
            try {
                if (mice) {
                    const cols = (missingColumns || [])
                        .map((r) => r?.original_name)
                        .filter((name) => name && profileTypeByName[name] === 'numeric');
                    if (cols.length === 0) {
                        setError('Нет числовых столбцов с пропусками для MICE');
                        return;
                    }
                    if (!confirm(`Импутировать пропуски MICE для ${cols.length} числовых столбцов?`)) return;
                    await imputeMice(id, cols, { max_iter: 10, n_imputations: 5, random_state: 42 });
                } else {
                    if (!column || !action) return;

                    const missingPct = missingPctByName?.[column];
                    const pct = typeof missingPct === 'number' ? missingPct : 0;
                    const mostlyEmpty = isMostlyEmptyMissingPct(pct);

                    if (action === 'drop_na' && mostlyEmpty) {
                        const ok = confirm(`В столбце "${column}" почти все значения пустые (${pct}%). Удаление строк удалит почти все строки. Удалить столбец?`);
                        if (!ok) return;

                        await modifyDataset(
                            id,
                            [{ type: 'drop_col', column }],
                            { page: 1, limit: PAGE_SIZE }
                        );
                    } else if ((action === 'fill_mean' || action === 'fill_median' || action === 'fill_mode' || action === 'fill_locf' || action === 'fill_nocb') && mostlyEmpty) {
                        setError(`В столбце "${column}" только пропуски — заполнение не имеет смысла. Удали столбец.`);
                        return;
                    } else {
                        const label = action === 'drop_na' ? 'Удалить строки с пропусками' : 'Заполнить пропуски';
                        if (!confirm(`${label} в столбце "${column}"?`)) return;
                        await cleanColumn(id, column, action);
                    }
                }

                setQualityOpen(false);
                setPage(1);
                const fresh = await getDataset(id, 1, PAGE_SIZE);
                setProfile(fresh);
                setDataReloadKey((v) => v + 1);
                if (isPrepareMode) {
                    await loadScan();
                    await refreshPrepHistory();
                }
            } catch (e) {
                setError(e?.message || 'Не удалось применить действие');
            } finally {
                setLoading(false);
            }
        },
        [PAGE_SIZE, id, isPrepareMode, loadScan, missingColumns, missingPctByName, profileTypeByName, refreshPrepHistory]
    );

    const allColumnNames = useMemo(() => {
        return (profile?.columns || []).map((c) => c?.name).filter(Boolean);
    }, [profile]);

    const piiCandidates = useMemo(() => {
        const rx = /(фио|фамили|имя\b|отчество|телефон|phone|e-?mail|почта)/i;
        return allColumnNames.filter((n) => rx.test(String(n || '')));
    }, [allColumnNames]);

    const mixedTypeIssues = useMemo(() => {
        const issues = Array.isArray(scanReport?.issues) ? scanReport.issues : [];
        return issues
            .filter((i) => i?.type === 'mixed_type')
            .map((i) => {
                const col = i?.column;
                const colInfo = col && scanReport?.columns ? scanReport.columns[col] : null;
                const polluters = Array.isArray(colInfo?.polluting_values) ? colInfo.polluting_values : [];
                return {
                    column: col,
                    details: String(i?.details || ''),
                    polluters,
                    severity: String(i?.severity || ''),
                };
            })
            .filter((i) => i.column);
    }, [scanReport]);

    const handleDropColumns = useCallback(
        async (names) => {
            const cols = (Array.isArray(names) ? names : []).map((v) => String(v || '').trim()).filter(Boolean);
            if (cols.length === 0) return;
            if (!confirm(`Удалить колонки (${cols.length})?`)) return;
            setLoading(true);
            setError(null);
            try {
                await modifyDataset(
                    id,
                    cols.map((c) => ({ type: 'drop_col', column: c })),
                    { page: 1, limit: PAGE_SIZE }
                );
                setPage(1);
                const fresh = await getDataset(id, 1, PAGE_SIZE);
                setProfile(fresh);
                setDataReloadKey((v) => v + 1);
                if (isPrepareMode) {
                    await loadScan();
                    await refreshPrepHistory();
                }
            } catch (e) {
                setError(e?.message || 'Не удалось удалить колонки');
            } finally {
                setLoading(false);
            }
        },
        [PAGE_SIZE, id, isPrepareMode, loadScan, refreshPrepHistory]
    );

    const handleToNumeric = useCallback(
        async (col) => {
            const name = String(col || '').trim();
            if (!name) return;
            if (!confirm(`Преобразовать "${name}" в числа? Некорректные значения станут пустыми.`)) return;
            setLoading(true);
            setError(null);
            try {
                await cleanColumn(id, name, 'to_numeric');
                setPage(1);
                const fresh = await getDataset(id, 1, PAGE_SIZE);
                setProfile(fresh);
                setDataReloadKey((v) => v + 1);
                if (isPrepareMode) {
                    await loadScan();
                    await refreshPrepHistory();
                }
            } catch (e) {
                setError(e?.message || 'Не удалось преобразовать колонку');
            } finally {
                setLoading(false);
            }
        },
        [PAGE_SIZE, id, isPrepareMode, loadScan, refreshPrepHistory]
    );

    const handleComputeDerived = useCallback(async () => {
        const op = String(derivedOp || '').trim();
        const name = String(derivedName || '').trim();
        if (!name) {
            setError('Задай имя новой колонки');
            return;
        }

        const payload = { name, op };

        if (op === 'difference') {
            payload.a = String(derivedA || '').trim();
            payload.b = String(derivedB || '').trim();
        } else {
            payload.source = String(derivedSource || '').trim();
            const thr = Number.parseFloat(String(derivedThreshold || '').trim());
            payload.threshold = Number.isFinite(thr) ? thr : null;
        }

        setLoading(true);
        setError(null);
        try {
            const next = await computeDatasetColumn(id, payload);
            setProfile(next);
            setDataReloadKey((v) => v + 1);
            if (isPrepareMode) {
                await loadScan();
                await refreshPrepHistory();
            }
            setDerivedName('');
        } catch (e) {
            setError(e?.message || 'Не удалось добавить колонку');
        } finally {
            setLoading(false);
        }
    }, [derivedA, derivedB, derivedName, derivedOp, derivedSource, derivedThreshold, id, isPrepareMode, loadScan, refreshPrepHistory]);

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
                        <span className="w-4 text-center text-xs font-bold text-[color:var(--text-primary)]">#</span> Число
                    </button>
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'text' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-[color:var(--text-secondary)]">T</span> Текст
                    </button>
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'categorical' })} className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-[color:var(--accent)]">Ab</span> Категория
                    </button>
                </div>
                <div className="border-t border-[color:var(--border-color)] p-1">
                    <button
                        onClick={() => {
                            const newName = prompt("Переименовать столбец:", activeMenu.colName);
                            if (newName && newName !== activeMenu.colName) handleAction({ type: 'rename_col', column: activeMenu.colName, new_name: newName });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--text-primary)] rounded-[2px] transition-colors"
                    >
                        Переименовать
                    </button>
                    <button
                        onClick={() => {
                            if (confirm(`Удалить столбец "${activeMenu.colName}"?`)) handleAction({ type: 'drop_col', column: activeMenu.colName });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-[color:var(--bg-tertiary)] text-[color:var(--accent)] rounded-[2px] transition-colors"
                    >
                        Удалить
                    </button>
                </div>
            </div>
        );
    };

    const prepOverview = (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Чувствительные колонки</div>
                    <button
                        type="button"
                        onClick={() => handleDropColumns(piiCandidates)}
                        disabled={loading || piiCandidates.length === 0}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                    >
                        Удалить все
                    </button>
                </div>
                <div className="p-3 space-y-2">
                    {piiCandidates.length ? (
                        <div className="space-y-1">
                            {piiCandidates.slice(0, 8).map((name) => (
                                <div key={name} className="flex items-center justify-between gap-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{name}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">похоже на ФИО/контакты</div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => handleDropColumns([name])}
                                        className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                    >
                                        Удалить
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">Подозрительных колонок не найдено.</div>
                    )}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Смешанные типы</div>
                    <button
                        type="button"
                        onClick={() => goToPrepStep('cleanup')}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                    >
                        Открыть
                    </button>
                </div>
                <div className="p-3 space-y-2">
                    {mixedTypeIssues.length ? (
                        <div className="space-y-1">
                            {mixedTypeIssues.slice(0, 6).map((i) => (
                                <div key={i.column} className="flex items-center justify-between gap-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{i.column}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)] truncate">{i.polluters?.[0] ? `пример: ${String(i.polluters[0])}` : (i.details || 'разнородные значения')}</div>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => handleToNumeric(i.column)}
                                        className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                    >
                                        В числа
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">Проблем смешанных типов не найдено.</div>
                    )}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Пропуски</div>
                    <button
                        type="button"
                        onClick={() => goToPrepStep('missing')}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                    >
                        Открыть
                    </button>
                </div>
                <div className="p-3 space-y-2">
                    <div className="text-xs text-[color:var(--text-secondary)]">Колонок с пропусками: <span className="font-semibold text-[color:var(--text-primary)]">{missingColumns.length}</span></div>
                    {missingColumns.length ? (
                        <div className="space-y-1">
                            {missingColumns.slice(0, 6).map((r) => {
                                const pct = Number(r?.missing_pct || 0);
                                const mostlyEmpty = isMostlyEmptyMissingPct(pct);
                                const name = r?.original_name;
                                return (
                                <div key={r?.original_name} className="flex items-center justify-between gap-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{name}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">{pct}% пропусков</div>
                                    </div>
                                    {mostlyEmpty ? (
                                        <button
                                            type="button"
                                            onClick={() => handleDropColumns([name])}
                                            className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                        >
                                            Удалить столбец
                                        </button>
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={() => applyQualityAction({ column: name, action: 'drop_na' })}
                                            className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                        >
                                            Удалить строки
                                        </button>
                                    )}
                                </div>
                                );
                            })}
                        </div>
                    ) : null}
                </div>
            </div>
        </div>
    );

    const prepCleanup = (
        <div className="space-y-3">
            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Смешанные типы (цифры + текст)</div>
                    <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">{mixedTypeIssues.length}</div>
                </div>
                <div className="p-3">
                    {mixedTypeIssues.length ? (
                        <div className="space-y-2">
                            {mixedTypeIssues.map((i) => (
                                <div key={i.column} className="flex flex-col md:flex-row md:items-center justify-between gap-2 rounded-[2px] border border-[color:var(--border-color)] px-3 py-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{i.column}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)] truncate">{i.polluters?.length ? `пример: ${String(i.polluters[0])}` : (i.details || '')}</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => handleToNumeric(i.column)}
                                            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                        >
                                            В числа
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => handleDropColumns([i.column])}
                                            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                        >
                                            Удалить
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">Проблемных колонок не найдено.</div>
                    )}
                </div>
            </div>

            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">ФИО / контакты</div>
                    <button
                        type="button"
                        onClick={() => handleDropColumns(piiCandidates)}
                        disabled={loading || piiCandidates.length === 0}
                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                    >
                        Удалить все
                    </button>
                </div>
                <div className="p-3">
                    {piiCandidates.length ? (
                        <div className="space-y-2">
                            {piiCandidates.map((name) => (
                                <div key={name} className="flex items-center justify-between gap-2 rounded-[2px] border border-[color:var(--border-color)] px-3 py-2">
                                    <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate min-w-0">{name}</div>
                                    <button
                                        type="button"
                                        onClick={() => handleDropColumns([name])}
                                        className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                    >
                                        Удалить
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-xs text-[color:var(--text-secondary)]">По названиям колонок ФИО/контакты не определились.</div>
                    )}
                </div>
            </div>
        </div>
    );

    const prepMissing = (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                <div>
                    <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Пропуски</div>
                    <div className="text-xs text-[color:var(--text-secondary)]">Выбирай действие по каждой колонке — без отката.</div>
                </div>
                <button
                    type="button"
                    onClick={() => applyQualityAction({ mice: true })}
                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                >
                    MICE (числовые)
                </button>
            </div>
            <div className="p-3">
                {missingColumns.length ? (
                    <div className="space-y-2">
                        {missingColumns.map((r) => {
                            const name = r?.original_name;
                            const pct = Number(r?.missing_pct || 0);
                            const mostlyEmpty = isMostlyEmptyMissingPct(pct);
                            const t = name ? profileTypeByName[name] : null;
                            const fillAction = t === 'numeric' ? 'fill_mean' : t === 'datetime' ? 'fill_locf' : 'fill_mode';

                            return (
                                <div key={name} className="flex flex-col lg:flex-row lg:items-center justify-between gap-2 rounded-[2px] border border-[color:var(--border-color)] px-3 py-2">
                                    <div className="min-w-0">
                                        <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{name}</div>
                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">{pct}% пропусков</div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {mostlyEmpty ? (
                                            <button
                                                type="button"
                                                onClick={() => handleDropColumns([name])}
                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                            >
                                                Удалить столбец
                                            </button>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => applyQualityAction({ column: name, action: 'drop_na' })}
                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                            >
                                                Удалить строки
                                            </button>
                                        )}
                                        <button
                                            type="button"
                                            onClick={() => applyQualityAction({ column: name, action: fillAction })}
                                            disabled={mostlyEmpty}
                                            className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                                        >
                                            Заполнить
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="text-xs text-[color:var(--text-secondary)]">Пропусков не найдено.</div>
                )}
            </div>
        </div>
    );

    const prepDerived = (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]">
                <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Новые колонки</div>
                <div className="text-xs text-[color:var(--text-secondary)]">Разница и индикаторы — для подготовки исходов/групп.</div>
            </div>
            <div className="p-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                    <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Операция</div>
                    <select
                        value={derivedOp}
                        onChange={(e) => setDerivedOp(e.target.value)}
                        className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                    >
                        <option value="difference">Разница (A - B)</option>
                        <option value="indicator">Индикатор (≥ порога)</option>
                    </select>
                </div>

                <div>
                    <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Имя</div>
                    <input
                        value={derivedName}
                        onChange={(e) => setDerivedName(e.target.value)}
                        placeholder="например: delta_score"
                        className="h-9 w-full px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                    />
                </div>

                {derivedOp === 'difference' ? (
                    <>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">A</div>
                            <select
                                value={derivedA}
                                onChange={(e) => setDerivedA(e.target.value)}
                                className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                            >
                                <option value="">Выбери колонку</option>
                                {allColumnNames.map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">B</div>
                            <select
                                value={derivedB}
                                onChange={(e) => setDerivedB(e.target.value)}
                                className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                            >
                                <option value="">Выбери колонку</option>
                                {allColumnNames.map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                    </>
                ) : (
                    <>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Источник</div>
                            <select
                                value={derivedSource}
                                onChange={(e) => setDerivedSource(e.target.value)}
                                className="h-9 w-full bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
                            >
                                <option value="">Выбери колонку</option>
                                {allColumnNames.map((n) => (
                                    <option key={n} value={n}>{n}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)] mb-1">Порог</div>
                            <input
                                value={derivedThreshold}
                                onChange={(e) => setDerivedThreshold(e.target.value)}
                                placeholder="например: 10"
                                className="h-9 w-full px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                            />
                        </div>
                    </>
                )}
            </div>
            <div className="px-3 pb-3">
                <button
                    type="button"
                    onClick={handleComputeDerived}
                    className="h-9 px-4 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold tracking-[0.18em] uppercase"
                >
                    Добавить колонку
                </button>
            </div>
        </div>
    );

    const prepDone = (
        <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
            <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]">
                <div className="text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">Готово</div>
                <div className="text-xs text-[color:var(--text-secondary)]">Это отдельный датасет. Можно откатить последние изменения.</div>
            </div>
            <div className="p-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="text-sm font-semibold text-[color:var(--text-primary)]">Дальше по потоку</div>
                <div className="flex items-center gap-2">
                    <Link
                        to={`/prep/${id}`}
                        className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-bold tracking-[0.18em] uppercase hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                    >
                        Переменные
                    </Link>
                    <Link
                        to={`/design/${id}`}
                        className="h-9 px-3 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold tracking-[0.18em] uppercase"
                    >
                        Дизайн анализа
                    </Link>
                </div>
            </div>
        </div>
    );

    const prepPanel = (
        <div className="mb-4">
            <div className="rounded-[2px] border border-black bg-[color:var(--white)] overflow-hidden">
                <div className="px-4 py-3 border-b border-[color:var(--border-color)] flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                    <div className="min-w-0">
                        <div className="text-[10px] font-bold tracking-[0.22em] uppercase text-[color:var(--text-muted)]">Подготовка данных</div>
                        <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">Шаг {safePrepStepIndex + 1} / {PREP_STEPS.length}: {activePrepStep?.label}</div>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPrepStepIndex((v) => Math.max(0, v - 1))}
                            disabled={safePrepStepIndex <= 0}
                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                        >
                            Назад
                        </button>
                        <button
                            type="button"
                            onClick={() => setPrepStepIndex((v) => Math.min(PREP_STEPS.length - 1, v + 1))}
                            disabled={safePrepStepIndex >= PREP_STEPS.length - 1}
                            className="h-9 px-3 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-semibold disabled:opacity-50"
                        >
                            Далее
                        </button>
                    </div>
                </div>

                <div className="px-3 py-2 border-b border-[color:var(--border-color)] overflow-x-auto">
                    <div className="flex items-center gap-2 min-w-max">
                        {PREP_STEPS.map((s, idx) => {
                            const active = idx === safePrepStepIndex;
                            return (
                                <button
                                    key={s.id}
                                    type="button"
                                    onClick={() => setPrepStepIndex(idx)}
                                    className={`h-8 px-3 rounded-[999px] border text-[11px] font-bold tracking-[0.18em] uppercase transition-colors ${active
                                        ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]'
                                        : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                        }`}
                                >
                                    {idx + 1}. {s.label}
                                </button>
                            );
                        })}
                        <div className="ml-2 text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">
                            <button
                                type="button"
                                onClick={handleUndoPrepare}
                                disabled={!isPrepareMode || scanLoading || loading || prepUndoLoading || prepHistoryCount <= 0}
                                className="h-7 px-2 rounded-[999px] border border-[color:var(--border-color)] text-[10px] font-bold tracking-[0.18em] uppercase text-[color:var(--text-muted)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                            >
                                Откат{prepHistoryCount > 0 ? ` (${prepHistoryCount})` : ''}
                            </button>
                        </div>
                    </div>
                </div>

                <div className="p-3 bg-[color:var(--bg-secondary)]">
                    {activePrepStep?.id === 'overview' ? prepOverview : null}
                    {activePrepStep?.id === 'cleanup' ? prepCleanup : null}
                    {activePrepStep?.id === 'missing' ? prepMissing : null}
                    {activePrepStep?.id === 'derived' ? prepDerived : null}
                    {activePrepStep?.id === 'done' ? prepDone : null}
                </div>
            </div>
        </div>
    );

    return (
        <div
            className="min-h-screen bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)] font-sans"
            onClick={() => {
                setActiveMenu(null);
                setQualityOpen(false);
            }}
        >

            {/* Simple Header */}
            <div className="bg-white border-b border-[color:var(--border-color)] px-6 py-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-lg font-bold text-[color:var(--text-primary)]">{filename}</h1>
                        <div className="text-xs text-[color:var(--text-secondary)]">
                            {profile.row_count} строк • {profile.col_count} столбцов
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {!isPrepareMode && (
                            <button
                                type="button"
                                onClick={handleStartPreparation}
                                className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-bold tracking-[0.18em] uppercase hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                            >
                                Подготовка данных
                            </button>
                        )}
                        <Link
                            to={`/protocol?dataset=${encodeURIComponent(id)}`}
                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] text-xs font-bold tracking-[0.18em] uppercase inline-flex items-center justify-center hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                        >
                            Авто‑отчёт
                        </Link>
                        <Link
                            to={`/design/${id}`}
                            className="h-9 px-3 rounded-[2px] border border-black bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold tracking-[0.18em] uppercase inline-flex items-center justify-center"
                        >
                            Дизайн анализа
                        </Link>

                        {sheets.length > 0 && (
                            <select
                                className="h-9 bg-white border border-[color:var(--border-color)] text-sm rounded-[2px] px-3"
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
            </div>

            <main className="max-w-full p-4">
                {isPrepareMode ? prepPanel : null}
                {/* Main Data Grid */}
                <div
                    className="bg-white rounded border border-[color:var(--border-color)] flex flex-col overflow-hidden min-h-[500px] relative"
                    style={{ height: 'min(800px, calc(100vh - 180px))' }}
                >
                    {(loading || dataLoading) && (
                        <div className="absolute inset-0 bg-[color:var(--white)]/80 z-20 flex items-center justify-center">
                            <div className="bg-[color:var(--white)] p-4 rounded-[2px] border border-[color:var(--border-color)] flex items-center gap-3">
                                <div className="w-4 h-4 border-2 border-[color:var(--accent)] border-t-transparent rounded-[2px] animate-spin"></div>
                                <span className="text-sm font-semibold text-[color:var(--text-primary)]">Проверяю данные…</span>
                            </div>
                        </div>
                    )}

                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 px-4 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setWorkspaceView('data')}
                                className={`h-9 px-4 min-w-[160px] rounded-[2px] text-xs font-bold uppercase tracking-[0.18em] border transition-colors inline-flex items-center justify-center ${workspaceView === 'data'
                                    ? 'bg-[color:var(--black)] text-[color:var(--white)] border-[color:var(--black)]'
                                    : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                    }`}
                            >
                                ДАННЫЕ
                            </button>
                            <button
                                type="button"
                                onClick={() => setWorkspaceView('variables')}
                                className={`h-9 px-4 min-w-[160px] rounded-[2px] text-xs font-bold uppercase tracking-[0.18em] border transition-colors inline-flex items-center justify-center ${workspaceView === 'variables'
                                    ? 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)]'
                                    : 'bg-[color:var(--white)] text-[color:var(--text-secondary)] border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                    }`}
                            >
                                ЛИСТ ПЕРЕМЕННЫХ
                            </button>
                            {workspaceView === 'variables' && (
                                <div className="flex items-center gap-2 ml-2">
                                    <input
                                        value={mappingFilter}
                                        onChange={(e) => setMappingFilter(e.target.value)}
                                        placeholder="Поиск…"
                                        className="h-9 w-56 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                                    />
                                    <div className="relative">
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setQualityOpen((v) => !v);
                                            }}
                                            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                                            title="Рекомендации по пропускам"
                                        >
                                            Пропуски: {missingColumns.length}
                                        </button>
                                        {qualityOpen && (
                                            <div
                                                className="absolute right-0 mt-2 w-[520px] max-w-[80vw] bg-[color:var(--white)] border border-black rounded-[2px] shadow-lg z-30 overflow-hidden"
                                                onClick={(e) => e.stopPropagation()}
                                            >
                                                <div className="px-3 py-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-between">
                                                    <div className="text-xs font-bold tracking-[0.18em] uppercase text-[color:var(--text-primary)]">
                                                        Рекомендации по пропускам
                                                    </div>
                                                    <button
                                                        type="button"
                                                        onClick={() => setQualityOpen(false)}
                                                        className="h-7 px-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black"
                                                    >
                                                        Закрыть
                                                    </button>
                                                </div>

                                                <div className="p-3 space-y-2">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <div className="text-xs text-[color:var(--text-secondary)]">
                                                            Сначала обработай столбцы с высоким % пропусков.
                                                        </div>
                                                        <button
                                                            type="button"
                                                            onClick={() => applyQualityAction({ mice: true })}
                                                            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)]"
                                                        >
                                                            MICE (числовые)
                                                        </button>
                                                    </div>

                                                    <div className="max-h-64 overflow-auto custom-scrollbar divide-y divide-[color:var(--border-color)] border border-[color:var(--border-color)] rounded-[2px]">
                                                        {missingColumns.slice(0, 8).map((r) => {
                                                            const name = r?.original_name;
                                                            const pct = Number(r?.missing_pct || 0);
                                                            const mostlyEmpty = isMostlyEmptyMissingPct(pct);
                                                            const t = name ? profileTypeByName[name] : null;
                                                            const fillAction = t === 'numeric' ? 'fill_mean' : t === 'datetime' ? 'fill_locf' : 'fill_mode';

                                                            return (
                                                                <div key={name} className="flex items-center gap-3 px-3 py-2">
                                                                    <div className="min-w-0 flex-1">
                                                                        <div className="text-xs font-semibold truncate text-[color:var(--text-primary)]">{name}</div>
                                                                        <div className="text-[10px] font-mono text-[color:var(--text-muted)]">{pct}% пропусков</div>
                                                                    </div>
                                                                    <div className="flex items-center gap-2">
                                                                        {mostlyEmpty ? (
                                                                            <button
                                                                                type="button"
                                                                                onClick={() => handleDropColumns([name])}
                                                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold text-[color:var(--accent)] hover:border-black"
                                                                            >
                                                                                Удалить столбец
                                                                            </button>
                                                                        ) : (
                                                                            <button
                                                                                type="button"
                                                                                onClick={() => applyQualityAction({ column: name, action: 'drop_na' })}
                                                                                className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black"
                                                                            >
                                                                                Удалить строки
                                                                            </button>
                                                                        )}
                                                                        <button
                                                                            type="button"
                                                                            onClick={() => applyQualityAction({ column: name, action: fillAction })}
                                                                            disabled={mostlyEmpty}
                                                                            className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[11px] font-semibold hover:border-black disabled:opacity-50"
                                                                        >
                                                                            Заполнить
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                        {missingColumns.length === 0 && (
                                                            <div className="px-3 py-3 text-xs text-[color:var(--text-secondary)]">
                                                                Пропусков не найдено.
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
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
                                <input
                                    value={dataFilter}
                                    onChange={(e) => setDataFilter(e.target.value)}
                                    placeholder="Фильтр…"
                                    className="h-9 w-56 px-3 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                                />

                                <div className="hidden md:flex items-center gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setDataColOffset((v) => Math.max(0, v - dataColLimit))}
                                        disabled={loading || dataLoading || dataColOffset <= 0}
                                        className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                                    >
                                        ◀︎ Колонки
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            const totalCols = Number(profile?.col_count || 0);
                                            const maxOffset = Math.max(0, totalCols - Math.max(1, dataColLimit));
                                            setDataColOffset((v) => Math.min(maxOffset, v + dataColLimit));
                                        }}
                                        disabled={loading || dataLoading || (Number(profile?.col_count || 0) > 0 && dataColOffset + dataColLimit >= Number(profile?.col_count || 0))}
                                        className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                                    >
                                        Колонки ▶︎
                                    </button>
                                    <input
                                        type="number"
                                        min={1}
                                        max={Math.max(1, maxDataColOffset + 1)}
                                        value={Math.max(1, dataColOffset + 1)}
                                        onChange={(e) => {
                                            const totalCols = Number(profile?.col_count || 0);
                                            const raw = Number(e.target.value);
                                            if (!Number.isFinite(raw)) return;
                                            const maxStart = Math.max(1, Math.max(0, totalCols - Math.max(1, dataColLimit)) + 1);
                                            const next = Math.max(1, Math.min(maxStart, raw));
                                            setDataColOffset(next - 1);
                                        }}
                                        className="h-9 w-24 px-2 rounded-[2px] border border-[color:var(--border-color)] text-sm outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]"
                                    />
                                    <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                        {Number(profile?.col_count || 0) > 0
                                            ? `Колонки ${dataColOffset + 1}–${Math.min(Number(profile?.col_count || 0), dataColOffset + dataColLimit)} / ${profile.col_count}`
                                            : 'Колонки'}
                                    </div>
                                </div>

                                <div className="text-[11px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">
                                    Страница {profile.page} / {profile.total_pages}
                                </div>
                                <button
                                    type="button"
                                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                                    disabled={loading || dataLoading || (profile.page || 1) <= 1}
                                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
                                >
                                    Назад
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setPage((p) => Math.min(profile.total_pages || p + 1, p + 1))}
                                    disabled={loading || dataLoading || (profile.page || 1) >= (profile.total_pages || 1)}
                                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] disabled:opacity-50"
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

                    <div className="flex-1 min-h-0">
                        <ColumnMenu />
                        <Suspense fallback={gridFallback}>
                            {workspaceView === 'data' ? (
                                <EditableDataGrid
                                    columns={dataColumns}
                                    rows={dataRows}
                                    quickFilterText={dataFilter}
                                    loading={loading || dataLoading}
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
