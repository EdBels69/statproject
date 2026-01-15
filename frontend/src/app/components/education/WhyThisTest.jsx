/**
 * Why This Test Component.
 * 
 * Explains why a particular statistical test was chosen based on data characteristics.
 * Shows:
 * - Data profile matching
 * - Assumptions status
 * - Alternative tests if needed
 * 
 * Usage:
 *   <WhyThisTest 
 *     testId="t_test_ind" 
 *     dataProfile={{ n_groups: 2, normality: true, homogeneity: false }}
 *   />
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
    LightBulbIcon,
    CheckCircleIcon,
    XCircleIcon,
    ChevronDownIcon,
    ChevronUpIcon
} from '@heroicons/react/24/outline';
import { getKnowledgeTest } from '../../../lib/api';

// Test knowledge base
const TEST_KNOWLEDGE = {
    t_test_ind: {
        name: "Independent t-test",
        name_ru: "T-test для независимых выборок",
        emoji: "📊",
        when_to_use: [
            "2 независимые группы",
            "Непрерывная зависимая переменная",
            "Нормальное распределение (или n > 30)",
            "Примерно равные дисперсии"
        ],
        why_it_works: {
            junior: "Сравнивает средние двух групп и проверяет, значима ли разница.",
            mid: "Использует t-распределение. При n → ∞ приближается к z-test благодаря ЦПТ.",
            senior: "Pooled variance estimate предполагает σ₁ = σ₂. При нарушении — Welch's correction."
        },
        assumptions: ["normality", "homogeneity", "independence"],
        alternatives: {
            non_normal: { test: "mann_whitney", reason: "если данные ненормальные" },
            unequal_variance: { test: "welch_t_test", reason: "если дисперсии различаются" }
        }
    },
    welch_t_test: {
        name: "Welch's t-test",
        name_ru: "T-test Уэлча",
        emoji: "📊",
        when_to_use: [
            "2 независимые группы",
            "Дисперсии могут различаться",
            "Рекомендуется по умолчанию вместо Student's t-test"
        ],
        why_it_works: {
            junior: "Как t-test, но не требует равных дисперсий.",
            mid: "Использует Satterthwaite approximation для degrees of freedom."
        },
        assumptions: ["normality", "independence"]
    },
    mann_whitney: {
        name: "Mann-Whitney U",
        name_ru: "U-тест Манна-Уитни",
        emoji: "📊",
        when_to_use: [
            "2 независимые группы",
            "Ненормальное распределение",
            "Ordinal или skewed данные"
        ],
        why_it_works: {
            junior: "Сравнивает ранги вместо средних. Не требует нормальности.",
            mid: "Тестирует H0: P(X > Y) = 0.5."
        },
        assumptions: ["independence"]
    },
    anova: {
        name: "One-way ANOVA",
        name_ru: "Однофакторный дисперсионный анализ",
        emoji: "📈",
        when_to_use: [
            "3+ независимых групп",
            "Нормальное распределение",
            "Равные дисперсии"
        ],
        why_it_works: {
            junior: "Проверяет, есть ли различия между группами.",
            mid: "F = MS_between / MS_within."
        },
        assumptions: ["normality", "homogeneity", "independence"],
        alternatives: {
            unequal_variance: { test: "welch_anova", reason: "если дисперсии различаются" },
            non_normal: { test: "kruskal_wallis", reason: "если данные ненормальные" }
        }
    },
    kruskal_wallis: {
        name: "Kruskal-Wallis",
        name_ru: "H-тест Краскела-Уоллиса",
        emoji: "📈",
        when_to_use: [
            "3+ независимых групп",
            "Ненормальное распределение"
        ],
        why_it_works: {
            junior: "Непараметрический аналог ANOVA. Сравнивает ранги.",
            mid: "Post-hoc: Dunn's test с коррекцией."
        },
        assumptions: ["independence"]
    },
    pearson: {
        name: "Pearson correlation",
        name_ru: "Корреляция Пирсона",
        emoji: "📈",
        when_to_use: [
            "Две непрерывные переменные",
            "Линейная связь"
        ],
        assumptions: ["normality", "linearity"],
        alternatives: {
            non_linear: { test: "spearman", reason: "для нелинейных монотонных связей" }
        }
    },
    spearman: {
        name: "Spearman correlation",
        name_ru: "Корреляция Спирмена",
        emoji: "📈",
        when_to_use: [
            "Ordinal данные",
            "Ненормальное распределение",
            "Монотонная связь"
        ],
        assumptions: []
    },
    chi_square: {
        name: "Chi-squared test",
        name_ru: "Хи-квадрат",
        emoji: "📊",
        when_to_use: [
            "Две категориальные переменные",
            "Expected count ≥ 5"
        ],
        assumptions: ["independence"],
        alternatives: {
            small_sample: { test: "fisher_exact", reason: "если expected < 5" }
        }
    }
};

const ASSUMPTION_LABELS = {
    normality: { name: "Нормальность", icon: "📈" },
    homogeneity: { name: "Равенство дисперсий", icon: "⚖️" },
    independence: { name: "Независимость", icon: "🔗" },
    linearity: { name: "Линейность", icon: "📏" }
};

export default function WhyThisTest({
    testId,
    dataProfile = {},
    level = 'junior',
    defaultExpanded = false
}) {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    const [remoteTest, setRemoteTest] = useState(null);
    const [remoteLevel, setRemoteLevel] = useState(null);
    const [remoteErrorTestId, setRemoteErrorTestId] = useState(null);

    const shapiroP = dataProfile?.shapiro_p;
    const leveneP = dataProfile?.levene_p;

    const fetchParams = useMemo(() => ({ level, shapiro_p: shapiroP, levene_p: leveneP }), [level, leveneP, shapiroP]);

    useEffect(() => {
        if (!isExpanded || !testId) return;
        if (remoteTest && remoteTest.test_id === testId && remoteLevel === level) return;
        if (remoteErrorTestId === testId && TEST_KNOWLEDGE[testId]) return;

        const controller = new AbortController();

        (async () => {
            try {
                const payload = await getKnowledgeTest(testId, { ...fetchParams, signal: controller.signal });
                if (controller.signal.aborted) return;
                setRemoteTest(payload);
                setRemoteLevel(level);
                setRemoteErrorTestId(null);
            } catch {
                if (controller.signal.aborted) return;
                setRemoteErrorTestId(testId);
            }
        })();

        return () => controller.abort();
    }, [fetchParams, isExpanded, level, remoteErrorTestId, remoteLevel, remoteTest, testId]);

    const fallbackTest = testId ? TEST_KNOWLEDGE[testId] : null;
    const activeTest = remoteTest || fallbackTest;
    if (!activeTest) return null;

    const why = remoteTest
        ? (remoteTest.why_it_works || "")
        : (fallbackTest.why_it_works?.[level] || fallbackTest.why_it_works?.junior || "");

    // Check assumptions against data profile
    const assumptionChecks = remoteTest?.assumption_checks
        ? (remoteTest.assumption_checks || []).map((a) => ({
            assumption: a.assumption,
            passed: a.passed,
            note: a.note || "",
            ...ASSUMPTION_LABELS[a.assumption],
        }))
        : (activeTest.assumptions || []).map(assumption => {
            let passed = null;
            let note = "";

            if (assumption === "normality" && typeof dataProfile.shapiro_p === 'number') {
                passed = dataProfile.shapiro_p > 0.05;
                note = `Shapiro p = ${dataProfile.shapiro_p.toFixed(3)}`;
            } else if (assumption === "homogeneity" && typeof dataProfile.levene_p === 'number') {
                passed = dataProfile.levene_p > 0.05;
                note = `Levene p = ${dataProfile.levene_p.toFixed(3)}`;
            } else if (assumption === "independence") {
                passed = dataProfile.independence !== false;
                note = "Предполагается по дизайну";
            }

            return { assumption, passed, note, ...ASSUMPTION_LABELS[assumption] };
        });

    // Find violated assumptions and suggest alternatives
    const violations = assumptionChecks.filter(a => a.passed === false);
    const suggestedAlternatives = [];

    if (violations.some(v => v.assumption === "normality") && activeTest.alternatives?.non_normal) {
        suggestedAlternatives.push(activeTest.alternatives.non_normal);
    }
    if (violations.some(v => v.assumption === "homogeneity") && activeTest.alternatives?.unequal_variance) {
        suggestedAlternatives.push(activeTest.alternatives.unequal_variance);
    }

    return (
        <div className="why-this-test bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg overflow-hidden">
            {/* Header - always visible */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between p-4 text-left hover:bg-blue-100/50 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <LightBulbIcon className="w-5 h-5 text-blue-600" />
                    <span className="font-medium text-blue-900">
                        Почему {activeTest.name_ru}?
                    </span>
                </div>
                {isExpanded ? (
                    <ChevronUpIcon className="w-5 h-5 text-blue-600" />
                ) : (
                    <ChevronDownIcon className="w-5 h-5 text-blue-600" />
                )}
            </button>

            {/* Expanded content */}
            {isExpanded && (
                <div className="px-4 pb-4 space-y-4">
                    {/* Why it works */}
                    <div className="text-sm text-gray-700">
                        <strong className="text-gray-900">💡 Как это работает:</strong>
                        <p className="mt-1">{why}</p>
                    </div>

                    {/* When to use */}
                    <div className="text-sm">
                        <strong className="text-gray-900">✓ Подходит когда:</strong>
                        <ul className="mt-1 space-y-1">
                            {(activeTest.when_to_use || []).map((condition, idx) => (
                                <li key={idx} className="flex items-start gap-2 text-gray-600">
                                    <span className="text-green-500 shrink-0">•</span>
                                    {condition}
                                </li>
                            ))}
                        </ul>
                    </div>

                    {/* Assumptions check */}
                    {assumptionChecks.length > 0 && (
                        <div className="text-sm">
                            <strong className="text-gray-900">📋 Допущения:</strong>
                            <div className="mt-2 space-y-2">
                                {assumptionChecks.map(({ assumption, name, icon, passed, note }) => (
                                    <div
                                        key={assumption}
                                        className={`flex items-center gap-2 p-2 rounded ${passed === null ? 'bg-gray-100' :
                                                passed ? 'bg-green-100' : 'bg-red-100'
                                            }`}
                                    >
                                        {passed === null ? (
                                            <span className="text-gray-400">?</span>
                                        ) : passed ? (
                                            <CheckCircleIcon className="w-4 h-4 text-green-600" />
                                        ) : (
                                            <XCircleIcon className="w-4 h-4 text-red-600" />
                                        )}
                                        <span className="flex-1 text-gray-700">
                                            {icon} {name}
                                        </span>
                                        {note && (
                                            <span className="text-xs text-gray-500">{note}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Alternatives if assumptions violated */}
                    {suggestedAlternatives.length > 0 && (
                        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
                            <strong className="text-amber-800">⚠️ Рассмотрите альтернативы:</strong>
                            <ul className="mt-1 space-y-1">
                                {suggestedAlternatives.map(({ test: altTest, reason }) => (
                                    <li key={altTest} className="text-amber-700">
                                        • <strong>{TEST_KNOWLEDGE[altTest]?.name_ru || altTest}</strong> — {reason}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Level indicator */}
                    <div className="flex items-center gap-1 text-xs text-gray-400">
                        <span>Объяснение:</span>
                        <span className={`px-1.5 py-0.5 rounded ${level === 'junior' ? 'bg-green-100 text-green-700' :
                                level === 'mid' ? 'bg-blue-100 text-blue-700' :
                                    'bg-purple-100 text-purple-700'
                            }`}>
                            {level === 'junior' ? 'базовое' : level === 'mid' ? 'среднее' : 'продвинутое'}
                        </span>
                    </div>
                </div>
            )}
        </div>
    );
}
