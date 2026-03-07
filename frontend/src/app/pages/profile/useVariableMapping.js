import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
    getVariableMapping,
    putVariableMapping,
} from '../../../lib/api';

/**
 * Hook for variable mapping CRUD: load, save (debounced), workspace grid rows/cols, bulk ops.
 */
export default function useVariableMapping({ id, profile }) {
    const [variableMapping, setVariableMapping] = useState({});
    const [mappingLoading, setMappingLoading] = useState(false);
    const [mappingSaving, setMappingSaving] = useState(false);
    const [mappingError, setMappingError] = useState(null);
    const [mappingFilter, setMappingFilter] = useState('');
    const [bulkSubgroup, setBulkSubgroup] = useState('');
    const [bulkTimepoint, setBulkTimepoint] = useState('');
    const mappingSaveTimerRef = useRef(null);
    const variableGridApiRef = useRef(null);

    const scheduleSaveMapping = useCallback(
        (nextMapping) => {
            if (mappingSaveTimerRef.current) clearTimeout(mappingSaveTimerRef.current);
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

    useEffect(() => {
        loadVariableMapping();
    }, [loadVariableMapping]);

    const columnNameByIndex = useMemo(
        () => (profile?.columns || []).map((c) => c?.name).filter(Boolean),
        [profile]
    );

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
                headerName: 'Переменная', field: 'original_name', pinned: 'left', lockPinned: true, editable: false, minWidth: 340, flex: 1, wrapText: true, autoHeight: true, tooltipField: 'original_name',
                cellClass: 'font-mono text-xs text-[color:var(--text-primary)] border-r border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]',
            },
            {
                headerName: 'Роль (анализ)', headerTooltip: 'Как использовать: ID — идентификатор; Группа/Подгруппа — разбиение; Ковариата — контрольная; Исход — целевая; Исключить — не использовать.',
                field: 'role', editable: true, width: 160, cellEditor: 'agSelectCellEditor', cellEditorParams: { values: roleValues },
            },
            {
                headerName: 'Тип', field: 'data_type', editable: true, width: 150, cellEditor: 'agSelectCellEditor', cellEditorParams: { values: typeValues },
                cellClass: 'font-mono text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Фактор', headerTooltip: 'Отметь, если переменная задаёт группировку для описания и сравнения.',
                field: 'group_var', editable: true, width: 110, cellRenderer: 'agCheckboxCellRenderer', cellEditor: 'agCheckboxCellEditor',
                cellClass: 'border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Подгруппа', field: 'subgroup', editable: true, width: 180,
                cellClass: 'text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Точка времени', headerTooltip: 'Используется для повторных измерений и динамики (например: baseline/1m/3m).',
                field: 'timepoint', editable: true, width: 140,
                cellClass: 'font-mono text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Название (отчёт)', headerTooltip: 'Как показывать переменную в интерфейсе и отчёте (если пусто — используется исходное имя).',
                field: 'display_name', editable: true, minWidth: 220, flex: 1, wrapText: true, autoHeight: true,
                cellClass: 'text-xs text-[color:var(--text-secondary)] border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Описательная', field: 'include_descriptive', editable: true, width: 100, cellRenderer: 'agCheckboxCellRenderer', cellEditor: 'agCheckboxCellEditor',
                cellClass: 'border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Сравнение', field: 'include_comparison', editable: true, width: 120, cellRenderer: 'agCheckboxCellRenderer', cellEditor: 'agCheckboxCellEditor',
                cellClass: 'border-r border-[color:var(--border-color)]',
            },
            {
                headerName: 'Пропуски%', headerTooltip: 'Доля пропусков в столбце.',
                field: 'missing_pct', editable: false, width: 120, cellClass: 'font-mono text-xs text-[color:var(--text-muted)]',
            },
            {
                headerName: 'Уникальных', field: 'unique_count', editable: false, width: 110,
                cellClass: 'font-mono text-xs text-[color:var(--text-muted)]',
            },
        ];
    }, []);

    const handleWorkspaceUpdateCell = useCallback(
        ({ rowIndex, colName, value }) => {
            const columnName = columnNameByIndex[rowIndex];
            if (!columnName) return;
            setVariableMapping((prev) => {
                const safePrev = prev && typeof prev === 'object' ? prev : {};
                const next = { ...safePrev };
                const current = next[columnName] && typeof next[columnName] === 'object' ? next[columnName] : {};
                next[columnName] = { ...current, [colName]: value };
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

    return {
        variableMapping, setVariableMapping,
        mappingLoading, mappingSaving, mappingError,
        mappingFilter, setMappingFilter,
        bulkSubgroup, setBulkSubgroup,
        bulkTimepoint, setBulkTimepoint,
        variableGridApiRef,
        scheduleSaveMapping,
        workspaceRows,
        workspaceColumnDefs,
        handleWorkspaceUpdateCell,
        subgroupSuggestions,
        timepointSuggestions,
        applyBulkMappingField,
    };
}
