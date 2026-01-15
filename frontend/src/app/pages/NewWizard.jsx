import React, { useState } from 'react';
import StepData from './steps/StepData';
import StepResults from './steps/StepResults';
import StepProtocol from './steps/StepProtocol';
import {
    ChartBarIcon,
    UserGroupIcon,
    ArrowTrendingUpIcon,
    ClockIcon,
    ArrowPathIcon
} from '@heroicons/react/24/outline';

const GoalCard = ({ title, description, icon: Icon, active, onClick }) => {
    const iconEl = React.createElement(Icon, { className: 'w-6 h-6', 'aria-hidden': 'true' });

    return (
        <button
            onClick={onClick}
            type="button"
            aria-pressed={active}
            aria-label={`Select ${title}: ${description}`}
            className={`p-6 rounded-[2px] border cursor-pointer transition-colors duration-200 flex flex-col items-center text-center group ${active
                ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)]'
                : 'border-[color:var(--border-color)] bg-[color:var(--white)] hover:border-[color:var(--accent)]'
                }`}
        >
            <div className={`w-12 h-12 rounded-[2px] mb-4 flex items-center justify-center transition-colors border ${active ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-[color:var(--white)]' : 'bg-[color:var(--bg-secondary)] border-[color:var(--border-color)] text-[color:var(--accent)]'
                } `}>
                {iconEl}
            </div>
            <h3 className="font-semibold text-lg mb-2 text-[color:var(--text-primary)]">{title}</h3>
            <p className="text-sm text-[color:var(--text-secondary)] leading-relaxed">{description}</p>
        </button>
    );
};

const STEPS = [
    { id: 'goal', title: 'Start' },
    { id: 'data', title: 'Data Prep' },
    { id: 'protocol', title: 'Study Design' },
    { id: 'results', title: 'Results' }
];

const StepGoal = ({ selectedGoal, onSelect }) => {
    const goals = [
        { id: 'compare_groups', title: 'Compare Groups', desc: 'Find differences between two or more groups (e.g. Treatment vs Control).', icon: UserGroupIcon },
        { id: 'relationship', title: 'Find Relationships', desc: 'Analyze correlations or associations between variables.', icon: ChartBarIcon },
        { id: 'prediction', title: 'Make Predictions', desc: 'Predict an outcome based on multiple risk factors.', icon: ArrowTrendingUpIcon },
        { id: 'survival', title: 'Survival Analysis', desc: 'Time-to-event analysis (Kaplan-Meier, Cox Regression).', icon: ClockIcon },
        { id: 'repeated_measures', title: 'Repeated Measures', desc: 'Same subjects measured multiple times (e.g. Before/During/After treatment).', icon: ArrowPathIcon },
    ];

    return (
        <div className="animate-fadeIn">
            <h2 className="text-xl font-semibold mb-2">What is your research question?</h2>
            <p className="text-[color:var(--text-secondary)] mb-8">Select the primary goal of your analysis to get AI-guided recommendations.</p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {goals.map((goal) => (
                    <GoalCard
                        key={goal.id}
                        {...goal}
                        active={selectedGoal === goal.id}
                        onClick={() => onSelect(goal.id)}
                    />
                ))}
            </div>
        </div>
    );
};

export default function NewWizard() {
    const [currStep, setCurrentStep] = useState(0);
    const [wizardData, setWizardData] = useState({
        goal: null,
        datasetId: null,
        variables: {},
        runId: null,
    });

    const nextStep = () => setCurrentStep(prev => Math.min(prev + 1, STEPS.length - 1));
    const prevStep = () => setCurrentStep(prev => Math.max(prev - 1, 0));

    // Determine if we can move forward
    const canShare = wizardData.datasetId && Object.keys(wizardData.variables).length > 0;

    return (
        <div className="max-w-5xl mx-auto">
            {/* Progress Stepper */}
            <div className="mb-12">
                <div className="flex items-center justify-between relative">
                    <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-full h-1 bg-[color:var(--border-color)] -z-10 rounded-[2px]"></div>
                    <div className={`absolute left-0 top-1/2 transform -translate-y-1/2 h-1 bg-[color:var(--accent)] -z-10 rounded-[2px] transition-all duration-300`}
                        style={{ width: `${(currStep / (STEPS.length - 1)) * 100}%` }}></div>

                    {STEPS.map((step, index) => (
                        <div key={step.id} className="flex flex-col items-center bg-[color:var(--bg-secondary)] px-4">
                            <div className={`w-8 h-8 rounded-[2px] flex items-center justify-center font-bold text-sm mb-2 transition-colors border ${currStep >= index ? 'bg-[color:var(--accent)] border-[color:var(--accent)] text-[color:var(--white)]' : 'bg-[color:var(--bg-secondary)] border-[color:var(--border-color)] text-[color:var(--text-muted)]'
                                } `}>
                                {index + 1}
                            </div>
                            <span className={`text-xs font-semibold uppercase tracking-wider ${currStep >= index ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-muted)]'
                                } `}>
                                {step.title}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Content Area */}
            <div className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-8 min-h-[400px]">
                {currStep === 0 && (
                    <StepGoal
                        selectedGoal={wizardData.goal}
                        onSelect={(goal) => setWizardData({ ...wizardData, goal })}
                    />
                )}

                {currStep === 1 && (
                    <StepData
                        goal={wizardData.goal}
                        onDataReady={(data) => {
                            setWizardData(prev => ({ ...prev, ...data }));
                        }}
                        onNext={() => setCurrentStep(2)}
                    />
                )}

                {currStep === 2 && (
                    <StepProtocol
                        data={wizardData}
                        onResultsReady={(runId) => {
                            setWizardData(prev => ({ ...prev, runId }));
                            setCurrentStep(3);
                        }}
                    />
                )}

                {currStep === 3 && (
                    <StepResults
                        runId={wizardData.runId}
                        datasetId={wizardData.datasetId}
                    />
                )}
            </div>

            {/* Navigation Footer (Only for Step 0/1, as Protocol/Results manage their own flow) */}
            {currStep < 2 && (
                <div className="mt-8 flex justify-between">
                    <button
                        onClick={prevStep}
                        disabled={currStep === 0}
                        className={`px-6 py-2.5 rounded-[2px] font-medium transition-colors ${currStep === 0
                            ? 'text-[color:var(--text-muted)] cursor-not-allowed'
                            : 'text-[color:var(--text-secondary)] hover:bg-[color:var(--bg-secondary)]'
                            } `}
                        aria-label="Go back to previous step"
                    >
                        Back
                    </button>

                    <button
                        onClick={nextStep}
                        disabled={
                            (currStep === 0 && !wizardData.goal) ||
                            (currStep === 1 && !canShare)
                        }
                        className={`px-6 py-2.5 rounded-[2px] font-medium transition-colors border ${((currStep === 0 && !wizardData.goal) || (currStep === 1 && !canShare))
                            ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-muted)] cursor-not-allowed border-[color:var(--border-color)]'
                            : 'bg-[color:var(--accent)] text-[color:var(--white)] border-[color:var(--accent)] hover:bg-[color:var(--accent-hover)] hover:border-[color:var(--accent-hover)]'
                            } `}
                        aria-label="Continue to next step"
                    >
                        Continue
                    </button>
                </div>
            )}
        </div>
    );
}
