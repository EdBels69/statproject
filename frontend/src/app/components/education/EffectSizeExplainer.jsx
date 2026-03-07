/**
 * Effect Size Explainer Component.
 * 
 * Provides visual interpretation of effect size values with:
 * - Scale indicator (small/medium/large)
 * - Practical meaning
 * - Confidence interval display
 * 
 * Usage:
 *   <EffectSizeExplainer type="cohens_d" value={0.67} ci={[0.23, 1.11]} />
 */

import React from 'react';
import { ChartBarIcon } from '@heroicons/react/24/outline';

const COHENS_D_THRESHOLDS = {
    negligible: { max: 0.2, label: "незначительный", color: "gray" },
    small: { max: 0.5, label: "малый", color: "blue" },
    medium: { max: 0.8, label: "средний", color: "amber" },
    large: { min: 0.8, label: "большой", color: "green" }
};

const ETA_THRESHOLDS = {
    small: { max: 0.06, label: "малый", color: "blue" },
    medium: { max: 0.14, label: "средний", color: "amber" },
    large: { min: 0.14, label: "большой", color: "green" }
};

const CORR_THRESHOLDS = {
    weak: { max: 0.3, label: "слабая", color: "blue" },
    moderate: { max: 0.5, label: "умеренная", color: "amber" },
    strong: { min: 0.5, label: "сильная", color: "green" }
};

const OR_THRESHOLDS = {
    negligible: { max: 1.5, label: "незначительный", color: "gray" },
    small: { max: 2.5, label: "малый", color: "blue" },
    medium: { max: 4.3, label: "средний", color: "amber" },
    large: { min: 4.3, label: "большой", color: "green" }
};

const THRESHOLDS = {
    cohens_d: COHENS_D_THRESHOLDS,
    partial_eta_squared: ETA_THRESHOLDS,
    eta_squared: ETA_THRESHOLDS,
    r: CORR_THRESHOLDS,
    cramers_v: CORR_THRESHOLDS,
    rank_biserial: CORR_THRESHOLDS,
    odds_ratio: OR_THRESHOLDS,
    or: OR_THRESHOLDS
};

const TYPE_NAMES = {
    cohens_d: "Cohen's d",
    partial_eta_squared: "Partial η²",
    eta_squared: "η²",
    r: "r",
    cramers_v: "Cramér's V",
    rank_biserial: "r (rank-biserial)",
    odds_ratio: "Odds ratio",
    or: "OR"
};

// Practical meaning for Cohen's d
const COHENS_D_PRACTICAL = {
    0.2: "~58%",
    0.5: "~69%",
    0.8: "~79%",
    1.0: "~84%",
    1.2: "~88%"
};

function getInterpretation(type, value) {
    const thresholds = THRESHOLDS[type] || THRESHOLDS.cohens_d;
    const absValue = Math.abs(value);

    for (const [key, config] of Object.entries(thresholds)) {
        const max = config.max ?? Infinity;
        const min = config.min ?? 0;

        if (absValue >= min && absValue < max) {
            return { key, ...config };
        }
        if (config.min !== undefined && absValue >= config.min) {
            return { key, ...config };
        }
    }

    return { key: "unknown", label: "неопределённый", color: "gray" };
}

function getPracticalMeaning(type, value) {
    if (type !== "cohens_d") return null;

    const absValue = Math.abs(value);
    const closest = Object.keys(COHENS_D_PRACTICAL)
        .map(Number)
        .reduce((prev, curr) =>
            Math.abs(curr - absValue) < Math.abs(prev - absValue) ? curr : prev
        );

    const pct = COHENS_D_PRACTICAL[closest];
    return `${pct} группы A выше среднего группы B`;
}

export function getEffectSizeInterpretation(type, value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return null;
    }

    return getInterpretation(type, value);
}

export default function EffectSizeExplainer({
    type = "cohens_d",
    value,
    ci,
    showScale = true,
    compact = false
}) {
    if (value === null || value === undefined) {
        return null;
    }

    const interpretation = getInterpretation(type, value);
    const typeName = TYPE_NAMES[type] || type;
    const ciIncludesZero = ci && ci[0] <= 0 && ci[1] >= 0;
    const practicalMeaning = getPracticalMeaning(type, value);

    const colorClasses = {
        gray: "bg-gray-100 text-gray-700 border-gray-300",
        blue: "bg-blue-100 text-blue-700 border-blue-300",
        amber: "bg-amber-100 text-amber-700 border-amber-300",
        green: "bg-green-100 text-green-700 border-green-300"
    };

    if (compact) {
        return (
            <div className="inline-flex items-center gap-2">
                <span className="font-mono text-sm">{typeName} = {value.toFixed(2)}</span>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${colorClasses[interpretation.color]}`}>
                    {interpretation.label}
                </span>
            </div>
        );
    }

    return (
        <div className="effect-size-explainer bg-white border border-gray-200 rounded-lg p-4">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <ChartBarIcon className="w-5 h-5 text-gray-400" />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                    Effect Size
                </span>
            </div>

            {/* Value */}
            <div className="flex items-baseline gap-3 mb-3">
                <span className="text-2xl font-mono font-bold text-gray-900">
                    {value.toFixed(2)}
                </span>
                <span className="text-sm text-gray-500">{typeName}</span>
                <span className={`px-2 py-1 rounded text-sm font-medium uppercase ${colorClasses[interpretation.color]}`}>
                    {interpretation.label} эффект
                </span>
            </div>

            {/* Scale */}
            {showScale && THRESHOLDS[type] && (
                <div className="mb-3">
                    <div className="flex items-center h-2 bg-gray-100 rounded-full overflow-hidden">
                        {Object.entries(THRESHOLDS[type]).map(([key, config], idx, arr) => {
                            const width = 100 / arr.length;
                            const isActive = key === interpretation.key;
                            return (
                                <div
                                    key={key}
                                    className={`h-full ${isActive ? `bg-${config.color}-500` : 'bg-gray-200'}`}
                                    style={{ width: `${width}%` }}
                                />
                            );
                        })}
                    </div>
                    <div className="flex justify-between text-xs text-gray-400 mt-1">
                        {Object.entries(THRESHOLDS[type]).map(([key, config]) => (
                            <span key={key} className={key === interpretation.key ? 'font-bold text-gray-700' : ''}>
                                {config.label}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Practical meaning */}
            {practicalMeaning && (
                <div className="text-sm text-gray-600 mb-3">
                    💡 <strong>Практически:</strong> {practicalMeaning}
                </div>
            )}

            {/* Confidence Interval */}
            {ci && ci.length === 2 && (
                <div className="text-sm">
                    <span className="text-gray-500">95% CI:</span>
                    <span className="font-mono ml-2">[{ci[0].toFixed(2)}, {ci[1].toFixed(2)}]</span>
                    {ciIncludesZero ? (
                        <span className="ml-2 text-amber-600">⚠️ Включает 0</span>
                    ) : (
                        <span className="ml-2 text-green-600">✓ Не включает 0</span>
                    )}
                </div>
            )}
        </div>
    );
}
