import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ScatterChart, Scatter, Line, LineChart, ZAxis, ErrorBar, Cell
} from 'recharts';

function getTheme() {
    if (typeof document === 'undefined') {
        return {
            accent: 'currentColor',
            accentHover: 'currentColor',
            bgSecondary: 'transparent',
            border: 'currentColor',
            textPrimary: 'currentColor',
            textSecondary: 'currentColor',
            textMuted: 'currentColor',
            white: 'transparent'
        };
    }

    const root = getComputedStyle(document.documentElement);
    return {
        accent: root.getPropertyValue('--accent').trim(),
        accentHover: root.getPropertyValue('--accent-hover').trim(),
        bgSecondary: root.getPropertyValue('--bg-secondary').trim(),
        border: root.getPropertyValue('--border-color').trim(),
        textPrimary: root.getPropertyValue('--text-primary').trim(),
        textSecondary: root.getPropertyValue('--text-secondary').trim(),
        textMuted: root.getPropertyValue('--text-muted').trim(),
        white: root.getPropertyValue('--white').trim()
    };
}

export default function AnalyticsChart({ result }) {
    if (!result) return null;

    const theme = getTheme();

    const { method, plot_stats, plot_data, regression, groups } = result;

    // 1. Group Comparisons (ANOVA, T-test, etc.)
    if (plot_stats && groups) {
        const data = groups.map((g, i) => ({
            name: g,
            mean: plot_stats[g].mean,
            median: plot_stats[g].median,
            error: [plot_stats[g].ci_lower, plot_stats[g].ci_upper],
            opacity: [0.95, 0.8, 0.65, 0.5, 0.35][i % 5]
        }));

        return (
            <div className="h-[400px] w-full mt-6">
                <h4 className="text-sm font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-4 text-center">Group Comparison (Mean & 95% CI)</h4>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.border} />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                        <YAxis axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                        <Tooltip
                            contentStyle={{ borderRadius: 2, border: `1px solid ${theme.border}`, backgroundColor: theme.white, color: theme.textPrimary }}
                            cursor={{ fill: theme.bgSecondary }}
                        />
                        <Bar dataKey="mean" radius={[2, 2, 0, 0]} barSize={60}>
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={theme.accent} fillOpacity={entry.opacity} />
                            ))}
                            <ErrorBar dataKey="error" width={4} strokeWidth={2} stroke={theme.textPrimary} />
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        );
    }

    // 2. Correlation (Pearson, Spearman)
    if (regression && plot_data) {
        const scatterData = plot_data.map(p => ({ x: p.x, y: p.y }));

        // Calculate regression line points
        const xValues = scatterData.map(d => d.x);
        const minX = Math.min(...xValues);
        const maxX = Math.max(...xValues);

        const lineData = [
            { x: minX, y: regression.slope * minX + regression.intercept },
            { x: maxX, y: regression.slope * maxX + regression.intercept }
        ];

        return (
            <div className="h-[400px] w-full mt-6">
                <h4 className="text-sm font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-4 text-center">Relationship Analysis (Scatter + Trend)</h4>
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                        <XAxis type="number" dataKey="x" name="Target" axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                        <YAxis type="number" dataKey="y" name="Feature" axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                        <ZAxis type="number" range={[64]} />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ borderRadius: 2, border: `1px solid ${theme.border}`, backgroundColor: theme.white, color: theme.textPrimary }} />
                        <Scatter name="Data Points" data={scatterData} fill={theme.accent} fillOpacity={0.35} />
                        <Line
                            type="monotone"
                            dataKey="y"
                            data={lineData}
                            stroke={theme.accent}
                            strokeWidth={3}
                            dot={false}
                            activeDot={false}
                            legendType="none"
                        />
                    </ScatterChart>
                </ResponsiveContainer>
                <div className="text-center mt-2 text-xs text-[color:var(--text-muted)] italic">
                    R-Squared: {regression.r_squared.toFixed(4)} | Slope: {regression.slope.toFixed(2)}
                </div>
            </div>
        );
    }

    // 2.1. Bland-Altman plot
    if (method === "bland_altman" && Array.isArray(plot_data) && plot_data.length > 0) {
        const scatterData = plot_data
            .map((p) => ({ x: Number(p?.x), y: Number(p?.y) }))
            .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
        if (scatterData.length === 0) {
            return null;
        }

        const xValues = scatterData.map((d) => d.x);
        const minX = Math.min(...xValues);
        const maxX = Math.max(...xValues);

        const refs = result.plot_reference_lines || {};
        const mkLine = (yVal) => (
            Number.isFinite(Number(yVal))
                ? [{ x: minX, y: Number(yVal) }, { x: maxX, y: Number(yVal) }]
                : []
        );
        const lineMean = mkLine(refs?.mean_difference?.y ?? result?.mean_difference);
        const lineLoaLow = mkLine(refs?.loa_lower?.y ?? result?.loa_lower);
        const lineLoaHigh = mkLine(refs?.loa_upper?.y ?? result?.loa_upper);
        const lineZero = mkLine(refs?.zero?.y ?? 0);

        return (
            <div className="h-[420px] w-full mt-6">
                <h4 className="text-sm font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-4 text-center">
                    Bland-Altman Agreement Plot
                </h4>
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                        <XAxis type="number" dataKey="x" name="Mean" axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                        <YAxis type="number" dataKey="y" name="Difference" axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                        <Tooltip contentStyle={{ borderRadius: 2, border: `1px solid ${theme.border}`, backgroundColor: theme.white, color: theme.textPrimary }} />
                        <Legend verticalAlign="top" height={32} />
                        <Scatter name="Observations" data={scatterData} fill={theme.accent} fillOpacity={0.35} />
                        {lineMean.length > 0 ? <Line data={lineMean} dataKey="y" stroke={theme.accent} strokeWidth={2} dot={false} name="Mean bias" /> : null}
                        {lineLoaLow.length > 0 ? <Line data={lineLoaLow} dataKey="y" stroke={theme.textMuted} strokeDasharray="6 4" strokeWidth={2} dot={false} name="LoA lower" /> : null}
                        {lineLoaHigh.length > 0 ? <Line data={lineLoaHigh} dataKey="y" stroke={theme.textMuted} strokeDasharray="6 4" strokeWidth={2} dot={false} name="LoA upper" /> : null}
                        {lineZero.length > 0 ? <Line data={lineZero} dataKey="y" stroke={theme.border} strokeDasharray="2 4" strokeWidth={1} dot={false} name="Zero" /> : null}
                    </ScatterChart>
                </ResponsiveContainer>
            </div>
        );
    }

    // 2.2. Time-series trend plot
    if (method === "time_series_analysis" && Array.isArray(plot_data) && plot_data.length > 0) {
        const lineData = plot_data.map((p, i) => ({
            x: p?.x ?? i,
            y: Number(p?.y),
            trend: Number(p?.trend),
            forecast: Number.NaN,
        })).filter((p) => Number.isFinite(p.y));
        const forecastPoints = Array.isArray(result?.forecast?.points)
            ? result.forecast.points
                .map((p, i) => ({
                    x: p?.x ?? `f_${i}`,
                    y: Number.NaN,
                    trend: Number.NaN,
                    forecast: Number(p?.y),
                }))
                .filter((p) => Number.isFinite(p.forecast))
            : [];
        const chartData = forecastPoints.length > 0 ? [...lineData, ...forecastPoints] : lineData;
        if (lineData.length === 0) {
            return null;
        }
        const hasTrend = lineData.some((d) => Number.isFinite(d.trend));
        const hasForecast = forecastPoints.length > 0;
        const diagnostics = (result?.diagnostics && typeof result.diagnostics === 'object') ? result.diagnostics : {};
        const timeQuality = (result?.time_quality && typeof result.time_quality === 'object')
            ? result.time_quality
            : ((diagnostics?.time_quality && typeof diagnostics.time_quality === 'object') ? diagnostics.time_quality : {});
        const qualityRaw = String(timeQuality?.quality || '').toLowerCase();
        const qualityLabel = ({
            ok: 'OK',
            caution: 'Caution',
            warning: 'High risk',
        })[qualityRaw] || 'n/a';
        const parseRatioValue = Number(timeQuality?.datetime_parse_ratio);
        const parseRatioLabel = Number.isFinite(parseRatioValue) ? `${(parseRatioValue * 100).toFixed(1)}%` : 'n/a';
        const minYear = Number(timeQuality?.min_year);
        const maxYear = Number(timeQuality?.max_year);
        const yearRangeLabel = Number.isFinite(minYear) && Number.isFinite(maxYear)
            ? `${Math.trunc(minYear)}-${Math.trunc(maxYear)}`
            : 'n/a';
        const inferredFrequency = String(timeQuality?.inferred_frequency || '').trim() || 'n/a';
        const axisType = String(result?.time_axis_kind || timeQuality?.time_axis_kind || 'index');
        const qualityFlags = Array.isArray(timeQuality?.flags)
            ? timeQuality.flags
                .map((flag) => String(flag || '').trim())
                .filter(Boolean)
            : [];
        const warnings = Array.isArray(result?.warnings)
            ? result.warnings
                .map((w) => String(w || '').trim())
                .filter(Boolean)
            : [];
        return (
            <div className="w-full mt-6">
                <div className="h-[420px]">
                    <h4 className="text-sm font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-4 text-center">
                        Time Series
                    </h4>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                            <XAxis dataKey="x" axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 11 }} />
                            <YAxis axisLine={false} tickLine={false} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                            <Tooltip contentStyle={{ borderRadius: 2, border: `1px solid ${theme.border}`, backgroundColor: theme.white, color: theme.textPrimary }} />
                            <Legend verticalAlign="top" height={32} />
                            <Line type="monotone" dataKey="y" name="Series" stroke={theme.accent} strokeWidth={2.5} dot={false} />
                            {hasTrend ? <Line type="monotone" dataKey="trend" name="Trend" stroke={theme.textMuted} strokeWidth={2} dot={false} strokeDasharray="6 4" /> : null}
                            {hasForecast ? <Line type="monotone" dataKey="forecast" name="Forecast" stroke={theme.accentHover || theme.accent} strokeWidth={2} dot={false} strokeDasharray="3 3" /> : null}
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                    <div className="px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)]">
                        <span className="text-[color:var(--text-muted)]">Time Axis:</span> <span className="font-semibold text-[color:var(--text-primary)]">{axisType}</span>
                    </div>
                    <div className="px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)]">
                        <span className="text-[color:var(--text-muted)]">Time Quality:</span> <span className="font-semibold text-[color:var(--text-primary)]">{qualityLabel}</span>
                    </div>
                    <div className="px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)]">
                        <span className="text-[color:var(--text-muted)]">Datetime Parse:</span> <span className="font-semibold text-[color:var(--text-primary)]">{parseRatioLabel}</span>
                    </div>
                    <div className="px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)]">
                        <span className="text-[color:var(--text-muted)]">Year Range:</span> <span className="font-semibold text-[color:var(--text-primary)]">{yearRangeLabel}</span>
                    </div>
                    <div className="px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)] col-span-2">
                        <span className="text-[color:var(--text-muted)]">Inferred Frequency:</span> <span className="font-semibold text-[color:var(--text-primary)]">{inferredFrequency}</span>
                        {qualityFlags.length > 0 ? (
                            <span className="ml-2 text-[color:var(--text-muted)]">Flags: {qualityFlags.join(', ')}</span>
                        ) : null}
                    </div>
                </div>

                {warnings.length > 0 ? (
                    <div className="mt-3 px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)]">
                        <div className="text-xs font-semibold text-[color:var(--text-primary)] mb-1">Chronology Warnings</div>
                        <ul className="list-disc pl-5 text-xs text-[color:var(--text-muted)]">
                            {warnings.slice(0, 5).map((w, idx) => <li key={`ts-warning-${idx}`}>{w}</li>)}
                        </ul>
                    </div>
                ) : null}
            </div>
        );
    }

    // 3. Survival Analysis (Kaplan-Meier)
    if (method === "survival_km" && plot_data) {
        const uniqueGroups = Array.from(new Set(plot_data.map(p => p.group)));

        return (
            <div className="h-[400px] w-full mt-6">
                <h4 className="text-sm font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-4 text-center">Survival Analysis (Kaplan-Meier)</h4>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.border} />
                        <XAxis
                            type="number"
                            dataKey="time"
                            name="Time"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: theme.textSecondary, fontSize: 12 }}
                            label={{ value: 'Time (Units)', position: 'insideBottom', offset: -10, fill: theme.textMuted }}
                        />
                        <YAxis
                            type="number"
                            domain={[0, 1]}
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: theme.textSecondary, fontSize: 12 }}
                            label={{ value: 'Survival Probability', angle: -90, position: 'insideLeft', offset: 10, fill: theme.textMuted }}
                        />
                        <Tooltip
                            contentStyle={{ borderRadius: 2, border: `1px solid ${theme.border}`, backgroundColor: theme.white, color: theme.textPrimary }}
                        />
                        <Legend verticalAlign="top" height={36} />
                        {uniqueGroups.map((g, i) => (
                            <Line
                                key={g}
                                type="stepAfter"
                                data={plot_data.filter(p => p.group === g)}
                                dataKey="probability"
                                name={g}
                                stroke={theme.accent}
                                strokeOpacity={[1, 0.8, 0.65, 0.5, 0.35][i % 5]}
                                strokeWidth={3}
                                dot={false}
                                activeDot={{ r: 2 }}
                                connectNulls
                            />
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        );
    }

    // 4. Regression Analysis (Linear & Logistic)
    if ((method === "linear_regression" || method === "logistic_regression") && result.coefficients) {
        const isLogistic = method === "logistic_regression";
        const data = result.coefficients.filter(c => c.variable !== 'const');

        return (
            <div className="h-[450px] w-full mt-6">
                <h4 className="text-sm font-bold text-[color:var(--text-muted)] uppercase tracking-widest mb-4 text-center">
                    {isLogistic ? 'Odds Ratios (Logistic Regression)' : 'Model Coefficients (Linear Regression)'}
                </h4>
                <div className="flex flex-col gap-6">
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke={theme.border} />
                            <XAxis type="number" hide={!isLogistic} domain={isLogistic ? [0, 'auto'] : ['auto', 'auto']} />
                            <YAxis type="category" dataKey="variable" axisLine={false} tickLine={false} width={100} tick={{ fill: theme.textSecondary, fontSize: 12 }} />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                contentStyle={{ borderRadius: 2, border: `1px solid ${theme.border}`, backgroundColor: theme.white, color: theme.textPrimary }}
                                formatter={(val, name) => {
                                    if (isLogistic && name === "OR") return [val.toFixed(2), "Odds Ratio"];
                                    return [val.toFixed(3), name];
                                }}
                            />
                            <Bar
                                dataKey={isLogistic ? "odds_ratio" : "coefficient"}
                                name={isLogistic ? "OR" : "Coef"}
                                radius={[0, 2, 2, 0]}
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.p_value < 0.05 ? theme.accent : theme.border} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] text-center">
                            <span className="block text-[color:var(--text-muted)] text-xs font-black uppercase tracking-tighter">Model Fit (R²)</span>
                            <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">{result.r_squared.toFixed(3)}</span>
                        </div>
                        <div className="p-4 bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] text-center">
                            <span className="block text-[color:var(--text-muted)] text-xs font-black uppercase tracking-tighter">Predictors</span>
                            <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">{data.length}</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 text-center text-[color:var(--text-muted)] bg-[color:var(--bg-secondary)] rounded-[2px] border border-dashed border-[color:var(--border-color)] italic">
            No visualization data available for this method.
        </div>
    );
}
