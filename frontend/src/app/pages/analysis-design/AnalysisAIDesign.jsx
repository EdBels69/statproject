import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import Button from '../../components/ui/Button';
import {
  getDatasets,
  getDataset,
  getScanReport,
  getVariableMapping,
  analysisPlan,
  executeProtocolV2,
  getAlphaSetting,
  getDatasetDesignReview,
  confirmDatasetDesignReview,
  revokeDatasetDesignReview,
} from '../../../lib/api';
import { useTranslation } from '../../../hooks/useTranslation';
import VariableWorkspace from '../../components/VariableWorkspace';
import ProtocolBuilder from '../../components/analysis/ProtocolBuilder';
import TestConfigModal from '../../components/TestConfigModal';
import AISuggestionsPane from '../../components/analysis/AISuggestionsPane';
import { normalizeDesignReviewStatus, buildDesignReviewGlobals } from './analysisDesignUtils';
import VariablePreview from './VariablePreview';
import MassDynamicsModal from './MassDynamicsModal';
import VibeDesignModal from './VibeDesignModal';

const AnalysisAIDesign = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { id: datasetIdFromRoute } = useParams();

  const [datasets, setDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetsError, setDatasetsError] = useState(null);

  const [datasetName, setDatasetName] = useState(null);
  const [columns, setColumns] = useState([]);
  const [scanReport, setScanReport] = useState(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [datasetError, setDatasetError] = useState(null);

  const [roles, setRoles] = useState({ target: '', group: '', time: '', subject: '', covariates: [] });
  const [outcomeMode, setOutcomeMode] = useState('all_numeric');
  const [selectedOutcomes, setSelectedOutcomes] = useState([]);
  const [outcomesLimit, setOutcomesLimit] = useState(25);
  const [protocol, setProtocol] = useState([]);

  const [outcomesQuery, setOutcomesQuery] = useState('');
  const [expandedOutcomes, setExpandedOutcomes] = useState(() => new Set());

  const [designText, setDesignText] = useState('');
  const [isDrafting, setIsDrafting] = useState(false);
  const [draftError, setDraftError] = useState(null);

  const autoDraftRef = useRef({ key: null });

  const massDraftCancelRef = useRef(false);
  const [isMassDrafting, setIsMassDrafting] = useState(false);
  const [massDraftProgress, setMassDraftProgress] = useState({ total: 0, done: 0, current: '' });
  const [massDraftError, setMassDraftError] = useState(null);

  const [isExecuting, setIsExecuting] = useState(false);
  const [runError, setRunError] = useState(null);
  const [designReviewConfirmed, setDesignReviewConfirmed] = useState(false);
  const [designReviewTimestamp, setDesignReviewTimestamp] = useState(null);
  const [designReviewSaving, setDesignReviewSaving] = useState(false);
  const [designReviewError, setDesignReviewError] = useState(null);

  const [isTestPickerOpen, setIsTestPickerOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState(null);
  const [editingTest, setEditingTest] = useState(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);

  const datasetIdResolved = datasetIdFromRoute || null;

  const syncDesignReviewStatus = useCallback(async (nextDatasetId) => {
    if (!nextDatasetId) {
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
      return;
    }
    try {
      const payload = await getDatasetDesignReview(nextDatasetId);
      const normalized = normalizeDesignReviewStatus(payload);
      setDesignReviewConfirmed(normalized.confirmed);
      setDesignReviewTimestamp(normalized.confirmedAt);
      setDesignReviewError(null);
    } catch {
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
      setDesignReviewError('Не удалось загрузить статус Design Review');
    }
  }, []);

  const handleToggleDesignReview = useCallback(async (checked) => {
    if (!datasetIdResolved || designReviewSaving) return;

    setDesignReviewSaving(true);
    setDesignReviewError(null);
    try {
      if (checked) {
        const payload = await confirmDatasetDesignReview(datasetIdResolved, {
          source: 'analysis_ai',
          actor: 'user',
        });
        const normalized = normalizeDesignReviewStatus(payload);
        setDesignReviewConfirmed(normalized.confirmed);
        setDesignReviewTimestamp(normalized.confirmedAt || new Date().toISOString());
      } else {
        await revokeDatasetDesignReview(datasetIdResolved, {
          source: 'analysis_ai',
          actor: 'user',
          reason: 'manual_uncheck',
        });
        setDesignReviewConfirmed(false);
        setDesignReviewTimestamp(null);
      }
    } catch (e) {
      setDesignReviewError(e?.message || 'Не удалось обновить Design Review');
    } finally {
      setDesignReviewSaving(false);
    }
  }, [datasetIdResolved, designReviewSaving]);

  const basePath = '/ai';
  const pageKicker = 'ИИ';

  const columnNames = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .map((c) => (typeof c === 'string' ? c : c?.name))
      .filter(Boolean)
      .map((n) => String(n));
  }, [columns]);

  const columnStatsByName = useMemo(() => {
    const stats = scanReport?.column_stats;
    return stats && typeof stats === 'object' ? stats : {};
  }, [scanReport]);

  const normalizedColumns = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .map((c) => {
        if (typeof c === 'string') return { name: c, type: '' };
        return { name: String(c?.name || ''), type: String(c?.type || '') };
      })
      .filter((c) => c.name);
  }, [columns]);

  const guessedTime = useMemo(() => {
    const list = Array.isArray(normalizedColumns) ? normalizedColumns : [];
    const dt = list.find((c) => {
      const ty = String(c.type || '').toLowerCase();
      return ty.includes('datetime') || ty.includes('date');
    });
    if (dt?.name) return dt.name;
    const byName = list.find((c) => /(^|[_\-\s])(time|date|visit|week|day)([_\-\s]|$)/i.test(String(c.name || '')) || /(время|дата|визит|недел|день)/i.test(String(c.name || '')));
    return byName?.name || '';
  }, [normalizedColumns]);

  const guessedSubject = useMemo(() => {
    const list = Array.isArray(normalizedColumns) ? normalizedColumns : [];
    const byName = list.find((c) => /(^|[_\-\s])(id|subject|patient|participant|uid)([_\-\s]|$)/i.test(String(c.name || '')) || /(пациент|испытуем|участник|код|номер)/i.test(String(c.name || '')));
    return byName?.name || '';
  }, [normalizedColumns]);

  const numericOutcomes = useMemo(() => {
    const fromColumns = normalizedColumns
      .filter((c) => c.type === 'numeric')
      .map((c) => c.name);

    const fallback = normalizedColumns
      .filter((c) => {
        const meta = columnStatsByName?.[c.name];
        const t1 = String(meta?.type || '').toLowerCase();
        const t2 = String(meta?.data_type || '').toLowerCase();
        return t1 === 'numeric' || t2 === 'numeric';
      })
      .map((c) => c.name);

    const merged = [...fromColumns, ...fallback]
      .map((n) => String(n))
      .filter(Boolean);

    return Array.from(new Set(merged));
  }, [columnStatsByName, normalizedColumns]);

  const selectedOutcomeList = useMemo(() => {
    if (outcomeMode === 'single') {
      return roles?.target ? [roles.target] : [];
    }

    if (outcomeMode === 'selected') {
      return (Array.isArray(selectedOutcomes) ? selectedOutcomes : [])
        .filter(Boolean)
        .slice(0, Math.max(1, Number(outcomesLimit) || 1));
    }

    return (Array.isArray(numericOutcomes) ? numericOutcomes : [])
      .filter(Boolean)
      .slice(0, Math.max(1, Number(outcomesLimit) || 1));
  }, [numericOutcomes, outcomeMode, outcomesLimit, roles?.target, selectedOutcomes]);

  const totalRows = useMemo(() => {
    const n = scanReport?.missing_report?.total_rows;
    return typeof n === 'number' ? n : 0;
  }, [scanReport]);

  useEffect(() => {
    void syncDesignReviewStatus(datasetIdResolved);
  }, [datasetIdResolved, syncDesignReviewStatus]);

  useEffect(() => {
    let cancelled = false;
    const loadDatasets = async () => {
      if (datasetIdFromRoute) return;
      setDatasetsError(null);
      setDatasetsLoading(true);
      try {
        const list = await getDatasets();
        if (cancelled) return;
        setDatasets(Array.isArray(list) ? list : []);
      } catch (e) {
        if (cancelled) return;
        setDatasets([]);
        setDatasetsError(e?.message || String(e));
      } finally {
        if (!cancelled) setDatasetsLoading(false);
      }
    };
    loadDatasets();
    return () => {
      cancelled = true;
    };
  }, [datasetIdFromRoute]);

  useEffect(() => {
    let cancelled = false;

    const loadDataset = async () => {
      setDatasetError(null);
      setScanReport(null);
      setRoles({ target: '', group: '', time: '', subject: '', covariates: [] });
      setOutcomeMode('all_numeric');
      setSelectedOutcomes([]);
      setProtocol([]);
      setRunError(null);
      setDraftError(null);
      setMassDraftError(null);
      setDesignReviewConfirmed(false);
      setDesignReviewTimestamp(null);
      setDesignReviewError(null);
      setIsMassDrafting(false);
      setMassDraftProgress({ total: 0, done: 0, current: '' });
      massDraftCancelRef.current = false;
      autoDraftRef.current.key = null;

      if (!datasetIdResolved) {
        setDatasetName(null);
        setColumns([]);
        return;
      }

      setDatasetLoading(true);
      try {
        const profile = await getDataset(datasetIdResolved);
        if (cancelled) return;
        const fallbackName = profile?.filename || profile?.name;
        setDatasetName(fallbackName || datasetIdResolved);
        setColumns(Array.isArray(profile?.columns) ? profile.columns : []);

        try {
          const report = await getScanReport(datasetIdResolved);
          if (!cancelled) setScanReport(report);
        } catch {
          if (!cancelled) setScanReport(null);
        }

        try {
          const res = await getVariableMapping(datasetIdResolved);
          if (cancelled) return;
          const mapping = res?.mapping && typeof res.mapping === 'object' ? res.mapping : {};
          let nextTarget = '';
          let nextGroup = '';
          let nextTime = '';
          let nextSubject = '';
          const nextCovariates = [];
          Object.entries(mapping).forEach(([name, meta]) => {
            const role = meta?.role;
            const roleL = String(role || '').toLowerCase();
            if (!nextTarget && role === 'Исход') nextTarget = name;
            if (!nextGroup && role === 'Группа') nextGroup = name;
            if (role === 'Ковариата') nextCovariates.push(name);
            if (!nextTime && (roleL.includes('врем') || roleL === 'time' || meta?.time_var === true)) nextTime = name;
            if (!nextSubject && (roleL.includes('суб') || roleL.includes('id') || roleL === 'subject' || meta?.subject_var === true || meta?.id_var === true)) nextSubject = name;
          });
          if (nextTarget || nextGroup || nextTime || nextSubject || nextCovariates.length > 0) {
            setRoles({ target: nextTarget, group: nextGroup, time: nextTime, subject: nextSubject, covariates: nextCovariates });
          }
        } catch (e) {
          void e;
        }
      } catch (e) {
        if (cancelled) return;
        setDatasetError(e?.message || String(e));
      } finally {
        if (!cancelled) setDatasetLoading(false);
      }
    };

    loadDataset();
    return () => {
      cancelled = true;
    };
  }, [datasetIdResolved]);

  useEffect(() => {
    if (!datasetIdResolved) return;
    setRoles((prev) => {
      const p = prev && typeof prev === 'object' ? prev : { target: '', group: '', time: '', subject: '', covariates: [] };
      const next = { ...p };
      if (!next.time && guessedTime) next.time = guessedTime;
      if (!next.subject && guessedSubject) next.subject = guessedSubject;
      return next;
    });
  }, [datasetIdResolved, guessedSubject, guessedTime]);

  const handleTestSelect = useCallback((test) => {
    setSelectedTest(test);
    setEditingTest(null);
    setIsConfigModalOpen(true);
  }, []);

  const handleConfigSave = useCallback((config) => {
    if (editingTest) {
      setProtocol((prev) =>
        (Array.isArray(prev) ? prev : []).map((step) => {
          if (step.id !== editingTest.id) return step;
          return { ...step, config: { ...(step.config || {}), ...(config || {}) } };
        })
      );
    } else {
      const methodId = selectedTest?.id;
      if (!methodId) {
        setIsConfigModalOpen(false);
        setSelectedTest(null);
        setEditingTest(null);
        return;
      }
      const newStep = {
        id: `step_${Date.now()}_${Math.random().toString(16).slice(2)}`,
        method: methodId,
        name: selectedTest?.name || String(methodId),
        config: config && typeof config === 'object' ? config : {},
        enabled: true,
      };
      setProtocol((prev) => [...(Array.isArray(prev) ? prev : []), newStep]);
    }

    setIsConfigModalOpen(false);
    setSelectedTest(null);
    setEditingTest(null);
  }, [editingTest, selectedTest]);

  const handleEditStep = useCallback((step) => {
    if (!step) return;
    setEditingTest(step);
    setSelectedTest({ id: step.method, name: step.name || step.method });
    setIsConfigModalOpen(true);
  }, []);

  const handleToggleStep = useCallback((stepId, enabled) => {
    setProtocol((prev) =>
      (Array.isArray(prev) ? prev : []).map((s) => {
        if (s?.id !== stepId) return s;
        return { ...s, enabled: Boolean(enabled) };
      })
    );
  }, []);

  const requestDraftSteps = useCallback(async ({ seedText, targetOverride } = {}) => {
    if (!datasetIdResolved) return [];

    const resolvedTarget = String(targetOverride ?? roles?.target ?? '').trim();
    if (!resolvedTarget) {
      throw new Error('Выбери хотя бы один исход');
    }

    const baseText = String(seedText ?? designText ?? '').trim();

    const constraints = [
      resolvedTarget ? `Target: ${resolvedTarget}` : '',
      roles?.group ? `Group: ${roles.group}` : '',
      roles?.time ? `Time: ${roles.time}` : '',
      roles?.subject ? `Subject: ${roles.subject}` : '',
      Array.isArray(roles?.covariates) && roles.covariates.length ? `Covariates: ${roles.covariates.join(', ')}` : '',
    ].filter(Boolean).join('\n');

    const text = [baseText, constraints].filter(Boolean).join('\n\n');
    if (text.length < 8) {
      throw new Error('Добавь цель исследования (пара фраз)');
    }

    const data = await analysisPlan(datasetIdResolved, text, {
      protocol: [],
      preferences: {},
    });
    const steps = Array.isArray(data?.protocol) ? data.protocol : [];
    const now = Date.now();
    const slug = resolvedTarget.replace(/[^a-z0-9]+/gi, '_').slice(0, 24) || 'target';

    const mapped = steps
      .map((s, idx) => {
        const method = String(s?.method || '').trim();
        if (!method) return null;
        const baseCfg = (s?.config && typeof s.config === 'object') ? s.config : {};
        const cfg = { ...baseCfg };

        if (cfg.outcome == null && cfg.target == null) {
          cfg.outcome = resolvedTarget;
          cfg.target = resolvedTarget;
        }

        if (cfg.outcome == null && cfg.target != null) cfg.outcome = cfg.target;
        if (cfg.target == null && cfg.outcome != null) cfg.target = cfg.outcome;

        if (roles?.group && cfg.group == null) cfg.group = roles.group;
        if (roles?.time && cfg.time == null) cfg.time = roles.time;
        if (roles?.subject && cfg.subject == null) cfg.subject = roles.subject;
        if (Array.isArray(roles?.covariates) && roles.covariates.length && cfg.covariates == null) {
          cfg.covariates = roles.covariates;
        }

        const name = String(s?.name || '').trim() || method.replace(/_/g, ' ');
        return {
          id: `draft_${slug}_${now}_${idx}`,
          method,
          name,
          config: cfg,
          enabled: true,
          outcome: resolvedTarget,
        };
      })
      .filter(Boolean);

    return mapped;
  }, [datasetIdResolved, designText, roles]);

  const generateDraft = useCallback(async ({ seedText, targetOverride } = {}) => {
    if (!datasetIdResolved) return;

    setIsDrafting(true);
    setDraftError(null);
    setMassDraftError(null);

    try {
      const mapped = await requestDraftSteps({ seedText, targetOverride });
      if (mapped.length === 0) throw new Error('ИИ не вернул шаги протокола');
      setProtocol(mapped);
    } catch (e) {
      setDraftError(e?.message || String(e));
    } finally {
      setIsDrafting(false);
    }
  }, [datasetIdResolved, requestDraftSteps]);

  const generateFullDesign = useCallback(async ({ seedText } = {}) => {
    if (!datasetIdResolved) return;
    const outcomes = Array.isArray(selectedOutcomeList) ? selectedOutcomeList.filter(Boolean) : [];
    if (outcomes.length === 0) {
      setMassDraftError('Нет выбранных показателей');
      return;
    }

    const base = String(seedText ?? designText ?? '').trim();
    const baseSeed = base.length >= 8 ? base : 'Собери полный дизайн исследования и предложи максимально применимые тесты.';

    massDraftCancelRef.current = false;
    setIsMassDrafting(true);
    setMassDraftError(null);
    setDraftError(null);
    setMassDraftProgress({ total: outcomes.length, done: 0, current: '' });

    try {
      const allSteps = [];
      let completed = 0;
      for (let i = 0; i < outcomes.length; i += 1) {
        if (massDraftCancelRef.current) break;
        const outcome = outcomes[i];
        setMassDraftProgress({ total: outcomes.length, done: i, current: String(outcome) });
        const perOutcomeSeed = `${baseSeed}\n\nСобери дизайн для показателя: ${outcome}.`; 
        const steps = await requestDraftSteps({ seedText: perOutcomeSeed, targetOverride: outcome });
        if (Array.isArray(steps) && steps.length) {
          allSteps.push(...steps);
        }
        completed = i + 1;
      }

      setMassDraftProgress({ total: outcomes.length, done: completed, current: '' });

      if (allSteps.length === 0) {
        throw new Error(massDraftCancelRef.current ? 'Остановлено' : 'ИИ не вернул шаги протокола');
      }

      setProtocol(allSteps);
    } catch (e) {
      setMassDraftError(e?.message || String(e));
    } finally {
      setIsMassDrafting(false);
    }
  }, [datasetIdResolved, designText, requestDraftSteps, selectedOutcomeList]);

  useEffect(() => {
    if (!datasetIdResolved) return;
    if (isDrafting || isMassDrafting) return;
    if (Array.isArray(protocol) && protocol.length > 0) return;

    const key = [
      datasetIdResolved,
      outcomeMode,
      roles?.target || '',
      roles?.group || '',
      roles?.time || '',
      roles?.subject || '',
      Array.isArray(roles?.covariates) ? roles.covariates.join(',') : '',
      Array.isArray(selectedOutcomeList) ? selectedOutcomeList.join(',') : '',
      String(designText || '').trim(),
    ].join('|');
    if (autoDraftRef.current.key === key) return;

    const covariatesText = Array.isArray(roles?.covariates) && roles.covariates.length
      ? `Ковариаты: ${roles.covariates.join(', ')}.`
      : '';

    if (outcomeMode === 'single') {
      if (!roles?.target) return;
      autoDraftRef.current.key = key;
      const seedText = [
        'Собери черновик протокола анализа для согласования.',
        roles?.group
          ? `Сравнить ${roles.target} между группами (${roles.group}).`
          : `Проанализировать переменную ${roles.target}.`,
        roles?.time && roles?.subject ? `Есть динамика: время=${roles.time}, субъект=${roles.subject}.` : '',
        covariatesText,
        'Подбери тесты, проверь предпосылки и добавь пост-хок при необходимости.'
      ].filter(Boolean).join(' ');
      void generateDraft({ seedText });
      return;
    }

    if (!Array.isArray(selectedOutcomeList) || selectedOutcomeList.length === 0) return;
    autoDraftRef.current.key = key;
    const seedText = [
      'Собери полный дизайн исследования по всем показателям для согласования.',
      roles?.group ? `Группа: ${roles.group}.` : '',
      roles?.time && roles?.subject ? `Динамика: время=${roles.time}, субъект=${roles.subject}.` : '',
      covariatesText,
      'Предложи максимально применимые тесты. Я буду отключать лишнее.'
    ].filter(Boolean).join(' ');
    void generateFullDesign({ seedText });
  }, [datasetIdResolved, designText, generateDraft, generateFullDesign, isDrafting, isMassDrafting, outcomeMode, protocol, roles, selectedOutcomeList]);

  const handleRun = useCallback(async () => {
    if (!datasetIdResolved) return;
    const enabledSteps = (Array.isArray(protocol) ? protocol : []).filter((s) => s?.enabled !== false);
    if (enabledSteps.length === 0) return;
    if (!designReviewConfirmed) {
      setDesignReviewError('Перед запуском подтвердите Design Review');
      setRunError('Design Review не подтвержден. Подтвердите дизайн перед запуском.');
      return;
    }

    const normalizeStepForBackend = (step) => {
      const rawMethod = step?.method;
      const method = rawMethod === 'mixed_model' ? 'mixed_effects' : rawMethod;
      const c = step?.config && typeof step.config === 'object' ? step.config : {};

      const inferredOutcome = c.outcome || c.target || step?.outcome || '';
      const inferredGroup = c.group || roles?.group || '';
      const inferredTime = c.time || roles?.time || '';
      const inferredSubject = c.subject || roles?.subject || '';
      const inferredCovariates = Array.isArray(c.covariates) ? c.covariates : Array.isArray(roles?.covariates) ? roles.covariates : [];

      if (method === 'clustered_correlation') {
        const variables = Array.isArray(c.variables) ? c.variables : Array.isArray(c.targets) ? c.targets : [];
        return { ...step, method, config: { ...c, variables } };
      }

      if (method === 'mixed_effects') {
        const outcome = inferredOutcome;
        return { ...step, method, config: { ...c, outcome, group: inferredGroup, time: inferredTime, subject: inferredSubject, covariates: inferredCovariates } };
      }

      if (method === 'linear_regression' || method === 'logistic_regression') {
        const outcome = inferredOutcome;
        const predictors = Array.isArray(c.predictors)
          ? c.predictors
          : Array.isArray(c.targets)
            ? c.targets
            : [];
        const covariates = inferredCovariates;
        const group = inferredGroup || predictors?.[0] || '';
        return { ...step, method, config: { ...c, outcome, group, predictors, covariates } };
      }

      if (method === 'pearson' || method === 'spearman') {
        const targets = Array.isArray(c.targets) ? c.targets : [];
        const outcome = inferredOutcome || targets?.[0] || '';
        const group = inferredGroup || targets?.[1] || '';
        return { ...step, method, config: { ...c, outcome, group } };
      }

      const outcome = inferredOutcome;
      const group = inferredGroup;
      return { ...step, method, config: { ...c, outcome, group, covariates: inferredCovariates } };
    };

    setIsExecuting(true);
    setRunError(null);
    setDesignReviewError(null);
    try {
      const payload = enabledSteps.map((s) => {
        const normalized = normalizeStepForBackend(s);
        return {
          id: normalized.id,
          method: normalized.method,
          config: normalized.config && typeof normalized.config === 'object' ? normalized.config : {},
        };
      });
      const globals = buildDesignReviewGlobals({
        source: 'analysis_design_ai',
        confirmed: designReviewConfirmed,
        confirmedAt: designReviewTimestamp,
      });
      const data = await executeProtocolV2(
        datasetIdResolved,
        payload,
        getAlphaSetting(),
        null,
        globals
      );
      const runId = data?.run_id;
      if (runId) {
        navigate(`/report/${datasetIdResolved}?run=${encodeURIComponent(String(runId))}`, {
          state: { ...(location.state || {}), origin: 'ai' },
        });
        return;
      }
      navigate(`/results/${datasetIdResolved}`, {
        state: { ...(location.state || {}), origin: 'ai' },
      });
    } catch (e) {
      setRunError(e?.message || String(e));
    } finally {
      setIsExecuting(false);
    }
  }, [datasetIdResolved, designReviewConfirmed, designReviewTimestamp, location.state, navigate, protocol, roles?.covariates, roles?.group, roles?.subject, roles?.time]);

  const enabledStepsCount = (Array.isArray(protocol) ? protocol : []).filter((s) => s?.enabled !== false).length;

  const filteredNumericOutcomes = useMemo(() => {
    const base = (Array.isArray(numericOutcomes) ? numericOutcomes : []).filter(Boolean);
    const q = String(outcomesQuery || '').trim().toLowerCase();
    const filtered = q ? base.filter((n) => String(n).toLowerCase().includes(q)) : base;
    return filtered.sort((a, b) => String(a).localeCompare(String(b), undefined, { sensitivity: 'base' }));
  }, [numericOutcomes, outcomesQuery]);

  const protocolGroups = useMemo(() => {
    const list = Array.isArray(protocol) ? protocol : [];
    const map = new Map();
    for (const s of list) {
      const k = String(s?.outcome || s?.config?.outcome || s?.config?.target || '—').trim() || '—';
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(s);
    }
    return Array.from(map.entries()).sort((a, b) => String(a[0]).localeCompare(String(b[0]), undefined, { sensitivity: 'base' }));
  }, [protocol]);

  const toggleAllSteps = useCallback((enabled) => {
    setProtocol((prev) => (Array.isArray(prev) ? prev : []).map((s) => ({ ...s, enabled: Boolean(enabled) })));
  }, []);

  const toggleOutcomeSteps = useCallback((outcome, enabled) => {
    const key = String(outcome || '—').trim() || '—';
    setProtocol((prev) =>
      (Array.isArray(prev) ? prev : []).map((s) => {
        const k = String(s?.outcome || s?.config?.outcome || s?.config?.target || '—').trim() || '—';
        if (k !== key) return s;
        return { ...s, enabled: Boolean(enabled) };
      })
    );
  }, []);

  const removeStep = useCallback((stepId) => {
    setProtocol((prev) => (Array.isArray(prev) ? prev.filter((s) => s?.id !== stepId) : []));
  }, []);

  const datasetPicker = (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-10">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{pageKicker}</div>
          <h1 className="mt-3 text-3xl font-black text-[color:var(--text-primary)] leading-tight">Согласование протокола</h1>
          <p className="mt-2 text-sm text-[color:var(--text-secondary)] max-w-2xl">Выбери датасет — затем исход, группы и шаги анализа.</p>
        </div>

        {datasetsError ? (
          <div className="mb-6 p-4 bg-[color:var(--white)] border border-[color:var(--black)] text-[color:var(--text-primary)] rounded-[2px] text-sm">{datasetsError}</div>
        ) : null}

        <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
          <div className="px-6 py-4 border-b border-[color:var(--border-color)] flex items-center justify-between">
            <div className="text-sm font-semibold text-[color:var(--text-primary)]">{t('datasets')}</div>
            <Button onClick={() => navigate('/upload')} variant="primary" size="sm" type="button">
              {t('upload_dataset')}
            </Button>
          </div>

          <div className="p-3">
            {datasetsLoading ? (
              <div className="p-8 text-center text-[color:var(--text-secondary)] text-sm">{t('loading')}</div>
            ) : datasets.length === 0 ? (
              <div className="p-8 text-center text-[color:var(--text-secondary)] text-sm">{t('no_datasets_found')}</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {datasets.map((ds) => (
                  <button
                    key={ds.id}
                    type="button"
                    onClick={() => navigate(`${basePath}/${ds.id}`, { state: { ...(location.state || {}), origin: 'ai' } })}
                    className="text-left p-4 rounded-[2px] border border-[color:var(--border-color)] hover:border-black hover:bg-[color:var(--bg-tertiary)] transition"
                  >
                    <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">{ds.filename || ds.name || ds.id}</div>
                    <div className="mt-1 text-xs text-[color:var(--text-secondary)] font-mono truncate">{ds.id}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (!datasetIdResolved) return datasetPicker;

  if (datasetLoading) {
    return (
      <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6">
        <div className="w-full max-w-3xl animate-pulse">
          <div className="h-7 w-56 bg-[color:var(--gray-200)] rounded-[2px]" />
          <div className="mt-3 h-4 w-80 bg-[color:var(--gray-200)] rounded-[2px]" />
          <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
            <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
            <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
            <div className="h-24 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px]" />
          </div>
          <div className="sr-only" aria-live="polite">{t('loading_dataset')}</div>
        </div>
      </div>
    );
  }

  if (datasetError) {
    return (
      <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6">
        <div className="w-full max-w-xl p-6 bg-[color:var(--white)] border border-[color:var(--black)] rounded-[2px] text-sm text-[color:var(--text-primary)]">
          {datasetError}
          <div className="mt-4">
            <button type="button" onClick={() => navigate(basePath)} className="text-[color:var(--text-primary)] font-semibold underline underline-offset-4">{t('back')}</button>
          </div>
        </div>
      </div>
    );
  }

  const covariateOptions = columnNames.filter((n) => n !== roles.target && n !== roles.group && n !== roles.time && n !== roles.subject);

  return (
    <>
      <div className="-mx-6 -my-6 min-h-[calc(100vh-56px)] bg-[color:var(--bg-secondary)]">
        <div className="bg-[color:var(--white)] border-b border-[color:var(--border-color)] px-6 py-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-4 min-w-0">
                <button
                  onClick={() => navigate(basePath)}
                  className="h-9 w-9 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-black hover:text-black active:scale-[0.98]"
                  type="button"
                  aria-label={t('back')}
                >
                  <ArrowLeftIcon className="w-5 h-5" />
                </button>
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Согласование дизайна</div>
                  <h1 className="mt-1 text-xl font-bold text-[color:var(--text-primary)] truncate">{datasetName || t('dataset')}</h1>
                  <div className="mt-1 text-xs text-[color:var(--text-secondary)] font-mono truncate">n = {totalRows || '—'} • {columnNames.length} колонок</div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  onClick={() => navigate(`/prep/${datasetIdResolved}`, { state: { ...(location.state || {}), origin: 'ai' } })}
                  disabled={!columnNames.length}
                  variant="ghost"
                  className="gap-2"
                  type="button"
                >
                  {t('variables')}
                </Button>
                <Button
                  onClick={() => setIsTestPickerOpen(true)}
                  disabled={!columnNames.length || isExecuting}
                  variant="ghost"
                  type="button"
                >
                  Добавить тест
                </Button>
                <Button
                  onClick={handleRun}
                    disabled={isExecuting || enabledStepsCount === 0}
                  variant="primary"
                  type="button"
                >
                  Выполнить
                </Button>
              </div>
            </div>
            <ResearchFlowNav active="design" datasetId={datasetIdResolved} className="mt-3" showMenu={false} designBasePath="/ai" />

            {datasetIdResolved ? (
              <div className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Design Review</div>
                  <div className={`mt-1 text-sm font-semibold ${designReviewConfirmed ? 'text-[color:var(--success)]' : 'text-[color:var(--accent)]'}`}>
                    {designReviewConfirmed ? 'Подтверждено' : 'Не подтверждено'}
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--text-secondary)]">
                    {designReviewTimestamp ? `Подтверждено: ${designReviewTimestamp}` : 'Перед запуском анализа подтвердите дизайн исследования.'}
                  </div>
                  {designReviewError ? (
                    <div className="mt-1 text-xs text-[color:var(--accent)]">{designReviewError}</div>
                  ) : null}
                </div>
                <div className="flex items-center gap-3">
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={designReviewConfirmed}
                      onChange={(e) => handleToggleDesignReview(e.target.checked)}
                      disabled={designReviewSaving || isExecuting}
                      className="h-4 w-4 accent-black"
                    />
                    Подтверждаю Design Review
                  </label>
                  <button
                    type="button"
                    onClick={() => navigate(`/design/${datasetIdResolved}`)}
                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-black"
                  >
                    Открыть Design Review
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="px-6 py-6">
          <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-[1.05fr_0.95fr] gap-4">
            <section className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
              <div className="px-5 py-4 border-b border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Draft</div>
                <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)]">Переменные</div>
                <div className="mt-1 text-sm text-[color:var(--text-secondary)]">Зафиксируй роли — ИИ и протокол будут держаться только их.</div>
              </div>

              <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-3">
                <label className="grid gap-1">
                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Исход (target)</div>
                  <select
                    value={roles.target}
                    onChange={(e) => setRoles((r) => ({ ...r, target: e.target.value }))}
                    className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                  >
                    <option value="">—</option>
                    {columnNames.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-1">
                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Группа (опц.)</div>
                  <select
                    value={roles.group}
                    onChange={(e) => setRoles((r) => ({ ...r, group: e.target.value }))}
                    className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                  >
                    <option value="">—</option>
                    {columnNames.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-1">
                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Время (опц.)</div>
                  <select
                    value={roles.time}
                    onChange={(e) => setRoles((r) => ({ ...r, time: e.target.value }))}
                    className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                  >
                    <option value="">—</option>
                    {columnNames.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-1">
                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Субъект (ID) (опц.)</div>
                  <select
                    value={roles.subject}
                    onChange={(e) => setRoles((r) => ({ ...r, subject: e.target.value }))}
                    className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                  >
                    <option value="">—</option>
                    {columnNames.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>

                <label className="grid gap-1 md:col-span-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Ковариаты (опц.)</div>
                    {Array.isArray(roles.covariates) && roles.covariates.length ? (
                      <button
                        type="button"
                        onClick={() => setRoles((r) => ({ ...r, covariates: [] }))}
                        className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-black"
                      >
                        Очистить
                      </button>
                    ) : null}
                  </div>
                  <select
                    multiple
                    value={Array.isArray(roles.covariates) ? roles.covariates : []}
                    onChange={(e) => {
                      const opts = Array.from(e.target.selectedOptions).map((o) => o.value);
                      setRoles((r) => ({ ...r, covariates: opts }));
                    }}
                    className="min-h-[140px] px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                  >
                    {covariateOptions.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="px-5 pb-5">
                <div className="mt-2 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Показатели</div>
                      <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">Что покрываем ИИ</div>
                      <div className="mt-1 text-xs text-[color:var(--text-secondary)]">Режим влияет только на автосборку черновика.</div>
                    </div>
                    <div className="flex items-center gap-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-1">
                      <button
                        type="button"
                        onClick={() => setOutcomeMode('single')}
                        className={`h-8 px-3 rounded-[2px] text-[10px] font-semibold tracking-[0.18em] uppercase transition ${outcomeMode === 'single' ? 'bg-black text-white' : 'text-[color:var(--text-secondary)] hover:text-black'}`}
                      >
                        1 исход
                      </button>
                      <button
                        type="button"
                        onClick={() => setOutcomeMode('all_numeric')}
                        className={`h-8 px-3 rounded-[2px] text-[10px] font-semibold tracking-[0.18em] uppercase transition ${outcomeMode === 'all_numeric' ? 'bg-black text-white' : 'text-[color:var(--text-secondary)] hover:text-black'}`}
                      >
                        Все числовые
                      </button>
                      <button
                        type="button"
                        onClick={() => setOutcomeMode('selected')}
                        className={`h-8 px-3 rounded-[2px] text-[10px] font-semibold tracking-[0.18em] uppercase transition ${outcomeMode === 'selected' ? 'bg-black text-white' : 'text-[color:var(--text-secondary)] hover:text-black'}`}
                      >
                        Выбор
                      </button>
                    </div>
                  </div>

                  <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                    <label className="grid gap-1">
                      <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Лимит показателей</div>
                      <input
                        type="number"
                        min={1}
                        max={200}
                        value={outcomesLimit}
                        onChange={(e) => setOutcomesLimit(e.target.value)}
                        className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                      />
                    </label>

                    <div className="grid gap-1">
                      <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">В работе</div>
                      <div className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm flex items-center justify-between">
                        <div className="text-[color:var(--text-primary)]">{selectedOutcomeList.length}</div>
                        <div className="text-xs text-[color:var(--text-secondary)]">из {numericOutcomes.length || 0}</div>
                      </div>
                    </div>
                  </div>

                  {outcomeMode === 'selected' ? (
                    <div className="mt-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Выбор показателей</div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setSelectedOutcomes([])}
                            className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-black"
                          >
                            Очистить
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const next = filteredNumericOutcomes.slice(0, Math.max(1, Number(outcomesLimit) || 1));
                              setSelectedOutcomes(next);
                            }}
                            className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-black"
                          >
                            Выбрать всё (фильтр)
                          </button>
                        </div>
                      </div>

                      <div className="mt-2 grid gap-2">
                        <input
                          value={outcomesQuery}
                          onChange={(e) => setOutcomesQuery(e.target.value)}
                          placeholder="Поиск по названию"
                          className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
                        />
                        <div className="max-h-[220px] overflow-auto rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)]">
                          {filteredNumericOutcomes.length === 0 ? (
                            <div className="p-3 text-sm text-[color:var(--text-secondary)]">Нет числовых показателей</div>
                          ) : (
                            <div className="divide-y divide-[color:var(--border-color)]">
                              {filteredNumericOutcomes.slice(0, 250).map((name) => {
                                const isChecked = Array.isArray(selectedOutcomes) && selectedOutcomes.includes(name);
                                return (
                                  <label key={name} className="px-3 py-2 flex items-center justify-between gap-3 hover:bg-[color:var(--bg-tertiary)]">
                                    <div className="min-w-0">
                                      <div className="text-sm text-[color:var(--text-primary)] truncate">{name}</div>
                                    </div>
                                    <input
                                      type="checkbox"
                                      checked={isChecked}
                                      onChange={(e) => {
                                        const checked = e.target.checked;
                                        setSelectedOutcomes((prev) => {
                                          const p = Array.isArray(prev) ? prev : [];
                                          if (checked) return p.includes(name) ? p : [...p, name];
                                          return p.filter((x) => x !== name);
                                        });
                                      }}
                                      className="h-4 w-4 accent-black"
                                      aria-label={`Выбрать ${name}`}
                                    />
                                  </label>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {massDraftError ? (
                    <div className="mt-3 text-xs text-[color:var(--accent)]">{massDraftError}</div>
                  ) : null}

                  {isMassDrafting ? (
                    <div className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">Собираю: {massDraftProgress.current || '…'}</div>
                          <div className="mt-1 text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{massDraftProgress.done}/{massDraftProgress.total}</div>
                        </div>
                        <Button
                          onClick={() => {
                            massDraftCancelRef.current = true;
                          }}
                          variant="ghost"
                          type="button"
                        >
                          Остановить
                        </Button>
                      </div>
                      <div className="mt-2 h-1.5 rounded-full bg-[color:var(--bg-tertiary)] overflow-hidden">
                        <div
                          className="h-full bg-black"
                          style={{ width: `${massDraftProgress.total > 0 ? Math.min(100, Math.round((massDraftProgress.done / massDraftProgress.total) * 100)) : 0}%` }}
                        />
                      </div>
                    </div>
                  ) : null}

                  <div className="mt-3 flex items-center justify-end gap-2">
                    <Button
                      onClick={() => {
                        autoDraftRef.current.key = null;
                        setProtocol([]);
                      }}
                      variant="ghost"
                      type="button"
                      disabled={isDrafting || isMassDrafting}
                    >
                      Пересобрать
                    </Button>
                    <Button
                      onClick={() => {
                        if (outcomeMode === 'single') {
                          void generateDraft();
                          return;
                        }
                        void generateFullDesign();
                      }}
                      variant="secondary"
                      type="button"
                      disabled={isDrafting || isMassDrafting || (outcomeMode === 'single' ? !roles.target : selectedOutcomeList.length === 0)}
                    >
                      {outcomeMode === 'single' ? (isDrafting ? 'Собираю…' : 'Собрать черновик') : (isMassDrafting ? 'Собираю…' : 'Собрать полный дизайн')}
                    </Button>
                  </div>
                </div>
              </div>

              <VariablePreview
                t={t}
                targetVar={roles.target}
                groupVar={roles.group}
                groupLabel={roles.group ? 'Группа' : 'Группа'}
                statsByName={columnStatsByName}
              />

              <div className="px-5 pb-5">
                <div className="mt-4 grid gap-2">
                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Цель исследования (для черновика ИИ)</div>
                  <textarea
                    value={designText}
                    onChange={(e) => setDesignText(e.target.value)}
                    rows={4}
                    className="w-full px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm resize-y"
                    placeholder="Например: сравнить исход между группами; учесть ковариаты; проверить нормальность; сделать пост‑хок при 3+ группах."
                  />
                  {draftError ? (
                    <div className="text-xs text-[color:var(--accent)]">{draftError}</div>
                  ) : null}
                  <div className="flex items-center justify-end">
                    <Button
                      onClick={() => generateDraft()}
                      disabled={isDrafting || !roles.target}
                      variant="secondary"
                      type="button"
                    >
                      {isDrafting ? 'Собираю…' : 'Собрать черновик'}
                    </Button>
                  </div>
                </div>
              </div>
            </section>

            <section className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
              <div className="px-5 py-4 border-b border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Confirm</div>
                <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)]">Протокол</div>
                <div className="mt-1 text-sm text-[color:var(--text-secondary)]">Проверь шаги: методы, переменные и фильтры. Затем запускай.</div>
              </div>

              <div className="p-5">
                {runError ? (
                  <div className="mb-4 p-4 bg-[color:var(--white)] border border-[color:var(--black)] text-[color:var(--text-primary)] rounded-[2px] text-sm">{runError}</div>
                ) : null}

                {protocol.length === 0 ? (
                  <div className="rounded-[2px] border border-dashed border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-6">
                    <div className="text-sm font-semibold text-[color:var(--text-primary)]">Пусто</div>
                    <div className="mt-1 text-sm text-[color:var(--text-secondary)]">Добавь тест вручную или собери черновик ИИ.</div>
                    <div className="mt-4 flex gap-2">
                      <Button onClick={() => setIsTestPickerOpen(true)} variant="ghost" type="button">Добавить тест</Button>
                      <Button onClick={() => generateDraft()} disabled={!roles.target || isDrafting} variant="secondary" type="button">Собрать черновик</Button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-xs text-[color:var(--text-secondary)]">Включено: {enabledStepsCount} из {protocol.length}</div>
                      <div className="flex items-center gap-2">
                        <Button onClick={() => toggleAllSteps(true)} disabled={isExecuting} variant="ghost" type="button">Включить всё</Button>
                        <Button onClick={() => toggleAllSteps(false)} disabled={isExecuting} variant="ghost" type="button">Отключить всё</Button>
                      </div>
                    </div>

                    <div className="space-y-2">
                      {protocolGroups.map(([outcome, steps]) => {
                        const key = String(outcome || '—').trim() || '—';
                        const isExpanded = expandedOutcomes.has(key);
                        const enabledCount = steps.filter((s) => s?.enabled !== false).length;
                        return (
                          <div key={key} className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden">
                            <button
                              type="button"
                              onClick={() => {
                                setExpandedOutcomes((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(key)) next.delete(key);
                                  else next.add(key);
                                  return next;
                                });
                              }}
                              className="w-full px-4 py-3 flex items-center justify-between gap-4 hover:bg-[color:var(--bg-tertiary)]"
                              aria-expanded={isExpanded}
                            >
                              <div className="min-w-0 text-left">
                                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Показатель</div>
                                <div className="mt-1 text-sm font-bold text-[color:var(--text-primary)] truncate">{key}</div>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <div className="text-xs text-[color:var(--text-secondary)]">{enabledCount}/{steps.length}</div>
                                <div className="h-8 px-2 rounded-[2px] border border-[color:var(--border-color)] text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-secondary)]">{isExpanded ? 'Скрыть' : 'Показать'}</div>
                              </div>
                            </button>

                            {isExpanded ? (
                              <div className="px-4 pb-4">
                                <div className="pt-3 flex items-center justify-between gap-3">
                                  <div className="text-xs text-[color:var(--text-secondary)]">Шагов: {steps.length}</div>
                                  <div className="flex items-center gap-2">
                                    <Button onClick={() => toggleOutcomeSteps(key, true)} disabled={isExecuting} variant="ghost" type="button">Включить</Button>
                                    <Button onClick={() => toggleOutcomeSteps(key, false)} disabled={isExecuting} variant="ghost" type="button">Отключить</Button>
                                  </div>
                                </div>

                                <div className="mt-3 space-y-2">
                                  {steps.map((step, localIdx) => {
                                    const isEnabled = step?.enabled !== false;
                                    return (
                                      <div key={step.id} className={`border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden ${isEnabled ? '' : 'opacity-60'}`}>
                                        <div className="px-4 py-3 flex items-start justify-between gap-4">
                                          <div className="min-w-0">
                                            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Шаг {localIdx + 1}</div>
                                            <div className="mt-1 text-sm font-bold text-[color:var(--text-primary)] truncate">{step.name || step.method}</div>
                                            <div className="mt-1 text-xs text-[color:var(--text-secondary)] font-mono truncate">{step.method}</div>
                                          </div>
                                          <div className="flex items-center gap-2 shrink-0">
                                            <label className="h-9 px-3 inline-flex items-center gap-2 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:border-black">
                                              <input
                                                type="checkbox"
                                                checked={isEnabled}
                                                onChange={(e) => handleToggleStep(step.id, e.target.checked)}
                                                className="h-4 w-4 accent-black"
                                                aria-label="Включить в анализ"
                                              />
                                              <span className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-secondary)] uppercase">В анализ</span>
                                            </label>
                                            <button
                                              type="button"
                                              onClick={() => handleEditStep(step)}
                                              className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                                            >
                                              {t('edit')}
                                            </button>
                                            <button
                                              type="button"
                                              onClick={() => removeStep(step.id)}
                                              className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                                            >
                                              Удалить
                                            </button>
                                          </div>
                                        </div>
                                        {step.config && typeof step.config === 'object' ? (
                                          <div className="px-4 pb-3">
                                            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] p-3">
                                              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1">
                                                {Object.entries(step.config)
                                                  .slice(0, 10)
                                                  .map(([k, v]) => (
                                                    <div key={k} className="flex items-baseline justify-between gap-3">
                                                      <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{k}</div>
                                                      <div className="text-xs text-[color:var(--text-primary)] font-mono truncate">{Array.isArray(v) ? v.filter(Boolean).join(', ') : String(v ?? '')}</div>
                                                    </div>
                                                  ))}
                                              </div>
                                            </div>
                                          </div>
                                        ) : null}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>

                    <div className="pt-2 flex items-center justify-between gap-3">
                      <Button onClick={() => setProtocol([])} disabled={isExecuting} variant="ghost" type="button">Очистить</Button>
                      <Button onClick={handleRun} disabled={isExecuting || enabledStepsCount === 0} variant="primary" type="button">{isExecuting ? 'Выполняю…' : 'Выполнить'}</Button>
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>

      {isTestPickerOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-label="Выбор теста"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setIsTestPickerOpen(false);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setIsTestPickerOpen(false);
          }}
        >
          <div className="w-full max-w-5xl max-h-[82vh] bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-[color:var(--border-color)] flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Тесты</div>
                <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Добавить шаг</div>
              </div>
              <button
                type="button"
                onClick={() => setIsTestPickerOpen(false)}
                className="h-9 w-9 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-black hover:text-black"
                aria-label="Закрыть"
              >
                ×
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <TestSelectionPanel
                variant="compact"
                onTestSelect={(test) => {
                  handleTestSelect(test);
                  setIsTestPickerOpen(false);
                }}
                datasetId={datasetIdResolved}
                suggestedConfig={roles}
                disabled={isExecuting}
              />
            </div>
          </div>
        </div>
      ) : null}

      <TestConfigModal
        isOpen={isConfigModalOpen}
        onClose={() => {
          setIsConfigModalOpen(false);
          setSelectedTest(null);
          setEditingTest(null);
        }}
        method={selectedTest?.id}
        initialConfig={editingTest?.config || {}}
        onConfigSave={handleConfigSave}
        columns={columns}
        suggestedConfig={roles}
        datasetId={datasetIdResolved}
      />
    </>
  );
};

export default AnalysisAIDesign;
