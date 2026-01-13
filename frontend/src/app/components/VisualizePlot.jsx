import React, { useMemo } from 'react';
import {
    ComposedChart,
    Scatter,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ErrorBar,
    ReferenceLine,
    LineChart, Line,
    Legend
} from 'recharts';

function VisualizeTooltip({ active, payload }) {
    if (!active || !payload || payload.length === 0) return null;

    const d = payload[0]?.payload;
    if (!d) return null;

    if (d.error && d.stats) {
        return (
            <div className="bg-slate-800 text-white p-2 rounded shadow text-xs">
                <p className="font-bold">{d.group}</p>
                <p>Mean: {Number(d.mean).toFixed(2)}</p>
                <p>CI: [{Number(d.stats.ci_lower).toFixed(2)}, {Number(d.stats.ci_upper).toFixed(2)}]</p>
            </div>
        );
    }

    if (typeof d.value === 'number') {
        return (
            <div className="bg-slate-800 text-white p-2 rounded shadow text-xs">
                <p>{d.group}: {d.value.toFixed(2)}</p>
            </div>
        );
    }

    return null;
}

export default function VisualizePlot({ data, stats, groups }) {
    const safeData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

    const isROC = useMemo(() => {
        if (safeData.length === 0) return false;
        const first = safeData[0];
        return first && typeof first === 'object' && 'x' in first && 'y' in first && !('group' in first);
    }, [safeData]);

    const chartData = useMemo(() => {
        if (safeData.length === 0 || isROC) return null;

        const uniqueGroups = groups || [...new Set(safeData.map(d => d.group))].filter(Boolean).sort();
        if (uniqueGroups.length === 0) return null;

        const groupMap = {};
        uniqueGroups.forEach((g, i) => { groupMap[g] = i + 1; });

        const jitteredData = safeData
            .filter(d => d && typeof d.value === 'number' && d.group != null)
            .map(d => {
                const xBase = groupMap[d.group];
                const jitter = ((d.value * 123.45) % 1 - 0.5) * 0.3;
                return {
                    ...d,
                    xPos: xBase + jitter,
                    xTick: xBase
                };
            });

        const summaryData = uniqueGroups
            .map(g => {
                const s = stats ? stats[g] : null;
                if (!s || typeof s.mean !== 'number' || typeof s.ci_lower !== 'number' || typeof s.ci_upper !== 'number') return null;

                const errorNeg = s.mean - s.ci_lower;
                const errorPos = s.ci_upper - s.mean;

                return {
                    group: g,
                    xPos: groupMap[g],
                    xTick: groupMap[g],
                    mean: s.mean,
                    error: [errorNeg, errorPos],
                    stats: s
                };
            })
            .filter(Boolean);

        const yValues = jitteredData.map(d => d.value);
        const minVal = Math.min(...yValues);
        const maxVal = Math.max(...yValues);
        const pad = (maxVal - minVal) * 0.1 || 1;
        const yDomain = [minVal - pad, maxVal + pad];

        const combinedData = [...jitteredData, ...summaryData];

        return { uniqueGroups, jitteredData, summaryData, yDomain, combinedData };
    }, [safeData, stats, groups, isROC]);

    if (safeData.length === 0) return null;

    if (isROC) {
        return (
            <div style={{ width: '100%', height: 400 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={safeData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
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

    if (!chartData) return null;

    const { uniqueGroups, jitteredData, summaryData, yDomain, combinedData } = chartData;

    return (
        <div style={{ width: '100%', height: 350 }}>
            <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                    data={combinedData}
                    margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />

                    {/* X Axis: Categorical mapped to Number */}
                    <XAxis
                        dataKey="xPos"
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

                    <Tooltip content={<VisualizeTooltip />} cursor={false} />

                    {/* 1. Raw Data Scatter (Blue, Transparent) */}
                    <Scatter
                        data={jitteredData}
                        name="Raw Data"
                        dataKey="value"
                        fill="#60a5fa"
                        fillOpacity={0.4}
                        shape="circle"
                    />

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
        </div>
    );
}
