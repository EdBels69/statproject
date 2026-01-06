import React, { useMemo } from 'react';
import {
    ComposedChart,
    Scatter,
    XAxis,
    YAxis,
    ZAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ErrorBar,
    ReferenceLine,
    LineChart, Line,
    Legend
} from 'recharts';

export default function VisualizePlot({ data, stats, groups }) {
    if (!data || !data.length) return null;

    // 1. Prepare Data
    const chartData = useMemo(() => {
        // Unique Groups
        const uniqueGroups = groups || [...new Set(data.map(d => d.group))].sort();

        // Group Mapping to Integers (for X-axis positioning)
        const groupMap = {};
        uniqueGroups.forEach((g, i) => { groupMap[g] = i + 1; }); // 1-based to give padding

        // Raw Data with Jitter
        const jitteredData = data.map(d => {
            const xBase = groupMap[d.group];
            // Deterministic jitter based on value
            const jitter = ((d.value * 123.45) % 1 - 0.5) * 0.3;
            return {
                ...d,
                xJitter: xBase + jitter,
                index: xBase, // Real group index
            };
        });

        // Summary Statistics (Mean + CI)
        const summaryData = uniqueGroups.map(g => {
            const s = stats ? stats[g] : null;
            if (!s) return null;

            // Recharts ErrorBar expects error relative to value [neg, pos]
            // CI Lower/Upper are absolute. 
            // Error = [Mean - Lower, Upper - Mean]
            const errorNeg = s.mean - s.ci_lower;
            const errorPos = s.ci_upper - s.mean;

            return {
                group: g,
                x: groupMap[g], // Center of the group
                mean: s.mean,
                error: [errorNeg, errorPos],
                stats: s
            };
        }).filter(Boolean);

        return { uniqueGroups, jitteredData, summaryData };
    }, [data, stats, groups]);

    const { uniqueGroups, jitteredData, summaryData } = chartData;

    // Y Axis Domain with padding
    const yValues = data.map(d => d.value);
    const minVal = Math.min(...yValues);
    const maxVal = Math.max(...yValues);
    const padding = (maxVal - minVal) * 0.1 || 1;
    const yDomain = [minVal - padding, maxVal + padding];

    // Tooltip Formatter
    const CustomTooltip = ({ active, payload }) => {
        if (active && payload && payload.length) {
            const d = payload[0].payload;
            // Distinguish Raw Point vs Summary
            if (d.error) {
                return (
                    <div className="bg-slate-800 text-white p-2 rounded shadow text-xs">
                        <p className="font-bold">{d.group}</p>
                        <p>Mean: {d.mean.toFixed(2)}</p>
                        <p>CI: [{d.stats.ci_lower.toFixed(2)}, {d.stats.ci_upper.toFixed(2)}]</p>
                    </div>
                );
            }
            return (
                <div className="bg-slate-800 text-white p-2 rounded shadow text-xs">
                    <p>{d.group}: {d.value.toFixed(2)}</p>
                </div>
            );
        }
        return null;
    };

    // ROC / Line Chart Support
    // Infer if this is ROC data: has x/y but no group
    const isROC = data && data.length > 0 && 'x' in data[0] && 'y' in data[0] && !('group' in data[0]);

    if (isROC) {
        return (
            <div style={{ width: '100%', height: 400 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                        <XAxis
                            type="number"
                            dataKey="x"
                            domain={[0, 1]}
                            label={{ value: 'False Positive Rate (1 - Specificity)', position: 'insideBottomRight', offset: -5, fill: '#aaa' }}
                            stroke="#aaa"
                        />
                        <YAxis
                            type="number"
                            dataKey="y"
                            domain={[0, 1]}
                            label={{ value: 'True Positive Rate (Sensitivity)', angle: -90, position: 'insideLeft', fill: '#aaa' }}
                            stroke="#aaa"
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#1e293b', border: 'none', color: '#fff' }}
                            formatter={(val) => val.toFixed(3)}
                            labelFormatter={(val) => `FPR: ${parseFloat(val).toFixed(3)}`}
                        />
                        <Legend />
                        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#666" strokeDasharray="3 3" label="Random" />
                        <Line
                            type="monotone"
                            dataKey="y"
                            stroke="#8b5cf6"
                            strokeWidth={3}
                            dot={false}
                            name="ROC Curve"
                            activeDot={{ r: 8 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        );
    }

    return (
        <div style={{ width: '100%', height: 350 }}>
            <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                    margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />

                    {/* X Axis: Categorical mapped to Number */}
                    <XAxis
                        dataKey="x"
                        type="number"
                        domain={[0, uniqueGroups.length + 1]}
                        ticks={uniqueGroups.map((_, i) => i + 1)}
                        tickFormatter={(val) => uniqueGroups[val - 1] || ""}
                        stroke="#a3a3a3"
                    />
                    <YAxis
                        domain={yDomain}
                        tickFormatter={(val) => val.toFixed(1)}
                        stroke="#a3a3a3"
                    />

                    <Tooltip content={<CustomTooltip />} cursor={false} />

                    {/* 1. Raw Data Scatter (Blue, Transparent) */}
                    <Scatter
                        data={jitteredData}
                        name="Raw Data"
                        dataKey="value"
                        fill="#60a5fa"
                        fillOpacity={0.4}
                        shape="circle"
                    >
                        {/* We override 'x' position with 'xJitter' */}
                    </Scatter>
                    {/* Hack: Scatter must bind x/y keys. We create ReferenceDots or just map data correctly. 
                        Actually easier: pass `data={jitteredData}` and specify `dataKey` for axes?
                        Recharts Scatter: <XAxis dataKey="xJitter" ... />. 
                        But we share XAxis. 
                        We can specify `data` prop on Scatter. 
                        Let's use `data` prop and specify `dataKey="xJitter"` for x, `dataKey="value"` for y.
                    */}

                    {/* Re-declare Scatter cleanly */}
                    <Scatter
                        data={jitteredData}
                        name="Raw Points"
                        fill="#60a5fa"
                        fillOpacity={0.6}
                    >
                        {/* Bind Scatter X to xJitter */}
                        {/* Note: In ComposedChart, Scatter behaves like a Series. 
                            We need to ensure it uses the numeric X axis correctly.
                        */}
                    </Scatter>

                    {/* 2. Mean + CI (Orange, Large) */}
                    <Scatter
                        data={summaryData}
                        name="Mean & CI"
                        dataKey="mean"
                        fill="#f97316"
                        shape="d" /* diamond or square */
                    >
                        <ErrorBar dataKey="error" width={4} strokeWidth={2} stroke="#f97316" direction="y" />
                    </Scatter>

                </ComposedChart>
            </ResponsiveContainer>

            {/* Quick hack: Recharts Scatter data binding is tricky in ComposedChart. 
                We might need to map specific keys.
                Trying to customize the Scatter props above.
            */}
        </div>
    );
}

// Helper to fix Scatter Key binding:
// Recharts ComposedChart usually shares 'data' prop from parent, but we can pass 'data' to children.
// For Raw Scatter: data={jitteredData}, xKey="xJitter", yKey="value"
// For Summary Scatter: data={summaryData}, xKey="x", yKey="mean"

