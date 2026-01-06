import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getDataset, autoClassifyVariables } from '../../lib/api';

export default function DataPreparation() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [classifying, setClassifying] = useState(false);
    const [error, setError] = useState(null);
    const [columns, setColumns] = useState([]);
    const [datasetName, setDatasetName] = useState('');
    const [classificationSummary, setClassificationSummary] = useState(null);

    // Variable configuration state
    const [variableConfig, setVariableConfig] = useState({});

    useEffect(() => {
        loadDataset();
    }, [id]);

    const loadDataset = async () => {
        try {
            const data = await getDataset(id);
            setDatasetName(data.filename || 'Dataset');

            // Initialize columns from dataset profile
            const cols = data.columns || [];
            setColumns(cols);

            // Initialize variable config
            const config = {};
            cols.forEach(col => {
                config[col.name] = {
                    type: col.type || 'numeric',
                    role: 'parameter',
                    timepoint: null
                };
            });
            setVariableConfig(config);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const updateConfig = (colName, field, value) => {
        setVariableConfig(prev => ({
            ...prev,
            [colName]: {
                ...prev[colName],
                [field]: value
            }
        }));
    };

    const handleAutoClassify = async () => {
        setClassifying(true);
        setError(null);
        try {
            const result = await autoClassifyVariables(id);
            // Apply classification to variable config
            setVariableConfig(result.classification);
            setClassificationSummary(result.summary);
        } catch (err) {
            setError(`Автоклассификация не удалась: ${err.message}`);
        } finally {
            setClassifying(false);
        }
    };

    const handleNext = () => {
        sessionStorage.setItem(`config_${id}`, JSON.stringify(variableConfig));
        navigate(`/analyze/${id}`, { state: { variableConfig } });
    };

    const getGroupColumn = () => {
        return Object.entries(variableConfig).find(([_, cfg]) => cfg.role === 'group')?.[0];
    };

    const getParameterCount = () => {
        return Object.values(variableConfig).filter(cfg => cfg.role === 'parameter').length;
    };

    const getNumericParameterCount = () => {
        return Object.entries(variableConfig).filter(([_, cfg]) =>
            cfg.role === 'parameter' && cfg.type === 'numeric'
        ).length;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="w-8 h-8 border-2 border-gray-200 border-t-blue-600 rounded-full animate-spin" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-6 bg-red-50 border border-red-200 text-red-700 rounded-lg">
                Error: {error}
            </div>
        );
    }

    return (
        <div className="animate-fadeIn">
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h1 className="text-xl font-bold text-gray-900">Подготовка данных</h1>
                    <p className="text-sm text-gray-500 mt-1">{datasetName} • {columns.length} переменных</p>
                </div>
                <button
                    onClick={handleAutoClassify}
                    disabled={classifying}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg hover:from-purple-700 hover:to-blue-700 transition disabled:opacity-50"
                >
                    {classifying ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Анализирую...
                        </>
                    ) : (
                        <>
                            ✨ AI Автоклассификация
                        </>
                    )}
                </button>
            </div>

            {/* Classification Summary */}
            {classificationSummary && (
                <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <p className="text-sm text-green-800">
                        ✅ Классификация завершена: {classificationSummary.roles.parameter} параметров,
                        {' '}{classificationSummary.roles.group} групп,
                        {' '}{classificationSummary.roles.exclude} исключено.
                        {classificationSummary.timepoints.length > 0 && (
                            <> Timepoints: {classificationSummary.timepoints.join(', ')}</>
                        )}
                    </p>
                </div>
            )}

            {/* Table */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-6">
                <table className="w-full text-sm">
                    <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Переменная</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Тип данных</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Роль</th>
                            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Timepoint</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                        {columns.map(col => (
                            <tr key={col.name} className={`hover:bg-gray-50 transition ${variableConfig[col.name]?.role === 'exclude' ? 'opacity-50' : ''}`}>
                                <td className="px-4 py-3 font-medium text-gray-900">{col.name}</td>
                                <td className="px-4 py-3">
                                    <select
                                        value={variableConfig[col.name]?.type || 'numeric'}
                                        onChange={(e) => updateConfig(col.name, 'type', e.target.value)}
                                        className="w-full px-2 py-1 text-sm border border-gray-200 rounded focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                                    >
                                        <option value="numeric">Числовой</option>
                                        <option value="categorical">Категориальный</option>
                                        <option value="date">Дата</option>
                                        <option value="text">Текст</option>
                                    </select>
                                </td>
                                <td className="px-4 py-3">
                                    <select
                                        value={variableConfig[col.name]?.role || 'parameter'}
                                        onChange={(e) => updateConfig(col.name, 'role', e.target.value)}
                                        className={`w-full px-2 py-1 text-sm border rounded focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none ${variableConfig[col.name]?.role === 'group' ? 'border-blue-400 bg-blue-50' :
                                                variableConfig[col.name]?.role === 'exclude' ? 'border-gray-300 bg-gray-100' :
                                                    'border-gray-200'
                                            }`}
                                    >
                                        <option value="parameter">Параметр</option>
                                        <option value="group">Группа</option>
                                        <option value="subgroup">Подгруппа</option>
                                        <option value="exclude">Исключить</option>
                                    </select>
                                </td>
                                <td className="px-4 py-3">
                                    <select
                                        value={variableConfig[col.name]?.timepoint || ''}
                                        onChange={(e) => updateConfig(col.name, 'timepoint', e.target.value || null)}
                                        className={`w-full px-2 py-1 text-sm border rounded focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none ${variableConfig[col.name]?.timepoint ? 'border-purple-400 bg-purple-50' : 'border-gray-200'
                                            }`}
                                    >
                                        <option value="">—</option>
                                        <option value="V0">V0 (Baseline)</option>
                                        <option value="V1">V1</option>
                                        <option value="V2">V2</option>
                                        <option value="V3">V3</option>
                                        <option value="V4">V4</option>
                                        <option value="V5">V5</option>
                                        <option value="V6">V6</option>
                                    </select>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between bg-gray-50 rounded-lg px-6 py-4 border border-gray-200">
                <div className="text-sm text-gray-600">
                    <span className="font-medium">{getNumericParameterCount()}</span> числовых параметров
                    {getGroupColumn() && (
                        <span className="ml-4">
                            Группа: <span className="font-medium text-blue-600">{getGroupColumn()}</span>
                        </span>
                    )}
                </div>
                <button
                    onClick={handleNext}
                    disabled={!getGroupColumn()}
                    className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Далее: Выбор анализа →
                </button>
            </div>
        </div>
    );
}
