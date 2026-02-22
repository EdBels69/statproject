import React, { useState, useCallback } from 'react';
import {
    DocumentArrowDownIcon,
    DocumentTextIcon,
    GlobeAltIcon,
} from '@heroicons/react/24/outline';
import { API_URL } from '../../lib/api';
import { useTranslation } from '../../hooks/useTranslation';

/**
 * Export buttons component for downloading reports in various formats
 */
export default function ExportButtons({
    datasetId,
    title = '',
    objective = '',
    sheetName = null,
    className = '',
}) {
    const { t } = useTranslation();
    const [loading, setLoading] = useState(null);
    const [error, setError] = useState(null);

    const handleExport = useCallback(async (format) => {
        if (!datasetId) return;

        setLoading(format);
        setError(null);

        try {
            const response = await fetch(`${API_URL}/analyze/universal/export/${format}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    dataset_id: datasetId,
                    sheet_name: sheetName,
                    title: title || undefined,
                    objective: objective || undefined,
                }),
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || t('export_failed_status', { status: response.status }));
            }

            // Handle HTML (open in new tab)
            if (format === 'html') {
                const html = await response.text();
                const blob = new Blob([html], { type: 'text/html' });
                const url = URL.createObjectURL(blob);
                window.open(url, '_blank');
                setTimeout(() => URL.revokeObjectURL(url), 60000);
                return;
            }

            // Handle file download
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `report_${datasetId.slice(0, 8)}.${format}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);

        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(null);
        }
    }, [datasetId, title, objective, sheetName, t]);

    const buttons = [
        { format: 'docx', label: t('export_word'), icon: DocumentTextIcon, color: 'text-blue-600' },
        { format: 'pdf', label: t('export_pdf'), icon: DocumentArrowDownIcon, color: 'text-red-600' },
        { format: 'html', label: t('export_html'), icon: GlobeAltIcon, color: 'text-green-600' },
    ];

    return (
        <div className={`flex flex-col gap-2 ${className}`}>
            <div className="flex items-center gap-2">
            {buttons.map(({ format, label, icon, color }) => (
                    <button
                        key={format}
                        type="button"
                        onClick={() => handleExport(format)}
                        disabled={loading || !datasetId}
                        className={`
              inline-flex items-center gap-2 h-9 px-3 rounded-[2px] 
              border border-[color:var(--border-color)] bg-[color:var(--white)]
              hover:border-[color:var(--black)] hover:bg-[color:var(--bg-tertiary)]
              disabled:opacity-50 disabled:cursor-not-allowed
              text-xs font-semibold transition-colors
            `}
                    >
                        {loading === format ? (
                            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                        ) : (
                            React.createElement(icon, { className: `w-4 h-4 ${color}` })
                        )}
                        <span>{label}</span>
                    </button>
                ))}
            </div>

            {error && (
                <div className="text-xs text-red-600 mt-1">{error}</div>
            )}
        </div>
    );
}
