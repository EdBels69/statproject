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
    mcnemar: {
        name: "McNemar test",
        name_ru: "Тест Мак-Немара",
        emoji: "🧷",
        when_to_use: [
            "Парные бинарные данные (до/после)",
            "Одна и та же группа субъектов",
            "Таблица 2×2 (успех/неуспех)"
        ],
        why_it_works: {
            junior: "Проверяет, изменились ли доли между двумя связанными измерениями (до/после).",
            mid: "Смотрит только на несогласованные пары (01 и 10) и тестирует их асимметрию."
        },
        assumptions: ["independence"]
    },
    cochran_q: {
        name: "Cochran's Q",
        name_ru: "Q-тест Кохрана",
        emoji: "🧷",
        when_to_use: [
            "Парные бинарные данные",
            "3+ условий/временных точек",
            "Одна и та же группа субъектов"
        ],
        why_it_works: {
            junior: "Проверяет, одинаковы ли доли успеха во всех условиях у одних и тех же субъектов.",
            mid: "Непараметрическое расширение Мак-Немара на 3+ связанных измерений (бинарный исход)."
        },
        assumptions: ["independence"],
        alternatives: {
            non_normal: { test: "cochran_q", reason: "подходит по умолчанию для бинарных повторных измерений" }
        }
    },
    cochran: {
        name: "Cochran's Q",
        name_ru: "Q-тест Кохрана",
        emoji: "🧷",
        when_to_use: [
            "Парные бинарные данные",
            "3+ условий/временных точек",
            "Одна и та же группа субъектов"
        ],
        why_it_works: {
            junior: "Проверяет, одинаковы ли доли успеха во всех условиях у одних и тех же субъектов.",
            mid: "Непараметрическое расширение Мак-Немара на 3+ связанных измерений (бинарный исход)."
        },
        assumptions: ["independence"]
    },
    point_biserial: {
        name: "Point-biserial correlation",
        name_ru: "Точечно-бисериальная корреляция",
        emoji: "📈",
        when_to_use: [
            "Одна бинарная переменная (0/1)",
            "Одна непрерывная переменная",
            "Нужно оценить связь как корреляцию"
        ],
        why_it_works: {
            junior: "Это корреляция между 0/1 и числом: показывает направление и силу связи.",
            mid: "Эквивалентна t-test для независимых групп, но в корреляционной форме (r)."
        },
        assumptions: ["normality", "independence"]
    },
    partial_correlation: {
        name: "Partial correlation",
        name_ru: "Частная корреляция",
        emoji: "📈",
        when_to_use: [
            "Нужно связь X и Y при контроле Z",
            "Есть потенциальная смешивающая переменная",
            "Интересует чистый эффект связи"
        ],
        why_it_works: {
            junior: "Убирает влияние Z и оценивает оставшуюся связь между X и Y.",
            mid: "Корреляция между остатками X~Z и Y~Z (после регрессии на Z)."
        },
        assumptions: ["linearity", "independence"]
    },
    bland_altman: {
        name: "Bland–Altman analysis",
        name_ru: "Анализ Бланда—Олтмана",
        emoji: "🧷",
        when_to_use: [
            "Нужно оценить согласие двух методов измерения",
            "Обе переменные измеряют одно и то же в одних и тех же объектах",
            "Важна не корреляция, а величина расхождений"
        ],
        why_it_works: {
            junior: "Показывает систематическое смещение (среднюю разницу) и диапазон, в котором лежит большинство расхождений. Если пределы узкие и приемлемые по смыслу задачи — методы можно считать согласованными.",
            mid: "Официально: метод оценки согласия двух количественных измерений через график разностей (A−B) от среднего ((A+B)/2) и расчёт пределов согласия (mean difference ± 1.96·SD differences)."
        },
        assumptions: ["normality", "independence"],
        alternatives: {
            non_normal: { test: "icc", reason: "если нужна численная оценка согласия или разности не близки к нормальным" }
        }
    },
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
            unequal_variance: { test: "t_test_welch", reason: "если дисперсии различаются" }
        }
    },
    t_test_welch: {
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
    t_test_rel: {
        name: "Paired t-test",
        name_ru: "Парный t-test",
        emoji: "📊",
        when_to_use: [
            "Две связанные выборки (до/после)",
            "Непрерывная переменная",
            "Нормальность разностей (или n > 30)"
        ],
        why_it_works: {
            junior: "Сравнивает среднее значение разностей внутри пары (до/после).",
            mid: "Работает с разностями: H0: mean(diff)=0."
        },
        assumptions: ["normality", "independence"],
        alternatives: {
            non_normal: { test: "wilcoxon", reason: "если разности ненормальные" }
        }
    },
    wilcoxon: {
        name: "Wilcoxon signed-rank",
        name_ru: "Критерий Вилкоксона (связанные)",
        emoji: "📊",
        when_to_use: [
            "Две связанные выборки (до/после)",
            "Ненормальные разности",
            "Ordinal или skewed данные"
        ],
        why_it_works: {
            junior: "Сравнивает ранги разностей, не требуя нормальности.",
            mid: "Тестирует симметрию распределения разностей вокруг 0."
        },
        assumptions: ["independence"]
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
            non_normal: { test: "kruskal", reason: "если данные сильно ненормальные/выбросы" }
        }
    },
    anova_twoway: {
        name: "Two-way ANOVA",
        name_ru: "Двухфакторный дисперсионный анализ",
        emoji: "📐",
        when_to_use: [
            "Два фактора (A и B)",
            "Непрерывная зависимая переменная",
            "Интерес к главным эффектам и взаимодействию (A×B)",
            "Нормальность остатков и независимость наблюдений"
        ],
        why_it_works: {
            junior: "Проверяет, влияет ли каждый фактор на исход, и есть ли взаимодействие между факторами.",
            mid: "Разбивает вариацию на компоненты: фактор A, фактор B, взаимодействие A×B и ошибка."
        },
        assumptions: ["normality", "homogeneity", "independence"],
        alternatives: {
            non_normal: { test: "kruskal", reason: "если распределения сильно ненормальные" }
        }
    },
    kruskal: {
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
    rm_anova: {
        name: "Repeated-measures ANOVA",
        name_ru: "RM-ANOVA (повторные измерения)",
        emoji: "🧷",
        when_to_use: [
            "2+ связанных измерения (повторные измерения)",
            "Непрерывная переменная",
            "Одна группа субъектов, несколько условий/временных точек"
        ],
        why_it_works: {
            junior: "Сравнивает средние между условиями внутри одних и тех же субъектов.",
            mid: "Моделирует вариацию внутри субъекта и проверяет эффект условия (времени)."
        },
        assumptions: ["normality", "independence"],
        alternatives: {
            non_normal: { test: "friedman", reason: "если нормальность сомнительна" }
        }
    },
    friedman: {
        name: "Friedman test",
        name_ru: "Тест Фридмана",
        emoji: "🧷",
        when_to_use: [
            "3+ связанных измерения (повторные измерения)",
            "Ненормальное распределение",
            "Одна группа субъектов, несколько условий/временных точек"
        ],
        why_it_works: {
            junior: "Сравнивает условия по рангам внутри каждого субъекта.",
            mid: "Непараметрический аналог RM-ANOVA: тестирует различия медианных рангов между условиями."
        },
        assumptions: ["independence"],
        alternatives: {
            non_normal: { test: "friedman", reason: "подходит по умолчанию при нарушении нормальности" }
        }
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
            small_sample: { test: "fisher", reason: "если expected < 5" }
        }
    },
    fisher: {
        name: "Fisher's exact test",
        name_ru: "Точный тест Фишера",
        emoji: "📊",
        when_to_use: [
            "Две категориальные переменные (2×2 или небольшие таблицы)",
            "Малые выборки",
            "Expected count < 5"
        ],
        why_it_works: {
            junior: "Считает точную вероятность наблюдать такую таблицу при отсутствии связи.",
            mid: "Точный тест на гипергеометрическом распределении без асимптотик."
        },
        assumptions: ["independence"]
    },
    clustered_correlation: {
        name: "Clustered correlation",
        name_ru: "Кластерная корреляция",
        emoji: "📈",
        when_to_use: [
            "Много переменных для корреляций",
            "Нужно устойчивее к структуре данных",
            "Кластеры/группы наблюдений (например, повторные измерения)"
        ],
        why_it_works: {
            junior: "Считает связи между переменными и группирует/суммирует результаты по правилам.",
            mid: "Учитывает структуру данных через агрегацию/кластеризацию признаков перед выводом."
        },
        assumptions: []
    },
    linear_regression: {
        name: "Linear regression",
        name_ru: "Линейная регрессия",
        emoji: "📐",
        when_to_use: [
            "Непрерывная зависимая переменная",
            "Линейная связь предикторов с исходом",
            "Интерпретация эффектов (коэффициенты)"
        ],
        why_it_works: {
            junior: "Подбирает прямую/плоскость, которая лучше всего объясняет исход.",
            mid: "Оценивает коэффициенты через минимизацию суммы квадратов ошибок."
        },
        assumptions: ["linearity", "independence", "normality"]
    },
    logistic_regression: {
        name: "Logistic regression",
        name_ru: "Логистическая регрессия",
        emoji: "📐",
        when_to_use: [
            "Бинарный исход (0/1)",
            "Нужны odds ratio и контроль ковариат",
            "Предсказание вероятности события"
        ],
        why_it_works: {
            junior: "Моделирует вероятность события через S-образную кривую.",
            mid: "Оценивает параметры максимизацией правдоподобия (logit link)."
        },
        assumptions: ["independence"]
    },
    mixed_model: {
        name: "Linear mixed model",
        name_ru: "Смешанная модель (LMM)",
        emoji: "🧩",
        when_to_use: [
            "Повторные измерения/иерархические данные",
            "Есть случайные эффекты (субъект/центр/партия)",
            "Нужна гибкость по пропускам и дизайну"
        ],
        why_it_works: {
            junior: "Добавляет случайные эффекты, чтобы учитывать зависимость внутри групп.",
            mid: "Разделяет фиксированные и случайные эффекты, оценивая дисперсионные компоненты."
        },
        assumptions: ["independence", "normality"]
    },
    survival_km: {
        name: "Kaplan–Meier",
        name_ru: "Выживаемость (Kaplan–Meier)",
        emoji: "⏳",
        when_to_use: [
            "Время до события",
            "Есть цензурирование",
            "Сравнение кривых выживаемости между группами"
        ],
        why_it_works: {
            junior: "Строит ступенчатую оценку вероятности выживания во времени.",
            mid: "Оценивает S(t) как произведение условных вероятностей с учетом цензуры."
        },
        assumptions: ["independence"]
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
    const safeTest = activeTest || (testId ? {
        name: String(testId),
        name_ru: String(testId),
        emoji: "🧠",
        when_to_use: [
            "Заполните поля слева и проверьте дизайн исследования",
            "Если сомневаетесь — начните с непараметрического аналога",
        ],
        why_it_works: {
            junior: "Показывает краткую справку по тесту и его допущениям.",
            mid: "Подсказывает, какие условия важны для корректного применения.",
            senior: "Нужна детальная справка — добавим в базу знаний для этого теста."
        },
        assumptions: ["independence"],
        alternatives: {}
    } : null);
    if (!safeTest) return null;

    const why = remoteTest
        ? (remoteTest.why_it_works || "")
        : (safeTest.why_it_works?.[level] || safeTest.why_it_works?.junior || "");

    // Check assumptions against data profile
    const assumptionChecks = remoteTest?.assumption_checks
        ? (remoteTest.assumption_checks || []).map((a) => ({
            assumption: a.assumption,
            passed: a.passed,
            note: a.note || "",
            ...ASSUMPTION_LABELS[a.assumption],
        }))
        : (safeTest.assumptions || []).map(assumption => {
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

    if (violations.some(v => v.assumption === "normality") && safeTest.alternatives?.non_normal) {
        suggestedAlternatives.push(safeTest.alternatives.non_normal);
    }
    if (violations.some(v => v.assumption === "homogeneity") && safeTest.alternatives?.unequal_variance) {
        suggestedAlternatives.push(safeTest.alternatives.unequal_variance);
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
                        Почему {safeTest.name_ru}?
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
                            {(safeTest.when_to_use || []).map((condition, idx) => (
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
