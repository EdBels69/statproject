// Copilot Page - Chat-First Statistical Analysis
import { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
    getDatasets,
    getDataset,
    getDatasetReport,
    analysisPlan,
    executeProtocolV2,
    downloadProtocolReport,
    uploadKnowledgeFile,
    listKnowledgeDocs,
    listKnowledgeCatalog,
    deleteKnowledgeDoc,
    generatePromptBrief,
    getStudyDesign,
    getDatasetDesignReview,
    getDatasetAnalysisSet,
    confirmDatasetDesignReview,
    revokeDatasetDesignReview,
    freezeDatasetAnalysisSet,
    getVariableMapping,
    putVariableMapping,
    downloadCopilotReportPdf,
} from '../../lib/api';
import { buildAnalysisSetFreezeSpec } from '../../app/utils/analysisSet';

// ...

const TokenCounter = ({ usage }) => {
    if (!usage) return null;

    // Estimate price (very rough average, e.g. based on Gemini Flash ~$0.20/1M)
    // 1M tokens = $0.20 -> 1 token = $0.0000002
    // 1000 tokens = $0.0002
    // Let's use a generic rate for visualization: $0.50 / 1M input, $1.50 / 1M output
    const inputCost = (usage.prompt_tokens / 1_000_000) * 0.50;
    const outputCost = (usage.completion_tokens / 1_000_000) * 1.50;
    const totalCost = inputCost + outputCost;
    const rubleRate = 100; // 1 USD = 100 RUB

    return (
        <div className="flex items-center gap-4 text-xs font-mono text-gray-500 bg-gray-50 px-3 py-1.5 rounded border border-gray-200">
            <div className="flex items-center gap-1">
                <span className="text-gray-400">⬆️</span>
                <span>{usage.prompt_tokens?.toLocaleString()} in</span>
            </div>
            <div className="w-px h-3 bg-gray-300"></div>
            <div className="flex items-center gap-1">
                <span className="text-gray-400">⬇️</span>
                <span>{usage.completion_tokens?.toLocaleString()} out</span>
            </div>
            <div className="w-px h-3 bg-gray-300"></div>
            <div className="flex items-center gap-1">
                <span className="text-gray-400">∑</span>
                <span className="font-semibold">{usage.total_tokens?.toLocaleString()}</span>
            </div>
            <div className="w-px h-3 bg-gray-300"></div>
            <div className="flex items-center gap-1 text-green-700">
                <span>💰</span>
                <span>~{(totalCost * rubleRate).toFixed(2)}₽</span>
            </div>
        </div>
    );
};

// New Component: Data Summary Card
const DataSummaryCard = ({ report }) => {
    if (!report) return null;

    const profile = report.profile || {};
    const issues = report.scan_report?.issues || [];
    const missing = report.scan_report?.missing_report || {};
    const columns = report.scan_report?.columns || {};

    // Calculate stats
    const numericCount = Object.values(columns).filter((c) => {
        const t = String(c?.type || '').toLowerCase();
        return t.includes('int') || t.includes('float') || t.includes('double') || t.includes('number') || t === 'numeric';
    }).length;
    const catCount = Object.values(columns).filter((c) => {
        const t = String(c?.type || '').toLowerCase();
        return t.includes('object') || t.includes('category') || t.includes('bool') || t === 'categorical' || t === 'text';
    }).length;

    return (
        <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6 shadow-sm animate-fadeIn">
            <div className="flex flex-wrap gap-6 items-start">
                {/* Basic Stats */}
                <div className="flex-1 min-w-[200px]">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Обзор данных</h3>
                    <div className="flex items-center gap-4">
                        <div className="text-2xl font-bold text-gray-900">
                            {profile.row_count?.toLocaleString()} <span className="text-sm font-normal text-gray-400">строк</span>
                        </div>
                        <div className="w-px h-8 bg-gray-200"></div>
                        <div className="text-2xl font-bold text-gray-900">
                            {profile.col_count?.toLocaleString()} <span className="text-sm font-normal text-gray-400">колонок</span>
                        </div>
                    </div>
                    <div className="flex gap-3 mt-2 text-xs text-gray-500">
                        <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-100">
                            🔢 {numericCount} числовых
                        </span>
                        <span className="px-2 py-1 bg-purple-50 text-purple-700 rounded-full border border-purple-100">
                            🔤 {catCount} категориальных
                        </span>
                    </div>
                </div>

                {/* Quality Health */}
                <div className="flex-1 min-w-[200px]">
                    <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">Качество данных</h3>
                    {issues.length === 0 ? (
                        <div className="flex items-center gap-2 text-green-700 bg-green-50 px-3 py-2 rounded-lg border border-green-100">
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                            <span className="font-medium">Проблем не найдено</span>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {missing.columns_with_missing > 0 && (
                                <div className="flex items-center gap-2 text-amber-700 bg-amber-50 px-2 py-1 rounded text-xs font-medium border border-amber-100">
                                    <span>⚠️ Пропуски в {missing.columns_with_missing} колонках</span>
                                </div>
                            )}
                            {issues.some(i => i.type === 'mixed_type') && (
                                <div className="flex items-center gap-2 text-red-700 bg-red-50 px-2 py-1 rounded text-xs font-medium border border-red-100">
                                    <span>❌ Найдены смешанные типы данных</span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

const DEFAULT_ROLE_MODEL = 'google/gemini-2.5-flash';
const ROLE_MODEL_OPTIONS_PLANNER = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_SEMANTICS = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_INTERPRET = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_REPORT = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_CODEGEN = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'deepseek/deepseek-chat-v3-0324:floor', label: '🏆 DeepSeek V3.2 (рекомендуется)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'z-ai/glm-4.7', label: 'z-ai/glm-4.7' },
    { value: 'z-ai/glm-4.7-flash', label: 'z-ai/glm-4.7-flash' },
    { value: 'qwen/qwen3-coder-next', label: 'qwen/qwen3-coder-next' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];

function parseCsvColumns(value) {
    return Array.from(
        new Set(
            String(value || '')
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean)
        )
    );
}

function normalizeList(values, allowedColumns) {
    const allowed = new Set(Array.isArray(allowedColumns) ? allowedColumns : []);
    const out = [];
    (Array.isArray(values) ? values : []).forEach((item) => {
        const name = String(item || '').trim();
        if (!name) return;
        if (allowed.size > 0 && !allowed.has(name)) return;
        if (!out.includes(name)) out.push(name);
    });
    return out;
}

function applyRoleOverride(mapping, column, role) {
    if (!column) return;
    const next = mapping[column] && typeof mapping[column] === 'object' ? { ...mapping[column] } : {};
    next.role = role;
    mapping[column] = next;
}

function toPlainObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function profileColumnsToScanColumns(profileColumns) {
    if (!Array.isArray(profileColumns)) return {};
    const out = {};
    profileColumns.forEach((entry) => {
        if (!entry || typeof entry !== 'object') return;
        const name = String(entry.name || '').trim();
        if (!name) return;
        out[name] = {
            type: String(entry.type || ''),
            missing_count: Number.isFinite(Number(entry.missing_count)) ? Number(entry.missing_count) : 0,
            unique_count: Number.isFinite(Number(entry.unique_count)) ? Number(entry.unique_count) : 0,
        };
    });
    return out;
}

function normalizeDatasetReportPayload(reportRaw, profileRaw) {
    const reportObj = toPlainObject(reportRaw);
    const profileObj = toPlainObject(profileRaw);
    const profileFromReport = toPlainObject(reportObj.profile);
    const scanFromNested = toPlainObject(reportObj.scan_report);
    const scanRoot = reportObj.columns || reportObj.issues || reportObj.missing_report ? reportObj : {};
    const scan = Object.keys(scanFromNested).length > 0 ? scanFromNested : toPlainObject(scanRoot);
    let columns = toPlainObject(scan.columns);

    if (!Object.keys(columns).length) {
        columns = profileColumnsToScanColumns(profileObj.columns || profileFromReport.columns || []);
    }

    const profile = {
        ...profileObj,
        ...profileFromReport,
    };

    if (!Number.isFinite(Number(profile.row_count)) && Number.isFinite(Number(reportObj.row_count))) {
        profile.row_count = Number(reportObj.row_count);
    }
    if (!Number.isFinite(Number(profile.col_count)) && Number.isFinite(Number(reportObj.col_count))) {
        profile.col_count = Number(reportObj.col_count);
    }
    if (!Number.isFinite(Number(profile.col_count)) && Object.keys(columns).length) {
        profile.col_count = Object.keys(columns).length;
    }

    return {
        ...reportObj,
        profile,
        scan_report: {
            ...scan,
            columns,
            issues: Array.isArray(scan.issues) ? scan.issues : [],
            missing_report: toPlainObject(scan.missing_report),
        },
    };
}

const WIZARD_STEPS = ['Данные', 'Промпт', 'План AI', 'Выполнение', 'Отчёт'];

function StepIndicator({ currentStep, steps }) {
    return (
        <div style={{ display: 'flex', gap: '4px', marginBottom: '24px', padding: '0 4px' }}>
            {steps.map((label, i) => {
                const stepNum = i + 1;
                const isActive = stepNum === currentStep;
                const isDone = stepNum < currentStep;
                return (
                    <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                        <div style={{
                            height: '4px',
                            borderRadius: '2px',
                            background: isDone ? '#22c55e' : isActive ? '#f97316' : '#27272a',
                            transition: 'background 0.3s'
                        }} />
                        <span style={{
                            fontSize: '11px',
                            color: isActive ? '#f97316' : isDone ? '#22c55e' : '#71717a',
                            marginTop: '4px',
                            display: 'block'
                        }}>
                            {stepNum}. {label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}

export default function CopilotPage() {
    const location = useLocation();
    const [datasets, setDatasets] = useState([]);
    const [selectedDataset, setSelectedDataset] = useState('');
    const [wizardStep, setWizardStep] = useState(1); // NEW: Wizard step state
    const [datasetReport, setDatasetReport] = useState(null); // NEW
    const [userRequest, setUserRequest] = useState('');
    const [analysis, setAnalysis] = useState(null);
    const [runId, setRunId] = useState(null);
    const [loading, setLoading] = useState(false);
    const [briefLoading, setBriefLoading] = useState(false);
    const [filesLoading, setFilesLoading] = useState(true); // NEW
    const [error, setError] = useState(null);
    const [briefError, setBriefError] = useState(null);
    const [refinement, setRefinement] = useState('');
    const [analysisMode, setAnalysisMode] = useState('exploratory');
    const [multiplicityCorrection, setMultiplicityCorrection] = useState('fdr_bh');
    const [useKnowledgeBase, setUseKnowledgeBase] = useState(true);
    const [smartSamplingMode, setSmartSamplingMode] = useState('off');
    const [rawSampleConfirmed, setRawSampleConfirmed] = useState(false);
    const [llmChunkPlan, setLlmChunkPlan] = useState(false);
    const [llmChunkSize, setLlmChunkSize] = useState(30);
    const [analysisEngine, setAnalysisEngine] = useState('python');
    const [plotEngine, setPlotEngine] = useState('python');
    const [primaryOutcome, setPrimaryOutcome] = useState('');
    const [groupColumnOverride, setGroupColumnOverride] = useState('');
    const [timeColumnOverride, setTimeColumnOverride] = useState('');
    const [subjectColumnOverride, setSubjectColumnOverride] = useState('');
    const [subgroupColumns, setSubgroupColumns] = useState('');
    const [studyDesign, setStudyDesign] = useState(null);
    const [variableMapping, setVariableMapping] = useState({});
    const [numericOutcomesSelection, setNumericOutcomesSelection] = useState([]);
    const [categoricalOutcomesSelection, setCategoricalOutcomesSelection] = useState([]);
    const [numericOutcomeSearch, setNumericOutcomeSearch] = useState('');
    const [categoricalOutcomeSearch, setCategoricalOutcomeSearch] = useState('');
    const [designLoading, setDesignLoading] = useState(false);
    const [designSaving, setDesignSaving] = useState(false);
    const [designError, setDesignError] = useState(null);
    const [designConfirmed, setDesignConfirmed] = useState(false);
    const [designReviewTimestamp, setDesignReviewTimestamp] = useState(null);
    const [analysisSetDoc, setAnalysisSetDoc] = useState(null);
    const [analysisSetBusy, setAnalysisSetBusy] = useState(false);
    const [modelPlanner, setModelPlanner] = useState(DEFAULT_ROLE_MODEL);
    const [modelQuality, setModelQuality] = useState(DEFAULT_ROLE_MODEL);
    const [modelReport, setModelReport] = useState(DEFAULT_ROLE_MODEL);
    const [modelInterpret, setModelInterpret] = useState(DEFAULT_ROLE_MODEL);
    const [modelCodegen, setModelCodegen] = useState(DEFAULT_ROLE_MODEL);

    const [knowledgeDocs, setKnowledgeDocs] = useState([]);
    const [knowledgeLoading, setKnowledgeLoading] = useState(false);
    const [knowledgeUploadLoading, setKnowledgeUploadLoading] = useState(false);
    const [knowledgeError, setKnowledgeError] = useState(null);
    const [knowledgeTitle, setKnowledgeTitle] = useState('');
    const [knowledgeTags, setKnowledgeTags] = useState('');
    const [knowledgeFile, setKnowledgeFile] = useState(null);
    const [knowledgeCatalog, setKnowledgeCatalog] = useState([]);
    const [catalogLoading, setCatalogLoading] = useState(false);
    const [catalogError, setCatalogError] = useState(null);
    const [catalogQuery, setCatalogQuery] = useState('');
    const rawSampleRequested = smartSamplingMode === 'raw';
    const effectiveSmartSamplingMode = rawSampleRequested && !rawSampleConfirmed ? 'masked' : smartSamplingMode;
    const useSmartSampling = effectiveSmartSamplingMode !== 'off';

    const buildRoleModels = () => {
        const models = {
            planner: modelPlanner,
            quality: modelQuality,
            report: modelReport,
            interpret: modelInterpret,
            codegen: modelCodegen,
        };
        return Object.fromEntries(Object.entries(models).filter(([, value]) => value));
    };

    const loadDatasets = useCallback(async () => {
        setFilesLoading(true); // NEW
        try {
            const data = await getDatasets();
            setDatasets(data);

            if (location.state?.datasetId) {
                const found = data.find(d => d.id === location.state.datasetId);
                if (found) {
                    setSelectedDataset(found.id);
                }
            }
        } catch (err) {
            console.error('Failed to load datasets:', err);
        } finally {
            setFilesLoading(false); // NEW
        }
    }, [location.state?.datasetId]);

    const loadReport = useCallback(async (id) => {
        try {
            const [report, profile] = await Promise.all([
                getDatasetReport(id).catch(() => null),
                getDataset(id, 1, 1).catch(() => null),
            ]);
            setDatasetReport(normalizeDatasetReportPayload(report, profile));
        } catch (err) {
            console.error("Failed to load report", err);
            setDatasetReport(normalizeDatasetReportPayload(null, null));
        }
    }, []);

    const loadDesign = useCallback(async (id) => {
        if (!id) {
            setStudyDesign(null);
            setVariableMapping({});
            setNumericOutcomesSelection([]);
            setCategoricalOutcomesSelection([]);
            setNumericOutcomeSearch('');
            setCategoricalOutcomeSearch('');
            setPrimaryOutcome('');
            setGroupColumnOverride('');
            setTimeColumnOverride('');
            setSubjectColumnOverride('');
            setSubgroupColumns('');
            setDesignConfirmed(false);
            setDesignReviewTimestamp(null);
            setAnalysisSetDoc(null);
            return;
        }
        setDesignLoading(true);
        setDesignError(null);
        try {
            const [designDoc, mappingDoc, designReviewDoc] = await Promise.all([
                getStudyDesign(id),
                getVariableMapping(id),
                getDatasetDesignReview(id),
            ]);
            const designPayload = designDoc && typeof designDoc === 'object' ? designDoc : {};
            const design = designPayload?.design && typeof designPayload.design === 'object' ? designPayload.design : {};
            const mappingPayload = mappingDoc?.mapping && typeof mappingDoc.mapping === 'object' ? mappingDoc.mapping : {};
            const reviewPayload = designReviewDoc && typeof designReviewDoc === 'object' ? designReviewDoc : {};
            const mappedSubgroups = Object.entries(mappingPayload)
                .filter(([, entry]) => entry && typeof entry === 'object' && entry.subgroup)
                .map(([name]) => name);

            const allDesignColumns = Object.keys(designPayload?.columns || {});
            const numericOutcomes = normalizeList(design?.outcomes, allDesignColumns);
            const categoricalOutcomes = normalizeList(design?.categorical_outcomes, allDesignColumns);
            const outcomeDefaults = [...numericOutcomes, ...categoricalOutcomes];

            setStudyDesign(designPayload);
            setVariableMapping(mappingPayload);
            setNumericOutcomesSelection(numericOutcomes);
            setCategoricalOutcomesSelection(categoricalOutcomes);
            setNumericOutcomeSearch('');
            setCategoricalOutcomeSearch('');
            setPrimaryOutcome(outcomeDefaults[0] || '');
            setGroupColumnOverride(design?.group_column || '');
            setTimeColumnOverride(design?.time_column || '');
            setSubjectColumnOverride(design?.subject_column || '');
            setSubgroupColumns(mappedSubgroups.join(', '));
            const confirmed = Boolean(reviewPayload?.confirmed);
            setDesignConfirmed(confirmed);
            setDesignReviewTimestamp(
                confirmed && typeof reviewPayload?.confirmed_at === 'string'
                    ? reviewPayload.confirmed_at
                    : null
            );
        } catch (err) {
            setDesignError(err?.message || 'Не удалось загрузить дизайн исследования');
            setStudyDesign(null);
            setVariableMapping({});
            setNumericOutcomesSelection([]);
            setCategoricalOutcomesSelection([]);
            setNumericOutcomeSearch('');
            setCategoricalOutcomeSearch('');
            setDesignConfirmed(false);
            setDesignReviewTimestamp(null);
        } finally {
            setDesignLoading(false);
        }
    }, []);

    const loadAnalysisSet = useCallback(async (id) => {
        if (!id) {
            setAnalysisSetDoc(null);
            return;
        }
        try {
            const doc = await getDatasetAnalysisSet(id);
            setAnalysisSetDoc(doc && typeof doc === 'object' ? doc : null);
        } catch {
            setAnalysisSetDoc(null);
        }
    }, []);

    const loadKnowledgeDocs = useCallback(async () => {
        setKnowledgeLoading(true);
        setKnowledgeError(null);
        try {
            const res = await listKnowledgeDocs();
            const docs = Array.isArray(res?.docs) ? res.docs : [];
            setKnowledgeDocs(docs);
        } catch (err) {
            setKnowledgeError(err?.message || 'Не удалось загрузить базу знаний');
        } finally {
            setKnowledgeLoading(false);
        }
    }, []);

    const loadKnowledgeCatalog = useCallback(async () => {
        setCatalogLoading(true);
        setCatalogError(null);
        try {
            const res = await listKnowledgeCatalog();
            const docs = Array.isArray(res?.docs) ? res.docs : [];
            setKnowledgeCatalog(docs);
        } catch (err) {
            setCatalogError(err?.message || 'Не удалось загрузить каталог');
        } finally {
            setCatalogLoading(false);
        }
    }, []);

    useEffect(() => {
        loadDatasets();
    }, [loadDatasets]);

    useEffect(() => {
        loadKnowledgeDocs();
    }, [loadKnowledgeDocs]);

    useEffect(() => {
        loadKnowledgeCatalog();
    }, [loadKnowledgeCatalog]);

    const ensurePublicationAnalysisSet = useCallback(async (protocolForRun = [], cohortPlan = null) => {
        if (!selectedDataset) {
            throw new Error('Выберите датасет перед запуском publication режима');
        }
        const enforce = String(cohortPlan?.enforce || 'models').trim() || 'models';
        const strict = cohortPlan?.strict !== false;
        let analysisSet = analysisSetDoc && typeof analysisSetDoc === 'object' ? analysisSetDoc : null;

        if (!analysisSet?.artifact_exists || !analysisSet?.analysis_set_id) {
            const mode = String(cohortPlan?.mode || 'complete_case').trim() || 'complete_case';
            let requiredNonMissing = Array.isArray(cohortPlan?.required_non_missing) ? cohortPlan.required_non_missing : [];
            let imputeColumns = Array.isArray(cohortPlan?.impute_columns) ? cohortPlan.impute_columns : [];

            if (!requiredNonMissing.length) {
                const spec = buildAnalysisSetFreezeSpec(protocolForRun, { mode });
                if (!spec) {
                    throw new Error(
                        'Publication mode требует fixed cohort: не удалось автоматически собрать freeze-спецификацию из протокола.'
                    );
                }
                requiredNonMissing = spec.required_non_missing;
                imputeColumns = spec.impute_columns;
            }

            if (!requiredNonMissing.length) {
                throw new Error('Publication mode требует непустой required_non_missing для заморозки когорты.');
            }

            setAnalysisSetBusy(true);
            const frozen = await freezeDatasetAnalysisSet(selectedDataset, {
                actor: 'user',
                source: 'copilot_auto_publication',
                mode,
                enforce,
                required_non_missing: requiredNonMissing,
                impute_columns: imputeColumns,
                notes: ['auto_freeze_publication_mode'],
            });
            setAnalysisSetBusy(false);
            analysisSet = frozen && typeof frozen === 'object' ? frozen : null;
            setAnalysisSetDoc(analysisSet);
        }

        const analysisSetId = String(analysisSet?.analysis_set_id || '').trim();
        if (!analysisSetId) {
            throw new Error('Не удалось получить analysis_set_id для publication режима.');
        }

        return {
            analysis_set_id: analysisSetId,
            analysis_set_enforce: String(analysisSet?.enforce || enforce || 'models'),
            analysis_set_strict: Boolean(strict),
        };
    }, [analysisSetDoc, selectedDataset]);

    const handleExecute = async () => {
        if (!analysis?.protocol || !selectedDataset) return;
        if (!designConfirmed) {
            setError('Подтвердите дизайн исследования перед выполнением');
            return;
        }
        setWizardStep(4); // Advance to "Execute" step
        setLoading(true);
        setError(null);
        try {
            const llmModels = buildRoleModels();
            const analysisModeResolved = String(
                analysis?.analysis_mode
                || analysis?.globals?.analysis_mode
                || analysis?.globals?.mode
                || analysisMode
                || 'exploratory'
            ).trim().toLowerCase();
            const publicationMode = analysisModeResolved === 'publication';
            const mergedGlobals = {
                ...(analysis?.globals || {}),
                ...(Object.keys(llmModels || {}).length ? { llm_models: llmModels } : {}),
                analysis_mode: analysisModeResolved,
                mode: analysisModeResolved,
                stats_engine: analysisEngine,
                plot_engine: plotEngine,
                design_confirmed: true,
                design_review_timestamp: designReviewTimestamp || new Date().toISOString(),
                design_snapshot: {
                    group_column: groupColumnOverride || null,
                    time_column: timeColumnOverride || null,
                    subject_column: subjectColumnOverride || null,
                    primary_outcome: primaryOutcome || null,
                    subgroup_columns: parseCsvColumns(subgroupColumns),
                },
            };
            if (publicationMode) {
                const cohortPlan = analysis?.cohort_plan && typeof analysis.cohort_plan === 'object'
                    ? analysis.cohort_plan
                    : null;
                const cohortGlobals = await ensurePublicationAnalysisSet(analysis?.protocol || [], cohortPlan);
                Object.assign(mergedGlobals, cohortGlobals);
            }
            const res = await executeProtocolV2(
                selectedDataset,
                analysis.protocol,
                null,
                analysis.protocol_name,
                mergedGlobals
            );
            setRunId(res?.run_id || null);
            setAnalysis(prev => ({
                ...(prev || {}),
                run_id: res?.run_id,
                result_ir: res?.result_ir,
                status: res?.status || prev?.status,
                errors: res?.errors || [],
            }));
            setWizardStep(5); // Advance to "Report" step
        } catch (err) {
            setError(err?.message || 'Не удалось выполнить протокол');
        } finally {
            setAnalysisSetBusy(false);
            setLoading(false);
        }
    };

    // NEW: Fetch report when dataset changes
    useEffect(() => {
        if (selectedDataset) {
            loadReport(selectedDataset);
            loadDesign(selectedDataset);
            loadAnalysisSet(selectedDataset);
        } else {
            setDatasetReport(null);
            setStudyDesign(null);
            setVariableMapping({});
            setNumericOutcomesSelection([]);
            setCategoricalOutcomesSelection([]);
            setNumericOutcomeSearch('');
            setCategoricalOutcomeSearch('');
            setDesignConfirmed(false);
            setDesignReviewTimestamp(null);
            setAnalysisSetDoc(null);
        }
    }, [selectedDataset, loadReport, loadDesign, loadAnalysisSet]);

    useEffect(() => {
        if (smartSamplingMode !== 'raw') {
            setRawSampleConfirmed(false);
        }
    }, [smartSamplingMode]);

    const markDesignDirty = useCallback(() => {
        if (!designConfirmed) return;
        setDesignConfirmed(false);
        setDesignReviewTimestamp(null);
        setDesignError(null);
        if (!selectedDataset) return;

        void (async () => {
            try {
                await revokeDatasetDesignReview(selectedDataset, {
                    actor: 'user',
                    source: 'copilot',
                    reason: 'design_inputs_changed',
                });
            } catch (err) {
                setDesignError(err?.message || 'Не удалось снять подтверждение дизайна');
            }
        })();
    }, [designConfirmed, selectedDataset]);

    const handleConfirmDesign = async () => {
        if (!selectedDataset) {
            setDesignError('Выберите датасет');
            return;
        }
        setDesignSaving(true);
        setDesignError(null);
        setError(null);
        try {
            const currentMapping = variableMapping && typeof variableMapping === 'object' ? variableMapping : {};
            const scanColumns = Object.keys(datasetReport?.scan_report?.columns || {});
            const designColumns = Object.keys(studyDesign?.columns || {});
            const knownColumns = Array.from(new Set([...scanColumns, ...designColumns, ...Object.keys(currentMapping)]));
            const subgroups = parseCsvColumns(subgroupColumns);
            const selectedNumericOutcomes = normalizeList(numericOutcomesSelection, knownColumns);
            const selectedCategoricalOutcomes = normalizeList(categoricalOutcomesSelection, knownColumns);
            const nextMapping = {};

            knownColumns.forEach((column) => {
                const currentEntry = currentMapping[column] && typeof currentMapping[column] === 'object'
                    ? { ...currentMapping[column] }
                    : {};

                if ([
                    'group',
                    'time',
                    'subject',
                    'outcome',
                    'numeric_outcome',
                    'categorical_outcome',
                    'binary_outcome',
                    'endpoint',
                    'target',
                    'predictor',
                    'exclude',
                    'ignore',
                ].includes(String(currentEntry.role || '').trim().toLowerCase())) {
                    delete currentEntry.role;
                }
                if (Object.prototype.hasOwnProperty.call(currentEntry, 'subgroup')) {
                    delete currentEntry.subgroup;
                }

                nextMapping[column] = currentEntry;
            });

            applyRoleOverride(nextMapping, groupColumnOverride, 'group');
            applyRoleOverride(nextMapping, timeColumnOverride, 'time');
            applyRoleOverride(nextMapping, subjectColumnOverride, 'subject');
            applyRoleOverride(nextMapping, primaryOutcome, 'outcome');
            selectedNumericOutcomes.forEach((column) => {
                applyRoleOverride(nextMapping, column, 'outcome');
            });
            selectedCategoricalOutcomes.forEach((column) => {
                applyRoleOverride(nextMapping, column, 'categorical_outcome');
            });

            subgroups.forEach((column) => {
                const currentEntry = nextMapping[column] && typeof nextMapping[column] === 'object'
                    ? { ...nextMapping[column] }
                    : {};
                currentEntry.subgroup = 'user';
                nextMapping[column] = currentEntry;
            });

            Object.keys(nextMapping).forEach((column) => {
                const entry = nextMapping[column];
                if (!entry || typeof entry !== 'object' || Object.keys(entry).length === 0) {
                    delete nextMapping[column];
                }
            });

            await putVariableMapping(selectedDataset, nextMapping);
            setVariableMapping(nextMapping);
            const reviewPayload = await confirmDatasetDesignReview(selectedDataset, {
                actor: 'user',
                source: 'copilot',
                details: {
                    group_column: groupColumnOverride || null,
                    time_column: timeColumnOverride || null,
                    subject_column: subjectColumnOverride || null,
                    primary_outcome: primaryOutcome || null,
                    numeric_outcomes: selectedNumericOutcomes,
                    categorical_outcomes: selectedCategoricalOutcomes,
                    subgroup_columns: subgroups,
                },
            });
            const confirmed = Boolean(reviewPayload?.confirmed);
            setDesignConfirmed(confirmed);
            setDesignReviewTimestamp(
                confirmed && typeof reviewPayload?.confirmed_at === 'string'
                    ? reviewPayload.confirmed_at
                    : null
            );
            await loadDesign(selectedDataset);
            setAnalysis(null);
            setRunId(null);
        } catch (err) {
            setDesignError(err?.message || 'Не удалось сохранить дизайн');
            setDesignConfirmed(false);
            setDesignReviewTimestamp(null);
        } finally {
            setDesignSaving(false);
        }
    };

    const handleGenerateBrief = async () => {
        if (!selectedDataset) {
            setBriefError('Выберите датасет');
            return;
        }
        if (!designConfirmed) {
            setBriefError('Подтвердите дизайн исследования перед генерацией брифа');
            return;
        }
        setBriefLoading(true);
        setBriefError(null);
        try {
            const chunkSize = Number.isFinite(Number(llmChunkSize)) ? Number(llmChunkSize) : 30;
            const preferences = {
                analysis_mode: analysisMode,
                allow_data_mining: analysisMode === 'exploratory',
                multiplicity_correction: multiplicityCorrection,
                post_hoc_correction: multiplicityCorrection,
                use_knowledge_base: useKnowledgeBase,
                smart_sampling: useSmartSampling,
                smart_sampling_mode: effectiveSmartSamplingMode,
                llm_chunk_plan: llmChunkPlan,
                llm_chunk_size: chunkSize,
                primary_outcome: primaryOutcome || null,
                group_column: groupColumnOverride || null,
                time_column: timeColumnOverride || null,
                subject_column: subjectColumnOverride || null,
                subgroup_columns: subgroupColumns || null,
                design_confirmed: true,
            };
            const res = await generatePromptBrief(selectedDataset, preferences);
            if (res?.prompt) {
                setUserRequest(res.prompt);
            }
        } catch (err) {
            setBriefError(err?.message || 'Не удалось сформировать бриф');
        } finally {
            setBriefLoading(false);
        }
    };

    const handlePlan = async () => {
        if (!selectedDataset || !userRequest.trim()) {
            setError('Выберите датасет и опишите задачу');
            return;
        }
        if (!designConfirmed) {
            setError('Подтвердите дизайн исследования перед запуском планирования');
            return;
        }

        setLoading(true);
        setError(null);
        setAnalysis(null);
        setRunId(null);

        try {
            const llmModels = buildRoleModels();
            const chunkSize = Number.isFinite(Number(llmChunkSize)) ? Number(llmChunkSize) : 30;
            const preferences = {
                analysis_mode: analysisMode,
                allow_data_mining: analysisMode === 'exploratory',
                multiplicity_correction: multiplicityCorrection,
                post_hoc_correction: multiplicityCorrection,
                use_knowledge_base: useKnowledgeBase,
                smart_sampling: useSmartSampling,
                smart_sampling_mode: effectiveSmartSamplingMode,
                llm_chunk_plan: llmChunkPlan,
                llm_chunk_size: chunkSize,
                primary_outcome: primaryOutcome || null,
                group_column: groupColumnOverride || null,
                time_column: timeColumnOverride || null,
                subject_column: subjectColumnOverride || null,
                subgroup_columns: subgroupColumns || null,
                llm_models: llmModels,
                design_confirmed: true,
            };
            const data = await analysisPlan(selectedDataset, userRequest, {
                protocol: null,
                preferences,
            });
            setAnalysis(data);
            setWizardStep(3); // Advance to "AI Plan" step
        } catch (err) {
            setError(err.message);
            console.error('Planning error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleRefine = async () => {
        if (!selectedDataset || !refinement.trim()) {
            setError('Введите уточнение');
            return;
        }
        if (!designConfirmed) {
            setError('Подтвердите дизайн исследования перед уточнением протокола');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const llmModels = buildRoleModels();
            const chunkSize = Number.isFinite(Number(llmChunkSize)) ? Number(llmChunkSize) : 30;
            const preferences = {
                analysis_mode: analysisMode,
                allow_data_mining: analysisMode === 'exploratory',
                multiplicity_correction: multiplicityCorrection,
                post_hoc_correction: multiplicityCorrection,
                use_knowledge_base: useKnowledgeBase,
                smart_sampling: useSmartSampling,
                smart_sampling_mode: effectiveSmartSamplingMode,
                llm_chunk_plan: llmChunkPlan,
                llm_chunk_size: chunkSize,
                primary_outcome: primaryOutcome || null,
                group_column: groupColumnOverride || null,
                time_column: timeColumnOverride || null,
                subject_column: subjectColumnOverride || null,
                subgroup_columns: subgroupColumns || null,
                llm_models: llmModels,
                design_confirmed: true,
            };
            const merged = `${userRequest}\n\nУточнение: ${refinement}`;
            const data = await analysisPlan(selectedDataset, merged, {
                protocol: Array.isArray(analysis?.protocol) ? analysis.protocol : null,
                preferences,
            });
            setAnalysis(data);
            setRunId(null);
            setRefinement('');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDownloadReport = async () => {
        if (!runId || !selectedDataset) return;

        try {
            const blob = await downloadProtocolReport(selectedDataset, runId, 'docx');
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `protocol_report_${runId.slice(0, 8)}.docx`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError(err?.message || 'Ошибка скачивания отчёта');
        }
    };

    const handleDownloadPdf = async () => {
        if (!runId || !selectedDataset) return;

        try {
            const blob = await downloadCopilotReportPdf(runId);
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `protocol_report_${runId.slice(0, 8)}.pdf`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError(err?.message || 'Ошибка скачивания PDF');
        }
    };

    const handleKnowledgeUpload = async () => {
        if (!knowledgeFile) {
            setKnowledgeError('Выберите файл для загрузки');
            return;
        }
        setKnowledgeUploadLoading(true);
        setKnowledgeError(null);
        try {
            await uploadKnowledgeFile(knowledgeFile, {
                title: knowledgeTitle?.trim() || null,
                tags: knowledgeTags?.trim() || null,
            });
            setKnowledgeFile(null);
            setKnowledgeTitle('');
            setKnowledgeTags('');
            await loadKnowledgeDocs();
            await loadKnowledgeCatalog();
        } catch (err) {
            setKnowledgeError(err?.message || 'Не удалось загрузить файл');
        } finally {
            setKnowledgeUploadLoading(false);
        }
    };

    const handleKnowledgeDelete = async (docId) => {
        if (!docId) return;
        if (!confirm('Удалить документ из базы знаний?')) return;
        setKnowledgeLoading(true);
        setKnowledgeError(null);
        try {
            await deleteKnowledgeDoc(docId);
            await loadKnowledgeDocs();
            await loadKnowledgeCatalog();
        } catch (err) {
            setKnowledgeError(err?.message || 'Не удалось удалить документ');
        } finally {
            setKnowledgeLoading(false);
        }
    };

    const renderResults = (resultIr) => {
        if (!resultIr || typeof resultIr !== 'object') return null;
        if (Array.isArray(resultIr.blocks)) {
            return resultIr.blocks.map((block) => {
                const title = block?.title || block?.id || 'Шаг';
                const method = block?.method?.name || block?.method?.id || block?.method || '';
                const summary = block?.summary;
                const conclusion = block?.conclusion;
                const summaryText = typeof summary === 'string' ? summary : (summary ? JSON.stringify(summary) : '');

                return (
                    <div key={block?.id || title} className="py-3 border-b border-gray-200 last:border-0">
                        <div className="flex items-center gap-3">
                            <span className="font-semibold text-gray-900">{title}</span>
                            {method ? (
                                <span className="text-xs text-gray-500">({method})</span>
                            ) : null}
                            {block?.status ? (
                                <span className="text-xs text-gray-400 uppercase">{block.status}</span>
                            ) : null}
                        </div>
                        {summaryText ? (
                            <div className="text-xs text-gray-600 mt-1 whitespace-pre-wrap">{summaryText}</div>
                        ) : null}
                        {conclusion ? (
                            <div className="text-sm text-gray-700 mt-2">{conclusion}</div>
                        ) : null}
                    </div>
                );
            });
        }
        return null;
    };

    const columnsMeta = datasetReport?.scan_report?.columns || {};
    const columnEntries = Object.entries(columnsMeta);
    const allColumns = columnEntries.map(([name]) => name);
    const columnTypeByName = Object.fromEntries(
        columnEntries.map(([name, meta]) => [name, String(meta?.type || '').toLowerCase()])
    );
    const isNumericColumn = (name) => {
        const t = columnTypeByName[name] || '';
        return t.includes('int') || t.includes('float') || t.includes('double') || t.includes('number') || t === 'numeric';
    };
    const isCategoricalColumn = (name) => {
        const t = columnTypeByName[name] || '';
        return (
            t.includes('object')
            || t.includes('category')
            || t.includes('bool')
            || t.includes('string')
            || t.includes('text')
            || t === 'categorical'
        );
    };
    const numericColumns = allColumns.filter((name) => isNumericColumn(name));
    const categoricalColumns = allColumns.filter((name) => isCategoricalColumn(name));
    const filteredNumericOptions = numericColumns.filter((name) => {
        if (!numericOutcomeSearch.trim()) return true;
        return name.toLowerCase().includes(numericOutcomeSearch.trim().toLowerCase());
    });
    const filteredCategoricalOptions = categoricalColumns.filter((name) => {
        if (!categoricalOutcomeSearch.trim()) return true;
        return name.toLowerCase().includes(categoricalOutcomeSearch.trim().toLowerCase());
    });
    const studyDesignCore = studyDesign?.design && typeof studyDesign.design === 'object' ? studyDesign.design : {};
    const studyPolicy = studyDesign?.analysis_policy && typeof studyDesign.analysis_policy === 'object'
        ? studyDesign.analysis_policy
        : {};
    const endpointGroups = Array.isArray(studyDesignCore?.endpoint_groups) ? studyDesignCore.endpoint_groups : [];
    const reviewOutcomes = normalizeList(numericOutcomesSelection, allColumns);
    const reviewCatOutcomes = normalizeList(categoricalOutcomesSelection, allColumns);
    const displayDesignType = studyDesignCore?.design_type || 'unknown';
    const canPlan = Boolean(selectedDataset && userRequest.trim() && designConfirmed && !loading && !designSaving);

    const catalogQueryNormalized = catalogQuery.trim().toLowerCase();
    const filteredCatalog = knowledgeCatalog.filter((doc) => {
        if (!catalogQueryNormalized) return true;
        const haystack = [
            doc?.title,
            Array.isArray(doc?.tags) ? doc.tags.join(' ') : '',
            Array.isArray(doc?.keywords) ? doc.keywords.join(' ') : '',
            doc?.preview,
            doc?.source_type,
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();
        return haystack.includes(catalogQueryNormalized);
    });

    return (
        <div className="max-w-6xl mx-auto">
            {/* Header */}
            <div className="mb-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
                        <span className="text-4xl">🤖</span>
                        AI Copilot
                    </h1>
                    <p className="text-gray-600 mt-2">
                        Статистический анализ через естественный язык
                    </p>
                </div>
            </div>

            <StepIndicator currentStep={wizardStep} steps={WIZARD_STEPS} />

            {/* Workflow Info */}
            {datasets.length === 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                    <h3 className="font-semibold text-blue-900 mb-2">📘 Как это работает:</h3>
                    <ol className="text-sm text-blue-800 space-y-1 ml-4">
                        <li><strong>1.</strong> Загрузите Excel/CSV файл в разделе <Link to="/upload" className="underline font-medium">"Данные"</Link></li>
                        <li><strong>2.</strong> Выберите датасет из списка</li>
                        <li><strong>3.</strong> Подтвердите дизайн исследования (Design Review)</li>
                        <li><strong>4.</strong> Опишите что нужно проанализировать естественным языком</li>
                        <li><strong>5.</strong> Получите результаты: план, анализ, отчёт</li>
                    </ol>
                </div>
            )}

            {/* Dataset Selection */}
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-lg font-semibold">📂 Выберите датасет</h2>
                    <Link
                        to="/upload"
                        className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                        ➕ Загрузить новый файл
                    </Link>
                </div>

                {datasets.length === 0 ? (
                    <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                        {filesLoading ? (
                            <p className="text-gray-500">Загрузка списка файлов...</p>
                        ) : (
                            <>
                                <p className="text-gray-600 mb-4">
                                    📁 Нет загруженных датасетов
                                </p>
                                <p className="text-sm text-gray-500 mb-4">
                                    Copilot работает с данными из раздела "Данные"
                                </p>
                                <Link
                                    to="/upload"
                                    className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-6 rounded-lg transition"
                                >
                                    Загрузить Excel/CSV файл
                                </Link>
                            </>
                        )}
                    </div>
                ) : (
                    <>
                        <select
                            value={selectedDataset}
                            onChange={(e) => setSelectedDataset(e.target.value)}
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="">-- Выберите файл --</option>
                            {datasets.map((ds) => (
                                <option key={ds.id} value={ds.id}>
                                    {ds.filename} ({ds.rows || '?'} × {ds.columns || '?'})
                                </option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            💡 Данные загружаются через раздел <Link to="/datasets" className="text-blue-600 hover:underline">"Данные"</Link>
                        </p>
                    </>
                )}
            </div>

            {/* Analysis Settings */}
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                <h2 className="text-lg font-semibold mb-4">⚙️ Настройки анализа</h2>
                <div className="grid md:grid-cols-2 gap-4">
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Режим</label>
                        <div className="flex flex-wrap gap-2">
                            <button
                                type="button"
                                onClick={() => setAnalysisMode('exploratory')}
                                className={`px-3 py-2 rounded-lg border text-sm font-medium ${analysisMode === 'exploratory'
                                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                                    : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                                    }`}
                            >
                                Exploratory / Maximal
                            </button>
                            <button
                                type="button"
                                onClick={() => setAnalysisMode('focused')}
                                className={`px-3 py-2 rounded-lg border text-sm font-medium ${analysisMode === 'focused'
                                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                                    : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                                    }`}
                            >
                                Focused
                            </button>
                            <button
                                type="button"
                                onClick={() => setAnalysisMode('publication')}
                                className={`px-3 py-2 rounded-lg border text-sm font-medium ${analysisMode === 'publication'
                                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                                    : 'bg-white border-gray-300 text-gray-600 hover:border-gray-400'
                                    }`}
                            >
                                Publication / Manuscript
                            </button>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                            Exploratory: широкий data mining. Focused: компактный протокол. Publication: строгий workflow с backend Design Review и fixed cohort.
                        </p>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Поправка за множественные сравнения</label>
                        <select
                            value={multiplicityCorrection}
                            onChange={(e) => setMultiplicityCorrection(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="fdr_bh">FDR (Benjamini-Hochberg)</option>
                            <option value="fdr_by">FDR (Benjamini-Yekutieli)</option>
                            <option value="fdr_tsbky">FDR (BKY)</option>
                            <option value="bonferroni">Bonferroni</option>
                            <option value="holm">Holm</option>
                            <option value="sidak">Šidák</option>
                            <option value="none">Без поправки</option>
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Применяется к batch-анализам и post-hoc тестам.
                        </p>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Primary outcome (override)</label>
                        <select
                            value={primaryOutcome}
                            onChange={(e) => {
                                setPrimaryOutcome(e.target.value);
                                markDesignDirty();
                            }}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            disabled={allColumns.length === 0}
                        >
                            <option value="">Авто (по правилам)</option>
                            {allColumns.map((c) => (
                                <option key={`primary-${c}`} value={c}>
                                    {c}
                                    {isNumericColumn(c) ? ' [N]' : (isCategoricalColumn(c) ? ' [C]' : '')}
                                </option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Можно выбрать любую переменную. Метки `[N]`/`[C]` показывают распознанный тип.
                        </p>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Group column (override)</label>
                        <select
                            value={groupColumnOverride}
                            onChange={(e) => {
                                setGroupColumnOverride(e.target.value);
                                markDesignDirty();
                            }}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            disabled={allColumns.length === 0}
                        >
                            <option value="">Авто (по правилам)</option>
                            {allColumns.map((c) => (
                                <option key={`group-${c}`} value={c}>{c}</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Доступны все колонки. Для устойчивых тестов рекомендуется категориальная переменная.
                        </p>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Time column (override)</label>
                        <select
                            value={timeColumnOverride}
                            onChange={(e) => {
                                setTimeColumnOverride(e.target.value);
                                markDesignDirty();
                            }}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            disabled={allColumns.length === 0}
                        >
                            <option value="">Авто (по правилам)</option>
                            {allColumns.map((c) => (
                                <option key={`time-${c}`} value={c}>{c}</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Определяет ось времени/визитов для repeated measures.
                        </p>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Subject column (override)</label>
                        <select
                            value={subjectColumnOverride}
                            onChange={(e) => {
                                setSubjectColumnOverride(e.target.value);
                                markDesignDirty();
                            }}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            disabled={allColumns.length === 0}
                        >
                            <option value="">Авто (по правилам)</option>
                            {allColumns.map((c) => (
                                <option key={`subject-${c}`} value={c}>{c}</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            ID субъекта для парных/повторных измерений.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">Числовые исходы (ручной выбор)</label>
                        <div className="grid md:grid-cols-[1fr_auto] gap-2 items-start">
                            <input
                                type="text"
                                value={numericOutcomeSearch}
                                onChange={(e) => setNumericOutcomeSearch(e.target.value)}
                                placeholder="Поиск по названию колонки"
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            />
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    className="px-3 py-2 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
                                    onClick={() => {
                                        setNumericOutcomesSelection(numericColumns);
                                        markDesignDirty();
                                    }}
                                    disabled={numericColumns.length === 0}
                                >
                                    Выбрать все
                                </button>
                                <button
                                    type="button"
                                    className="px-3 py-2 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
                                    onClick={() => {
                                        setNumericOutcomesSelection([]);
                                        markDesignDirty();
                                    }}
                                    disabled={numericOutcomesSelection.length === 0}
                                >
                                    Очистить
                                </button>
                            </div>
                        </div>
                        <select
                            multiple
                            size={Math.min(14, Math.max(6, filteredNumericOptions.length || 6))}
                            value={numericOutcomesSelection}
                            onChange={(e) => {
                                const selected = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                                setNumericOutcomesSelection(selected);
                                markDesignDirty();
                            }}
                            className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                        >
                            {filteredNumericOptions.map((c) => (
                                <option key={`num-outcome-${c}`} value={c}>{c}</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Выбрано: {numericOutcomesSelection.length}. Зажмите `Cmd`/`Ctrl` для множественного выбора.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">Категориальные исходы (ручной выбор)</label>
                        <div className="grid md:grid-cols-[1fr_auto] gap-2 items-start">
                            <input
                                type="text"
                                value={categoricalOutcomeSearch}
                                onChange={(e) => setCategoricalOutcomeSearch(e.target.value)}
                                placeholder="Поиск по названию колонки"
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            />
                            <div className="flex gap-2">
                                <button
                                    type="button"
                                    className="px-3 py-2 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
                                    onClick={() => {
                                        setCategoricalOutcomesSelection(categoricalColumns);
                                        markDesignDirty();
                                    }}
                                    disabled={categoricalColumns.length === 0}
                                >
                                    Выбрать все
                                </button>
                                <button
                                    type="button"
                                    className="px-3 py-2 text-xs rounded border border-gray-300 bg-white hover:bg-gray-50"
                                    onClick={() => {
                                        setCategoricalOutcomesSelection([]);
                                        markDesignDirty();
                                    }}
                                    disabled={categoricalOutcomesSelection.length === 0}
                                >
                                    Очистить
                                </button>
                            </div>
                        </div>
                        <select
                            multiple
                            size={Math.min(14, Math.max(6, filteredCategoricalOptions.length || 6))}
                            value={categoricalOutcomesSelection}
                            onChange={(e) => {
                                const selected = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                                setCategoricalOutcomesSelection(selected);
                                markDesignDirty();
                            }}
                            className="mt-2 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                        >
                            {filteredCategoricalOptions.map((c) => (
                                <option key={`cat-outcome-${c}`} value={c}>{c}</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Выбрано: {categoricalOutcomesSelection.length}. Эти переменные попадут в `categorical_outcomes` дизайна.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                    <div className="text-sm font-semibold text-gray-900">Design Review</div>
                                    <div className="text-xs text-gray-600 mt-1">
                                        Тип дизайна: <span className="font-medium">{displayDesignType}</span>
                                        {studyDesignCore?.repeated_measures ? ' • repeated measures' : ''}
                                    </div>
                                </div>
                                <span
                                    className={`text-xs px-2 py-1 rounded-full border ${designConfirmed
                                        ? 'bg-green-50 text-green-700 border-green-200'
                                        : 'bg-amber-50 text-amber-700 border-amber-200'
                                        }`}
                                >
                                    {designConfirmed ? 'Подтверждено' : 'Требует подтверждения'}
                                </span>
                            </div>
                            <div className="mt-3 grid md:grid-cols-2 gap-2 text-xs text-gray-700">
                                <div>Group: <span className="font-medium">{groupColumnOverride || '-'}</span></div>
                                <div>Time: <span className="font-medium">{timeColumnOverride || '-'}</span></div>
                                <div>Subject: <span className="font-medium">{subjectColumnOverride || '-'}</span></div>
                                <div>Primary outcome: <span className="font-medium">{primaryOutcome || '-'}</span></div>
                            </div>
                            {(reviewOutcomes.length > 0 || reviewCatOutcomes.length > 0) && (
                                <div className="mt-3 text-xs text-gray-700">
                                    <div className="font-medium mb-1">
                                        Исходы в дизайне
                                        {' '}
                                        <span className="text-gray-500">
                                            (N={reviewOutcomes.length}, C={reviewCatOutcomes.length})
                                        </span>
                                    </div>
                                    <div className="max-h-44 overflow-y-auto rounded border border-gray-200 bg-white p-2 flex flex-wrap gap-1">
                                        {reviewOutcomes.map((col) => (
                                            <span key={`outcome-chip-${col}`} className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-200">
                                                {col}
                                            </span>
                                        ))}
                                        {reviewCatOutcomes.map((col) => (
                                            <span key={`cat-outcome-chip-${col}`} className="px-2 py-0.5 rounded bg-purple-100 text-purple-700 border border-purple-200">
                                                {col}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {endpointGroups.length > 0 && (
                                <div className="mt-3 text-xs text-gray-700">
                                    <div className="font-medium mb-1">Endpoint группы ({endpointGroups.length})</div>
                                    <div className="max-h-40 overflow-y-auto rounded border border-gray-200 bg-white p-2 flex flex-wrap gap-1">
                                        {endpointGroups.map((item, idx) => (
                                            <span key={`endpoint-${item?.endpoint || idx}`} className="px-2 py-0.5 rounded bg-gray-200 text-gray-800 border border-gray-300">
                                                {item?.endpoint || `endpoint_${idx + 1}`} ({Array.isArray(item?.columns) ? item.columns.length : 0})
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {typeof studyPolicy?.multiplicity_correction === 'string' && (
                                <div className="mt-3 text-xs text-gray-600">
                                    Политика: multiplicity = <span className="font-medium">{studyPolicy.multiplicity_correction}</span>
                                </div>
                            )}
                            <div className="mt-3 text-xs text-gray-700">
                                Fixed cohort:
                                {' '}
                                {analysisSetDoc?.artifact_exists && analysisSetDoc?.analysis_set_id
                                    ? (
                                        <span className="font-medium text-green-700">
                                            ready ({analysisSetDoc.analysis_set_id}, mode={analysisSetDoc.mode || '?'}, N={analysisSetDoc.n_selected ?? '?'})
                                        </span>
                                    )
                                    : (
                                        <span className="font-medium text-amber-700">
                                            not frozen
                                        </span>
                                    )}
                            </div>
                            {analysisMode === 'publication' && !analysisSetDoc?.analysis_set_id && (
                                <div className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                                    Publication mode: при запуске будет выполнена автоматическая заморозка когорты по `cohort_plan`.
                                </div>
                            )}
                            <div className="mt-4 flex flex-wrap items-center gap-3">
                                <button
                                    type="button"
                                    onClick={handleConfirmDesign}
                                    disabled={!selectedDataset || designLoading || designSaving || analysisSetBusy}
                                    className="px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 disabled:bg-gray-300"
                                >
                                    {designSaving ? 'Сохраняю...' : 'Сохранить и подтвердить дизайн'}
                                </button>
                                <span className="text-xs text-gray-600">
                                    Планирование и запуск анализа доступны только после подтверждения.
                                </span>
                            </div>
                            {designLoading && <div className="mt-2 text-xs text-gray-500">Загрузка дизайна...</div>}
                            {analysisSetBusy && <div className="mt-2 text-xs text-gray-500">Подготавливаю fixed cohort...</div>}
                            {designError && <div className="mt-2 text-xs text-red-600">{designError}</div>}
                        </div>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">База знаний в планировании</label>
                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                                checked={useKnowledgeBase}
                                onChange={(e) => setUseKnowledgeBase(e.target.checked)}
                            />
                            <span className="text-sm text-gray-700">
                                Подмешивать выдержки из базы знаний в контекст LLM при планировании
                            </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                            Отключите, если хотите план только по метаданным или экономить токены.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">Smart Sampling (опционально)</label>
                        <div className="flex flex-col gap-2">
                            <select
                                value={smartSamplingMode}
                                onChange={(e) => setSmartSamplingMode(e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                            >
                                <option value="off">Выключено (без строк)</option>
                                <option value="masked">Masked (PII скрывается)</option>
                                <option value="strict">Strict (все строки скрыты)</option>
                                <option value="raw">Raw (небезопасно)</option>
                            </select>
                            <p className="text-xs text-gray-500">
                                Используется только для понимания смыслов колонок. Рекомендуем Masked/Strict.
                            </p>
                            {smartSamplingMode === 'raw' && (
                                <div className="flex items-start gap-2 text-xs text-red-700 bg-red-50 border border-red-100 rounded-lg p-2">
                                    <input
                                        type="checkbox"
                                        className="mt-0.5 h-4 w-4 text-red-600 border-gray-300 rounded"
                                        checked={rawSampleConfirmed}
                                        onChange={(e) => setRawSampleConfirmed(e.target.checked)}
                                    />
                                    <span>
                                        Подтверждаю, что понимаю риск передачи персональных данных в LLM при Raw‑режиме.
                                    </span>
                                </div>
                            )}
                            {smartSamplingMode === 'raw' && !rawSampleConfirmed && (
                                <p className="text-xs text-amber-600">
                                    Без подтверждения будет использован режим Masked.
                                </p>
                            )}
                        </div>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">LLM‑chunking для планирования</label>
                        <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-3">
                                <input
                                    type="checkbox"
                                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                                    checked={llmChunkPlan}
                                    onChange={(e) => setLlmChunkPlan(e.target.checked)}
                                />
                                <span className="text-sm text-gray-700">
                                    Разбивать планирование на чанки по колонкам
                                </span>
                            </div>
                            <div className="flex items-center gap-3">
                                <label className="text-xs text-gray-500">Размер чанка (колонок)</label>
                                <input
                                    type="number"
                                    min="10"
                                    max="120"
                                    step="1"
                                    value={llmChunkSize}
                                    onChange={(e) => setLlmChunkSize(e.target.value)}
                                    className="w-28 px-2 py-1 border border-gray-300 rounded-md text-sm"
                                    disabled={!llmChunkPlan}
                                />
                            </div>
                            <p className="text-xs text-gray-500">
                                Полезно для больших таблиц: повышает охват, но увеличивает стоимость.
                            </p>
                        </div>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">Подгруппы (через запятую)</label>
                        <input
                            type="text"
                            value={subgroupColumns}
                            onChange={(e) => {
                                setSubgroupColumns(e.target.value);
                                markDesignDirty();
                            }}
                            placeholder="например: пол, возрастная группа"
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                        <p className="text-xs text-gray-500 mt-2">
                            Опционально. Если пусто, в exploratory‑режиме подгруппы выбираются автоматически.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">LLM модели по ролям</label>
                        <div className="grid md:grid-cols-2 gap-3">
                            <div>
                                <label className="text-xs text-gray-500 block mb-1">Планер / дизайн</label>
                                <select
                                    value={modelPlanner}
                                    onChange={(e) => setModelPlanner(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                >
                                    {ROLE_MODEL_OPTIONS_PLANNER.map((opt) => (
                                        <option key={`planner-${opt.value || 'default'}`} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 block mb-1">Семантика / качество</label>
                                <select
                                    value={modelQuality}
                                    onChange={(e) => setModelQuality(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                >
                                    {ROLE_MODEL_OPTIONS_SEMANTICS.map((opt) => (
                                        <option key={`quality-${opt.value || 'default'}`} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 block mb-1">Интерпретация (Results)</label>
                                <select
                                    value={modelInterpret}
                                    onChange={(e) => setModelInterpret(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                >
                                    {ROLE_MODEL_OPTIONS_INTERPRET.map((opt) => (
                                        <option key={`interpret-${opt.value || 'default'}`} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="text-xs text-gray-500 block mb-1">Обсуждение / выводы</label>
                                <select
                                    value={modelReport}
                                    onChange={(e) => setModelReport(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                >
                                    {ROLE_MODEL_OPTIONS_REPORT.map((opt) => (
                                        <option key={`report-${opt.value || 'default'}`} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="md:col-span-2">
                                <label className="text-xs text-gray-500 block mb-1">Codegen (Advanced режим)</label>
                                <select
                                    value={modelCodegen}
                                    onChange={(e) => setModelCodegen(e.target.value)}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                >
                                    {ROLE_MODEL_OPTIONS_CODEGEN.map((opt) => (
                                        <option key={`codegen-${opt.value || 'default'}`} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                            Эти настройки применяются к планированию, критике протокола и текстовой интерпретации в отчёте.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">Движок расчёта</label>
                        <select
                            value={analysisEngine}
                            onChange={(e) => setAnalysisEngine(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="python">Python (по умолчанию)</option>
                            <option value="r">R (альтернативный)</option>
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            R‑движок использует системный R для расчётов. Графики можно отдать Python или R отдельно.
                        </p>
                    </div>
                    <div className="md:col-span-2">
                        <label className="text-sm font-medium text-gray-700 block mb-2">Движок графиков</label>
                        <select
                            value={plotEngine}
                            onChange={(e) => setPlotEngine(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="python">Python (seaborn/matplotlib)</option>
                            <option value="r">R (ggplot2/tidyverse)</option>
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            R‑графики строятся через ggplot2. Полезно для публикационного стиля и тонкой кастомизации.
                        </p>
                    </div>
                </div>
            </div>

            {/* Data Summary Card */}
            {datasetReport && (
                <DataSummaryCard
                    report={datasetReport}
                    onConfirm={wizardStep === 1 ? () => setWizardStep(2) : null}
                />
            )}
            {/* Knowledge Base */}
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                <div className="flex items-center justify-between mb-3">
                    <h2 className="text-lg font-semibold">📚 База знаний</h2>
                    <span className="text-xs text-gray-500">txt / md / docx / pdf</span>
                </div>
                <div className="grid md:grid-cols-3 gap-3 items-end">
                    <div className="md:col-span-1">
                        <label className="text-xs text-gray-500 block mb-1">Файл</label>
                        <input
                            type="file"
                            onChange={(e) => setKnowledgeFile(e.target.files?.[0] || null)}
                            className="w-full text-sm"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-gray-500 block mb-1">Название (опционально)</label>
                        <input
                            type="text"
                            value={knowledgeTitle}
                            onChange={(e) => setKnowledgeTitle(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                            placeholder="Например: GCP, SAP, методичка"
                        />
                    </div>
                    <div>
                        <label className="text-xs text-gray-500 block mb-1">Теги (через запятую)</label>
                        <input
                            type="text"
                            value={knowledgeTags}
                            onChange={(e) => setKnowledgeTags(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                            placeholder="biostat, sap, gcp"
                        />
                    </div>
                </div>
                <button
                    onClick={handleKnowledgeUpload}
                    disabled={knowledgeUploadLoading || !knowledgeFile}
                    className="mt-4 bg-gray-900 hover:bg-gray-800 disabled:bg-gray-300 text-white font-semibold py-2 px-4 rounded-lg text-sm"
                >
                    {knowledgeUploadLoading ? '⏳ Загружаю...' : '⬆️ Добавить в базу знаний'}
                </button>
                {knowledgeError && (
                    <div className="mt-3 text-sm text-red-600">
                        {knowledgeError}
                    </div>
                )}
                <div className="mt-4">
                    {knowledgeLoading ? (
                        <div className="text-sm text-gray-500">Загрузка базы знаний...</div>
                    ) : (
                        <div className="space-y-2">
                            {knowledgeDocs.length === 0 ? (
                                <div className="text-sm text-gray-500">База знаний пока пустая.</div>
                            ) : (
                                knowledgeDocs.slice(0, 6).map((doc) => (
                                    <div key={doc.id} className="flex items-center justify-between border border-gray-200 rounded-lg px-3 py-2">
                                        <div>
                                            <div className="text-sm font-medium text-gray-900">{doc.title || doc.filename}</div>
                                            <div className="text-xs text-gray-500">
                                                {doc.text_chars || 0} символов • {doc.num_chunks || 0} чанков
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleKnowledgeDelete(doc.id)}
                                            className="text-xs text-red-600 hover:text-red-800"
                                        >
                                            Удалить
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>
                <div className="mt-6 border-t border-gray-200 pt-4">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-semibold text-gray-700">Каталог тем</h3>
                        <span className="text-xs text-gray-500">по ключевым словам</span>
                    </div>
                    <input
                        type="text"
                        value={catalogQuery}
                        onChange={(e) => setCatalogQuery(e.target.value)}
                        placeholder="Поиск по темам, тегам, ключевым словам"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm mb-3"
                    />
                    {catalogLoading ? (
                        <div className="text-sm text-gray-500">Загрузка каталога...</div>
                    ) : catalogError ? (
                        <div className="text-sm text-red-600">{catalogError}</div>
                    ) : filteredCatalog.length === 0 ? (
                        <div className="text-sm text-gray-500">Каталог пока пуст или ничего не найдено.</div>
                    ) : (
                        <div className="grid md:grid-cols-2 gap-3">
                            {filteredCatalog.slice(0, 12).map((doc) => (
                                <div key={`catalog-${doc.id}`} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
                                    <div className="text-sm font-semibold text-gray-900">{doc.title}</div>
                                    <div className="text-xs text-gray-500 mt-1">
                                        {doc.source_type || 'document'}
                                    </div>
                                    {Array.isArray(doc.tags) && doc.tags.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-1">
                                            {doc.tags.slice(0, 4).map((tag) => (
                                                <span key={`tag-${doc.id}-${tag}`} className="text-[10px] px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full border border-blue-200">
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                    {Array.isArray(doc.keywords) && doc.keywords.length > 0 && (
                                        <div className="mt-2 text-[11px] text-gray-600">
                                            Ключевые слова: {doc.keywords.slice(0, 6).join(', ')}
                                        </div>
                                    )}
                                    {doc.preview && (
                                        <div className="mt-2 text-xs text-gray-600 line-clamp-3">
                                            {doc.preview}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                    <p className="text-[11px] text-gray-500 mt-3">
                        Каталог используется для выбора релевантных источников и экономии токенов.
                    </p>
                </div>
            </div>

            {/* Request Input */}
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
                <h2 className="text-lg font-semibold mb-3">💬 Что нужно проанализировать?</h2>
                <div className="flex flex-wrap gap-2 mb-3">
                    <button
                        type="button"
                        onClick={handleGenerateBrief}
                        disabled={briefLoading || !selectedDataset || !designConfirmed || designSaving}
                        className="px-3 py-2 rounded-lg border text-sm font-medium bg-white border-gray-300 text-gray-600 hover:border-gray-400 disabled:bg-gray-100 disabled:text-gray-400"
                    >
                        {briefLoading ? '⏳ Формирую бриф...' : '⚡ Сгенерировать бриф из метаданных'}
                    </button>
                    <span className="text-xs text-gray-500 self-center">
                        Бриф основан на scan_report + study_design и подлежит правке.
                    </span>
                </div>
                <textarea
                    value={userRequest}
                    onChange={(e) => setUserRequest(e.target.value)}
                    placeholder="Например: Сравни группы по исходу. Проверь динамику лабораторных V1→V2. Найди предикторы смерти (логрегрессия на возраст, CRP, WBC)."
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-32"
                />
                {briefError && (
                    <div className="mt-2 text-xs text-red-600">{briefError}</div>
                )}
                <button
                    onClick={handlePlan}
                    disabled={!canPlan}
                    className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-lg transition"
                >
                    {loading ? '⏳ Анализирую...' : '🚀 Анализировать'}
                </button>
                {!designConfirmed && selectedDataset && (
                    <div className="mt-2 text-xs text-amber-600">
                        Сначала подтвердите дизайн исследования в блоке Design Review.
                    </div>
                )}
            </div>

            {/* Error */}
            {error && (
                <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-lg mb-6">
                    <strong>Ошибка:</strong> {error}
                </div>
            )}

            {/* Results */}
            {analysis && (
                <>
                    {/* Stats & Metadata - NEW */}
                    <div className="flex justify-end mb-4">
                        <TokenCounter usage={analysis.usage} />
                    </div>

                    {/* Plan */}
                    <div className="bg-white rounded-lg border border-gray-200 mb-6 border-l-4 border-l-blue-500">
                        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                            <h2 className="text-lg font-semibold flex items-center gap-2">
                                📋 План анализа
                                {!analysis.result_ir && <span className="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-1 rounded">Ожидает подтверждения</span>}
                            </h2>
                        </div>
                        <div className="px-6 py-4">
                            <p className="mb-3">
                                <strong>Протокол:</strong> {analysis.protocol_name || 'Протокол'}
                            </p>
                            {analysis.analysis_mode && (
                                <p className="mb-3">
                                    <strong>Режим:</strong> {String(analysis.analysis_mode)}
                                </p>
                            )}
                            <p className="mb-3">
                                <strong>Шагов:</strong> {Array.isArray(analysis.protocol) ? analysis.protocol.length : 0}
                            </p>
                            {Array.isArray(analysis.notes) && analysis.notes.length > 0 && (
                                <div className="mb-3 text-sm text-gray-600">
                                    {analysis.notes.slice(0, 3).map((n, idx) => (
                                        <div key={`note-${idx}`}>• {n}</div>
                                    ))}
                                </div>
                            )}
                            {analysis.cleaning_plan && typeof analysis.cleaning_plan === 'object' && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Cleaning plan</strong>
                                    <div>
                                        required: <span className="font-medium">{analysis.cleaning_plan.required ? 'yes' : 'no'}</span>
                                    </div>
                                    {Array.isArray(analysis.cleaning_plan.operations) && analysis.cleaning_plan.operations.length > 0 && (
                                        <div className="text-xs text-gray-600 mt-1">
                                            ops: {analysis.cleaning_plan.operations.slice(0, 6).map((op) => String(op?.type || '?')).join(', ')}
                                        </div>
                                    )}
                                </div>
                            )}
                            {analysis.cohort_plan && typeof analysis.cohort_plan === 'object' && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Cohort plan</strong>
                                    <div>
                                        required: <span className="font-medium">{analysis.cohort_plan.required ? 'yes' : 'no'}</span>
                                        {' '}• mode: <span className="font-medium">{analysis.cohort_plan.mode || '-'}</span>
                                        {' '}• enforce: <span className="font-medium">{analysis.cohort_plan.enforce || '-'}</span>
                                        {' '}• strict: <span className="font-medium">{analysis.cohort_plan.strict ? 'true' : 'false'}</span>
                                    </div>
                                    {Array.isArray(analysis.cohort_plan.required_non_missing) && analysis.cohort_plan.required_non_missing.length > 0 && (
                                        <div className="text-xs text-gray-600 mt-1">
                                            required_non_missing: {analysis.cohort_plan.required_non_missing.slice(0, 10).join(', ')}
                                        </div>
                                    )}
                                </div>
                            )}
                            {analysis.report_spec && typeof analysis.report_spec === 'object' && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Report spec</strong>
                                    <div>
                                        style: <span className="font-medium">{analysis.report_spec.style || 'standard'}</span>
                                    </div>
                                    {Array.isArray(analysis.report_spec.sections) && analysis.report_spec.sections.length > 0 && (
                                        <div className="text-xs text-gray-600 mt-1">
                                            sections: {analysis.report_spec.sections.map((s) => String(s?.title || s?.id || '?')).join(', ')}
                                        </div>
                                    )}
                                </div>
                            )}
                            {Array.isArray(analysis.protocol) && analysis.protocol.length > 0 && (
                                <div>
                                    <strong className="block mb-2">Шаги протокола:</strong>
                                    <div className="flex flex-wrap gap-2">
                                        {analysis.protocol.slice(0, 12).map((s, idx) => (
                                            <span
                                                key={s?.id || idx}
                                                className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm border border-blue-100"
                                            >
                                                {s?.name || s?.method || 'Шаг'}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                        {/* Execute Button - Only if no results yet */}
                        {!analysis.result_ir && (
                            <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
                                <button
                                    onClick={() => setAnalysis(null)}
                                    className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium"
                                >
                                    Отмена
                                </button>
                                <button
                                    onClick={handleExecute}
                                    disabled={loading || analysisSetBusy || !designConfirmed}
                                    className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-6 rounded-lg flex items-center gap-2 shadow-sm transition transform hover:scale-105"
                                >
                                    {loading || analysisSetBusy ? '⚡ Выполняю...' : '🚀 Выполнить анализ'}
                                </button>
                            </div>
                        )}
                    </div>

                    {/* Execution Results */}
                    {analysis.result_ir && (
                        <>
                            <div className="bg-white rounded-lg border border-gray-200 mb-6 shadow-sm">
                                <div className="px-6 py-4 border-b border-gray-200 bg-green-50">
                                    <h2 className="text-lg font-semibold text-green-900">📊 Результаты</h2>
                                </div>
                                <div className="px-6 py-4 divide-y divide-gray-100">
                                    {renderResults(analysis.result_ir)}
                                </div>
                            </div>

                            {Array.isArray(analysis.errors) && analysis.errors.length > 0 && (
                                <div className="bg-red-50 border border-red-200 rounded-lg px-6 py-4 mb-6">
                                    <h3 className="font-semibold mb-2 text-red-900">Ошибки выполнения</h3>
                                    <div className="text-sm text-red-800 space-y-1">
                                        {analysis.errors.map((e, idx) => (
                                            <div key={`err-${idx}`}>• {e?.error || String(e)}</div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="flex gap-4 mb-6">
                                <div className="flex gap-4">
                                    <button
                                        onClick={handleDownloadReport}
                                        disabled={!runId}
                                        className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2"
                                    >
                                        📄 Скачать отчёт (DOCX)
                                    </button>
                                    <button
                                        onClick={handleDownloadPdf}
                                        disabled={!runId}
                                        className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2"
                                    >
                                        📕 Скачать PDF
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {/* Refinement */}
                    <div className="bg-white rounded-lg border border-gray-200 p-6">
                        <h2 className="text-lg font-semibold mb-3">🔄 Уточнить анализ</h2>
                        <input
                            type="text"
                            value={refinement}
                            onChange={(e) => setRefinement(e.target.value)}
                            placeholder="Например: Добавь ROC-кривую для CRP"
                            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 mb-3"
                        />
                        <button
                            onClick={handleRefine}
                            disabled={loading || !refinement.trim()}
                            className="w-full bg-gray-600 hover:bg-gray-700 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-lg transition"
                        >
                            ➕ Уточнить
                        </button>
                    </div>
                </>
            )}
        </div>
    );
}
