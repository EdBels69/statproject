import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  getSorcererRecommendation,
  listDatasets,
  getDataset,
  listDatasetColumns,
  getAlphaSetting,
  aiAnalyzeDesign,
  executeProtocolV2,
  cleanColumn,
  getScanReport,
  getSemantics,
  getStudyDesign,
  putStudyDesign,
  getDatasetDesignReview,
  confirmDatasetDesignReview,
  revokeDatasetDesignReview,
  getDatasetAnalysisSet,
  freezeDatasetAnalysisSet,
  clearDatasetAnalysisSet,
} from '../../lib/api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { useLocation, useNavigate } from 'react-router-dom';
import { buildAnalysisSetFreezeSpec } from '../utils/analysisSet';

function dedupeNames(values) {
  const out = [];
  for (const item of (Array.isArray(values) ? values : [])) {
    const text = String(item || '').trim();
    if (!text) continue;
    if (!out.includes(text)) out.push(text);
  }
  return out;
}

export default function ProtocolSorcerer() {
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState(0); // Step 0: Dataset Selection
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [columns, setColumns] = useState([]);
  const [allDatasetColumns, setAllDatasetColumns] = useState([]);

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
  const [studyDesignDraft, setStudyDesignDraft] = useState(null);
  const [studyDesignRevision, setStudyDesignRevision] = useState(null);
  const [studyDesignSaving, setStudyDesignSaving] = useState(false);
  const [studyDesignError, setStudyDesignError] = useState(null);
  const [numericOutcomeFilter, setNumericOutcomeFilter] = useState('');
  const [categoricalOutcomeFilter, setCategoricalOutcomeFilter] = useState('');
  const [analysisSet, setAnalysisSet] = useState(null);
  const [analysisSetLoading, setAnalysisSetLoading] = useState(false);
  const [analysisSetSaving, setAnalysisSetSaving] = useState(false);
  const [analysisSetError, setAnalysisSetError] = useState(null);
  const [analysisSetUse, setAnalysisSetUse] = useState(false);
  const [analysisSetMode, setAnalysisSetMode] = useState('complete_case');
  const [analysisSetEnforce, setAnalysisSetEnforce] = useState('models');
  const [analysisSetStrict, setAnalysisSetStrict] = useState(true);
  const [analysisProcess, setAnalysisProcess] = useState('discovery');
  const [allowDeepMining, setAllowDeepMining] = useState(false);
  const [externalValidationDatasetId, setExternalValidationDatasetId] = useState('');
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
    multiplicity_correction: 'fdr_bh',
    post_hoc: 'none',
    post_hoc_correction: 'none',
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
    const fullList = dedupeNames(allDatasetColumns);
    const list = Array.isArray(columns) ? columns : [];
    const profileList = list
      .map((c) => (typeof c === 'string' ? c : c?.name))
      .filter(Boolean)
      .map((n) => String(n));
    if (!fullList.length) return profileList;
    return dedupeNames([...fullList, ...profileList]);
  }, [allDatasetColumns, columns]);

  const externalValidationCandidates = useMemo(() => {
    const currentId = selectedDataset?.id ? String(selectedDataset.id) : '';
    return (Array.isArray(datasets) ? datasets : []).filter((ds) => {
      const id = String(ds?.id || '');
      if (!id) return false;
      return id !== currentId;
    });
  }, [datasets, selectedDataset?.id]);

  const numericColumnNames = useMemo(() => {
    const out = [];
    for (const col of (Array.isArray(columns) ? columns : [])) {
      const name = typeof col === 'string' ? String(col) : String(col?.name || '');
      if (!name) continue;
      const typeRaw = typeof col === 'string' ? '' : String(col?.type || '').toLowerCase();
      const isNumeric = ['int', 'float', 'double', 'number', 'numeric', 'decimal'].some((token) => typeRaw.includes(token));
      if (isNumeric && !out.includes(name)) out.push(name);
    }
    return out;
  }, [columns]);

  const categoricalColumnNames = useMemo(() => {
    const out = [];
    for (const col of (Array.isArray(columns) ? columns : [])) {
      const name = typeof col === 'string' ? String(col) : String(col?.name || '');
      if (!name) continue;
      const typeRaw = typeof col === 'string' ? '' : String(col?.type || '').toLowerCase();
      const isCategorical = ['categorical', 'text', 'object', 'string', 'category', 'bool'].some((token) => typeRaw.includes(token));
      if (isCategorical && !out.includes(name)) out.push(name);
    }
    return out;
  }, [columns]);

  const designOutcomeOptions = useMemo(() => {
    return dedupeNames([
      ...columnNames,
      ...numericColumnNames,
      ...categoricalColumnNames,
      ...(Array.isArray(studyDesignDraft?.outcomes) ? studyDesignDraft.outcomes : []),
      ...(Array.isArray(studyDesignDraft?.categorical_outcomes) ? studyDesignDraft.categorical_outcomes : []),
    ]);
  }, [categoricalColumnNames, columnNames, numericColumnNames, studyDesignDraft?.categorical_outcomes, studyDesignDraft?.outcomes]);

  const filteredNumericOutcomeOptions = useMemo(() => {
    const q = String(numericOutcomeFilter || '').trim().toLowerCase();
    if (!q) return designOutcomeOptions;
    return designOutcomeOptions.filter((name) => String(name).toLowerCase().includes(q));
  }, [designOutcomeOptions, numericOutcomeFilter]);

  const filteredCategoricalOutcomeOptions = useMemo(() => {
    const q = String(categoricalOutcomeFilter || '').trim().toLowerCase();
    if (!q) return designOutcomeOptions;
    return designOutcomeOptions.filter((name) => String(name).toLowerCase().includes(q));
  }, [categoricalOutcomeFilter, designOutcomeOptions]);

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

  const syncStudyDesignDraft = useCallback(async (datasetId) => {
    if (!datasetId) {
      setStudyDesignDraft(null);
      setStudyDesignRevision(null);
      setStudyDesignError(null);
      return;
    }
    try {
      const payload = await getStudyDesign(datasetId);
      const design = payload?.design && typeof payload.design === 'object' ? payload.design : {};
      setStudyDesignDraft({
        design_type: typeof design.design_type === 'string' && design.design_type ? design.design_type : 'cross_sectional',
        group_column: typeof design.group_column === 'string' ? design.group_column : '',
        time_column: typeof design.time_column === 'string' ? design.time_column : '',
        subject_column: typeof design.subject_column === 'string' ? design.subject_column : '',
        outcomes: dedupeNames(design.outcomes),
        categorical_outcomes: dedupeNames(design.categorical_outcomes),
      });
      const revision = Number(payload?.revision);
      setStudyDesignRevision(Number.isFinite(revision) && revision > 0 ? revision : 1);
      setStudyDesignError(null);
    } catch (e) {
      setStudyDesignDraft(null);
      setStudyDesignRevision(null);
      setStudyDesignError(e?.message || 'Не удалось загрузить study_design');
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

  const handleSaveStudyDesign = useCallback(async () => {
    const datasetId = selectedDataset?.id;
    if (!datasetId || !studyDesignDraft || studyDesignSaving) return;

    const groupColumn = String(studyDesignDraft.group_column || '').trim();
    const timeColumn = String(studyDesignDraft.time_column || '').trim();
    const subjectColumn = String(studyDesignDraft.subject_column || '').trim();
    const outcomes = dedupeNames(studyDesignDraft.outcomes);
    const categoricalOutcomes = dedupeNames(studyDesignDraft.categorical_outcomes);
    const predictorsFromText = String(variables.predictors || '')
      .split(',')
      .map((x) => String(x || '').trim())
      .filter(Boolean);
    const predictors = dedupeNames([
      ...predictorsFromText,
      ...outcomes,
      ...categoricalOutcomes,
      String(variables.target || '').trim(),
      groupColumn,
    ]);

    setStudyDesignSaving(true);
    setStudyDesignError(null);
    try {
      const payload = await putStudyDesign(datasetId, {
        actor: 'user',
        source: 'sorcerer',
        reason: 'manual_design_edit',
        expected_revision: Number.isFinite(Number(studyDesignRevision)) ? Number(studyDesignRevision) : undefined,
        design: {
          design_type: String(studyDesignDraft.design_type || 'cross_sectional').trim() || 'cross_sectional',
          group_column: groupColumn || null,
          time_column: timeColumn || null,
          subject_column: subjectColumn || null,
          outcomes,
          categorical_outcomes: categoricalOutcomes,
          predictors,
        },
      });

      const nextRevision = Number(payload?.revision);
      if (Number.isFinite(nextRevision) && nextRevision > 0) {
        setStudyDesignRevision(nextRevision);
      }
      await syncStudyDesignDraft(datasetId);
      await syncDesignReviewStatus(datasetId);
    } catch (e) {
      setStudyDesignError(e?.message || 'Не удалось сохранить study_design');
    } finally {
      setStudyDesignSaving(false);
    }
  }, [
    selectedDataset?.id,
    studyDesignDraft,
    studyDesignRevision,
    studyDesignSaving,
    syncDesignReviewStatus,
    syncStudyDesignDraft,
    variables.predictors,
    variables.target,
  ]);

  const patchStudyDesignDraft = useCallback((patch) => {
    setStudyDesignDraft((prev) => {
      const base = prev && typeof prev === 'object'
        ? prev
        : {
          design_type: 'cross_sectional',
          group_column: '',
          time_column: '',
          subject_column: '',
          outcomes: [],
          categorical_outcomes: [],
        };
      return { ...base, ...(patch && typeof patch === 'object' ? patch : {}) };
    });
  }, []);

  const contract = useMemo(() => {
    const existingCols = new Set(columnNames.map(String));
    const issues = [];

    const safeStr = (v) => {
      const s = String(v || '').trim();
      return s ? s : null;
    };

    const stepConfig = (s) => (s && typeof s === 'object' && s.config && typeof s.config === 'object') ? s.config : {};

    const findOutcome = (cfg) => safeStr(cfg.outcome) || safeStr(cfg.target);
    const findGroup = (cfg) => safeStr(cfg.group) || safeStr(cfg.group_col) || safeStr(cfg.predictor);

    const validateStep = (s, idx) => {
      const method = safeStr(s?.method) || 'unknown';
      const cfg = stepConfig(s);
      const title = safeStr(s?.name) || safeStr(s?.title) || `Шаг ${idx + 1}`;

      if (method === 'descriptive_compare') {
        const t = safeStr(cfg.target) || safeStr(cfg.outcome);
        const g = findGroup(cfg);
        if (!t || !g) issues.push(`${title}: нужны target/outcome и group`);
        if (t && !existingCols.has(t)) issues.push(`${title}: колонка ${t} не найдена`);
        if (g && !existingCols.has(g)) issues.push(`${title}: колонка ${g} не найдена`);
        return;
      }

      if (method === 'clustered_correlation') {
        const vars = cfg.variables;
        if (!Array.isArray(vars) || vars.length < 2) issues.push(`${title}: нужны variables (2+)`);
        if (Array.isArray(vars)) {
          for (const v of vars) {
            const col = safeStr(v);
            if (col && !existingCols.has(col)) issues.push(`${title}: колонка ${col} не найдена`);
          }
        }
        return;
      }

      if (method === 'cluster_profiles') {
        const vars = cfg.variables;
        if (!Array.isArray(vars) || vars.length < 2) issues.push(`${title}: нужны variables (2+)`);
        if (Array.isArray(vars)) {
          for (const v of vars) {
            const col = safeStr(v);
            if (col && !existingCols.has(col)) issues.push(`${title}: колонка ${col} не найдена`);
          }
        }
        return;
      }

      if (method === 'bootstrap_pipeline') {
        const o = findOutcome(cfg);
        if (!o) issues.push(`${title}: нужен outcome/target`);
        if (o && !existingCols.has(o)) issues.push(`${title}: колонка ${o} не найдена`);
        const g = findGroup(cfg);
        if (g && !existingCols.has(g)) issues.push(`${title}: колонка ${g} не найдена`);
        return;
      }

      if (method === 'external_validation') {
        const o = findOutcome(cfg);
        const predictors = Array.isArray(cfg.predictors)
          ? cfg.predictors.map((x) => safeStr(x)).filter(Boolean)
          : [];
        const extDatasetId = safeStr(cfg.external_dataset_id);
        if (!o) issues.push(`${title}: нужен outcome/target`);
        if (!predictors.length) issues.push(`${title}: нужны predictors (1+)`);
        if (!extDatasetId) issues.push(`${title}: нужен external_dataset_id`);
        if (o && !existingCols.has(o)) issues.push(`${title}: колонка ${o} не найдена`);
        for (const col of predictors) {
          if (col && !existingCols.has(col)) issues.push(`${title}: колонка ${col} не найдена`);
        }
        return;
      }

      if (method === 'mixed_effects') {
        const o = findOutcome(cfg);
        const t = safeStr(cfg.time);
        const g = findGroup(cfg);
        const sub = safeStr(cfg.subject);
        if (!o || !t || !g || !sub) issues.push(`${title}: нужны outcome, time, group, subject`);
        for (const col of [o, t, g, sub]) {
          if (col && !existingCols.has(col)) issues.push(`${title}: колонка ${col} не найдена`);
        }
        return;
      }

      if (method === 'rm_anova') {
        const outcomeCols = cfg.outcome_cols;
        const subject = safeStr(cfg.subject_col);
        if (!Array.isArray(outcomeCols) || outcomeCols.length < 2) issues.push(`${title}: нужны outcome_cols (2+)`);
        if (!subject) issues.push(`${title}: нужен subject_col`);
        if (Array.isArray(outcomeCols)) {
          for (const v of outcomeCols) {
            const col = safeStr(v);
            if (col && !existingCols.has(col)) issues.push(`${title}: колонка ${col} не найдена`);
          }
        }
        if (subject && !existingCols.has(subject)) issues.push(`${title}: колонка ${subject} не найдена`);
        return;
      }

      if (method === 'friedman') {
        const outcomeCols = cfg.outcome_cols;
        if (!Array.isArray(outcomeCols) || outcomeCols.length < 3) issues.push(`${title}: нужны outcome_cols (3+)`);
        if (Array.isArray(outcomeCols)) {
          for (const v of outcomeCols) {
            const col = safeStr(v);
            if (col && !existingCols.has(col)) issues.push(`${title}: колонка ${col} не найдена`);
          }
        }
        return;
      }

      const o = findOutcome(cfg);
      const g = findGroup(cfg);
      if (!o || !g) issues.push(`${title}: нужны outcome/target и group/predictor`);
      if (o && !existingCols.has(o)) issues.push(`${title}: колонка ${o} не найдена`);
      if (g && !existingCols.has(g)) issues.push(`${title}: колонка ${g} не найдена`);
    };

    if (hasChatProtocol) {
      chatProtocol.forEach((s, idx) => validateStep(s, idx));
      return {
        mode: 'chat',
        issues,
      };
    }

    const baseIssues = [];
    const m = safeStr(recommendation?.method_id);

    if (m && m !== 'consult_statistician') {
      const needsGroup = m !== 'survival_km' && !(m?.includes('regression')) && !(m === 'rm_anova' || m === 'friedman');
      const needsTarget = m !== 'kw_timepoints_all_numeric' && !(Boolean(variables.all_numeric) && !['pearson', 'spearman', 'chi_square'].includes(m)) && !(m === 'rm_anova' || m === 'friedman');
      const needsOutcomeCols = m === 'rm_anova' || m === 'friedman';
      const needsSubject = m === 'rm_anova';
      const needsEvent = m === 'survival_km';
      const needsTimepoint = m === 'kw_timepoints_all_numeric';
      const needsPredictors = Boolean(m?.includes('regression'));

      if (needsGroup && !safeStr(variables.group)) baseIssues.push('Нужна колонка группы');
      if (needsTarget && !safeStr(variables.target)) baseIssues.push('Нужна целевая колонка');
      if (needsEvent && !safeStr(variables.event)) baseIssues.push('Нужна колонка события');
      if (needsTimepoint && !safeStr(variables.timepoint)) baseIssues.push('Нужна колонка таймпоинта');
      if (needsPredictors && !safeStr(variables.predictors)) baseIssues.push('Нужны предикторы');
      if (needsOutcomeCols) {
        const min = m === 'friedman' ? 3 : 2;
        const cols = Array.isArray(variables.outcome_cols) ? variables.outcome_cols : [];
        if (cols.length < min) baseIssues.push(`Нужно outcome_cols (${min}+)`);
      }
      if (needsSubject && !safeStr(variables.subject_col)) baseIssues.push('Нужна колонка субъекта (subject_col)');

      const checkCols = (arr) => {
        for (const v of arr) {
          const col = safeStr(v);
          if (col && !existingCols.has(col)) baseIssues.push(`Колонка не найдена: ${col}`);
        }
      };

      if (safeStr(variables.group)) checkCols([variables.group]);
      if (safeStr(variables.target)) checkCols([variables.target]);
      if (safeStr(variables.event)) checkCols([variables.event]);
      if (safeStr(variables.timepoint)) checkCols([variables.timepoint]);
      if (safeStr(variables.subject_col)) checkCols([variables.subject_col]);
      if (Array.isArray(variables.outcome_cols)) checkCols(variables.outcome_cols);
    }

    return {
      mode: 'sorcerer',
      issues: baseIssues,
    };
  }, [chatProtocol, columnNames, hasChatProtocol, recommendation?.method_id, variables]);

  const resolvedAnalysisMode = useMemo(() => {
    const process = String(analysisProcess || '').trim().toLowerCase();
    if (process === 'confirmatory') return 'publication';
    if (process === 'data_prep') return 'data_prep';
    return 'discovery';
  }, [analysisProcess]);

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
    if (resolvedAnalysisMode !== 'publication') return true;
    if (designReviewConfirmed) return true;
    alert('Перед запуском откройте и подтвердите Design Review');
    return false;
  }, [designReviewConfirmed, resolvedAnalysisMode]);

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
      const restoredProcess = typeof parsed.analysisProcess === 'string' ? parsed.analysisProcess : null;
      const restoredDeepMining = Boolean(parsed.allowDeepMining);
      const restoredExternalDatasetId = typeof parsed.externalValidationDatasetId === 'string'
        ? parsed.externalValidationDatasetId
        : '';

      setChatText(restoredText);
      setChatDesign(restoredDesign);
      setChatNotes(restoredNotes);
      setApproved(restoredApproved);
      setAllowDeepMining(restoredDeepMining);
      setExternalValidationDatasetId(restoredExternalDatasetId);
      if (restoredProcess && ['discovery', 'confirmatory', 'data_prep'].includes(restoredProcess)) {
        setAnalysisProcess(restoredProcess);
      }

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
          analysisProcess,
          allowDeepMining,
          externalValidationDatasetId,
          ts: Date.now(),
        })
      );
    } catch {
      return;
    }
  }, [allowDeepMining, analysisProcess, approvalStorageKey, approved, chatDesign, chatNotes, chatText, externalValidationDatasetId, variables.event, variables.group, variables.outcome_cols, variables.predictors, variables.subject_col, variables.target, variables.timepoint, variables.timepoint_value]);

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

  useEffect(() => {
    const currentId = selectedDataset?.id ? String(selectedDataset.id) : '';
    const extId = String(externalValidationDatasetId || '').trim();
    if (!currentId || !extId) return;
    if (extId === currentId) {
      setExternalValidationDatasetId('');
    }
  }, [externalValidationDatasetId, selectedDataset?.id]);

  const methodId = recommendation?.method_id;
  const isRepeatedMeasures = methodId === 'rm_anova' || methodId === 'friedman';
  const needsTimepoint = methodId === 'kw_timepoints_all_numeric';
  const needsEvent = methodId === 'survival_km';
  const needsPredictors = Boolean(methodId?.includes('regression'));
  const allowsAllNumeric = !needsPredictors && !needsEvent && !needsTimepoint && !['pearson', 'spearman', 'chi_square'].includes(methodId);
  const allNumericEnabled = Boolean(variables.all_numeric) && allowsAllNumeric;

  const [rmBaseKey, setRmBaseKey] = useState('');

  const repeatedOutcomeGroups = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    const names = list
      .map((c) => (typeof c === 'string' ? c : c?.name))
      .filter(Boolean)
      .map((n) => String(n));

    const parse = (raw) => {
      const s0 = String(raw || '').trim();
      const s = s0.replace(/\s+/g, ' ').trim();
      const m = s.match(/(?:[_\-\s]*[([]?)(\d+)(?:[)\]]?)\s*$/);
      const idx = m ? Number.parseInt(m[1], 10) : null;
      const time = Number.isFinite(idx) ? idx : null;
      const label = s
        .replace(/(?:[_\-\s]*[([]?\d+[)\]]?)\s*$/g, '')
        .replace(/[_\-\s]+$/g, '')
        .trim() || s0;
      const key = String(label).toLowerCase() || s0.toLowerCase();
      return { key, label, time };
    };

    const minPoints = methodId === 'friedman' ? 3 : 2;

    const byBase = new Map();
    for (const n of names) {
      const p = parse(n);
      const k = p.key;
      if (!byBase.has(k)) byBase.set(k, { cols: [], labels: new Map() });
      const entry = byBase.get(k);
      entry.cols.push(n);
      const lab = String(p.label || '').trim();
      if (lab) entry.labels.set(lab, (entry.labels.get(lab) || 0) + 1);
    }

    const groups = Array.from(byBase.entries())
      .map(([k, entry]) => {
        const cols = Array.isArray(entry?.cols) ? entry.cols : [];
        const labels = entry?.labels instanceof Map ? entry.labels : new Map();
        const label = Array.from(labels.entries())
          .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length || a[0].localeCompare(b[0], 'ru'))
          .map(([name]) => name)[0] || k;

        const sorted = [...cols].sort((a, b) => {
          const ia = parse(a).time;
          const ib = parse(b).time;
          if (ia == null && ib == null) return a.localeCompare(b, 'ru');
          if (ia == null) return 1;
          if (ib == null) return -1;
          return ia - ib;
        });
        const indices = sorted
          .map((c) => parse(c).time)
          .filter((x) => x != null);
        const uniqIndices = Array.from(new Set(indices)).sort((a, b) => a - b);
        return { key: k, label, cols: sorted, indices: uniqIndices };
      })
      .filter((g) => g.cols.length >= minPoints)
      .sort((a, b) => b.cols.length - a.cols.length || String(a.label).localeCompare(String(b.label), 'ru'));

    return groups;
  }, [columns, methodId]);

  const rmTimeIndex = (raw) => {
    const s = String(raw || '').trim();
    const m = s.match(/(?:[_\-\s]*[([]?)(\d+)(?:[)\]]?)\s*$/);
    if (!m) return null;
    const n = Number.parseInt(m[1], 10);
    return Number.isFinite(n) ? n : null;
  };

  const rmGroup = useMemo(() => {
    if (!rmBaseKey) return null;
    return repeatedOutcomeGroups.find((g) => g.key === rmBaseKey) || null;
  }, [repeatedOutcomeGroups, rmBaseKey]);

  useEffect(() => {
    if (!isRepeatedMeasures) return;
    if (!rmBaseKey && repeatedOutcomeGroups.length > 0) {
      setRmBaseKey(repeatedOutcomeGroups[0].key);
    }
  }, [isRepeatedMeasures, repeatedOutcomeGroups, rmBaseKey]);

  useEffect(() => {
    if (!isRepeatedMeasures) return;
    if (!rmGroup) return;
    setVariables((v) => {
      const current = Array.isArray(v.outcome_cols) ? v.outcome_cols : [];
      const groupSet = new Set(rmGroup.cols.map(String));
      const hasForeign = current.some((c) => !groupSet.has(String(c)));
      if (current.length === 0 || hasForeign) {
        return { ...v, outcome_cols: rmGroup.cols };
      }
      const next = current.filter((c) => groupSet.has(String(c)));
      return next.length ? { ...v, outcome_cols: next } : { ...v, outcome_cols: rmGroup.cols };
    });
  }, [isRepeatedMeasures, rmGroup]);

  const isPostHocRelevant = useMemo(() => {
    return allNumericEnabled || needsTimepoint || ['anova', 'anova_welch', 'kruskal'].includes(String(methodId || '').trim());
  }, [allNumericEnabled, methodId, needsTimepoint]);

  const manualMethodOptions = useMemo(() => {
    const goal = selections.goal;
    const structure = selections.structure;
    const dataType = selections.data_type;
    const groups = selections.groups;

    const option = (method_id, name, description, assumptions = []) => ({
      method_id,
      name,
      description,
      assumptions,
    });

    if (goal === 'compare_groups') {
      if (dataType === 'categorical') {
        if (groups === '2') {
          return [
            option(
              'fisher',
              'Фишера (точный)',
              'Для малых выборок и 2×2 таблиц сопряжённости.',
              ['Независимость наблюдений', 'Таблица 2×2']
            ),
            option(
              'chi_square',
              'χ² (хи‑квадрат)',
              'Для сравнения распределений категорий между группами.',
              ['Независимость наблюдений', 'Достаточная наполняемость ячеек']
            ),
          ];
        }
        return [
          option(
            'chi_square',
            'χ² (хи‑квадрат)',
            'Для сравнения распределений категорий между группами.',
            ['Независимость наблюдений', 'Достаточная наполняемость ячеек']
          ),
        ];
      }

      if (dataType === 'numeric') {
        if (structure === 'paired') {
          if (groups === '2') {
            return [
              option(
                'wilcoxon',
                'Уилкоксона (парный)',
                'Непараметрическое сравнение двух связанных измерений.',
                ['Парные наблюдения']
              ),
              option(
                't_test_rel',
                't‑тест (парный)',
                'Параметрическое сравнение двух связанных измерений.',
                ['Нормальность разностей (желательно)']
              ),
            ];
          }

          return [
            option(
              'friedman',
              'Фридмана (повторные)',
              'Непараметрическое сравнение 3+ связанных измерений.',
              ['Повторные измерения']
            ),
            option(
              'rm_anova',
              'RM ANOVA (повторные)',
              'Параметрическое сравнение 3+ связанных измерений.',
              ['Нормальность', 'Сферичность (возможна коррекция)']
            ),
          ];
        }

        if (groups === '2') {
          return [
            option(
              'mann_whitney',
              'Манна–Уитни',
              'Непараметрическое сравнение двух независимых групп.',
              ['Независимость наблюдений']
            ),
            option(
              't_test_welch',
              't‑тест Уэлча',
              'Параметрическое сравнение средних при неравных дисперсиях.',
              ['Нормальность (желательно)', 'Допускает разные дисперсии']
            ),
            option(
              't_test_ind',
              't‑тест (независимые)',
              'Параметрическое сравнение средних двух независимых групп.',
              ['Нормальность (желательно)', 'Однородность дисперсий (для классического варианта)']
            ),
          ];
        }

        return [
          option(
            'kruskal',
            'Краскела–Уоллиса',
            'Непараметрическое сравнение 3+ независимых групп.',
            ['Независимость наблюдений']
          ),
          option(
            'anova_welch',
            'ANOVA Уэлча',
            'Параметрическая ANOVA при неравных дисперсиях.',
            ['Нормальность (желательно)', 'Не требует равенства дисперсий']
          ),
          option(
            'anova',
            'ANOVA (однофакторная)',
            'Параметрическое сравнение средних 3+ независимых групп.',
            ['Нормальность (желательно)', 'Однородность дисперсий']
          ),
        ];
      }
    }

    if (goal === 'relationship') {
      if (dataType === 'categorical') {
        return [
          option(
            'chi_square',
            'χ² (хи‑квадрат)',
            'Ассоциация между двумя категориальными переменными.',
            ['Достаточная наполняемость ячеек']
          ),
          option(
            'fisher',
            'Фишера (точный)',
            'Ассоциация для малых выборок и 2×2.',
            ['Таблица 2×2']
          ),
        ];
      }
      return [
        option(
          'spearman',
          'Спирмена',
          'Ранговая корреляция для ненормальных данных и выбросов.',
          ['Монотонная связь']
        ),
        option(
          'pearson',
          'Пирсона',
          'Линейная корреляция для приблизительно нормальных данных.',
          ['Линейность', 'Нет сильных выбросов']
        ),
      ];
    }

    if (goal === 'prediction') {
      if (dataType === 'categorical') {
        return [
          option(
            'logistic_regression',
            'Логистическая регрессия',
            'Прогноз бинарного исхода по предикторам.',
            ['Корректная кодировка исхода']
          ),
        ];
      }
      return [
        option(
          'linear_regression',
          'Линейная регрессия',
          'Прогноз числового исхода по предикторам.',
          ['Линейность', 'Гомоскедастичность (желательно)']
        ),
      ];
    }

    return [];
  }, [selections.data_type, selections.goal, selections.groups, selections.structure]);

  const handleDatasetSelect = useCallback(async (ds) => {
    setSelectedDataset(ds);
    resetChatState();
    setPrepNormalizeCol('');
    setPrepBusy(false);
    setPrepError(null);
    setLoading(true);
    const fetchAllColumnNames = async (datasetId) => {
      const out = [];
      let offset = 0;
      const pageSize = 2000;
      let total = null;
      while (true) {
        const payload = await listDatasetColumns(datasetId, { offset, limit: pageSize });
        const chunk = Array.isArray(payload?.columns) ? payload.columns.map((c) => String(c || '').trim()).filter(Boolean) : [];
        if (!chunk.length) break;
        out.push(...chunk);

        const payloadTotal = Number(payload?.total);
        total = Number.isFinite(payloadTotal) && payloadTotal >= 0 ? payloadTotal : total;
        offset += chunk.length;
        if ((total != null && offset >= total) || chunk.length < pageSize) break;
      }
      return dedupeNames(out);
    };

    try {
      const [data, allCols] = await Promise.all([
        getDataset(ds.id),
        fetchAllColumnNames(ds.id).catch(() => []),
      ]);
      setColumns(data.columns || []);
      setAllDatasetColumns(Array.isArray(allCols) && allCols.length ? allCols : dedupeNames((data.columns || []).map((c) => (typeof c === 'string' ? c : c?.name))));
      setNumericOutcomeFilter('');
      setCategoricalOutcomeFilter('');
      await syncDesignReviewStatus(ds.id);
      await syncStudyDesignDraft(ds.id);
      await syncAnalysisSetStatus(ds.id);
      setStep(1);
    } catch (e) {
      alert("Не удалось загрузить колонки: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [resetChatState, syncAnalysisSetStatus, syncDesignReviewStatus, syncStudyDesignDraft]);

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
    if (!text && analysisProcess !== 'data_prep') return;
    setChatBusy(true);
    setChatError(null);
    try {
      if (analysisProcess === 'data_prep') {
        const prepNotes = [
          'Выбран процесс Data Prep: статистический протокол не генерируется.',
          'Откройте подготовку датасета, выполните интерактивную очистку и вернитесь в Discovery/Confirmatory.',
        ];
        setChatDesign({
          status: 'completed',
          protocol_name: 'Data Preparation Workflow',
          protocol: [],
          notes: prepNotes,
          analysis_mode: 'data_prep',
        });
        setChatNotes(prepNotes);
        setApproved(false);
        setDesignReviewConfirmed(false);
        setDesignReviewTimestamp(null);
        navigate(`/prepare/${encodeURIComponent(String(selectedDataset.id))}`, { state: { origin: 'sorcerer' } });
        return;
      }

      const preferences = {
        source: 'sorcerer',
        workflow_track: analysisProcess,
        analysis_mode: resolvedAnalysisMode,
        mode: resolvedAnalysisMode,
      };
      if (allowDeepMining) {
        preferences.allow_data_mining = true;
      }
      const extDatasetId = String(externalValidationDatasetId || '').trim();
      const currentDatasetId = String(selectedDataset?.id || '').trim();
      if (extDatasetId && extDatasetId !== currentDatasetId) {
        preferences.external_validation_dataset_id = extDatasetId;
      }
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
  }, [allowDeepMining, analysisProcess, analysisSet?.analysis_set_id, analysisSet?.artifact_exists, analysisSet?.enforce, analysisSetEnforce, analysisSetStrict, analysisSetUse, chatDesign?.protocol, chatText, externalValidationDatasetId, navigate, resolvedAnalysisMode, selectedDataset?.id]);

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
    base.analysis_mode = base.analysis_mode || resolvedAnalysisMode;
    base.mode = base.mode || resolvedAnalysisMode;
    base.workflow_track = base.workflow_track || analysisProcess;
    if (allowDeepMining) {
      base.allow_data_mining = true;
    }
    const extDatasetId = String(externalValidationDatasetId || '').trim();
    const currentDatasetId = selectedDataset?.id ? String(selectedDataset.id) : '';
    if (extDatasetId && extDatasetId !== currentDatasetId) {
      base.external_validation_dataset_id = extDatasetId;
    }

    const requireDesignReview = resolvedAnalysisMode === 'publication';
    base.design_confirmed = Boolean(designReviewConfirmed);
    if (designReviewConfirmed) {
      base.design_review_timestamp = base.design_review_timestamp || designReviewTimestamp || new Date().toISOString();
    } else {
      delete base.design_review_timestamp;
    }
    if (!requireDesignReview && !designReviewConfirmed && base.allow_unconfirmed_design === undefined) {
      base.allow_unconfirmed_design = true;
    }
    if (requireDesignReview) {
      base.allow_unconfirmed_design = false;
    }
    if (analysisSetUse && analysisSet?.artifact_exists && analysisSet?.analysis_set_id) {
      base.analysis_set_id = String(analysisSet.analysis_set_id);
      base.analysis_set_strict = Boolean(analysisSetStrict);
    } else {
      delete base.analysis_set_id;
      delete base.analysis_set_strict;
    }
    base.source = base.source || 'sorcerer';
    return base;
  }, [allowDeepMining, analysisProcess, analysisSet?.analysis_set_id, analysisSet?.artifact_exists, analysisSetStrict, analysisSetUse, designReviewConfirmed, designReviewTimestamp, externalValidationDatasetId, resolvedAnalysisMode, selectedDataset?.id]);

  const buildManualProtocol = useCallback(({ targetOverride = null, sliceOverride = undefined } = {}) => {
    const method = normalizeMethodId(recommendation?.method_id);
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
      auto_fallback: Boolean(variables.auto_fallback),
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

    if (method === 'pearson' || method === 'spearman' || method === 'chi_square' || method === 'fisher_exact') {
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
    variables.event,
    variables.group,
    variables.multiplicity_correction,
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
    } catch (e) {
      setAnalysisSetError(e?.message || 'Не удалось сбросить выборку');
    } finally {
      setAnalysisSetSaving(false);
    }
  }, [analysisSetSaving, selectedDataset?.id]);

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
    if (analysisProcess === 'data_prep') {
      if (!selectedDataset?.id) return;
      navigate(`/prepare/${encodeURIComponent(String(selectedDataset.id))}`, { state: { origin: 'sorcerer' } });
      return;
    }
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
    if (analysisProcess === 'data_prep') {
      if (!selectedDataset?.id) return;
      navigate(`/prepare/${encodeURIComponent(String(selectedDataset.id))}`, { state: { origin: 'sorcerer' } });
      return;
    }
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
  }, [allNumericEnabled, analysisProcess, buildManualProtocol, ensureApproved, ensureDesignReviewed, isRepeatedMeasures, methodId, navigate, needsEvent, needsPredictors, needsTimepoint, recommendation?.method_id, recommendation?.name, runProtocolAndNavigate, selectedDataset?.id, variables]);

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
    setAnalysisProcess('discovery');
    setAllowDeepMining(false);
    setExternalValidationDatasetId('');
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
      multiplicity_correction: 'fdr_bh',
      post_hoc: 'none',
      post_hoc_correction: 'none',
      alpha: getAlphaSetting()
    });
    setSelectedDataset(null);
  };

  const requiresDesignReview = resolvedAnalysisMode === 'publication';
  const requiresApprove = analysisProcess !== 'data_prep';
  const runDisabled = (requiresApprove && !approved)
    || (requiresDesignReview && !designReviewConfirmed)
    || designReviewSaving
    || loading
    || (analysisProcess === 'data_prep' && !selectedDataset?.id)
    || (!hasChatProtocol && analysisProcess !== 'data_prep' && (
      recommendation?.method_id === 'kw_timepoints_all_numeric'
        ? (!variables.group || !variables.timepoint)
        : ((variables.all_numeric && !['pearson', 'spearman', 'chi_square', 'survival_km'].includes(recommendation?.method_id) && !(recommendation?.method_id?.includes('regression')))
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
        <div className="bg-[color:var(--white)] p-8 border border-[color:var(--border-color)] rounded-[2px] relative overflow-hidden">
          {/* Progress Bar (if step > 0) */}
          {step > 0 && (
            <div className="flex gap-2 mb-10">
              {[1, 2, 3, 4, 5].map(s => (
                <div key={s} className={`h-1.5 flex-1 rounded-[2px] transition-colors ${s <= step ? 'bg-[color:var(--accent)]' : 'bg-[color:var(--bg-secondary)]'}`} />
              ))}
            </div>
          )}

          {/* STEP 0: DATASET SELECTION */}
          {step === 0 && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="text-center mb-8">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--accent)] mb-4">
                  <span className="text-3xl">📊</span>
                </div>
                <h2 className="text-2xl font-bold text-[color:var(--text-primary)]">Выберите источник данных</h2>
                <p className="text-[color:var(--text-secondary)] mt-2">Выберите файл данных, чтобы начать дизайн протокола</p>
              </div>

              <div className="grid grid-cols-1 gap-3">
                {datasets.length === 0 ? (
                  <div className="p-10 border border-dashed border-[color:var(--border-color)] rounded-[2px] text-center text-[color:var(--text-secondary)]">
                    Файлы данных не найдены. Сначала загрузите файл во вкладке «Данные».
                  </div>
                ) : (
                  datasets.map(ds => (
                    <button
                      key={ds.id}
                      onClick={() => handleDatasetSelect(ds)}
                      className="flex items-center justify-between p-4 border border-[color:var(--border-color)] rounded-[2px] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] transition-colors text-left group"
                    >
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] flex items-center justify-center transition-colors">📄</div>
                        <div>
                          <div className="font-bold text-[color:var(--text-primary)]">{ds.filename}</div>
                          <div className="text-xs text-[color:var(--text-secondary)] font-mono">{ds.id.slice(0, 8)}...</div>
                        </div>
                      </div>
                      <span className="text-[color:var(--accent)] font-bold opacity-0 group-hover:opacity-100 transition-opacity">Выбрать →</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">Какова основная цель исследования?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="⚔️"
                  title="Сравнить группы"
                  desc="Различия между группами лечения или популяциями"
                  onClick={() => handleSelect('goal', 'compare_groups')}
                />
                <OptionCard
                  icon="∞"
                  title="ИИ: всё‑на‑всё по группам"
                  desc="Автовыбор группирующей колонки и пакетный анализ всех числовых показателей"
                  onClick={handleAIBatchAllNumeric}
                />
                <OptionCard
                  icon="⏱️"
                  title="Сравнить по точкам времени"
                  desc="Все числовые показатели на каждой точке (Краскел–Уоллис)"
                  onClick={() => handleSelect('goal', 'compare_timepoints')}
                />
                <OptionCard
                  icon="🔗"
                  title="Найти связи"
                  desc="Корреляции или ассоциации между переменными"
                  onClick={() => handleSelect('goal', 'relationship')}
                />
                <OptionCard
                  icon="📈"
                  title="Прогнозирование"
                  desc="Фокус на прогнозе исхода (регрессия)"
                  disabled
                />
                <OptionCard
                  icon="⏳"
                  title="Анализ выживаемости"
                  desc="Время до события (клиническая выживаемость)"
                  onClick={() => handleSelect('goal', 'survival')}
                />
                <OptionCard
                  icon="🔮"
                  title="Предсказать исход"
                  desc="Многофакторное прогнозирование (регрессия)"
                  onClick={() => handleSelect('goal', 'prediction')}
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">Как устроены группы?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="👥"
                  title="Независимые"
                  desc="Две или больше разных групп (плацебо vs препарат)"
                  onClick={() => handleSelect('structure', 'independent')}
                />
                <OptionCard
                  icon="🔄"
                  title="Парные / сопоставленные"
                  desc="Те же участники дважды или сопоставленные пары"
                  onClick={() => handleSelect('structure', 'paired')}
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">Какого типа данные у исхода?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="📏"
                  title="Числовые (непрерывные)"
                  desc="например: вес, давление, вирусная нагрузка"
                  onClick={() => handleSelect('data_type', 'numeric')}
                />
                <OptionCard
                  icon="🏷️"
                  title="Категориальные (номинальные)"
                  desc="например: выздоровел/нет, генотип, нежелательное явление"
                  onClick={() => handleSelect('data_type', 'categorical')}
                />
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">Сколько групп?</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <OptionCard
                  icon="🏘️"
                  title="Две группы"
                  desc="например: контроль vs лечение"
                  onClick={() => handleSelect('groups', '2')}
                />
                <OptionCard
                  icon="🏘️🏘️"
                  title="Больше двух (> 2)"
                  desc="например: дозовые группы (низкая/средняя/высокая)"
                  onClick={() => handleSelect('groups', '>2')}
                />
              </div>
            </div>
          )}

          {step === 5 && (
            <div className="animate-in fade-in slide-in-from-right-4 duration-350">
              <h2 className="text-xl font-bold mb-6 text-[color:var(--text-primary)]">Какой метод применить?</h2>
              <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
                <div className="text-xs text-[color:var(--text-secondary)] max-w-xl">
                  Здесь показываются базовые варианты для вашего дизайна. Перед запуском лучше привести категории и пропуски в порядок.
                </div>
                <Button
                  variant="ghost"
                  onClick={() => navigate(selectedDataset ? `/prepare/${selectedDataset.id}` : '/datasets')}
                  className="px-4"
                >
                  Подготовка данных →
                </Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {manualMethodOptions.map((m) => (
                  <OptionCard
                    key={m.method_id}
                    icon={m.method_id === 'kruskal' || m.method_id === 'mann_whitney' || m.method_id === 'wilcoxon' || m.method_id === 'friedman' || m.method_id === 'spearman' || m.method_id === 'fisher' ? '⬛' : '⬜'}
                    title={m.name}
                    desc={m.description}
                    onClick={() => handlePickMethod(m)}
                  />
                ))}
              </div>
            </div>
          )}

          {step > 0 && (
            <button
              onClick={() => step > 1 ? setStep(step - 1) : setStep(0)}
              className="mt-8 px-4 py-2 text-sm text-[color:var(--text-secondary)] hover:text-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] border border-transparent hover:border-[color:var(--border-color)] transition-colors"
            >
              ← Назад к предыдущему вопросу
            </button>
          )}
        </div>
      ) : (
        <div className="animate-in zoom-in-95 duration-500 space-y-8">
          {/* Recommendation Card */}
          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-10 text-center relative overflow-hidden">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-[2px] bg-[color:var(--bg-secondary)] text-[color:var(--accent)] mb-8 border border-[color:var(--border-color)]">
              <span className="text-4xl">💡</span>
            </div>
            <div className="text-[color:var(--text-secondary)] text-sm font-bold uppercase tracking-widest mb-2">Решение по протоколу</div>
            <h2 className="text-4xl font-black text-[color:var(--text-primary)] mb-6">{recommendation.name}</h2>
            <p className="text-xl text-[color:var(--text-secondary)] mb-10 max-w-2xl mx-auto leading-relaxed">{recommendation.description}</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10 max-w-xl mx-auto text-left">
              {recommendation.assumptions?.map((ass, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-[color:var(--text-secondary)] bg-[color:var(--bg-secondary)] px-4 py-2 rounded-[2px] border border-[color:var(--border-color)]">
                  <span className="text-[color:var(--accent)]">✓</span> {ass}
                </div>
              ))}
            </div>

            {!showApplyForm ? (
              <div className="flex justify-center flex-wrap gap-4">
                <Button variant="ghost" onClick={reset} className="px-8">
                  Начать заново
                </Button>
                {recommendation.method_id !== "consult_statistician" && (
                  <Button variant="primary" onClick={() => setShowApplyForm(true)} className="px-8">
                    Применить к файлу данных →
                  </Button>
                )}
              </div>
            ) : null}
          </div>

          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-6">
            <div className="flex items-start justify-between gap-6 flex-wrap">
              <div className="min-w-0">
                <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Согласование дизайна</div>
                <div className="mt-2 text-sm text-[color:var(--text-secondary)] max-w-2xl">
                  Опишите дизайн исследования человеческим языком — ИИ соберёт черновик протокола. Запуск доступен только после approve.
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className={approved ? 'px-3 py-2 rounded-[999px] bg-[color:var(--accent)] text-[color:var(--white)] text-xs font-black tracking-widest' : 'px-3 py-2 rounded-[999px] border border-[color:var(--border-color)] text-xs font-black tracking-widest text-[color:var(--text-secondary)]'}>
                  {approved ? 'СОГЛАСОВАНО' : 'НЕ СОГЛАСОВАНО'}
                </div>
                <Button
                  variant="ghost"
                  onClick={resetChatState}
                  className="px-4"
                >
                  Сбросить
                </Button>
                <Button
                  variant="primary"
                  onClick={() => setApproved(true)}
                  disabled={approveDisabled}
                  className="px-6"
                >
                  Approve
                </Button>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 lg:grid-cols-12 gap-4">
              <div className="lg:col-span-7 border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-secondary)]">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-[10px] font-black text-[color:var(--text-primary)] uppercase tracking-wide">Prep-чеклист</div>
                  <div className="flex items-center gap-2 flex-wrap justify-end">
                    <Badge variant={prepSummary.missingCols ? 'accent' : 'neutral'}>ПРОПУСКИ · {prepSummary.missingCols}</Badge>
                    <Badge variant={prepSummary.constantCols ? 'accent' : 'neutral'}>КОНСТАНТЫ · {prepSummary.constantCols}</Badge>
                    <Badge variant={prepSummary.categoricalCols ? 'neutral' : 'neutral'}>КАТЕГОРИИ · {prepSummary.categoricalCols}</Badge>
                  </div>
                </div>
                <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                  Быстро выровняйте орфографию/регистр/пробелы в категориях, затем переходите к полноценной подготовке.
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
                  <div className="md:col-span-2">
                    <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Нормализация категорий</div>
                    <select
                      className="mt-2 w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={prepNormalizeCol}
                      onChange={(e) => setPrepNormalizeCol(e.target.value)}
                      disabled={prepBusy || !selectedDataset?.id}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {prepCategoricalColumns.map((name) => {
                        const info = prepInfoByName.get(String(name));
                        const uniq = typeof info?.unique_count === 'number' && Number.isFinite(info.unique_count) ? info.unique_count : null;
                        const miss = typeof info?.missing_count === 'number' && Number.isFinite(info.missing_count) ? info.missing_count : null;
                        const suffix = [
                          uniq != null ? `уник. ${uniq}` : null,
                          miss != null ? `проп. ${miss}` : null,
                        ].filter(Boolean).join(' · ');

                        return (
                          <option key={String(name)} value={String(name)}>
                            {String(name)}{suffix ? ` — ${suffix}` : ''}
                          </option>
                        );
                      })}
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      onClick={() => selectedDataset?.id && navigate(`/prepare/${selectedDataset.id}`)}
                      disabled={!selectedDataset?.id || prepBusy}
                      className="px-4"
                    >
                      Подготовка →
                    </Button>
                    <Button
                      variant="primary"
                      onClick={handlePrepNormalizeCategories}
                      disabled={prepBusy || !selectedDataset?.id || !String(prepNormalizeCol || '').trim()}
                      className="px-5"
                    >
                      {prepBusy ? 'Обрабатываю…' : 'Нормализовать'}
                    </Button>
                  </div>
                </div>
                {prepError ? (
                  <div className="mt-3 text-xs font-semibold text-[color:var(--accent)]">{String(prepError)}</div>
                ) : null}
              </div>

              <div className="lg:col-span-5 border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-[10px] font-black text-[color:var(--text-primary)] uppercase tracking-wide">Контракт</div>
                  <Badge variant={contract.issues.length ? 'error' : 'success'}>
                    {contract.issues.length ? `ПРОБЛЕМЫ · ${contract.issues.length}` : 'OK'}
                  </Badge>
                </div>

                {contract.issues.length ? (
                  <div className="mt-3 space-y-1">
                    {contract.issues.slice(0, 8).map((it, idx) => (
                      <div key={idx} className="text-[11px] font-mono text-[color:var(--text-secondary)] break-words">
                        — {String(it)}
                      </div>
                    ))}
                    {contract.issues.length > 8 ? (
                      <div className="pt-1 text-[11px] font-mono text-[color:var(--text-muted)]">
                        …и ещё {contract.issues.length - 8}
                      </div>
                    ) : null}
                    <div className="pt-2 text-xs text-[color:var(--text-secondary)]">Approve заблокирован, пока не исправите обязательные поля.</div>
                  </div>
                ) : (
                  <div className="mt-3 text-sm text-[color:var(--text-secondary)]">
                    Контракт согласования чист. Можно approve и запускать.
                  </div>
                )}

                {!hasChatProtocol && recommendation?.method_id === 'consult_statistician' ? (
                  <div className="mt-3 text-xs text-[color:var(--text-secondary)]">
                    Выбран вариант «Консультация статистика» — протокол запуска не требуется.
                  </div>
                ) : null}
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-secondary)]">
                <div className="text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Чат</div>
                <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                  Пример: «3 группы, исход — выписан/нет, хотим сравнить доли, поправка на множественность не нужна».
                </div>
                <details className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-3 py-2">
                  <summary className="cursor-pointer text-[11px] font-semibold text-[color:var(--text-primary)]">
                    Что видит ИИ (метаданные)
                  </summary>
                  <div className="mt-2 text-[11px] text-[color:var(--text-secondary)] space-y-1">
                    {aiContextLoading ? (
                      <div>Загружаю метаданные…</div>
                    ) : (
                      <>
                        <div>Строк: {aiContextSummary.rows ?? '—'} · Колонок: {aiContextSummary.cols ?? '—'}</div>
                        <div>Числовых: {aiContextSummary.numericCount ?? '—'} · Категорий: {aiContextSummary.catCount ?? '—'}</div>
                        <div>
                          Группа: {aiContextSummary.groupCol || '—'} · Время: {aiContextSummary.timeCol || '—'} · Субъект: {aiContextSummary.subjectCol || '—'}
                        </div>
                      </>
                    )}
                  </div>
                </details>
                <textarea
                  value={chatText}
                  onChange={(e) => setChatText(e.target.value)}
                  placeholder="Опишите дизайн…"
                  className="mt-3 w-full min-h-[120px] border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] text-sm focus:border-[color:var(--accent)] focus:outline-none"
                />
                {chatError ? (
                  <div className="mt-2 text-xs font-semibold text-[color:var(--accent)]">{String(chatError)}</div>
                ) : null}
                <div className="mt-3 flex items-center justify-between gap-3">
                  <Button
                    variant="ghost"
                    onClick={() => selectedDataset?.id && navigate(`/prepare/${selectedDataset.id}`)}
                    disabled={!selectedDataset?.id}
                    className="px-4"
                  >
                    Подготовка данных
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleChatSend}
                    disabled={
                      chatBusy
                      || !selectedDataset?.id
                      || (analysisProcess !== 'data_prep' && !String(chatText || '').trim())
                    }
                    className="px-6"
                  >
                    {chatBusy ? 'Думаю…' : 'Собрать протокол'}
                  </Button>
                </div>
              </div>

              <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--white)]">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Черновик протокола</div>
                  <div className="text-xs font-mono text-[color:var(--text-secondary)]">
                    {(Array.isArray(chatDesign?.protocol) ? chatDesign.protocol.length : 0) ? `${chatDesign.protocol.length} шаг(ов)` : '—'}
                  </div>
                </div>

                {(Array.isArray(chatDesign?.protocol) && chatDesign.protocol.length) ? (
                  <div className="mt-3 space-y-2">
                    {chatDesign.protocol.slice(0, 12).map((s, idx) => (
                      <div key={String(s?.id || idx)} className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-2">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-xs font-black text-[color:var(--text-primary)] truncate">
                            {String(s?.name || s?.method || 'Шаг')}
                          </div>
                          <div className="text-[11px] font-mono text-[color:var(--text-secondary)]">{String(s?.method || '')}</div>
                        </div>
                        {s?.config && typeof s.config === 'object' ? (
                          <div className="mt-1 text-[11px] font-mono text-[color:var(--text-secondary)] break-words">
                            {Object.entries(s.config)
                              .filter(([, v]) => v !== null && v !== undefined && String(v) !== '')
                              .slice(0, 4)
                              .map(([k, v]) => `${k}=${String(v)}`)
                              .join(' · ')}
                          </div>
                        ) : null}
                      </div>
                    ))}
                    {chatNotes.length ? (
                      <div className="mt-3 border-l-2 border-[color:var(--accent)] pl-3 py-2 bg-[color:var(--bg-secondary)]">
                        <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Примечания</div>
                        <div className="mt-2 space-y-1">
                          {chatNotes.slice(0, 6).map((n, i) => (
                            <div key={i} className="text-xs text-[color:var(--text-primary)]">{String(n)}</div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-4 text-sm text-[color:var(--text-secondary)]">
                    Пока пусто. Напишите дизайн и нажмите «Собрать протокол».
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Apply Form - Appears below recommendation */}
          {showApplyForm && (
            <div className="bg-[color:var(--white)] p-8 border border-[color:var(--border-color)] rounded-[2px] animate-in slide-in-from-bottom-8 duration-500">
              <div className="flex items-center gap-3 mb-8">
                <div className="w-10 h-10 bg-[color:var(--accent)] text-[color:var(--white)] rounded-[2px] flex items-center justify-center font-bold">🛠️</div>
                <div>
                  <h3 className="font-bold text-xl text-[color:var(--text-primary)]">Настройка анализа</h3>
                  <p className="text-sm text-[color:var(--text-secondary)]">Сопоставление переменных для {recommendation.name}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                {!needsTimepoint && !allNumericEnabled && !isRepeatedMeasures && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">
                      {recommendation?.method_id === 'survival_km' ? 'Колонка длительности (время)' : 'Целевой исход'}
                    </label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">
                      {recommendation?.method_id === 'survival_km' ? 'например: дни до выздоровления' : 'Выберите колонку, которую хотите измерять'}
                    </p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.target}
                      onChange={e => setVariables({ ...variables, target: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {isRepeatedMeasures && (
                  <div className="space-y-4 col-span-full">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">
                          Показатель (динамика)
                        </label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">
                          Выберите блок переменных одной шкалы на разных точках.
                        </p>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={rmBaseKey}
                          onChange={(e) => setRmBaseKey(e.target.value)}
                        >
                          <option value="">-- Выберите блок --</option>
                          {repeatedOutcomeGroups.map((g) => (
                            <option key={g.key} value={g.key}>{g.label} ({g.cols.length})</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Субъект (ID)</label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">Колонка идентификатора пациента/ответчика.</p>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.subject_col}
                          onChange={(e) => setVariables((v) => ({ ...v, subject_col: e.target.value }))}
                        >
                          <option value="">-- Выберите ID --</option>
                          {columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Межгрупповой фактор (опц.)</label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">Нужно только если сравниваете группы между собой.</p>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.group}
                          onChange={(e) => setVariables((v) => ({ ...v, group: e.target.value }))}
                        >
                          <option value="">-- Не задавать --</option>
                          {columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-secondary)]">
                      <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                          <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Точки и дистанция</div>
                          <div className="mt-1 text-xs text-[color:var(--text-secondary)]">Выберите конкретные точки (например 1–6) или удалите лишние.</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              if (!rmGroup) return;
                              setVariables((v) => ({ ...v, outcome_cols: rmGroup.cols }));
                            }}
                            disabled={!rmGroup}
                            className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] disabled:opacity-40"
                          >
                            Сбросить
                          </button>
                        </div>
                      </div>

                      {rmGroup && rmGroup.indices.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {rmGroup.indices.map((idx) => {
                            const curr = Array.isArray(variables.outcome_cols) ? variables.outcome_cols : [];
                            const selectedIdx = new Set(curr.map((c) => rmTimeIndex(c)).filter((x) => x != null));
                            const isOn = selectedIdx.has(idx);
                            return (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  const minPoints = methodId === 'friedman' ? 3 : 2;
                                  const currCols = Array.isArray(variables.outcome_cols) ? variables.outcome_cols : [];
                                  const currIdx = Array.from(new Set(currCols.map((c) => rmTimeIndex(c)).filter((x) => x != null))).sort((a, b) => a - b);
                                  const nextIdx = (() => {
                                    const set = new Set(currIdx);
                                    if (set.has(idx)) set.delete(idx);
                                    else set.add(idx);
                                    return Array.from(set).sort((a, b) => a - b);
                                  })();
                                  if (nextIdx.length < minPoints) return;
                                  const wanted = new Set(nextIdx);
                                  const nextCols = rmGroup.cols.filter((c) => {
                                    const ti = rmTimeIndex(c);
                                    return ti != null && wanted.has(ti);
                                  });
                                  if (nextCols.length < minPoints) return;
                                  setVariables((v) => ({ ...v, outcome_cols: nextCols }));
                                }}
                                className={
                                  isOn
                                    ? 'h-8 px-3 rounded-[999px] bg-[color:var(--accent)] text-[color:var(--white)] text-xs font-black tracking-widest'
                                    : 'h-8 px-3 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-xs font-black tracking-widest text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)]'
                                }
                                aria-label={`Переключить точку ${idx}`}
                              >
                                {idx}
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {(Array.isArray(variables.outcome_cols) ? variables.outcome_cols : []).map((c) => (
                            <div key={String(c)} className="inline-flex items-center gap-2 px-2.5 py-1 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)]">
                              <div className="text-xs font-mono text-[color:var(--text-primary)] truncate max-w-[240px]">{String(c)}</div>
                              <button
                                type="button"
                                onClick={() => setVariables((v) => ({
                                  ...v,
                                  outcome_cols: (Array.isArray(v.outcome_cols) ? v.outcome_cols : []).filter((x) => String(x) !== String(c))
                                }))}
                                className="text-xs font-semibold text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                aria-label="Удалить"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {recommendation?.method_id === 'kw_timepoints_all_numeric' && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Точка времени</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Колонка, по которой разбиваем на визиты/временные точки</p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.timepoint}
                      onChange={e => setVariables({ ...variables, timepoint: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {recommendation?.method_id === 'survival_km' && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Событие (цензурирование)</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Колонка, где 1 — событие, 0 — цензура</p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.event}
                      onChange={e => setVariables({ ...variables, event: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {(recommendation?.method_id === 'linear_regression' || recommendation?.method_id === 'logistic_regression') ? (
                  <div className="space-y-4 col-span-full">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Предикторы (входные факторы)</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Выберите одну или несколько колонок, которые могут предсказывать исход</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {columns.map(c => (
                        <button
                          key={c.name}
                          onClick={() => handlePredictorToggle(c.name)}
                          className={`p-3 rounded-[2px] border text-xs font-bold transition-colors ${variables.predictors?.split(',').includes(c.name)
                            ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]'
                            : 'border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)]'
                            }`}
                        >
                          {c.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : !isRepeatedMeasures ? (
                  <div className={`space-y-2 ${(!needsTimepoint && allNumericEnabled) ? 'col-span-full' : ''}`.trim()}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Группирующий фактор</label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">Выберите колонку, которая задаёт группы (для выживаемости необязательно)</p>
                      </div>
                      {allowsAllNumeric && !isRepeatedMeasures && (
                        <button
                          type="button"
                          onClick={() => setVariables(v => ({ ...v, all_numeric: !v.all_numeric }))}
                          className={`shrink-0 mt-1 px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${variables.all_numeric ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)]'}`}
                        >
                          Все количественные
                        </button>
                      )}
                    </div>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.group}
                      onChange={e => setVariables({ ...variables, group: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                ) : null}
              </div>

              {(allNumericEnabled || needsTimepoint || isPostHocRelevant) && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--bg-secondary)] mb-10">
                  <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Множественные сравнения</div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                    {(allNumericEnabled || needsTimepoint) && (
                      <div className="space-y-2">
                        <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Поправка (batch)</label>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.multiplicity_correction}
                          onChange={(e) => setVariables(v => ({ ...v, multiplicity_correction: e.target.value }))}
                        >
                          <option value="fdr_bh">FDR (Benjamini–Hochberg)</option>
                          <option value="fdr_by">FDR (Benjamini–Yekutieli)</option>
                          <option value="fdr_tsbky">FDR (BKY)</option>
                          <option value="bonferroni">Bonferroni</option>
                          <option value="holm">Holm</option>
                          <option value="holm-sidak">Holm–Šidák</option>
                          <option value="sidak">Šidák</option>
                          <option value="none">Без поправки</option>
                        </select>
                        <div className="text-xs text-[color:var(--text-secondary)] leading-snug">
                          Поправка применяется между разными переменными в batch (много p по разным показателям).
                        </div>
                      </div>
                    )}

                    {isPostHocRelevant && (
                      <div className="space-y-2">
                        <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Пост‑хок (между группами)</label>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.post_hoc}
                          onChange={(e) => setVariables(v => ({ ...v, post_hoc: e.target.value }))}
                        >
                          <option value="none">Не делать</option>
                          <option value="dunn">Dunn (для ранговых)</option>
                          <option value="games_howell">Games–Howell (неравные дисперсии)</option>
                          <option value="tukey">Tukey HSD</option>
                        </select>
                      </div>
                    )}

                    {isPostHocRelevant && (
                      <div className="space-y-2">
                        <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Поправка пост‑хок</label>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.post_hoc_correction}
                          onChange={(e) => setVariables(v => ({ ...v, post_hoc_correction: e.target.value }))}
                        >
                          <option value="none">Без поправки</option>
                          <option value="bh">FDR (BH)</option>
                          <option value="bky">FDR (BKY)</option>
                          <option value="by">FDR (BY)</option>
                          <option value="bonferroni">Bonferroni</option>
                          <option value="holm">Holm</option>
                          <option value="holm-sidak">Holm–Šidák</option>
                          <option value="sidak">Šidák</option>
                        </select>
                        <div className="text-xs text-[color:var(--text-secondary)] leading-snug">
                          Поправка применяется внутри одного показателя между парами групп (post‑hoc).
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--white)] mb-8">
                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Процесс анализа</div>
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                  Разделите этапы: подготовка данных отдельно, генерация гипотез отдельно, строгий confirmatory запуск отдельно.
                </div>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Контур</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={analysisProcess}
                      onChange={(e) => setAnalysisProcess(String(e.target.value || 'discovery'))}
                    >
                      <option value="data_prep">Data Prep (только очистка и подготовка)</option>
                      <option value="discovery">Discovery (гипотезы, широкое покрытие)</option>
                      <option value="confirmatory">Confirmatory (строгий, воспроизводимый)</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <div className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Текущий режим v2</div>
                    <div className="text-xs font-mono text-[color:var(--text-secondary)]">
                      analysis_mode={resolvedAnalysisMode}
                    </div>
                    {analysisProcess === 'data_prep' && (
                      <Button
                        variant="ghost"
                        onClick={() => selectedDataset?.id ? navigate(`/prepare/${encodeURIComponent(String(selectedDataset.id))}`) : null}
                        className="px-4"
                        disabled={!selectedDataset?.id}
                      >
                        Открыть Data Prep →
                      </Button>
                    )}
                  </div>
                </div>
                {analysisProcess !== 'data_prep' && (
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Deep mining</div>
                      <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                        <input
                          type="checkbox"
                          checked={allowDeepMining}
                          onChange={(e) => setAllowDeepMining(Boolean(e.target.checked))}
                          aria-label="Расширить охват (allow_data_mining)"
                          className="accent-[color:var(--accent)]"
                        />
                        Расширить охват (allow_data_mining)
                      </label>
                      <div className="text-xs text-[color:var(--text-secondary)]">
                        Добавляет exploratory-ветки и добор гипотез/подгрупп в plan.
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label
                        htmlFor="external-validation-dataset-select"
                        className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide"
                      >
                        External validation dataset (опционально)
                      </label>
                      <select
                        id="external-validation-dataset-select"
                        aria-label="External validation dataset (опционально)"
                        className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                        value={externalValidationDatasetId}
                        onChange={(e) => setExternalValidationDatasetId(String(e.target.value || ''))}
                      >
                        <option value="">-- Не использовать --</option>
                        {externalValidationCandidates.map((ds) => (
                          <option key={`external_ds_${String(ds.id)}`} value={String(ds.id)}>
                            {String(ds.filename || ds.id)} ({String(ds.id).slice(0, 8)}...)
                          </option>
                        ))}
                      </select>
                      <div className="text-xs text-[color:var(--text-secondary)]">
                        Передается в planner как `external_validation_dataset_id`.
                      </div>
                    </div>
                  </div>
                )}
                <div className="mt-3 text-xs text-[color:var(--text-secondary)] leading-snug">
                  {analysisProcess === 'confirmatory'
                    ? 'Confirmatory: Design Review + fixed cohort + cleaning artifact обязательны.'
                    : (analysisProcess === 'discovery'
                      ? 'Discovery: допускается exploratory запуск с широким покрытием и мягкими gate.'
                      : 'Data Prep: протокол не запускается, только подготовка первички.' )}
                </div>
              </div>

              {analysisProcess === 'confirmatory' && (
              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--white)] mb-8">
                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Fixed cohort (N)</div>
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                  Делает сравнение моделей воспроизводимым: фиксирует когорту и не даёт анализу «плавать» из‑за пропусков.
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Режим</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={analysisSetMode}
                      onChange={(e) => setAnalysisSetMode(e.target.value)}
                    >
                      <option value="complete_case">Complete‑case (строго, но N уменьшается)</option>
                      <option value="simple_impute">Simple impute (предикторы median/mode)</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Применение</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={analysisSetEnforce}
                      onChange={(e) => setAnalysisSetEnforce(e.target.value)}
                    >
                      <option value="models">Только модели (linear/logistic)</option>
                      <option value="all">Весь протокол</option>
                    </select>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-4 flex-wrap">
                  <Button
                    variant="ghost"
                    onClick={() => void handleFreezeAnalysisSet()}
                    className="px-4"
                    disabled={!selectedDataset?.id || analysisSetSaving}
                  >
                    {analysisSetSaving ? 'Замораживаю…' : 'Заморозить по текущему протоколу'}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => void handleClearAnalysisSet()}
                    className="px-4"
                    disabled={!selectedDataset?.id || analysisSetSaving || !analysisSet?.artifact_exists}
                  >
                    Сбросить
                  </Button>

                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={analysisSetStrict}
                      onChange={(e) => setAnalysisSetStrict(Boolean(e.target.checked))}
                      className="accent-[color:var(--accent)]"
                    />
                    Strict
                  </label>

                  <label className={`inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest ${analysisSet?.artifact_exists ? 'text-[color:var(--text-secondary)]' : 'text-[color:var(--text-secondary)] opacity-60'}`}>
                    <input
                      type="checkbox"
                      checked={analysisSetUse}
                      onChange={(e) => setAnalysisSetUse(Boolean(e.target.checked))}
                      disabled={!analysisSet?.artifact_exists}
                      className="accent-[color:var(--accent)]"
                    />
                    Использовать fixed cohort
                  </label>

                  {analysisSetLoading && (
                    <span className="text-xs text-[color:var(--text-secondary)]">Загружаю…</span>
                  )}
                  {!analysisSetLoading && analysisSet?.artifact_exists && (
                    <span className="text-xs font-mono text-[color:var(--text-secondary)]">
                      id={analysisSet.analysis_set_id || 'unknown'}; N={analysisSet.n_selected ?? '?'} / {analysisSet.n_total ?? '?'}; mode={analysisSet.mode || '?'}
                    </span>
                  )}
                </div>

                {analysisSetError && (
                  <div className="mt-3 text-sm text-red-700">
                    {analysisSetError}
                  </div>
                )}

                {!analysisSet?.artifact_exists && (
                  <div className="mt-3 text-xs text-[color:var(--text-secondary)] leading-snug">
                    Совет: сначала нажмите «Заморозить по текущему протоколу», затем включите «Использовать fixed cohort» и запускайте протокол.
                  </div>
                )}
              </div>
              )}

              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--white)] mb-8">
                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Design Review</div>
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                  Перед запуском протокола проверьте роли переменных и исходы на отдельном экране дизайна.
                </div>
                {studyDesignDraft && (
                  <>
                    <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                      <label className="block text-xs text-[color:var(--text-secondary)]">
                        <span className="font-black uppercase tracking-wide text-[color:var(--text-primary)]">Design type</span>
                        <select
                          className="mt-1 w-full border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          value={String(studyDesignDraft.design_type || 'cross_sectional')}
                          onChange={(e) => patchStudyDesignDraft({ design_type: e.target.value })}
                          disabled={studyDesignSaving}
                        >
                          <option value="cross_sectional">cross_sectional</option>
                          <option value="repeated_measures_long">repeated_measures_long</option>
                          <option value="repeated_measures_wide">repeated_measures_wide</option>
                        </select>
                      </label>
                      <label className="block text-xs text-[color:var(--text-secondary)]">
                        <span className="font-black uppercase tracking-wide text-[color:var(--text-primary)]">Group</span>
                        <select
                          className="mt-1 w-full border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          value={String(studyDesignDraft.group_column || '')}
                          onChange={(e) => patchStudyDesignDraft({ group_column: e.target.value })}
                          disabled={studyDesignSaving}
                        >
                          <option value="">—</option>
                          {columnNames.map((name) => (
                            <option key={`sd_group_${name}`} value={name}>{name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-xs text-[color:var(--text-secondary)]">
                        <span className="font-black uppercase tracking-wide text-[color:var(--text-primary)]">Time</span>
                        <select
                          className="mt-1 w-full border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          value={String(studyDesignDraft.time_column || '')}
                          onChange={(e) => patchStudyDesignDraft({ time_column: e.target.value })}
                          disabled={studyDesignSaving}
                        >
                          <option value="">—</option>
                          {columnNames.map((name) => (
                            <option key={`sd_time_${name}`} value={name}>{name}</option>
                          ))}
                        </select>
                      </label>
                      <label className="block text-xs text-[color:var(--text-secondary)]">
                        <span className="font-black uppercase tracking-wide text-[color:var(--text-primary)]">Subject</span>
                        <select
                          className="mt-1 w-full border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          value={String(studyDesignDraft.subject_column || '')}
                          onChange={(e) => patchStudyDesignDraft({ subject_column: e.target.value })}
                          disabled={studyDesignSaving}
                        >
                          <option value="">—</option>
                          {columnNames.map((name) => (
                            <option key={`sd_subject_${name}`} value={name}>{name}</option>
                          ))}
                        </select>
                      </label>
                    </div>

                    <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
                      <label className="block text-xs text-[color:var(--text-secondary)]">
                        <span className="font-black uppercase tracking-wide text-[color:var(--text-primary)]">Numeric outcomes</span>
                        <input
                          type="text"
                          value={numericOutcomeFilter}
                          onChange={(e) => setNumericOutcomeFilter(e.target.value)}
                          className="mt-1 w-full border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          placeholder="Фильтр колонок…"
                          aria-label="Numeric outcomes filter"
                          disabled={studyDesignSaving}
                        />
                        <select
                          multiple
                          value={Array.isArray(studyDesignDraft.outcomes) ? studyDesignDraft.outcomes : []}
                          onChange={(e) => {
                            const selected = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                            patchStudyDesignDraft({ outcomes: dedupeNames(selected) });
                          }}
                          className="mt-1 w-full min-h-[118px] border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          aria-label="Numeric outcomes"
                          disabled={studyDesignSaving}
                        >
                          {filteredNumericOutcomeOptions.map((name) => (
                            <option key={`sd_outcome_${name}`} value={name}>{name}</option>
                          ))}
                        </select>
                        <div className="mt-1 text-[11px] text-[color:var(--text-secondary)]">
                          Доступно {filteredNumericOutcomeOptions.length} / {designOutcomeOptions.length} колонок.
                        </div>
                      </label>
                      <label className="block text-xs text-[color:var(--text-secondary)]">
                        <span className="font-black uppercase tracking-wide text-[color:var(--text-primary)]">Categorical outcomes</span>
                        <input
                          type="text"
                          value={categoricalOutcomeFilter}
                          onChange={(e) => setCategoricalOutcomeFilter(e.target.value)}
                          className="mt-1 w-full border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          placeholder="Фильтр колонок…"
                          aria-label="Categorical outcomes filter"
                          disabled={studyDesignSaving}
                        />
                        <select
                          multiple
                          value={Array.isArray(studyDesignDraft.categorical_outcomes) ? studyDesignDraft.categorical_outcomes : []}
                          onChange={(e) => {
                            const selected = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                            patchStudyDesignDraft({ categorical_outcomes: dedupeNames(selected) });
                          }}
                          className="mt-1 w-full min-h-[118px] border border-[color:var(--border-color)] rounded-[2px] px-2 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none"
                          aria-label="Categorical outcomes"
                          disabled={studyDesignSaving}
                        >
                          {filteredCategoricalOutcomeOptions.map((name) => (
                            <option key={`sd_cat_outcome_${name}`} value={name}>{name}</option>
                          ))}
                        </select>
                        <div className="mt-1 text-[11px] text-[color:var(--text-secondary)]">
                          Доступно {filteredCategoricalOutcomeOptions.length} / {designOutcomeOptions.length} колонок.
                        </div>
                      </label>
                    </div>

                    <div className="mt-3 flex items-center gap-3 flex-wrap">
                      <Button
                        variant="ghost"
                        onClick={() => patchStudyDesignDraft({
                          group_column: String(variables.group || '').trim(),
                          time_column: String(variables.timepoint || '').trim(),
                          subject_column: String(variables.subject_col || '').trim(),
                          outcomes: dedupeNames([
                            ...(Array.isArray(variables.outcome_cols) ? variables.outcome_cols : []),
                            String(variables.target || '').trim(),
                          ]),
                        })}
                        className="px-4"
                        disabled={studyDesignSaving}
                      >
                        Подставить текущие переменные
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => void handleSaveStudyDesign()}
                        className="px-4"
                        disabled={studyDesignSaving || !selectedDataset?.id}
                      >
                        {studyDesignSaving ? 'Сохраняю дизайн…' : 'Сохранить дизайн в backend'}
                      </Button>
                      <span className="text-xs font-mono text-[color:var(--text-secondary)]">
                        revision={studyDesignRevision ?? 'n/a'}
                      </span>
                    </div>
                  </>
                )}
                <div className="mt-4 flex items-center gap-4 flex-wrap">
                  <Button
                    variant="ghost"
                    onClick={() => selectedDataset?.id ? navigate(`/design/${encodeURIComponent(String(selectedDataset.id))}`) : null}
                    className="px-4"
                    disabled={!selectedDataset?.id}
                  >
                    Открыть Design Review
                  </Button>
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={designReviewConfirmed}
                      onChange={(e) => {
                        const checked = Boolean(e.target.checked);
                        void handleToggleDesignReview(checked);
                      }}
                      disabled={!selectedDataset?.id || designReviewSaving}
                      className="accent-[color:var(--accent)]"
                    />
                    {designReviewSaving ? 'Сохранение…' : 'Дизайн подтвержден'}
                  </label>
                  {designReviewConfirmed && (
                    <span className="text-xs font-mono text-[color:var(--text-secondary)]">
                      {designReviewTimestamp ? `confirmed: ${designReviewTimestamp}` : 'confirmed'}
                    </span>
                  )}
                </div>
                {studyDesignError && (
                  <div className="mt-2 text-xs text-red-700">
                    {studyDesignError}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between pt-6 border-t border-[color:var(--border-color)]">
                <button onClick={() => setShowApplyForm(false)} className="text-[color:var(--text-secondary)] font-bold hover:text-[color:var(--text-primary)] transition-colors">Отмена</button>
                <div className="flex gap-4">
                  <button
                    onClick={handleRunApproved}
                    disabled={runDisabled}
                    className="bg-[color:var(--accent)] text-[color:var(--white)] px-10 py-4 rounded-[2px] font-black text-lg hover:bg-[color:var(--accent-hover)] disabled:opacity-30 transition-colors"
                  >
                    {loading ? 'Выполняю…' : (analysisProcess === 'data_prep' ? 'Открыть Data Prep' : 'Запустить протокол')}
                  </button>
                </div>
              </div>

              <div className="mt-6 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-4 text-sm text-[color:var(--text-secondary)]">
                {analysisProcess === 'data_prep'
                  ? 'Data Prep выполняется в отдельном изолированном контуре (/prepare/:id) и не запускает статистический execute.'
                  : 'После запуска вы автоматически переходите к run-результатам в отдельный экран. Этот шаг использует только canonical v2 workflow.'}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function OptionCard({ icon, title, desc, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-left p-6 border rounded-[2px] transition-colors relative overflow-hidden group ${disabled
        ? 'opacity-40 border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] cursor-not-allowed'
        : 'border-[color:var(--border-color)] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)]'
        }`}
    >
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-[2px] border border-[color:var(--border-color)] flex items-center justify-center text-2xl transition-colors ${disabled ? 'bg-[color:var(--bg-secondary)]' : 'bg-[color:var(--bg-secondary)] group-hover:border-[color:var(--accent)]'}`}>
          {icon}
        </div>
        <div className="flex-1">
          <h3 className={`font-black text-lg ${disabled ? 'text-[color:var(--text-secondary)]' : 'text-[color:var(--text-primary)]'}`}>
            {title}
          </h3>
          <p className="text-sm text-[color:var(--text-secondary)] leading-tight mt-1">
            {desc}
          </p>
        </div>
      </div>
    </button>
  );
}
