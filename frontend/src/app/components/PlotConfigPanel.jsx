import { useMemo, useState } from 'react';
import { useTranslation } from '../../hooks/useTranslation';

export default function PlotConfigPanel({
    isROC,
    showGrid,
    setShowGrid,
    showRaw,
    setShowRaw,
    showMeanCI,
    setShowMeanCI,
    jitterStrength,
    setJitterStrength,
    rawOpacity,
    setRawOpacity,
    rawPointSize,
    setRawPointSize,
    showRandomLine,
    setShowRandomLine,
    rocCurveWidth,
    setRocCurveWidth,
    rocShowDots,
    setRocShowDots
}) {
    const { t, hasTranslation } = useTranslation();
    const [collapsed, setCollapsed] = useState(false);

    const panelTitle = useMemo(() => {
        return hasTranslation('plot_settings') ? t('plot_settings') : 'Plot';
    }, [hasTranslation, t]);

    const controlWrapStyle = {
        display: 'flex',
        flexWrap: 'wrap',
        gap: '10px',
        alignItems: 'center',
        padding: '10px 12px',
        border: '1px solid var(--border-color)',
        borderRadius: '2px',
        background: 'var(--bg-tertiary)'
    };

    const controlTitleStyle = {
        fontSize: '10px',
        fontWeight: 700,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: 'var(--text-muted)',
        marginRight: '6px'
    };

    const labelStyle = {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '11px',
        color: 'var(--text-secondary)',
        fontFamily: 'monospace'
    };

    const rangeStyle = {
        width: '120px',
        accentColor: 'var(--accent)'
    };

    const valueStyle = {
        fontSize: '10px',
        color: 'var(--text-muted)',
        fontFamily: 'monospace',
        minWidth: '36px',
        textAlign: 'right'
    };

    const collapseButtonStyle = {
        marginLeft: 'auto',
        fontSize: '10px',
        fontFamily: 'monospace',
        border: '1px solid var(--border-color)',
        background: 'transparent',
        color: 'var(--text-muted)',
        padding: '4px 8px',
        borderRadius: '2px',
        cursor: 'pointer'
    };

    return (
        <div style={controlWrapStyle}>
            <span style={controlTitleStyle}>{panelTitle}</span>
            <button
                type="button"
                onClick={() => setCollapsed((v) => !v)}
                style={collapseButtonStyle}
            >
                {collapsed ? (hasTranslation('show') ? t('show') : 'Show') : (hasTranslation('hide') ? t('hide') : 'Hide')}
            </button>

            {!collapsed && (
                <>
                    <label style={labelStyle}>
                        <input type="checkbox" checked={!!showGrid} onChange={(e) => setShowGrid?.(e.target.checked)} />
                        {hasTranslation('plot_grid') ? t('plot_grid') : 'Grid'}
                    </label>

                    {isROC ? (
                        <>
                            <label style={labelStyle}>
                                <input type="checkbox" checked={!!showRandomLine} onChange={(e) => setShowRandomLine?.(e.target.checked)} />
                                {hasTranslation('plot_random_line') ? t('plot_random_line') : 'Random'}
                            </label>
                            <label style={labelStyle}>
                                <input type="checkbox" checked={!!rocShowDots} onChange={(e) => setRocShowDots?.(e.target.checked)} />
                                {hasTranslation('plot_dots') ? t('plot_dots') : 'Dots'}
                            </label>
                            <label style={labelStyle}>
                                {hasTranslation('plot_curve_width') ? t('plot_curve_width') : 'Width'}
                                <input
                                    type="range"
                                    min={1}
                                    max={6}
                                    step={1}
                                    value={typeof rocCurveWidth === 'number' ? rocCurveWidth : 3}
                                    onChange={(e) => setRocCurveWidth?.(Number(e.target.value))}
                                    style={rangeStyle}
                                />
                                <span style={valueStyle}>{typeof rocCurveWidth === 'number' ? rocCurveWidth : 3}</span>
                            </label>
                        </>
                    ) : (
                        <>
                            <label style={labelStyle}>
                                <input type="checkbox" checked={!!showRaw} onChange={(e) => setShowRaw?.(e.target.checked)} />
                                {t('raw_data')}
                            </label>
                            <label style={labelStyle}>
                                <input type="checkbox" checked={!!showMeanCI} onChange={(e) => setShowMeanCI?.(e.target.checked)} />
                                {t('mean_ci')}
                            </label>
                            <label style={labelStyle}>
                                {hasTranslation('plot_jitter') ? t('plot_jitter') : 'Jitter'}
                                <input
                                    type="range"
                                    min={0}
                                    max={0.6}
                                    step={0.05}
                                    value={typeof jitterStrength === 'number' ? jitterStrength : 0.3}
                                    onChange={(e) => setJitterStrength?.(Number(e.target.value))}
                                    style={rangeStyle}
                                />
                                <span style={valueStyle}>{(typeof jitterStrength === 'number' ? jitterStrength : 0.3).toFixed(2)}</span>
                            </label>
                            <label style={labelStyle}>
                                {hasTranslation('plot_opacity') ? t('plot_opacity') : 'Opacity'}
                                <input
                                    type="range"
                                    min={0.1}
                                    max={0.9}
                                    step={0.05}
                                    value={typeof rawOpacity === 'number' ? rawOpacity : 0.4}
                                    onChange={(e) => setRawOpacity?.(Number(e.target.value))}
                                    style={rangeStyle}
                                />
                                <span style={valueStyle}>{(typeof rawOpacity === 'number' ? rawOpacity : 0.4).toFixed(2)}</span>
                            </label>
                            <label style={labelStyle}>
                                {hasTranslation('plot_point') ? t('plot_point') : 'Point'}
                                <input
                                    type="range"
                                    min={2}
                                    max={8}
                                    step={1}
                                    value={typeof rawPointSize === 'number' ? rawPointSize : 3}
                                    onChange={(e) => setRawPointSize?.(Number(e.target.value))}
                                    style={rangeStyle}
                                />
                                <span style={valueStyle}>{typeof rawPointSize === 'number' ? rawPointSize : 3}</span>
                            </label>
                        </>
                    )}
                </>
            )}
        </div>
    );
}
