import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export default function ResultsPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    const [results, setResults] = useState(null);
    const [descriptives, setDescriptives] = useState([]);
    const [selectedVariable, setSelectedVariable] = useState(null);
    const [generating, setGenerating] = useState(false);
    const [datasetName, setDatasetName] = useState('Dataset');

    // Global chart settings
    const [globalChartMode, setGlobalChartMode] = useState('boxplot'); // 'boxplot', 'scatter', 'bar', 'manual'
    const [perVariableChartType, setPerVariableChartType] = useState({});
    const [chartOptions, setChartOptions] = useState({
        showDataPoints: true,
        showMean: true,
        showPValue: false
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

    const generateReport = async () => {
        setGenerating(true);
        try {
            const response = await fetch(`${API_URL}/analysis/report/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    results,
                    descriptives,
                    dataset_name: datasetName,
                    options: {}
                })
            });

            if (!response.ok) throw new Error('Report generation failed');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'batch_report.docx';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert(`Ошибка генерации отчёта: ${err.message}`);
        } finally {
            setGenerating(false);
        }
    };

    const variables = Object.keys(results || {});

    const getChartType = (varName) => {
        if (globalChartMode === 'manual') {
            return perVariableChartType[varName] || 'boxplot';
        }
        return globalChartMode;
    };

    const setVariableChartType = (varName, type) => {
        setPerVariableChartType(prev => ({ ...prev, [varName]: type }));
    };

    const getSignificanceColor = (pValue) => {
        if (pValue === null || pValue === undefined) return 'text-gray-500';
        if (pValue < 0.001) return 'text-green-700 font-bold';
        if (pValue < 0.01) return 'text-green-600 font-semibold';
        if (pValue < 0.05) return 'text-green-500';
        return 'text-gray-600';
    };

    const formatPValue = (p) => {
        if (p === null || p === undefined) return '—';
        if (p < 0.001) return '<0.001';
        return p.toFixed(4);
    };

    if (!results || variables.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                <p className="text-lg">Нет результатов анализа</p>
                <button
                    onClick={() => navigate(`/analyze/${id}`)}
                    className="mt-4 text-blue-600 hover:underline"
                >
                    ← Вернуться к настройке
                </button>
            </div>
        );
    }

    const activeResult = selectedVariable ? results[selectedVariable] : null;

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Результаты анализа</h1>
                    <p className="text-sm text-gray-500 mt-1">{variables.length} переменных проанализировано</p>
                </div>
                <button
                    onClick={generateReport}
                    disabled={generating}
                    className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition disabled:opacity-50 flex items-center gap-2"
                >
                    {generating ? (
                        <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Генерация...</>
                    ) : (
                        '📄 Скачать отчёт (.docx)'
                    )}
                </button>
            </div>

            {/* Global Chart Settings Bar */}
            <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl border border-gray-200 p-4 mb-6">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-6">
                        <span className="text-sm font-semibold text-gray-700">Тип графиков:</span>
                        <div className="flex items-center gap-2">
                            {[
                                { id: 'boxplot', label: '📦 Все Boxplot' },
                                { id: 'scatter', label: '⚫ Все точечные' },
                                { id: 'bar', label: '📊 Все столбцы' },
                                { id: 'manual', label: '🎛️ Вручную' }
                            ].map(opt => (
                                <button
                                    key={opt.id}
                                    onClick={() => setGlobalChartMode(opt.id)}
                                    className={`px-3 py-1.5 text-sm rounded-lg transition ${globalChartMode === opt.id
                                        ? 'bg-blue-600 text-white'
                                        : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                                        }`}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                        <label className="flex items-center gap-1 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={chartOptions.showDataPoints}
                                onChange={(e) => setChartOptions(p => ({ ...p, showDataPoints: e.target.checked }))}
                                className="w-4 h-4"
                            />
                            Точки
                        </label>
                        <label className="flex items-center gap-1 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={chartOptions.showMean}
                                onChange={(e) => setChartOptions(p => ({ ...p, showMean: e.target.checked }))}
                                className="w-4 h-4"
                            />
                            Среднее
                        </label>
                        <label className="flex items-center gap-1 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={chartOptions.showPValue}
                                onChange={(e) => setChartOptions(p => ({ ...p, showPValue: e.target.checked }))}
                                className="w-4 h-4"
                            />
                            p-value
                        </label>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Left: Results Table */}
                <div className="col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Сводка результатов</h2>
                    </div>
                    <div className="max-h-[55vh] overflow-y-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-gray-50 sticky top-0">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Переменная</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Метод</th>
                                    <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">p-value</th>
                                    <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase">Знач.</th>
                                    {globalChartMode === 'manual' && (
                                        <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase">График</th>
                                    )}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {variables.map(varName => {
                                    const r = results[varName];
                                    const isSignificant = r.p_value !== null && r.p_value < 0.05;
                                    return (
                                        <tr
                                            key={varName}
                                            onClick={() => setSelectedVariable(varName)}
                                            className={`hover:bg-blue-50 cursor-pointer transition ${selectedVariable === varName ? 'bg-blue-100' : ''}`}
                                        >
                                            <td className="px-4 py-3 font-medium text-gray-900">{varName}</td>
                                            <td className="px-4 py-3 text-gray-600 text-xs">{r.method?.name || '—'}</td>
                                            <td className={`px-4 py-3 text-right ${getSignificanceColor(r.p_value)}`}>
                                                {formatPValue(r.p_value)}
                                            </td>
                                            <td className="px-4 py-3 text-center">
                                                {isSignificant ? (
                                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">✓</span>
                                                ) : (
                                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">—</span>
                                                )}
                                            </td>
                                            {globalChartMode === 'manual' && (
                                                <td className="px-4 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                                                    <select
                                                        value={getChartType(varName)}
                                                        onChange={(e) => setVariableChartType(varName, e.target.value)}
                                                        className="text-xs px-1 py-0.5 border border-gray-200 rounded"
                                                    >
                                                        <option value="boxplot">Box</option>
                                                        <option value="scatter">Точки</option>
                                                        <option value="bar">Столбцы</option>
                                                    </select>
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Right: Selected Variable Details */}
                <div className="space-y-4">
                    {/* Chart Panel */}
                    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                            <h2 className="text-sm font-semibold text-gray-700">
                                {selectedVariable || 'Выберите переменную'}
                            </h2>
                        </div>
                        <div className="p-4 min-h-[280px] flex items-center justify-center">
                            {selectedVariable && activeResult?.plot_stats ? (
                                <Chart
                                    data={activeResult.plot_stats}
                                    groups={activeResult.groups || []}
                                    chartType={getChartType(selectedVariable)}
                                    options={chartOptions}
                                    pValue={activeResult.p_value}
                                />
                            ) : (
                                <p className="text-gray-400 text-sm">Кликните на строку таблицы</p>
                            )}
                        </div>
                    </div>

                    {/* Stats Details */}
                    {selectedVariable && activeResult && (
                        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                            <h3 className="text-sm font-semibold text-gray-700 mb-3">Детали теста</h3>
                            <dl className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <dt className="text-gray-500">Метод:</dt>
                                    <dd className="font-medium text-right max-w-[150px] truncate" title={activeResult.method?.name}>{activeResult.method?.name}</dd>
                                </div>
                                <div className="flex justify-between">
                                    <dt className="text-gray-500">Статистика:</dt>
                                    <dd className="font-medium">{activeResult.stat_value?.toFixed(3) || '—'}</dd>
                                </div>
                                <div className="flex justify-between">
                                    <dt className="text-gray-500">p-value:</dt>
                                    <dd className={`font-medium ${getSignificanceColor(activeResult.p_value)}`}>
                                        {formatPValue(activeResult.p_value)}
                                    </dd>
                                </div>
                                {activeResult.effect_size && (
                                    <div className="flex justify-between">
                                        <dt className="text-gray-500">{activeResult.effect_size_name || 'Effect'}:</dt>
                                        <dd className="font-medium">{activeResult.effect_size.toFixed(3)}</dd>
                                    </div>
                                )}
                            </dl>
                        </div>
                    )}
                </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
                <button
                    onClick={() => navigate(`/analyze/${id}`)}
                    className="text-sm text-gray-600 hover:text-gray-900"
                >
                    ← Назад к настройке
                </button>
                <div className="space-x-3">
                    <button
                        onClick={() => alert('Скачать CSV: будет реализовано')}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                    >
                        📊 CSV
                    </button>
                    <button
                        onClick={() => alert('Отчёт: будет реализовано')}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition"
                    >
                        📝 Отчёт
                    </button>
                </div>
            </div>
        </div>
    );
}

// Universal Chart Component
function Chart({ data, groups, chartType, options, pValue }) {
    const width = 280;
    const height = 240;
    const margin = { top: 25, right: 20, bottom: 40, left: 45 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;

    let minVal = Infinity, maxVal = -Infinity;
    groups.forEach(g => {
        if (data[g]) {
            minVal = Math.min(minVal, data[g].min);
            maxVal = Math.max(maxVal, data[g].max);
        }
    });

    if (!isFinite(minVal) || !isFinite(maxVal)) return <p className="text-gray-400 text-sm">Нет данных</p>;

    const padding = (maxVal - minVal) * 0.15 || 1;
    const yMin = minVal - padding;
    const yMax = maxVal + padding;

    const yScale = (val) => plotHeight - ((val - yMin) / (yMax - yMin)) * plotHeight;
    const boxWidth = plotWidth / groups.length * 0.6;
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

    return (
        <svg width={width} height={height} className="font-sans">
            <g transform={`translate(${margin.left}, ${margin.top})`}>
                {/* P-value label */}
                {options.showPValue && pValue !== null && (
                    <text x={plotWidth / 2} y={-10} textAnchor="middle" fontSize="11" fill="#6b7280">
                        p = {pValue < 0.001 ? '<0.001' : pValue.toFixed(3)}
                    </text>
                )}

                {/* Y axis */}
                <line x1="0" y1="0" x2="0" y2={plotHeight} stroke="#e5e7eb" />
                {[0, 0.5, 1].map((t, i) => {
                    const val = yMin + (yMax - yMin) * (1 - t);
                    const y = t * plotHeight;
                    return (
                        <g key={i}>
                            <line x1="-5" y1={y} x2={plotWidth} y2={y} stroke="#f3f4f6" strokeDasharray="2,2" />
                            <text x="-8" y={y} dy="4" textAnchor="end" fontSize="10" fill="#9ca3af">{val.toFixed(0)}</text>
                        </g>
                    );
                })}

                {/* Render based on chart type */}
                {groups.map((group, i) => {
                    const stats = data[group];
                    if (!stats) return null;

                    const x = (i + 0.5) * (plotWidth / groups.length);
                    const color = colors[i % colors.length];

                    if (chartType === 'boxplot') {
                        const bx = x - boxWidth / 2;
                        return (
                            <g key={group}>
                                {/* Whiskers */}
                                <line x1={x} y1={yScale(stats.min)} x2={x} y2={yScale(stats.q1)} stroke={color} />
                                <line x1={x} y1={yScale(stats.max)} x2={x} y2={yScale(stats.q3)} stroke={color} />
                                <line x1={x - boxWidth * 0.3} y1={yScale(stats.min)} x2={x + boxWidth * 0.3} y2={yScale(stats.min)} stroke={color} />
                                <line x1={x - boxWidth * 0.3} y1={yScale(stats.max)} x2={x + boxWidth * 0.3} y2={yScale(stats.max)} stroke={color} />
                                {/* Box */}
                                <rect x={bx} y={yScale(stats.q3)} width={boxWidth} height={Math.max(1, yScale(stats.q1) - yScale(stats.q3))}
                                    fill={color} fillOpacity="0.2" stroke={color} strokeWidth="2" />
                                {/* Median */}
                                <line x1={bx} y1={yScale(stats.median)} x2={bx + boxWidth} y2={yScale(stats.median)} stroke={color} strokeWidth="3" />
                                {/* Mean */}
                                {options.showMean && <circle cx={x} cy={yScale(stats.mean)} r="3" fill="white" stroke={color} strokeWidth="2" />}
                                {/* Label */}
                                <text x={x} y={plotHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">{group}</text>
                            </g>
                        );
                    } else if (chartType === 'scatter') {
                        // Scatter with jitter
                        const jitter = () => (Math.random() - 0.5) * boxWidth * 0.8;
                        return (
                            <g key={group}>
                                {/* Points - simulate from quartiles */}
                                {[stats.min, stats.q1, stats.median, stats.q3, stats.max].map((v, j) => (
                                    <circle key={j} cx={x + jitter()} cy={yScale(v)} r="4" fill={color} fillOpacity="0.6" />
                                ))}
                                {/* Mean line */}
                                {options.showMean && (
                                    <line x1={x - boxWidth * 0.4} y1={yScale(stats.mean)} x2={x + boxWidth * 0.4} y2={yScale(stats.mean)} stroke={color} strokeWidth="2" />
                                )}
                                <text x={x} y={plotHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">{group}</text>
                            </g>
                        );
                    } else { // bar
                        const barWidth = boxWidth * 0.8;
                        const barHeight = yScale(yMin) - yScale(stats.mean);
                        return (
                            <g key={group}>
                                <rect x={x - barWidth / 2} y={yScale(stats.mean)} width={barWidth} height={barHeight}
                                    fill={color} fillOpacity="0.6" stroke={color} strokeWidth="1" />
                                {/* Error bar (SD) */}
                                <line x1={x} y1={yScale(stats.mean + stats.sd)} x2={x} y2={yScale(stats.mean - stats.sd)} stroke={color} strokeWidth="2" />
                                <line x1={x - 5} y1={yScale(stats.mean + stats.sd)} x2={x + 5} y2={yScale(stats.mean + stats.sd)} stroke={color} strokeWidth="2" />
                                <line x1={x - 5} y1={yScale(stats.mean - stats.sd)} x2={x + 5} y2={yScale(stats.mean - stats.sd)} stroke={color} strokeWidth="2" />
                                <text x={x} y={plotHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">{group}</text>
                            </g>
                        );
                    }
                })}
            </g>
        </svg>
    );
}
