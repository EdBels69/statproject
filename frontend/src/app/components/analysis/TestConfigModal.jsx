import React, { useState } from 'react';
import { XMarkIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import { useTranslation } from '../../../hooks/useTranslation';

// InfoTip component - defined outside to avoid recreating on each render
const InfoTip = ({ text }) => (
    <div className="group relative inline-block ml-1">
        <InformationCircleIcon className="w-4 h-4 text-[color:var(--text-muted)] cursor-help" />
        <div className="absolute z-50 hidden group-hover:block w-64 p-2 bg-[color:var(--text-primary)] text-[color:var(--white)] text-xs rounded shadow-lg -top-2 left-6">
            {text}
        </div>
    </div>
);

/**
 * Modal for fine-tuning statistical test parameters
 * Inspired by JASP/Jamovi options panels
 */
export default function TestConfigModal({
    isOpen,
    onClose,
    test,
    onApply,
    initialConfig = {}
}) {
    const { t } = useTranslation();

    // Common options for all tests
    const [alpha, setAlpha] = useState(initialConfig.alpha || 0.05);
    const [ciLevel, setCiLevel] = useState(initialConfig.ciLevel || 0.95);
    const [showEffectSize, setShowEffectSize] = useState(initialConfig.showEffectSize !== false);
    const [showCI, setShowCI] = useState(initialConfig.showCI !== false);
    const [showBayesFactor, setShowBayesFactor] = useState(initialConfig.showBayesFactor || false);

    // Post-hoc options (for ANOVA)
    const [postHocMethod, setPostHocMethod] = useState(initialConfig.postHocMethod || 'tukey');
    const [postHocCorrection, setPostHocCorrection] = useState(initialConfig.postHocCorrection || 'bonferroni');

    // Bootstrap options
    const [useBootstrap, setUseBootstrap] = useState(initialConfig.useBootstrap || false);
    const [bootstrapSamples, setBootstrapSamples] = useState(initialConfig.bootstrapSamples || 1000);

    // Alternative hypothesis (for t-tests)
    const [alternative, setAlternative] = useState(initialConfig.alternative || 'two-sided');

    // For correlation (kept for future use)
    const [correlationType] = useState(initialConfig.correlationType || 'pearson');

    // For clustering
    const [nClusters, setNClusters] = useState(initialConfig.nClusters || 3);
    const [linkageMethod, setLinkageMethod] = useState(initialConfig.linkageMethod || 'ward');

    // For factor analysis
    const [nFactors, setNFactors] = useState(initialConfig.nFactors || 'auto');
    const [rotation, setRotation] = useState(initialConfig.rotation || 'varimax');

    if (!isOpen || !test) return null;

    const testType = test?.id || '';

    // Determine which options to show based on test type
    const showPostHoc = ['anova', 'anova_welch', 'kruskal', 'anova_twoway', 'rm_anova', 'friedman'].includes(testType);
    const showAlternative = ['t_test_ind', 't_test_rel', 't_test_welch', 't_test_one', 'mann_whitney', 'wilcoxon'].includes(testType);
    const showCorrelationOptions = ['pearson', 'spearman', 'partial_correlation'].includes(testType);
    const showClusteringOptions = ['kmeans', 'hierarchical_clustering'].includes(testType);
    const showFactorOptions = ['pca', 'efa'].includes(testType);
    const showBootstrapOption = ['t_test_ind', 't_test_rel', 'pearson', 'spearman', 'anova'].includes(testType);

    const handleApply = () => {
        onApply({
            alpha,
            ciLevel,
            showEffectSize,
            showCI,
            showBayesFactor,
            postHocMethod: showPostHoc ? postHocMethod : undefined,
            postHocCorrection: showPostHoc ? postHocCorrection : undefined,
            useBootstrap,
            bootstrapSamples: useBootstrap ? bootstrapSamples : undefined,
            alternative: showAlternative ? alternative : undefined,
            correlationType: showCorrelationOptions ? correlationType : undefined,
            nClusters: showClusteringOptions ? nClusters : undefined,
            linkageMethod: showClusteringOptions ? linkageMethod : undefined,
            nFactors: showFactorOptions ? nFactors : undefined,
            rotation: showFactorOptions ? rotation : undefined
        });
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-[color:var(--white)] rounded-lg shadow-xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-[color:var(--border-color)]">
                    <div>
                        <h2 className="text-lg font-bold text-[color:var(--text-primary)]">
                            {t('test_options') || 'Настройки теста'}
                        </h2>
                        <p className="text-sm text-[color:var(--text-muted)]">{test.name}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-[color:var(--bg-secondary)] rounded">
                        <XMarkIcon className="w-5 h-5" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {/* === COMMON OPTIONS === */}
                    <section>
                        <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3 flex items-center">
                            Общие настройки
                            <InfoTip text="Параметры, применимые к большинству статистических тестов" />
                        </h3>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                    Уровень α (значимости)
                                    <InfoTip text="Вероятность ошибки I рода. Стандарт: 0.05. Для множественных сравнений используйте 0.01." />
                                </label>
                                <select
                                    value={alpha}
                                    onChange={(e) => setAlpha(parseFloat(e.target.value))}
                                    className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                >
                                    <option value={0.001}>0.001 (очень строгий)</option>
                                    <option value={0.01}>0.01 (строгий)</option>
                                    <option value={0.05}>0.05 (стандарт)</option>
                                    <option value={0.1}>0.1 (либеральный)</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                    Доверительный интервал
                                    <InfoTip text="Уровень доверия для интервальных оценок. 95% — стандарт, 99% — для публикаций в топ-журналах." />
                                </label>
                                <select
                                    value={ciLevel}
                                    onChange={(e) => setCiLevel(parseFloat(e.target.value))}
                                    className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                >
                                    <option value={0.90}>90%</option>
                                    <option value={0.95}>95% (стандарт)</option>
                                    <option value={0.99}>99%</option>
                                </select>
                            </div>
                        </div>

                        <div className="mt-4 space-y-2">
                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={showEffectSize}
                                    onChange={(e) => setShowEffectSize(e.target.checked)}
                                    className="rounded border-[color:var(--border-color)]"
                                />
                                <span className="text-sm">Показать размер эффекта</span>
                                <InfoTip text="Cohen's d, η², r — показывают практическую значимость результата, не только статистическую." />
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={showCI}
                                    onChange={(e) => setShowCI(e.target.checked)}
                                    className="rounded border-[color:var(--border-color)]"
                                />
                                <span className="text-sm">Показать доверительные интервалы</span>
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={showBayesFactor}
                                    onChange={(e) => setShowBayesFactor(e.target.checked)}
                                    className="rounded border-[color:var(--border-color)]"
                                />
                                <span className="text-sm">Показать Bayes Factor (BF₁₀)</span>
                                <InfoTip text="Байесовская альтернатива p-value. Показывает силу доказательств в пользу гипотезы." />
                            </label>
                        </div>
                    </section>

                    {/* === ALTERNATIVE HYPOTHESIS (for t-tests) === */}
                    {showAlternative && (
                        <section>
                            <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3 flex items-center">
                                Альтернативная гипотеза
                                <InfoTip text="Двусторонняя: проверяем отличие в любую сторону (A ≠ B). Односторонняя: проверяем только в одну сторону (A > B или A < B). Односторонний тест имеет бо́льшую мощность (легче найти эффект), но его можно использовать только если вы ЗАРАНЕЕ знаете направление эффекта из теории или предыдущих исследований." />
                            </h3>

                            <div className="space-y-2">
                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="radio"
                                        name="alternative"
                                        value="two-sided"
                                        checked={alternative === 'two-sided'}
                                        onChange={(e) => setAlternative(e.target.value)}
                                    />
                                    <span className="text-sm">Двусторонняя (≠)</span>
                                    <span className="text-xs text-[color:var(--text-muted)]">— стандарт</span>
                                </label>

                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="radio"
                                        name="alternative"
                                        value="greater"
                                        checked={alternative === 'greater'}
                                        onChange={(e) => setAlternative(e.target.value)}
                                    />
                                    <span className="text-sm">Односторонняя ({">"}) — группа 1 {">"} группа 2</span>
                                </label>

                                <label className="flex items-center gap-2 cursor-pointer">
                                    <input
                                        type="radio"
                                        name="alternative"
                                        value="less"
                                        checked={alternative === 'less'}
                                        onChange={(e) => setAlternative(e.target.value)}
                                    />
                                    <span className="text-sm">Односторонняя ({"<"}) — группа 1 {"<"} группа 2</span>
                                </label>
                            </div>
                        </section>
                    )}

                    {/* === POST-HOC OPTIONS (for ANOVA) === */}
                    {showPostHoc && (
                        <section>
                            <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3 flex items-center">
                                Post-hoc анализ
                                <InfoTip text="Попарные сравнения после значимого ANOVA. Нужны для определения, какие группы отличаются." />
                            </h3>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                        Метод сравнения
                                    </label>
                                    <select
                                        value={postHocMethod}
                                        onChange={(e) => setPostHocMethod(e.target.value)}
                                        className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                    >
                                        <option value="tukey">Tukey HSD (стандарт)</option>
                                        <option value="games_howell">Games-Howell (неравные дисперсии)</option>
                                        <option value="scheffe">Scheffé (консервативный)</option>
                                        <option value="dunnett">Dunnett (сравнение с контролем)</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                        Коррекция p-value
                                    </label>
                                    <select
                                        value={postHocCorrection}
                                        onChange={(e) => setPostHocCorrection(e.target.value)}
                                        className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                    >
                                        <option value="bonferroni">Bonferroni (строгий)</option>
                                        <option value="holm">Holm (менее строгий)</option>
                                        <option value="fdr_bh">Benjamini-Hochberg FDR</option>
                                        <option value="none">Без коррекции</option>
                                    </select>
                                </div>
                            </div>
                        </section>
                    )}

                    {/* === CLUSTERING OPTIONS === */}
                    {showClusteringOptions && (
                        <section>
                            <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3">
                                Настройки кластеризации
                            </h3>

                            <div className="grid grid-cols-2 gap-4">
                                {testType === 'kmeans' && (
                                    <div>
                                        <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                            Число кластеров (K)
                                            <InfoTip text="Используйте метод локтя или силуэт для выбора оптимального K." />
                                        </label>
                                        <input
                                            type="number"
                                            min={2}
                                            max={20}
                                            value={nClusters}
                                            onChange={(e) => setNClusters(parseInt(e.target.value))}
                                            className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                        />
                                    </div>
                                )}

                                {testType === 'hierarchical_clustering' && (
                                    <div>
                                        <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                            Метод связи
                                        </label>
                                        <select
                                            value={linkageMethod}
                                            onChange={(e) => setLinkageMethod(e.target.value)}
                                            className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                        >
                                            <option value="ward">Ward (минимизация дисперсии)</option>
                                            <option value="complete">Complete (максимальное расстояние)</option>
                                            <option value="average">Average (UPGMA)</option>
                                            <option value="single">Single (минимальное расстояние)</option>
                                        </select>
                                    </div>
                                )}
                            </div>
                        </section>
                    )}

                    {/* === FACTOR ANALYSIS OPTIONS === */}
                    {showFactorOptions && (
                        <section>
                            <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3">
                                Настройки факторного анализа
                            </h3>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                        Число факторов
                                        <InfoTip text="'Авто' использует критерий Кайзера (eigenvalue > 1)." />
                                    </label>
                                    <select
                                        value={nFactors}
                                        onChange={(e) => setNFactors(e.target.value)}
                                        className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                    >
                                        <option value="auto">Авто (Kaiser)</option>
                                        <option value="1">1</option>
                                        <option value="2">2</option>
                                        <option value="3">3</option>
                                        <option value="4">4</option>
                                        <option value="5">5</option>
                                    </select>
                                </div>

                                {testType === 'efa' && (
                                    <div>
                                        <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                            Метод вращения
                                            <InfoTip text="Varimax — для независимых факторов. Oblimin — если факторы коррелируют." />
                                        </label>
                                        <select
                                            value={rotation}
                                            onChange={(e) => setRotation(e.target.value)}
                                            className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                        >
                                            <option value="varimax">Varimax (ортогональное)</option>
                                            <option value="oblimin">Oblimin (косоугольное)</option>
                                            <option value="promax">Promax</option>
                                            <option value="none">Без вращения</option>
                                        </select>
                                    </div>
                                )}
                            </div>
                        </section>
                    )}

                    {/* === BOOTSTRAP OPTIONS === */}
                    {showBootstrapOption && (
                        <section>
                            <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3 flex items-center">
                                Bootstrap
                                <InfoTip text="Непараметрический метод для оценки доверительных интервалов. Полезен при малых выборках или нарушении нормальности." />
                            </h3>

                            <label className="flex items-center gap-2 cursor-pointer mb-3">
                                <input
                                    type="checkbox"
                                    checked={useBootstrap}
                                    onChange={(e) => setUseBootstrap(e.target.checked)}
                                    className="rounded border-[color:var(--border-color)]"
                                />
                                <span className="text-sm">Использовать bootstrap для CI</span>
                            </label>

                            {useBootstrap && (
                                <div className="w-48">
                                    <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">
                                        Число итераций
                                    </label>
                                    <select
                                        value={bootstrapSamples}
                                        onChange={(e) => setBootstrapSamples(parseInt(e.target.value))}
                                        className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded text-sm"
                                    >
                                        <option value={500}>500 (быстро)</option>
                                        <option value={1000}>1000 (стандарт)</option>
                                        <option value={5000}>5000 (точнее)</option>
                                        <option value={10000}>10000 (для публикации)</option>
                                    </select>
                                </div>
                            )}
                        </section>
                    )}
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                    >
                        {t('cancel') || 'Отмена'}
                    </button>
                    <button
                        onClick={handleApply}
                        className="px-4 py-2 text-sm font-semibold bg-[color:var(--accent)] text-white rounded hover:opacity-90"
                    >
                        {t('apply') || 'Применить'}
                    </button>
                </div>
            </div>
        </div>
    );
}
