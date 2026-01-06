import React, { useState, useEffect } from 'react';
import { suggestAnalysisDesign, runAnalysisProtocol } from '../../../lib/api';
import { BeakerIcon, PlayIcon, ClipboardDocumentCheckIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

const StepProtocol = ({ data, onResultsReady }) => {
    const [protocol, setProtocol] = useState(null);
    const [loading, setLoading] = useState(true);
    const [running, setRunning] = useState(false);
    const [error, setError] = useState(null);

    // 1. Auto-generate protocol on mount
    useEffect(() => {
        const generate = async () => {
            try {
                setLoading(true);
                // "Thinking" simulation
                await new Promise(r => setTimeout(r, 800));

                const proto = await suggestAnalysisDesign(
                    data.datasetId,
                    data.goal,
                    data.variables
                );
                setProtocol(proto);
            } catch (err) {
                setError("Failed to generate study design: " + err.message);
            } finally {
                setLoading(false);
            }
        };
        generate();
    }, [data]);

    // 2. Execute the approved protocol
    const handleExecute = async () => {
        try {
            setRunning(true);
            const res = await runAnalysisProtocol(data.datasetId, protocol);
            // res = { run_id: "...", status: "completed" }
            if (res.run_id) {
                onResultsReady(res.run_id);
            } else {
                setError("Analysis failed to start.");
            }
        } catch (err) {
            setError("Execution failed: " + err.message);
            setRunning(false);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 animate-pulse">
                <BeakerIcon className="w-16 h-16 text-blue-200 mb-4" />
                <h3 className="text-xl font-medium text-gray-700">Designing Study Protocol...</h3>
                <p className="text-gray-500 mt-2">AI is analyzing variable types and normality</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="bg-red-50 p-6 rounded-lg text-center">
                <div className="text-red-600 font-medium mb-2">Error</div>
                {error}
                <button onClick={() => window.location.reload()} className="mt-4 text-sm text-blue-600 underline">Retry</button>
            </div>
        );
    }

    return (
        <div className="max-w-3xl mx-auto animate-fadeIn">
            {/* Header */}
            <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 text-green-600 mb-4">
                    <ClipboardDocumentCheckIcon className="w-6 h-6" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900">Proposed Analysis Plan</h2>
                <p className="text-gray-500 mt-2">
                    Based on your goal <strong>{data.goal?.replace('_', ' ')}</strong>, we recommend the following pipeline:
                </p>
            </div>

            {/* Protocol Card */}
            <div className="bg-white border-2 border-indigo-50 rounded-xl overflow-hidden shadow-sm mb-8">
                <div className="bg-indigo-50/50 p-4 border-b border-indigo-100 flex justify-between items-center">
                    <span className="font-semibold text-indigo-900">{protocol.name}</span>
                    <span className="text-xs bg-indigo-200 text-indigo-800 px-2 py-1 rounded-full uppercase tracking-wide">
                        {protocol.steps.length} Steps
                    </span>
                </div>

                <div className="divide-y divide-gray-100">
                    {protocol.steps.map((step, idx) => (
                        <div key={idx} className="p-4 flex items-start hover:bg-gray-50 transition-colors">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-sm font-bold text-gray-500 mr-4">
                                {idx + 1}
                            </div>
                            <div>
                                <h4 className="text-sm font-bold text-gray-900 uppercase">
                                    {step.type.replace(/_/g, ' ')}
                                </h4>
                                <p className="text-sm text-gray-600 mt-1">
                                    Target: <code className="bg-gray-100 px-1 rounded">{step.target}</code>
                                    {step.group && <> vs Group: <code className="bg-gray-100 px-1 rounded">{step.group}</code></>}
                                    {step.split_by && <> (Split by: <code className="bg-blue-50 text-blue-700 px-1 rounded">{step.split_by}</code>)</>}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Action */}
            <div className="flex justify-center">
                <button
                    onClick={handleExecute}
                    disabled={running}
                    className="flex items-center px-8 py-3 bg-indigo-600 text-white rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-70 shadow-lg hover:shadow-xl transition-all"
                >
                    {running ? (
                        <>
                            <ArrowPathIcon className="w-5 h-5 mr-2 animate-spin" />
                            Running Analysis...
                        </>
                    ) : (
                        <>
                            <PlayIcon className="w-5 h-5 mr-2" />
                            Confirm & Run Protocol
                        </>
                    )}
                </button>
            </div>
        </div>
    );
};

export default StepProtocol;
