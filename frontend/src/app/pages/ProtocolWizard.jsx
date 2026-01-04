import { useState } from 'react';
import { getWizardRecommendation } from '../../lib/api';

export default function ProtocolWizard() {
    const [step, setStep] = useState(1);
    const [selections, setSelections] = useState({
        goal: '',
        structure: '',
        data_type: '',
        groups: '',
        normal_distribution: true
    });
    const [recommendation, setRecommendation] = useState(null);
    const [loading, setLoading] = useState(false);

    const handleSelect = (key, value) => {
        setSelections({ ...selections, [key]: value });
        if (key === 'goal' && value === 'compare_groups') setStep(2);
        else if (key === 'goal' && value !== 'compare_groups') {
            // Shortcuts for other goals not fully implemented yet in UI flow but logic exists or fallback
            if (value === 'relationship') setStep(3); // skip structure
            else setStep(5); // skip to end
        }
        else if (step < 4) setStep(step + 1);
        else handleSubmit();
    };

    const handleSubmit = async () => {
        setLoading(true);
        try {
            const res = await getWizardRecommendation(selections);
            setRecommendation(res);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const reset = () => {
        setStep(1);
        setSelections({
            goal: '',
            structure: '',
            data_type: '',
            groups: '',
            normal_distribution: true
        });
        setRecommendation(null);
    };

    return (
        <div className="max-w-3xl mx-auto px-4">
            <h1 className="text-2xl font-bold text-slate-900 mb-8 flex items-center gap-2">
                🧙‍♂️ Clinical Protocol Wizard
            </h1>

            {!recommendation ? (
                <div className="bg-white p-8 border border-slate-200 shadow-sm rounded-lg">
                    {/* Progress Bar */}
                    <div className="flex gap-2 mb-8">
                        {[1, 2, 3, 4].map(s => (
                            <div key={s} className={`h-2 flex-1 rounded-full ${s <= step ? 'bg-indigo-600' : 'bg-slate-100'}`} />
                        ))}
                    </div>

                    {step === 1 && (
                        <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                            <h2 className="text-xl font-bold mb-6">What is your primary study objective?</h2>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <OptionCard
                                    title="Compare Groups"
                                    desc="Difference between treatment arms or populations"
                                    onClick={() => handleSelect('goal', 'compare_groups')}
                                />
                                <OptionCard
                                    title="Find Relationships"
                                    desc="Correlation or association between variables"
                                    onClick={() => handleSelect('goal', 'relationship')}
                                />
                                <OptionCard
                                    title="Prediction"
                                    desc="Predict outcome based on risk factors (Regression)"
                                    onClick={() => handleSelect('goal', 'prediction')}
                                    disabled
                                />
                                <OptionCard
                                    title="Survival Analysis"
                                    desc="Time-to-event analysis"
                                    onClick={() => handleSelect('goal', 'survival')}
                                    disabled
                                />
                            </div>
                        </div>
                    )}

                    {step === 2 && (
                        <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                            <h2 className="text-xl font-bold mb-6">How are the groups structured?</h2>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <OptionCard
                                    title="Independent"
                                    desc="Different subjects in each group (e.g., Placebo vs Drug)"
                                    onClick={() => handleSelect('structure', 'independent')}
                                />
                                <OptionCard
                                    title="Paired / Matched"
                                    desc="Same subjects measured twice (e.g., Pre-Post) or matched pairs"
                                    onClick={() => handleSelect('structure', 'paired')}
                                />
                            </div>
                        </div>
                    )}

                    {step === 3 && (
                        <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                            <h2 className="text-xl font-bold mb-6">What type of data is the outcome?</h2>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <OptionCard
                                    title="Numeric (Continuous)"
                                    desc="Height, Weight, Blood Pressure"
                                    onClick={() => handleSelect('data_type', 'numeric')}
                                />
                                <OptionCard
                                    title="Categorical (Nominal)"
                                    desc="Yes/No, Disease Status, Color"
                                    onClick={() => handleSelect('data_type', 'categorical')}
                                />
                            </div>
                            {selections.data_type === 'numeric' && (
                                <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={selections.normal_distribution}
                                            onChange={(e) => setSelections({ ...selections, normal_distribution: e.target.checked })}
                                        />
                                        Assume Normal Distribution (Parametric)
                                    </label>
                                </div>
                            )}
                        </div>
                    )}

                    {step === 4 && (
                        <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                            <h2 className="text-xl font-bold mb-6">How many groups are there?</h2>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <OptionCard
                                    title="Two Groups"
                                    desc="e.g., Control vs Treatment"
                                    onClick={() => {
                                        setSelections({ ...selections, groups: '2' });
                                        setStep(5);
                                        // Manually trigger submit here effectively
                                        getWizardRecommendation({ ...selections, groups: '2' }).then(setRecommendation).catch(console.error);
                                    }}
                                />
                                <OptionCard
                                    title="More than Two (> 2)"
                                    desc="e.g., Low Dose vs High Dose vs Placebo"
                                    onClick={() => {
                                        setSelections({ ...selections, groups: '>2' });
                                        setStep(5);
                                        getWizardRecommendation({ ...selections, groups: '>2' }).then(setRecommendation).catch(console.error);
                                    }}
                                />
                            </div>
                        </div>
                    )}

                    {/* Back Button */}
                    {step > 1 && (
                        <button
                            onClick={() => setStep(step - 1)}
                            className="mt-8 text-sm text-slate-500 hover:text-slate-800 underline"
                        >
                            ← Back
                        </button>
                    )}
                </div>
            ) : (
                <div className="animate-in zoom-in-95 duration-300">
                    <div className="bg-white border-2 border-indigo-600 rounded-xl p-8 shadow-lg text-center relative overflow-hidden">
                        <div className="absolute top-0 left-0 w-full h-2 bg-indigo-600" />

                        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 text-indigo-600 mb-6">
                            <span className="text-3xl">💡</span>
                        </div>

                        <h2 className="text-2xl font-bold text-slate-900 mb-2">
                            Recommended Method:
                        </h2>
                        <h3 className="text-3xl font-black text-indigo-600 mb-6 uppercase tracking-tight">
                            {recommendation.name}
                        </h3>

                        <p className="text-lg text-slate-600 mb-8 max-w-lg mx-auto">
                            {recommendation.description}
                        </p>

                        <div className="bg-slate-50 rounded-lg p-6 mb-8 text-left max-w-lg mx-auto border border-slate-200">
                            <h4 className="font-bold text-slate-700 mb-3 text-sm uppercase tracking-wider">Assumptions to Check:</h4>
                            <ul className="space-y-2">
                                {recommendation.assumptions.map((a, i) => (
                                    <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                                        <span className="text-indigo-500 font-bold">•</span>
                                        {a}
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div className="flex justify-center gap-4">
                            <button onClick={reset} className="px-6 py-2 rounded-lg border border-slate-300 text-slate-600 font-bold hover:bg-slate-50 transition-colors">
                                Start Over
                            </button>
                            <a href="/" className="px-6 py-2 rounded-lg bg-indigo-600 text-white font-bold hover:bg-indigo-700 transition-colors shadow-lg shadow-indigo-200">
                                Apply to Data →
                            </a>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

function OptionCard({ title, desc, onClick, disabled }) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            className={`text-left p-6 border rounded-xl transition-all ${disabled
                    ? 'opacity-50 border-slate-100 bg-slate-50 cursor-not-allowed'
                    : 'border-slate-200 hover:border-indigo-600 hover:shadow-md hover:bg-indigo-50/10 group'
                }`}
        >
            <h3 className={`font-bold text-lg mb-1 ${disabled ? 'text-slate-400' : 'text-slate-900 group-hover:text-indigo-700'}`}>
                {title}
            </h3>
            <p className="text-sm text-slate-500">
                {desc}
            </p>
        </button>
    );
}
