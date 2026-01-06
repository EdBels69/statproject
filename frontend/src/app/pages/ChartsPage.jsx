import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';

export default function ChartsPage() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    const [results, setResults] = useState({});
    const [descriptives, setDescriptives] = useState([]);
    const [datasetName, setDatasetName] = useState('Dataset');
    const [tableSettings, setTableSettings] = useState({});
    const [selectedVariable, setSelectedVariable] = useState(null);

    // Chart settings
    const [globalChartType, setGlobalChartType] = useState('boxplot');
    const [perVariableSettings, setPerVariableSettings] = useState({});
    const [chartOptions, setChartOptions] = useState({
        showDataPoints: true,
        showMean: true,
        showPValue: true,
        colorScheme: 'default'
    });

    useEffect(() => {
        if (location.state?.result) {
            setResults(location.state.result.results || {});
            setDescriptives(location.state.result.descriptives || []);
        }
        if (location.state?.datasetName) setDatasetName(location.state.datasetName);
        if (location.state?.tableSettings) setTableSettings(location.state.tableSettings);
    }, [location.state]);

    const variables = Object.keys(results);
    const significantVars = variables.filter(v => results[v]?.significant);

    const getChartType = (varName) => perVariableSettings[varName]?.chartType || globalChartType;

    const updateVarSetting = (varName, key, value) => {
        setPerVariableSettings(prev => ({
            ...prev,
            [varName]: { ...prev[varName], [key]: value }
        }));
    };

    const handleNext = () => {
        navigate(`/report-preview/${id}`, {
            state: {
                result: { results, descriptives },
                datasetName,
                tableSettings,
                chartSettings: { globalChartType, perVariableSettings, chartOptions }
            }
        });
    };

    if (!variables.length) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                <p>Нет данных для отображения</p>
                <button onClick={() => navigate(`/analyze/${id}`)} className="mt-4 text-blue-600 hover:underline">
                    ← Вернуться
                </button>
            </div>
        );
    }

    const activeResult = selectedVariable ? results[selectedVariable] : null;

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Шаг 2: Графики</h1>
                <p className="text-sm text-gray-500 mt-1">Настройте визуализацию для каждой переменной</p>
            </div>

            {/* Global Chart Settings */}
            <div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl border border-gray-200 p-4 mb-6">
                <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-4">
                        <span className="text-sm font-semibold text-gray-700">Тип по умолчанию:</span>
                        {['boxplot', 'scatter', 'bar'].map(type => (
                            <button
                                key={type}
                                onClick={() => setGlobalChartType(type)}
                                className={`px-3 py-1.5 text-sm rounded-lg transition ${globalChartType === type
                                        ? 'bg-purple-600 text-white'
                                        : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                                    }`}
                            >
                                {type === 'boxplot' ? '📦 Boxplot' : type === 'scatter' ? '⚫ Точки' : '📊 Столбцы'}
                            </button>
                        ))}
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                        <label className="flex items-center gap-1.5 cursor-pointer">
                            <input type="checkbox" checked={chartOptions.showDataPoints}
                                onChange={(e) => setChartOptions(p => ({ ...p, showDataPoints: e.target.checked }))} className="w-4 h-4" />
                            Точки данных
                        </label>
                        <label className="flex items-center gap-1.5 cursor-pointer">
                            <input type="checkbox" checked={chartOptions.showMean}
                                onChange={(e) => setChartOptions(p => ({ ...p, showMean: e.target.checked }))} className="w-4 h-4" />
                            Среднее
                        </label>
                        <label className="flex items-center gap-1.5 cursor-pointer">
                            <input type="checkbox" checked={chartOptions.showPValue}
                                onChange={(e) => setChartOptions(p => ({ ...p, showPValue: e.target.checked }))} className="w-4 h-4" />
                            p-value
                        </label>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-6">
                {/* Left: Variable List */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                        <h3 className="text-sm font-semibold text-gray-700">Переменные ({variables.length})</h3>
                    </div>
                    <div className="max-h-[50vh] overflow-y-auto divide-y divide-gray-100">
                        {variables.map(varName => {
                            const r = results[varName];
                            const isSignificant = r?.significant;
                            return (
                                <div
                                    key={varName}
                                    onClick={() => setSelectedVariable(varName)}
                                    className={`px-4 py-3 cursor-pointer transition flex items-center justify-between ${selectedVariable === varName ? 'bg-blue-100' : 'hover:bg-gray-50'
                                        } ${isSignificant ? 'border-l-4 border-l-green-500' : ''}`}
                                >
                                    <span className="text-sm font-medium text-gray-900 truncate">{varName}</span>
                                    <span className="text-xs text-gray-500">
                                        {getChartType(varName) === 'boxplot' ? '📦' : getChartType(varName) === 'scatter' ? '⚫' : '📊'}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Center: Chart Preview */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-gray-700">{selectedVariable || 'Выберите переменную'}</h3>
                        {selectedVariable && (
                            <select
                                value={getChartType(selectedVariable)}
                                onChange={(e) => updateVarSetting(selectedVariable, 'chartType', e.target.value)}
                                className="text-xs px-2 py-1 border border-gray-200 rounded"
                            >
                                <option value="boxplot">Boxplot</option>
                                <option value="scatter">Точечный</option>
                                <option value="bar">Столбцы</option>
                            </select>
                        )}
                    </div>
                    <div className="p-4 min-h-[300px] flex items-center justify-center">
                        {selectedVariable && activeResult?.plot_stats ? (
                            <Chart
                                data={activeResult.plot_stats}
                                groups={activeResult.groups || []}
                                chartType={getChartType(selectedVariable)}
                                options={chartOptions}
                                pValue={activeResult.p_value}
                            />
                        ) : (
                            <p className="text-gray-400 text-sm">Выберите переменную слева</p>
                        )}
                    </div>
                </div>

                {/* Right: Per-Variable Settings */}
                <div className="space-y-4">
                    {selectedVariable && (
                        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                            <h3 className="text-sm font-semibold text-gray-700 mb-3">Настройки: {selectedVariable}</h3>
                            <div className="space-y-3">
                                <div>
                                    <label className="block text-xs text-gray-500 mb-1">Тип графика</label>
                                    <select
                                        value={getChartType(selectedVariable)}
                                        onChange={(e) => updateVarSetting(selectedVariable, 'chartType', e.target.value)}
                                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
                                    >
                                        <option value="boxplot">📦 Boxplot</option>
                                        <option value="scatter">⚫ Точечный</option>
                                        <option value="bar">📊 Столбцы (M±SD)</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-xs text-gray-500 mb-1">Заголовок графика</label>
                                    <input
                                        type="text"
                                        value={perVariableSettings[selectedVariable]?.title || selectedVariable}
                                        onChange={(e) => updateVarSetting(selectedVariable, 'title', e.target.value)}
                                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg"
                                    />
                                </div>
                                <label className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={perVariableSettings[selectedVariable]?.includeInReport !== false}
                                        onChange={(e) => updateVarSetting(selectedVariable, 'includeInReport', e.target.checked)}
                                        className="w-4 h-4"
                                    />
                                    Включить в отчёт
                                </label>
                            </div>
                        </div>
                    )}

                    {/* Summary */}
                    <div className="bg-gradient-to-r from-green-50 to-blue-50 rounded-xl border border-gray-200 p-4">
                        <h3 className="text-sm font-semibold text-gray-700 mb-2">Сводка</h3>
                        <ul className="text-sm text-gray-600 space-y-1">
                            <li>📊 Всего графиков: {variables.length}</li>
                            <li>✅ Значимых: {significantVars.length}</li>
                            <li>📦 Boxplot: {variables.filter(v => getChartType(v) === 'boxplot').length}</li>
                            <li>⚫ Точечных: {variables.filter(v => getChartType(v) === 'scatter').length}</li>
                            <li>📊 Столбцов: {variables.filter(v => getChartType(v) === 'bar').length}</li>
                        </ul>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between mt-6">
                <button onClick={() => navigate(`/results/${id}`, { state: location.state })} className="text-sm text-gray-600 hover:text-gray-900">
                    ← Назад к таблице
                </button>
                <button onClick={handleNext} className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition">
                    Далее: Превью отчёта →
                </button>
            </div>
        </div>
    );
}

// Chart Component (simplified)
function Chart({ data, groups, chartType, options, pValue }) {
    const width = 280, height = 240;
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

    if (!isFinite(minVal)) return <p className="text-gray-400 text-sm">Нет данных</p>;

    const padding = (maxVal - minVal) * 0.15 || 1;
    const yMin = minVal - padding, yMax = maxVal + padding;
    const yScale = (val) => plotHeight - ((val - yMin) / (yMax - yMin)) * plotHeight;
    const boxWidth = plotWidth / groups.length * 0.6;
    const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

    return (
        <svg width={width} height={height} className="font-sans">
            <g transform={`translate(${margin.left}, ${margin.top})`}>
                {options.showPValue && pValue != null && (
                    <text x={plotWidth / 2} y={-10} textAnchor="middle" fontSize="11" fill="#6b7280">
                        p = {pValue < 0.001 ? '<0.001' : pValue.toFixed(3)}
                    </text>
                )}
                <line x1="0" y1="0" x2="0" y2={plotHeight} stroke="#e5e7eb" />
                {[0, 0.5, 1].map((t, i) => {
                    const val = yMin + (yMax - yMin) * (1 - t);
                    return <g key={i}><line x1="-5" y1={t * plotHeight} x2={plotWidth} y2={t * plotHeight} stroke="#f3f4f6" strokeDasharray="2,2" /><text x="-8" y={t * plotHeight} dy="4" textAnchor="end" fontSize="10" fill="#9ca3af">{val.toFixed(0)}</text></g>;
                })}
                {groups.map((group, i) => {
                    const stats = data[group];
                    if (!stats) return null;
                    const x = (i + 0.5) * (plotWidth / groups.length);
                    const color = colors[i % colors.length];

                    if (chartType === 'boxplot') {
                        const bx = x - boxWidth / 2;
                        return <g key={group}>
                            <line x1={x} y1={yScale(stats.min)} x2={x} y2={yScale(stats.q1)} stroke={color} />
                            <line x1={x} y1={yScale(stats.max)} x2={x} y2={yScale(stats.q3)} stroke={color} />
                            <line x1={x - boxWidth * 0.3} y1={yScale(stats.min)} x2={x + boxWidth * 0.3} y2={yScale(stats.min)} stroke={color} />
                            <line x1={x - boxWidth * 0.3} y1={yScale(stats.max)} x2={x + boxWidth * 0.3} y2={yScale(stats.max)} stroke={color} />
                            <rect x={bx} y={yScale(stats.q3)} width={boxWidth} height={Math.max(1, yScale(stats.q1) - yScale(stats.q3))} fill={color} fillOpacity="0.2" stroke={color} strokeWidth="2" />
                            <line x1={bx} y1={yScale(stats.median)} x2={bx + boxWidth} y2={yScale(stats.median)} stroke={color} strokeWidth="3" />
                            {options.showMean && <circle cx={x} cy={yScale(stats.mean)} r="3" fill="white" stroke={color} strokeWidth="2" />}
                            <text x={x} y={plotHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">{group}</text>
                        </g>;
                    } else if (chartType === 'bar') {
                        const barWidth = boxWidth * 0.8;
                        return <g key={group}>
                            <rect x={x - barWidth / 2} y={yScale(stats.mean)} width={barWidth} height={yScale(yMin) - yScale(stats.mean)} fill={color} fillOpacity="0.6" stroke={color} />
                            <line x1={x} y1={yScale(stats.mean + stats.sd)} x2={x} y2={yScale(stats.mean - stats.sd)} stroke={color} strokeWidth="2" />
                            <text x={x} y={plotHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">{group}</text>
                        </g>;
                    } else {
                        return <g key={group}>
                            {[stats.min, stats.q1, stats.median, stats.q3, stats.max].map((v, j) => (
                                <circle key={j} cx={x + (Math.random() - 0.5) * boxWidth * 0.6} cy={yScale(v)} r="4" fill={color} fillOpacity="0.6" />
                            ))}
                            {options.showMean && <line x1={x - boxWidth * 0.3} y1={yScale(stats.mean)} x2={x + boxWidth * 0.3} y2={yScale(stats.mean)} stroke={color} strokeWidth="2" />}
                            <text x={x} y={plotHeight + 18} textAnchor="middle" fontSize="11" fill="#6b7280">{group}</text>
                        </g>;
                    }
                })}
            </g>
        </svg>
    );
}
