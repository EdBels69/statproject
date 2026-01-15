import React, { useState } from 'react';
import { useLanguage } from '../../contexts/LanguageContext';
import { useTranslation } from '../../hooks/useTranslation';

export default function Settings() {
    const { t } = useTranslation();
    const { educationLevel, changeEducationLevel } = useLanguage();
    const alphaOptions = [
        { value: 0.01, key: '001' },
        { value: 0.05, key: '005' },
        { value: 0.10, key: '010' },
    ];
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

    const handleEducationLevelChange = (value) => {
        changeEducationLevel(value);
        setShowToast(true);
        setTimeout(() => setShowToast(false), 2000);
    };

    return (
        <div className="max-w-3xl mx-auto animate-fadeIn">
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-[color:var(--text-primary)]">{t('settings_title')}</h1>
                <p className="text-[color:var(--text-secondary)] mt-1">{t('settings_subtitle')}</p>
            </div>

            <div className="space-y-6">
                <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-6">
                    <h2 className="text-lg font-semibold text-[color:var(--text-primary)] mb-4">{t('settings_alpha_title')}</h2>
                    <p className="text-sm text-[color:var(--text-secondary)] mb-6">{t('settings_alpha_desc')}</p>

                    <div className="space-y-3">
                        {alphaOptions.map((opt) => (
                            <label
                                key={opt.key}
                                className={`relative flex items-start p-4 rounded-[2px] border cursor-pointer transition-colors ${alpha === opt.value
                                    ? 'border-[color:var(--accent)] bg-[color:var(--bg-tertiary)]'
                                    : 'border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                } focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]`}
                                tabIndex={0}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        handleAlphaChange(opt.value);
                                    }
                                }}
                            >
                                <input
                                    type="radio"
                                    name="alpha"
                                    value={opt.value}
                                    checked={alpha === opt.value}
                                    onChange={() => handleAlphaChange(opt.value)}
                                    className="sr-only"
                                />
                                <div className={`w-5 h-5 rounded-[2px] border-2 flex items-center justify-center mt-0.5 mr-4 flex-shrink-0 transition-colors ${alpha === opt.value
                                    ? 'border-[color:var(--accent)] bg-[color:var(--accent)]'
                                    : 'border-[color:var(--border-color)]'
                                }`}>
                                    {alpha === opt.value && (
                                        <div className="w-2.5 h-2.5 rounded-[2px] bg-[color:var(--white)]"></div>
                                    )}
                                </div>
                                <div>
                                    <div className="font-semibold text-[color:var(--text-primary)]">{t(`settings_alpha_${opt.key}_label`)}</div>
                                    <div className="text-sm text-[color:var(--text-secondary)] mt-0.5">{t(`settings_alpha_${opt.key}_desc`)}</div>
                                </div>
                            </label>
                        ))}
                    </div>
                </section>

                <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-6">
                    <h2 className="text-lg font-semibold text-[color:var(--text-primary)] mb-4">{t('settings_education_title')}</h2>
                    <p className="text-sm text-[color:var(--text-secondary)] mb-6">{t('settings_education_desc')}</p>

                    <div className="space-y-3">
                        {['junior', 'mid', 'senior'].map((value) => (
                            <label
                                key={value}
                                className={`relative flex items-start p-4 rounded-[2px] border cursor-pointer transition-colors ${educationLevel === value
                                    ? 'border-[color:var(--accent)] bg-[color:var(--bg-tertiary)]'
                                    : 'border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)]'
                                } focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]`}
                                tabIndex={0}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        handleEducationLevelChange(value);
                                    }
                                }}
                            >
                                <input
                                    type="radio"
                                    name="education_level"
                                    value={value}
                                    checked={educationLevel === value}
                                    onChange={() => handleEducationLevelChange(value)}
                                    className="sr-only"
                                />
                                <div className={`w-5 h-5 rounded-[2px] border-2 flex items-center justify-center mt-0.5 mr-4 flex-shrink-0 transition-colors ${educationLevel === value
                                    ? 'border-[color:var(--accent)] bg-[color:var(--accent)]'
                                    : 'border-[color:var(--border-color)]'
                                }`}>
                                    {educationLevel === value && (
                                        <div className="w-2.5 h-2.5 rounded-[2px] bg-[color:var(--white)]"></div>
                                    )}
                                </div>
                                <div>
                                    <div className="font-semibold text-[color:var(--text-primary)]">{t(`settings_education_${value}_label`)}</div>
                                    <div className="text-sm text-[color:var(--text-secondary)] mt-0.5">{t(`settings_education_${value}_desc`)}</div>
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
                    {t('settings_saved')}
                </div>
            )}
        </div>
    );
}
