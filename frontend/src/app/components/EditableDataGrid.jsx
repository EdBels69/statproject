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
    let badgeClass = 'text-slate-600 bg-slate-50 border-slate-100';
    if (type === 'numeric') {
        badge = '#';
        badgeClass = 'text-blue-600 bg-blue-50 border-blue-100';
    } else if (type === 'categorical') {
        badge = 'Ab';
        badgeClass = 'text-orange-600 bg-orange-50 border-orange-100';
    } else if (type === 'datetime') {
        badge = '⏱';
        badgeClass = 'text-purple-600 bg-purple-50 border-purple-100';
    }

    return (
        <div className="flex items-center gap-2 min-w-0">
            <span className={`text-[10px] font-bold px-1 py-0.5 rounded border ${badgeClass}`}>{badge}</span>
            <span className="truncate font-bold text-slate-700">{displayName}</span>
            <span className="ml-auto opacity-40 text-[10px]">▼</span>
        </div>
    );
}

function RowIndexCellRenderer(props) {
    const { value, onDelete } = props;
    return (
        <div className="h-full w-full flex items-center justify-center relative group">
            <span className="text-xs text-slate-400 font-mono group-hover:opacity-0 transition-opacity">{value}</span>
            <button
                type="button"
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onDelete?.();
                }}
                className="absolute inset-0 hidden group-hover:flex items-center justify-center bg-red-50 text-red-600 hover:text-red-700"
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
    loading,
    onUpdateCell,
    onDropRow,
    onHeaderMenu,
}) {
    const gridRef = useRef(null);

    const columnDefs = useMemo(() => {
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
            cellClass: 'bg-slate-50/50 border-r border-slate-100',
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
            cellClass: 'font-mono text-xs text-slate-700 border-r border-slate-100',
            valueFormatter: (p) => {
                const v = p?.value;
                if (v === null || v === undefined || v === '') return 'null';
                return String(v);
            },
        }));

        return [indexCol, ...dataCols];
    }, [columns, onDropRow]);

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
            '--ag-border-color': 'rgb(226 232 240)',
            '--ag-header-background-color': 'rgb(248 250 252)',
            '--ag-odd-row-background-color': 'rgb(255 255 255)',
            '--ag-row-hover-color': 'rgba(99, 102, 241, 0.06)',
            '--ag-selected-row-background-color': 'rgba(99, 102, 241, 0.10)',
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
                    singleClickEdit={false}
                    stopEditingWhenCellsLoseFocus
                    suppressRowClickSelection
                    rowSelection={{ mode: 'singleRow', enableClickSelection: false }}
                    onCellValueChanged={onCellValueChanged}
                    onColumnHeaderClicked={onColumnHeaderClicked}
                    loading={Boolean(loading)}
                    animateRows
                />
            </div>
        </div>
    );
}

