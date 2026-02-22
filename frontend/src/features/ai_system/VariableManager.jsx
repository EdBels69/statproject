import React, { useState, useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry } from 'ag-grid-community';

// Register modules
ModuleRegistry.registerModules([AllCommunityModule]);

export default function VariableManager({ manifest, onConfirm, onCancel }) {
    // manifest: [{ name, inferred_type, missing_pct, unique }]

    // Ag Grid Rows
    const [rowData, setRowData] = useState(
        manifest.map(m => ({
            ...m,
            selected: m.inferred_type !== 'id', // Default select non-ids
            type: m.inferred_type
        }))
    );

    const columnDefs = useMemo(() => [
        {
            field: "selected",
            headerName: "Вкл.",
            width: 80,
            checkboxSelection: true,
            headerCheckboxSelection: true,
            editable: true
        },
        { field: "name", headerName: "Переменная", flex: 2, filter: true },
        {
            field: "type",
            headerName: "Тип",
            width: 140,
            editable: true,
            cellEditor: 'agSelectCellEditor',
            cellEditorParams: {
                values: ['numeric', 'categorical', 'text', 'id']
            },
            cellClassRules: {
                'text-indigo-600 font-bold': params => params.value === 'numeric',
                'text-purple-600 font-bold': params => params.value === 'categorical',
            }
        },
        { field: "unique", headerName: "Уник.", width: 100, type: 'numericColumn' },
        {
            field: "missing_pct",
            headerName: "Пропуски %",
            width: 120,
            cellStyle: params => params.value > 20 ? { color: 'red', fontWeight: 'bold' } : null
        },
        { field: "example", headerName: "Пример", flex: 1, textWrap: ' nowrap' }
    ], []);

    const handleConfirm = () => {
        // Filter selected rows
        const selected = rowData.filter(r => r.selected);
        onConfirm(selected);
    };

    return (
        <div className="bg-white rounded-xl border shadow-sm p-6 animate-fadeIn h-[calc(100vh-200px)] flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">Менеджер переменных</h2>
                    <p className="text-gray-500">Отметьте галочками переменные для анализа и проверьте их типы.</p>
                </div>
                <div className="text-sm text-gray-600 bg-gray-100 px-3 py-1 rounded">
                    Выбрано: <b>{rowData.filter(r => r.selected).length}</b> из {rowData.length}
                </div>
            </div>

            <div className="flex-1 ag-theme-quartz" style={{ width: '100%' }}>
                <AgGridReact
                    rowData={rowData}
                    columnDefs={columnDefs}
                    defaultColDef={{ resizable: true, sortable: true }}
                    rowSelection={{ mode: "multiRow", checkboxes: true }}
                    getRowId={(params) => params.data.name}
                    onSelectionChanged={(event) => {
                        // Get selected rows from AG Grid API (preserves scroll)
                        const selectedNodes = event.api.getSelectedNodes();
                        const selectedNames = new Set(selectedNodes.map(n => n.data.name));
                        setRowData(prev => prev.map(r => ({
                            ...r,
                            selected: selectedNames.has(r.name)
                        })));
                    }}
                    onCellValueChanged={(event) => {
                        // Handle type dropdown change only
                        if (event.colDef.field === 'type') {
                            setRowData(prev => prev.map(r =>
                                r.name === event.data.name ? { ...r, type: event.newValue } : r
                            ));
                        }
                    }}
                    onGridReady={(params) => {
                        // Pre-select rows that were marked as selected in initial state
                        params.api.forEachNode(node => {
                            if (node.data.selected) {
                                node.setSelected(true, false, 'api');
                            }
                        });
                    }}
                />
            </div>

            <div className="flex justify-end gap-3 pt-6 mt-2 border-t">
                <button onClick={onCancel} className="px-6 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">
                    Отмена
                </button>
                <button onClick={handleConfirm} className="bg-indigo-600 text-white px-8 py-2 rounded-lg font-bold hover:bg-indigo-700 shadow-lg">
                    Далее: Согласование протокола →
                </button>
            </div>
        </div>
    );
}
