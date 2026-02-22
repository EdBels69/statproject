import { useState } from 'react';

export default function StepEditor({ step, index, onUpdate, onDelete }) {
    const [showOptions, setShowOptions] = useState(false);

    // Filter relevant methods based on context could be complex, 
    // for now we list common ones or just all if we are power users.
    // Ideally, we restrict by 'parametric/non-parametric' or 'comparison/correlation'.
    // Let's filter simply by context keywords in description or type for better UX, or just show all.
    // User wants "Choice". Let's show all compatible ones.

    const handleChangeMethod = (e) => {
        onUpdate(index, { ...step, method: e.target.value });
    };

    const handleParamChange = (key, value) => {
        onUpdate(index, {
            ...step,
            [key]: value // merging into step root for now as key-value args
        });
    };

    return (
        <div className="bg-[color:var(--white)] p-4 border border-[color:var(--border-color)] rounded-[2px] relative">
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                    <span className="bg-[color:var(--bg-secondary)] text-[color:var(--accent)] text-xs font-bold px-2 py-1 rounded-[2px] border border-[color:var(--border-color)]">
                        Step {index + 1}
                    </span>
                    <span className="font-medium text-[color:var(--text-secondary)]">
                        {step.type === 'compare' ? 'Comparison' : step.type}
                    </span>
                </div>
                <button
                    onClick={() => onDelete(index)}
                    className="text-[color:var(--text-muted)] hover:text-[color:var(--error)] text-sm"
                    type="button"
                >
                    &times; Remove
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Variable Config */}
                <div className="text-sm">
                    <div className="mb-1">
                        <span className="text-[color:var(--text-muted)]">Target:</span>
                        <span className="font-mono ml-2 bg-[color:var(--bg-secondary)] px-1 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)]">{step.target}</span>
                    </div>
                    {step.group && (
                        <div className="mb-1">
                            <span className="text-[color:var(--text-muted)]">Group:</span>
                            <span className="font-mono ml-2 bg-[color:var(--bg-secondary)] px-1 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)]">{step.group}</span>
                        </div>
                    )}
                </div>

                {/* Method Selection */}
                <div>
                    <label className="block text-xs font-medium text-[color:var(--text-muted)] mb-1">Statistical Method</label>
                    <select
                        value={step.method || ""}
                        onChange={handleChangeMethod}
                        className="w-full text-sm border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] text-[color:var(--text-primary)] focus:outline-none focus:border-[color:var(--accent)]"
                    >
                        <option value="">Auto (AI Recommended)</option>
                        <optgroup label="T-Tests / Means">
                            <option value="t_test_ind">Student's T-Test (Independent)</option>
                            <option value="t_test_welch">Welch's T-Test (Unequal Variance)</option>
                            <option value="t_test_rel">Paired T-Test</option>
                            <option value="t_test_one">One-Sample T-Test</option>
                        </optgroup>
                        <optgroup label="Non-Parametric">
                            <option value="mann_whitney">Mann-Whitney U</option>
                            <option value="wilcoxon">Wilcoxon Signed-Rank</option>
                            <option value="kruskal">Kruskal-Wallis</option>
                        </optgroup>
                        <optgroup label="Correlations/Proportions">
                            <option value="pearson">Pearson Correlation</option>
                            <option value="spearman">Spearman Correlation</option>
                            <option value="chi_square">Chi-Square Test</option>
                        </optgroup>
                        <optgroup label="Regression">
                            <option value="linear_regression">Linear Regression</option>
                            <option value="logistic_regression">Logistic Regression</option>
                        </optgroup>
                    </select>
                </div>
            </div>

            {/* Advanced Options Toggle */}
            <div className="mt-3">
                <button
                    onClick={() => setShowOptions(!showOptions)}
                    className="text-xs text-[color:var(--accent)] hover:opacity-80 flex items-center"
                    type="button"
                >
                    {showOptions ? '▼ Hide Options' : '▶ Advanced Options'}
                </button>

                {showOptions && (
                    <div className="mt-2 p-3 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] text-sm grid grid-cols-2 gap-3">
                        {/* One Sample Params */}
                        {step.method === 't_test_one' && (
                            <div>
                                <label className="block text-xs text-[color:var(--text-muted)]">Test Value (μ)</label>
                                <input
                                    type="number"
                                    defaultValue={step.test_value || 0}
                                    onBlur={(e) => handleParamChange('test_value', parseFloat(e.target.value))}
                                    className="mt-1 block w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] focus:outline-none focus:border-[color:var(--accent)] sm:text-sm"
                                />
                            </div>
                        )}

                        {/* General Params */}
                        <div>
                            <label className="block text-xs text-[color:var(--text-muted)]">Confidence Level</label>
                            <select
                                defaultValue={step.conf_level || 0.95}
                                onChange={(e) => handleParamChange('conf_level', parseFloat(e.target.value))}
                                className="mt-1 block w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] focus:outline-none focus:border-[color:var(--accent)] sm:text-sm"
                            >
                                <option value="0.90">90%</option>
                                <option value="0.95">95%</option>
                                <option value="0.99">99%</option>
                            </select>
                        </div>

                        <div>
                            <label className="block text-xs text-[color:var(--text-muted)]">Alternative Hypothesis</label>
                            <select
                                defaultValue={step.alternative || "two-sided"}
                                onChange={(e) => handleParamChange('alternative', e.target.value)}
                                className="mt-1 block w-full rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-primary)] focus:outline-none focus:border-[color:var(--accent)] sm:text-sm"
                            >
                                <option value="two-sided">Two-Sided (≠)</option>
                                <option value="less">Less ({'<'})</option>
                                <option value="greater">Greater ({'>'})</option>
                            </select>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
