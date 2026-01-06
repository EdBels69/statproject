import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export default function ReportPreview() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    const [results, setResults] = useState({});
    const [descriptives, setDescriptives] = useState([]);
    const [datasetName, setDatasetName] = useState('Dataset');
    const [tableSettings, setTableSettings] = useState({});
    const [chartSettings, setChartSettings] = useState({});
    const [generating, setGenerating] = useState(false);

    // Report options
    const [reportOptions, setReportOptions] = useState({
        includeTableOne: true,
        includeSignificantOnly: false,
        includeCharts: true,
        includeMethodsSection: true,
        reportTitle: 'Статистический отчёт'
    });

    useEffect(() => {
        if (location.state?.result) {
            setResults(location.state.result.results || {});
            setDescriptives(location.state.result.descriptives || []);
        }
        if (location.state?.datasetName) setDatasetName(location.state.datasetName);
        if (location.state?.tableSettings) setTableSettings(location.state.tableSettings);
        if (location.state?.chartSettings) setChartSettings(location.state.chartSettings);
    }, [location.state]);

    const variables = Object.keys(results);
    const significantVars = variables.filter(v => results[v]?.significant);
    const groups = [...new Set(descriptives.map(d => d.group).filter(Boolean))].sort();

    const generateAndDownload = async () => {
        setGenerating(true);
        try {
            const response = await fetch(`${API_URL}/analysis/report/batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    results,
                    descriptives,
                    dataset_name: datasetName,
                    options: reportOptions
                })
            });

            if (!response.ok) throw new Error('Report generation failed');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${datasetName.replace(/\s+/g, '_')}_report.docx`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert(`Ошибка: ${err.message}`);
        } finally {
            setGenerating(false);
        }
    };

    if (!variables.length) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                <p>Нет данных</p>
                <button onClick={() => navigate(`/analyze/${id}`)} className="mt-4 text-blue-600 hover:underline">← Назад</button>
            </div>
        );
    }

    return (
        <div className="animate-fadeIn">
            {/* Header */}
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900">Шаг 3: Превью отчёта</h1>
                <p className="text-sm text-gray-500 mt-1">Проверьте и настройте содержание перед скачиванием</p>
            </div>

            <div className="grid grid-cols-2 gap-6">
                {/* Left: Report Options */}
                <div className="space-y-4">
                    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
                        <h3 className="text-sm font-semibold text-gray-800 mb-4">Настройки отчёта</h3>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-gray-600 mb-1">Заголовок отчёта</label>
                                <input
                                    type="text"
                                    value={reportOptions.reportTitle}
                                    onChange={(e) => setReportOptions(p => ({ ...p, reportTitle: e.target.value }))}
                                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:border-blue-500 outline-none"
                                />
                            </div>

                            <div className="space-y-3">
                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={reportOptions.includeTableOne}
                                        onChange={(e) => setReportOptions(p => ({ ...p, includeTableOne: e.target.checked }))}
                                        className="w-4 h-4 text-blue-600 rounded"
                                    />
                                    <span className="text-sm">Включить сводную таблицу результатов</span>
                                </label>

                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={reportOptions.includeSignificantOnly}
                                        onChange={(e) => setReportOptions(p => ({ ...p, includeSignificantOnly: e.target.checked }))}
                                        className="w-4 h-4 text-blue-600 rounded"
                                    />
                                    <span className="text-sm">Только значимые результаты (p&lt;0.05)</span>
                                </label>

                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={reportOptions.includeCharts}
                                        onChange={(e) => setReportOptions(p => ({ ...p, includeCharts: e.target.checked }))}
                                        className="w-4 h-4 text-blue-600 rounded"
                                    />
                                    <span className="text-sm">Включить графики (будет добавлено)</span>
                                </label>

                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={reportOptions.includeMethodsSection}
                                        onChange={(e) => setReportOptions(p => ({ ...p, includeMethodsSection: e.target.checked }))}
                                        className="w-4 h-4 text-blue-600 rounded"
                                    />
                                    <span className="text-sm">Раздел "Методы анализа"</span>
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Stats Summary */}
                    <div className="bg-gradient-to-r from-blue-50 to-green-50 rounded-xl border border-gray-200 p-5">
                        <h3 className="text-sm font-semibold text-gray-800 mb-3">Содержание отчёта</h3>
                        <ul className="text-sm text-gray-700 space-y-2">
                            <li className="flex justify-between">
                                <span>Датасет:</span>
                                <span className="font-medium">{datasetName}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Групп:</span>
                                <span className="font-medium">{groups.length}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Всего переменных:</span>
                                <span className="font-medium">{variables.length}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Значимых (p&lt;0.05):</span>
                                <span className="font-medium text-green-600">{significantVars.length}</span>
                            </li>
                            <li className="flex justify-between">
                                <span>Будет в отчёте:</span>
                                <span className="font-medium">
                                    {reportOptions.includeSignificantOnly ? significantVars.length : variables.length}
                                </span>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* Right: Preview */}
                <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                        <h3 className="text-sm font-semibold text-gray-700">Превью отчёта</h3>
                    </div>
                    <div className="p-5 max-h-[60vh] overflow-y-auto">
                        {/* Simulated report preview */}
                        <div className="prose prose-sm max-w-none">
                            <h2 className="text-lg font-bold text-center mb-4">{reportOptions.reportTitle}</h2>
                            <p className="text-gray-600 text-sm mb-4">Файл данных: {datasetName}</p>

                            {reportOptions.includeTableOne && (
                                <>
                                    <h3 className="text-sm font-semibold mt-4 mb-2">Таблица 1. Сводные результаты</h3>
                                    <div className="overflow-x-auto">
                                        <table className="w-full text-xs border-collapse border border-gray-300">
                                            <thead>
                                                <tr className="bg-gray-100">
                                                    <th className="border border-gray-300 px-2 py-1 text-left">Показатель</th>
                                                    {groups.map(g => (
                                                        <th key={g} className="border border-gray-300 px-2 py-1 text-center">Гр. {g}</th>
                                                    ))}
                                                    <th className="border border-gray-300 px-2 py-1 text-center">p</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {(reportOptions.includeSignificantOnly ? significantVars : variables).slice(0, 5).map(v => {
                                                    const r = results[v];
                                                    return (
                                                        <tr key={v}>
                                                            <td className="border border-gray-300 px-2 py-1">{v}</td>
                                                            {groups.map(g => {
                                                                const d = descriptives.find(x => x.variable === v && String(x.group) === String(g));
                                                                return (
                                                                    <td key={g} className="border border-gray-300 px-2 py-1 text-center">
                                                                        {d?.mean?.toFixed(1) || '—'}
                                                                    </td>
                                                                );
                                                            })}
                                                            <td className={`border border-gray-300 px-2 py-1 text-center ${r?.significant ? 'font-bold text-green-700' : ''}`}>
                                                                {r?.p_value != null ? (r.p_value < 0.001 ? '<0.001' : r.p_value.toFixed(3)) : '—'}
                                                            </td>
                                                        </tr>
                                                    );
                                                })}
                                                {variables.length > 5 && (
                                                    <tr><td colSpan={groups.length + 2} className="border border-gray-300 px-2 py-1 text-center text-gray-500">... и ещё {variables.length - 5} показателей</td></tr>
                                                )}
                                            </tbody>
                                        </table>
                                    </div>
                                </>
                            )}

                            {significantVars.length > 0 && (
                                <>
                                    <h3 className="text-sm font-semibold mt-4 mb-2">Статистически значимые различия</h3>
                                    <ul className="text-xs">
                                        {significantVars.slice(0, 3).map(v => (
                                            <li key={v}>• <strong>{v}</strong>: p={results[v]?.p_value?.toFixed(4)}</li>
                                        ))}
                                        {significantVars.length > 3 && <li>... и ещё {significantVars.length - 3}</li>}
                                    </ul>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
                <button onClick={() => navigate(`/charts/${id}`, { state: location.state })} className="text-sm text-gray-600 hover:text-gray-900">
                    ← Назад к графикам
                </button>
                <button
                    onClick={generateAndDownload}
                    disabled={generating}
                    className="px-6 py-3 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition disabled:opacity-50 flex items-center gap-2"
                >
                    {generating ? (
                        <><div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Генерация...</>
                    ) : (
                        '📥 Скачать отчёт (.docx)'
                    )}
                </button>
            </div>
        </div>
    );
}
