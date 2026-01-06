import React, { useState } from 'react';
import StepData from './steps/StepData';
import StepResults from './steps/StepResults';
import StepProtocol from './steps/StepProtocol';
import {
    ChartBarIcon,
    UserGroupIcon,
    ArrowTrendingUpIcon,
    ClockIcon
} from '@heroicons/react/24/outline';

const GoalCard = ({ title, description, icon: Icon, active, onClick }) => (
    <div
        onClick={onClick}
        className={`p-6 rounded-xl border cursor-pointer transition-all duration-200 flex flex-col items-center text-center group ${active
            ? 'border-blue-600 bg-blue-50 ring-1 ring-blue-600'
            : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-md'
            } `}
    >
        <div className={`w-12 h-12 rounded-full mb-4 flex items-center justify-center transition-colors ${active ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-600 group-hover:bg-blue-100'
            } `}>
            <Icon className="w-6 h-6" />
        </div>
        <h3 className={`font-semibold text-lg mb-2 ${active ? 'text-blue-900' : 'text-gray-900'} `}>{title}</h3>
        <p className="text-sm text-gray-500 leading-relaxed">{description}</p>
    </div>
);

const STEPS = [
    { id: 'goal', title: 'Start' },
    { id: 'data', title: 'Data Prep' },
    { id: 'protocol', title: 'Study Design' },
    { id: 'results', title: 'Results' }
];

const StepGoal = ({ selectedGoal, onSelect }) => {
    const goals = [
        { id: 'compare_groups', title: 'Compare Groups', desc: 'Find differences between two or more groups (e.g. Treatment vs Control).', icon: UserGroupIcon },
        { id: 'compare_paired', title: 'Paired Samples', desc: 'Compare related samples (e.g. Before vs After, Matched Pairs).', icon: ClockIcon },
        { id: 'correlation', title: 'Correlation Matrix', desc: 'Explore relationships between multiple numeric variables (Heatmap).', icon: ChartBarIcon },
        { id: 'prediction', title: 'Make Predictions', desc: 'Predict an outcome based on multiple risk factors.', icon: ArrowTrendingUpIcon },
        { id: 'survival', title: 'Survival Analysis', desc: 'Time-to-event analysis (Kaplan-Meier, Cox Regression).', icon: ClockIcon },
    ];

    return (
        <div className="animate-fadeIn">
            <h2 className="text-xl font-semibold mb-2">What is your research question?</h2>
            <p className="text-gray-500 mb-8">Select the primary goal of your analysis to get AI-guided recommendations.</p>

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
                    <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-full h-1 bg-gray-200 -z-10 rounded-full"></div>
                    <div className={`absolute left-0 top-1/2 transform -translate-y-1/2 h-1 bg-blue-600 -z-10 rounded-full transition-all duration-300`}
                        style={{ width: `${(currStep / (STEPS.length - 1)) * 100}%` }}></div>

                    {STEPS.map((step, index) => (
                        <div key={step.id} className={`flex flex-col items-center bg-[#F9FAFB] px-4`}>
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm mb-2 transition-colors ${currStep >= index ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-200 text-gray-500'
                                } `}>
                                {index + 1}
                            </div>
                            <span className={`text-xs font-semibold uppercase tracking-wider ${currStep >= index ? 'text-blue-600' : 'text-gray-400'
                                } `}>
                                {step.title}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Content Area */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8 min-h-[400px]">
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
                        goal={wizardData.goal}
                    />
                )}
            </div>

            {/* Navigation Footer (Only for Step 0/1, as Protocol/Results manage their own flow) */}
            {currStep < 2 && (
                <div className="mt-8 flex justify-between">
                    <button
                        onClick={prevStep}
                        disabled={currStep === 0}
                        className={`px-6 py-2.5 rounded-lg font-medium transition-colors ${currStep === 0
                            ? 'text-gray-300 cursor-not-allowed'
                            : 'text-gray-600 hover:bg-gray-100'
                            } `}
                    >
                        Back
                    </button>

                    <button
                        onClick={nextStep}
                        disabled={
                            (currStep === 0 && !wizardData.goal) ||
                            (currStep === 1 && !canShare)
                        }
                        className={`px-6 py-2.5 rounded-lg font-medium transition-all shadow-sm ${((currStep === 0 && !wizardData.goal) || (currStep === 1 && !canShare))
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed shadow-none'
                            : 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-md hover:-translate-y-0.5'
                            } `}
                    >
                        Continue
                    </button>
                </div>
            )}
        </div>
    );
}
