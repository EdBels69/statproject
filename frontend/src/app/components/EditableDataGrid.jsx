import { useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';

ModuleRegistry.registerModules([AllCommunityModule]);

function HeaderRenderer(props) {
    const { displayName, column } = props;
    const type = column?.getColDef()?.typeTag;

    let badge = 'T';
    let badgeClass = 'text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]';
    if (type === 'numeric') {
        badge = '#';
        badgeClass = 'text-[color:var(--accent)] bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]';
    } else if (type === 'categorical') {
        badge = 'Ab';
        badgeClass = 'text-[color:var(--text-primary)] bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]';
    } else if (type === 'datetime') {
        badge = '⏱';
        badgeClass = 'text-[color:var(--text-muted)] bg-[color:var(--bg-secondary)] border-[color:var(--border-color)]';
    }

    return (
        <div className="flex items-center gap-2 min-w-0">
            <span className={`text-[10px] font-bold px-1 py-0.5 rounded-[2px] border ${badgeClass}`}>{badge}</span>
            <span className="truncate font-bold text-[color:var(--text-primary)]">{displayName}</span>
            <span className="ml-auto opacity-40 text-[10px]">▼</span>
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
                className="absolute inset-0 hidden group-hover:flex items-center justify-center bg-[color:var(--bg-secondary)] text-[color:var(--error)]"
                aria-label="Delete row"
            >
                🗑
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
                    if (!confirm('Delete row?')) return;
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
                <AgGridReact
                    ref={gridRef}
                    rowData={rows || []}
                    columnDefs={columnDefs}
                    defaultColDef={defaultColDef}
                    quickFilterText={quickFilterText || ''}
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
            </div>
        </div>
    );
}
