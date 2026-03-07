import React from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import { formatP, formatNum } from './utils';

export default function RegressionTable({ result }) {
    const { t } = useTranslation();

    if (!result || !result.coefficients) return null;

    // result.coefficients is array of { variable, coefficient, p_value, std_err, ci_lower, ci_upper, vif }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm text-center text-[color:var(--text-primary)]">
                <thead className="text-xs text-[color:var(--text-secondary)] uppercase bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)]">
                    <tr>
                        <th className="px-4 py-3 font-semibold text-left">{t('variable') || 'Variable'}</th>
                        <th className="px-4 py-3 font-semibold">{t('coefficients') || 'Coeff'}</th>
                        <th className="px-4 py-3 font-semibold">{t('se') || 'SE'}</th>
                        <th className="px-4 py-3 font-semibold">{t('p_value') || 'p'}</th>
                        {result.coefficients[0].ci_lower !== undefined && (
                            <th className="px-4 py-3 font-semibold">{t('ci_95') || '95% CI'}</th>
                        )}
                        {result.coefficients[0].vif !== undefined && (
                            <th className="px-4 py-3 font-semibold">VIF</th>
                        )}
                        {result.coefficients[0].odds_ratio !== undefined && (
                            <th className="px-4 py-3 font-semibold">{t('odds_ratio') || 'OR'} (95% CI)</th>
                        )}
                    </tr>
                </thead>
                <tbody>
                    {result.coefficients.map((row, idx) => (
                        <tr key={idx} className="border-b border-[color:var(--border-color)] last:border-0 hover:bg-[color:var(--bg-secondary)]/50">
                            <td className="px-4 py-3 text-left font-medium">{row.variable}</td>
                            <td className="px-4 py-3 font-mono">{formatNum(row.coefficient, 3)}</td>
                            <td className="px-4 py-3 font-mono text-[color:var(--text-secondary)]">
                                {formatNum(row.std_err, 3)}
                            </td>
                            <td className={`px-4 py-3 font-mono ${row.p_value < 0.05 ? 'text-[color:var(--success)] font-bold' : ''}`}>
                                {formatP(row.p_value)}
                            </td>

                            {/* Linear Regression CI */}
                            {row.ci_lower !== undefined && (
                                <td className="px-4 py-3 font-mono text-xs text-[color:var(--text-secondary)]">
                                    [{formatNum(row.ci_lower, 2)}, {formatNum(row.ci_upper, 2)}]
                                </td>
                            )}

                            {/* VIF */}
                            {row.vif !== undefined && (
                                <td className={`px-4 py-3 font-mono ${row.vif > 10 ? 'text-[color:var(--error)] font-bold' : row.vif > 5 ? 'text-[color:var(--warning)]' : ''}`}>
                                    {formatNum(row.vif, 2)}
                                </td>
                            )}

                            {/* Logistic OR */}
                            {row.odds_ratio !== undefined && (
                                <td className="px-4 py-3 font-mono">
                                    {formatNum(row.odds_ratio, 2)}
                                    <span className="text-[color:var(--text-secondary)] text-xs ml-1">
                                        [{formatNum(row.or_ci_lower, 2)}, {formatNum(row.or_ci_upper, 2)}]
                                    </span>
                                </td>
                            )}
                        </tr>
                    ))}
                </tbody>
            </table>
            {result.r_squared !== undefined && (
                <div className="mt-2 text-xs text-[color:var(--text-secondary)] px-4 flex gap-4">
                    <span>R²: <b>{formatNum(result.r_squared, 3)}</b></span>
                    {result.adj_r_squared !== undefined && (
                        <span>Adj. R²: <b>{formatNum(result.adj_r_squared, 3)}</b></span>
                    )}
                </div>
            )}
        </div>
    );
}
