import React, { useEffect, useMemo, useRef, useState } from 'react';
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
    Customized
} from 'recharts';

import { useTranslation } from '../../hooks/useTranslation';
import PlotCustomizer from './PlotCustomizer';
import ExportSettingsModal from './ExportSettingsModal';
import { exportPlot } from '../utils/exportPlot';
import { ArrowDownTrayIcon } from '@heroicons/react/24/outline';

const GRAPHPAD_STYLE = {
    fontFamily: "'Arial', 'Helvetica Neue', sans-serif",
    fontSize: {
        title: 16,
        axisLabel: 13,
        tickLabel: 11,
        legend: 11
    },
    fontWeight: {
        title: 600,
        axisLabel: 500,
        tickLabel: 400
    },
    colors: {
        primary: '#2E86AB',
        secondary: '#A23B72',
        tertiary: '#F18F01',
        quaternary: '#C73E1D',
        text: '#1a1a1a',
        axis: '#4a4a4a',
        grid: '#f0f0f0'
    },
    palette: ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#6B8E23'],
    margin: { top: 25, right: 30, bottom: 55, left: 65 },
    axis: {
        strokeWidth: 1.2,
        tickSize: 5,
        tickWidth: 1
    },
    errorBar: {
        strokeWidth: 1.5,
        capWidth: 6
    },
    grid: {
        stroke: '#f0f0f0',
        strokeDasharray: 'none',
        vertical: false
    }
};

function VisualizeTooltip({ active, payload }) {
    const { t } = useTranslation();

    if (!active || !payload || payload.length === 0) return null;

    const d = payload[0]?.payload;
    if (!d) return null;

    if (d.error && d.stats) {
        return (
            <div style={{
                background: 'var(--white)',
                border: '1px solid var(--border-color)',
                borderRadius: '2px',
                color: 'var(--text-primary)',
                padding: '10px 12px',
                fontSize: '12px',
                lineHeight: 1.4
            }}>
                <div style={{ fontWeight: 800 }}>{d.group}</div>
                <div style={{ marginTop: '6px', color: 'var(--text-secondary)' }}>{t('mean')}: {Number(d.mean).toFixed(2)}</div>
                <div style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>
                    {t('confidence_interval')}: [{Number(d.stats.ci_lower).toFixed(2)}, {Number(d.stats.ci_upper).toFixed(2)}]
                </div>
            </div>
        );
    }

    if (typeof d.value === 'number') {
        return (
            <div style={{
                background: 'var(--white)',
                border: '1px solid var(--border-color)',
                borderRadius: '2px',
                color: 'var(--text-primary)',
                padding: '10px 12px',
                fontSize: '12px',
                lineHeight: 1.4
            }}>
                <div style={{ color: 'var(--text-secondary)' }}>{d.group}: {d.value.toFixed(2)}</div>
            </div>
        );
    }

    return null;
}

export default function VisualizePlot({ data, stats, groups, comparisons, exportScopeId, exportKey = 'main' }) {
    const { t } = useTranslation();
    const plotRef = useRef(null);
    const [isExportOpen, setIsExportOpen] = useState(false);
    const [showRaw, setShowRaw] = useState(true);
    const [showMeanCI, setShowMeanCI] = useState(true);
    const [showBrackets, setShowBrackets] = useState(true);
    const [jitterStrength, setJitterStrength] = useState(0.3);
    const [rawOpacity, setRawOpacity] = useState(0.4);
    const [rawPointSize, setRawPointSize] = useState(3);
    const [showGrid, setShowGrid] = useState(false);
    const [showRandomLine, setShowRandomLine] = useState(true);
    const [rocCurveWidth, setRocCurveWidth] = useState(3);
    const [rocShowDots, setRocShowDots] = useState(false);

    useEffect(() => {
        const handler = (e) => {
            const scopeId = e?.detail?.scopeId;
            const key = e?.detail?.key;
            if (exportScopeId && scopeId && String(scopeId) !== String(exportScopeId)) return;
            if (key && String(key) !== String(exportKey)) return;
            setIsExportOpen(true);
        };

        window.addEventListener('statproject:export-plot', handler);
        return () => window.removeEventListener('statproject:export-plot', handler);
    }, [exportScopeId, exportKey]);

    const safeData = useMemo(() => (Array.isArray(data) ? data : []), [data]);

    const isROC = useMemo(() => {
        if (safeData.length === 0) return false;
        const first = safeData[0];
        return first && typeof first === 'object' && 'x' in first && 'y' in first && !('group' in first);
    }, [safeData]);

    const plotComparisons = useMemo(() => {
        const raw = Array.isArray(comparisons)
            ? comparisons
            : (stats && typeof stats === 'object'
                ? (stats.comparisons || stats.pairwise || stats.pairwise_comparisons)
                : null);
        if (!Array.isArray(raw)) return [];

        const norm = raw
            .map((c) => {
                const a = c?.a ?? c?.group_a ?? c?.group1 ?? c?.left ?? c?.from;
                const b = c?.b ?? c?.group_b ?? c?.group2 ?? c?.right ?? c?.to;
                const p = c?.p_value ?? c?.p ?? c?.pval ?? c?.pValue;
                if (!a || !b || typeof p !== 'number') return null;
                return { a: String(a), b: String(b), p_value: p };
            })
            .filter(Boolean);

        return norm;
    }, [comparisons, stats]);

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
                const jitter = ((d.value * 123.45) % 1 - 0.5) * jitterStrength;
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

        const yValues = [
            ...jitteredData.map(d => d.value).filter(v => typeof v === 'number' && Number.isFinite(v)),
            ...summaryData.map(d => d.mean).filter(v => typeof v === 'number' && Number.isFinite(v))
        ];
        if (yValues.length === 0) return null;
        const minVal = Math.min(...yValues);
        const maxVal = Math.max(...yValues);

        const basePad = (maxVal - minVal) * 0.1 || 1;
        const stepPad = (maxVal - minVal) * 0.06 || 1;

        const groupIndex = Object.fromEntries(uniqueGroups.map((g, i) => [g, i + 1]));
        const comps = plotComparisons
            .map((c) => {
                const ia = groupIndex[c.a];
                const ib = groupIndex[c.b];
                if (typeof ia !== 'number' || typeof ib !== 'number') return null;
                const start = Math.min(ia, ib);
                const end = Math.max(ia, ib);
                return { ...c, start, end };
            })
            .filter(Boolean)
            .sort((x, y) => (x.start - y.start) || (x.end - y.end));

        const levels = [];
        const placed = comps.map((c) => {
            let level = 0;
            while (true) {
                const taken = levels[level] || [];
                const overlaps = taken.some((r) => !(c.end < r.start || c.start > r.end));
                if (!overlaps) break;
                level += 1;
            }
            if (!levels[level]) levels[level] = [];
            levels[level].push({ start: c.start, end: c.end });
            return { ...c, level };
        });

        const maxLevel = placed.length > 0 ? Math.max(...placed.map((c) => c.level)) : -1;
        const extraTop = maxLevel >= 0 ? (maxLevel + 2) * stepPad : 0;
        const yDomain = [minVal - basePad, maxVal + basePad + extraTop];

        const combinedData = [...jitteredData, ...summaryData];

        return { uniqueGroups, jitteredData, summaryData, yDomain, combinedData, comparisonsPlaced: placed, stepPad, maxVal };
    }, [safeData, stats, groups, isROC, jitterStrength, plotComparisons]);

    if (safeData.length === 0) return null;

    const controls = (
        <PlotCustomizer
            isROC={isROC}
            showGrid={showGrid}
            setShowGrid={setShowGrid}
            showRaw={showRaw}
            setShowRaw={setShowRaw}
            showMeanCI={showMeanCI}
            setShowMeanCI={setShowMeanCI}
            showBrackets={showBrackets}
            setShowBrackets={setShowBrackets}
            jitterStrength={jitterStrength}
            setJitterStrength={setJitterStrength}
            rawOpacity={rawOpacity}
            setRawOpacity={setRawOpacity}
            rawPointSize={rawPointSize}
            setRawPointSize={setRawPointSize}
            showRandomLine={showRandomLine}
            setShowRandomLine={setShowRandomLine}
            rocCurveWidth={rocCurveWidth}
            setRocCurveWidth={setRocCurveWidth}
            rocShowDots={rocShowDots}
            setRocShowDots={setRocShowDots}
        />
    );

    if (isROC) {
        return (
            <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {controls}
                <div ref={plotRef} className="relative" style={{ width: '100%', height: 400 }}>
                    <button
                        type="button"
                        onClick={() => setIsExportOpen(true)}
                        className="absolute right-2 top-2 z-10 inline-flex items-center gap-2 px-3 py-2 rounded-[2px] text-xs font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]"
                    >
                        <ArrowDownTrayIcon className="w-4 h-4" />
                        Экспорт
                    </button>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={safeData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                            <CartesianGrid strokeDasharray="2 6" stroke="var(--border-color)" strokeOpacity={0.35} vertical={showGrid} horizontal={showGrid} />
                        <XAxis
                            type="number"
                            dataKey="x"
                            domain={[0, 1]}
                            label={{ value: t('roc_fpr'), position: 'insideBottomRight', offset: -5, fill: 'var(--text-muted)' }}
                            stroke={GRAPHPAD_STYLE.colors.axis}
                            tickLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.tickWidth }}
                            axisLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.strokeWidth }}
                            tick={{ fill: GRAPHPAD_STYLE.colors.axis, fontSize: GRAPHPAD_STYLE.fontSize.tickLabel, fontFamily: GRAPHPAD_STYLE.fontFamily }}
                        />
                        <YAxis
                            type="number"
                            dataKey="y"
                            domain={[0, 1]}
                            label={{ value: t('roc_tpr'), angle: -90, position: 'insideLeft', fill: 'var(--text-muted)' }}
                            stroke={GRAPHPAD_STYLE.colors.axis}
                            tickLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.tickWidth }}
                            axisLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.strokeWidth }}
                            tick={{ fill: GRAPHPAD_STYLE.colors.axis, fontSize: GRAPHPAD_STYLE.fontSize.tickLabel, fontFamily: GRAPHPAD_STYLE.fontFamily }}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: 'var(--white)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', borderRadius: 2 }}
                            formatter={(val) => val.toFixed(3)}
                            labelFormatter={(val) => t('roc_fpr_short', { value: parseFloat(val).toFixed(3) })}
                        />
                        {showRandomLine && (
                            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--text-muted)" strokeDasharray="3 3" strokeOpacity={0.7} label={t('roc_random')} />
                        )}
                        <Line
                            type="monotone"
                            dataKey="y"
                            stroke={GRAPHPAD_STYLE.colors.primary}
                            strokeWidth={rocCurveWidth}
                            dot={rocShowDots ? { r: 3 } : false}
                            name={t('roc_curve')}
                            activeDot={{ r: 8 }}
                        />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
                <ExportSettingsModal
                    isOpen={isExportOpen}
                    onClose={() => setIsExportOpen(false)}
                    defaultTitle={t('roc_curve')}
                    onConfirm={async (settings) => {
                        setIsExportOpen(false);
                        try {
                            await exportPlot(plotRef.current, settings, { fileBaseName: 'roc_curve', defaultTitle: settings?.title || t('roc_curve') });
                        } catch (e) {
                            window.alert(e?.message || 'Не удалось экспортировать график');
                        }
                    }}
                />
            </div>
        );
    }

    if (!chartData) return null;

    const { uniqueGroups, jitteredData, summaryData, yDomain, combinedData, comparisonsPlaced, stepPad, maxVal } = chartData;

    const rawShape = (shapeProps) => {
        const { cx, cy } = shapeProps;
        if (cx == null || cy == null) return null;
        return <circle cx={cx} cy={cy} r={rawPointSize} fill={GRAPHPAD_STYLE.colors.primary} fillOpacity={rawOpacity} />;
    };

    const meanShape = (shapeProps) => {
        const { cx, cy } = shapeProps;
        if (cx == null || cy == null) return null;
        return (
            <circle
                cx={cx}
                cy={cy}
                r={5}
                fill="var(--white)"
                stroke={GRAPHPAD_STYLE.colors.tertiary}
                strokeWidth={2}
            />
        );
    };

    return (
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {controls}
            <div ref={plotRef} className="relative" style={{ width: '100%', height: 350 }}>
                <button
                    type="button"
                    onClick={() => setIsExportOpen(true)}
                    className="absolute right-2 top-2 z-10 inline-flex items-center gap-2 px-3 py-2 rounded-[2px] text-xs font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]"
                >
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    Экспорт
                </button>
                <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart
                        data={combinedData}
                        margin={GRAPHPAD_STYLE.margin}
                    >
                        <CartesianGrid
                            stroke={GRAPHPAD_STYLE.grid.stroke}
                            strokeWidth={1}
                            strokeOpacity={1}
                            strokeDasharray={GRAPHPAD_STYLE.grid.strokeDasharray}
                            vertical={GRAPHPAD_STYLE.grid.vertical && showGrid}
                            horizontal={showGrid}
                        />

                    {/* X Axis: Categorical mapped to Number */}
                    <XAxis
                        dataKey="xPos"
                        type="number"
                        domain={[0, uniqueGroups.length + 1]}
                        ticks={uniqueGroups.map((_, i) => i + 1)}
                        tickFormatter={(val) => uniqueGroups[val - 1] || ""}
                        stroke={GRAPHPAD_STYLE.colors.axis}
                        tickLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.tickWidth, length: GRAPHPAD_STYLE.axis.tickSize }}
                        axisLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.strokeWidth }}
                        tick={{ fill: GRAPHPAD_STYLE.colors.axis, fontSize: GRAPHPAD_STYLE.fontSize.tickLabel, fontFamily: GRAPHPAD_STYLE.fontFamily }}
                    />
                    <YAxis
                        domain={yDomain}
                        tickFormatter={(val) => val.toFixed(1)}
                        stroke={GRAPHPAD_STYLE.colors.axis}
                        tickLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.tickWidth, length: GRAPHPAD_STYLE.axis.tickSize }}
                        axisLine={{ stroke: GRAPHPAD_STYLE.colors.axis, strokeWidth: GRAPHPAD_STYLE.axis.strokeWidth }}
                        tick={{ fill: GRAPHPAD_STYLE.colors.axis, fontSize: GRAPHPAD_STYLE.fontSize.tickLabel, fontFamily: GRAPHPAD_STYLE.fontFamily }}
                    />

                    <Tooltip content={<VisualizeTooltip />} cursor={false} />

                    {showBrackets && Array.isArray(comparisonsPlaced) && comparisonsPlaced.length > 0 && (
                        <Customized
                            component={(p) => {
                                const xAxis = Object.values(p?.xAxisMap || {})?.[0];
                                const yAxis = Object.values(p?.yAxisMap || {})?.[0];
                                const xScale = xAxis?.scale;
                                const yScale = yAxis?.scale;

                                if (typeof xScale !== 'function' || typeof yScale !== 'function') return null;

                                const cap = 8;
                                const yBase = maxVal + stepPad;
                                const labelForP = (pv) => {
                                    if (pv < 0.001) return '***';
                                    if (pv < 0.01) return '**';
                                    if (pv < 0.05) return '*';
                                    return t('not_significant_short');
                                };

                                return (
                                    <g>
                                        {comparisonsPlaced.map((c, i) => {
                                            const yVal = yBase + c.level * stepPad;
                                            const x1 = xScale(c.start);
                                            const x2 = xScale(c.end);
                                            const y = yScale(yVal);
                                            const mid = (x1 + x2) / 2;

                                            return (
                                                <g key={`${c.a}_${c.b}_${i}`}>
                                                    <line x1={x1} y1={y} x2={x2} y2={y} stroke="var(--text-secondary)" strokeWidth={1.25} />
                                                    <line x1={x1} y1={y} x2={x1} y2={y + cap} stroke="var(--text-secondary)" strokeWidth={1.25} />
                                                    <line x1={x2} y1={y} x2={x2} y2={y + cap} stroke="var(--text-secondary)" strokeWidth={1.25} />
                                                    <text x={mid} y={y - 4} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--text-primary)">
                                                        {labelForP(c.p_value)}
                                                    </text>
                                                </g>
                                            );
                                        })}
                                    </g>
                                );
                            }}
                        />
                    )}

                    {/* 1. Raw Data Scatter (Blue, Transparent) */}
                    {showRaw && (
                        <Scatter
                            data={jitteredData}
                            name={t('raw_data')}
                            dataKey="value"
                            shape={rawShape}
                        />
                    )}

                    {/* 2. Mean + CI (Orange, Large) */}
                    {showMeanCI && (
                        <Scatter
                            data={summaryData}
                            name={t('mean_ci')}
                            dataKey="mean"
                            fill={GRAPHPAD_STYLE.colors.tertiary}
                            shape={meanShape}
                        >
                            <ErrorBar
                                dataKey="error"
                                width={GRAPHPAD_STYLE.errorBar.capWidth}
                                strokeWidth={GRAPHPAD_STYLE.errorBar.strokeWidth}
                                stroke={GRAPHPAD_STYLE.colors.tertiary}
                                direction="y"
                            />
                        </Scatter>
                    )}

                    </ComposedChart>
                </ResponsiveContainer>
            </div>
            <ExportSettingsModal
                isOpen={isExportOpen}
                onClose={() => setIsExportOpen(false)}
                defaultTitle={t('mean_ci')}
                onConfirm={async (settings) => {
                    setIsExportOpen(false);
                    try {
                        await exportPlot(plotRef.current, settings, { fileBaseName: 'group_plot', defaultTitle: settings?.title || t('mean_ci') });
                    } catch (e) {
                        window.alert(e?.message || 'Не удалось экспортировать график');
                    }
                }}
            />
        </div>
    );
}
