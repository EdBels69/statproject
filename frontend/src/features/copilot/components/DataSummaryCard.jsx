import React from 'react';

// New Component: Data Summary Card
const DataSummaryCard = ({ report }) => {
    if (!report) return null;

    const profile = report.profile || {};
    // API may return columns at root level OR nested in scan_report
    const issues = report.scan_report?.issues || report.issues || [];
    const missing = report.scan_report?.missing_report || report.missing_report || {};
    const columns = report.scan_report?.columns || report.columns || {};

    // Calculate stats
    const colValues = Object.values(columns);
    const numericCount = colValues.filter(c => {
        const t = (c.type || c.dtype || '').toLowerCase();
        return t.includes("int") || t.includes("float") || t.includes("numeric");
    }).length;
    const catCount = colValues.filter(c => {
        const t = (c.type || c.dtype || '').toLowerCase();
        return t.includes("object") || t.includes("category") || t.includes("bool") || t.includes("str");
    }).length;

    // row_count / col_count: try profile first, then compute from columns metadata
    const rowCount = profile.row_count || (colValues.length > 0 ? colValues[0]?.total : null);
    const colCount = profile.col_count || colValues.length || null;

    return (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6 shadow-sm animate-fadeIn">
            <div className="flex flex-wrap gap-6 items-start">
                {/* Basic Stats */}
                <div className="flex-1 min-w-[200px]">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Обзор данных</h3>
                    <div className="flex items-center gap-4">
                        <div className="text-2xl font-bold text-gray-900">
                            {rowCount?.toLocaleString() || '?'} <span className="text-sm font-normal text-gray-400">строк</span>
                        </div>
                        <div className="w-px h-8 bg-gray-200"></div>
                        <div className="text-2xl font-bold text-gray-900">
                            {colCount?.toLocaleString() || '?'} <span className="text-sm font-normal text-gray-400">колонок</span>
                        </div>
                    </div>
                    <div className="flex gap-3 mt-2 text-xs text-gray-500">
                        <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-100">
                            🔢 {numericCount} числовых
                        </span>
                        <span className="px-2 py-1 bg-purple-50 text-purple-700 rounded-full border border-purple-100">
                            🔤 {catCount} категориальных
                        </span>
                    </div>
                </div>

                {/* Quality Health */}
                <div className="flex-1 min-w-[200px]">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Качество данных</h3>
                    {issues.length === 0 ? (
                        <div className="flex items-center gap-2 text-green-700 bg-green-50 px-3 py-2 rounded-lg border border-green-100">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                            <span className="font-medium">Проблем не найдено</span>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {missing.columns_with_missing > 0 && (
                                <div className="flex items-center gap-2 text-amber-700 bg-amber-50 px-2 py-1 rounded text-xs font-medium border border-amber-100">
                                    <span>⚠️ Пропуски в {missing.columns_with_missing} колонках</span>
                                </div>
                            )}
                            {issues.some(i => i.type === 'mixed_type') && (
                                <div className="flex items-center gap-2 text-red-700 bg-red-50 px-2 py-1 rounded text-xs font-medium border border-red-100">
                                    <span>❌ Найдены смешанные типы данных</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default DataSummaryCard;
