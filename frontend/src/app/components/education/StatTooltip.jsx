/**
 * Statistical Tooltip Component.
 * 
 * Provides contextual explanations for statistical terms.
 * Shows definition on hover with optional depth levels.
 * 
 * Usage:
 *   <StatTooltip term="p_value" level="junior">
 *     <span>P-value: 0.023</span>
 *   </StatTooltip>
 */

import React, { useState, useRef, useEffect } from 'react';
import { InformationCircleIcon } from '@heroicons/react/24/outline';
import { getKnowledgeTerm } from '../../../lib/api';

// Knowledge base (inline for now, later can fetch from API)
const STAT_KNOWLEDGE = {
    p_value: {
        term: "P-value",
        term_ru: "P-значение",
        definitions: {
            junior: "Чем меньше p-value, тем сильнее доказательства против нулевой гипотезы. Сравнивают с 0.05.",
            mid: "Вероятность получить такой же или более экстремальный результат, если H0 верна.",
            senior: "P(data|H0). При большом n даже trivial эффекты дают p < 0.05. Смотрите effect size."
        },
        emoji: "📊",
        warnings: ["p < 0.05 ≠ практическая значимость", "Смотрите effect size!"]
    },
    effect_size: {
        term: "Effect Size",
        term_ru: "Размер эффекта",
        definitions: {
            junior: "Насколько большой эффект мы нашли. Не зависит от размера выборки.",
            mid: "Стандартизированная мера силы эффекта. Cohen's d = разница средних / SD.",
            senior: "Позволяет сравнивать результаты между исследованиями. Для метаанализа важнее p-value."
        },
        emoji: "📏"
    },
    power: {
        term: "Power",
        term_ru: "Мощность теста",
        definitions: {
            junior: "Вероятность найти эффект, если он существует. Рекомендуется ≥ 80%.",
            mid: "Power = 1 - β. При power 80% — 20% шанс пропустить реальный эффект.",
            senior: "Зависит от n, effect size, alpha. Post-hoc power analysis имеет ограничения."
        },
        emoji: "⚡"
    },
    confidence_interval: {
        term: "Confidence Interval",
        term_ru: "Доверительный интервал",
        definitions: {
            junior: "Диапазон, в котором с 95% уверенностью находится истинное значение.",
            mid: "При повторении 100 раз, ~95 CI захватят истинное значение.",
            senior: "Если CI не включает 0 — эффект значим. CI для effect size важнее CI для mean."
        },
        emoji: "📐"
    },
    cohens_d: {
        term: "Cohen's d",
        term_ru: "d Коэна",
        definitions: {
            junior: "Разница между группами в единицах стандартного отклонения.",
            mid: "d = (M1 - M2) / SD. Интерпретация: 0.2 малый, 0.5 средний, 0.8 большой.",
            senior: "Hedges' g — коррекция для малых выборок. Glass's Δ — когда SD групп различаются."
        },
        emoji: "📊"
    },
    alpha: {
        term: "Alpha",
        term_ru: "Уровень значимости",
        definitions: {
            junior: "Порог для решения. Обычно 0.05 (5%). Если p < alpha — результат значимый.",
            mid: "Вероятность ошибки I рода. При alpha 0.05 в 5% случаев отвергаем верную H0.",
            senior: "При множественных сравнениях — коррекция Bonferroni/FDR. Иногда alpha = 0.005."
        },
        emoji: "🎯"
    },
    p_value_adj: {
        term: "Adjusted p-value",
        term_ru: "Поправленное p-значение",
        definitions: {
            junior: "p после поправки за множественные сравнения (Bonferroni/FDR и т.п.). Его сравнивают с alpha.",
            mid: "Корректирует инфляцию ложноположительных находок при множественных тестах.",
            senior: "Интерпретация зависит от метода (FWER vs FDR). Смотрите, что именно контролируется."
        },
        emoji: "🧮",
        warnings: ["Всегда указывайте метод поправки", "Не смешивайте p(raw) и p(adj) в одной интерпретации"]
    },
    multiplicity_correction: {
        term: "Multiplicity correction",
        term_ru: "Поправка за множественные сравнения",
        definitions: {
            junior: "Когда тестов много, часть результатов станет значимой случайно. Поправка это контролирует.",
            mid: "Bonferroni/Holm контролируют вероятность хотя бы одной ложной находки (FWER). FDR(BH) контролирует долю ложных находок среди значимых.",
            senior: "FWER строже и снижает мощность; FDR мягче и подходит для скрининга/омики. Выбор — часть дизайна анализа."
        },
        emoji: "🧷",
        warnings: ["Поправка выбирается до анализа", "Уточняйте: контроль FWER или FDR"]
    },
    post_hoc: {
        term: "Post-hoc",
        term_ru: "Пост‑хок сравнения",
        definitions: {
            junior: "Если общий тест (ANOVA/Краскел‑Уоллис) значим, пост‑хок показывает, какие пары групп различаются.",
            mid: "Пост‑хок — набор парных сравнений с коррекцией множественности.",
            senior: "Лучше планировать контрасты заранее; пост‑хок увеличивает число тестов и требует корректной поправки."
        },
        emoji: "🔎"
    },
    post_hoc_correction: {
        term: "Post-hoc correction",
        term_ru: "Поправка в пост‑хок",
        definitions: {
            junior: "Пост‑хок делает много парных тестов, поэтому p нужно корректировать.",
            mid: "Метод поправки определяет, что контролируем: FWER (Bonferroni/Holm) или FDR (BH/BY/BKY).",
            senior: "Старайтесь согласовать поправку пост‑хок и общую стратегию множественности в исследовании."
        },
        emoji: "🧷"
    },
    post_hoc_dunn: {
        term: "Dunn",
        term_ru: "Dunn (пост‑хок)",
        definitions: {
            junior: "Пост‑хок для Краскела‑Уоллиса: сравнивает ранги между парами групп.",
            mid: "Непараметрические парные сравнения рангов с последующей поправкой.",
            senior: "Хорош для не-нормальных распределений; мощность зависит от структуры данных и размера выборки."
        },
        emoji: "📎"
    },
    post_hoc_tukey: {
        term: "Tukey HSD",
        term_ru: "Tukey HSD (пост‑хок)",
        definitions: {
            junior: "Классический пост‑хок после ANOVA: сравнивает все пары средних.",
            mid: "Контролирует FWER для всех парных сравнений (при выполнении предпосылок).",
            senior: "Предполагает нормальность/однородность дисперсий; при гетероскедастичности лучше Games–Howell."
        },
        emoji: "📐"
    },
    post_hoc_games_howell: {
        term: "Games–Howell",
        term_ru: "Games–Howell (пост‑хок)",
        definitions: {
            junior: "Пост‑хок для сравнения средних, когда дисперсии могут быть разными.",
            mid: "Альтернатива Tukey при неоднородности дисперсий и разных n.",
            senior: "Часто используется с Welch ANOVA; осторожно интерпретируйте при малых n."
        },
        emoji: "🧪"
    }
};

export default function StatTooltip({
    term,
    level = 'junior',
    position = 'top',
    showIcon = true,
    children
}) {
    const [isVisible, setIsVisible] = useState(false);
    const [coords, setCoords] = useState({ top: 0, left: 0 });
    const [remoteKnowledge, setRemoteKnowledge] = useState(null);
    const [remoteLevel, setRemoteLevel] = useState(null);
    const [remoteErrorTerm, setRemoteErrorTerm] = useState(null);
    const triggerRef = useRef(null);
    const tooltipRef = useRef(null);

    const fallbackKnowledge = term ? STAT_KNOWLEDGE[term] : null;

    useEffect(() => {
        if (!isVisible || !term) return;
        if (remoteKnowledge && remoteKnowledge._term === term && remoteLevel === level) return;
        if (remoteErrorTerm === term && fallbackKnowledge) return;

        const controller = new AbortController();

        (async () => {
            try {
                const payload = await getKnowledgeTerm(term, level);
                if (controller.signal.aborted) return;
                setRemoteKnowledge({ ...payload, _term: term });
                setRemoteLevel(level);
                setRemoteErrorTerm(null);
            } catch {
                if (controller.signal.aborted) return;
                setRemoteErrorTerm(term);
            }
        })();

        return () => controller.abort();
    }, [fallbackKnowledge, isVisible, level, remoteErrorTerm, remoteKnowledge, remoteLevel, term]);

    useEffect(() => {
        if (isVisible && triggerRef.current && tooltipRef.current) {
            const triggerRect = triggerRef.current.getBoundingClientRect();
            const tooltipRect = tooltipRef.current.getBoundingClientRect();

            let top, left;

            switch (position) {
                case 'bottom':
                    top = triggerRect.bottom + 8;
                    left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
                    break;
                case 'left':
                    top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2;
                    left = triggerRect.left - tooltipRect.width - 8;
                    break;
                case 'right':
                    top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2;
                    left = triggerRect.right + 8;
                    break;
                default: // top
                    top = triggerRect.top - tooltipRect.height - 8;
                    left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
            }

            // Keep within viewport
            left = Math.max(8, Math.min(left, window.innerWidth - tooltipRect.width - 8));
            top = Math.max(8, top);

            setCoords({ top, left });
        }
    }, [isVisible, position]);

    if (!term) {
        return children;
    }

    const activeKnowledge = remoteKnowledge || fallbackKnowledge;
    if (!activeKnowledge) {
        return children;
    }

    const definition = remoteKnowledge
        ? remoteKnowledge.definition
        : (fallbackKnowledge.definitions[level] || fallbackKnowledge.definitions.junior);

    const warnings = remoteKnowledge?.common_mistakes || fallbackKnowledge?.warnings || [];

    return (
        <span className="stat-tooltip-wrapper inline-flex items-center gap-1">
            <span
                ref={triggerRef}
                onMouseEnter={() => setIsVisible(true)}
                onMouseLeave={() => setIsVisible(false)}
                className="cursor-help"
            >
                {children}
                {showIcon && (
                    <InformationCircleIcon className="w-4 h-4 text-gray-400 hover:text-gray-600 inline-block ml-1" />
                )}
            </span>

            {isVisible && (
                <div
                    ref={tooltipRef}
                    className="stat-tooltip fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs"
                    style={{ top: coords.top, left: coords.left }}
                >
                    {/* Header */}
                    <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">{activeKnowledge.emoji}</span>
                        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                            {activeKnowledge.term_ru}
                        </span>
                    </div>

                    {/* Definition */}
                    <p className="text-sm text-gray-700 leading-relaxed">
                        {definition}
                    </p>

                    {/* Warnings */}
                    {warnings.length > 0 && (
                        <div className="mt-3 bg-amber-50 border-l-2 border-amber-400 px-3 py-2 text-xs text-amber-800">
                            <strong>⚠️ Важно:</strong>
                            <ul className="mt-1 space-y-0.5">
                                {warnings.map((w, i) => (
                                    <li key={i}>• {w}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Level indicator */}
                    <div className="mt-3 flex items-center gap-1 text-xs text-gray-400">
                        <span>Уровень:</span>
                        <span className={`px-1.5 py-0.5 rounded text-xs ${level === 'junior' ? 'bg-green-100 text-green-700' :
                                level === 'mid' ? 'bg-blue-100 text-blue-700' :
                                    'bg-purple-100 text-purple-700'
                            }`}>
                            {level === 'junior' ? 'базовый' : level === 'mid' ? 'средний' : 'продвинутый'}
                        </span>
                    </div>
                </div>
            )}
        </span>
    );
}
