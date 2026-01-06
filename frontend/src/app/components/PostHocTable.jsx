import React from 'react';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/20/solid';

const PostHocTable = ({ data }) => {
    if (!data || data.length === 0) return null;

    // Helper to format p-value
    const formatP = (p) => {
        if (p < 0.001) return '<0.001';
        return p.toFixed(3);
    };

    return (
        <div className="mt-6 border rounded-lg overflow-hidden bg-white shadow-sm">
            <div className="bg-gray-50 px-4 py-3 border-b">
                <h4 className="text-sm font-semibold text-gray-700">Попарные сравнения (Post-Hoc Tukey)</h4>
            </div>
            <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Группа A</th>
                            <th scope="col" className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Группа B</th>
                            <th scope="col" className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Разница (Diff)</th>
                            <th scope="col" className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">95% CI</th>
                            <th scope="col" className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">P-Value</th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {data.map((row, idx) => (
                            <tr key={idx} className={row.significant ? "bg-green-50" : ""}>
                                <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">{row.group1}</td>
                                <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-900">{row.group2}</td>
                                <td className="px-3 py-2 whitespace-nowrap text-sm text-center text-gray-500">{row.diff.toFixed(2)}</td>
                                <td className="px-3 py-2 whitespace-nowrap text-sm text-center text-gray-500 text-xs">
                                    [{row.ci_lower.toFixed(2)}, {row.ci_upper.toFixed(2)}]
                                </td>
                                <td className="px-3 py-2 whitespace-nowrap text-sm text-center font-medium">
                                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${row.significant ? 'bg-green-100 text-green-800' : 'text-gray-500'
                                        }`}>
                                        {formatP(row.p_value)}
                                        {row.significant && <CheckCircleIcon className="w-3 h-3 ml-1" />}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};

export default PostHocTable;
