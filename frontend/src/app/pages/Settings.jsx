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
                <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
                <p className="text-gray-500 mt-1">Configure your analysis preferences</p>
            </div>

            <div className="space-y-6">
                <section className="bg-white rounded-xl border border-gray-200 p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Significance Level (α)</h2>
                    <p className="text-sm text-gray-600 mb-6">
                        The threshold for determining statistical significance. Results with p-value &lt; α are considered statistically significant.
                    </p>

                    <div className="space-y-3">
                        {ALPHA_OPTIONS.map((option) => (
                            <label
                                key={option.value}
                                className={`relative flex items-start p-4 rounded-lg border cursor-pointer transition-all ${alpha === option.value
                                    ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500'
                                    : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50'
                                } focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-600`}
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
                                <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center mt-0.5 mr-4 flex-shrink-0 transition-colors ${alpha === option.value
                                    ? 'border-blue-600 bg-blue-600'
                                    : 'border-gray-300'
                                }`}>
                                    {alpha === option.value && (
                                        <div className="w-2.5 h-2.5 rounded-full bg-white"></div>
                                    )}
                                </div>
                                <div>
                                    <div className="font-medium text-gray-900">{option.label}</div>
                                    <div className="text-sm text-gray-500 mt-0.5">{option.description}</div>
                                </div>
                            </label>
                        ))}
                    </div>
                </section>
            </div>

            {showToast && (
                <div
                    className="fixed bottom-6 right-6 bg-gray-900 text-white px-4 py-2 rounded-lg shadow-lg animate-fadeIn"
                    role="alert"
                    aria-live="polite"
                >
                    Settings saved successfully
                </div>
            )}
        </div>
    );
}
