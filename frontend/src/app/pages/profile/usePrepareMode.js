import { useState, useEffect, useCallback, useMemo } from 'react';
import {
    getDataset,
    getScanReport,
    getCleaningLog,
    getDeltaLog,
    cleanColumn,
    modifyDataset,
    computeDatasetColumn,
    imputeMice,
    getPrepareHistory,
    undoPrepare,
} from '../../../lib/api';

const MISSING_MOSTLY_EMPTY_THRESHOLD_PCT = 99.5;
const isMostlyEmptyMissingPct = (pct) => Number(pct) >= MISSING_MOSTLY_EMPTY_THRESHOLD_PCT;

const PAGE_SIZE = 500;

/**
 * Hook for data preparation mode: scan report, cleaning, missing values, derived columns.
 */
export default function usePrepareMode({
    id,
    isPrepareMode,
    profile, setProfile,
    setPage,
    setDataReloadKey,
    setLoading,
    setError,
    profileTypeByName,
    workspaceRows,
}) {
    const [scanReport, setScanReport] = useState(null);
    const [scanLoading, setScanLoading] = useState(false);
    const [cleaningLog, setCleaningLog] = useState(null);
    const [deltaLog, setDeltaLog] = useState(null);
    const [logLoading, setLogLoading] = useState(false);
    const [prepHistoryCount, setPrepHistoryCount] = useState(0);
    const [prepUndoLoading, setPrepUndoLoading] = useState(false);
    const [qualityOpen, setQualityOpen] = useState(false);

    // Derived column state
    const [derivedOp, setDerivedOp] = useState('difference');
    const [derivedName, setDerivedName] = useState('');
    const [derivedA, setDerivedA] = useState('');
    const [derivedB, setDerivedB] = useState('');
    const [derivedSource, setDerivedSource] = useState('');
    const [derivedThreshold, setDerivedThreshold] = useState('');

    // Prep steps
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
        PREP_STEPS.forEach((s, idx) => { map[s.id] = idx; });
        return map;
    }, [PREP_STEPS]);

    const goToPrepStep = useCallback((stepId) => {
        const idx = prepStepIndexById?.[stepId];
        if (typeof idx !== 'number') return;
        setPrepStepIndex(idx);
    }, [prepStepIndexById]);

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

    const loadLogs = useCallback(async () => {
        if (!id) return;
        setLogLoading(true);
        try {
            const [cleaning, delta] = await Promise.all([getCleaningLog(id), getDeltaLog(id)]);
            setCleaningLog(cleaning && typeof cleaning === 'object' ? cleaning : null);
            setDeltaLog(delta && typeof delta === 'object' ? delta : null);
        } catch {
            setCleaningLog(null);
            setDeltaLog(null);
        } finally {
            setLogLoading(false);
        }
    }, [id]);

    const refreshPrepHistory = useCallback(async () => {
        if (!isPrepareMode || !id) return;
        try {
            const res = await getPrepareHistory(id);
            const n = Number(res?.count ?? 0);
            setPrepHistoryCount(Number.isFinite(n) ? n : 0);
        } catch {
            setPrepHistoryCount(0);
        }
    }, [id, isPrepareMode]);

    const handleUndoPrepare = useCallback(async () => {
        if (!isPrepareMode || !id || prepUndoLoading) return;
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
    }, [id, isPrepareMode, loadScan, prepUndoLoading, refreshPrepHistory, setDataReloadKey, setError, setLoading, setPage, setProfile]);

    // Effects
    useEffect(() => { if (isPrepareMode) loadScan(); }, [isPrepareMode, loadScan]);
    useEffect(() => { loadLogs(); }, [loadLogs]);
    useEffect(() => { if (isPrepareMode) refreshPrepHistory(); }, [id, isPrepareMode, refreshPrepHistory]);

    // Derived data
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
            if (name) map[name] = Number(r?.missing_pct || 0);
        });
        return map;
    }, [missingColumns]);

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
                return { column: col, details: String(i?.details || ''), polluters, severity: String(i?.severity || '') };
            })
            .filter((i) => i.column);
    }, [scanReport]);

    const cleaningActions = useMemo(() => {
        const actions = cleaningLog?.auto?.actions;
        return Array.isArray(actions) ? actions : [];
    }, [cleaningLog]);

    const deltaEntries = useMemo(() => {
        const entries = Array.isArray(deltaLog?.entries) ? deltaLog.entries : [];
        return entries.slice(-5).reverse();
    }, [deltaLog]);

    // Handlers
    const applyQualityAction = useCallback(
        async ({ column, action, mice = false } = {}) => {
            setLoading(true);
            setError(null);
            try {
                if (mice) {
                    const cols = (missingColumns || [])
                        .map((r) => r?.original_name)
                        .filter((name) => name && profileTypeByName[name] === 'numeric');
                    if (cols.length === 0) { setError('Нет числовых столбцов с пропусками для MICE'); return; }
                    if (!confirm(`Импутировать пропуски MICE для ${cols.length} числовых столбцов?`)) return;
                    await imputeMice(id, cols, { max_iter: 10, n_imputations: 5, random_state: 42 });
                } else {
                    if (!column || !action) return;
                    const missingPct = missingPctByName?.[column];
                    const pct = typeof missingPct === 'number' ? missingPct : 0;
                    const mostlyEmpty = isMostlyEmptyMissingPct(pct);

                    if (action === 'drop_na' && mostlyEmpty) {
                        if (!confirm(`В столбце "${column}" почти все значения пустые (${pct}%). Удалить столбец?`)) return;
                        await modifyDataset(id, [{ type: 'drop_col', column }], { page: 1, limit: PAGE_SIZE });
                    } else if (['fill_mean', 'fill_median', 'fill_mode', 'fill_locf', 'fill_nocb'].includes(action) && mostlyEmpty) {
                        setError(`В столбце "${column}" только пропуски — заполнение не имеет смысла. Удали столбец.`);
                        return;
                    } else if (action === 'normalize_categories') {
                        if (!confirm(`Нормализовать значения категорий в столбце "${column}"?`)) return;
                        await cleanColumn(id, column, action);
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
        [id, isPrepareMode, loadScan, missingColumns, missingPctByName, profileTypeByName, refreshPrepHistory, setDataReloadKey, setError, setLoading, setPage, setProfile]
    );

    const handleDropColumns = useCallback(
        async (names) => {
            const cols = (Array.isArray(names) ? names : []).map((v) => String(v || '').trim()).filter(Boolean);
            if (cols.length === 0) return;
            if (!confirm(`Удалить колонки (${cols.length})?`)) return;
            setLoading(true);
            setError(null);
            try {
                await modifyDataset(id, cols.map((c) => ({ type: 'drop_col', column: c })), { page: 1, limit: PAGE_SIZE });
                setPage(1);
                const fresh = await getDataset(id, 1, PAGE_SIZE);
                setProfile(fresh);
                setDataReloadKey((v) => v + 1);
                if (isPrepareMode) { await loadScan(); await refreshPrepHistory(); }
            } catch (e) {
                setError(e?.message || 'Не удалось удалить колонки');
            } finally {
                setLoading(false);
            }
        },
        [id, isPrepareMode, loadScan, refreshPrepHistory, setDataReloadKey, setError, setLoading, setPage, setProfile]
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
                if (isPrepareMode) { await loadScan(); await refreshPrepHistory(); }
            } catch (e) {
                setError(e?.message || 'Не удалось преобразовать колонку');
            } finally {
                setLoading(false);
            }
        },
        [id, isPrepareMode, loadScan, refreshPrepHistory, setDataReloadKey, setError, setLoading, setPage, setProfile]
    );

    const handleComputeDerived = useCallback(async () => {
        const op = String(derivedOp || '').trim();
        const name = String(derivedName || '').trim();
        if (!name) { setError('Задай имя новой колонки'); return; }
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
            if (isPrepareMode) { await loadScan(); await refreshPrepHistory(); }
            setDerivedName('');
        } catch (e) {
            setError(e?.message || 'Не удалось добавить колонку');
        } finally {
            setLoading(false);
        }
    }, [derivedA, derivedB, derivedName, derivedOp, derivedSource, derivedThreshold, id, isPrepareMode, loadScan, refreshPrepHistory, setDataReloadKey, setError, setLoading, setProfile]);

    return {
        scanReport, scanLoading,
        cleaningLog, logLoading,
        prepHistoryCount, prepUndoLoading,
        qualityOpen, setQualityOpen,
        derivedOp, setDerivedOp,
        derivedName, setDerivedName,
        derivedA, setDerivedA,
        derivedB, setDerivedB,
        derivedSource, setDerivedSource,
        derivedThreshold, setDerivedThreshold,
        PREP_STEPS, prepStepIndex, setPrepStepIndex,
        safePrepStepIndex, activePrepStep,
        goToPrepStep,
        handleUndoPrepare,
        missingColumns, missingPctByName,
        piiCandidates, mixedTypeIssues,
        cleaningActions, deltaEntries,
        applyQualityAction,
        handleDropColumns,
        handleToNumeric,
        handleComputeDerived,
    };
}
