import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { runBatchAnalysis, getDataset } from '../../lib/api';

export default function AnalysisSelection() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [datasetName, setDatasetName] = useState('Dataset');
    const [groupValues, setGroupValues] = useState([]);
    const [showExcluded, setShowExcluded] = useState(false);

    // Get config from navigation state or sessionStorage
    const [variableConfig, setVariableConfig] = useState(() => {
        if (location.state?.variableConfig) return location.state.variableConfig;
        const stored = sessionStorage.getItem(`config_${id}`);
        return stored ? JSON.parse(stored) : {};
    });

    // Comparison mode
    const [comparisonMode, setComparisonMode] = useState('between'); // 'between' or 'within'

    // Analysis options
    const [options, setOptions] = useState({
        correction: 'bonferroni',
        alpha: 0.05
    });

    useEffect(() => {
        loadDatasetInfo();
    }, [id]);

    const loadDatasetInfo = async () => {
        try {
            const data = await getDataset(id);
            setDatasetName(data.filename || 'Dataset');

            // Get unique values for group column
            const groupCol = getGroupColumn();
            if (groupCol && data.head) {
                const values = [...new Set(data.head.map(row => row[groupCol]).filter(Boolean))];
                setGroupValues(values.slice(0, 5)); // Show first 5 values
            }
        } catch (e) { }
    };

    const getGroupColumn = () => {
        return Object.entries(variableConfig).find(([_, cfg]) => cfg.role === 'group')?.[0];
    };

    const getNumericParameters = () => {
        return Object.entries(variableConfig)
            .filter(([_, cfg]) => cfg.role === 'parameter' && cfg.type === 'numeric')
            .map(([name]) => name);
    };

    const getExcludedVariables = () => {
        return Object.entries(variableConfig)
            .filter(([_, cfg]) => cfg.role === 'exclude' || (cfg.role === 'parameter' && cfg.type !== 'numeric'))
            .map(([name, cfg]) => ({ name, reason: cfg.reason || 'Не числовой тип' }));
    };

    const handleRunAnalysis = async () => {
        const groupCol = getGroupColumn();
        const params = getNumericParameters();

        if (!groupCol || params.length === 0) {
            setError('Выберите группу и хотя бы один числовой параметр');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const result = await runBatchAnalysis(id, params, groupCol, {
                ...options,
                paired: comparisonMode === 'within'
            });
            navigate(`/results/${id}`, { state: { result, variableConfig } });
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const numericParams = getNumericParameters();
    const excludedVars = getExcludedVariables();
    const groupColumn = getGroupColumn();

    return (
        <div className="animate-fadeIn max-w-3xl mx-auto">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-gray-900">Конструктор анализа</h1>
                <p className="text-sm text-gray-500 mt-1">{datasetName}</p>
            </div>

            {/* Error */}
            {error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                    {error}
                </div>
            )}

            {/* Section 1: What are we analyzing? */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
                    Что анализируем?
                </h2>

                <div className="space-y-3">
                    <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <div>
                            <p className="font-medium text-gray-900">{numericParams.length} числовых параметров</p>
                            <p className="text-sm text-gray-500 mt-1">
                                {numericParams.slice(0, 3).join(', ')}{numericParams.length > 3 ? '...' : ''}
                            </p>
                        </div>
                        <div className="text-2xl">📊</div>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-purple-50 rounded-lg border border-purple-100">
                        <div>
                            <p className="font-medium text-gray-900">
                                Группа: <span className="text-purple-600">{groupColumn || 'Не выбрана'}</span>
                            </p>
                            {groupValues.length > 0 && (
                                <p className="text-sm text-gray-500 mt-1">
                                    Значения: {groupValues.join(', ')}{groupValues.length >= 5 ? '...' : ''}
                                </p>
                            )}
                        </div>
                        <div className="text-2xl">👥</div>
                    </div>
                </div>
            </div>

            {/* Section 2: How are we comparing? */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
                    Как сравниваем?
                </h2>

                <div className="space-y-3">
                    <label
                        className={`flex items-start p-4 rounded-lg border-2 cursor-pointer transition ${comparisonMode === 'between'
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                        onClick={() => setComparisonMode('between')}
                    >
                        <input
                            type="radio"
                            checked={comparisonMode === 'between'}
                            onChange={() => setComparisonMode('between')}
                            className="mt-1 w-4 h-4 text-blue-600"
                        />
                        <div className="ml-3">
                            <p className="font-medium text-gray-900">Между группами (независимые)</p>
                            <p className="text-sm text-gray-500 mt-1">
                                Сравнить значения параметров между разными группами пациентов
                            </p>
                            <p className="text-xs text-gray-400 mt-2">
                                → T-test, Mann-Whitney, ANOVA, Kruskal-Wallis
                            </p>
                        </div>
                    </label>

                    <label
                        className={`flex items-start p-4 rounded-lg border-2 cursor-pointer transition ${comparisonMode === 'within'
                                ? 'border-blue-500 bg-blue-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                        onClick={() => setComparisonMode('within')}
                    >
                        <input
                            type="radio"
                            checked={comparisonMode === 'within'}
                            onChange={() => setComparisonMode('within')}
                            className="mt-1 w-4 h-4 text-blue-600"
                        />
                        <div className="ml-3">
                            <p className="font-medium text-gray-900">Внутри группы по времени (парные)</p>
                            <p className="text-sm text-gray-500 mt-1">
                                Сравнить значения одних и тех же пациентов в разные визиты
                            </p>
                            <p className="text-xs text-gray-400 mt-2">
                                → Парный T-test, Wilcoxon, RM-ANOVA, Friedman
                            </p>
                        </div>
                    </label>
                </div>
            </div>

            {/* Section 3: Settings */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-4">
                    Настройки
                </h2>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Коррекция множественных сравнений
                        </label>
                        <select
                            value={options.correction}
                            onChange={(e) => setOptions(prev => ({ ...prev, correction: e.target.value }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                        >
                            <option value="none">Без коррекции</option>
                            <option value="bonferroni">Bonferroni</option>
                            <option value="holm">Holm</option>
                            <option value="fdr_bh">Benjamini-Hochberg (FDR)</option>
                        </select>
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Уровень значимости (α)
                        </label>
                        <select
                            value={options.alpha}
                            onChange={(e) => setOptions(prev => ({ ...prev, alpha: parseFloat(e.target.value) }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                        >
                            <option value={0.05}>0.05</option>
                            <option value={0.01}>0.01</option>
                            <option value={0.001}>0.001</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Section 4: Excluded variables */}
            {excludedVars.length > 0 && (
                <div className="bg-amber-50 rounded-xl border border-amber-200 p-4 mb-6">
                    <button
                        onClick={() => setShowExcluded(!showExcluded)}
                        className="flex items-center justify-between w-full text-left"
                    >
                        <div className="flex items-center gap-2 text-amber-800">
                            <span>⚠️</span>
                            <span className="font-medium">
                                {excludedVars.length} переменных исключены из анализа
                            </span>
                        </div>
                        <span className="text-amber-600 text-sm">
                            {showExcluded ? 'Скрыть' : 'Показать'}
                        </span>
                    </button>

                    {showExcluded && (
                        <div className="mt-4 space-y-2 max-h-48 overflow-y-auto">
                            {excludedVars.map(v => (
                                <div key={v.name} className="flex justify-between text-sm py-1 border-b border-amber-200 last:border-0">
                                    <span className="text-gray-700">{v.name}</span>
                                    <span className="text-amber-600">{v.reason}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Footer Actions */}
            <div className="flex items-center justify-between">
                <button
                    onClick={() => navigate(`/data/${id}`)}
                    className="text-sm text-gray-600 hover:text-gray-900"
                >
                    ← Назад к данным
                </button>
                <button
                    onClick={handleRunAnalysis}
                    disabled={loading || !groupColumn || numericParams.length === 0}
                    className="px-8 py-3 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                    {loading ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Выполняется...
                        </>
                    ) : (
                        'Запустить анализ'
                    )}
                </button>
            </div>
        </div>
    );
}
