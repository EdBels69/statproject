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
    Legend,
    ScatterChart
} from 'recharts';

export default function VisualizePlot({ data, stats, groups, qqData, type = 'dist' }) {
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
                value: d.value,
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
                    <div className="bg-white border border-gray-200 text-black p-2 rounded shadow-sm text-xs font-mono">
                        <p className="font-bold border-b border-gray-100 mb-1 pb-1">{d.group}</p>
                        <p>Mean: {d.mean.toFixed(2)}</p>
                        <p>CI: [{d.stats.ci_lower.toFixed(2)}, {d.stats.ci_upper.toFixed(2)}]</p>
                    </div>
                );
            }
            return (
                <div className="bg-white border border-gray-200 text-black p-2 rounded shadow-sm text-xs font-mono">
                    <p>{d.group}: {d.value.toFixed(2)}</p>
                </div>
            );
        }
        return null;
    };

    // ROC / Line Chart Support
    const isROC = data && data.length > 0 && 'x' in data[0] && 'y' in data[0] && !('group' in data[0]);

    if (isROC) {
        return (
            <div style={{ width: '100%', height: 400 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                        <XAxis
                            type="number"
                            dataKey="x"
                            domain={[0, 1]}
                            label={{ value: '1 - Specificity', position: 'insideBottomRight', offset: -5, fill: '#737373', fontSize: 12 }}
                            stroke="#d4d4d4"
                            tick={{ fontSize: 11 }}
                        />
                        <YAxis
                            type="number"
                            dataKey="y"
                            domain={[0, 1]}
                            label={{ value: 'Sensitivity', angle: -90, position: 'insideLeft', fill: '#737373', fontSize: 12 }}
                            stroke="#d4d4d4"
                            tick={{ fontSize: 11 }}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e5e5', color: '#000', fontSize: '12px' }}
                            formatter={(val) => val.toFixed(3)}
                            labelFormatter={(val) => `FPR: ${parseFloat(val).toFixed(3)}`}
                            cursor={{ stroke: '#d4d4d4' }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="#a3a3a3" strokeDasharray="3 3" label={{ value: 'Random', fill: '#a3a3a3', fontSize: 10 }} />
                        <Line
                            type="monotone"
                            dataKey="y"
                            stroke="#171717"
                            strokeWidth={2}
                            dot={false}
                            name="ROC Curve"
                            activeDot={{ r: 6, fill: '#000' }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        );
    }

    // Q-Q Plot Logic
    if (type === 'qq' && qqData && qqData.length > 0) {
        // Determine domains
        const xVals = qqData.map(d => d.x);
        const yVals = qqData.map(d => d.y);
        const minX = Math.min(...xVals);
        const maxX = Math.max(...xVals);
        const minY = Math.min(...yVals);
        const maxY = Math.max(...yVals);

        // Reference line (y=x approximate scaling? No, usually probplot is quantiles vs values)
        // Usually, if normal, points lie on straight line.
        // We can just plot the points. Ideally a regression line through them (center).
        // Let's just plot points for now, users know Q-Q look.

        return (
            <div style={{ width: '100%', height: 350 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
                        <XAxis
                            type="number"
                            dataKey="x"
                            name="Theoretical Quantiles"
                            label={{ value: 'Theoretical Quantiles', position: 'insideBottom', offset: -10, fill: '#737373', fontSize: 12 }}
                            domain={['auto', 'auto']}
                            stroke="#d4d4d4"
                            tick={{ fontSize: 11, fill: '#737373' }}
                        />
                        <YAxis
                            type="number"
                            dataKey="y"
                            name="Sample Quantiles"
                            label={{ value: 'Sample Quantiles', angle: -90, position: 'insideLeft', fill: '#737373', fontSize: 12 }}
                            domain={['auto', 'auto']}
                            stroke="#d4d4d4"
                            tick={{ fontSize: 11, fill: '#737373' }}
                        />
                        <Tooltip
                            cursor={{ strokeDasharray: '3 3' }}
                            contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e5e5', color: '#000', fontSize: '12px' }}
                        />
                        <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />
                        <Scatter name="Q-Q Points" data={qqData} fill="#171717" shape="circle" fillOpacity={0.6} />
                    </ScatterChart>
                </ResponsiveContainer>
            </div>
        );
    }

    // Interactive Strip Plot + Mean/CI
    return (
        <div style={{ width: '100%', height: 350 }}>
            <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                    margin={{ top: 20, right: 20, bottom: 20, left: 20 }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" vertical={false} />

                    <XAxis
                        dataKey="x"
                        type="number"
                        domain={[0, uniqueGroups.length + 1]}
                        ticks={uniqueGroups.map((_, i) => i + 1)}
                        tickFormatter={(val) => uniqueGroups[val - 1] || ""}
                        stroke="#d4d4d4"
                        tick={{ fontSize: 12, fill: '#171717' }}
                        interval={0}
                    />
                    <YAxis
                        domain={yDomain}
                        tickFormatter={(val) => val.toFixed(1)}
                        stroke="#d4d4d4"
                        tick={{ fontSize: 11, fill: '#737373' }}
                    />

                    <Tooltip content={<CustomTooltip />} cursor={false} />
                    <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px' }} />

                    {/* 1. Raw Data Scatter */}
                    <Scatter
                        data={jitteredData}
                        name="Raw Points"
                        fill="#525252"
                        fillOpacity={0.3}
                        line={false}
                    >
                        {/* Manually specify cells if needed, but Recharts handles fillOpacity */}
                    </Scatter>

                    {/* 2. Mean + CI */}
                    <Scatter
                        data={summaryData}
                        name="Mean & CI"
                        dataKey="mean"
                        fill="#000000"
                        shape="square"
                        legendType="square"
                    >
                        <ErrorBar dataKey="error" width={6} strokeWidth={1.5} stroke="#000000" direction="y" />
                    </Scatter>

                </ComposedChart>
            </ResponsiveContainer>
        </div>
    );
}

