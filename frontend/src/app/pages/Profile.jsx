import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { reparseDataset, modifyDataset, getDataset, scanDataset, getSheets } from '../../lib/api';

export default function Profile() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    // Data State
    const [profile, setProfile] = useState(location.state?.profile || null);
    const [filename] = useState(location.state?.filename || "Unknown file");
    const [sheets, setSheets] = useState([]);
    const [selectedSheet, setSelectedSheet] = useState(null);
    const [editingCell, setEditingCell] = useState(null);

    // Pagination Removed (Show All Mode)
    // We set a high limit effectively disabling pagination for typical datasets
    const LIMIT = 10000;

    // UI State
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [activeMenu, setActiveMenu] = useState(null);

    // Audit State
    const [auditReport, setAuditReport] = useState(null);
    const [auditLoading, setAuditLoading] = useState(false);
    const [fixingIssue, setFixingIssue] = useState(null);

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
            const data = await getDataset(id, 1, LIMIT);
            setProfile(data);
        } catch (e) {
            console.error(e);
            setError("Не удалось загрузить данные. Возможно, файл удален или поврежден.");
        } finally {
            setLoading(false);
        }
    }, [id, LIMIT]);

    // Initial Load
    useEffect(() => {
        loadProfile();
    }, [loadProfile]);

    // Sheets check
    useEffect(() => {
        checkSheets();
    }, [checkSheets]);

    const handleSheetChange = async (sheetName) => {
        if (sheetName === selectedSheet) return;
        setLoading(true);
        setError(null);
        try {
            const newProfile = await reparseDataset(id, 0, sheetName);
            setProfile(newProfile);
            setSelectedSheet(sheetName);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleAction = async (action) => {
        setLoading(true);
        setError(null);
        setActiveMenu(null);
        try {
            await modifyDataset(id, [action]);
            await loadProfile();
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleScan = async () => {
        setAuditLoading(true);
        try {
            const report = await scanDataset(id);
            setAuditReport(report);
        } catch (e) {
            alert("Ошибка аудита: " + e.message);
        } finally {
            setAuditLoading(false);
        }
    }

    const handleApplyFix = async (issue) => {
        if (!confirm(`Применить исправление: ${issue.suggestion}?`)) return;

        setFixingIssue(issue);
        // Mock fix for now
        setTimeout(() => {
            alert("Fix applied (Backend logic pending)");
            setFixingIssue(null);
        }, 1000);
    };

    const handleNext = () => {
        navigate(`/analyze/${id}`, {
            state: { columns: profile.columns }
        });
    };

    if (!profile) {
        return (
            <div className="flex items-center justify-center h-screen bg-slate-50">
                <div className="text-center">
                    <div className="text-4xl mb-4 animate-spin">🌀</div>
                    <p className="text-slate-500 font-medium">Загрузка данных...</p>
                    {error && <p className="text-red-500 mt-2">{error}</p>}
                </div>
            </div>
        );
    }

    function TypeIcon({ type }) {
        switch (type) {
            case 'numeric': return <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-1 py-0.5 rounded border border-blue-100">#</span>;
            case 'categorical': return <span className="text-[10px] font-bold text-orange-600 bg-orange-50 px-1 py-0.5 rounded border border-orange-100">Ab</span>;
            case 'datetime': return <span className="text-[10px] font-bold text-purple-600 bg-purple-50 px-1 py-0.5 rounded border border-purple-100">📅</span>;
            default: return <span className="text-[10px] font-bold text-slate-600 bg-slate-50 px-1 py-0.5 rounded border border-slate-100">T</span>;
        }
    }

    const ColumnMenu = () => {
        if (!activeMenu) return null;
        return (
            <div
                ref={menuRef}
                className="absolute bg-white rounded-lg shadow-xl ring-1 ring-slate-900/5 w-48 z-50 text-sm overflow-hidden animate-in fade-in zoom-in-95 duration-100"
                style={{ top: activeMenu.y, left: activeMenu.x }}
            >
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-100 font-medium text-slate-700 truncate">
                    {activeMenu.colName}
                </div>
                <div className="p-1 space-y-0.5">
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'numeric' })} className="w-full text-left px-2 py-1.5 hover:bg-blue-50 text-slate-700 rounded flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-blue-600">#</span> Number
                    </button>
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'text' })} className="w-full text-left px-2 py-1.5 hover:bg-slate-50 text-slate-700 rounded flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-slate-500">T</span> Text
                    </button>
                    <button onClick={() => handleAction({ type: 'change_type', column: activeMenu.colName, new_type: 'categorical' })} className="w-full text-left px-2 py-1.5 hover:bg-orange-50 text-slate-700 rounded flex items-center gap-2 transition-colors">
                        <span className="w-4 text-center text-xs font-bold text-orange-600">Ab</span> Category
                    </button>
                </div>
                <div className="border-t border-slate-100 p-1">
                    <button
                        onClick={() => {
                            const newName = prompt("Rename column:", activeMenu.colName);
                            if (newName && newName !== activeMenu.colName) handleAction({ type: 'rename_col', column: activeMenu.colName, new_name: newName });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-slate-50 text-slate-700 rounded transition-colors"
                    >
                        Rename
                    </button>
                    <button
                        onClick={() => {
                            if (confirm(`Delete column "${activeMenu.colName}"?`)) handleAction({ type: 'drop_col', column: activeMenu.colName });
                        }}
                        className="w-full text-left px-2 py-1.5 hover:bg-red-50 text-red-600 rounded transition-colors"
                    >
                        Delete
                    </button>
                </div>
            </div>
        );
    };

    return (
        <div className="min-h-screen bg-slate-50/50 text-slate-900 font-sans selection:bg-indigo-100 selection:text-indigo-900" onClick={() => setActiveMenu(null)}>

            {/* 1. Header */}
            <header className="bg-white border-b border-slate-200 sticky top-0 z-30 h-16 px-6 flex items-center justify-between shadow-sm/30 backdrop-blur-md bg-white/80">
                <div className="flex items-center gap-4">
                    <div className="w-8 h-8 bg-gradient-to-br from-indigo-600 to-violet-600 rounded-lg flex items-center justify-center text-white font-bold shadow-lg shadow-indigo-200">
                        S
                    </div>
                    <div>
                        <h1 className="font-bold text-slate-800 leading-tight text-sm">{filename}</h1>
                        <div className="flex items-center gap-2 text-[10px] text-slate-500 uppercase tracking-wider font-medium">
                            <span>{profile.row_count} rows</span>
                            <span className="text-slate-300">•</span>
                            <span>{profile.col_count} cols</span>
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {sheets.length > 0 && (
                        <select
                            className="bg-white border border-slate-200 text-slate-600 text-sm rounded-md px-3 py-1.5 focus:ring-2 focus:ring-indigo-500 outline-none w-40 shadow-sm"
                            onChange={(e) => handleSheetChange(e.target.value)}
                            value={selectedSheet || sheets[0] || ""}
                        >
                            {sheets.map(sheet => (
                                <option key={sheet} value={sheet}>{sheet}</option>
                            ))}
                        </select>
                    )}
                    <button
                        onClick={handleNext}
                        className="bg-slate-900 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-slate-800 transition-all shadow-lg shadow-slate-200 hover:-translate-y-0.5"
                    >
                        Next Step →
                    </button>
                </div>
            </header>

            <main className="max-w-[1600px] mx-auto p-6 space-y-8">

                {/* 2. Audit Dashboard (Top Center) */}
                <section className="w-full flex flex-col items-center">
                    {!auditReport && !auditLoading && (
                        <div className="w-full max-w-2xl bg-white rounded-xl border border-dashed border-slate-300 p-8 flex flex-col items-center justify-center text-center hover:border-indigo-400 hover:bg-indigo-50/10 transition-all cursor-pointer group shadow-sm hover:shadow-md" onClick={handleScan}>
                            <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-sm">
                                <span className="text-2xl">🧠</span>
                            </div>
                            <h3 className="text-xl font-bold text-slate-800 mb-2">AI Dataset Audit</h3>
                            <p className="text-slate-500 text-sm max-w-md mx-auto mb-6 leading-relaxed">
                                Let our AI analyze your data for quality issues, outliers, and schema suggestions before you proceed.
                            </p>
                            <button className="px-6 py-2.5 bg-indigo-600 text-white font-semibold rounded-lg shadow-md shadow-indigo-200 hover:bg-indigo-700 transition-all pointer-events-none">
                                Run Smart Scan
                            </button>
                        </div>
                    )}

                    {auditLoading && (
                        <div className="w-full max-w-2xl bg-white rounded-xl border border-slate-200 p-10 flex flex-col items-center justify-center shadow-sm">
                            <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4"></div>
                            <p className="text-slate-700 font-medium animate-pulse">Running Deep Scan...</p>
                            <p className="text-xs text-slate-400 mt-2">Checking types, missing values, and anomalies</p>
                        </div>
                    )}

                    {auditReport && (
                        <div className="w-full bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden animate-in slide-in-from-top-4 fade-in duration-500">
                            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                                    <span className="flex h-3 w-3 relative">
                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                        <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                    </span>
                                    Audit Report
                                </h3>
                                <button
                                    onClick={() => setAuditReport(null)}
                                    className="text-xs text-slate-400 hover:text-slate-600 underline"
                                >
                                    Close
                                </button>
                            </div>

                            {auditReport.issues.length === 0 ? (
                                <div className="p-10 text-center">
                                    <div className="text-4xl mb-4">✨</div>
                                    <h4 className="font-bold text-slate-800">Perfect Score!</h4>
                                    <p className="text-slate-500 text-sm mt-2">No data quality issues regarding missing values, types, or outliers were detected.</p>
                                </div>
                            ) : (
                                <div className="p-6 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 bg-slate-50/30">
                                    {auditReport.issues.map((issue, idx) => (
                                        <div key={idx} className="relative group bg-white border border-slate-200 rounded-lg p-5 shadow-sm hover:shadow-md hover:border-indigo-300 transition-all">
                                            {/* Severity Indicator */}
                                            <div className={`absolute top-4 right-4 w-2 h-2 rounded-full ${issue.severity === 'high' ? 'bg-red-500 ring-4 ring-red-100' :
                                                    issue.severity === 'medium' ? 'bg-orange-400 ring-4 ring-orange-100' : 'bg-blue-400 ring-4 ring-blue-100'
                                                }`}></div>

                                            <div className="mb-3">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className="text-[10px] font-bold uppercase tracking-widest text-slate-500 border border-slate-200 px-2 py-0.5 rounded-full bg-slate-50">
                                                        {issue.issue_type}
                                                    </span>
                                                    {issue.column && (
                                                        <span className="text-xs font-mono text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                                                            {issue.column}
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="text-sm font-semibold text-slate-800 leading-snug">
                                                    {issue.description}
                                                </p>
                                            </div>

                                            <div className="text-xs text-slate-500 mb-4 bg-slate-50 p-2 rounded border border-slate-100 leading-relaxed">
                                                💡 {issue.suggestion}
                                            </div>

                                            <button
                                                onClick={() => handleApplyFix(issue)}
                                                disabled={fixingIssue === issue}
                                                className="w-full text-center py-2 rounded-md border border-indigo-200 text-indigo-700 text-xs font-bold hover:bg-indigo-50 hover:border-indigo-300 transition-colors uppercase tracking-wide disabled:opacity-50 flex items-center justify-center gap-2"
                                            >
                                                {fixingIssue === issue ? (
                                                    <>
                                                        <span className="animate-spin">⏳</span> Applying...
                                                    </>
                                                ) : 'Apply Fix'}
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </section>

                {/* 3. Main Workspace: Sidebar & Grid */}
                <div className="flex flex-col lg:flex-row gap-6 items-start">

                    {/* Left: Columns Sidebar */}
                    <aside className="w-full lg:w-64 bg-white rounded-xl border border-slate-200 flex flex-col overflow-hidden shadow-sm sticky top-24">
                        <div className="p-3 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
                            <h3 className="font-bold text-slate-700 text-xs uppercase tracking-wide">Schema</h3>
                            <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 rounded-full">{profile.columns.length}</span>
                        </div>
                        <div className="max-h-[500px] overflow-y-auto custom-scrollbar p-2 space-y-1">
                            {profile.columns.map(col => (
                                <div key={col.name} className="flex items-center justify-between text-xs p-2 rounded-lg hover:bg-slate-50 transition-colors group cursor-default border border-transparent hover:border-slate-100">
                                    <div className="flex items-center gap-2 overflow-hidden">
                                        <TypeIcon type={col.type} />
                                        <span className="font-medium text-slate-700 truncate max-w-[120px]" title={col.name}>{col.name}</span>
                                    </div>
                                    <div className="text-[10px] font-mono">
                                        {col.missing_count > 0 ? (
                                            <span className="text-red-500 font-bold">{((col.missing_count / profile.row_count) * 100).toFixed(0)}%</span>
                                        ) : (
                                            <span className="text-slate-300">✓</span>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </aside>

                    {/* Right: Data Grid */}
                    <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col overflow-hidden relative min-h-[500px]">
                        {loading && (
                            <div className="absolute inset-0 bg-white/60 z-20 backdrop-blur-[1px] flex items-center justify-center">
                                <div className="bg-white p-4 rounded-lg shadow-xl border border-slate-100 flex items-center gap-3">
                                    <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                                    <span className="text-sm font-medium text-slate-700">Checking data...</span>
                                </div>
                            </div>
                        )}

                        <div className="flex-1 overflow-auto custom-scrollbar max-h-[800px]">
                            <ColumnMenu />
                            <table className="w-full text-sm text-left text-slate-600 border-separate border-spacing-0">
                                <thead className="text-xs text-slate-500 uppercase bg-slate-50 sticky top-0 z-10 shadow-sm">
                                    <tr>
                                        <th className="px-4 py-3 border-b border-r border-slate-200 font-medium w-14 text-center bg-slate-50">#</th>
                                        {profile.columns.map(col => (
                                            <th
                                                key={col.name}
                                                className="px-4 py-3 border-b border-r border-slate-200 font-bold text-slate-700 min-w-[150px] cursor-pointer hover:bg-indigo-50/50 transition-colors select-none group"
                                                onClick={(e) => {
                                                    const rect = e.currentTarget.getBoundingClientRect();
                                                    setActiveMenu({ colName: col.name, x: rect.left, y: rect.bottom + 5 });
                                                }}
                                            >
                                                <div className="flex items-center gap-2">
                                                    <TypeIcon type={col.type} />
                                                    <span>{col.name}</span>
                                                    <span className="opacity-0 group-hover:opacity-100 text-[9px] text-slate-400">▼</span>
                                                </div>
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                    {profile.head && profile.head.map((row, rowIdxPage) => {
                                        // Since we effectively have page 1 always, absIndex is just rowIdxPage
                                        const absIndex = rowIdxPage;
                                        return (
                                            <tr key={rowIdxPage} className="hover:bg-indigo-50/20 transition-colors group">
                                                <td className="px-2 py-2 text-center text-xs text-slate-400 border-r border-slate-100 font-mono relative bg-slate-50/50">
                                                    <span className="group-hover:hidden">{absIndex + 1}</span>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            if (confirm("Delete row?")) handleAction({ type: 'drop_row', row_index: absIndex });
                                                        }}
                                                        className="hidden group-hover:flex absolute inset-0 items-center justify-center bg-red-50 text-red-500 hover:text-red-700"
                                                    >
                                                        🗑
                                                    </button>
                                                </td>
                                                {profile.columns.map(col => {
                                                    const val = row[col.name];
                                                    const isNull = val === null || val === undefined || val === "";
                                                    const isEditing = editingCell?.rowIdx === rowIdxPage && editingCell?.colName === col.name;

                                                    return (
                                                        <td
                                                            key={col.name}
                                                            className={`px-4 py-2 border-r border-slate-100 whitespace-nowrap overflow-hidden text-ellipsis max-w-[250px] font-mono text-xs ${isEditing ? 'p-0 ring-2 ring-indigo-500 z-10' : ''}`}
                                                            onDoubleClick={() => setEditingCell({ rowIdx: rowIdxPage, colName: col.name, value: val ?? "" })}
                                                        >
                                                            {isEditing ? (
                                                                <input
                                                                    autoFocus
                                                                    className="w-full h-full px-4 py-2 bg-white outline-none text-slate-900"
                                                                    value={editingCell.value}
                                                                    onChange={(e) => setEditingCell(prev => ({ ...prev, value: e.target.value }))}
                                                                    onBlur={() => {
                                                                        if (editingCell.value !== String(val ?? "")) {
                                                                            handleAction({
                                                                                type: 'update_cell',
                                                                                row_index: absIndex,
                                                                                column: col.name,
                                                                                value: editingCell.value
                                                                            });
                                                                        }
                                                                        setEditingCell(null);
                                                                    }}
                                                                    onKeyDown={(e) => {
                                                                        if (e.key === 'Enter') e.target.blur();
                                                                        if (e.key === 'Escape') setEditingCell(null);
                                                                    }}
                                                                />
                                                            ) : (
                                                                isNull ? <span className="text-slate-300 italic opacity-50">null</span> : <span className="text-slate-700">{String(val)}</span>
                                                            )}
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
