import { useState, useEffect, lazy, Suspense, useMemo, useRef, useCallback } from 'react';
import { getWizardRecommendation, applyStrategy, listDatasets, getDataset, exportReport, exportDocx, getAlphaSetting, aiAnalyzeDesign, executeProtocolV2, cleanColumn } from '../../lib/api';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../components/ui/Table';
import { StatTooltip } from '../components/education';
import { useLocation, useNavigate } from 'react-router-dom';

const AnalyticsChart = lazy(() => import('../components/AnalyticsChart'));

export default function ProtocolWizard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState(0); // Step 0: Dataset Selection
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [columns, setColumns] = useState([]);

  const reportPrefsKey = 'statproject_report_prefs_v1';
  const readReportPrefs = () => {
    try {
      const raw = localStorage.getItem(reportPrefsKey);
      const parsed = raw ? JSON.parse(raw) : null;
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch {
      return {};
    }
  };
  const initialReportPrefs = readReportPrefs();
  const [reportStyle, setReportStyle] = useState(() => String(initialReportPrefs?.style || 'apa7'));
  const [reportDensity, setReportDensity] = useState(() => String(initialReportPrefs?.density || 'comfortable'));
  const [reportAccent, setReportAccent] = useState(() => String(initialReportPrefs?.accent || ''));

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
  const [analysisResult, setAnalysisResult] = useState(null);
  const [inspector, setInspector] = useState(null);
  const [drilldownResult, setDrilldownResult] = useState(null);
  const [resultsOpen, setResultsOpen] = useState(false);
  const [drilldownSort, setDrilldownSort] = useState('alpha');
  const [resultsSections, setResultsSections] = useState({
    article: true,
    details: true,
    chart: true,
    significant: true,
  });
  const [articleMetrics, setArticleMetrics] = useState({
    n: true,
    mean: true,
    sd: true,
    sem: false,
    median: true,
    iqr: true,
    min: true,
    max: true,
    cv: true,
    ci: true,
  });
  const [articleUi, setArticleUi] = useState({
    showColumns: false,
    showSignificantOnly: false,
    query: '',
  });
  const chartRef = useRef(null);
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
      mode: 'wizard',
      issues: baseIssues,
    };
  }, [chatProtocol, columnNames, hasChatProtocol, recommendation?.method_id, variables]);

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
    selectedDataset?.id ? `statproject_wizard_approval_${String(selectedDataset.id)}` : null
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

  useEffect(() => {
    try {
      const raw = localStorage.getItem(reportPrefsKey);
      const parsed = raw ? JSON.parse(raw) : null;
      const prev = parsed && typeof parsed === 'object' ? parsed : {};
      localStorage.setItem(
        reportPrefsKey,
        JSON.stringify({
          ...prev,
          style: reportStyle,
          density: reportDensity,
          accent: reportAccent,
        })
      );
    } catch {
      return;
    }
  }, [reportAccent, reportDensity, reportStyle]);

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

  const multiplicityLabel = useMemo(() => {
    const corr = String(variables.multiplicity_correction || '').trim().toLowerCase();
    if (!corr || corr === 'fdr_bh') return 'FDR(BH)';
    if (corr === 'fdr_tsbky') return 'FDR(BKY)';
    if (corr === 'fdr_by') return 'FDR(BY)';
    if (corr === 'bonferroni') return 'Bonferroni';
    if (corr === 'holm-sidak') return 'Holm–Šidák';
    if (corr === 'sidak') return 'Šidák';
    if (corr === 'holm') return 'Holm';
    if (corr === 'none') return 'none';
    return corr;
  }, [variables.multiplicity_correction]);

  const postHocCorrectionLabel = useMemo(() => {
    const corr = String(variables.post_hoc_correction || '').trim().toLowerCase();
    if (!corr || corr === 'none') return 'none';
    if (corr === 'bh' || corr === 'fdr_bh') return 'FDR(BH)';
    if (corr === 'bky' || corr === 'fdr_tsbky') return 'FDR(BKY)';
    if (corr === 'by' || corr === 'fdr_by') return 'FDR(BY)';
    if (corr === 'bonferroni') return 'Bonferroni';
    if (corr === 'holm-sidak') return 'Holm–Šidák';
    if (corr === 'sidak') return 'Šidák';
    if (corr === 'holm') return 'Holm';
    return corr;
  }, [variables.post_hoc_correction]);

  const postHocLabel = useMemo(() => {
    const ph = String(variables.post_hoc || '').trim().toLowerCase();
    if (!ph || ph === 'none') return 'none';
    if (ph === 'dunn') return 'Dunn';
    if (ph === 'games_howell') return 'Games–Howell';
    if (ph === 'tukey') return 'Tukey HSD';
    return ph;
  }, [variables.post_hoc]);

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

  const chartFallback = useMemo(() => (
    <div className="animate-pulse" style={{
      height: 400,
      borderRadius: '2px',
      border: '1px solid var(--border-color)',
      background: 'var(--white)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--text-secondary)',
      fontSize: '12px',
      fontWeight: 800,
      letterSpacing: '0.18em',
      textTransform: 'uppercase'
    }}>
      Загружаю график
    </div>
  ), []);

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
      setStep(1);
    } catch (e) {
      alert("Не удалось загрузить колонки: " + e.message);
    } finally {
      setLoading(false);
    }
  }, [resetChatState]);

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (!recommendation) return;
    if (!allowsAllNumeric && variables.all_numeric) {
      setVariables(v => ({ ...v, all_numeric: false }));
    }
  }, [allowsAllNumeric, recommendation, variables.all_numeric]);

  useEffect(() => {
    if (!analysisResult) return;
    setResultsOpen(true);
  }, [analysisResult]);

  const loadDatasets = async () => {
    try {
      const list = await listDatasets();
      setDatasets(list);
    } catch (e) {
      console.error(e);
    }
  };

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
    setShowApplyForm(false);
    setAnalysisResult(null);
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
    setShowApplyForm(true);
    setVariables(nextVariables);
  }, [aiPickGroupColumn, selectedDataset?.id, variables]);

  const handleSubmit = async (finalSelections) => {
    setLoading(true);
    try {
      const res = await getWizardRecommendation(finalSelections);
      setRecommendation(res);
      setApproved(false);
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
      const res = await aiAnalyzeDesign(selectedDataset.id, text, {
        protocol: Array.isArray(chatDesign?.protocol) ? chatDesign.protocol : null,
        preferences: {
          source: 'wizard',
        },
      });
      setChatDesign(res);
      setChatNotes(Array.isArray(res?.notes) ? res.notes : []);
      setApproved(false);
    } catch (e) {
      setChatError(e?.message || 'Не удалось разобрать дизайн исследования');
    } finally {
      setChatBusy(false);
    }
  }, [chatDesign?.protocol, chatText, selectedDataset?.id]);

  const handleRunApproved = async () => {
    if (!ensureApproved()) return;
    if (!selectedDataset?.id) return;

    if (hasChatProtocol) {
      setLoading(true);
      try {
        const res = await executeProtocolV2(selectedDataset.id, chatProtocol, variables.alpha);
        const runId = res?.run_id;
        if (!runId) throw new Error('Не удалось получить run_id');
        navigate(`/results/${encodeURIComponent(String(selectedDataset.id))}?run=${encodeURIComponent(String(runId))}`, { state: { origin: 'ai' } });
      } catch (e) {
        alert(`Ошибка анализа: ${e?.message || 'Не удалось запустить протокол'}`);
      } finally {
        setLoading(false);
      }
      return;
    }

    await handleApply();
  };

  const handleApply = async () => {
    if (!ensureApproved()) return;
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
      const test_config = {
        multiplicity_correction: variables.multiplicity_correction,
        post_hoc: variables.post_hoc,
        post_hoc_correction: variables.post_hoc_correction,
        auto_fallback: variables.auto_fallback,
      };
      const res = await applyStrategy({
        recommendation: recommendation,
        variables: variables,
        test_config,
        dataset_id: selectedDataset.id,
        alpha: variables.alpha
      });
      setAnalysisResult(res.results);
      setInspector(null);
      setDrilldownResult(null);
      setResultsOpen(true);
    } catch (e) {
      console.error(e);
      alert("Ошибка анализа: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const formatP = (p) => {
    if (typeof p !== 'number' || !Number.isFinite(p)) return '—';
    return p < 0.001 ? '< 0.001' : p.toFixed(4);
  };

  const pClass = (p) => {
    if (typeof p !== 'number' || !Number.isFinite(p)) return 'text-[color:var(--text-secondary)]';
    if (p < 0.05) return 'text-[color:var(--success)]';
    if (p < 0.1) return 'text-amber-700';
    return 'text-[color:var(--text-primary)]';
  };

  const formatNum = (n, digits = 2) => {
    if (typeof n !== 'number' || !Number.isFinite(n)) return '—';
    return n.toFixed(digits);
  };

  const formatGroupCell = (s) => {
    if (!s || typeof s !== 'object') return '—';
    const parts = [];
    if (articleMetrics.n) parts.push(`n=${typeof s.count === 'number' ? String(s.count) : '—'}`);

    if (articleMetrics.mean) {
      if (articleMetrics.sd) parts.push(`M±SD ${formatNum(s.mean, 2)}±${formatNum(s.sd, 2)}`);
      else parts.push(`M ${formatNum(s.mean, 2)}`);
    } else if (articleMetrics.sd) {
      parts.push(`SD ${formatNum(s.sd, 2)}`);
    }

    if (articleMetrics.sem) parts.push(`SEM ${formatNum(s.sem, 2)}`);

    if (articleMetrics.median) {
      if (articleMetrics.iqr) parts.push(`Me[IQR] ${formatNum(s.median, 2)}[${formatNum(s.q1, 2)};${formatNum(s.q3, 2)}]`);
      else parts.push(`Me ${formatNum(s.median, 2)}`);
    } else if (articleMetrics.iqr) {
      parts.push(`IQR ${formatNum(s.q1, 2)}–${formatNum(s.q3, 2)}`);
    }

    if (articleMetrics.min && articleMetrics.max) parts.push(`min–max ${formatNum(s.min, 2)}–${formatNum(s.max, 2)}`);
    else if (articleMetrics.min) parts.push(`min ${formatNum(s.min, 2)}`);
    else if (articleMetrics.max) parts.push(`max ${formatNum(s.max, 2)}`);

    if (articleMetrics.cv) {
      const mean = typeof s.mean === 'number' && Number.isFinite(s.mean) ? s.mean : null;
      const sd = typeof s.sd === 'number' && Number.isFinite(s.sd) ? s.sd : null;
      if (mean !== null && sd !== null && mean !== 0) {
        parts.push(`CV ${formatNum(Math.abs(sd / mean) * 100, 1)}%`);
      }
    }

    if (articleMetrics.ci) {
      const lo = typeof s.ci_lower === 'number' && Number.isFinite(s.ci_lower) ? s.ci_lower : null;
      const hi = typeof s.ci_upper === 'number' && Number.isFinite(s.ci_upper) ? s.ci_upper : null;
      if (lo !== null && hi !== null) parts.push(`CI95 ${formatNum(lo, 2)}–${formatNum(hi, 2)}`);
    }

    return parts.length ? parts.join(' · ') : '—';
  };

  const getGroupStatsRows = (plotStats) => {
    if (!plotStats || typeof plotStats !== 'object') return [];
    return Object.entries(plotStats)
      .filter(([k]) => k !== 'overall')
      .map(([groupName, s]) => ({ groupName, s }))
      .sort((a, b) => String(a.groupName).localeCompare(String(b.groupName)));
  };

  const getPostHocRows = (postHoc) => {
    if (!Array.isArray(postHoc)) return [];
    const keyP = (r) => {
      const p = typeof r?.p_value_adj === 'number' ? r.p_value_adj : r?.p_value;
      return typeof p === 'number' && Number.isFinite(p) ? p : 1;
    };
    return postHoc
      .slice()
      .sort((a, b) => keyP(a) - keyP(b));
  };

  const flatBatchItems = useMemo(() => {
    if (!analysisResult) return [];
    if (analysisResult?.type === 'batch_analysis' && Array.isArray(analysisResult?.items)) {
      return analysisResult.items.map((item) => ({ slice: null, item }));
    }
    if (analysisResult?.type === 'timepoint_batch_analysis' && analysisResult?.slices) {
      return Object.entries(analysisResult.slices)
        .sort(([a], [b]) => String(a).localeCompare(String(b)))
        .flatMap(([slice, sliceRes]) => {
          const items = Array.isArray(sliceRes?.items) ? sliceRes.items : [];
          return items.map((item) => ({ slice, item }));
        });
    }
    return [];
  }, [analysisResult]);

  const batchSummary = useMemo(() => {
    if (!flatBatchItems.length) return null;
    const alpha = Number(variables.alpha);
    const threshold = Number.isFinite(alpha) ? alpha : 0.05;
    const rows = flatBatchItems
      .map(({ slice, item }) => {
        const pAdj = item?.p_value_adj;
        const pRaw = item?.p_value;
        const pUsed = (typeof pAdj === 'number' && Number.isFinite(pAdj)) ? pAdj : pRaw;
        const isSig = typeof pUsed === 'number' && Number.isFinite(pUsed) ? pUsed < threshold : false;
        return { slice, target: item?.target, pUsed, pRaw, pAdj, isSig, item };
      })
      .filter((r) => r.target);

    const sig = rows.filter((r) => r.isSig);
    return {
      total: rows.length,
      significant: sig.length,
      significantTargets: Array.from(new Set(sig.map((r) => String(r.target)))),
    };
  }, [flatBatchItems, variables.alpha]);

  const batchGroupNames = useMemo(() => {
    const first = flatBatchItems[0]?.item;
    const stats = first?.plot_stats;
    if (!stats || typeof stats !== 'object') return [];
    return Object.keys(stats)
      .filter((k) => k && k !== 'overall')
      .sort((a, b) => String(a).localeCompare(String(b)));
  }, [flatBatchItems]);

  const articleRows = useMemo(() => {
    if (!flatBatchItems.length) return [];

    const alpha = Number(variables.alpha);
    const threshold = Number.isFinite(alpha) ? alpha : 0.05;
    const query = String(articleUi.query || '').trim().toLowerCase();
    const significantOnly = Boolean(articleUi.showSignificantOnly);

    return flatBatchItems
      .map(({ slice, item }) => {
        const pAdj = item?.p_value_adj;
        const pRaw = item?.p_value;
        const pUsed = (typeof pAdj === 'number' && Number.isFinite(pAdj)) ? pAdj : pRaw;
        const isSig = typeof pUsed === 'number' && Number.isFinite(pUsed) ? pUsed < threshold : false;
        return {
          slice,
          target: item?.target,
          pRaw,
          pAdj,
          pUsed,
          isSig,
          item,
        };
      })
      .filter((r) => r.target)
      .filter((r) => (query ? String(r.target).toLowerCase().includes(query) : true))
      .filter((r) => (significantOnly ? r.isSig : true))
      .sort((a, b) => {
        const ap = (typeof a.pUsed === 'number' && Number.isFinite(a.pUsed)) ? a.pUsed : 1;
        const bp = (typeof b.pUsed === 'number' && Number.isFinite(b.pUsed)) ? b.pUsed : 1;
        if (ap !== bp) return ap - bp;
        return String(a.target).localeCompare(String(b.target));
      });
  }, [articleUi.query, articleUi.showSignificantOnly, flatBatchItems, variables.alpha]);

  const articleHasSlice = useMemo(() => {
    return articleRows.some((r) => r.slice !== null && r.slice !== undefined);
  }, [articleRows]);

  const topSignificantRows = useMemo(() => {
    const sig = articleRows.filter((r) => r.isSig).slice();
    const hasSlice = sig.some((r) => r.slice !== null && r.slice !== undefined);

    const normalizeSlice = (v) => (v === null || v === undefined) ? '' : String(v);
    const normalizeTarget = (v) => String(v ?? '');

    const sorted = sig.sort((a, b) => {
      if (drilldownSort === 'alpha') {
        if (hasSlice) {
          const as = normalizeSlice(a.slice);
          const bs = normalizeSlice(b.slice);
          if (as !== bs) return as.localeCompare(bs);
        }
        return normalizeTarget(a.target).localeCompare(normalizeTarget(b.target));
      }

      if (drilldownSort === 'slice') {
        const as = normalizeSlice(a.slice);
        const bs = normalizeSlice(b.slice);
        if (as !== bs) return as.localeCompare(bs);
        return normalizeTarget(a.target).localeCompare(normalizeTarget(b.target));
      }

      const ap = (typeof a.pUsed === 'number' && Number.isFinite(a.pUsed)) ? a.pUsed : 1;
      const bp = (typeof b.pUsed === 'number' && Number.isFinite(b.pUsed)) ? b.pUsed : 1;
      if (ap !== bp) return ap - bp;
      return normalizeTarget(a.target).localeCompare(normalizeTarget(b.target));
    });

    return sorted.slice(0, 24);
  }, [articleRows, drilldownSort]);

  const runDrilldown = async ({ target, slice } = {}) => {
    if (!target || !selectedDataset) return;
    setResultsOpen(true);
    setResultsSections((s) => ({ ...s, chart: true }));
    setInspector(null);
    setLoading(true);
    try {
      const recMethodId = needsTimepoint ? 'kruskal' : methodId;
      const vars = {
        ...variables,
        target,
        all_numeric: false,
      };
      if (needsTimepoint && slice) {
        vars.timepoint_value = String(slice);
      } else {
        vars.timepoint_value = '';
      }

      const test_config = {
        multiplicity_correction: vars.multiplicity_correction,
        post_hoc: vars.post_hoc,
        post_hoc_correction: vars.post_hoc_correction,
      };
      const res = await applyStrategy({
        recommendation: {
          method_id: recMethodId,
          name: recommendation?.name || recMethodId,
          description: recommendation?.description || '',
          assumptions: recommendation?.assumptions || [],
        },
        variables: vars,
        test_config,
        dataset_id: selectedDataset.id,
        alpha: variables.alpha
      });

      setDrilldownResult(res.results);
      setTimeout(() => {
        chartRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 75);
    } catch (e) {
      console.error(e);
      alert("Ошибка построения графика: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePredictorToggle = (colName) => {
    setVariables(prev => {
      const current = prev.predictors ? prev.predictors.split(',').filter(x => x) : [];
      const next = current.includes(colName)
        ? current.filter(c => c !== colName)
        : [...current, colName];
      return { ...prev, predictors: next.join(',') };
    });
  };

  const handleDownloadReport = async () => {
    if (!analysisResult || !selectedDataset) return;
    try {
      const format_options = {
        density: reportDensity,
        accent: reportAccent || undefined,
      };
      const blob = await exportReport({
        results: analysisResult,
        variables,
        dataset_id: selectedDataset.id,
        style: reportStyle,
        format_options,
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Clinical_Report_${selectedDataset.id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch {
      alert('Не удалось скачать отчёт');
    }
  };

  const handleDownloadReportDocx = async () => {
    if (!analysisResult || !selectedDataset) return;
    try {
      const format_options = {
        density: reportDensity,
        accent: reportAccent || undefined,
      };
      const blob = await exportDocx({
        dataset_name: selectedDataset.filename || selectedDataset.id,
        filename: `Clinical_Report_${selectedDataset.id}.docx`,
        style: reportStyle,
        format_options,
        results: {
          protocol_name: 'Clinical Report',
          results: {
            analysis: analysisResult
          }
        }
      });

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Clinical_Report_${selectedDataset.id}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Не удалось скачать DOCX-отчёт');
    }
  };

  const reset = () => {
    setStep(0);
    setSelections({
      goal: '', structure: '', data_type: '', groups: '', normal_distribution: true
    });
    setRecommendation(null);
    setShowApplyForm(false);
    resetChatState();
    setAnalysisResult(null);
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
    setInspector(null);
    setDrilldownResult(null);
    setResultsOpen(false);
  };

  const runDisabled = !approved || loading || (!hasChatProtocol && (
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
          🧙‍♂️ Мастер клинического протокола
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
                  onClick={() => navigate(selectedDataset ? `/prep/${selectedDataset.id}` : '/datasets')}
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
                      onClick={() => selectedDataset?.id && navigate(`/prep/${selectedDataset.id}`)}
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
                    onClick={() => selectedDataset?.id && navigate(`/prep/${selectedDataset.id}`)}
                    disabled={!selectedDataset?.id}
                    className="px-4"
                  >
                    Подготовка данных
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleChatSend}
                    disabled={chatBusy || !selectedDataset?.id || !String(chatText || '').trim()}
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

              <div className="flex items-center justify-between pt-6 border-t border-[color:var(--border-color)]">
                <button onClick={() => setShowApplyForm(false)} className="text-[color:var(--text-secondary)] font-bold hover:text-[color:var(--text-primary)] transition-colors">Отмена</button>
                <div className="flex gap-4">
                  <button
                    onClick={handleRunApproved}
                    disabled={runDisabled}
                    className="bg-[color:var(--accent)] text-[color:var(--white)] px-10 py-4 rounded-[2px] font-black text-lg hover:bg-[color:var(--accent-hover)] disabled:opacity-30 transition-colors"
                  >
                    {loading ? 'Выполняю…' : 'Запустить протокол'}
                  </button>
                </div>
              </div>

              {/* Results Display */}
              {analysisResult && (
                <>
                  {!resultsOpen && (
                    <div className="mt-10 flex justify-end">
                      <button
                        type="button"
                        onClick={() => setResultsOpen(true)}
                        className="px-4 py-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                      >
                        Открыть результаты
                      </button>
                    </div>
                  )}

                  {resultsOpen && (
                    <div className="fixed inset-0 z-50 flex items-end md:items-center justify-center p-3 md:p-6">
                      <div
                        className="absolute inset-0 bg-black/50"
                        onClick={() => {
                          setResultsOpen(false);
                          setInspector(null);
                        }}
                      />
                      <div
                        role="dialog"
                        aria-modal="true"
                        className="relative w-full max-w-6xl bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden"
                      >
                        <div className="px-6 py-4 border-b border-[color:var(--border-color)] flex items-center justify-between gap-6">
                          <div>
                            <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Результаты</div>
                            <div className="mt-1 font-black text-[color:var(--text-primary)]">
                              {selectedDataset?.filename ? selectedDataset.filename : selectedDataset?.id}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              setResultsOpen(false);
                              setInspector(null);
                            }}
                            className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                          >
                            Закрыть
                          </button>
                        </div>
                        <div className="max-h-[calc(100vh-8rem)] overflow-y-auto p-6">
                          <div className="space-y-8 animate-in fade-in duration-700">
                  <div className="flex items-center gap-4">
                    <div className="h-px flex-1 bg-[color:var(--border-color)]"></div>
                    <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Результаты</div>
                    <div className="h-px flex-1 bg-[color:var(--border-color)]"></div>
                  </div>

                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setResultsSections((s) => ({ ...s, article: !s.article }))}
                        className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.article ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                      >
                        Статья
                      </button>
                      <button
                        type="button"
                        onClick={() => setResultsSections((s) => ({ ...s, details: !s.details }))}
                        className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.details ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                      >
                        Детали
                      </button>
                      <button
                        type="button"
                        onClick={() => setResultsSections((s) => ({ ...s, chart: !s.chart }))}
                        className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.chart ? 'border-[color:var(--accent)] text-[color:var(--text-primary)] bg-[color:var(--bg-secondary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                      >
                        График
                      </button>
                      <button
                        type="button"
                        onClick={() => setResultsSections((s) => ({ ...s, significant: !s.significant }))}
                        className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${resultsSections.significant ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                      >
                        Значимые
                      </button>
                    </div>
                    <div className="text-xs font-mono text-[color:var(--text-secondary)]">
                      α={Number.isFinite(Number(variables.alpha)) ? Number(variables.alpha).toFixed(3) : '0.050'}
                    </div>
                  </div>

                  {resultsSections.article && flatBatchItems.length > 0 && (
                    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                      <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                        <div className="flex items-start justify-between gap-6 flex-wrap">
                          <div>
                            <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Таблица для статьи</div>
                            <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                              {batchSummary ? `Всего: ${batchSummary.total} · значимые: ${batchSummary.significant}` : 'Сводка недоступна'}
                            </div>
                          </div>
                          <div className="flex items-center gap-3 flex-wrap">
                            <input
                              value={articleUi.query}
                              onChange={(e) => setArticleUi((s) => ({ ...s, query: e.target.value }))}
                              placeholder="Поиск по показателю…"
                              className="w-64 max-w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors text-sm"
                            />
                            <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                              <input
                                type="checkbox"
                                checked={articleUi.showSignificantOnly}
                                onChange={(e) => setArticleUi((s) => ({ ...s, showSignificantOnly: e.target.checked }))}
                                className="accent-[color:var(--accent)]"
                              />
                              Только значимые
                            </label>
                            <button
                              type="button"
                              onClick={() => setArticleUi((s) => ({ ...s, showColumns: !s.showColumns }))}
                              className={`px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${articleUi.showColumns ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)]'}`}
                            >
                              Колонки
                            </button>
                          </div>
                        </div>

                        {articleUi.showColumns && (
                          <div className="mt-5 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)] p-4">
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                              {([
                                ['n', 'n'],
                                ['mean', 'Mean'],
                                ['sd', 'SD'],
                                ['sem', 'SEM'],
                                ['median', 'Median'],
                                ['iqr', 'IQR'],
                                ['min', 'Min'],
                                ['max', 'Max'],
                                ['cv', 'CV'],
                                ['ci', 'CI95'],
                              ]).map(([key, label]) => (
                                <label key={key} className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                                  <input
                                    type="checkbox"
                                    checked={Boolean(articleMetrics[key])}
                                    onChange={(e) => setArticleMetrics((m) => ({ ...m, [key]: e.target.checked }))}
                                    className="accent-[color:var(--accent)]"
                                  />
                                  {label}
                                </label>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {resultsSections.significant && topSignificantRows.length > 0 && (
                        <div className="px-6 py-4 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
                          <div className="flex items-center justify-between gap-4 flex-wrap">
                            <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Быстрый drilldown</div>
                            <div className="flex items-center gap-3">
                              <div className="text-xs font-mono text-[color:var(--text-secondary)]">top {topSignificantRows.length}</div>
                              <div className="flex items-center gap-1">
                                <button
                                  type="button"
                                  onClick={() => setDrilldownSort('alpha')}
                                  className={`h-7 px-2 rounded-[2px] border text-[10px] font-black uppercase tracking-widest transition-colors ${drilldownSort === 'alpha'
                                    ? 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
                                    : 'border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'}`}
                                >
                                  A–Z
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setDrilldownSort('slice')}
                                  className={`h-7 px-2 rounded-[2px] border text-[10px] font-black uppercase tracking-widest transition-colors ${drilldownSort === 'slice'
                                    ? 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
                                    : 'border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'}`}
                                >
                                  По точке
                                </button>
                                <button
                                  type="button"
                                  onClick={() => setDrilldownSort('p')}
                                  className={`h-7 px-2 rounded-[2px] border text-[10px] font-black uppercase tracking-widest transition-colors ${drilldownSort === 'p'
                                    ? 'border-[color:var(--accent)] bg-[color:var(--white)] text-[color:var(--text-primary)]'
                                    : 'border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'}`}
                                >
                                  p
                                </button>
                              </div>
                            </div>
                          </div>
                          <div className="mt-3 overflow-x-auto">
                            <Table className="w-full text-sm">
                              <TableHeader className="text-[color:var(--text-secondary)]">
                                <TableRow className="border-b border-[color:var(--border-color)]">
                                  {articleHasSlice && (
                                    <TableHead className="py-2 pr-4 text-left font-black uppercase tracking-widest text-xs">Точка</TableHead>
                                  )}
                                  <TableHead className="py-2 pr-4 text-left font-black uppercase tracking-widest text-xs">Показатель</TableHead>
                                  <TableHead className="py-2 pr-4 text-left font-black uppercase tracking-widest text-xs">p</TableHead>
                                  <TableHead className="py-2 text-left font-black uppercase tracking-widest text-xs">Действия</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {topSignificantRows.map((r) => (
                                  <TableRow key={`${String(r.slice)}__${String(r.target)}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                    {articleHasSlice && (
                                      <TableCell className="py-2 pr-4 text-[color:var(--text-secondary)]">{r.slice ?? '—'}</TableCell>
                                    )}
                                    <TableCell className="py-2 pr-4 font-bold text-[color:var(--text-primary)]">{r.target}</TableCell>
                                    <TableCell className="py-2 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(r.pUsed)}</TableCell>
                                    <TableCell className="py-2">
                                      <button
                                        type="button"
                                        onClick={() => runDrilldown({ target: r.target, slice: r.slice })}
                                        className="px-3 py-2 rounded-[2px] border border-[color:var(--success)] text-[10px] font-black uppercase tracking-widest text-[color:var(--text-primary)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)] transition-colors"
                                      >
                                        График
                                      </button>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </div>
                        </div>
                      )}

                      <div className="p-6 overflow-x-auto">
                        <Table className="w-full text-sm">
                          <TableHeader className="text-[color:var(--text-secondary)]">
                            <TableRow className="border-b border-[color:var(--border-color)]">
                              {articleHasSlice && (
                                <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Точка</TableHead>
                              )}
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Показатель</TableHead>
                              {batchGroupNames.map((g) => (
                                <TableHead key={String(g)} className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">{g}</TableHead>
                              ))}
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                <StatTooltip term="p_value" level="junior" position="top">
                                  <span>p</span>
                                </StatTooltip>
                              </TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                <StatTooltip term="multiplicity_correction" level="junior" position="top">
                                  <span>p({multiplicityLabel})</span>
                                </StatTooltip>
                              </TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Значимо</TableHead>
                              <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Действия</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {articleRows.map((row) => {
                              const inspectorKey = articleHasSlice
                                ? `${String(row.slice)}__${String(row.target)}`
                                : String(row.target);
                              return (
                                <TableRow key={inspectorKey} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                  {articleHasSlice && (
                                    <TableCell className="py-3 pr-4 text-[color:var(--text-secondary)]">{row.slice ?? '—'}</TableCell>
                                  )}
                                  <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{row.target}</TableCell>
                                  {batchGroupNames.map((g) => (
                                    <TableCell key={`${inspectorKey}__${String(g)}`} className="py-3 pr-4 font-mono text-[color:var(--text-secondary)] whitespace-nowrap">
                                      {formatGroupCell(row.item?.plot_stats?.[g])}
                                    </TableCell>
                                  ))}
                                  <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(row.pRaw)}</TableCell>
                                  <TableCell className={`py-3 pr-4 font-mono font-black ${pClass(row.pUsed)}`}>{formatP(row.pUsed)}</TableCell>
                                  <TableCell className="py-3 pr-4">
                                    <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${row.isSig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                      {row.isSig ? 'ДА' : 'НЕТ'}
                                    </span>
                                  </TableCell>
                                  <TableCell className="py-3">
                                    <div className="flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={() => {
                                          setResultsSections((s) => ({ ...s, details: true }));
                                          setInspector((prev) => (prev?.key === inspectorKey ? null : { key: inspectorKey, target: row.target, slice: row.slice, item: row.item }));
                                        }}
                                        className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                                      >
                                        Детали
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() => runDrilldown({ target: row.target, slice: row.slice })}
                                        className="px-3 py-2 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-xs font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] transition-colors"
                                      >
                                        График
                                      </button>
                                    </div>
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>

                        {!articleRows.length && (
                          <div className="mt-4 text-sm text-[color:var(--text-secondary)]">Нет строк по текущему фильтру.</div>
                        )}
                      </div>
                    </div>
                  )}

                  {analysisResult?.type === 'timepoint_batch_analysis' && analysisResult?.slices ? (
                    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                      <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                        <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Все количественные по таймпоинтам</div>
                        <div className="mt-2 text-sm text-[color:var(--text-secondary)]">Строка = показатель × точка, колонки = p и p(FDR)</div>
                      </div>
                      <div className="p-6">
                        <Table className="w-full text-sm">
                          <TableHeader className="text-[color:var(--text-secondary)]">
                            <TableRow className="border-b border-[color:var(--border-color)]">
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Точка</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Показатель</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p({multiplicityLabel})</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Стат</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Значимо</TableHead>
                              <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Действия</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {Object.entries(analysisResult.slices)
                              .sort(([a], [b]) => String(a).localeCompare(String(b)))
                              .flatMap(([slice, sliceRes]) => {
                                const items = Array.isArray(sliceRes?.items) ? sliceRes.items : [];
                                return items
                                  .slice()
                                  .sort((a, b) => String(a?.target || '').localeCompare(String(b?.target || '')))
                                  .map((r) => {
                                    const p = r?.p_value;
                                    const pAdj = r?.p_value_adj;
                                    const stat = r?.stat_value;
                                    const sig = r?.significant_adj ?? r?.significant;
                                    const inspectorKey = `${slice}__${String(r?.target)}`;
                                    return (
                                      <TableRow key={inspectorKey} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                        <TableCell className="py-3 pr-4 text-[color:var(--text-secondary)]">{slice}</TableCell>
                                        <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{r?.target}</TableCell>
                                        <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(p)}</TableCell>
                                        <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(pAdj)}</TableCell>
                                        <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatNum(stat, 2)}</TableCell>
                                        <TableCell className="py-3">
                                          <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                            {sig ? 'ДА' : 'НЕТ'}
                                          </span>
                                        </TableCell>
                                        <TableCell className="py-3">
                                          <div className="flex items-center gap-2">
                                            <button
                                              type="button"
                                              onClick={() => setInspector(prev => (prev?.key === inspectorKey ? null : { key: inspectorKey, target: r?.target, slice, item: r }))}
                                              className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                                            >
                                              Детали
                                            </button>
                                            <button
                                              type="button"
                                              onClick={() => runDrilldown({ target: r?.target, slice })}
                                              className="px-3 py-2 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-xs font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] transition-colors"
                                            >
                                              График
                                            </button>
                                          </div>
                                        </TableCell>
                                      </TableRow>
                                    );
                                  });
                              })}
                          </TableBody>
                        </Table>

                        {inspector?.item && (
                          <div className="mt-8 border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                            <div className="px-6 py-4 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-6">
                              <div>
                                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Детали</div>
                                <div className="mt-1 font-black text-[color:var(--text-primary)]">
                                  {inspector?.slice ? `${inspector.slice} · ` : ''}{inspector?.target}
                                </div>
                              </div>
                              <button
                                type="button"
                                onClick={() => setInspector(null)}
                                className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                              >
                                Закрыть
                              </button>
                            </div>
                            <div className="p-6 space-y-8 bg-[color:var(--white)]">
                              <div>
                                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Описательная статистика</div>
                                {getGroupStatsRows(inspector.item?.plot_stats).length ? (
                                  <div className="mt-4 overflow-x-auto">
                                    <Table className="w-full text-sm">
                                      <TableHeader className="text-[color:var(--text-secondary)]">
                                        <TableRow className="border-b border-[color:var(--border-color)]">
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Группа</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">n</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Mean ± SD</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Median [IQR]</TableHead>
                                          <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Min–Max</TableHead>
                                        </TableRow>
                                      </TableHeader>
                                      <TableBody>
                                        {getGroupStatsRows(inspector.item?.plot_stats).map(({ groupName, s }) => (
                                          <TableRow key={String(groupName)} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                            <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{groupName}</TableCell>
                                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{typeof s?.count === 'number' ? String(s.count) : '—'}</TableCell>
                                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.mean, 2)} ± ${formatNum(s?.sd, 2)}`}</TableCell>
                                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.median, 2)} [${formatNum(s?.q1, 2)}; ${formatNum(s?.q3, 2)}]`}</TableCell>
                                            <TableCell className="py-3 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.min, 2)}–${formatNum(s?.max, 2)}`}</TableCell>
                                          </TableRow>
                                        ))}
                                      </TableBody>
                                    </Table>
                                  </div>
                                ) : (
                                  <div className="mt-3 text-sm text-[color:var(--text-secondary)]">Нет данных статистики для этого результата.</div>
                                )}
                              </div>

                              <div>
                                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Пост‑хок</div>
                                <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                                  Метод:{' '}
                                  <StatTooltip term={variables.post_hoc === 'dunn' ? 'post_hoc_dunn' : (variables.post_hoc === 'games_howell' ? 'post_hoc_games_howell' : (variables.post_hoc === 'tukey' ? 'post_hoc_tukey' : 'post_hoc'))} level="junior" position="top">
                                    <span className="font-mono font-black text-[color:var(--text-primary)]">{postHocLabel}</span>
                                  </StatTooltip>
                                  {' '}· поправка:{' '}
                                  <StatTooltip term="post_hoc_correction" level="junior" position="top">
                                    <span className="font-mono font-black text-[color:var(--text-primary)]">{postHocCorrectionLabel}</span>
                                  </StatTooltip>
                                </div>
                                {getPostHocRows(inspector.item?.post_hoc).length ? (
                                  <div className="mt-4 overflow-x-auto">
                                    <Table className="w-full text-sm">
                                      <TableHeader className="text-[color:var(--text-secondary)]">
                                        <TableRow className="border-b border-[color:var(--border-color)]">
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">A</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">B</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                            {postHocCorrectionLabel === 'none' ? 'p' : `p(${postHocCorrectionLabel})`}
                                          </TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                            <StatTooltip term="p_value" level="junior" position="top">
                                              <span>p(raw)</span>
                                            </StatTooltip>
                                          </TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                            <StatTooltip term="p_value_adj" level="junior" position="top">
                                              <span>p(adj)</span>
                                            </StatTooltip>
                                          </TableHead>
                                          <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Значимо</TableHead>
                                        </TableRow>
                                      </TableHeader>
                                      <TableBody>
                                        {getPostHocRows(inspector.item?.post_hoc).map((r, idx) => {
                                          const raw = r?.p_value;
                                          const adj = r?.p_value_adj;
                                          const pShown = typeof adj === 'number' ? adj : raw;
                                          const sig = r?.significant_adj ?? r?.significant;
                                          return (
                                            <TableRow key={`${String(r?.group1)}__${String(r?.group2)}__${idx}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                              <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{String(r?.group1 ?? '')}</TableCell>
                                              <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{String(r?.group2 ?? '')}</TableCell>
                                              <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(pShown)}</TableCell>
                                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(raw)}</TableCell>
                                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(adj)}</TableCell>
                                              <TableCell className="py-3">
                                                <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                                  {sig ? 'ДА' : 'НЕТ'}
                                                </span>
                                              </TableCell>
                                            </TableRow>
                                          );
                                        })}
                                      </TableBody>
                                    </Table>
                                  </div>
                                ) : (
                                  <div className="mt-3 text-sm text-[color:var(--text-secondary)]">Пост‑хок не выполнен или не требуется.</div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : analysisResult?.type === 'batch_analysis' && Array.isArray(analysisResult?.items) ? (
                    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                      <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                        <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Все количественные</div>
                        <div className="mt-2 text-sm text-[color:var(--text-secondary)]">Строка = показатель, колонки = p и p(FDR)</div>
                      </div>
                      <div className="p-6">
                        <Table className="w-full text-sm">
                          <TableHeader className="text-[color:var(--text-secondary)]">
                            <TableRow className="border-b border-[color:var(--border-color)]">
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Показатель</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p({multiplicityLabel})</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Стат</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Значимо</TableHead>
                              <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Действия</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {analysisResult.items
                              .slice()
                              .sort((a, b) => String(a?.target || '').localeCompare(String(b?.target || '')))
                              .map((r) => {
                                const p = r?.p_value;
                                const pAdj = r?.p_value_adj;
                                const stat = r?.stat_value;
                                const sig = r?.significant_adj ?? r?.significant;
                                const inspectorKey = String(r?.target);
                                return (
                                  <TableRow key={inspectorKey} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                    <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{r?.target}</TableCell>
                                    <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(p)}</TableCell>
                                    <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(pAdj)}</TableCell>
                                    <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatNum(stat, 2)}</TableCell>
                                    <TableCell className="py-3">
                                      <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                        {sig ? 'ДА' : 'НЕТ'}
                                      </span>
                                    </TableCell>
                                    <TableCell className="py-3">
                                      <div className="flex items-center gap-2">
                                        <button
                                          type="button"
                                          onClick={() => setInspector(prev => (prev?.key === inspectorKey ? null : { key: inspectorKey, target: r?.target, slice: null, item: r }))}
                                          className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                                        >
                                          Детали
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => runDrilldown({ target: r?.target })}
                                          className="px-3 py-2 rounded-[2px] border border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-xs font-black uppercase tracking-widest text-[color:var(--text-primary)] hover:bg-[color:var(--white)] transition-colors"
                                        >
                                          График
                                        </button>
                                      </div>
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                          </TableBody>
                        </Table>

                        {inspector?.item && (
                          <div className="mt-8 border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                            <div className="px-6 py-4 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-6">
                              <div>
                                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Детали</div>
                                <div className="mt-1 font-black text-[color:var(--text-primary)]">{inspector?.target}</div>
                              </div>
                              <button
                                type="button"
                                onClick={() => setInspector(null)}
                                className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] transition-colors"
                              >
                                Закрыть
                              </button>
                            </div>
                            <div className="p-6 space-y-8 bg-[color:var(--white)]">
                              <div>
                                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Описательная статистика</div>
                                {getGroupStatsRows(inspector.item?.plot_stats).length ? (
                                  <div className="mt-4 overflow-x-auto">
                                    <Table className="w-full text-sm">
                                      <TableHeader className="text-[color:var(--text-secondary)]">
                                        <TableRow className="border-b border-[color:var(--border-color)]">
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Группа</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">n</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Mean ± SD</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Median [IQR]</TableHead>
                                          <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Min–Max</TableHead>
                                        </TableRow>
                                      </TableHeader>
                                      <TableBody>
                                        {getGroupStatsRows(inspector.item?.plot_stats).map(({ groupName, s }) => (
                                          <TableRow key={String(groupName)} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                            <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{groupName}</TableCell>
                                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{typeof s?.count === 'number' ? String(s.count) : '—'}</TableCell>
                                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.mean, 2)} ± ${formatNum(s?.sd, 2)}`}</TableCell>
                                            <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.median, 2)} [${formatNum(s?.q1, 2)}; ${formatNum(s?.q3, 2)}]`}</TableCell>
                                            <TableCell className="py-3 font-mono text-[color:var(--text-secondary)]">{`${formatNum(s?.min, 2)}–${formatNum(s?.max, 2)}`}</TableCell>
                                          </TableRow>
                                        ))}
                                      </TableBody>
                                    </Table>
                                  </div>
                                ) : (
                                  <div className="mt-3 text-sm text-[color:var(--text-secondary)]">Нет данных статистики для этого результата.</div>
                                )}
                              </div>

                              <div>
                                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Пост‑хок</div>
                                <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                                  Метод: <span className="font-mono font-black text-[color:var(--text-primary)]">{postHocLabel}</span> · поправка:{' '}
                                  <span className="font-mono font-black text-[color:var(--text-primary)]">{postHocCorrectionLabel}</span>
                                </div>
                                {getPostHocRows(inspector.item?.post_hoc).length ? (
                                  <div className="mt-4 overflow-x-auto">
                                    <Table className="w-full text-sm">
                                      <TableHeader className="text-[color:var(--text-secondary)]">
                                        <TableRow className="border-b border-[color:var(--border-color)]">
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">A</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">B</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">
                                            {postHocCorrectionLabel === 'none' ? 'p' : `p(${postHocCorrectionLabel})`}
                                          </TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p(raw)</TableHead>
                                          <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p(adj)</TableHead>
                                          <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Значимо</TableHead>
                                        </TableRow>
                                      </TableHeader>
                                      <TableBody>
                                        {getPostHocRows(inspector.item?.post_hoc).map((r, idx) => {
                                          const raw = r?.p_value;
                                          const adj = r?.p_value_adj;
                                          const pShown = typeof adj === 'number' ? adj : raw;
                                          const sig = r?.significant_adj ?? r?.significant;
                                          return (
                                            <TableRow key={`${String(r?.group1)}__${String(r?.group2)}__${idx}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                              <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{String(r?.group1 ?? '')}</TableCell>
                                              <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{String(r?.group2 ?? '')}</TableCell>
                                              <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">{formatP(pShown)}</TableCell>
                                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(raw)}</TableCell>
                                              <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">{formatP(adj)}</TableCell>
                                              <TableCell className="py-3">
                                                <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                                  {sig ? 'ДА' : 'НЕТ'}
                                                </span>
                                              </TableCell>
                                            </TableRow>
                                          );
                                        })}
                                      </TableBody>
                                    </Table>
                                  </div>
                                ) : (
                                  <div className="mt-3 text-sm text-[color:var(--text-secondary)]">Пост‑хок не выполнен или не требуется.</div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : analysisResult?.protocol_name && analysisResult?.results ? (
                    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                      <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                        <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">{analysisResult.protocol_name}</div>
                        <div className="mt-2 text-sm text-[color:var(--text-secondary)]">Строка = переменная × точка времени</div>
                      </div>
                      <div className="p-6">
                        <Table className="w-full text-sm">
                          <TableHeader className="text-[color:var(--text-secondary)]">
                            <TableRow className="border-b border-[color:var(--border-color)]">
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Показатель</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Точка</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">p</TableHead>
                              <TableHead className="py-3 pr-4 text-left font-black uppercase tracking-widest text-xs">Стат</TableHead>
                              <TableHead className="py-3 text-left font-black uppercase tracking-widest text-xs">Значимо</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {Object.entries(analysisResult.results)
                              .sort(([a], [b]) => String(a).localeCompare(String(b)))
                              .flatMap(([targetName, res]) => {
                                if (!res || res.type !== 'longitudinal_comparison' || !res.slices) return [];
                                return Object.entries(res.slices)
                                  .sort(([a], [b]) => String(a).localeCompare(String(b)))
                                  .map(([slice, sliceRes]) => {
                                    const p = sliceRes?.p_value;
                                    const stat = sliceRes?.stats ?? sliceRes?.stat_value;
                                    const sig = sliceRes?.significant;
                                    return (
                                      <TableRow key={`${targetName}__${slice}`} className="border-b border-[color:var(--border-color)] last:border-b-0">
                                        <TableCell className="py-3 pr-4 font-bold text-[color:var(--text-primary)]">{targetName}</TableCell>
                                        <TableCell className="py-3 pr-4 text-[color:var(--text-secondary)]">{slice}</TableCell>
                                        <TableCell className="py-3 pr-4 font-mono font-black text-[color:var(--text-primary)]">
                                          {typeof p === 'number' ? (p < 0.001 ? '< 0.001' : p.toFixed(4)) : '—'}
                                        </TableCell>
                                        <TableCell className="py-3 pr-4 font-mono text-[color:var(--text-secondary)]">
                                          {typeof stat === 'number' ? stat.toFixed(2) : '—'}
                                        </TableCell>
                                        <TableCell className="py-3">
                                          <span className={`inline-flex items-center px-2 py-1 rounded-[2px] border text-xs font-black tracking-wide ${sig ? 'border-[color:var(--success)] text-[color:var(--success)]' : 'border-[color:var(--border-color)] text-[color:var(--text-muted)]'}`}>
                                            {sig ? 'ДА' : 'НЕТ'}
                                          </span>
                                        </TableCell>
                                      </TableRow>
                                    );
                                  });
                              })}
                          </TableBody>
                        </Table>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                          <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">p-значение</span>
                          <span className={`text-4xl font-mono font-black ${analysisResult.significant ? 'text-[color:var(--success)]' : 'text-[color:var(--text-primary)]'}`}>
                            {analysisResult.p_value < 0.001 ? '< 0.001' : analysisResult.p_value.toFixed(4)}
                          </span>
                        </div>
                        <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                          <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">статистика</span>
                          <span className="text-4xl font-mono font-black text-[color:var(--text-primary)]">
                            {analysisResult.stat_value.toFixed(2)}
                          </span>
                        </div>
                        <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                          <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">значимость</span>
                          <span className={`text-xl font-bold ${analysisResult.significant ? 'text-[color:var(--success)]' : 'text-[color:var(--text-muted)]'}`}>
                            {analysisResult.significant ? '✓ Значимо' : '✖ Не значимо'}
                          </span>
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                          <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">размер эффекта</span>
                          <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
                            {typeof analysisResult.effect_size === 'number'
                              ? `${analysisResult.effect_size_name || 'effect'} ${analysisResult.effect_size.toFixed(2)}`
                              : '—'
                            }
                          </span>
                          <div className="mt-2 text-xs text-[color:var(--text-secondary)] font-mono">
                            {typeof analysisResult.effect_size_ci_lower === 'number' && typeof analysisResult.effect_size_ci_upper === 'number'
                              ? `CI: [${analysisResult.effect_size_ci_lower.toFixed(2)}, ${analysisResult.effect_size_ci_upper.toFixed(2)}]`
                              : 'CI: —'
                            }
                          </div>
                        </div>
                        <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                          <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">мощность</span>
                          <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
                            {typeof analysisResult.power === 'number' ? analysisResult.power.toFixed(2) : '—'}
                          </span>
                        </div>
                        <div className="bg-[color:var(--white)] p-6 rounded-[2px] border border-[color:var(--border-color)] text-center">
                          <span className="block text-[color:var(--text-secondary)] text-xs font-black mb-1 uppercase tracking-tighter">BF10</span>
                          <span className="text-2xl font-mono font-black text-[color:var(--text-primary)]">
                            {typeof analysisResult.bf10 === 'number' ? analysisResult.bf10.toPrecision(3) : '—'}
                          </span>
                        </div>
                      </div>

                      <div className="bg-[color:var(--white)] p-8 rounded-[2px] border border-[color:var(--border-color)]">
                        <Suspense fallback={chartFallback}>
                          <AnalyticsChart result={analysisResult} />
                        </Suspense>
                      </div>
                    </>
                  )}

                  <div className="flex justify-center mt-4 gap-3 flex-wrap">
                    <Button variant="secondary" onClick={handleDownloadReport} className="px-8">
                      <span>📥</span> Скачать официальный отчёт (PDF)
                    </Button>
                    <Button variant="ghost" onClick={handleDownloadReportDocx} className="px-8">
                      <span>⌁</span> Скачать Word-отчёт (DOCX)
                    </Button>
                  </div>

                  <div className="flex justify-center mt-3 gap-2 flex-wrap items-center">
                    <div className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-muted)]">Оформление</div>
                    <select
                      value={reportStyle}
                      onChange={(e) => setReportStyle(e.target.value)}
                      className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                      aria-label="Стиль отчёта"
                    >
                      <option value="apa7">APA 7</option>
                      <option value="gost">ГОСТ</option>
                      <option value="simple">Простой</option>
                      <option value="editorial">Редакционный</option>
                      <option value="brutal">Брутал</option>
                    </select>
                    <select
                      value={reportDensity}
                      onChange={(e) => setReportDensity(e.target.value)}
                      className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                      aria-label="Плотность отчёта"
                    >
                      <option value="compact">Плотно</option>
                      <option value="comfortable">Комфортно</option>
                      <option value="spacious">Просторно</option>
                    </select>
                    <select
                      value={reportAccent}
                      onChange={(e) => setReportAccent(e.target.value)}
                      className="h-8 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-xs text-[color:var(--text-primary)]"
                      aria-label="Акцент"
                    >
                      <option value="">Акцент: авто</option>
                      <option value="#111111">Акцент: чёрный</option>
                      <option value="#3498db">Акцент: синий</option>
                      <option value="#ff2d55">Акцент: фуксия</option>
                      <option value="#a3ff12">Акцент: лайм</option>
                    </select>
                  </div>

                  {analysisResult.conclusion && (
                    <div className="bg-[color:var(--white)] text-[color:var(--text-primary)] p-10 rounded-[2px] relative border border-[color:var(--accent)] overflow-hidden">
                      <h4 className="font-black text-lg mb-4 flex items-center gap-2">
                        <span className="w-2 h-2 bg-[color:var(--accent)] rounded-[2px]"></span>
                        Клиническая интерпретация (AI)
                      </h4>
                      <p className="text-xl leading-relaxed italic">"{analysisResult.conclusion}"</p>
                    </div>
                  )}

                  <button onClick={reset} className="w-full py-4 text-[color:var(--text-secondary)] hover:text-[color:var(--accent)] font-bold text-sm transition-colors mt-8">
                    Очистить результаты и начать заново
                  </button>

                  {resultsSections.chart && drilldownResult && (
                    <div ref={chartRef} className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                      <div className="px-6 py-5 border-b border-[color:var(--border-color)]">
                        <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">График</div>
                        <div className="mt-2 text-sm text-[color:var(--text-secondary)]">Выбранный показатель для визуальной проверки распределений и различий</div>
                      </div>
                      <div className="p-6">
                        <Suspense fallback={chartFallback}>
                          <AnalyticsChart result={drilldownResult} />
                        </Suspense>
                      </div>
                    </div>
                  )}
                </div>
                          </div>
                        </div>
                      </div>
                  )}
                </>
              )}
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
