import React from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import { formatP, formatNum } from './utils';

export default function AnovaTable({ result }) {
    const { t } = useTranslation();

    if (!result || !result.anova_table) return null;

    // result.anova_table is expected to be a list of objects from backend
    // e.g., [{ "Source": "Group", "SS": 10.5, "df": 2, "MS": 5.25, "F": 4.1, "p-unc": 0.02, "np2": 0.15 }]

    const columns = [
        { key: 'Source', label: t('source') || 'Source' },
        { key: 'SS', label: 'SS' },
        { key: 'df', label: 'df' },
        { key: 'MS', label: 'MS' },
        { key: 'F', label: 'F' },
        { key: 'p-unc', label: 'p' },
        { key: 'np2', label: 'η²p' }, // Partial eta-squared
        { key: 'eta2', label: 'η²' },   // Etc.
        { key: 'omega2', label: 'ω²' }
    ];

    // Filter columns that actually exist in the data
    const availableColumns = columns.filter(col =>
        result.anova_table.some(row => row[col.key] !== undefined)
    );

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm text-left text-[color:var(--text-primary)]">
                <thead className="text-xs text-[color:var(--text-secondary)] uppercase bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)]">
                    <tr>
                        {availableColumns.map(col => (
                            <th key={col.key} className="px-4 py-3 font-semibold">{col.label}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {result.anova_table.map((row, idx) => (
                        <tr key={idx} className="border-b border-[color:var(--border-color)] last:border-0 hover:bg-[color:var(--bg-secondary)]/50">
                            {availableColumns.map(col => (
                                <td key={col.key} className="px-4 py-3">
                                    {col.key === 'Source' ? (
                                        <span className="font-medium">{row[col.key]}</span>
                                    ) : col.key === 'p-unc' ? (
                                        <span className={row[col.key] < 0.05 ? 'text-[color:var(--success)] font-bold' : ''}>
                                            {formatP(row[col.key])}
                                        </span>
                                    ) : (
                                        formatNum(row[col.key], col.key === 'df' ? 0 : 3)
                                    )}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
            {result.effect_size_interpretation && (
                <div className="mt-2 text-xs text-[color:var(--text-secondary)] px-4">
                    {t('interpretation')}: <span className="font-medium">{result.effect_size_interpretation}</span>
                </div>
            )}
        </div>
    );
}
