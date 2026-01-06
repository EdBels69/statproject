import React from 'react';
import { ChartBarIcon, ArrowTrendingUpIcon } from '@heroicons/react/24/outline';
import ChartCustomizer from './ChartCustomizer';

const RegressionResults = ({ data, runId, datasetId, stepId, onUpdate }) => {
    if (!data) return null;

    const { coef_table, fit_stats, plot_image, method } = data;
    const isLogit = method === "logit";

    // Helper for P-values
    const formatP = (p) => p < 0.001 ? '<0.001' : p.toFixed(4);

    return (
        <div className="space-y-6">
            {/* Model Summary Card */}
            <div className="bg-white p-5 rounded-xl border shadow-sm">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center">
                    <ArrowTrendingUpIcon className="w-5 h-5 mr-2 text-indigo-600" />
                    Model Summary ({isLogit ? "Logistic" : "Linear"} Regression)
                </h3>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                    <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="text-xs text-gray-500 uppercase font-semibold">Observations</div>
                        <div className="text-xl font-bold text-gray-800">{fit_stats.n_obs}</div>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="text-xs text-gray-500 uppercase font-semibold">
                            {isLogit ? "Pseudo R²" : "R-Squared"}
                        </div>
                        <div className="text-xl font-bold text-gray-800">
                            {(fit_stats.r_squared || 0).toFixed(3)}
                        </div>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="text-xs text-gray-500 uppercase font-semibold">AIC</div>
                        <div className="text-lg font-medium text-gray-600">
                            {fit_stats.aic.toFixed(1)}
                        </div>
                    </div>
                    <div className="p-3 bg-gray-50 rounded-lg">
                        <div className="text-xs text-gray-500 uppercase font-semibold">BIC</div>
                        <div className="text-lg font-medium text-gray-600">
                            {fit_stats.bic.toFixed(1)}
                        </div>
                    </div>
                </div>
            </div>

            {/* Coefficients Table */}
            <div className="bg-white border rounded-xl shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b bg-gray-50">
                    <h4 className="text-sm font-semibold text-gray-700">Coefficients</h4>
                </div>
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Input</th>
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Coef</th>
                                {isLogit && (
                                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Odds Ratio</th>
                                )}
                                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Std.Err</th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">P-Value</th>
                                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase">95% CI</th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {coef_table.map((row, idx) => (
                                <tr key={idx} className={row.p_value < 0.05 ? "bg-green-50" : ""}>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                        {row.variable === "const" ? "(Intercept)" : row.variable}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-500">
                                        {row.coef.toFixed(3)}
                                    </td>
                                    {isLogit && (
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium text-indigo-600">
                                            {row.odds_ratio ? row.odds_ratio.toFixed(2) : "-"}
                                        </td>
                                    )}
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right text-gray-400">
                                        {row.std_err.toFixed(3)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-center">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${row.p_value < 0.05 ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                            }`}>
                                            {formatP(row.p_value)}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-500 text-xs">
                                        [{row.ci_lower.toFixed(2)} ; {row.ci_upper.toFixed(2)}]
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Diagnostic Plot */}
            {plot_image && (
                <div className="bg-white p-5 rounded-xl border shadow-sm flex flex-col items-center relative group">
                    {runId && (
                        <ChartCustomizer
                            runId={runId}
                            datasetId={datasetId}
                            stepId={stepId}
                            currentImage={plot_image}
                            onUpdate={onUpdate}
                        />
                    )}
                    <h4 className="text-sm font-semibold text-gray-700 mb-4 self-start">Model Diagnostics</h4>
                    <img
                        src={`data:image/png;base64,${plot_image}`}
                        alt="Regression Plot"
                        className="max-w-md rounded-lg border shadow-sm"
                    />
                    <p className="text-xs text-gray-500 mt-2">
                        {isLogit ? "ROC Curve" : "Actual vs Predicted Values"}
                    </p>
                </div>
            )}
        </div>
    );
};

export default RegressionResults;
