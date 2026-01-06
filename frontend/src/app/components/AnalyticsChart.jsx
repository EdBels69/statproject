import React from 'react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ScatterChart, Scatter, Line, ZAxis, ErrorBar, Cell
} from 'recharts';

const COLORS = ['#4f46e5', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316'];

export default function AnalyticsChart({ result }) {
    if (!result) return null;

    const { method, plot_stats, plot_data, regression, groups } = result;

    // 1. Group Comparisons (ANOVA, T-test, etc.)
    if (plot_stats && groups) {
        const data = groups.map((g, i) => ({
            name: g,
            mean: plot_stats[g].mean,
            median: plot_stats[g].median,
            error: [plot_stats[g].ci_lower, plot_stats[g].ci_upper],
            fill: COLORS[i % COLORS.length]
        }));

        return (
            <div className="h-[400px] w-full mt-6">
                <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4 text-center">Group Comparison (Mean & 95% CI)</h4>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="name" axisLine={false} tickLine={false} />
                        <YAxis axisLine={false} tickLine={false} />
                        <Tooltip
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                            cursor={{ fill: '#f8fafc' }}
                        />
                        <Bar dataKey="mean" radius={[6, 6, 0, 0]} barSize={60}>
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.fill} fillOpacity={0.8} />
                            ))}
                            <ErrorBar dataKey="error" width={4} strokeWidth={2} stroke="#334155" />
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
                <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4 text-center">Relationship Analysis (Scatter + Trend)</h4>
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis type="number" dataKey="x" name="Target" axisLine={false} tickLine={false} />
                        <YAxis type="number" dataKey="y" name="Feature" axisLine={false} tickLine={false} />
                        <ZAxis type="number" range={[64]} />
                        <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }} />
                        <Scatter name="Data Points" data={scatterData} fill="#4f46e5" fillOpacity={0.5} />
                        <Line
                            type="monotone"
                            dataKey="y"
                            data={lineData}
                            stroke="#ec4899"
                            strokeWidth={3}
                            dot={false}
                            activeDot={false}
                            legendType="none"
                        />
                    </ScatterChart>
                </ResponsiveContainer>
                <div className="text-center mt-2 text-xs text-slate-400 italic">
                    R-Squared: {regression.r_squared.toFixed(4)} | Slope: {regression.slope.toFixed(2)}
                </div>
            </div>
        );
    }

    // 3. Survival Analysis (Kaplan-Meier)
    if (method === "survival_km" && plot_data) {
        const uniqueGroups = Array.from(new Set(plot_data.map(p => p.group)));

        return (
            <div className="h-[400px] w-full mt-6">
                <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4 text-center">Survival Analysis (Kaplan-Meier)</h4>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                        <XAxis
                            type="number"
                            dataKey="time"
                            name="Time"
                            axisLine={false}
                            tickLine={false}
                            label={{ value: 'Time (Units)', position: 'insideBottom', offset: -10 }}
                        />
                        <YAxis
                            type="number"
                            domain={[0, 1]}
                            axisLine={false}
                            tickLine={false}
                            label={{ value: 'Survival Probability', angle: -90, position: 'insideLeft', offset: 10 }}
                        />
                        <Tooltip
                            contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                        />
                        <Legend verticalAlign="top" height={36} />
                        {uniqueGroups.map((g, i) => (
                            <Line
                                key={g}
                                type="stepAfter"
                                data={plot_data.filter(p => p.group === g)}
                                dataKey="probability"
                                name={g}
                                stroke={COLORS[i % COLORS.length]}
                                strokeWidth={3}
                                dot={false}
                                activeDot={{ r: 6 }}
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
                <h4 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-4 text-center">
                    {isLogistic ? 'Odds Ratios (Logistic Regression)' : 'Model Coefficients (Linear Regression)'}
                </h4>
                <div className="flex flex-col gap-6">
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="#f1f5f9" />
                            <XAxis type="number" hide={!isLogistic} domain={isLogistic ? [0, 'auto'] : ['auto', 'auto']} />
                            <YAxis type="category" dataKey="variable" axisLine={false} tickLine={false} width={100} />
                            <Tooltip
                                cursor={{ fill: 'transparent' }}
                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                                formatter={(val, name, props) => {
                                    if (isLogistic && name === "OR") return [val.toFixed(2), "Odds Ratio"];
                                    return [val.toFixed(3), name];
                                }}
                            />
                            <Bar
                                dataKey={isLogistic ? "odds_ratio" : "coefficient"}
                                name={isLogistic ? "OR" : "Coef"}
                                radius={[0, 4, 4, 0]}
                            >
                                {data.map((entry, index) => (
                                    <Cell key={`cell-${index}`} fill={entry.p_value < 0.05 ? '#4f46e5' : '#cbd5e1'} />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>

                    <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-slate-50 rounded-2xl text-center">
                            <span className="block text-slate-400 text-xs font-black uppercase tracking-tighter">Model Fit (R²)</span>
                            <span className="text-2xl font-mono font-black text-slate-900">{result.r_squared.toFixed(3)}</span>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-2xl text-center">
                            <span className="block text-slate-400 text-xs font-black uppercase tracking-tighter">Predictors</span>
                            <span className="text-2xl font-mono font-black text-slate-900">{data.length}</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="p-8 text-center text-slate-400 bg-slate-50 rounded-2xl border-2 border-dashed border-slate-100 italic">
            No visualization data available for this method.
        </div>
    );
}
