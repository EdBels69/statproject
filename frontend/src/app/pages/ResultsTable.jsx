import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';

export default function ResultsTable() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    const [results, setResults] = useState(null);
    const [descriptives, setDescriptives] = useState([]);
    const [datasetName, setDatasetName] = useState('Dataset');

    // Table display settings
    const [tableSettings, setTableSettings] = useState({
        showMean: true,
        showMedian: false,
        showSD: true,
        showMinMax: false,
        showCI: false,
        showN: true
    });

    useEffect(() => {
        if (location.state?.result) {
            setResults(location.state.result.results || {});
            setDescriptives(location.state.result.descriptives || []);
        }
        if (location.state?.datasetName) {
            setDatasetName(location.state.datasetName);
        }
    }, [location.state]);

    const variables = Object.keys(results || {});
    const groups = [...new Set(descriptives.map(d => d.group).filter(Boolean))].sort();

    const getSignificanceColor = (p) => {
        if (p === null || p === undefined) return 'text-gray-500';
        if (p < 0.001) return 'text-green-700 font-bold';
        if (p < 0.01) return 'text-green-600 font-semibold';
        if (p < 0.05) return 'text-green-500';
        return 'text-gray-600';
    };

    const formatPValue = (p) => {
        if (p === null || p === undefined) return '—';
        if (p < 0.001) return '<0.001';
        return p.toFixed(4);
    };

    const formatGroupValue = (desc) => {
        if (!desc) return '—';
        const parts = [];
        if (tableSettings.showN) parts.push(`n=${desc.count || 0}`);
        if (tableSettings.showMean && desc.mean != null) {
            if (tableSettings.showSD && desc.sd != null) {
                parts.push(`${desc.mean.toFixed(1)}±${desc.sd.toFixed(1)}`);
            } else {
                parts.push(`M=${desc.mean.toFixed(1)}`);
            }
        }
        if (tableSettings.showMedian && desc.median != null) {
            parts.push(`Me=${desc.median.toFixed(1)}`);
        }
        if (tableSettings.showMinMax && desc.min != null && desc.max != null) {
            parts.push(`[${desc.min.toFixed(0)}-${desc.max.toFixed(0)}]`);
        }
        return parts.join(' ') || '—';
    };

    const handleNext = () => {
        navigate(`/charts/${id}`, {
            state: {
                result: { results, descriptives },
                datasetName,
                tableSettings
            }
        });
    };

    if (!results || variables.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                <p className="text-lg">Нет результатов анализа</p>
                <button onClick={() => navigate(`/analyze/${id}`)} className="mt-4 text-blue-600 hover:underline">
                    ← Вернуться к настройке
                </button>
            </div>
        );
    }

    const significantCount = Object.values(results).filter(r => r.significant).length;

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Шаг 1: Таблица результатов</h1>
                <p className="text-sm text-gray-500 mt-1">
                    {variables.length} переменных • {significantCount} значимых (p&lt;0.05)
                </p>
            </div>

            {/* Table Settings */}
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl border border-gray-200 p-4 mb-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Настройки отображения таблицы</h3>
                <div className="flex flex-wrap gap-4">
                    {[
                        { key: 'showN', label: 'n (размер выборки)' },
                        { key: 'showMean', label: 'Среднее (M)' },
                        { key: 'showSD', label: 'Станд. откл. (SD)' },
                        { key: 'showMedian', label: 'Медиана (Me)' },
                        { key: 'showMinMax', label: 'Мин-Макс' },
                        { key: 'showCI', label: '95% ДИ' }
                    ].map(opt => (
                        <label key={opt.key} className="flex items-center gap-2 text-sm cursor-pointer">
                            <input
                                type="checkbox"
                                checked={tableSettings[opt.key]}
                                onChange={(e) => setTableSettings(prev => ({ ...prev, [opt.key]: e.target.checked }))}
                                className="w-4 h-4 text-blue-600 rounded"
                            />
                            {opt.label}
                        </label>
                    ))}
                </div>
            </div>

            {/* Results Table */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-6">
                <div className="max-h-[55vh] overflow-y-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-gray-50 sticky top-0">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Переменная</th>
                                {groups.map(g => (
                                    <th key={g} className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase">
                                        Группа {g}
                                    </th>
                                ))}
                                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Метод</th>
                                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">p-value</th>
                                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase">Знач.</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {variables.map(varName => {
                                const r = results[varName];
                                const varDescs = descriptives.filter(d => d.variable === varName);
                                const isSignificant = r.p_value !== null && r.p_value < 0.05;

                                return (
                                    <tr key={varName} className={`hover:bg-gray-50 ${isSignificant ? 'bg-green-50/50' : ''}`}>
                                        <td className="px-4 py-3 font-medium text-gray-900">{varName}</td>
                                        {groups.map(g => {
                                            const desc = varDescs.find(d => String(d.group) === String(g));
                                            return (
                                                <td key={g} className="px-4 py-3 text-center text-gray-600 text-xs">
                                                    {formatGroupValue(desc)}
                                                </td>
                                            );
                                        })}
                                        <td className="px-4 py-3 text-gray-600 text-xs">{r.method?.name || '—'}</td>
                                        <td className={`px-4 py-3 text-right ${getSignificanceColor(r.p_value)}`}>
                                            {formatPValue(r.p_value)}
                                        </td>
                                        <td className="px-4 py-3 text-center">
                                            {isSignificant ? (
                                                <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">✓</span>
                                            ) : (
                                                <span className="text-gray-400">—</span>
                                            )}
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between">
                <button onClick={() => navigate(`/analyze/${id}`)} className="text-sm text-gray-600 hover:text-gray-900">
                    ← Назад к настройке
                </button>
                <button
                    onClick={handleNext}
                    className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition"
                >
                    Далее: Графики →
                </button>
            </div>
        </div>
    );
}
