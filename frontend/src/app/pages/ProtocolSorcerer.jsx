import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  getSorcererRecommendation,
  listDatasets,
  getDataset,
  getAlphaSetting,
  aiAnalyzeDesign,
  executeProtocolV2,
  cleanColumn,
  getScanReport,
  getSemantics,
  getDatasetDesignReview,
  confirmDatasetDesignReview,
  revokeDatasetDesignReview,
  getDatasetAnalysisSet,
  getDatasetPipelineState,
  freezeDatasetAnalysisSet,
  clearDatasetAnalysisSet,
} from '../../lib/api';
import Badge from '../components/ui/Badge';
import { useLocation, useNavigate } from 'react-router-dom';
import { buildAnalysisSetFreezeSpec } from '../utils/analysisSet';
import getManualMethodOptions from './protocol/manualMethodOptions';
import { buildContract } from './protocol/sorcererContract';
import { getMultiplicityLabel, getPostHocCorrectionLabel, getPostHocLabel } from './protocol/correctionLabels';
import ProtocolSorcererStepFlow from './protocol/ProtocolSorcererStepFlow';
import ProtocolSorcererApprovalPanel from './protocol/ProtocolSorcererApprovalPanel';
import ProtocolSorcererApplyForm from './protocol/ProtocolSorcererApplyForm';
import ProtocolSorcererRecommendationCard from './protocol/ProtocolSorcererRecommendationCard';
import useRepeatedOutcomeGroups from './protocol/useRepeatedOutcomeGroups';


export default function ProtocolSorcerer() {
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState(0); // Step 0: Dataset Selection
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [columns, setColumns] = useState([]);

  const [selections, setSelections] = useState({
    goal: '',
    structure: '',
    data_type: '',
    groups: '',
    normal_distribution: true
  });

  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showApplyForm, setShowApplyForm] = useState(false);
  const [approved, setApproved] = useState(false);
  const [chatText, setChatText] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState(null);
  const [chatDesign, setChatDesign] = useState(null);
  const [chatNotes, setChatNotes] = useState([]);
  const [designReviewConfirmed, setDesignReviewConfirmed] = useState(false);
  const [designReviewTimestamp, setDesignReviewTimestamp] = useState(null);
  const [designReviewSaving, setDesignReviewSaving] = useState(false);
  const [analysisSet, setAnalysisSet] = useState(null);
  const [analysisSetLoading, setAnalysisSetLoading] = useState(false);
  const [analysisSetSaving, setAnalysisSetSaving] = useState(false);
  const [analysisSetError, setAnalysisSetError] = useState(null);
  const [analysisSetUse, setAnalysisSetUse] = useState(false);
  const [analysisSetMode, setAnalysisSetMode] = useState('complete_case');
  const [analysisSetEnforce, setAnalysisSetEnforce] = useState('models');
  const [analysisSetStrict, setAnalysisSetStrict] = useState(true);
  const [pipelineState, setPipelineState] = useState(null);
  const [pipelineStateLoading, setPipelineStateLoading] = useState(false);
  const [pipelineStateError, setPipelineStateError] = useState(null);
  const [aiContext, setAiContext] = useState(null);
  const [aiContextLoading, setAiContextLoading] = useState(false);
  const [prepNormalizeCol, setPrepNormalizeCol] = useState('');
  const [prepBusy, setPrepBusy] = useState(false);
  const [prepError, setPrepError] = useState(null);
  const [variables, setVariables] = useState({
    target: '',
    group: '',
    outcome_cols: [],
    subject_col: '',
    event: '',
    timepoint: '',
    timepoint_value: '',
    all_numeric: true,
    auto_fallback: true,
    max_steps: 20000,
    multiplicity_correction: 'fdr_bh',
    post_hoc: 'none',
    post_hoc_correction: 'none',
    bootstrap_ci: false,
    bootstrap_samples: 1000,
    normality_test: 'suite',
    normality_decision: 'majority',
    homogeneity_test: 'levene',
    homogeneity_center: 'median',
    correlation_method: 'spearman',
    alpha: getAlphaSetting()
  });
  const aiContextSummary = useMemo(() => {
    const scan = aiContext?.scan;
    const report = scan?.scan_report || scan;
    const profile = scan?.profile || {};
    const columns = report?.columns || {};
    const semantics = aiContext?.semantics || {};
    const design = semantics?.design || {};

    const colValues = Object.values(columns);
    const numericCount = colValues.filter((c) => String(c?.type || '').includes('int') || String(c?.type || '').includes('float')).length;
    const catCount = colValues.filter((c) => String(c?.type || '').includes('object') || String(c?.type || '').includes('category')).length;

    return {
      rows: profile.row_count ?? report?.missing_report?.total_rows ?? null,
      cols: profile.col_count ?? (colValues.length || null),
      numericCount,
      catCount,
      groupCol: design.group_column || null,
      timeCol: design.time_column || null,
      subjectCol: design.subject_column || null,
    };
  }, [aiContext]);
  const autoPickRef = useRef(false);

  const chatProtocol = useMemo(() => (
    Array.isArray(chatDesign?.protocol) ? chatDesign.protocol : []
  ), [chatDesign?.protocol]);

  const hasChatProtocol = chatProtocol.length > 0;

  const columnNames = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .map((c) => (typeof c === 'string' ? c : c?.name))
      .filter(Boolean)
      .map((n) => String(n));
  }, [columns]);

  const prepColumns = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .map((c) => ({
        name: typeof c === 'string' ? String(c) : String(c?.name || ''),
        type: typeof c === 'object' && c ? String(c?.type || '') : '',
        missing_count: typeof c === 'object' && c ? c?.missing_count : null,
        unique_count: typeof c === 'object' && c ? c?.unique_count : null,
      }))
      .filter((c) => Boolean(c.name));
  }, [columns]);

  const prepCategoricalColumns = useMemo(() => {
    const list = Array.isArray(prepColumns) ? prepColumns : [];
    const out = list.filter((c) => ['categorical', 'text'].includes(String(c.type || ''))).map((c) => c.name);
    return out.length ? out : list.map((c) => c.name);
  }, [prepColumns]);

  const prepInfoByName = useMemo(() => {
    const out = new Map();
    for (const c of prepColumns) out.set(String(c.name), c);
    return out;
  }, [prepColumns]);

  const prepSummary = useMemo(() => {
    const list = Array.isArray(prepColumns) ? prepColumns : [];
    let missingCols = 0;
    let constantCols = 0;
    let categoricalCols = 0;
    for (const c of list) {
      const type = String(c?.type || '');
      if (type === 'categorical' || type === 'text') categoricalCols += 1;
      const miss = typeof c?.missing_count === 'number' && Number.isFinite(c.missing_count) ? c.missing_count : 0;
      if (miss > 0) missingCols += 1;
      const uniq = typeof c?.unique_count === 'number' && Number.isFinite(c.unique_count) ? c.unique_count : null;
      if (uniq != null && uniq <= 1) constantCols += 1;
    }
    return {
      total: list.length,
      categoricalCols,
      missingCols,
      constantCols,
    };
  }, [prepColumns]);

  const resetChatState = useCallback(() => {
    setApproved(false);
    setChatText('');
    setChatBusy(false);
    setChatError(null);
    setChatDesign(null);
    setChatNotes([]);
    setDesignReviewConfirmed(false);
    setDesignReviewTimestamp(null);
  }, []);

  const syncDesignReviewStatus = useCallback(async (datasetId) => {
    if (!datasetId) {
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
      return;
    }
    try {
      const payload = await getDatasetDesignReview(datasetId);
      const confirmed = Boolean(payload?.confirmed);
      setDesignReviewConfirmed(confirmed);
      setDesignReviewTimestamp(
        confirmed && typeof payload?.confirmed_at === 'string' ? payload.confirmed_at : null
      );
    } catch {
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
    }
  }, []);

  const syncAnalysisSetStatus = useCallback(async (datasetId) => {
    if (!datasetId) {
      setAnalysisSet(null);
      setAnalysisSetUse(false);
      return;
    }
    setAnalysisSetLoading(true);
    setAnalysisSetError(null);
    try {
      const payload = await getDatasetAnalysisSet(datasetId);
      setAnalysisSet(payload);
      const exists = Boolean(payload?.artifact_exists);
      setAnalysisSetUse(exists);
      if (exists) {
        if (typeof payload?.mode === 'string' && payload.mode) setAnalysisSetMode(payload.mode);
        if (typeof payload?.enforce === 'string' && payload.enforce) setAnalysisSetEnforce(payload.enforce);
      }
    } catch (e) {
      setAnalysisSet(null);
      setAnalysisSetUse(false);
      setAnalysisSetError(e?.message || 'Не удалось загрузить фиксированную выборку');
    } finally {
      setAnalysisSetLoading(false);
    }
  }, []);

  const syncPipelineState = useCallback(async (datasetId) => {
    if (!datasetId) {
      setPipelineState(null);
      setPipelineStateError(null);
      return;
    }
    setPipelineStateLoading(true);
    setPipelineStateError(null);
    try {
      const payload = await getDatasetPipelineState(datasetId);
      setPipelineState(payload && typeof payload === 'object' ? payload : null);
    } catch (e) {
      setPipelineState(null);
      setPipelineStateError(e?.message || 'Не удалось загрузить состояние pipeline');
    } finally {
      setPipelineStateLoading(false);
    }
  }, []);

  const handleToggleDesignReview = useCallback(async (checked) => {
    const datasetId = selectedDataset?.id;
    if (!datasetId || designReviewSaving) return;

    setDesignReviewSaving(true);
    try {
      if (checked) {
        const payload = await confirmDatasetDesignReview(datasetId, {
          source: 'sorcerer',
          actor: 'user',
        });
        const confirmed = Boolean(payload?.confirmed);
        setDesignReviewConfirmed(confirmed);
        setDesignReviewTimestamp(
          confirmed && typeof payload?.confirmed_at === 'string'
            ? payload.confirmed_at
            : (confirmed ? new Date().toISOString() : null)
        );
      } else {
        await revokeDatasetDesignReview(datasetId, {
          source: 'sorcerer',
          actor: 'user',
          reason: 'manual_uncheck',
        });
        setDesignReviewConfirmed(false);
        setDesignReviewTimestamp(null);
      }
    } catch (e) {
      alert(e?.message || 'Не удалось обновить Design Review');
    } finally {
      setDesignReviewSaving(false);
    }
  }, [designReviewSaving, selectedDataset?.id]);

  const contract = useMemo(() => buildContract({
    columnNames, chatProtocol, hasChatProtocol, recommendation, variables,
  }), [chatProtocol, columnNames, hasChatProtocol, recommendation, variables]);


  const approveDisabled = Boolean(chatBusy) || contract.issues.length > 0 || (!(recommendation && recommendation.method_id !== 'consult_statistician') && !hasChatProtocol);

  const ensureApproved = useCallback(() => {
    if (approved && contract.issues.length === 0) return true;
    if (contract.issues.length > 0) {
      alert('Согласование невозможно: заполните обязательные поля контракта');
      return false;
    }
    alert('Сначала согласуйте дизайн (Approve)');
    return false;
  }, [approved, contract.issues.length]);

  const ensureDesignReviewed = useCallback(() => {
    if (designReviewConfirmed) return true;
    alert('Перед запуском откройте и подтвердите Design Review');
    return false;
  }, [designReviewConfirmed]);

  const handlePrepNormalizeCategories = useCallback(async () => {
    const datasetId = selectedDataset?.id;
    const col = String(prepNormalizeCol || '').trim();
    if (!datasetId || !col) return;
    if (!confirm(`Нормализовать значения категорий в столбце "${col}"?`)) return;

    setPrepBusy(true);
    setPrepError(null);
    try {
      const profile = await cleanColumn(datasetId, col, 'normalize_categories');
      if (profile && typeof profile === 'object' && Array.isArray(profile.columns)) {
        setColumns(profile.columns);
      } else {
        const fresh = await getDataset(datasetId);
        setColumns(fresh.columns || []);
      }
    } catch (e) {
      setPrepError(e?.message ? String(e.message) : 'Не удалось нормализовать категории');
    } finally {
      setPrepBusy(false);
    }
  }, [prepNormalizeCol, selectedDataset?.id]);

  const approvalStorageKey = useMemo(() => (
    selectedDataset?.id ? `statproject_sorcerer_approval_${String(selectedDataset.id)}` : null
  ), [selectedDataset?.id]);

  useEffect(() => {
    if (!approvalStorageKey) return;
    try {
      const raw = sessionStorage.getItem(approvalStorageKey);
      const parsed = raw ? JSON.parse(raw) : null;
      if (!parsed || typeof parsed !== 'object') return;

      const restoredText = typeof parsed.chatText === 'string' ? parsed.chatText : '';
      const restoredDesign = parsed.chatDesign && typeof parsed.chatDesign === 'object' ? parsed.chatDesign : null;
      const restoredNotes = Array.isArray(parsed.chatNotes) ? parsed.chatNotes : [];
      const restoredApproved = Boolean(parsed.approved);
      const restoredVars = parsed.variables && typeof parsed.variables === 'object' ? parsed.variables : null;

      setChatText(restoredText);
      setChatDesign(restoredDesign);
      setChatNotes(restoredNotes);
      setApproved(restoredApproved);

      if (restoredVars) {
        setVariables((v) => ({
          ...v,
          group: typeof restoredVars.group === 'string' ? restoredVars.group : v.group,
          target: typeof restoredVars.target === 'string' ? restoredVars.target : v.target,
          outcome_cols: Array.isArray(restoredVars.outcome_cols) ? restoredVars.outcome_cols : v.outcome_cols,
          subject_col: typeof restoredVars.subject_col === 'string' ? restoredVars.subject_col : v.subject_col,
          event: typeof restoredVars.event === 'string' ? restoredVars.event : v.event,
          timepoint: typeof restoredVars.timepoint === 'string' ? restoredVars.timepoint : v.timepoint,
          timepoint_value: restoredVars.timepoint_value !== undefined ? restoredVars.timepoint_value : v.timepoint_value,
          predictors: typeof restoredVars.predictors === 'string' ? restoredVars.predictors : v.predictors,
        }));
      }
    } catch {
      return;
    }
  }, [approvalStorageKey]);

  useEffect(() => {
    if (!approvalStorageKey) return;
    try {
      sessionStorage.setItem(
        approvalStorageKey,
        JSON.stringify({
          chatText,
          chatDesign,
          chatNotes,
          approved,
          variables: {
            group: variables.group,
            target: variables.target,
            outcome_cols: variables.outcome_cols,
            subject_col: variables.subject_col,
            event: variables.event,
            timepoint: variables.timepoint,
            timepoint_value: variables.timepoint_value,
            predictors: variables.predictors,
          },
          ts: Date.now(),
        })
      );
    } catch {
      return;
    }
  }, [approvalStorageKey, approved, chatDesign, chatNotes, chatText, variables.event, variables.group, variables.outcome_cols, variables.predictors, variables.subject_col, variables.target, variables.timepoint, variables.timepoint_value]);

  useEffect(() => {
    if (!approved) return;
    if (contract.issues.length === 0) return;
    setApproved(false);
  }, [approved, contract.issues.length]);

  useEffect(() => {
    if (prepNormalizeCol) return;
    if (!prepCategoricalColumns.length) return;
    const candidate = String(variables.group || '').trim();
    if (candidate && prepCategoricalColumns.includes(candidate)) {
      setPrepNormalizeCol(candidate);
      return;
    }
    setPrepNormalizeCol(prepCategoricalColumns[0]);
  }, [prepCategoricalColumns, prepNormalizeCol, variables.group]);

  const methodId = recommendation?.method_id;
  const isRepeatedMeasures = methodId === 'rm_anova' || methodId === 'friedman';
  const needsTimepoint = methodId === 'kw_timepoints_all_numeric';
  const needsEvent = methodId === 'survival_km';
  const needsPredictors = Boolean(methodId?.includes('regression'));
  const allowsAllNumeric = !needsPredictors && !needsEvent && !needsTimepoint && !['pearson', 'spearman', 'kendall', 'chi_square'].includes(methodId);
  const allNumericEnabled = Boolean(variables.all_numeric) && allowsAllNumeric;

  const {
    rmBaseKey,
    setRmBaseKey,
    repeatedOutcomeGroups,
    rmGroup,
    rmTimeIndex,
  } = useRepeatedOutcomeGroups({
    columns,
    methodId,
    isRepeatedMeasures,
    setVariables,
  });

  const multiplicityLabel = useMemo(() => getMultiplicityLabel(variables.multiplicity_correction), [variables.multiplicity_correction]);
  const postHocCorrectionLabel = useMemo(() => getPostHocCorrectionLabel(variables.post_hoc_correction), [variables.post_hoc_correction]);
  const postHocLabel = useMemo(() => getPostHocLabel(variables.post_hoc), [variables.post_hoc]);

  const isPostHocRelevant = useMemo(() => {
    return allNumericEnabled || needsTimepoint || ['anova', 'anova_welch', 'kruskal'].includes(String(methodId || '').trim());
  }, [allNumericEnabled, methodId, needsTimepoint]);

  const manualMethodOptions = useMemo(() => getManualMethodOptions(selections), [selections]);


  const handleDatasetSelect = useCallback(async (ds) => {
    setSelectedDataset(ds);
    resetChatState();
    setPrepNormalizeCol('');
    setPrepBusy(false);
    setPrepError(null);
    setLoading(true);
    try {
      const data = await getDataset(ds.id);
      setColumns(data.columns || []);
      await syncDesignReviewStatus(ds.id);
      await syncAnalysisSetStatus(ds.id);
      await syncPipelineState(ds.id);
      setStep(1);
    } catch (e) {
      alert("Не удалось загрузить колонки: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [resetChatState, syncAnalysisSetStatus, syncDesignReviewStatus, syncPipelineState]);

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (!recommendation) return;
    if (!allowsAllNumeric && variables.all_numeric) {
      setVariables(v => ({ ...v, all_numeric: false }));
    }
  }, [allowsAllNumeric, recommendation, variables.all_numeric]);

  const loadDatasets = async () => {
    try {
      const list = await listDatasets();
      setDatasets(list);
    } catch (e) {
      console.error(e);
    }
  };

  const loadAiContext = useCallback(async () => {
    if (!selectedDataset?.id) {
      setAiContext(null);
      return;
    }
    setAiContextLoading(true);
    try {
      const [scan, semantics] = await Promise.all([
        getScanReport(selectedDataset.id),
        getSemantics(selectedDataset.id),
      ]);
      setAiContext({ scan, semantics });
    } catch (e) {
      console.error(e);
      setAiContext(null);
    } finally {
      setAiContextLoading(false);
    }
  }, [selectedDataset?.id]);

  useEffect(() => {
    loadAiContext();
  }, [loadAiContext]);

  useEffect(() => {
    if (autoPickRef.current) return;
    const params = new URLSearchParams(location.search);
    const datasetId = params.get('dataset') || params.get('dataset_id') || params.get('id');
    if (!datasetId) return;
    if (!Array.isArray(datasets) || datasets.length === 0) return;
    if (selectedDataset?.id && String(selectedDataset.id) === String(datasetId)) {
      autoPickRef.current = true;
      return;
    }
    const match = datasets.find((d) => String(d?.id) === String(datasetId));
    if (!match) return;
    autoPickRef.current = true;
    handleDatasetSelect(match);
  }, [datasets, handleDatasetSelect, location.search, selectedDataset?.id]);

  const handleSelect = (key, value) => {
    const newSelections = { ...selections, [key]: value };
    setSelections(newSelections);

    // Logic for steps
    if (key === 'goal') {
      if (value === 'compare_groups') setStep(2);
      else if (value === 'compare_timepoints') handleSubmit({ goal: 'compare_timepoints' });
      else if (value === 'relationship' || value === 'survival' || value === 'prediction') setStep(3);
      else setStep(0);
    }
    else if (step === 2) setStep(3); // structure -> data_type
    else if (step === 3) {
      if (newSelections.goal === 'compare_groups') setStep(4); // data_type -> groups
      else if (newSelections.goal === 'survival') handleSubmit(newSelections);
      else setStep(5); // choose method manually
    }
    else if (step === 4) setStep(5);
  };

  const handlePickMethod = (method) => {
    setRecommendation(method);
    setApproved(false);
    setDesignReviewConfirmed(false);
    setDesignReviewTimestamp(null);
    setShowApplyForm(false);
    setVariables(v => ({ ...v, target: '', group: '', outcome_cols: [], subject_col: '', event: '', timepoint: '', all_numeric: true, auto_fallback: true }));
    setRmBaseKey('');
  };

  const aiPickGroupColumn = useCallback(() => {
    const cols = Array.isArray(columns) ? columns : [];
    const scored = cols
      .map((c) => {
        const name = String(c?.name || '').trim();
        if (!name) return null;
        const nameL = name.toLowerCase();
        const t = String(c?.type || '').trim().toLowerCase();
        const unique = typeof c?.unique_count === 'number' ? c.unique_count : null;

        let score = 0;
        if (t === 'categorical') score += 4;
        if (t === 'numeric' && typeof unique === 'number' && unique > 1 && unique <= 12) score += 2;

        if (typeof unique === 'number') {
          if (unique >= 2 && unique <= 6) score += 4;
          if (unique >= 7 && unique <= 12) score += 2;
          if (unique > 50) score -= 6;
        }

        if (/(group|групп|arm|treat|treatment|cohort|coh|site|center|центр|sex|gender|пол)/.test(nameL)) score += 5;
        if (/(id|uuid|guid|patient|subject|person|номер|ид)/.test(nameL)) score -= 6;

        return { name, type: t, unique, score };
      })
      .filter(Boolean)
      .sort((a, b) => (b.score - a.score) || String(a.name).localeCompare(String(b.name)));

    const best = scored[0] || null;
    if (!best) return null;
    if (typeof best.unique === 'number' && best.unique < 2) return null;
    return best;
  }, [columns]);

  const handleAIBatchAllNumeric = useCallback(async () => {
    if (!selectedDataset?.id) {
      alert('Сначала выберите файл данных');
      return;
    }

    const bestGroup = aiPickGroupColumn();
    if (!bestGroup?.name) {
      alert('Не удалось автоматически выбрать группирующую колонку');
      return;
    }

    const groupUnique = typeof bestGroup.unique === 'number' ? bestGroup.unique : null;
    const method_id = groupUnique === 2 ? 't_test_ind' : 'kruskal';
    const nextRecommendation = {
      method_id,
      name: method_id === 't_test_ind' ? 't‑тест (независимые)' : 'Краскела–Уоллиса',
      description: 'Пакетный анализ всех числовых показателей по группам (с авто‑подбором теста и FDR).',
      assumptions: [],
    };

    const nextVariables = {
      ...variables,
      target: '',
      group: bestGroup.name,
      all_numeric: true,
      auto_fallback: true,
      multiplicity_correction: 'fdr_bh',
      post_hoc: groupUnique && groupUnique > 2 ? 'dunn' : 'none',
      post_hoc_correction: groupUnique && groupUnique > 2 ? 'bh' : 'none',
    };

    setRecommendation(nextRecommendation);
    setApproved(false);
    setDesignReviewConfirmed(false);
    setDesignReviewTimestamp(null);
    setShowApplyForm(true);
    setVariables(nextVariables);
  }, [aiPickGroupColumn, selectedDataset?.id, variables]);

  const handleSubmit = async (finalSelections) => {
    setLoading(true);
    try {
      const res = await getSorcererRecommendation(finalSelections);
      setRecommendation(res);
      setApproved(false);
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
    } catch (e) {
      console.error(e);
      alert("Не удалось получить рекомендацию: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChatSend = useCallback(async () => {
    if (!selectedDataset?.id) return;
    const text = String(chatText || '').trim();
    if (!text) return;
    setChatBusy(true);
    setChatError(null);
    try {
      const preferences = {
        source: 'sorcerer',
        max_steps: Number.isFinite(Number(variables.max_steps)) ? Number(variables.max_steps) : undefined,
        normality_test: variables.normality_test,
        normality_decision: variables.normality_decision,
        homogeneity_test: variables.homogeneity_test,
        homogeneity_center: variables.homogeneity_center,
        correlation_method: variables.correlation_method,
        multiplicity_correction: variables.multiplicity_correction,
        post_hoc: variables.post_hoc,
        post_hoc_correction: variables.post_hoc_correction,
        bootstrap_ci: Boolean(variables.bootstrap_ci),
        bootstrap_samples: Number.isFinite(Number(variables.bootstrap_samples))
          ? Math.max(100, Math.min(100000, Math.trunc(Number(variables.bootstrap_samples))))
          : 1000,
      };
      if (analysisSetUse && analysisSet?.artifact_exists && analysisSet?.analysis_set_id) {
        preferences.analysis_set_id = String(analysisSet.analysis_set_id);
        preferences.analysis_set_enforce = String(analysisSet.enforce || analysisSetEnforce || 'models');
        preferences.analysis_set_strict = Boolean(analysisSetStrict);
      }
      const res = await aiAnalyzeDesign(selectedDataset.id, text, {
        protocol: Array.isArray(chatDesign?.protocol) ? chatDesign.protocol : null,
        preferences,
      });
      setChatDesign(res);
      setChatNotes(Array.isArray(res?.notes) ? res.notes : []);
      setApproved(false);
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
    } catch (e) {
      setChatError(e?.message || 'Не удалось разобрать дизайн исследования');
    } finally {
      setChatBusy(false);
    }
  }, [
    analysisSet?.analysis_set_id,
    analysisSet?.artifact_exists,
    analysisSet?.enforce,
    analysisSetEnforce,
    analysisSetStrict,
    analysisSetUse,
    chatDesign?.protocol,
    chatText,
    selectedDataset?.id,
    variables.correlation_method,
    variables.homogeneity_center,
    variables.homogeneity_test,
    variables.max_steps,
    variables.multiplicity_correction,
    variables.bootstrap_ci,
    variables.bootstrap_samples,
    variables.normality_decision,
    variables.normality_test,
    variables.post_hoc,
    variables.post_hoc_correction,
  ]);

  const normalizeMethodId = useCallback((rawMethodId) => {
    const method = String(rawMethodId || '').trim().toLowerCase();
    if (!method) return '';
    if (method === 'fisher') return 'fisher_exact';
    if (method === 'kruskal_wallis') return 'kruskal';
    if (method === 'welch_t_test') return 't_test_welch';
    return method;
  }, []);

  const parsePredictors = useCallback((raw) => {
    if (Array.isArray(raw)) {
      return raw.map((x) => String(x || '').trim()).filter(Boolean);
    }
    if (typeof raw === 'string') {
      return raw.split(',').map((x) => String(x || '').trim()).filter(Boolean);
    }
    return [];
  }, []);

  const inferNumericTargets = useCallback(({ exclude = [] } = {}) => {
    const excluded = new Set((Array.isArray(exclude) ? exclude : []).map((x) => String(x || '').trim()).filter(Boolean));
    const out = [];
    for (const col of (Array.isArray(columns) ? columns : [])) {
      const name = typeof col === 'string' ? String(col) : String(col?.name || '');
      if (!name || excluded.has(name)) continue;
      const typeRaw = typeof col === 'string' ? '' : String(col?.type || '').toLowerCase();
      const looksNumericType = ['int', 'float', 'double', 'number', 'numeric', 'decimal'].some((token) => typeRaw.includes(token));
      if (looksNumericType) {
        out.push(name);
      }
    }
    if (out.length) return Array.from(new Set(out));
    const fallback = [];
    for (const col of (Array.isArray(columns) ? columns : [])) {
      const name = typeof col === 'string' ? String(col) : String(col?.name || '');
      if (name && !excluded.has(name)) fallback.push(name);
    }
    return Array.from(new Set(fallback));
  }, [columns]);

  const buildExecutionGlobals = useCallback((extra = {}) => {
    const base = (extra && typeof extra === 'object') ? { ...extra } : {};
    base.design_confirmed = Boolean(designReviewConfirmed);
    if (designReviewConfirmed) {
      base.design_review_timestamp = base.design_review_timestamp || designReviewTimestamp || new Date().toISOString();
    } else {
      delete base.design_review_timestamp;
    }
    if (analysisSetUse && analysisSet?.artifact_exists && analysisSet?.analysis_set_id) {
      base.analysis_set_id = String(analysisSet.analysis_set_id);
      base.analysis_set_strict = Boolean(analysisSetStrict);
    } else {
      delete base.analysis_set_id;
      delete base.analysis_set_strict;
    }
    if (Number.isFinite(Number(variables.max_steps))) {
      base.max_steps = Math.max(5, Math.min(20000, Number(variables.max_steps)));
    }
    if (variables.normality_test) base.normality_test = String(variables.normality_test);
    if (variables.normality_decision) base.normality_decision = String(variables.normality_decision);
    if (variables.homogeneity_test) base.homogeneity_test = String(variables.homogeneity_test);
    if (variables.homogeneity_center) base.homogeneity_center = String(variables.homogeneity_center);
    if (variables.correlation_method) base.correlation_method = String(variables.correlation_method);
    base.bootstrap_ci = Boolean(variables.bootstrap_ci);
    base.bootstrap_samples = Number.isFinite(Number(variables.bootstrap_samples))
      ? Math.max(100, Math.min(100000, Math.trunc(Number(variables.bootstrap_samples))))
      : 1000;
    base.source = base.source || 'sorcerer';
    return base;
  }, [
    analysisSet?.analysis_set_id,
    analysisSet?.artifact_exists,
    analysisSetStrict,
    analysisSetUse,
    designReviewConfirmed,
    designReviewTimestamp,
    variables.correlation_method,
    variables.homogeneity_center,
    variables.homogeneity_test,
    variables.max_steps,
    variables.bootstrap_ci,
    variables.bootstrap_samples,
    variables.normality_decision,
    variables.normality_test,
  ]);

  const buildManualProtocol = useCallback(({ targetOverride = null, sliceOverride = undefined } = {}) => {
    let method = normalizeMethodId(recommendation?.method_id);
    const corrMethod = String(variables.correlation_method || '').trim().toLowerCase();
    if (['pearson', 'spearman', 'kendall'].includes(method) && ['pearson', 'spearman', 'kendall'].includes(corrMethod)) {
      method = corrMethod;
    }
    if (!method || method === 'consult_statistician') {
      throw new Error('Не выбран валидный метод анализа');
    }

    const group = String(variables.group || '').trim();
    const target = String(targetOverride || variables.target || '').trim();
    const timepoint = String(variables.timepoint || '').trim();
    const event = String(variables.event || '').trim();
    const alternative = String(variables.alternative || '').trim().toLowerCase() || null;
    const outcomeCols = Array.isArray(variables.outcome_cols) ? variables.outcome_cols.map((x) => String(x || '').trim()).filter(Boolean) : [];
    const subjectCol = String(variables.subject_col || '').trim();
    const predictors = parsePredictors(variables.predictors);
    const baseConfig = {
      multiplicity_correction: variables.multiplicity_correction,
      post_hoc: variables.post_hoc,
      post_hoc_correction: variables.post_hoc_correction,
      bootstrap_ci: Boolean(variables.bootstrap_ci),
      bootstrap_samples: Number.isFinite(Number(variables.bootstrap_samples))
        ? Math.max(100, Math.min(100000, Math.trunc(Number(variables.bootstrap_samples))))
        : 1000,
      auto_fallback: Boolean(variables.auto_fallback),
      normality_test: variables.normality_test,
      normality_decision: variables.normality_decision,
      homogeneity_test: variables.homogeneity_test,
      homogeneity_center: variables.homogeneity_center,
      correlation_method: variables.correlation_method,
    };
    if (alternative) {
      baseConfig.alternative = alternative;
    }

    if (needsTimepoint) {
      if (!timepoint) throw new Error('Нужна колонка таймпоинта');
      if (!group) throw new Error('Нужна колонка группы');
      const step = {
        id: 'sorcerer_1',
        method: 'timepoint_batch_analysis',
        config: {
          ...baseConfig,
          split_by: timepoint,
          group,
          method_id: 'kruskal',
        },
      };
      return [step];
    }

    if (allNumericEnabled && !targetOverride) {
      if (!group) throw new Error('Нужна колонка группы');
      const exclude = [group];
      if (timepoint) exclude.push(timepoint);
      if (event) exclude.push(event);
      const targets = inferNumericTargets({ exclude });
      if (!targets.length) {
        throw new Error('Не найдены колонки для пакетного анализа');
      }
      return [
        {
          id: 'sorcerer_1',
          method: 'batch_analysis',
          config: {
            ...baseConfig,
            group,
            method_id: method,
            targets,
          },
        },
      ];
    }

    if (isRepeatedMeasures) {
      const minPoints = method === 'friedman' ? 3 : 2;
      if (outcomeCols.length < minPoints) {
        throw new Error(`Нужно outcome_cols (${minPoints}+)`);
      }
      if (method === 'rm_anova' && !subjectCol) {
        throw new Error('Нужна колонка субъекта (subject_col)');
      }
      return [
        {
          id: 'sorcerer_1',
          method,
          config: {
            ...baseConfig,
            outcome_cols: outcomeCols,
            ...(subjectCol ? { subject_col: subjectCol } : {}),
            ...(group ? { group_col: group } : {}),
          },
        },
      ];
    }

    if (!target) {
      throw new Error('Нужна целевая колонка');
    }

    const step = {
      id: 'sorcerer_1',
      method,
      config: {
        ...baseConfig,
        outcome: target,
      },
    };

    const filterValue = sliceOverride !== undefined ? sliceOverride : variables.timepoint_value;
    if (timepoint && filterValue !== null && filterValue !== undefined && String(filterValue).trim() !== '') {
      step.filter = {
        col: timepoint,
        op: 'eq',
        value: String(filterValue),
      };
    }

    if (method === 'survival_km') {
      if (!event) throw new Error('Нужна колонка события');
      step.config.event = event;
      if (group) step.config.group = group;
      return [step];
    }

    if (method === 'linear_regression' || method === 'logistic_regression') {
      if (!predictors.length) {
        throw new Error('Нужны предикторы');
      }
      step.config.predictors = predictors;
      if (group) step.config.group = group;
      return [step];
    }

    if (method === 'pearson' || method === 'spearman' || method === 'kendall' || method === 'chi_square' || method === 'fisher_exact') {
      if (!group) throw new Error('Нужна колонка группы/предиктора');
      step.config.group = group;
      return [step];
    }

    if (!group) {
      throw new Error('Нужна колонка группы');
    }
    step.config.group = group;
    if (method === 't_test_rel' || method === 'wilcoxon') {
      step.config.is_paired = true;
    }
    return [step];
  }, [
    allNumericEnabled,
    inferNumericTargets,
    isRepeatedMeasures,
    needsTimepoint,
    normalizeMethodId,
    parsePredictors,
    recommendation?.method_id,
    variables.alternative,
    variables.auto_fallback,
    variables.correlation_method,
    variables.event,
    variables.group,
    variables.homogeneity_center,
    variables.homogeneity_test,
    variables.bootstrap_ci,
    variables.bootstrap_samples,
    variables.multiplicity_correction,
    variables.normality_decision,
    variables.normality_test,
    variables.outcome_cols,
    variables.post_hoc,
    variables.post_hoc_correction,
    variables.predictors,
    variables.subject_col,
    variables.target,
    variables.timepoint,
    variables.timepoint_value,
  ]);

  const handleFreezeAnalysisSet = useCallback(async () => {
    const datasetId = selectedDataset?.id;
    if (!datasetId || analysisSetSaving) return;
    setAnalysisSetSaving(true);
    setAnalysisSetError(null);
    try {
      let protocol = null;
      if (hasChatProtocol) {
        protocol = chatProtocol;
      } else {
        protocol = buildManualProtocol();
      }

      const spec = buildAnalysisSetFreezeSpec(protocol, { mode: analysisSetMode });
      if (!spec) {
        throw new Error('В протоколе нет регрессионных моделей для фиксации N');
      }

      const payload = {
        actor: 'user',
        source: 'sorcerer',
        mode: analysisSetMode,
        enforce: analysisSetEnforce,
        required_non_missing: spec.required_non_missing,
        impute_columns: spec.impute_columns,
        notes: spec.notes,
      };
      const doc = await freezeDatasetAnalysisSet(datasetId, payload);
      setAnalysisSet(doc);
      setAnalysisSetUse(Boolean(doc?.artifact_exists));
      if (doc?.analysis_set_id) setAnalysisSetUse(true);
      await syncPipelineState(datasetId);
    } catch (e) {
      setAnalysisSetError(e?.message || 'Не удалось заморозить выборку');
    } finally {
      setAnalysisSetSaving(false);
    }
  }, [
    analysisSetEnforce,
    analysisSetMode,
    analysisSetSaving,
    buildManualProtocol,
    chatProtocol,
    hasChatProtocol,
    selectedDataset?.id,
    syncPipelineState,
  ]);

  const handleClearAnalysisSet = useCallback(async () => {
    const datasetId = selectedDataset?.id;
    if (!datasetId || analysisSetSaving) return;
    setAnalysisSetSaving(true);
    setAnalysisSetError(null);
    try {
      const doc = await clearDatasetAnalysisSet(datasetId, { actor: 'user', source: 'sorcerer' });
      setAnalysisSet(doc);
      setAnalysisSetUse(false);
      await syncPipelineState(datasetId);
    } catch (e) {
      setAnalysisSetError(e?.message || 'Не удалось сбросить выборку');
    } finally {
      setAnalysisSetSaving(false);
    }
  }, [analysisSetSaving, selectedDataset?.id, syncPipelineState]);

  const runProtocolAndNavigate = useCallback(async (protocol, { protocolName = null, globalsExtra = null } = {}) => {
    if (!selectedDataset?.id) {
      throw new Error('Сначала выберите датасет');
    }
    const globals = buildExecutionGlobals(globalsExtra || {});
    const res = await executeProtocolV2(
      selectedDataset.id,
      protocol,
      variables.alpha,
      protocolName,
      globals
    );
    const runId = res?.run_id;
    if (!runId) {
      throw new Error('Не удалось получить run_id');
    }
    navigate(
      `/results/${encodeURIComponent(String(selectedDataset.id))}?run=${encodeURIComponent(String(runId))}`,
      { state: { origin: 'sorcerer' } }
    );
  }, [buildExecutionGlobals, navigate, selectedDataset?.id, variables.alpha]);

  const handleRunApproved = async () => {
    if (!ensureApproved()) return;
    if (!ensureDesignReviewed()) return;
    if (!selectedDataset?.id) return;

    if (hasChatProtocol) {
      setLoading(true);
      try {
        await runProtocolAndNavigate(chatProtocol, {
          protocolName: chatDesign?.protocol_name,
          globalsExtra: chatDesign?.globals,
        });
      } catch (e) {
        alert(`Ошибка анализа: ${e?.message || 'Не удалось запустить протокол'}`);
      } finally {
        setLoading(false);
      }
      return;
    }

    await handleApply();
  };

  const handleApply = useCallback(async () => {
    if (!ensureApproved()) return;
    if (!ensureDesignReviewed()) return;
    const needsGroup = methodId !== 'survival_km' && !(methodId?.includes('regression')) && !isRepeatedMeasures;
    const needsTarget = methodId !== 'kw_timepoints_all_numeric' && !allNumericEnabled && !isRepeatedMeasures;
    const needsOutcomeCols = isRepeatedMeasures;
    const needsSubject = isRepeatedMeasures && methodId === 'rm_anova';

    if (
      (needsTarget && !variables.target) ||
      (needsGroup && !variables.group) ||
      (needsOutcomeCols && (!Array.isArray(variables.outcome_cols) || variables.outcome_cols.length < (methodId === 'friedman' ? 3 : 2))) ||
      (needsSubject && !variables.subject_col) ||
      (needsPredictors && !variables.predictors) ||
      (needsEvent && !variables.event) ||
      (needsTimepoint && !variables.timepoint)
    ) {
      alert("Выберите обязательные переменные");
      return;
    }
    setLoading(true);
    try {
      const protocol = buildManualProtocol();
      await runProtocolAndNavigate(protocol, {
        protocolName: recommendation?.name || 'Sorcerer protocol',
        globalsExtra: {
          recommendation: recommendation?.method_id || null,
          mode: 'sorcerer_manual',
        },
      });
    } catch (e) {
      console.error(e);
      alert("Ошибка анализа: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [allNumericEnabled, buildManualProtocol, ensureApproved, ensureDesignReviewed, isRepeatedMeasures, methodId, needsEvent, needsPredictors, needsTimepoint, recommendation?.method_id, recommendation?.name, runProtocolAndNavigate, variables]);

  const handlePredictorToggle = (colName) => {
    setVariables(prev => {
      const current = prev.predictors ? prev.predictors.split(',').filter(x => x) : [];
      const next = current.includes(colName)
        ? current.filter(c => c !== colName)
        : [...current, colName];
      return { ...prev, predictors: next.join(',') };
    });
  };

  const reset = () => {
    setStep(0);
    setSelections({
      goal: '', structure: '', data_type: '', groups: '', normal_distribution: true
    });
    setRecommendation(null);
    setShowApplyForm(false);
    resetChatState();
    setVariables({
      target: '',
      group: '',
      outcome_cols: [],
      subject_col: '',
      event: '',
      timepoint: '',
      timepoint_value: '',
      all_numeric: true,
      auto_fallback: true,
      max_steps: 20000,
      multiplicity_correction: 'fdr_bh',
      post_hoc: 'none',
      post_hoc_correction: 'none',
      bootstrap_ci: false,
      bootstrap_samples: 1000,
      normality_test: 'suite',
      normality_decision: 'majority',
      homogeneity_test: 'levene',
      homogeneity_center: 'median',
      correlation_method: 'spearman',
      alpha: getAlphaSetting()
    });
    setSelectedDataset(null);
    setPipelineState(null);
    setPipelineStateError(null);
  };

  const runDisabled = !approved || !designReviewConfirmed || designReviewSaving || loading || (!hasChatProtocol && (
    recommendation?.method_id === 'kw_timepoints_all_numeric'
      ? (!variables.group || !variables.timepoint)
      : ((variables.all_numeric && !['pearson', 'spearman', 'kendall', 'chi_square', 'survival_km'].includes(recommendation?.method_id) && !(recommendation?.method_id?.includes('regression')))
        ? (!variables.group)
        : (!variables.target || (recommendation?.method_id === 'survival_km' ? !variables.event :
          (recommendation?.method_id?.includes('regression') ? !variables.predictors : !variables.group))))
  ));

  return (
    <div className="max-w-4xl mx-auto px-4 pb-20">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-[color:var(--text-primary)] flex items-center gap-2">
          🧪 Конструктор клинического протокола
        </h1>
        {selectedDataset && (
          <Badge variant="accent">
            Файл данных: <span className="font-bold">{selectedDataset.filename}</span>
          </Badge>
        )}
      </div>

      {!recommendation ? (
        <ProtocolSorcererStepFlow
          step={step}
          datasets={datasets}
          manualMethodOptions={manualMethodOptions}
          onSelect={handleSelect}
          onPickMethod={handlePickMethod}
          onAIBatchAllNumeric={handleAIBatchAllNumeric}
          onDatasetSelect={handleDatasetSelect}
          onBack={() => (step > 1 ? setStep(step - 1) : setStep(0))}
          onOpenDesign={() => navigate(selectedDataset ? `/prep/${selectedDataset.id}` : '/datasets')}
          loading={loading}
          aiMode={false}
        />
      ) : (
        <div className="animate-in zoom-in-95 duration-500 space-y-8">
          {/* Recommendation Card */}
          <ProtocolSorcererRecommendationCard
            recommendation={recommendation}
            showApplyForm={showApplyForm}
            onReset={reset}
            onOpenApplyForm={() => setShowApplyForm(true)}
          />

          <ProtocolSorcererApprovalPanel
            approved={approved}
            onResetChat={resetChatState}
            onApprove={() => setApproved(true)}
            approveDisabled={approveDisabled}
            prepSummary={prepSummary}
            prepNormalizeCol={prepNormalizeCol}
            onPrepNormalizeColChange={setPrepNormalizeCol}
            prepBusy={prepBusy}
            selectedDatasetId={selectedDataset?.id}
            prepCategoricalColumns={prepCategoricalColumns}
            prepInfoByName={prepInfoByName}
            onOpenPrep={() => selectedDataset?.id && navigate(`/prep/${selectedDataset.id}`)}
            onPrepNormalizeCategories={handlePrepNormalizeCategories}
            prepError={prepError}
            contractIssues={contract.issues}
            hasChatProtocol={hasChatProtocol}
            recommendationMethodId={recommendation?.method_id}
            aiContextLoading={aiContextLoading}
            aiContextSummary={aiContextSummary}
            chatText={chatText}
            onChatTextChange={setChatText}
            chatError={chatError}
            onChatSend={handleChatSend}
            chatBusy={chatBusy}
            chatProtocol={chatDesign?.protocol}
            chatNotes={chatNotes}
          />

          {/* Apply Form - Appears below recommendation */}
          {showApplyForm && (
            <ProtocolSorcererApplyForm
              recommendation={recommendation}
              needsTimepoint={needsTimepoint}
              allNumericEnabled={allNumericEnabled}
              isRepeatedMeasures={isRepeatedMeasures}
              variables={variables}
              setVariables={setVariables}
              columns={columns}
              rmBaseKey={rmBaseKey}
              setRmBaseKey={setRmBaseKey}
              repeatedOutcomeGroups={repeatedOutcomeGroups}
              rmGroup={rmGroup}
              rmTimeIndex={rmTimeIndex}
              methodId={methodId}
              handlePredictorToggle={handlePredictorToggle}
              allowsAllNumeric={allowsAllNumeric}
              isPostHocRelevant={isPostHocRelevant}
              multiplicityLabel={multiplicityLabel}
              postHocCorrectionLabel={postHocCorrectionLabel}
              postHocLabel={postHocLabel}
              analysisSetMode={analysisSetMode}
              setAnalysisSetMode={setAnalysisSetMode}
              analysisSetEnforce={analysisSetEnforce}
              setAnalysisSetEnforce={setAnalysisSetEnforce}
              handleFreezeAnalysisSet={handleFreezeAnalysisSet}
              selectedDataset={selectedDataset}
              analysisSetSaving={analysisSetSaving}
              handleClearAnalysisSet={handleClearAnalysisSet}
              analysisSet={analysisSet}
              analysisSetStrict={analysisSetStrict}
              setAnalysisSetStrict={setAnalysisSetStrict}
              analysisSetUse={analysisSetUse}
              setAnalysisSetUse={setAnalysisSetUse}
              analysisSetLoading={analysisSetLoading}
              analysisSetError={analysisSetError}
              pipelineState={pipelineState}
              pipelineStateLoading={pipelineStateLoading}
              pipelineStateError={pipelineStateError}
              navigate={navigate}
              designReviewConfirmed={designReviewConfirmed}
              handleToggleDesignReview={handleToggleDesignReview}
              designReviewSaving={designReviewSaving}
              designReviewTimestamp={designReviewTimestamp}
              setShowApplyForm={setShowApplyForm}
              handleRunApproved={handleRunApproved}
              runDisabled={runDisabled}
              loading={loading}
            />
          )}
        </div>
      )}
    </div>
  );
}
