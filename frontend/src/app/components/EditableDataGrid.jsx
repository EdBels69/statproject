import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

let agGridRegistered = false;

function HeaderRenderer(props) {
    const { displayName, column } = props;

    return (
        <div className="flex items-center gap-2 min-w-0 group">
            <span className="truncate font-bold text-[color:var(--text-primary)]">{displayName}</span>
            <button
                type="button"
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const colName = column?.getColDef?.()?.field;
                    const onHeaderMenu = props?.context?.onHeaderMenu;
                    if (!colName || typeof onHeaderMenu !== 'function') return;
                    const r = e.currentTarget.getBoundingClientRect();
                    onHeaderMenu({ colName, x: r.left, y: r.bottom + 6 });
                }}
                className="ml-auto h-6 w-6 rounded-[2px] border border-transparent text-[color:var(--text-muted)] opacity-0 group-hover:opacity-100 hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)] transition"
                aria-label="Меню столбца"
                title="Меню столбца"
            >
                ⋯
            </button>
        </div>
    );
}

function RowIndexCellRenderer(props) {
    const { value, onDelete } = props;
    return (
        <div className="h-full w-full flex items-center justify-center relative group">
            <span className="text-xs text-[color:var(--text-muted)] font-mono group-hover:opacity-0 transition-opacity">{value}</span>
            <button
                type="button"
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onDelete?.();
                }}
                className="absolute inset-0 hidden group-hover:flex items-center justify-center bg-[color:var(--bg-secondary)] text-[color:var(--error)] text-xs font-semibold"
                aria-label="Удалить строку"
                title="Удалить строку"
            >
                Удалить
            </button>
        </div>
    );
}

export default function EditableDataGrid({
    columns,
    rows,
    columnDefsOverride,
    quickFilterText,
    loading,
    onUpdateCell,
    onDropRow,
    onHeaderMenu,
    onGridReady,
}) {
    const gridRef = useRef(null);
    const [AgGridComponent, setAgGridComponent] = useState(null);
    const [agGridLoadState, setAgGridLoadState] = useState({ status: 'loading', error: null });

    const loadAgGrid = useCallback(async () => {
        setAgGridLoadState({ status: 'loading', error: null });

        const [{ AgGridReact }, agGridCommunity] = await Promise.all([
            import('ag-grid-react'),
            import('ag-grid-community'),
            import('ag-grid-community/styles/ag-grid.css'),
            import('ag-grid-community/styles/ag-theme-quartz.css'),
        ]);

        if (!agGridRegistered) {
            const { ModuleRegistry, AllCommunityModule } = agGridCommunity;
            ModuleRegistry.registerModules([AllCommunityModule]);
            agGridRegistered = true;
        }

        setAgGridComponent(() => AgGridReact);
        setAgGridLoadState({ status: 'ready', error: null });
    }, []);

    useEffect(() => {
        let mounted = true;

        loadAgGrid().catch((err) => {
            if (!mounted) return;
            setAgGridComponent(null);
            setAgGridLoadState({
                status: 'error',
                error: err instanceof Error ? err.message : String(err || 'Неизвестная ошибка'),
            });
        });

        return () => {
            mounted = false;
        };
    }, [loadAgGrid]);

    const columnDefs = useMemo(() => {
        if (Array.isArray(columnDefsOverride) && columnDefsOverride.length > 0) {
            return columnDefsOverride;
        }

        const indexCol = {
            headerName: '#',
            colId: '__row_index__',
            width: 64,
            pinned: 'left',
            lockPinned: true,
            editable: false,
            sortable: false,
            resizable: false,
            filter: false,
            suppressMovable: true,
            cellClass: 'bg-[color:var(--bg-secondary)] border-r border-[color:var(--border-color)]',
            valueGetter: (p) => (typeof p?.node?.rowIndex === 'number' ? p.node.rowIndex + 1 : ''),
            cellRenderer: RowIndexCellRenderer,
            cellRendererParams: (p) => ({
                onDelete: () => {
                    const rowIndex = p?.node?.rowIndex;
                    if (typeof rowIndex !== 'number') return;
                    if (!confirm('Удалить строку?')) return;
                    onDropRow?.(rowIndex);
                },
            }),
        };

        const dataCols = (columns || []).map((c) => ({
            headerName: c?.name,
            field: c?.name,
            typeTag: c?.type,
            editable: true,
            sortable: false,
            filter: false,
            resizable: true,
            suppressMovable: true,
            headerComponent: HeaderRenderer,
            cellClass: 'font-mono text-xs text-[color:var(--text-primary)] border-r border-[color:var(--border-color)]',
            valueFormatter: (p) => {
                const v = p?.value;
                if (v === null || v === undefined || v === '') return 'null';
                return String(v);
            },
        }));

        return [indexCol, ...dataCols];
    }, [columns, columnDefsOverride, onDropRow]);

    const defaultColDef = useMemo(
        () => ({
            minWidth: 150,
            wrapHeaderText: false,
            autoHeaderHeight: false,
        }),
        []
    );

    const onCellValueChanged = useCallback(
        (e) => {
            const colName = e?.colDef?.field;
            const rowIndex = e?.node?.rowIndex;
            if (!colName || typeof rowIndex !== 'number') return;

            const next = e?.newValue;
            const prev = e?.oldValue;
            if (String(next ?? '') === String(prev ?? '')) return;

            onUpdateCell?.({ rowIndex, colName, value: next });
        },
        [onUpdateCell]
    );

    const onColumnHeaderClicked = useCallback(
        (e) => {
            const colName = e?.column?.getColDef?.()?.field;
            const rawEvent = e?.event;
            if (!colName || !rawEvent) return;
            rawEvent.stopPropagation?.();
            onHeaderMenu?.({
                colName,
                x: (rawEvent.clientX ?? 0) + 0,
                y: (rawEvent.clientY ?? 0) + 10,
            });
        },
        [onHeaderMenu]
    );

    const gridStyle = useMemo(
        () => ({
            height: '100%',
            width: '100%',
            '--ag-font-family': 'ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif',
            '--ag-font-size': '12px',
            '--ag-row-height': '34px',
            '--ag-header-height': '42px',
            '--ag-borders': 'solid 1px',
            '--ag-border-color': 'var(--border-color)',
            '--ag-header-background-color': 'var(--bg-secondary)',
            '--ag-odd-row-background-color': 'var(--white)',
            '--ag-row-hover-color': 'color-mix(in oklab, var(--accent) 7%, var(--white))',
            '--ag-selected-row-background-color': 'color-mix(in oklab, var(--accent) 12%, var(--white))',
            '--ag-foreground-color': 'var(--text-primary)',
            '--ag-secondary-foreground-color': 'var(--text-secondary)',
            '--ag-header-foreground-color': 'var(--text-secondary)',
            '--ag-border-radius': '2px',
            '--ag-cell-horizontal-padding': '16px',
        }),
        []
    );

    return (
        <div className="h-full w-full">
            <div className="h-full w-full ag-theme-quartz" style={gridStyle}>
                {AgGridComponent ? (
                    <AgGridComponent
                        ref={gridRef}
                        rowData={rows || []}
                        columnDefs={columnDefs}
                        defaultColDef={defaultColDef}
                        quickFilterText={quickFilterText || ''}
                        context={{ onHeaderMenu }}
                        singleClickEdit={false}
                        stopEditingWhenCellsLoseFocus
                        suppressRowClickSelection
                        rowSelection={{ mode: 'singleRow', enableClickSelection: false }}
                        onCellValueChanged={onCellValueChanged}
                        onColumnHeaderClicked={onColumnHeaderClicked}
                        onGridReady={onGridReady}
                        loading={Boolean(loading)}
                        animateRows
                    />
                ) : agGridLoadState.status === 'error' ? (
                    <div className="h-full w-full flex items-center justify-center">
                        <div className="w-full max-w-[520px] px-6 py-5 border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] rounded-[2px]">
                            <div className="text-[13px] text-[color:var(--text-primary)] font-semibold">
                                Таблица не загрузилась
                            </div>
                            <div className="mt-1 text-xs text-[color:var(--text-muted)] leading-relaxed">
                                Похоже, не удалось загрузить модуль ag-grid (часто это сеть/кэш/блокировка ресурсов).
                            </div>
                            <div className="mt-3 flex items-center gap-2">
                                <button
                                    type="button"
                                    onClick={() => {
                                        loadAgGrid().catch((err) => {
                                            setAgGridComponent(null);
                                            setAgGridLoadState({
                                                status: 'error',
                                                error: err instanceof Error ? err.message : String(err || 'Неизвестная ошибка'),
                                            });
                                        });
                                    }}
                                    className="h-9 px-3 rounded-[2px] bg-[color:var(--text-primary)] text-[color:var(--white)] text-xs font-semibold"
                                >
                                    Повторить
                                </button>
                                <button
                                    type="button"
                                    onClick={() => window.location.reload()}
                                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] text-xs font-semibold"
                                >
                                    Обновить страницу
                                </button>
                            </div>
                            {agGridLoadState.error ? (
                                <div className="mt-3 text-[11px] font-mono text-[color:var(--text-muted)] break-words">
                                    {agGridLoadState.error}
                                </div>
                            ) : null}
                        </div>
                    </div>
                ) : (
                    <div className="h-full w-full flex items-center justify-center text-sm text-zinc-500">
                        Загрузка таблицы…
                    </div>
                )}
            </div>
        </div>
    );
}
