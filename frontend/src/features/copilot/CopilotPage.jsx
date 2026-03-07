// Copilot Page - Chat-First Statistical Analysis
import { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
    getDatasets,
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
    downloadProtocolReleaseBundle,
    getModelRouterBenchmarkSnapshot,
} from '../../lib/api';
import { buildAnalysisSetFreezeSpec } from '../../app/utils/analysisSet';

// ...
import TokenCounter from './components/TokenCounter';
import DataSummaryCard from './components/DataSummaryCard';
import StepIndicator from './components/StepIndicator';
import {
    MODEL_PRESET_PROFILES,
    MODEL_BENCHMARK_VARIANTS,
    DEFAULT_ROLE_MODELS,
    formatCorrectionLabel,
    ROLE_MODEL_OPTIONS_PLANNER,
    ROLE_MODEL_OPTIONS_SEMANTICS,
    ROLE_MODEL_OPTIONS_INTERPRET,
    ROLE_MODEL_OPTIONS_REPORT,
    ROLE_MODEL_OPTIONS_CODEGEN,
} from './components/modelPresets';
import { rankBenchmarkRows } from './components/benchmarkScoring';

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

function extractUsageTokenTotal(usage) {
    const rootTotal = Number(usage?.total_tokens);
    if (Number.isFinite(rootTotal) && rootTotal >= 0) {
        return rootTotal;
    }

    const seen = new Set();
    let total = 0;
    let found = false;

    const walk = (node, depth = 0) => {
        if (!node || depth > 8) return;
        if (typeof node !== 'object') return;
        if (seen.has(node)) return;
        seen.add(node);

        const directTotal = Number(node?.total_tokens);
        if (Number.isFinite(directTotal) && directTotal >= 0) {
            total += directTotal;
            found = true;
        }

        if (Array.isArray(node)) {
            node.forEach((item) => walk(item, depth + 1));
            return;
        }

        Object.values(node).forEach((value) => walk(value, depth + 1));
    };

    walk(usage);
    return found ? total : null;
}

function applyRoleOverride(mapping, column, role) {
    if (!column) return;
    const next = mapping[column] && typeof mapping[column] === 'object' ? { ...mapping[column] } : {};
    next.role = role;
    mapping[column] = next;
}

function getHypothesisItems(doc, limit = 6) {
    if (!doc || typeof doc !== 'object') return [];
    const raw = Array.isArray(doc.items) ? doc.items : [];
    return raw
        .filter((item) => item && typeof item === 'object')
        .slice(0, Math.max(1, Number(limit) || 6));
}

function formatPercent(value, digits = 1) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '-';
    return `${(number * 100).toFixed(digits)}%`;
}

function formatCaptureStatus(status) {
    const normalized = String(status || '').trim().toLowerCase();
    if (!normalized) return '-';
    if (normalized === 'completed') return 'COMPLETED';
    if (normalized === 'skipped') return 'SKIPPED';
    if (normalized === 'missing') return 'MISSING';
    if (normalized === 'invalid') return 'INVALID';
    return normalized.toUpperCase();
}

const WIZARD_STEPS = ['Данные', 'Промпт', 'План AI', 'Выполнение', 'Отчёт'];


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
    const [briefValidationPolicy, setBriefValidationPolicy] = useState(null);
    const [briefHypotheses, setBriefHypotheses] = useState(null);
    const [refinement, setRefinement] = useState('');
    const [analysisMode, setAnalysisMode] = useState('exploratory');
    const [multiplicityCorrection, setMultiplicityCorrection] = useState('fdr_bh');
    const [bootstrapCi, setBootstrapCi] = useState(false);
    const [bootstrapSamples, setBootstrapSamples] = useState(1000);
    const [validationProfile, setValidationProfile] = useState('auto');
    const [validatorStrictOverride, setValidatorStrictOverride] = useState('auto');
    const [reflectionEnabledOverride, setReflectionEnabledOverride] = useState('auto');
    const [reflectionRoundsOverride, setReflectionRoundsOverride] = useState('');
    const [repairCorrectionOverride, setRepairCorrectionOverride] = useState('auto');
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
    const [designLoading, setDesignLoading] = useState(false);
    const [designSaving, setDesignSaving] = useState(false);
    const [designError, setDesignError] = useState(null);
    const [designConfirmed, setDesignConfirmed] = useState(false);
    const [designReviewTimestamp, setDesignReviewTimestamp] = useState(null);
    const [analysisSetDoc, setAnalysisSetDoc] = useState(null);
    const [analysisSetBusy, setAnalysisSetBusy] = useState(false);
    const [modelPlanner, setModelPlanner] = useState(DEFAULT_ROLE_MODELS.planner);
    const [modelQuality, setModelQuality] = useState(DEFAULT_ROLE_MODELS.quality);
    const [modelReport, setModelReport] = useState(DEFAULT_ROLE_MODELS.report);
    const [modelInterpret, setModelInterpret] = useState(DEFAULT_ROLE_MODELS.interpret);
    const [modelCodegen, setModelCodegen] = useState(DEFAULT_ROLE_MODELS.codegen);
    const [benchmarkLoading, setBenchmarkLoading] = useState(false);
    const [benchmarkRows, setBenchmarkRows] = useState([]);
    const [benchmarkError, setBenchmarkError] = useState(null);
    const [benchmarkRunAt, setBenchmarkRunAt] = useState(null);
    const [benchmarkSnapshotLoading, setBenchmarkSnapshotLoading] = useState(false);
    const [benchmarkSnapshot, setBenchmarkSnapshot] = useState(null);
    const [benchmarkSnapshotError, setBenchmarkSnapshotError] = useState(null);

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

    const buildRoleModels = (override = null) => {
        const source = override && typeof override === 'object'
            ? override
            : {
                planner: modelPlanner,
                quality: modelQuality,
                report: modelReport,
                interpret: modelInterpret,
                codegen: modelCodegen,
            };
        return Object.fromEntries(
            Object.entries(source).filter(([, value]) => typeof value === 'string' && value.trim())
        );
    };

    const applyModelPreset = (preset) => {
        if (!preset || typeof preset !== 'object') return;
        setModelPlanner(String(preset.planner || ''));
        setModelQuality(String(preset.quality || ''));
        setModelInterpret(String(preset.interpret || ''));
        setModelReport(String(preset.report || ''));
        setModelCodegen(String(preset.codegen || ''));
    };

    const applyRouterAiProfile = () => {
        applyModelPreset(MODEL_PRESET_PROFILES.routerai_combo);
    };

    const clearRoleModelsToServerDefaults = () => {
        applyModelPreset(DEFAULT_ROLE_MODELS);
    };

    const buildValidationPolicyPreferences = () => {
        const policy = {};
        if (validationProfile && validationProfile !== 'auto') {
            policy.validation_profile = validationProfile;
        }
        if (validatorStrictOverride === 'true') {
            policy.validator_strict = true;
        } else if (validatorStrictOverride === 'false') {
            policy.validator_strict = false;
        }
        if (reflectionEnabledOverride === 'true') {
            policy.agent_reflection_enabled = true;
        } else if (reflectionEnabledOverride === 'false') {
            policy.agent_reflection_enabled = false;
        }
        const rounds = Number(reflectionRoundsOverride);
        if (Number.isFinite(rounds) && rounds > 0) {
            policy.agent_reflection_max_rounds = Math.max(1, Math.min(10, Math.round(rounds)));
        }
        if (repairCorrectionOverride && repairCorrectionOverride !== 'auto') {
            policy.verifier_repair_correction = repairCorrectionOverride;
        }
        return policy;
    };

    const buildPlanningPreferences = (llmModelsOverride = null, options = null) => {
        const chunkSize = Number.isFinite(Number(llmChunkSize)) ? Number(llmChunkSize) : 30;
        const llmModels = buildRoleModels(llmModelsOverride);
        const policyPrefs = buildValidationPolicyPreferences();
        const includeUsage = Boolean(options && options.returnUsage);
        return {
            analysis_mode: analysisMode,
            allow_data_mining: analysisMode === 'exploratory',
            multiplicity_correction: multiplicityCorrection,
            post_hoc_correction: multiplicityCorrection,
            bootstrap_ci: Boolean(bootstrapCi),
            bootstrap_samples: Number.isFinite(Number(bootstrapSamples))
                ? Math.max(100, Math.min(100000, Math.round(Number(bootstrapSamples))))
                : 1000,
            ...policyPrefs,
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
            ...(includeUsage ? { return_usage: true } : {}),
            ...(Object.keys(llmModels).length ? { llm_models: llmModels } : {}),
        };
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
            const report = await getDatasetReport(id);
            setDatasetReport(report);
        } catch (err) {
            console.error("Failed to load report", err);
        }
    }, []);

    const loadDesign = useCallback(async (id) => {
        if (!id) {
            setStudyDesign(null);
            setVariableMapping({});
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

            const outcomeDefaults = []
                .concat(Array.isArray(design?.outcomes) ? design.outcomes : [])
                .concat(Array.isArray(design?.categorical_outcomes) ? design.categorical_outcomes : []);

            setStudyDesign(designPayload);
            setVariableMapping(mappingPayload);
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
            const policyGlobals = buildValidationPolicyPreferences();
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
                ...policyGlobals,
                ...(Object.keys(llmModels || {}).length ? { llm_models: llmModels } : {}),
                analysis_mode: analysisModeResolved,
                mode: analysisModeResolved,
                bootstrap_ci: Boolean(bootstrapCi),
                bootstrap_samples: Number.isFinite(Number(bootstrapSamples))
                    ? Math.max(100, Math.min(100000, Math.round(Number(bootstrapSamples))))
                    : 1000,
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
            if (Array.isArray(benchmarkRows) && benchmarkRows.length > 0) {
                const recommendedRow = benchmarkRows.find((row) => row && row.recommended) || null;
                const benchmarkStepCounts = benchmarkRows
                    .map((row) => Number(row?.stepCount))
                    .filter((value) => Number.isFinite(value) && value > 0);
                const expectedStepCount = benchmarkStepCounts.length > 0
                    ? Math.max(
                        1,
                        Math.round(
                            benchmarkStepCounts.reduce((sum, value) => sum + value, 0) / benchmarkStepCounts.length
                        )
                    )
                    : null;
                const benchmarkPayload = {
                    schema: 'clinimetria.llm_benchmark',
                    version: 1,
                    recorded_at: benchmarkRunAt || new Date().toISOString(),
                    benchmark_context: {
                        analysis_mode: analysisModeResolved,
                        validation_profile: validationProfile || null,
                        expected_step_count: expectedStepCount,
                        variant_count: benchmarkRows.length,
                    },
                    recommended_id: recommendedRow?.id || null,
                    recommended_models: recommendedRow?.models && typeof recommendedRow.models === 'object'
                        ? buildRoleModels(recommendedRow.models)
                        : null,
                    variants: benchmarkRows.map((row) => ({
                        id: row?.id || null,
                        label: row?.label || null,
                        status: row?.status || 'unknown',
                        elapsed_ms: Number.isFinite(Number(row?.elapsedMs)) ? Number(row.elapsedMs) : null,
                        quality_score: Number.isFinite(Number(row?.qualityScore)) ? Number(row.qualityScore) : null,
                        benchmark_score: Number.isFinite(Number(row?.benchmarkScore)) ? Number(row.benchmarkScore) : null,
                        step_count: Number.isFinite(Number(row?.stepCount)) ? Number(row.stepCount) : null,
                        token_total: Number.isFinite(Number(row?.tokenTotal)) ? Number(row.tokenTotal) : null,
                        attempt_count: Number.isFinite(Number(row?.attemptCount)) ? Number(row.attemptCount) : null,
                        fallback_used: typeof row?.fallbackUsed === 'boolean' ? row.fallbackUsed : null,
                        planner_model: row?.plannerModel || null,
                        model_used: row?.modelUsed || null,
                        models: row?.models && typeof row.models === 'object'
                            ? buildRoleModels(row.models)
                            : null,
                        validation_profile: row?.policyProfile || null,
                        validator_strict: typeof row?.validatorStrict === 'boolean' ? row.validatorStrict : null,
                        reflection_enabled: typeof row?.reflectionEnabled === 'boolean' ? row.reflectionEnabled : null,
                        repair_correction: row?.repairCorrection || null,
                        analysis_mode: analysisModeResolved,
                        expected_step_count: expectedStepCount,
                        error: row?.error || null,
                        recommended: Boolean(row?.recommended),
                    })),
                };
                mergedGlobals.llm_benchmark = benchmarkPayload;
            }
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
                warnings: Array.isArray(res?.warnings) ? res.warnings : (prev?.warnings || []),
                run_state: res?.run_state || prev?.run_state || null,
                protocol_validation: res?.protocol_validation || prev?.protocol_validation || null,
                validation_policy: res?.validation_policy || prev?.validation_policy || null,
                reproducibility: res?.reproducibility || prev?.reproducibility || null,
                agent_orchestration: res?.agent_orchestration || prev?.agent_orchestration || null,
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
            setDesignConfirmed(false);
            setDesignReviewTimestamp(null);
            setAnalysisSetDoc(null);
        }
        setBenchmarkRows([]);
        setBenchmarkError(null);
        setBenchmarkRunAt(null);
        setBriefValidationPolicy(null);
        setBriefHypotheses(null);
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
            const scanColumns = Object.keys(datasetReport?.scan_report?.columns || datasetReport?.columns || {});
            const designColumns = Object.keys(studyDesign?.columns || {});
            const knownColumns = Array.from(new Set([...scanColumns, ...designColumns, ...Object.keys(currentMapping)]));
            const subgroups = parseCsvColumns(subgroupColumns);
            const nextMapping = {};

            knownColumns.forEach((column) => {
                const currentEntry = currentMapping[column] && typeof currentMapping[column] === 'object'
                    ? { ...currentMapping[column] }
                    : {};

                if (['group', 'time', 'subject', 'outcome'].includes(String(currentEntry.role || ''))) {
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
            if (confirmed && wizardStep < 2) {
                setWizardStep(2);
            }
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
        setBriefValidationPolicy(null);
        setBriefHypotheses(null);
        try {
            const chunkSize = Number.isFinite(Number(llmChunkSize)) ? Number(llmChunkSize) : 30;
            const policyPrefs = buildValidationPolicyPreferences();
            const preferences = {
                analysis_mode: analysisMode,
                allow_data_mining: analysisMode === 'exploratory',
                multiplicity_correction: multiplicityCorrection,
                post_hoc_correction: multiplicityCorrection,
                bootstrap_ci: Boolean(bootstrapCi),
                bootstrap_samples: Number.isFinite(Number(bootstrapSamples))
                    ? Math.max(100, Math.min(100000, Math.round(Number(bootstrapSamples))))
                    : 1000,
                ...policyPrefs,
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
            if (res?.validation_policy && typeof res.validation_policy === 'object') {
                setBriefValidationPolicy(res.validation_policy);
            }
            if (res?.hypotheses && typeof res.hypotheses === 'object') {
                setBriefHypotheses(res.hypotheses);
            }
        } catch (err) {
            setBriefError(err?.message || 'Не удалось сформировать бриф');
        } finally {
            setBriefLoading(false);
        }
    };

    const resolveBenchmarkProfile = () => {
        const profile = String(validationProfile || '').trim().toLowerCase();
        if (profile === 'publication' || profile === 'focused' || profile === 'exploratory') {
            return profile;
        }
        if (analysisMode === 'publication') return 'publication';
        if (analysisMode === 'focused') return 'focused';
        return 'exploratory';
    };

    const loadBenchmarkSnapshot = useCallback(async ({ silent = false } = {}) => {
        if (!silent) {
            setBenchmarkSnapshotLoading(true);
        }
        if (!silent) {
            setBenchmarkSnapshotError(null);
        }
        try {
            const payload = await getModelRouterBenchmarkSnapshot({
                minRuns: 10,
                includeMarkdown: false,
                topN: 8,
            });
            setBenchmarkSnapshot(payload && typeof payload === 'object' ? payload : null);
        } catch (err) {
            if (!silent) {
                setBenchmarkSnapshotError(err?.message || 'Не удалось загрузить сводный benchmark');
            }
        } finally {
            if (!silent) {
                setBenchmarkSnapshotLoading(false);
            }
        }
    }, []);

    const handleLoadBenchmarkSnapshot = async ({ silent = false } = {}) => {
        await loadBenchmarkSnapshot({ silent });
    };

    const handleBenchmarkModels = async () => {
        if (!selectedDataset || !userRequest.trim()) {
            setBenchmarkError('Выберите датасет и опишите задачу для сравнения моделей');
            return;
        }
        if (!designConfirmed) {
            setBenchmarkError('Подтвердите дизайн исследования перед сравнением моделей');
            return;
        }

        setBenchmarkLoading(true);
        setBenchmarkError(null);
        setBenchmarkRows([]);

        const nowMs = () => {
            if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
                return performance.now();
            }
            return Date.now();
        };

        try {
            const rows = [];
            for (const variant of MODEL_BENCHMARK_VARIANTS) {
                const started = nowMs();
                try {
                    const preferences = buildPlanningPreferences(variant.models, { returnUsage: true });
                    const planData = await analysisPlan(selectedDataset, userRequest, {
                        protocol: null,
                        preferences,
                    });
                    const elapsedMs = Math.max(0, Math.round(nowMs() - started));
                    const qualityScore = Number.isFinite(Number(planData?.quality?.score))
                        ? Number(planData.quality.score)
                        : null;
                    const stepCount = Array.isArray(planData?.protocol) ? planData.protocol.length : 0;
                    const tokenTotal = extractUsageTokenTotal(planData?.usage);
                    rows.push({
                        id: variant.id,
                        label: variant.label,
                        models: variant.models,
                        status: 'ok',
                        elapsedMs,
                        qualityScore,
                        stepCount,
                        tokenTotal,
                        plannerModel: variant?.models?.planner || null,
                        modelUsed: typeof planData?.usage?.model_used === 'string' ? planData.usage.model_used : null,
                        fallbackUsed: Boolean(planData?.usage?.fallback_used),
                        attemptCount: Number.isFinite(Number(planData?.usage?.attempt_count))
                            ? Number(planData.usage.attempt_count)
                            : 1,
                        policyProfile: planData?.validation_policy?.profile || null,
                        validatorStrict: typeof planData?.validation_policy?.validator_strict === 'boolean'
                            ? planData.validation_policy.validator_strict
                            : null,
                        reflectionEnabled: typeof planData?.validation_policy?.reflection_enabled === 'boolean'
                            ? planData.validation_policy.reflection_enabled
                            : null,
                        repairCorrection: planData?.validation_policy?.repair_correction || null,
                    });
                } catch (err) {
                    const elapsedMs = Math.max(0, Math.round(nowMs() - started));
                    rows.push({
                        id: variant.id,
                        label: variant.label,
                        models: variant.models,
                        status: 'error',
                        elapsedMs,
                        qualityScore: null,
                        stepCount: 0,
                        tokenTotal: null,
                        plannerModel: variant?.models?.planner || null,
                        modelUsed: null,
                        fallbackUsed: false,
                        attemptCount: null,
                        policyProfile: null,
                        validatorStrict: null,
                        reflectionEnabled: null,
                        repairCorrection: null,
                        error: err?.message || 'Ошибка планирования',
                    });
                }
            }

            setBenchmarkRows(
                rankBenchmarkRows(rows, {
                    analysisMode,
                    validationProfile,
                })
            );
            setBenchmarkRunAt(new Date().toISOString());
            void loadBenchmarkSnapshot({ silent: true });
        } catch (err) {
            setBenchmarkError(err?.message || 'Не удалось выполнить сравнение моделей');
        } finally {
            setBenchmarkLoading(false);
        }
    };

    const handleApplyRecommendedBenchmarkModels = () => {
        const recommended = Array.isArray(benchmarkRows)
            ? benchmarkRows.find((row) => row && row.recommended && row.models && typeof row.models === 'object')
            : null;
        if (!recommended) return;
        applyModelPreset(recommended.models);
    };

    const handleApplyHistoricalWinner = () => {
        const winners = benchmarkSnapshot && typeof benchmarkSnapshot === 'object'
            ? benchmarkSnapshot.winners_by_profile
            : null;
        const profile = resolveBenchmarkProfile();
        const winner = winners && typeof winners === 'object' && winners[profile] && typeof winners[profile] === 'object'
            ? winners[profile]
            : null;
        const winnerId = String(winner?.variant_id || '').trim();
        if (!winnerId) {
            setBenchmarkSnapshotError(`Для профиля ${profile} пока нет исторического победителя`);
            return;
        }
        const variant = MODEL_BENCHMARK_VARIANTS.find((item) => item && item.id === winnerId);
        if (!variant || !variant.models || typeof variant.models !== 'object') {
            setBenchmarkSnapshotError(`Победитель ${winnerId} не найден в доступных пресетах`);
            return;
        }
        applyModelPreset(variant.models);
        setBenchmarkSnapshotError(null);
    };

    useEffect(() => {
        void loadBenchmarkSnapshot({ silent: true });
    }, [loadBenchmarkSnapshot]);

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
            const preferences = buildPlanningPreferences();
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
            const preferences = buildPlanningPreferences();
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

    const handleDownloadReleaseBundle = async () => {
        if (!runId || !selectedDataset) return;

        try {
            const blob = await downloadProtocolReleaseBundle(selectedDataset, runId);
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `release_bundle_${runId.slice(0, 8)}.zip`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError(err?.message || 'Ошибка скачивания release bundle');
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

    const columnsMeta = datasetReport?.scan_report?.columns || datasetReport?.columns || {};
    const columnEntries = Object.entries(columnsMeta);
    const numericColumns = columnEntries
        .filter(([, meta]) => {
            const t = String(meta?.type || '').toLowerCase();
            return t.includes('int') || t.includes('float') || t.includes('double') || t.includes('number');
        })
        .map(([name]) => name);
    const categoricalColumns = columnEntries
        .filter(([, meta]) => {
            const t = String(meta?.type || '').toLowerCase();
            return t.includes('object') || t.includes('category') || t.includes('bool');
        })
        .map(([name]) => name);
    const allColumns = columnEntries.map(([name]) => name);
    const studyDesignCore = studyDesign?.design && typeof studyDesign.design === 'object' ? studyDesign.design : {};
    const studyPolicy = studyDesign?.analysis_policy && typeof studyDesign.analysis_policy === 'object'
        ? studyDesign.analysis_policy
        : {};
    const endpointGroups = Array.isArray(studyDesignCore?.endpoint_groups) ? studyDesignCore.endpoint_groups : [];
    const displayOutcomes = Array.isArray(studyDesignCore?.outcomes) ? studyDesignCore.outcomes : [];
    const displayCatOutcomes = Array.isArray(studyDesignCore?.categorical_outcomes) ? studyDesignCore.categorical_outcomes : [];
    const displayDesignType = studyDesignCore?.design_type || 'unknown';
    const benchmarkRecommendedHasModels = Array.isArray(benchmarkRows)
        ? benchmarkRows.some(
            (row) => row && row.recommended && row.models && typeof row.models === 'object'
        )
        : false;
    const benchmarkSnapshotSummary = benchmarkSnapshot && typeof benchmarkSnapshot.summary === 'object'
        ? benchmarkSnapshot.summary
        : null;
    const benchmarkSnapshotCoverage = benchmarkSnapshot && typeof benchmarkSnapshot.coverage_gate === 'object'
        ? benchmarkSnapshot.coverage_gate
        : null;
    const benchmarkSnapshotWinners = benchmarkSnapshot && typeof benchmarkSnapshot.winners_by_profile === 'object'
        ? benchmarkSnapshot.winners_by_profile
        : {};
    const benchmarkSnapshotVariants = Array.isArray(benchmarkSnapshot?.variants)
        ? benchmarkSnapshot.variants.slice(0, 5)
        : [];
    const benchmarkSnapshotGeneratedAt = typeof benchmarkSnapshot?.generated_at === 'string'
        ? benchmarkSnapshot.generated_at
        : null;
    const benchmarkCaptureLast = benchmarkSnapshot && typeof benchmarkSnapshot.capture_last === 'object'
        ? benchmarkSnapshot.capture_last
        : null;
    const benchmarkCaptureStatus = benchmarkCaptureLast && typeof benchmarkCaptureLast.status === 'string'
        ? benchmarkCaptureLast.status
        : '';
    const benchmarkCaptureSkipReason = benchmarkCaptureLast && typeof benchmarkCaptureLast.skip_reason === 'string'
        ? benchmarkCaptureLast.skip_reason
        : null;
    const benchmarkCaptureGeneratedAt = benchmarkCaptureLast && typeof benchmarkCaptureLast.generated_at === 'string'
        ? benchmarkCaptureLast.generated_at
        : null;
    const benchmarkCaptureCoverage = benchmarkCaptureLast && typeof benchmarkCaptureLast.snapshot === 'object'
        && benchmarkCaptureLast.snapshot && typeof benchmarkCaptureLast.snapshot.coverage_gate === 'object'
        ? benchmarkCaptureLast.snapshot.coverage_gate
        : null;
    const benchmarkCaptureStatusClass = benchmarkCaptureStatus === 'completed'
        ? 'text-green-700'
        : benchmarkCaptureStatus === 'skipped'
            ? 'text-amber-700'
            : 'text-gray-600';
    const activeBenchmarkProfile = resolveBenchmarkProfile();
    const benchmarkActiveWinner = benchmarkSnapshotWinners && typeof benchmarkSnapshotWinners[activeBenchmarkProfile] === 'object'
        ? benchmarkSnapshotWinners[activeBenchmarkProfile]
        : null;
    const canPlan = Boolean(
        selectedDataset && userRequest.trim() && designConfirmed && !loading && !designSaving && !benchmarkLoading
    );

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
                        <label className="text-sm font-medium text-gray-700 block mb-2">Bootstrap CI</label>
                        <select
                            value={bootstrapCi ? 'on' : 'off'}
                            onChange={(e) => setBootstrapCi(e.target.value === 'on')}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="off">Отключен</option>
                            <option value="on">Включен</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Bootstrap samples</label>
                        <input
                            type="number"
                            min={100}
                            max={100000}
                            step={100}
                            value={bootstrapSamples}
                            onChange={(e) => {
                                const raw = Number(e.target.value);
                                setBootstrapSamples(
                                    Number.isFinite(raw) ? Math.max(100, Math.min(100000, Math.round(raw))) : 1000
                                );
                            }}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Validation profile</label>
                        <select
                            value={validationProfile}
                            onChange={(e) => setValidationProfile(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="auto">Auto (по analysis mode)</option>
                            <option value="publication">Publication (strict)</option>
                            <option value="focused">Focused (balanced)</option>
                            <option value="exploratory">Exploratory (soft)</option>
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Управляет strictness валидатора и политикой verifier reflection.
                        </p>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Validator strict (override)</label>
                        <select
                            value={validatorStrictOverride}
                            onChange={(e) => setValidatorStrictOverride(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="auto">Auto (from profile)</option>
                            <option value="true">Strict gate</option>
                            <option value="false">Soft gate</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Verifier reflection (override)</label>
                        <select
                            value={reflectionEnabledOverride}
                            onChange={(e) => setReflectionEnabledOverride(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="auto">Auto (from profile)</option>
                            <option value="true">Enabled</option>
                            <option value="false">Disabled</option>
                        </select>
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Reflection rounds (override)</label>
                        <input
                            type="number"
                            min={1}
                            max={10}
                            value={reflectionRoundsOverride}
                            onChange={(e) => setReflectionRoundsOverride(e.target.value)}
                            placeholder="Auto"
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        />
                    </div>
                    <div>
                        <label className="text-sm font-medium text-gray-700 block mb-2">Verifier repair correction</label>
                        <select
                            value={repairCorrectionOverride}
                            onChange={(e) => setRepairCorrectionOverride(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                            <option value="auto">Auto (from profile)</option>
                            <option value="fdr_bh">FDR (BH)</option>
                            <option value="fdr_by">FDR (BY)</option>
                            <option value="fdr_tsbky">FDR (BKY)</option>
                            <option value="bonferroni">Bonferroni</option>
                            <option value="holm">Holm</option>
                            <option value="sidak">Šidák</option>
                            <option value="none">None</option>
                        </select>
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
                            {numericColumns.length > 0 && (
                                <optgroup label="Числовые">
                                    {numericColumns.map((c) => (
                                        <option key={`num-${c}`} value={c}>{c}</option>
                                    ))}
                                </optgroup>
                            )}
                            {categoricalColumns.length > 0 && (
                                <optgroup label="Категориальные">
                                    {categoricalColumns.map((c) => (
                                        <option key={`cat-${c}`} value={c}>{c}</option>
                                    ))}
                                </optgroup>
                            )}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Если указано, используется как главный исход для описательных и регрессионных моделей.
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
                            {categoricalColumns.map((c) => (
                                <option key={`group-${c}`} value={c}>{c}</option>
                            ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-2">
                            Используется как основной фактор группового сравнения.
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
                            {(displayOutcomes.length > 0 || displayCatOutcomes.length > 0) && (
                                <div className="mt-3 text-xs text-gray-700">
                                    <div className="font-medium mb-1">Исходы в дизайне</div>
                                    <div className="flex flex-wrap gap-1">
                                        {displayOutcomes.slice(0, 10).map((col) => (
                                            <span key={`outcome-chip-${col}`} className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 border border-blue-200">
                                                {col}
                                            </span>
                                        ))}
                                        {displayCatOutcomes.slice(0, 8).map((col) => (
                                            <span key={`cat-outcome-chip-${col}`} className="px-2 py-0.5 rounded bg-purple-100 text-purple-700 border border-purple-200">
                                                {col}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {endpointGroups.length > 0 && (
                                <div className="mt-3 text-xs text-gray-700">
                                    <div className="font-medium mb-1">Endpoint группы</div>
                                    <div className="flex flex-wrap gap-1">
                                        {endpointGroups.slice(0, 8).map((item, idx) => (
                                            <span key={`endpoint-${item?.endpoint || idx}`} className="px-2 py-0.5 rounded bg-gray-200 text-gray-800 border border-gray-300">
                                                {item?.endpoint || `endpoint_${idx + 1}`} ({Array.isArray(item?.columns) ? item.columns.length : 0})
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {typeof studyPolicy?.multiplicity_correction === 'string' && (
                                <div className="mt-3 text-xs text-gray-600">
                                    Политика: multiplicity = <span className="font-medium">{formatCorrectionLabel(studyPolicy.multiplicity_correction)}</span>
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
                        <div className="flex flex-wrap gap-2 mb-3">
                            <button
                                type="button"
                                onClick={() => applyModelPreset(MODEL_PRESET_PROFILES.gemini_single)}
                                className="px-3 py-1.5 text-xs border border-gray-300 text-gray-700 bg-gray-50 rounded-md hover:bg-gray-100"
                            >
                                Только Gemini Flash 2.5
                            </button>
                            <button
                                type="button"
                                onClick={() => applyModelPreset(MODEL_PRESET_PROFILES.minimax_single)}
                                className="px-3 py-1.5 text-xs border border-teal-300 text-teal-700 bg-teal-50 rounded-md hover:bg-teal-100"
                            >
                                Только MiniMax M2.5
                            </button>
                            <button
                                type="button"
                                onClick={() => applyModelPreset(MODEL_PRESET_PROFILES.glm5_single)}
                                className="px-3 py-1.5 text-xs border border-emerald-300 text-emerald-700 bg-emerald-50 rounded-md hover:bg-emerald-100"
                            >
                                Только GLM-5
                            </button>
                            <button
                                type="button"
                                onClick={() => applyModelPreset(MODEL_PRESET_PROFILES.qwen_single)}
                                className="px-3 py-1.5 text-xs border border-indigo-300 text-indigo-700 bg-indigo-50 rounded-md hover:bg-indigo-100"
                            >
                                Только Qwen 3.5
                            </button>
                            <button
                                type="button"
                                onClick={applyRouterAiProfile}
                                className="px-3 py-1.5 text-xs border border-blue-300 text-blue-700 bg-blue-50 rounded-md hover:bg-blue-100"
                            >
                                Профиль RouterAI: M2.5 + GLM-5 + Qwen3.5
                            </button>
                            <button
                                type="button"
                                onClick={clearRoleModelsToServerDefaults}
                                className="px-3 py-1.5 text-xs border border-gray-300 text-gray-700 bg-white rounded-md hover:bg-gray-50"
                            >
                                Сбросить на серверные дефолты
                            </button>
                        </div>
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
                {briefValidationPolicy && typeof briefValidationPolicy === 'object' && (
                    <div className="mt-2 text-xs text-gray-600">
                        Brief policy: profile <span className="font-medium">{briefValidationPolicy.profile || 'auto'}</span>
                        {' '}• strict <span className="font-medium">{briefValidationPolicy.validator_strict ? 'true' : 'false'}</span>
                        {' '}• reflection <span className="font-medium">{briefValidationPolicy.reflection_enabled ? 'on' : 'off'}</span>
                        {' '}• repair <span className="font-medium">{formatCorrectionLabel(briefValidationPolicy.repair_correction)}</span>
                    </div>
                )}
                {getHypothesisItems(briefHypotheses, 4).length > 0 && (
                    <div className="mt-2 text-xs text-gray-700">
                        <div className="font-medium mb-1">Auto hypotheses (brief):</div>
                        {getHypothesisItems(briefHypotheses, 4).map((item, idx) => (
                            <div key={`brief-hyp-${idx}`} className="text-gray-600">
                                • {item.title || item.h1 || item.id || `H${idx + 1}`}
                                {item.suggested_method ? ` (${item.suggested_method})` : ''}
                            </div>
                        ))}
                    </div>
                )}
                <button
                    onClick={handlePlan}
                    disabled={!canPlan}
                    className="mt-4 w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-lg transition"
                >
                    {loading ? '⏳ Анализирую...' : '🚀 Анализировать'}
                </button>
                <button
                    type="button"
                    onClick={handleBenchmarkModels}
                    disabled={!canPlan || loading || benchmarkLoading}
                    className="mt-2 w-full bg-white border border-gray-300 hover:border-gray-400 disabled:bg-gray-100 disabled:text-gray-400 text-gray-700 font-medium py-2.5 px-6 rounded-lg transition"
                >
                    {benchmarkLoading ? '⏳ Сравниваю модели...' : '⚖️ Сравнить MiniMax / GLM-5 / Qwen / Gemini'}
                </button>
                {benchmarkError && (
                    <div className="mt-2 text-xs text-red-600">{benchmarkError}</div>
                )}
                {Array.isArray(benchmarkRows) && benchmarkRows.length > 0 && (
                    <div className="mt-4 rounded-lg border border-gray-200 overflow-hidden">
                        <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-600 flex items-center justify-between">
                            <span>Сравнение моделей (планирование на одном запросе)</span>
                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    onClick={handleApplyRecommendedBenchmarkModels}
                                    disabled={!benchmarkRecommendedHasModels}
                                    className="px-2 py-1 rounded border border-gray-300 bg-white text-[11px] hover:border-gray-400 disabled:bg-gray-100 disabled:text-gray-400"
                                >
                                    Применить рекомендованную
                                </button>
                                <span>{benchmarkRunAt ? new Date(benchmarkRunAt).toLocaleString() : ''}</span>
                            </div>
                        </div>
                        <div className="overflow-auto">
                            <table className="min-w-full text-xs">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="text-left px-3 py-2 border-b border-gray-200">Модель</th>
                                        <th className="text-left px-3 py-2 border-b border-gray-200">Статус</th>
                                        <th className="text-right px-3 py-2 border-b border-gray-200">Время, мс</th>
                                        <th className="text-right px-3 py-2 border-b border-gray-200">Шагов</th>
                                        <th className="text-right px-3 py-2 border-b border-gray-200">Quality</th>
                                        <th className="text-right px-3 py-2 border-b border-gray-200">Score</th>
                                        <th className="text-right px-3 py-2 border-b border-gray-200">Tokens</th>
                                        <th className="text-left px-3 py-2 border-b border-gray-200">Routing</th>
                                        <th className="text-left px-3 py-2 border-b border-gray-200">Policy</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {benchmarkRows.map((row) => (
                                        <tr key={`bench-${row.id}`} className={row.recommended ? 'bg-green-50' : ''}>
                                            <td className="px-3 py-2 border-b border-gray-100">
                                                {row.label}
                                                {row.recommended ? <span className="ml-2 text-[10px] text-green-700">рекомендуется</span> : null}
                                            </td>
                                            <td className="px-3 py-2 border-b border-gray-100">
                                                {row.status === 'ok' ? (
                                                    <span className="text-green-700">ok</span>
                                                ) : (
                                                    <span className="text-red-600" title={row.error || ''}>error</span>
                                                )}
                                            </td>
                                            <td className="px-3 py-2 border-b border-gray-100 text-right">{row.elapsedMs}</td>
                                            <td className="px-3 py-2 border-b border-gray-100 text-right">{row.stepCount}</td>
                                            <td className="px-3 py-2 border-b border-gray-100 text-right">
                                                {typeof row.qualityScore === 'number' ? row.qualityScore.toFixed(1) : '-'}
                                            </td>
                                            <td className="px-3 py-2 border-b border-gray-100 text-right">
                                                {typeof row.benchmarkScore === 'number' ? row.benchmarkScore.toFixed(3) : '-'}
                                            </td>
                                            <td className="px-3 py-2 border-b border-gray-100 text-right">
                                                {typeof row.tokenTotal === 'number' ? row.tokenTotal.toLocaleString() : '-'}
                                            </td>
                                            <td className="px-3 py-2 border-b border-gray-100">
                                                {row.status === 'ok' ? (
                                                    <span>
                                                        {row.fallbackUsed ? 'fallback' : 'direct'}
                                                        {Number.isFinite(Number(row.attemptCount)) ? ` • attempts:${Number(row.attemptCount)}` : ''}
                                                    </span>
                                                ) : '-'}
                                            </td>
                                            <td className="px-3 py-2 border-b border-gray-100">
                                                {row.policyProfile ? (
                                                    <span>
                                                        {row.policyProfile}
                                                        {typeof row.validatorStrict === 'boolean' ? ` • strict:${row.validatorStrict ? '1' : '0'}` : ''}
                                                        {row.repairCorrection ? ` • ${formatCorrectionLabel(row.repairCorrection)}` : ''}
                                                    </span>
                                                ) : '-'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
                <div className="mt-4 rounded-lg border border-gray-200 overflow-hidden">
                    <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-600 flex items-center justify-between">
                        <span>Исторический benchmark моделей (все run в workspace)</span>
                        <div className="flex items-center gap-2">
                            {benchmarkSnapshotGeneratedAt ? (
                                <span className="text-[11px] text-gray-500">
                                    {new Date(benchmarkSnapshotGeneratedAt).toLocaleString()}
                                </span>
                            ) : null}
                            <button
                                type="button"
                                onClick={() => handleLoadBenchmarkSnapshot()}
                                disabled={benchmarkSnapshotLoading}
                                className="px-2 py-1 rounded border border-gray-300 bg-white text-[11px] hover:border-gray-400 disabled:bg-gray-100 disabled:text-gray-400"
                            >
                                {benchmarkSnapshotLoading ? 'Обновляю...' : 'Обновить'}
                            </button>
                            <button
                                type="button"
                                onClick={handleApplyHistoricalWinner}
                                disabled={!benchmarkActiveWinner?.variant_id}
                                className="px-2 py-1 rounded border border-gray-300 bg-white text-[11px] hover:border-gray-400 disabled:bg-gray-100 disabled:text-gray-400"
                            >
                                Применить winner ({activeBenchmarkProfile})
                            </button>
                        </div>
                    </div>
                    {benchmarkSnapshotError && (
                        <div className="px-3 py-2 text-xs text-red-600 border-b border-gray-100">{benchmarkSnapshotError}</div>
                    )}
                    {benchmarkSnapshotLoading ? (
                        <div className="px-3 py-3 text-xs text-gray-500">Загружаю benchmark snapshot...</div>
                    ) : benchmarkSnapshotSummary ? (
                        <div className="p-3 space-y-3">
                            <div className="text-xs text-gray-700 flex flex-wrap gap-x-4 gap-y-1">
                                <span>Runs: <span className="font-medium">{benchmarkSnapshotSummary.runs_total ?? 0}</span></span>
                                <span>Variants: <span className="font-medium">{benchmarkSnapshotSummary.variants_total ?? 0}</span></span>
                                <span>Distinct: <span className="font-medium">{benchmarkSnapshotSummary.distinct_variants ?? 0}</span></span>
                                <span>
                                    Active profile winner ({activeBenchmarkProfile}):
                                    {' '}
                                    <span className="font-medium">{benchmarkActiveWinner?.variant_id || '-'}</span>
                                </span>
                                {benchmarkSnapshotCoverage && (
                                    <span className={benchmarkSnapshotCoverage.meets_threshold ? 'text-green-700' : 'text-amber-700'}>
                                        Coverage: {benchmarkSnapshotCoverage.meets_threshold ? 'PASS' : 'WARN'}
                                        {' '}({benchmarkSnapshotCoverage.runs_total ?? 0}/{benchmarkSnapshotCoverage.min_runs ?? 0})
                                    </span>
                                )}
                                {benchmarkCaptureLast && (
                                    <span className={benchmarkCaptureStatusClass}>
                                        Live capture: {formatCaptureStatus(benchmarkCaptureStatus)}
                                        {benchmarkCaptureSkipReason ? ` (${benchmarkCaptureSkipReason})` : ''}
                                    </span>
                                )}
                            </div>
                            {benchmarkCaptureLast && (
                                <div className="text-[11px] text-gray-600 flex flex-wrap gap-x-4 gap-y-1">
                                    <span>
                                        Capture dataset: <span className="font-medium">{benchmarkCaptureLast.dataset_id || '-'}</span>
                                    </span>
                                    <span>
                                        Capture run: <span className="font-medium">{benchmarkCaptureLast.run_id || '-'}</span>
                                    </span>
                                    <span>
                                        Capture recommended: <span className="font-medium">{benchmarkCaptureLast.recommended_id || '-'}</span>
                                    </span>
                                    {benchmarkCaptureGeneratedAt ? (
                                        <span>
                                            Captured at: <span className="font-medium">{new Date(benchmarkCaptureGeneratedAt).toLocaleString()}</span>
                                        </span>
                                    ) : null}
                                    {benchmarkCaptureCoverage && (
                                        <span className={benchmarkCaptureCoverage.meets_threshold ? 'text-green-700' : 'text-amber-700'}>
                                            Capture coverage: {benchmarkCaptureCoverage.meets_threshold ? 'PASS' : 'WARN'}
                                            {' '}({benchmarkCaptureCoverage.runs_total ?? 0}/{benchmarkCaptureCoverage.min_runs ?? 0})
                                        </span>
                                    )}
                                </div>
                            )}
                            <div className="grid md:grid-cols-3 gap-2">
                                {['publication', 'focused', 'exploratory'].map((profile) => {
                                    const winner = benchmarkSnapshotWinners?.[profile];
                                    return (
                                        <div key={`bench-winner-${profile}`} className="rounded border border-gray-200 bg-white px-2 py-2 text-xs">
                                            <div className="text-gray-500">{profile}</div>
                                            <div className="font-medium text-gray-900">{winner?.variant_id || '-'}</div>
                                            <div className="text-gray-600">
                                                share {formatPercent(winner?.share)} • n={winner?.total_runs ?? 0}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                            {benchmarkSnapshotVariants.length > 0 && (
                                <div className="overflow-auto">
                                    <table className="min-w-full text-xs">
                                        <thead className="bg-gray-50">
                                            <tr>
                                                <th className="text-left px-2 py-1 border-b border-gray-200">Variant</th>
                                                <th className="text-right px-2 py-1 border-b border-gray-200">Rec share</th>
                                                <th className="text-right px-2 py-1 border-b border-gray-200">Success</th>
                                                <th className="text-right px-2 py-1 border-b border-gray-200">Auto score</th>
                                                <th className="text-right px-2 py-1 border-b border-gray-200">Fallback</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {benchmarkSnapshotVariants.map((item) => (
                                                <tr key={`bench-variant-${item.id}`}>
                                                    <td className="px-2 py-1 border-b border-gray-100">{item.id || '-'}</td>
                                                    <td className="px-2 py-1 border-b border-gray-100 text-right">{formatPercent(item.recommendation_share)}</td>
                                                    <td className="px-2 py-1 border-b border-gray-100 text-right">{formatPercent(item.success_rate)}</td>
                                                    <td className="px-2 py-1 border-b border-gray-100 text-right">
                                                        {typeof item.mean_auto_score === 'number' ? item.mean_auto_score.toFixed(3) : '-'}
                                                    </td>
                                                    <td className="px-2 py-1 border-b border-gray-100 text-right">{formatPercent(item.fallback_rate)}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="px-3 py-3 text-xs text-gray-500">
                            Snapshot пока не загружен. Нажмите «Обновить».
                        </div>
                    )}
                </div>
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
                            {analysis.validation_policy && typeof analysis.validation_policy === 'object' && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Validation policy</strong>
                                    <div>
                                        profile: <span className="font-medium">{analysis.validation_policy.profile || 'auto'}</span>
                                        {' '}• strict: <span className="font-medium">{analysis.validation_policy.validator_strict ? 'true' : 'false'}</span>
                                        {' '}• reflection: <span className="font-medium">{analysis.validation_policy.reflection_enabled ? 'on' : 'off'}</span>
                                        {' '}• rounds: <span className="font-medium">{analysis.validation_policy.reflection_max_rounds ?? '-'}</span>
                                        {' '}• repair: <span className="font-medium">{formatCorrectionLabel(analysis.validation_policy.repair_correction)}</span>
                                    </div>
                                </div>
                            )}
                            {analysis.multiplicity_policy && typeof analysis.multiplicity_policy === 'object' && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Multiplicity policy</strong>
                                    <div>
                                        correction: <span className="font-medium">{formatCorrectionLabel(
                                            analysis.multiplicity_policy.correction || analysis.multiplicity_policy.multiplicity_correction
                                        )}</span>
                                        {' '}• post-hoc: <span className="font-medium">{formatCorrectionLabel(analysis.multiplicity_policy.post_hoc_correction)}</span>
                                        {' '}• applied steps: <span className="font-medium">{analysis.multiplicity_policy.n_applied_steps ?? 0}</span>
                                    </div>
                                </div>
                            )}
                            {analysis.bootstrap_policy && typeof analysis.bootstrap_policy === 'object' && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Bootstrap policy</strong>
                                    <div>
                                        enabled: <span className="font-medium">{analysis.bootstrap_policy.enabled ? 'on' : 'off'}</span>
                                        {' '}• samples: <span className="font-medium">{analysis.bootstrap_policy.samples ?? '-'}</span>
                                        {' '}• applied steps: <span className="font-medium">{analysis.bootstrap_policy.n_applied_steps ?? 0}</span>
                                    </div>
                                </div>
                            )}
                            {getHypothesisItems(analysis.hypotheses, 6).length > 0 && (
                                <div className="mb-3 text-sm text-gray-700">
                                    <strong className="block mb-1">Hypothesis discovery</strong>
                                    <div className="text-xs text-gray-600 mb-1">
                                        total: <span className="font-medium">{analysis?.hypotheses?.count ?? getHypothesisItems(analysis.hypotheses, 6).length}</span>
                                        {' '}• mode: <span className="font-medium">{analysis?.hypotheses?.analysis_mode || '-'}</span>
                                    </div>
                                    {getHypothesisItems(analysis.hypotheses, 6).map((item, idx) => (
                                        <div key={`plan-hyp-${idx}`} className="text-xs text-gray-600">
                                            • {item.title || item.h1 || item.id || `H${idx + 1}`}
                                            {item.suggested_method ? ` (${item.suggested_method})` : ''}
                                        </div>
                                    ))}
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

                            {analysis.protocol_validation && typeof analysis.protocol_validation === 'object' && (
                                <div className="bg-amber-50 border border-amber-200 rounded-lg px-6 py-4 mb-6">
                                    <h3 className="font-semibold mb-2 text-amber-900">Protocol validator</h3>
                                    <div className="text-sm text-amber-800">
                                        status: <span className="font-medium">{analysis.protocol_validation.status || '-'}</span>
                                        {' '}• strict: <span className="font-medium">{analysis.protocol_validation.strict ? 'true' : 'false'}</span>
                                        {' '}• failed steps: <span className="font-medium">{analysis.protocol_validation?.summary?.steps_failed ?? 0}</span>
                                    </div>
                                    {analysis.validation_policy && typeof analysis.validation_policy === 'object' && (
                                        <div className="mt-1 text-xs text-amber-700">
                                            profile: <span className="font-medium">{analysis.validation_policy.profile || 'auto'}</span>
                                            {' '}• reflection: <span className="font-medium">{analysis.validation_policy.reflection_enabled ? 'on' : 'off'}</span>
                                            {' '}• repair: <span className="font-medium">{formatCorrectionLabel(analysis.validation_policy.repair_correction)}</span>
                                        </div>
                                    )}
                                    {Array.isArray(analysis.protocol_validation.global_errors) && analysis.protocol_validation.global_errors.length > 0 && (
                                        <div className="mt-2 text-xs text-amber-700 space-y-1">
                                            {analysis.protocol_validation.global_errors.slice(0, 3).map((row, idx) => (
                                                <div key={`pv-global-${idx}`}>• {row?.message || row?.code || 'validation error'}</div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {analysis.agent_orchestration && typeof analysis.agent_orchestration === 'object' && (
                                <div className="bg-slate-50 border border-slate-200 rounded-lg px-6 py-4 mb-6">
                                    <h3 className="font-semibold mb-2 text-slate-900">Agent orchestration</h3>
                                    <div className="text-sm text-slate-700">
                                        state: <span className="font-medium">{analysis.agent_orchestration.state || '-'}</span>
                                        {' '}• status: <span className="font-medium">{analysis.agent_orchestration.status || '-'}</span>
                                        {' '}• rounds: <span className="font-medium">
                                            {analysis.agent_orchestration.rounds_executed || 0}
                                            /
                                            {analysis.agent_orchestration.max_rounds || 0}
                                        </span>
                                    </div>
                                    {Array.isArray(analysis.agent_orchestration.events) && analysis.agent_orchestration.events.length > 0 && (
                                        <div className="mt-2 text-xs text-slate-600 space-y-1">
                                            {analysis.agent_orchestration.events.slice(-8).map((ev, idx) => (
                                                <div key={`orch-${idx}`}>
                                                    [{ev?.role || '-'}] {ev?.state || '-'} → {ev?.action || '-'}
                                                    {ev?.next_state ? ` (${ev.next_state})` : ''}
                                                </div>
                                            ))}
                                        </div>
                                    )}
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
                                    <button
                                        onClick={handleDownloadReleaseBundle}
                                        disabled={!runId}
                                        className="flex-1 bg-slate-700 hover:bg-slate-800 disabled:bg-gray-300 text-white font-semibold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2"
                                    >
                                        🧩 Release ZIP
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
