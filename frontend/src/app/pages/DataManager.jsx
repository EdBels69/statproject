import React, { useState, useEffect } from 'react';
import { getDatasets, getDataset, previewData, createSubset } from '../../lib/api';

export default function DataManager() {
    const [datasets, setDatasets] = useState([]);
    const [selectedDatasetId, setSelectedDatasetId] = useState(null);
    const [columns, setColumns] = useState([]);

    // Table Data
    const [rows, setRows] = useState([]);
    const [totalRows, setTotalRows] = useState(0);
    const [page, setPage] = useState(0);
    const LIMIT = 50;

    // Filter State: [{ column: 'Age', operator: 'gt', value: 30 }]
    const [filters, setFilters] = useState([]);
    const [activeFilterCol, setActiveFilterCol] = useState(null); // Which column header popup is open

    // Subset State
    const [subsetName, setSubsetName] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [successMsg, setSuccessMsg] = useState("");

    useEffect(() => {
        loadDatasets();
    }, []);

    const loadDatasets = async () => {
        try {
            const ds = await getDatasets();
            setDatasets(ds);
            if (ds.length > 0 && !selectedDatasetId) {
                handleSelectDataset(ds[0].id);
            }
        } catch (err) {
            console.error(err);
        }
    };

    const handleSelectDataset = async (id) => {
        setSelectedDatasetId(id);
        setFilters([]);
        setPage(0);
        setSuccessMsg("");

        // Load metadata (columns)
        try {
            const meta = await getDataset(id);
            setColumns(meta.columns || []);
            // Load initial data
            fetchData(id, 0, []);
        } catch (e) { console.error(e); }
    };

    const fetchData = async (id, pageNum, currentFilters) => {
        try {
            const res = await previewData(id, LIMIT, pageNum * LIMIT, currentFilters);
            setRows(res.rows);
            setTotalRows(res.total_rows);
        } catch (e) {
            console.error(e);
        }
    };

    const applyFilter = (filter) => {
        // Replace existing filter for this column or add new
        const existingIdx = filters.findIndex(f => f.column === filter.column);
        let newFilters = [...filters];

        if (filter.value === "" || filter.value === null) {
            // Remove filter
            if (existingIdx >= 0) newFilters.splice(existingIdx, 1);
        } else {
            if (existingIdx >= 0) newFilters[existingIdx] = filter;
            else newFilters.push(filter);
        }

        setFilters(newFilters);
        setPage(0);
        setActiveFilterCol(null);
        fetchData(selectedDatasetId, 0, newFilters);
    };

    const removeFilter = (colName) => {
        const newFilters = filters.filter(f => f.column !== colName);
        setFilters(newFilters);
        setPage(0);
        fetchData(selectedDatasetId, 0, newFilters);
    };

    const handleSaveSubset = async () => {
        if (!subsetName) return alert("Enter a name");
        setIsSubmitting(true);
        try {
            await createSubset(selectedDatasetId, subsetName, filters);
            setSuccessMsg(`Subset '${subsetName}' created! Check the Datasets list.`);
            setSubsetName("");
            loadDatasets(); // Refresh list
        } catch (e) {
            alert("Failed to create subset");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="flex h-screen bg-gray-50">
            {/* Sidebar */}
            <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
                <div className="p-4 border-b">
                    <h2 className="font-bold text-gray-700">Datasets</h2>
                </div>
                <div className="overflow-y-auto flex-1">
                    {datasets.map(ds => (
                        <button
                            key={ds.id}
                            onClick={() => handleSelectDataset(ds.id)}
                            className={`w-full text-left px-4 py-3 text-sm ${selectedDatasetId === ds.id ? 'bg-blue-50 text-blue-600 border-l-4 border-blue-500' : 'text-gray-600 hover:bg-gray-50'}`}
                        >
                            {ds.filename}
                        </button>
                    ))}
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 flex flex-col overflow-hidden">
                {/* Toolbar */}
                <div className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm z-10">
                    <div>
                        <h1 className="text-xl font-bold text-gray-800">
                            Data View <span className="text-sm font-normal text-gray-500">({totalRows} rows)</span>
                        </h1>
                        <div className="text-sm text-gray-500 mt-1">
                            {filters.length > 0 ? (
                                <div className="flex gap-2 flex-wrap">
                                    {filters.map((f, i) => (
                                        <span key={i} className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs flex items-center gap-1">
                                            {f.column} {f.operator} {f.value}
                                            <button onClick={() => removeFilter(f.column)} className="hover:text-blue-900">×</button>
                                        </span>
                                    ))}
                                    <span className="text-xs text-gray-400 self-center">Filtered View</span>
                                </div>
                            ) : "No filters applied (Showing all data)"}
                        </div>
                    </div>

                    <div className="flex gap-3 items-center">
                        {filters.length > 0 && (
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    placeholder="Subset Name (e.g. Males > 50)"
                                    className="border rounded px-3 py-2 text-sm w-48"
                                    value={subsetName}
                                    onChange={e => setSubsetName(e.target.value)}
                                />
                                <button
                                    onClick={handleSaveSubset}
                                    disabled={isSubmitting}
                                    className="bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700 disabled:opacity-50"
                                >
                                    {isSubmitting ? "Saving..." : "Save Subset"}
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {successMsg && (
                    <div className="bg-green-50 text-green-800 px-6 py-2 text-sm border-b border-green-100">
                        {successMsg}
                    </div>
                )}

                {/* Grid */}
                <div className="flex-1 overflow-auto p-6">
                    <div className="bg-white border rounded shadow-sm overflow-hidden inline-block min-w-full">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    {columns.map(col => (
                                        <th key={col.name} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider sticky top-0 bg-gray-50 border-b">
                                            <div className="flex justify-between items-center gap-2">
                                                <span>{col.name}</span>
                                                <button
                                                    onClick={() => setActiveFilterCol(activeFilterCol === col.name ? null : col.name)}
                                                    className={`p-1 rounded hover:bg-gray-200 ${filters.find(f => f.column === col.name) ? 'text-blue-600' : 'text-gray-400'}`}
                                                >
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" /></svg>
                                                </button>

                                                {/* Filter Popup */}
                                                {activeFilterCol === col.name && (
                                                    <FilterPopup
                                                        col={col}
                                                        currentFilter={filters.find(f => f.column === col.name)}
                                                        onApply={applyFilter}
                                                        onClose={() => setActiveFilterCol(null)}
                                                    />
                                                )}
                                            </div>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {rows.map((row, idx) => (
                                    <tr key={idx} className="hover:bg-gray-50">
                                        {columns.map(col => (
                                            <td key={col.name} className="px-3 py-2 text-sm text-gray-700 whitespace-nowrap">
                                                {row[col.name]?.toString() || <span className="text-gray-300">null</span>}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>

                        {rows.length === 0 && (
                            <div className="p-8 text-center text-gray-500">No rows found.</div>
                        )}
                    </div>
                </div>

                {/* Pagination */}
                <div className="bg-white border-t p-3 flex justify-between items-center">
                    <span className="text-sm text-gray-600">
                        Page {page + 1} of {Math.ceil(totalRows / LIMIT)}
                    </span>
                    <div className="flex gap-2">
                        <button
                            disabled={page === 0}
                            onClick={() => { setPage(p => p - 1); fetchData(selectedDatasetId, page - 1, filters); }}
                            className="px-3 py-1 border rounded text-sm hover:bg-gray-50 disabled:opacity-50"
                        >
                            Prev
                        </button>
                        <button
                            disabled={(page + 1) * LIMIT >= totalRows}
                            onClick={() => { setPage(p => p + 1); fetchData(selectedDatasetId, page + 1, filters); }}
                            className="px-3 py-1 border rounded text-sm hover:bg-gray-50 disabled:opacity-50"
                        >
                            Next
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

function FilterPopup({ col, currentFilter, onApply, onClose }) {
    const [op, setOp] = useState(currentFilter?.operator || (col.type === "numeric" ? "gt" : "eq"));
    const [val, setVal] = useState(currentFilter?.value || "");

    return (
        <div className="absolute mt-8 bg-white border shadow-lg rounded p-3 z-50 w-48 text-left">
            <div className="text-xs font-bold text-gray-500 mb-2">Filter {col.name}</div>
            <select
                className="w-full border rounded text-sm mb-2 p-1"
                value={op}
                onChange={e => setOp(e.target.value)}
            >
                {col.type === "numeric" ? (
                    <>
                        <option value="eq">=</option>
                        <option value="gt">&gt;</option>
                        <option value="lt">&lt;</option>
                        <option value="gte">&ge;</option>
                        <option value="lte">&le;</option>
                    </>
                ) : (
                    <>
                        <option value="eq">Equals</option>
                        <option value="contains">Contains</option>
                        <option value="neq">Not Equal</option>
                    </>
                )}
            </select>
            <input
                type="text"
                className="w-full border rounded text-sm mb-2 p-1"
                placeholder="Value..."
                value={val}
                onChange={e => setVal(e.target.value)}
            />
            <div className="flex justify-end gap-2">
                <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-700">Cancel</button>
                <button
                    onClick={() => onApply({ column: col.name, operator: op, value: val })}
                    className="bg-blue-600 text-white px-2 py-1 rounded text-xs hover:bg-blue-700"
                >
                    Apply
                </button>
            </div>
        </div>
    );
}
