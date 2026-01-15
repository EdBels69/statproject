import React, { useState } from 'react';

const ALPHA_OPTIONS = [
    { value: 0.01, label: '0.01 (Very Strict)', description: 'Higher confidence, lower false positive rate' },
    { value: 0.05, label: '0.05 (Standard)', description: 'Most common in scientific research' },
    { value: 0.10, label: '0.10 (More Lenient)', description: 'Higher sensitivity, exploratory analysis' },
];

export default function Settings() {
    const [alpha, setAlpha] = useState(() => {
        try {
            const savedAlpha = typeof window !== 'undefined' ? localStorage.getItem('statwizard_alpha') : null;
            const parsed = savedAlpha ? Number.parseFloat(savedAlpha) : Number.NaN;
            return Number.isFinite(parsed) ? parsed : 0.05;
        } catch {
            return 0.05;
        }
    });
    const [showToast, setShowToast] = useState(false);

    const handleAlphaChange = (value) => {
        setAlpha(value);
        localStorage.setItem('statwizard_alpha', value.toString());
        setShowToast(true);
        setTimeout(() => setShowToast(false), 2000);
    };

    return (
        <div className="max-w-3xl mx-auto animate-fadeIn">
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-[color:var(--text-primary)]">Settings</h1>
                <p className="text-[color:var(--text-secondary)] mt-1">Configure your analysis preferences</p>
            </div>

            <div className="space-y-6">
                <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-6">
                    <h2 className="text-lg font-semibold text-[color:var(--text-primary)] mb-4">Significance Level (α)</h2>
                    <p className="text-sm text-[color:var(--text-secondary)] mb-6">
                        The threshold for determining statistical significance. Results with p-value &lt; α are considered statistically significant.
                    </p>

                    <div className="space-y-3">
                        {ALPHA_OPTIONS.map((option) => (
                            <label
                                key={option.value}
                                className={`relative flex items-start p-4 rounded-[2px] border cursor-pointer transition-colors ${alpha === option.value
                                    ? 'border-[color:var(--accent)] bg-[color:var(--bg-tertiary)]'
                                    : 'border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                } focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]`}
                                tabIndex={0}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        handleAlphaChange(option.value);
                                    }
                                }}
                            >
                                <input
                                    type="radio"
                                    name="alpha"
                                    value={option.value}
                                    checked={alpha === option.value}
                                    onChange={() => handleAlphaChange(option.value)}
                                    className="sr-only"
                                />
                                <div className={`w-5 h-5 rounded-[2px] border-2 flex items-center justify-center mt-0.5 mr-4 flex-shrink-0 transition-colors ${alpha === option.value
                                    ? 'border-[color:var(--accent)] bg-[color:var(--accent)]'
                                    : 'border-[color:var(--border-color)]'
                                }`}>
                                    {alpha === option.value && (
                                        <div className="w-2.5 h-2.5 rounded-[2px] bg-[color:var(--white)]"></div>
                                    )}
                                </div>
                                <div>
                                    <div className="font-semibold text-[color:var(--text-primary)]">{option.label}</div>
                                    <div className="text-sm text-[color:var(--text-secondary)] mt-0.5">{option.description}</div>
                                </div>
                            </label>
                        ))}
                    </div>
                </section>
            </div>

            {showToast && (
                <div
                    className="fixed bottom-6 right-6 bg-[color:var(--black)] text-[color:var(--white)] px-4 py-2 rounded-[2px] border border-[color:var(--black)] animate-fadeIn"
                    role="alert"
                    aria-live="polite"
                >
                    Settings saved successfully
                </div>
            )}
        </div>
    );
}
