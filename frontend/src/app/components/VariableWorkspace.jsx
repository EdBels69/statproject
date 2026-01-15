import React, { useMemo, useCallback, useRef, useState } from 'react';
import { FixedSizeList as List } from 'react-window';
import AutoSizer from 'react-virtualized-auto-sizer';
import {
    MagnifyingGlassIcon,
    FunnelIcon,
    HashtagIcon,
    TagIcon,
    CalendarIcon,
    DocumentTextIcon,
    XMarkIcon,
    CheckIcon
} from '@heroicons/react/24/outline';

/**
 * VariableWorkspace - Advanced variable management for datasets with 100+ columns.
 * Features:
 * - Virtualized list for performance
 * - Fuzzy search
 * - Filter by type (Numeric, Categorical, DateTime, Text)
 * - Multi-select with checkboxes
 * - Grouping by type
 */

const TYPE_CONFIG = {
    numeric: { icon: HashtagIcon, label: 'Числовая' },
    categorical: { icon: TagIcon, label: 'Категориальная' },
    datetime: { icon: CalendarIcon, label: 'Дата/время' },
    text: { icon: DocumentTextIcon, label: 'Текст' }
};

function getVariableType(column) {
    if (!column || !column.type) return 'text';
    const dtype = String(column.type).toLowerCase();

    if (dtype.includes('int') || dtype.includes('float') || dtype === 'numeric') {
        return 'numeric';
    }
    if (dtype.includes('category') || dtype === 'categorical') {
        return 'categorical';
    }
    if (dtype.includes('datetime') || dtype.includes('date')) {
        return 'datetime';
    }
    return 'text';
}

export default function VariableWorkspace({
    columns = [],
    selectedVariables = [],
    onSelectionChange,
    onVariableClick,
    columnStatsByName,
    roleByName,
    roles,
    onRolesChange,
    secondaryRoleLabel,
    mode = 'multi', // 'single' or 'multi'
    showStats = true
}) {
    const [search, setSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState(null); // null = all
    const [roleFilter, setRoleFilter] = useState('all');
    const [showFilters, setShowFilters] = useState(false);
    const [previewName, setPreviewName] = useState(null);
    const [dragActiveRole, setDragActiveRole] = useState(null);
    const [draggingName, setDraggingName] = useState(null);
    const [focusedIndex, setFocusedIndex] = useState(0);
    const listRef = useRef(null);

    const effectivePreviewName = previewName
        ? previewName
        : selectedVariables.length > 0
            ? selectedVariables[selectedVariables.length - 1]
            : null;

    // Process columns with type detection
    const processedColumns = useMemo(() => {
        return columns.map(col => ({
            ...col,
            varType: getVariableType(col),
            name: col.name || col
        }));
    }, [columns]);

    // Filter and search
    const filteredColumns = (() => {
        let result = processedColumns;

        if (typeFilter) {
            result = result.filter(col => col.varType === typeFilter);
        }

        if (search.trim()) {
            const query = search.toLowerCase();
            result = result.filter(col =>
                col.name.toLowerCase().includes(query)
            );
        }

        if (roleFilter && roleFilter !== 'all') {
            result = result.filter((col) => {
                const role = roleByName?.[col.name] || 'unused';
                return role === roleFilter;
            });
        }

        return result;
    })();

    const safeFocusedIndex = filteredColumns.length > 0
        ? Math.max(0, Math.min(focusedIndex, filteredColumns.length - 1))
        : 0;

    // Type statistics
    const typeStats = useMemo(() => {
        const stats = { numeric: 0, categorical: 0, datetime: 0, text: 0 };
        processedColumns.forEach(col => {
            stats[col.varType]++;
        });
        return stats;
    }, [processedColumns]);

    const selectedSet = useMemo(() => new Set(selectedVariables), [selectedVariables]);

    const handleToggle = useCallback((colName) => {
        if (mode === 'single') {
            onSelectionChange?.([colName]);
            onVariableClick?.(colName);
            return;
        }

        const newSelection = selectedSet.has(colName)
            ? selectedVariables.filter(v => v !== colName)
            : [...selectedVariables, colName];
        onSelectionChange?.(newSelection);
    }, [mode, selectedSet, selectedVariables, onSelectionChange, onVariableClick]);

    const preview = useMemo(() => {
        if (!effectivePreviewName) return null;
        const base = processedColumns.find((c) => c.name === effectivePreviewName) || null;
        const stats = columnStatsByName?.[effectivePreviewName] || null;
        const merged = base
            ? { ...base, ...(stats || {}) }
            : stats
                ? { ...(stats || {}), name: effectivePreviewName }
                : { name: effectivePreviewName };

        const histogram = merged?.histogram;
        const bins = Array.isArray(histogram?.bins) ? histogram.bins : null;
        const maxBin = bins ? Math.max(1, ...bins) : 1;
        const bars = bins
            ? bins.map((b) => ({ value: b, pct: Math.round((b / maxBin) * 100) }))
            : [];

        const topValues = Array.isArray(merged?.top_values)
            ? merged.top_values
            : Array.isArray(merged?.categories)
                ? merged.categories.slice(0, 3).map((v) => ({ value: v, count: null }))
                : [];

        return {
            merged,
            bars,
            topValues,
        };
    }, [effectivePreviewName, processedColumns, columnStatsByName]);

    const assignRole = useCallback((roleKey, name) => {
        if (!name) return;
        const next = {
            target: roles?.target || '',
            group: roles?.group || '',
            covariates: Array.isArray(roles?.covariates) ? roles.covariates : [],
        };

        if (roleKey === 'target') {
            next.target = name;
        } else if (roleKey === 'group') {
            next.group = name;
        } else if (roleKey === 'covariates') {
            next.covariates = next.covariates.includes(name)
                ? next.covariates
                : [...next.covariates, name];
        }

        onRolesChange?.(next);
        setPreviewName(name);
    }, [roles, onRolesChange]);

    const removeRole = useCallback((roleKey, name) => {
        const next = {
            target: roles?.target || '',
            group: roles?.group || '',
            covariates: Array.isArray(roles?.covariates) ? roles.covariates : [],
        };

        if (roleKey === 'target') {
            next.target = '';
        } else if (roleKey === 'group') {
            next.group = '';
        } else if (roleKey === 'covariates') {
            const list = Array.isArray(next.covariates) ? next.covariates : [];
            next.covariates = name ? list.filter((n) => n !== name) : [];
        }

        onRolesChange?.(next);
    }, [onRolesChange, roles]);

    const handleDragStart = (e, name) => {
        if (!name) return;
        setPreviewName(name);
        setDraggingName(name);
        e.dataTransfer.setData('application/x-statwizard-variable', name);
        e.dataTransfer.setData('variable', name);
        e.dataTransfer.setData('text/plain', name);
        e.dataTransfer.effectAllowed = 'move';
    };

    const handleDragEnd = () => {
        setDraggingName(null);
        setDragActiveRole(null);
    };

    const handleDrop = (e, roleKey) => {
        e.preventDefault();
        const name = e.dataTransfer.getData('application/x-statwizard-variable')
            || e.dataTransfer.getData('variable')
            || e.dataTransfer.getData('text/plain');
        assignRole(roleKey, name);
        setDragActiveRole(null);
    };

    const handleDragOver = (e, roleKey) => {
        e.preventDefault();
        setDragActiveRole(roleKey);
    };

    const handleDragLeave = (e, roleKey) => {
        const current = e?.currentTarget;
        const next = e?.relatedTarget;
        if (current && next && typeof current.contains === 'function' && current.contains(next)) return;
        setDragActiveRole((prev) => (prev === roleKey ? null : prev));
    };

    const focusItem = useCallback((nextIndex) => {
        if (filteredColumns.length === 0) return;
        const safe = Math.max(0, Math.min(nextIndex, filteredColumns.length - 1));
        setFocusedIndex(safe);
        const name = filteredColumns[safe]?.name;
        if (name) setPreviewName(name);
        if (listRef.current?.scrollToItem) listRef.current.scrollToItem(safe, 'smart');
    }, [filteredColumns]);

    const handleListKeyDown = useCallback((e) => {
        const tag = e.target?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
        if (filteredColumns.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            focusItem(safeFocusedIndex + 1);
            return;
        }

        if (e.key === 'ArrowUp') {
            e.preventDefault();
            focusItem(safeFocusedIndex - 1);
            return;
        }

        if (e.key === 'Enter') {
            e.preventDefault();
            const name = filteredColumns[safeFocusedIndex]?.name;
            if (!name) return;

            if (mode === 'single') {
                onSelectionChange?.([name]);
                onVariableClick?.(name);
                return;
            }

            const roleKey = roles?.target
                ? (roles?.group ? 'covariates' : 'group')
                : 'target';
            assignRole(roleKey, name);
            return;
        }

        if (e.key === 't' || e.key === 'T') {
            e.preventDefault();
            const name = filteredColumns[safeFocusedIndex]?.name;
            if (name) assignRole('target', name);
            return;
        }

        if (e.key === 'g' || e.key === 'G') {
            e.preventDefault();
            const name = filteredColumns[safeFocusedIndex]?.name;
            if (name) assignRole('group', name);
            return;
        }

        if (e.key === 'c' || e.key === 'C') {
            e.preventDefault();
            const name = filteredColumns[safeFocusedIndex]?.name;
            if (name) assignRole('covariates', name);
            return;
        }
    }, [assignRole, filteredColumns, safeFocusedIndex, mode, onSelectionChange, onVariableClick, roles?.group, roles?.target, focusItem]);

    const handleSelectAll = () => {
        const allNames = filteredColumns.map(c => c.name);
        onSelectionChange?.(allNames);
    };

    const handleClearSelection = () => {
        onSelectionChange?.([]);
    };

    // Render single variable row
    const VariableRow = useCallback(({ index, style, data }) => {
        const col = data.items[index];
        if (!col) return null;

        const isSelected = data.selectedSet.has(col.name);
        const isFocused = data.focusedIndex === index;
        const typeConfig = TYPE_CONFIG[col.varType] || TYPE_CONFIG.text;
        const Icon = typeConfig.icon;

        const mergedStats = data.columnStatsByName?.[col.name] || null;
        const uniqueCount = mergedStats?.unique_count ?? col.unique_count;
        const missingCount = mergedStats?.missing_count ?? col.missing_count;
        const mean = mergedStats?.mean;

        return (
            <div style={style}>
                <div
                    onClick={() => {
                        data.onToggle(col.name);
                        data.onPreview(col.name);
                    }}
                    onMouseEnter={() => data.onFocus(index)}
                    draggable
                    onDragStart={(e) => data.onDragStart(e, col.name)}
                    onDragEnd={data.onDragEnd}
                    className={`
            variable-card h-full flex items-center gap-3 px-3 cursor-pointer transition-colors transition-transform active:scale-[0.99] cursor-grab active:cursor-grabbing
            border-b border-[color:var(--border-color)]
            ${isSelected ? 'bg-[color:var(--bg-secondary)] border-l-2 border-l-[color:var(--accent)]' : 'hover:bg-[color:var(--bg-secondary)]'}
            ${isFocused ? 'ring-1 ring-[color:var(--accent)] ring-inset' : ''}
            ${data.draggingName === col.name ? 'opacity-60 scale-[0.985]' : ''}
          `}
                >
                    {/* Checkbox for multi-select */}
                    {data.mode === 'multi' && (
                        <div className={`
              w-4 h-4 rounded-[2px] border flex items-center justify-center flex-shrink-0
              ${isSelected ? 'bg-[color:var(--accent)] border-[color:var(--accent)]' : 'border-[color:var(--border-color)] bg-[color:var(--white)]'}
            `}>
                            {isSelected && <CheckIcon className="w-3 h-3 text-white" />}
                        </div>
                    )}

                    {/* Type badge */}
                    <div className={`
            px-1.5 py-0.5 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-muted)] text-[10px] font-semibold uppercase flex-shrink-0
          `}>
                        <Icon className="w-3 h-3 inline mr-0.5" />
                        {col.varType.slice(0, 3)}
                    </div>

                    {/* Variable name */}
                    <span className={`
            text-sm truncate flex-1
            ${isSelected ? 'font-semibold text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}
          `} title={col.name}>
                        {col.name}
                    </span>

                    {/* Stats preview */}
                    {data.showStats && (
                        <div className="flex items-center gap-2 flex-shrink-0 text-[10px] font-mono text-[color:var(--text-muted)]">
                            {typeof missingCount === 'number' && missingCount > 0 ? (
                                <span>{missingCount} NA</span>
                            ) : null}
                            {typeof uniqueCount === 'number' ? (
                                <span>u:{uniqueCount}</span>
                            ) : null}
                            {typeof mean === 'number' ? (
                                <span>μ:{mean < 0.001 && mean > 0 ? '<0.001' : mean.toFixed(3)}</span>
                            ) : null}
                        </div>
                    )}
                </div>
            </div>
        );
    }, []);

    const listData = useMemo(() => ({
        items: filteredColumns,
        selectedSet,
        onToggle: handleToggle,
        onPreview: (name) => setPreviewName(name),
        onFocus: (idx) => setFocusedIndex(idx),
        focusedIndex: safeFocusedIndex,
        onDragStart: handleDragStart,
        onDragEnd: handleDragEnd,
        draggingName,
        columnStatsByName,
        mode,
        showStats
    }), [filteredColumns, selectedSet, handleToggle, safeFocusedIndex, mode, showStats, columnStatsByName, draggingName]);

    return (
        <div className="flex flex-col h-full bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden">
            {/* Header */}
            <div className="flex-shrink-0 p-3 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
                <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">Переменные</h3>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setShowFilters(!showFilters)}
                            className={`p-1.5 rounded-[2px] border transition-colors ${showFilters ? 'bg-[color:var(--white)] border-[color:var(--border-color)] text-[color:var(--accent)]' : 'bg-transparent border-transparent text-[color:var(--text-muted)] hover:bg-[color:var(--white)] hover:border-[color:var(--border-color)] hover:text-[color:var(--text-primary)]'}`}
                            type="button"
                        >
                            <FunnelIcon className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Search */}
                <div className="relative">
                    <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[color:var(--text-muted)]" />
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => {
                            setSearch(e.target.value);
                            setFocusedIndex(0);
                        }}
                        placeholder="Поиск по названию…"
                        className="w-full pl-9 pr-8 py-2 text-sm border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] text-[color:var(--text-primary)] placeholder:text-[color:var(--text-muted)] focus:outline-none focus:border-[color:var(--accent)]"
                    />
                    {search && (
                        <button
                            onClick={() => {
                                setSearch('');
                                setFocusedIndex(0);
                            }}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                            type="button"
                        >
                            <XMarkIcon className="w-4 h-4" />
                        </button>
                    )}
                </div>

                {/* Type filters */}
                {showFilters && (
                    <div className="flex flex-wrap gap-1 mt-2">
                        <button
                            onClick={() => {
                                setTypeFilter(null);
                                setFocusedIndex(0);
                            }}
                            className={`px-2 py-1 text-xs rounded-[2px] border transition-colors ${typeFilter === null
                                    ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-[color:var(--white)]'
                                    : 'bg-[color:var(--white)] border-[color:var(--border-color)] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]'
                                }`}
                            type="button"
                        >
                            Все ({processedColumns.length})
                        </button>
                        {Object.entries(TYPE_CONFIG).map(([type, config]) => (
                            <button
                                key={type}
                                onClick={() => {
                                    setTypeFilter(typeFilter === type ? null : type);
                                    setFocusedIndex(0);
                                }}
                                className={`px-2 py-1 text-xs rounded-[2px] border transition-colors flex items-center gap-1 ${typeFilter === type
                                        ? 'bg-[color:var(--bg-secondary)] border-[color:var(--accent)] text-[color:var(--accent)]'
                                        : 'bg-[color:var(--white)] border-[color:var(--border-color)] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]'
                                    }`}
                                type="button"
                            >
                                {config.label} ({typeStats[type]})
                            </button>
                        ))}
                    </div>
                )}

                {showFilters && (
                    <div className="flex flex-wrap gap-1 mt-2">
                        {[{ id: 'all', label: 'Все' }, { id: 'unused', label: 'Не назначены' }, { id: 'target', label: 'Target' }, { id: 'group', label: secondaryRoleLabel || 'Group' }, { id: 'covariate', label: 'Covariates' }].map((opt) => (
                            <button
                                key={opt.id}
                                onClick={() => {
                                    setRoleFilter(roleFilter === opt.id ? 'all' : opt.id);
                                    setFocusedIndex(0);
                                }}
                                className={`px-2 py-1 text-xs rounded-[2px] border transition-colors ${roleFilter === opt.id
                                    ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-[color:var(--white)]'
                                    : 'bg-[color:var(--white)] border-[color:var(--border-color)] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]'
                                    }`}
                                type="button"
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                )}
            </div>

            <div className="flex-shrink-0 p-3 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                <div className="grid grid-cols-1 gap-2">
                    <div
                        onDragOver={(e) => handleDragOver(e, 'target')}
                        onDragLeave={(e) => handleDragLeave(e, 'target')}
                        onDrop={(e) => handleDrop(e, 'target')}
                        className={`rounded-[2px] border px-3 py-2 text-xs transition-colors ${roles?.target ? 'bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]' : 'bg-[color:var(--white)] border-[color:var(--border-color)]'} ${dragActiveRole === 'target' ? 'border-[color:var(--accent)] bg-[color:var(--bg-tertiary)]' : ''}`}
                        aria-label="Цель: зона назначения"
                    >
                        <div className="flex items-center justify-between gap-3">
                            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Цель</div>
                            {roles?.target ? (
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeRole('target');
                                    }}
                                    className="p-1 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                    aria-label="Убрать цель"
                                >
                                    <XMarkIcon className="w-4 h-4" />
                                </button>
                            ) : null}
                        </div>
                        <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{roles?.target || 'Перетащите переменную сюда'}</div>
                    </div>

                    <div
                        onDragOver={(e) => handleDragOver(e, 'group')}
                        onDragLeave={(e) => handleDragLeave(e, 'group')}
                        onDrop={(e) => handleDrop(e, 'group')}
                        className={`rounded-[2px] border px-3 py-2 text-xs transition-colors ${roles?.group ? 'bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]' : 'bg-[color:var(--white)] border-[color:var(--border-color)]'} ${dragActiveRole === 'group' ? 'border-[color:var(--accent)] bg-[color:var(--bg-tertiary)]' : ''}`}
                        aria-label="Группа: зона назначения"
                    >
                        <div className="flex items-center justify-between gap-3">
                            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{secondaryRoleLabel || 'Group'}</div>
                            {roles?.group ? (
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeRole('group');
                                    }}
                                    className="p-1 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                    aria-label="Убрать группу"
                                >
                                    <XMarkIcon className="w-4 h-4" />
                                </button>
                            ) : null}
                        </div>
                        <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{roles?.group || 'Перетащите переменную сюда'}</div>
                    </div>

                    <div
                        onDragOver={(e) => handleDragOver(e, 'covariates')}
                        onDragLeave={(e) => handleDragLeave(e, 'covariates')}
                        onDrop={(e) => handleDrop(e, 'covariates')}
                        className={`rounded-[2px] border px-3 py-2 text-xs transition-colors ${(Array.isArray(roles?.covariates) && roles.covariates.length > 0) ? 'bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]' : 'bg-[color:var(--white)] border-[color:var(--border-color)]'} ${dragActiveRole === 'covariates' ? 'border-[color:var(--accent)] bg-[color:var(--bg-tertiary)]' : ''}`}
                        aria-label="Ковариаты: зона назначения"
                    >
                        <div className="flex items-center justify-between gap-3">
                            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Ковариаты</div>
                            {Array.isArray(roles?.covariates) && roles.covariates.length > 0 ? (
                                <button
                                    type="button"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeRole('covariates');
                                    }}
                                    className="p-1 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                    aria-label="Очистить ковариаты"
                                >
                                    <XMarkIcon className="w-4 h-4" />
                                </button>
                            ) : null}
                        </div>
                        {Array.isArray(roles?.covariates) && roles.covariates.length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-1.5">
                                {roles.covariates.map((n) => (
                                    <span key={n} className="inline-flex items-center gap-1 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 py-1 text-xs text-[color:var(--text-secondary)]">
                                        <span className="max-w-[180px] truncate">{n}</span>
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                removeRole('covariates', n);
                                            }}
                                            className="text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                            aria-label={`Убрать ковариату ${n}`}
                                        >
                                            <XMarkIcon className="w-3.5 h-3.5" />
                                        </button>
                                    </span>
                                ))}
                            </div>
                        ) : (
                            <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">Перетащите переменные сюда</div>
                        )}
                    </div>
                </div>
            </div>

            {/* Selection actions */}
            {mode === 'multi' && (
                <div className="flex-shrink-0 px-3 py-2 border-b border-[color:var(--border-color)] flex items-center justify-between bg-[color:var(--white)]">
                    <span className="text-xs text-[color:var(--text-muted)]">
                        Выбрано: {selectedVariables.length}
                    </span>
                    <div className="flex gap-2">
                        <button
                            onClick={handleSelectAll}
                            className="text-xs text-[color:var(--accent)] hover:opacity-80"
                            type="button"
                        >
                            Выбрать все
                        </button>
                        <button
                            onClick={handleClearSelection}
                            className="text-xs text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                            type="button"
                        >
                            Очистить
                        </button>
                    </div>
                </div>
            )}

            {/* Variables list */}
            <div className="flex-1 min-h-0">
                {filteredColumns.length === 0 ? (
                    <div className="flex items-center justify-center h-32 text-sm text-[color:var(--text-muted)]">
                        Переменные не найдены
                    </div>
                ) : (
                    <div className="h-full" tabIndex={0} onKeyDown={handleListKeyDown}>
                        <AutoSizer>
                            {({ height: autoHeight, width }) => (
                                <List
                                    ref={listRef}
                                    height={autoHeight}
                                    width={width}
                                    itemCount={filteredColumns.length}
                                    itemSize={40}
                                    itemData={listData}
                                    overscanCount={10}
                                >
                                    {VariableRow}
                                </List>
                            )}
                        </AutoSizer>
                    </div>
                )}
            </div>

            {/* Footer status */}
            <div className="flex-shrink-0 px-3 py-2 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-xs text-[color:var(--text-muted)]">
                {filteredColumns.length} из {processedColumns.length} переменных
                {typeFilter && ` • Тип: ${TYPE_CONFIG[typeFilter].label}`}
            </div>

            {preview?.merged && (
                <div className="flex-shrink-0 border-t border-[color:var(--border-color)] bg-[color:var(--white)] p-3">
                    <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Предпросмотр</div>
                            <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{preview.merged.name}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-muted)] font-mono">
                                {typeof preview.merged.unique_count === 'number' ? `u:${preview.merged.unique_count}` : null}
                                {typeof preview.merged.missing_count === 'number' ? ` · NA:${preview.merged.missing_count}` : null}
                                {typeof preview.merged.mean === 'number' ? ` · μ:${preview.merged.mean.toFixed(3)}` : null}
                                {typeof preview.merged.min === 'number' ? ` · min:${preview.merged.min}` : null}
                                {typeof preview.merged.max === 'number' ? ` · max:${preview.merged.max}` : null}
                            </div>
                        </div>
                        <button
                            type="button"
                            onClick={() => setPreviewName(null)}
                            className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                            aria-label="закрыть"
                        >
                            <XMarkIcon className="w-4 h-4" />
                        </button>
                    </div>

                    {Array.isArray(preview.bars) && preview.bars.length > 0 ? (
                        <div className="mt-3 h-10 flex items-end gap-[2px]">
                            {preview.bars.map((b, idx) => (
                                <div
                                    key={idx}
                                    className="flex-1 bg-[color:var(--accent)] opacity-15 rounded-[2px]"
                                    style={{ height: `${Math.max(6, b.pct)}%` }}
                                />
                            ))}
                        </div>
                    ) : preview.topValues.length > 0 ? (
                        <div className="mt-3 grid grid-cols-1 gap-1">
                            {preview.topValues.map((tv, idx) => (
                                <div key={`${tv.value}_${idx}`} className="flex items-center justify-between text-xs">
                                    <div className="truncate text-[color:var(--text-secondary)]">{tv.value}</div>
                                    {typeof tv.count === 'number' ? (
                                        <div className="font-mono text-[color:var(--text-muted)]">{tv.count}</div>
                                    ) : null}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="mt-3 text-xs text-[color:var(--text-muted)]">Нет статистики для предпросмотра</div>
                    )}
                </div>
            )}
        </div>
    );
}
