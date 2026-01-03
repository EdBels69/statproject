export default function VisualizePlot({ data, stats, groups }) {
    if (!data || !data.length) return null;

    // Dimensions
    const width = 600;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 50 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Scales
    const uniqueGroups = groups || [...new Set(data.map(d => d.group))].sort();

    // Y Scale
    const yValues = data.map(d => d.value);
    const minVal = Math.min(...yValues);
    const maxVal = Math.max(...yValues);
    const range = maxVal - minVal;
    // Add 10% padding to Y axis
    const yDomainMin = minVal - (range * 0.1);
    const yDomainMax = maxVal + (range * 0.1);

    const getY = (val) => {
        return chartHeight - ((val - yDomainMin) / (yDomainMax - yDomainMin)) * chartHeight;
    };

    // X Scale (Categorical)
    const bandWidth = chartWidth / uniqueGroups.length;
    const getXCenter = (groupIndex) => {
        return (groupIndex * bandWidth) + (bandWidth / 2);
    };

    return (
        <div className="w-full flex justify-center overflow-hidden">
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto max-w-2xl bg-white rounded-lg">
                <g transform={`translate(${padding.left}, ${padding.top})`}>
                    {/* Grid & Axis */}
                    <line x1={0} y1={chartHeight} x2={chartWidth} y2={chartHeight} stroke="#cbd5e1" strokeWidth="2" />
                    <line x1={0} y1={0} x2={0} y2={chartHeight} stroke="#cbd5e1" strokeWidth="2" />

                    {/* Y Axis Ticks (Rough approx) */}
                    {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
                        const val = yDomainMin + (yDomainMax - yDomainMin) * t;
                        const y = getY(val);
                        return (
                            <g key={i}>
                                <line x1="-5" y1={y} x2="0" y2={y} stroke="#cbd5e1" />
                                <text x="-10" y={y + 4} textAnchor="end" fontSize="10" fill="#64748b">{val.toFixed(1)}</text>
                                <line x1="0" y1={y} x2={chartWidth} y2={y} stroke="#f1f5f9" strokeDasharray="4" />
                            </g>
                        );
                    })}

                    {/* X Axis Labels & Group Zones */}
                    {uniqueGroups.map((group, i) => {
                        const cx = getXCenter(i);
                        const groupStats = stats ? stats[group] : null;

                        return (
                            <g key={group}>
                                {/* Label */}
                                <text x={cx} y={chartHeight + 20} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#334155">
                                    {group}
                                </text>

                                {/* Stats Lines (Mean/Median) */}
                                {groupStats && (
                                    <>
                                        {/* Mean Line (Red) */}
                                        <line
                                            x1={cx - bandWidth / 3}
                                            y1={getY(groupStats.mean)}
                                            x2={cx + bandWidth / 3}
                                            y2={getY(groupStats.mean)}
                                            stroke="#ef4444"
                                            strokeWidth="3"
                                            opacity="0.8"
                                        />
                                        {/* SD Box (Optional, simplified as vertical line) */}
                                        <line
                                            x1={cx}
                                            y1={getY(groupStats.mean - groupStats.sd)}
                                            x2={cx}
                                            y2={getY(groupStats.mean + groupStats.sd)}
                                            stroke="#ef4444"
                                            strokeWidth="1"
                                            opacity="0.5"
                                        />
                                    </>
                                )}
                            </g>
                        );
                    })}

                    {/* Data Points (Jittered) */}
                    {data.map((d, i) => {
                        const groupIdx = uniqueGroups.indexOf(d.group);
                        if (groupIdx === -1) return null;

                        const cx = getXCenter(groupIdx);
                        // Deterministic pseudo-random jitter based on value
                        const jitter = ((d.value * 123.45) % 1 - 0.5) * (bandWidth * 0.4);

                        return (
                            <circle
                                key={i}
                                cx={cx + jitter}
                                cy={getY(d.value)}
                                r="4"
                                fill="#3b82f6"
                                fillOpacity="0.6"
                                stroke="#2563eb"
                                strokeWidth="1"
                            >
                                <title>{`${d.group}: ${d.value}`}</title>
                            </circle>
                        );
                    })}


                    {/* Legend */}
                    <g transform={`translate(${chartWidth - 100}, -10)`}>
                        <rect width="10" height="10" fill="#3b82f6" fillOpacity="0.6" stroke="#2563eb" />
                        <text x="15" y="9" fontSize="10" fill="#64748b">Data Point</text>

                        <line x1="0" y1="20" x2="10" y2="20" stroke="#ef4444" strokeWidth="2" />
                        <text x="15" y="24" fontSize="10" fill="#64748b">Mean ± SD</text>
                    </g>
                </g>
            </svg>
        </div>
    );
}
