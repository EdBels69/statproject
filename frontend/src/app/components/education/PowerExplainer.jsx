/**
 * Power Explainer Component.
 * 
 * Shows statistical power with:
 * - Visual gauge
 * - Status indicator (insufficient/adequate/high)
 * - Recommendations for improvement
 * - Sample size calculator hint
 * 
 * Usage:
 *   <PowerExplainer power={0.72} alpha={0.05} n={50} effectSize={0.5} />
 */

import React from 'react';
import { BoltIcon, ExclamationTriangleIcon, CheckCircleIcon } from '@heroicons/react/24/outline';

const POWER_THRESHOLDS = {
    critical: { max: 0.5, label: "критически низкая", color: "red", icon: ExclamationTriangleIcon },
    insufficient: { max: 0.8, label: "недостаточная", color: "amber", icon: ExclamationTriangleIcon },
    adequate: { max: 0.95, label: "адекватная", color: "green", icon: CheckCircleIcon },
    high: { min: 0.95, label: "высокая", color: "green", icon: CheckCircleIcon }
};

function getPowerStatus(power) {
    if (power < 0.5) return { ...POWER_THRESHOLDS.critical, key: "critical" };
    if (power < 0.8) return { ...POWER_THRESHOLDS.insufficient, key: "insufficient" };
    if (power < 0.95) return { ...POWER_THRESHOLDS.adequate, key: "adequate" };
    return { ...POWER_THRESHOLDS.high, key: "high" };
}

// Approximate sample size needed for 80% power
function estimateSampleSize(effectSize, targetAlpha = 0.05, targetPower = 0.8) {
    if (!effectSize || effectSize <= 0) return null;

    // Simplified formula for two-sample t-test
    // n ≈ 2 * ((z_α + z_β) / d)²
    // For α=0.05 (two-tailed), z_α ≈ 1.96
    // For power=0.8, z_β ≈ 0.84
    // Note: targetAlpha and targetPower are used for documentation, formula uses standard values
    void targetAlpha; void targetPower; // Suppress unused warnings
    const z_alpha = 1.96;
    const z_beta = 0.84;
    const n_per_group = 2 * Math.pow((z_alpha + z_beta) / effectSize, 2);

    return Math.ceil(n_per_group);
}

export default function PowerExplainer({
    power,
    alpha = 0.05,
    n,
    effectSize,
    compact = false
}) {
    if (power === null || power === undefined) {
        return null;
    }

    const status = getPowerStatus(power);
    const Icon = status.icon;
    const powerPct = (power * 100).toFixed(0);
    const missRate = ((1 - power) * 100).toFixed(0);
    const neededN = effectSize ? estimateSampleSize(effectSize, alpha, 0.8) : null;

    const colorClasses = {
        red: {
            bg: "bg-red-50",
            border: "border-red-200",
            text: "text-red-700",
            accent: "bg-red-500"
        },
        amber: {
            bg: "bg-amber-50",
            border: "border-amber-200",
            text: "text-amber-700",
            accent: "bg-amber-500"
        },
        green: {
            bg: "bg-green-50",
            border: "border-green-200",
            text: "text-green-700",
            accent: "bg-green-500"
        }
    };

    const colors = colorClasses[status.color];

    if (compact) {
        return (
            <div className={`inline-flex items-center gap-2 px-2 py-1 rounded ${colors.bg}`}>
                <BoltIcon className={`w-4 h-4 ${colors.text}`} />
                <span className="font-mono text-sm">{powerPct}%</span>
                {power < 0.8 && (
                    <span className={`text-xs ${colors.text}`}>⚠️</span>
                )}
            </div>
        );
    }

    return (
        <div className={`power-explainer border rounded-lg p-4 ${colors.bg} ${colors.border}`}>
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <BoltIcon className={`w-5 h-5 ${colors.text}`} />
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                        Мощность теста
                    </span>
                </div>
                <div className={`flex items-center gap-1 text-sm font-medium ${colors.text}`}>
                    <Icon className="w-4 h-4" />
                    {status.label}
                </div>
            </div>

            {/* Power gauge */}
            <div className="mb-3">
                <div className="flex items-baseline gap-2 mb-2">
                    <span className="text-3xl font-bold text-gray-900">{powerPct}%</span>
                    {power < 0.8 && (
                        <span className="text-sm text-gray-500">(рекомендуется ≥ 80%)</span>
                    )}
                </div>

                {/* Visual bar */}
                <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                        className={`h-full ${colors.accent} transition-all duration-300`}
                        style={{ width: `${powerPct}%` }}
                    />
                </div>

                {/* Scale markers */}
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                    <span>0%</span>
                    <span className={power >= 0.8 ? 'text-green-600 font-bold' : ''}>80%</span>
                    <span>100%</span>
                </div>
            </div>

            {/* Explanation */}
            <div className="text-sm text-gray-700 mb-3">
                💡 <strong>Что это значит:</strong>
                <p className="mt-1">
                    При реальном эффекте — <strong>{missRate}% шанс его пропустить</strong> (получить p &gt; 0.05).
                </p>
            </div>

            {/* Recommendations */}
            {power < 0.8 && (
                <div className="bg-white border border-gray-200 rounded p-3 text-sm">
                    <strong className="text-gray-900">🔧 Как улучшить?</strong>
                    <ul className="mt-2 space-y-1 text-gray-600">
                        {n && neededN && neededN > n && (
                            <li>• Увеличьте n с {n} до <strong>~{neededN}</strong> на группу</li>
                        )}
                        {!n && neededN && (
                            <li>• Для Power 80% нужно <strong>~{neededN}</strong> на группу</li>
                        )}
                        <li>• Или ищите больший effect size (более эффективное воздействие)</li>
                        <li>• Или увеличьте alpha (с 0.05 до 0.10) — но осторожно!</li>
                    </ul>
                </div>
            )}

            {/* High power note */}
            {power >= 0.95 && (
                <div className="text-sm text-gray-600">
                    ℹ️ Выборка возможно избыточна для данного effect size.
                </div>
            )}
        </div>
    );
}
