import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
    getDataset,
    getDatasets,
    getSheets,
    reparseDataset,
    getDatasetContent,
    modifyDataset,
    cloneDatasetForPreparation,
} from '../../../lib/api';

const PAGE_SIZE = 500;

/**
 * Hook for core dataset profile state: loading, sheets, pagination, data grid content.
 */
export default function useProfileData({ id, locationState, navigate }) {
    const [profile, setProfile] = useState(locationState?.profile || null);
    const [filename, setFilename] = useState(locationState?.filename || 'Неизвестный файл');
    const [sheets, setSheets] = useState([]);
    const [selectedSheet, setSelectedSheet] = useState(null);
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

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeMenu, setActiveMenu] = useState(null);
    const menuRef = useRef(null);

    // Click outside to close menu
    useEffect(() => {
        function handleClickOutside(event) {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setActiveMenu(null);
            }
        }
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const loadProfile = useCallback(async () => {
        setLoading(true);
        try {
            const data = await getDataset(id, page, PAGE_SIZE);
            setProfile(data);
        } catch (e) {
            console.error(e);
            setError('Не удалось загрузить данные. Возможно, файл удален или поврежден.');
        } finally {
            setLoading(false);
        }
    }, [id, page]);

    const checkSheets = useCallback(async () => {
        try {
            const s = await getSheets(id);
            if (s && s.length > 0) setSheets(s);
        } catch (e) {
            console.error('Failed to load sheets', e);
        }
    }, [id]);

    // Clamp col offset
    useEffect(() => {
        setDataColOffset((prev) => Math.min(Math.max(0, prev), maxDataColOffset));
    }, [maxDataColOffset]);

    // Data content fetch
    useEffect(() => {
        if (!id) return;
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
        return () => { cancelled = true; };
    }, [dataColLimit, dataColOffset, dataReloadKey, id, page, selectedSheet]);

    // Initial load
    useEffect(() => { loadProfile(); }, [loadProfile]);
    useEffect(() => { checkSheets(); }, [checkSheets]);

    // Load filename
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
        return () => { cancelled = true; };
    }, [id, filename]);

    const handleSheetChange = useCallback(async (sheetName) => {
        if (sheetName === selectedSheet) return;
        setLoading(true);
        setError(null);
        try {
            const newProfile = await reparseDataset(id, 0, sheetName, { page: 1, limit: PAGE_SIZE });
            setProfile(newProfile);
            setSelectedSheet(sheetName);
            setPage(1);
            setDataReloadKey((v) => v + 1);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [id, selectedSheet]);

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
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        },
        [id, page]
    );

    const handleStartPreparation = useCallback(async () => {
        if (!id) return;
        setLoading(true);
        setError(null);
        try {
            const res = await cloneDatasetForPreparation(id);
            const nextId = res?.id;
            if (!nextId) throw new Error('Не удалось создать подготовленную копию');
            navigate(`/prepare/${nextId}`, { state: { profile: res?.profile || null, filename: res?.filename || nextId } });
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
        (Array.isArray(profile?.columns) ? profile.columns : []).forEach((c) => {
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

    const columnNameByIndex = useMemo(
        () => (profile?.columns || []).map((c) => c?.name).filter(Boolean),
        [profile]
    );

    const profileTypeByName = useMemo(() => {
        const map = {};
        (profile?.columns || []).forEach((c) => {
            if (c?.name) map[c.name] = c?.type;
        });
        return map;
    }, [profile]);

    const allColumnNames = useMemo(() => {
        return (profile?.columns || []).map((c) => c?.name).filter(Boolean);
    }, [profile]);

    return {
        profile, setProfile,
        filename,
        sheets, selectedSheet,
        page, setPage,
        PAGE_SIZE,
        dataColOffset, setDataColOffset,
        dataColLimit, maxDataColOffset,
        dataRows, dataColNames, dataLoading, dataFilter, setDataFilter,
        dataReloadKey, setDataReloadKey,
        loading, setLoading,
        error, setError,
        activeMenu, setActiveMenu,
        menuRef,
        handleSheetChange,
        handleAction,
        handleStartPreparation,
        handleHeaderMenu,
        baseRowIndex,
        profileColumnsByName,
        dataColumns,
        columnNameByIndex,
        profileTypeByName,
        allColumnNames,
        loadProfile,
    };
}
