import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useUndoRedo } from '../hooks/useUndoRedo';
import { useTranslation } from '../../hooks/useTranslation';
import {
  getAISuggestions,
  getAlphaSetting,
  getDataset,
  getDatasets,
  getScanReport,
  getVariableMapping,
  getAnalysisTemplates,
  analysisPlan,
  designAnalysisFromTemplate,
  executeProtocolV2,
  getDatasetDesignReview,
  confirmDatasetDesignReview,
  revokeDatasetDesignReview,
} from '../../lib/api';
import { parseError } from '../utils/errorMessages';

import { DatasetErrorView, DatasetLoadingView, DatasetPickerView } from './analysis-design/AnalysisDesignStates';
import AnalysisDesignWorkspaceLayout from './analysis-design/AnalysisDesignWorkspaceLayout';
import {
  normalizeWorkspaceRoles,
  buildRoleByName,
  mergeTemplateVarsFromRoles,
  makeId,
  normalizeDesignReviewStatus,
  buildDesignReviewGlobals,
  normalizeSavedProtocol,
  loadSavedProtocols,
  normalizeGlobalSettings,
  loadGlobalSettings,
  saveGlobalSettings,
  saveSavedProtocols,
  PROTOCOL_STORAGE_KEY,
  GLOBAL_SETTINGS_STORAGE_KEY,
} from './analysis-design/analysisDesignUtils';

export const AnalysisDesignLegacy = ({ mode = 'constructor' }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id: datasetIdFromRoute } = useParams();

  const formatMethodName = useCallback((methodId) => {
    if (!methodId) return '';
    if (methodId === 'mixed_effects') return t('mixed_effects');
    if (methodId === 'clustered_correlation') return t('clustered_correlation');
    return String(methodId).replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  }, [t]);

  const [datasets, setDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetsError, setDatasetsError] = useState(null);

  const [datasetId, setDatasetId] = useState(null);
  const [datasetName, setDatasetName] = useState(null);
  const [columns, setColumns] = useState([]);
  const [scanReport, setScanReport] = useState(null);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [datasetError, setDatasetError] = useState(null);

  const {
    present: protocol,
    set: setProtocol,
    undo: undoProtocol,
    redo: redoProtocol,
    reset: resetProtocolHistory,
    canUndo,
    canRedo
  } = useUndoRedo([], { limit: 20 });
  const [savedProtocols, setSavedProtocols] = useState(() => loadSavedProtocols());
  const [globalSettings, setGlobalSettings] = useState(() => loadGlobalSettings());
  const [isSaveProtocolOpen, setIsSaveProtocolOpen] = useState(false);
  const [isProtocolLibraryOpen, setIsProtocolLibraryOpen] = useState(false);
  const [saveProtocolSeed, setSaveProtocolSeed] = useState(0);
  const [isShortcutsHelpOpen, setIsShortcutsHelpOpen] = useState(false);
  const [isMassDynamicsOpen, setIsMassDynamicsOpen] = useState(false);
  const [massDynamicsSeed, setMassDynamicsSeed] = useState(0);
  const [selectedTest, setSelectedTest] = useState(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [editingTest, setEditingTest] = useState(null);
  const [rightPane, setRightPane] = useState('inspector');
  const [selectedStepId, setSelectedStepId] = useState(null);
  const [workspaceRoles, setWorkspaceRoles] = useState({ target: '', group: '', covariates: [] });
  const [aiRecommendations, setAIRecommendations] = useState([]);
  const [isAIAnalyzing, setIsAIAnalyzing] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [results, setResults] = useState(null);

  const [isVibeOpen, setIsVibeOpen] = useState(false);
  const [vibeText, setVibeText] = useState('');
  const [vibePreview, setVibePreview] = useState(null);
  const [vibeError, setVibeError] = useState(null);
  const [isVibeLoading, setIsVibeLoading] = useState(false);

  const [isResultsOpen, setIsResultsOpen] = useState(false);
  const [designReviewConfirmed, setDesignReviewConfirmed] = useState(false);
  const [designReviewTimestamp, setDesignReviewTimestamp] = useState(null);
  const [designReviewSaving, setDesignReviewSaving] = useState(false);
  const [designReviewError, setDesignReviewError] = useState(null);

  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [templateVars, setTemplateVars] = useState({
    target: '',
    group: '',
    predictor: ''
  });

  const datasetIdResolved = datasetIdFromRoute || datasetId;

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
          source: 'analysis_design',
          actor: 'user',
        });
        const normalized = normalizeDesignReviewStatus(payload);
        setDesignReviewConfirmed(normalized.confirmed);
        setDesignReviewTimestamp(normalized.confirmedAt || new Date().toISOString());
      } else {
        await revokeDatasetDesignReview(datasetIdResolved, {
          source: 'analysis_design',
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

  useEffect(() => {
    if (!selectedStepId) return;
    const exists = protocol.some((s) => s?.id === selectedStepId);
    if (!exists) setSelectedStepId(null);
  }, [protocol, selectedStepId]);

  const totalRows = useMemo(() => {
    const n = scanReport?.missing_report?.total_rows;
    return typeof n === 'number' ? n : 0;
  }, [scanReport]);

  useEffect(() => {
    void syncDesignReviewStatus(datasetIdResolved);
  }, [datasetIdResolved, syncDesignReviewStatus]);

  useEffect(() => {
    saveSavedProtocols(savedProtocols);
  }, [savedProtocols]);

  useEffect(() => {
    saveGlobalSettings(globalSettings);
  }, [globalSettings]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setDatasetError(null);

      if (!datasetIdFromRoute) {
        setDatasetId(null);
        setDatasetName(null);
        setColumns([]);
        setDesignReviewConfirmed(false);
        setDesignReviewTimestamp(null);
        setDesignReviewError(null);
        return;
      }

      setDatasetLoading(true);
      try {
        const profile = await getDataset(datasetIdFromRoute);
        if (cancelled) return;
        setDatasetId(profile?.id || datasetIdFromRoute);
        const fallbackName = profile?.filename || profile?.name;
        setDatasetName(fallbackName || datasetIdFromRoute);
        setColumns(Array.isArray(profile?.columns) ? profile.columns : []);

        try {
          const report = await getScanReport(datasetIdFromRoute);
          if (!cancelled) setScanReport(report);
        } catch {
          if (!cancelled) setScanReport(null);
        }

        setSelectedTemplateId('');
        setTemplateVars({ target: '', group: '', predictor: '' });
        setWorkspaceRoles({ target: '', group: '', covariates: [] });
        resetProtocolHistory([]);
        setResults(null);
        setIsResultsOpen(false);

        try {
          const res = await getVariableMapping(datasetIdFromRoute);
          if (cancelled) return;
          const mapping = res?.mapping && typeof res.mapping === 'object' ? res.mapping : {};

          let nextTarget = '';
          let nextGroup = '';
          const nextCovariates = [];

          Object.entries(mapping).forEach(([name, meta]) => {
            const role = meta?.role;
            if (!nextTarget && role === 'Исход') nextTarget = name;
            if (!nextGroup && role === 'Группа') nextGroup = name;
            if (role === 'Ковариата') nextCovariates.push(name);
          });

          if (nextTarget || nextGroup || nextCovariates.length > 0) {
            setWorkspaceRoles({ target: nextTarget, group: nextGroup, covariates: nextCovariates });
            setTemplateVars((prev) => ({
              ...prev,
              target: prev.target || nextTarget,
              group: prev.group || nextGroup,
            }));
          }
        } catch (e) {
          void e;
        }

        if (!fallbackName) {
          try {
            const list = await getDatasets();
            if (cancelled) return;
            const hit = Array.isArray(list) ? list.find((d) => d?.id === datasetIdFromRoute) : null;
            if (hit?.filename) setDatasetName(hit.filename);
          } catch {
            if (cancelled) return;
          }
        }
      } catch (e) {
        if (cancelled) return;
        setDatasetError(e?.message || String(e));
      } finally {
        if (!cancelled) setDatasetLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [datasetIdFromRoute, resetProtocolHistory]);

  useEffect(() => {
    let cancelled = false;

    const loadTemplates = async () => {
      setTemplatesError(null);
      setTemplatesLoading(true);
      try {
        const data = await getAnalysisTemplates();
        if (cancelled) return;
        setTemplates(Array.isArray(data?.templates) ? data.templates : []);
      } catch (e) {
        if (cancelled) return;
        setTemplates([]);
        setTemplatesError(e?.message || String(e));
      } finally {
        if (!cancelled) setTemplatesLoading(false);
      }
    };

    loadTemplates();

    return () => {
      cancelled = true;
    };
  }, []);

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

  const handleTestSelect = (test) => {
    setSelectedTest(test);
    setEditingTest(null);
    setIsConfigModalOpen(true);
  };

  const handleConfigSave = (config) => {
    if (editingTest) {
      setProtocol((prev) =>
        prev.map((test) => {
          if (test.id !== editingTest.id) return test;
          const mergedConfig = { ...(test.config || {}), ...(config || {}) };
          return {
            ...test,
            config: applyGlobalDefaultsToConfig(test.method, mergedConfig),
          };
        })
      );
    } else {
      const methodId = selectedTest?.id;

      if (
        (methodId === 'anova' || methodId === 'anova_welch' || methodId === 'kruskal')
        && Array.isArray(config?.targets)
        && config.targets.length > 0
      ) {
        const group = config.group || '';
        const baseConfig = { ...config };
        delete baseConfig.targets;
        delete baseConfig.target;
        delete baseConfig.outcome;

        const now = Date.now();
        const newTests = config.targets
          .filter(Boolean)
          .map((target, idx) => ({
            id: `test_${now}_${idx}`,
            method: methodId,
            name: selectedTest.name,
            config: applyGlobalDefaultsToConfig(methodId, { ...baseConfig, target, group }),
            enabled: true,
          }));

        if (newTests.length > 0) setProtocol(prev => [...prev, ...newTests]);
      } else {
        const newTest = {
          id: `test_${Date.now()}`,
          method: selectedTest.id,
          name: selectedTest.name,
          config: applyGlobalDefaultsToConfig(selectedTest.id, config),
          enabled: true,
        };
        setProtocol(prev => [...prev, newTest]);
      }
    }
    setIsConfigModalOpen(false);
    setSelectedTest(null);
    setEditingTest(null);
  };

  const handleRemoveTest = (testId) => {
    setProtocol(prev => prev.filter(test => test.id !== testId));
    setSelectedStepId((current) => (current === testId ? null : current));
  };

  const handleEditTest = (test) => {
    setEditingTest(test);
    setSelectedTest({ id: test.method, name: test.name });
    setIsConfigModalOpen(true);
  };

  const handleMoveTest = (fromIndex, toIndex) => {
    setProtocol((prev) => {
      const next = Array.isArray(prev) ? [...prev] : [];
      const [moved] = next.splice(fromIndex, 1);
      if (!moved) return prev;
      next.splice(toIndex, 0, moved);
      return next;
    });
  };

  const handleToggleTest = useCallback((testId, enabled) => {
    setProtocol((prev) =>
      (Array.isArray(prev) ? prev : []).map((s) => {
        if (s?.id !== testId) return s;
        return { ...s, enabled: Boolean(enabled) };
      })
    );
    setSelectedStepId((current) => (current === testId ? null : current));
  }, [setProtocol, setSelectedStepId]);

  const handleAISuggest = async () => {
    if (!datasetIdResolved) {
      setRightPane('ai');
      setAiError(t('select_dataset_first'));
      setAIRecommendations([]);
      return;
    }

    setIsAIAnalyzing(true);
    setRightPane('ai');
    setAiError(null);

    try {
      const data = await getAISuggestions(
        datasetIdResolved,
        protocol.filter((s) => s?.enabled !== false).map((test) => ({
          id: test.id,
          method: test.method,
          config: test.config,
        }))
      );
      setAIRecommendations(Array.isArray(data?.recommendations) ? data.recommendations : []);
    } catch (error) {
      const parsed = parseError(error?.message || String(error));
      setAiError(parsed?.title || 'Не удалось получить рекомендации ИИ');
      setAIRecommendations([]);
    } finally {
      setIsAIAnalyzing(false);
    }
  };

  const handleAddRecommendation = (recommendation) => {
    const newTest = {
      id: `test_${Date.now()}`,
      method: recommendation.test.id,
      name: recommendation.test.name,
      config: applyGlobalDefaultsToConfig(recommendation.test.id, recommendation.test.config || {}),
      enabled: true,
    };
    setProtocol(prev => [...prev, newTest]);
  };

  const globalDefaults = useMemo(() => normalizeGlobalSettings(globalSettings), [globalSettings]);

  const applyGlobalDefaultsToConfig = useCallback((methodId, config) => {
    const c = (config && typeof config === 'object') ? { ...config } : {};
    const method = String(methodId || '').trim();

    const needsAlternative = new Set([
      't_test_ind',
      't_test_welch',
      'mann_whitney',
      't_test_rel',
      'wilcoxon',
      'pearson',
      'spearman',
    ]);

    const needsPostHoc = new Set(['anova', 'anova_welch', 'kruskal']);

    if (needsAlternative.has(method) && c.alternative == null) {
      c.alternative = globalDefaults.alternative;
    }

    if (needsPostHoc.has(method)) {
      if (c.post_hoc == null) c.post_hoc = globalDefaults.post_hoc;
      if (c.post_hoc_correction == null) c.post_hoc_correction = globalDefaults.post_hoc_correction;
    }

    return c;
  }, [globalDefaults]);

  const handleGlobalSettingsChange = useCallback((nextValue) => {
    const next = normalizeGlobalSettings(nextValue);
    setGlobalSettings(next);
    setProtocol((prev) => {
      const list = Array.isArray(prev) ? prev : [];

      const needsAlternative = new Set([
        't_test_ind',
        't_test_welch',
        'mann_whitney',
        't_test_rel',
        'wilcoxon',
        'pearson',
        'spearman',
      ]);

      const needsPostHoc = new Set(['anova', 'anova_welch', 'kruskal']);

      return list.map((s) => {
        const method = String(s?.method || '').trim();
        const cfg = (s?.config && typeof s.config === 'object') ? { ...s.config } : {};

        if (needsAlternative.has(method) && cfg.alternative == null) {
          cfg.alternative = next.alternative;
        }

        if (needsPostHoc.has(method)) {
          if (cfg.post_hoc == null) cfg.post_hoc = next.post_hoc;
          if (cfg.post_hoc_correction == null) cfg.post_hoc_correction = next.post_hoc_correction;
        }

        return { ...s, config: cfg };
      });
    });
  }, [setProtocol]);

  const openVibe = useCallback(() => {
    setIsVibeOpen(true);
    setVibeError(null);
    setVibePreview(null);
  }, []);

  const handleExecuteProtocol = useCallback(async (protocolToExecute, options) => {
    const stepsToExecute = (Array.isArray(protocolToExecute) ? protocolToExecute : []).filter((s) => s?.enabled !== false);
    if (!designReviewConfirmed) {
      setDesignReviewError('Перед запуском подтвердите Design Review');
      return;
    }
    setDesignReviewError(null);

    const normalizeStepForBackend = (step) => {
      const rawMethod = step?.method;
      const method = rawMethod === 'mixed_model' ? 'mixed_effects' : rawMethod;
      const c = step?.config && typeof step.config === 'object' ? step.config : {};

      if (method === 'clustered_correlation') {
        const variables = Array.isArray(c.variables) ? c.variables : Array.isArray(c.targets) ? c.targets : [];
        return { ...step, method, config: { ...c, variables } };
      }

      if (method === 'mixed_effects') {
        const outcome = c.outcome || c.target || '';
        return { ...step, method, config: { ...c, outcome } };
      }

      if (method === 'linear_regression' || method === 'logistic_regression') {
        const outcome = c.outcome || c.target || '';
        const predictors = Array.isArray(c.predictors)
          ? c.predictors
          : Array.isArray(c.targets)
            ? c.targets
            : [];
        const covariates = Array.isArray(c.covariates) ? c.covariates : [];
        const group = c.group || predictors?.[0] || '';
        return { ...step, method, config: { ...c, outcome, group, predictors, covariates } };
      }

      if (method === 'pearson' || method === 'spearman') {
        const targets = Array.isArray(c.targets) ? c.targets : [];
        const outcome = c.outcome || c.target || targets?.[0] || '';
        const group = c.group || targets?.[1] || '';
        return { ...step, method, config: { ...c, outcome, group } };
      }

      const outcome = c.outcome || c.target || '';
      const group = c.group || '';
      return { ...step, method, config: { ...c, outcome, group } };
    };

    setIsExecuting(true);

    try {
      const payload = stepsToExecute.map((test) => {
        const normalized = normalizeStepForBackend(test);
        return {
          id: normalized.id,
          method: normalized.method,
          config: applyGlobalDefaultsToConfig(normalized.method, normalized.config)
        };
      });
      const globals = buildDesignReviewGlobals({
        source: 'analysis_design_legacy',
        confirmed: designReviewConfirmed,
        confirmedAt: designReviewTimestamp,
        extra: options?.globals,
      });
      const data = await executeProtocolV2(
        datasetIdResolved,
        payload,
        getAlphaSetting(),
        options?.protocolName || null,
        globals
      );
      setResults(data);
      setIsResultsOpen(true);
      options?.onSuccess?.(data);
    } catch (error) {
      const err = error?.message || String(error) || 'Не удалось выполнить протокол';
      setResults({
        status: 'error',
        completed_steps: 0,
        total_steps: stepsToExecute.length,
        errors: [{ method: 'protocol', error: err }],
        results: []
      });
      setIsResultsOpen(true);
      console.error('Protocol execution failed:', error);
    } finally {
      setIsExecuting(false);
    }
  }, [applyGlobalDefaultsToConfig, datasetIdResolved, designReviewConfirmed, designReviewTimestamp]);

  const handleVibeGenerate = useCallback(async () => {
    if (!datasetIdResolved) return;
    const text = String(vibeText || '').trim();
    if (text.length < 12) return;

    setIsVibeLoading(true);
    setVibeError(null);
    try {
      const data = await analysisPlan(datasetIdResolved, text, {
        protocol: protocol.map((test) => ({ id: test.id, method: test.method, config: test.config })),
        preferences: globalDefaults,
      });
      setVibePreview(data);
      const merged = normalizeGlobalSettings({
        ...globalDefaults,
        ...(data?.globals && typeof data.globals === 'object' ? data.globals : {}),
      });
      setGlobalSettings(merged);
    } catch (e) {
      setVibePreview(null);
      setVibeError(e?.message || String(e));
    } finally {
      setIsVibeLoading(false);
    }
  }, [datasetIdResolved, globalDefaults, protocol, vibeText]);

  const handleVibeGenerateAndRun = useCallback(async () => {
    if (!datasetIdResolved) return;
    const text = String(vibeText || '').trim();
    if (text.length < 12) return;

    setIsVibeLoading(true);
    setVibeError(null);

    try {
      const data = await analysisPlan(datasetIdResolved, text, {
        protocol: protocol.map((test) => ({ id: test.id, method: test.method, config: test.config })),
        preferences: globalDefaults,
      });
      setVibePreview(data);
      const merged = normalizeGlobalSettings({
        ...globalDefaults,
        ...(data?.globals && typeof data.globals === 'object' ? data.globals : {}),
      });
      setGlobalSettings(merged);

      const steps = Array.isArray(data?.protocol) ? data.protocol : [];
      if (steps.length === 0) {
        throw new Error('ИИ не вернул шаги протокола');
      }

      const now = Date.now();
      const protocolToExecute = steps
        .map((s, idx) => {
          const method = String(s?.method || '').trim();
          if (!method) return null;
          const cfg = (s?.config && typeof s.config === 'object') ? s.config : {};
          const nextCfg = applyGlobalDefaultsToConfig(method, cfg);
          return {
            id: `vibe_${now}_${idx}`,
            method,
            name: String(s?.name || '').trim() || formatMethodName(method),
            config: nextCfg,
          };
        })
        .filter(Boolean);

      if (protocolToExecute.length === 0) {
        throw new Error('Не удалось собрать валидные шаги для выполнения');
      }

      await handleExecuteProtocol(protocolToExecute, {
        protocolName: String(data?.protocol_name || '').trim() || (datasetName ? `Протокол: ${datasetName}` : 'Протокол'),
        onSuccess: (res) => {
          const runId = res?.run_id;
          if (!runId) return;
          setIsVibeOpen(false);
          setResults(null);
          setIsResultsOpen(false);
          navigate(`/report/${datasetIdResolved}?run=${encodeURIComponent(String(runId))}`);
        },
      });
    } catch (e) {
      setVibeError(e?.message || String(e));
    } finally {
      setIsVibeLoading(false);
    }
  }, [applyGlobalDefaultsToConfig, datasetIdResolved, datasetName, formatMethodName, globalDefaults, handleExecuteProtocol, navigate, protocol, vibeText]);

  const handleApplyVibePreview = useCallback(() => {
    const steps = Array.isArray(vibePreview?.protocol) ? vibePreview.protocol : [];
    if (steps.length === 0) return;

    const now = Date.now();
    const mergedSteps = steps
      .map((s, idx) => {
        const method = String(s?.method || '').trim();
        if (!method) return null;
        const cfg = (s?.config && typeof s.config === 'object') ? s.config : {};
        const nextCfg = applyGlobalDefaultsToConfig(method, cfg);
        return {
          id: `vibe_${now}_${idx}`,
          method,
          name: String(s?.name || '').trim() || formatMethodName(method),
          config: nextCfg,
        };
      })
      .filter(Boolean);

    if (mergedSteps.length === 0) return;

    setProtocol((prev) => {
      const next = Array.isArray(prev) ? prev : [];
      return [...next, ...mergedSteps];
    });
    setIsVibeOpen(false);
    setResults(null);
    setIsResultsOpen(false);
  }, [applyGlobalDefaultsToConfig, formatMethodName, setProtocol, vibePreview]);

  const handleAppendMassSteps = useCallback((steps) => {
    const list = Array.isArray(steps) ? steps.filter(Boolean) : [];
    if (list.length === 0) return;
    setProtocol((prev) => {
      const next = Array.isArray(prev) ? prev : [];
      return [...next, ...list];
    });
    setResults(null);
    setIsResultsOpen(false);
  }, [setProtocol]);

  const selectedStepMeta = useMemo(() => {
    if (!selectedStepId) return { step: null, index: -1 };
    const idx = protocol.findIndex((s) => s?.id === selectedStepId);
    if (idx < 0) return { step: null, index: -1 };
    return { step: protocol[idx], index: idx };
  }, [protocol, selectedStepId]);

  const columnNames = useMemo(() => {
    return Array.isArray(columns)
      ? columns
        .map((c) => {
          if (!c) return null;
          if (typeof c === 'string') return c;
          return c.name || c.column || c.id || null;
        })
        .filter(Boolean)
      : [];
  }, [columns]);

  const selectedTemplate = useMemo(() => {
    return templates.find((tpl) => tpl.id === selectedTemplateId) || null;
  }, [selectedTemplateId, templates]);

  const humanizeError = parseError;

  const templateGoal = selectedTemplate?.goal;
  const templateSecondaryKey = templateGoal === 'relationship' ? 'predictor' : 'group';

  const roleByName = useMemo(() => buildRoleByName(workspaceRoles), [workspaceRoles]);

  const handleWorkspaceRolesChange = useCallback((next) => {
    const safeNext = normalizeWorkspaceRoles(next);
    setWorkspaceRoles(safeNext);
    setTemplateVars((prev) => mergeTemplateVarsFromRoles(prev, safeNext, templateSecondaryKey));
  }, [templateSecondaryKey]);

  const applySavedProtocol = (p) => {
    const normalized = normalizeSavedProtocol(p);
    if (!normalized) return;

    const steps = Array.isArray(normalized.steps) ? normalized.steps : [];
    setProtocol(
      steps.map((step, idx) => ({
        id: step?.id || `saved_${Date.now()}_${idx}`,
        method: step?.method,
        name: formatMethodName(step?.method),
        config: applyGlobalDefaultsToConfig(step?.method, step?.config || {})
      }))
    );
    setResults(null);
    setIsResultsOpen(false);
    setIsProtocolLibraryOpen(false);
  };

  const handleSaveProtocol = ({ name, description, tags }) => {
    const normalized = normalizeSavedProtocol({
      id: makeId(),
      name,
      description,
      tags,
      created_at: new Date().toISOString(),
      steps: protocol.map((s) => ({ method: s?.method, config: s?.config || {} }))
    });
    if (!normalized) return;
    setSavedProtocols((prev) => [normalized, ...(Array.isArray(prev) ? prev : [])]);
    setIsSaveProtocolOpen(false);
  };

  const handleImportProtocol = (raw) => {
    const normalized = normalizeSavedProtocol(raw);
    if (!normalized) {
      window.alert('Импорт не удался: проверьте формат протокола');
      return;
    }

    setSavedProtocols((prev) => {
      const next = Array.isArray(prev) ? prev : [];
      const deduped = next.filter((p) => p.id !== normalized.id);
      return [normalized, ...deduped];
    });
  };

  useEffect(() => {
    const target = templateVars?.target || '';
    const group = templateSecondaryKey === 'predictor' ? (templateVars?.predictor || '') : (templateVars?.group || '');
    setWorkspaceRoles((prev) => {
      const next = { ...prev, target, group };
      if (next.target === prev.target && next.group === prev.group) return prev;
      return next;
    });
  }, [templateSecondaryKey, templateVars?.target, templateVars?.group, templateVars?.predictor]);

  const columnStatsByName = useMemo(() => {
    const cols = scanReport?.columns;
    if (!cols || typeof cols !== 'object') return {};
    return cols;
  }, [scanReport]);

  const flowStepData = useMemo(() => {
    const dataLoaded = Boolean(datasetIdResolved) && Array.isArray(columns) && columns.length > 0;
    const variablesSet = Boolean(workspaceRoles?.target) && Boolean(workspaceRoles?.group);
    const designReady = variablesSet;

    const analysisRunning = Boolean(isExecuting);
    const analysisDone = Boolean(results) && results?.status !== 'error';
    const resultsReady = Boolean(results) && results?.status !== 'error';
    const graphsReady = resultsReady;
    const reportReady = resultsReady;

    const dataSummary = totalRows > 0
      ? `${totalRows}×${columns.length}`
      : columns.length > 0
        ? `${columns.length} колонок`
        : '';

    const designSummary = workspaceRoles?.target
      ? `${workspaceRoles.target}${workspaceRoles?.group ? `, ${workspaceRoles.group}` : ''}`
      : '';

    const analyzeSummary = analysisRunning
      ? 'выполняется'
      : analysisDone
        ? `${results?.completed_steps ?? 0}/${results?.total_steps ?? 0}`
        : '';

    const reportSummary = resultsReady ? 'готово' : '';

    return {
      dataLoaded,
      variablesSet,
      designReady,
      analysisRunning,
      analysisDone,
      resultsReady,
      graphsReady,
      reportReady,
      data_summary: dataSummary,
      design_summary: designSummary,
      analyze_summary: analyzeSummary,
      report_summary: reportSummary,
    };
  }, [columns, datasetIdResolved, isExecuting, results, totalRows, workspaceRoles?.group, workspaceRoles?.target]);

  const previewSteps = useMemo(() => {
    const out = [];
    if (datasetIdResolved && (totalRows > 0 || columns.length > 0)) {
      out.push({
        label: 'После загрузки',
        summary: `${totalRows > 0 ? `n = ${totalRows}` : 'n = —'} • ${columns.length} колонок`,
      });
    }

    const target = workspaceRoles?.target;
    const group = workspaceRoles?.group;
    if (target || group) {
      const targetStats = target ? columnStatsByName?.[target] : null;
      const groupStats = group ? columnStatsByName?.[group] : null;

      const pieces = [];
      if (target) {
        const mean = typeof targetStats?.mean === 'number' ? targetStats.mean : null;
        pieces.push(mean != null ? `Target: ${target} (M=${mean.toFixed(2)})` : `Target: ${target}`);
      }
      if (group) {
        const top = Array.isArray(groupStats?.top_values) ? groupStats.top_values : [];
        const topLine = top
          .slice(0, 3)
          .map((v) => (v?.value != null && typeof v?.count === 'number' ? `${v.value}: ${v.count}` : null))
          .filter(Boolean)
          .join(', ');
        pieces.push(topLine ? `Group: ${group} (${topLine})` : `Group: ${group}`);
      }

      let warning = '';
      const unique = typeof groupStats?.unique_count === 'number' ? groupStats.unique_count : null;
      if (unique != null && unique < 2) warning = t('groups_too_few_warning');

      out.push({
        label: 'После выбора переменных',
        summary: pieces.join(' • ') || '—',
        warning: warning || undefined,
      });
    }

    if (results) {
      const resList = Array.isArray(results?.results) ? results.results : [];
      const best = resList.find((r) => typeof r?.p_value === 'number') || resList[0] || null;
      const method = best?.method ? formatMethodName(best.method) : null;
      const p = typeof best?.p_value === 'number' ? best.p_value : null;
      const pStr = typeof p === 'number' ? (p < 0.001 ? '<0.001' : p.toFixed(4)) : null;

      out.push({
        label: 'После анализа',
        summary: method && pStr ? `${method} • p=${pStr}` : results?.status ? String(results.status) : '—',
      });
    }

    return out;
  }, [columnStatsByName, columns.length, datasetIdResolved, formatMethodName, results, t, totalRows, workspaceRoles?.group, workspaceRoles?.target]);

  const canApplyTemplate = Boolean(selectedTemplate)
    && Boolean(datasetIdResolved)
    && Boolean(templateVars.target)
    && Boolean(templateVars[templateSecondaryKey]);

  const handleApplyTemplate = async () => {
    if (!canApplyTemplate) return;

    const goal = selectedTemplate.goal;
    const variables = goal === 'relationship'
      ? { target: templateVars.target, predictor: templateVars.predictor }
      : { target: templateVars.target, group: templateVars.group };

    try {
      const data = await designAnalysisFromTemplate(
        datasetIdResolved,
        goal,
        variables,
        selectedTemplate.id
      );
      const steps = Array.isArray(data?.protocol) ? data.protocol : [];
      setProtocol(
        steps.map((step, idx) => ({
          id: step?.id || `tpl_${Date.now()}_${idx}`,
          method: step?.method,
          name: formatMethodName(step?.method),
          config: step?.config || {}
        }))
      );
      setResults(null);
      setIsResultsOpen(false);
    } catch (e) {
      setTemplatesError(e?.message || String(e));
    }
  };

  const handleCloseConfigModal = useCallback(() => {
    setIsConfigModalOpen(false);
    setSelectedTest(null);
    setEditingTest(null);
  }, []);

  const closeAllModals = useCallback(() => {
    if (isConfigModalOpen) handleCloseConfigModal();
    if (isSaveProtocolOpen) setIsSaveProtocolOpen(false);
    if (isProtocolLibraryOpen) setIsProtocolLibraryOpen(false);
    if (isShortcutsHelpOpen) setIsShortcutsHelpOpen(false);
    if (isVibeOpen) setIsVibeOpen(false);
  }, [handleCloseConfigModal, isConfigModalOpen, isProtocolLibraryOpen, isSaveProtocolOpen, isShortcutsHelpOpen, isVibeOpen]);

  const shortcuts = useMemo(() => ({
    'mod+enter': () => {
      if (isExecuting) return;
      if (protocol.length === 0) return;
      handleExecuteProtocol(protocol);
    },
    'mod+s': () => {
      if (isExecuting) return;
      if (protocol.length === 0) return;
      setSaveProtocolSeed(Date.now());
      setIsSaveProtocolOpen(true);
    },
    'mod+o': () => {
      if (isExecuting) return;
      setIsProtocolLibraryOpen(true);
    },
    'mod+z': () => {
      if (canUndo) undoProtocol();
    },
    'mod+shift+z': () => {
      if (canRedo) redoProtocol();
    },
    escape: () => {
      closeAllModals();
    },
    '?': () => {
      setIsShortcutsHelpOpen(true);
    }
  }), [canRedo, canUndo, closeAllModals, handleExecuteProtocol, isExecuting, protocol, redoProtocol, undoProtocol]);

  useKeyboardShortcuts(shortcuts);

  const onBack = useCallback(() => {
    navigate('/datasets');
  }, [navigate]);

  const resolveDatasetRoute = useCallback((nextDatasetId) => {
    if (mode === 'tests') return nextDatasetId ? `/tests/${nextDatasetId}` : '/tests';
    if (mode === 'protocol') return nextDatasetId ? `/protocol/${nextDatasetId}` : '/protocol';
    return nextDatasetId ? `/design/${nextDatasetId}` : '/design';
  }, [mode]);

  if (!datasetIdFromRoute) {
    return (
      <DatasetPickerView
        t={t}
        datasets={datasets}
        datasetsLoading={datasetsLoading}
        datasetsError={datasetsError}
        onSelectDataset={(nextDatasetId) => navigate(resolveDatasetRoute(nextDatasetId))}
        onUpload={() => navigate('/upload')}
      />
    );
  }

  if (datasetLoading) {
    return <DatasetLoadingView t={t} />;
  }

  if (datasetError) {
    return <DatasetErrorView t={t} error={datasetError} onBack={onBack} />;
  }

  return (
    <AnalysisDesignWorkspaceLayout
      t={t}
      mode={mode}
      onBack={onBack}
      datasetName={datasetName}
      navigate={navigate}
      datasetIdResolved={datasetIdResolved}
      columns={columns}
      flowStepData={flowStepData}
      designReviewConfirmed={designReviewConfirmed}
      designReviewTimestamp={designReviewTimestamp}
      designReviewError={designReviewError}
      designReviewSaving={designReviewSaving}
      isExecuting={isExecuting}
      handleToggleDesignReview={handleToggleDesignReview}
      protocol={protocol}
      handleTestSelect={handleTestSelect}
      workspaceRoles={workspaceRoles}
      setMassDynamicsSeed={setMassDynamicsSeed}
      setIsMassDynamicsOpen={setIsMassDynamicsOpen}
      templates={templates}
      templatesLoading={templatesLoading}
      templatesError={templatesError}
      selectedTemplateId={selectedTemplateId}
      setSelectedTemplateId={setSelectedTemplateId}
      setTemplateVars={setTemplateVars}
      selectedTemplate={selectedTemplate}
      templateVars={templateVars}
      columnNames={columnNames}
      columnStatsByName={columnStatsByName}
      canApplyTemplate={canApplyTemplate}
      handleApplyTemplate={handleApplyTemplate}
      selectedStepId={selectedStepId}
      setSelectedStepId={setSelectedStepId}
      handleToggleTest={handleToggleTest}
      handleEditTest={handleEditTest}
      resetProtocolHistory={resetProtocolHistory}
      setResults={setResults}
      formatMethodName={formatMethodName}
      handleMoveTest={handleMoveTest}
      handleExecuteProtocol={handleExecuteProtocol}
      handleAISuggest={handleAISuggest}
      openVibe={openVibe}
      setSaveProtocolSeed={setSaveProtocolSeed}
      setIsSaveProtocolOpen={setIsSaveProtocolOpen}
      setIsProtocolLibraryOpen={setIsProtocolLibraryOpen}
      undoProtocol={undoProtocol}
      redoProtocol={redoProtocol}
      canUndo={canUndo}
      canRedo={canRedo}
      isAIAnalyzing={isAIAnalyzing}
      results={results}
      isResultsOpen={isResultsOpen}
      setIsResultsOpen={setIsResultsOpen}
      humanizeError={humanizeError}
      rightPane={rightPane}
      setRightPane={setRightPane}
      aiRecommendations={aiRecommendations}
      aiError={aiError}
      handleAddRecommendation={handleAddRecommendation}
      roleByName={roleByName}
      handleWorkspaceRolesChange={handleWorkspaceRolesChange}
      templateSecondaryKey={templateSecondaryKey}
      previewSteps={previewSteps}
      selectedStepMeta={selectedStepMeta}
      handleRemoveTest={handleRemoveTest}
      massDynamicsSeed={massDynamicsSeed}
      isMassDynamicsOpen={isMassDynamicsOpen}
      handleAppendMassSteps={handleAppendMassSteps}
      isVibeOpen={isVibeOpen}
      setIsVibeOpen={setIsVibeOpen}
      vibeText={vibeText}
      setVibeText={setVibeText}
      globalDefaults={globalDefaults}
      handleGlobalSettingsChange={handleGlobalSettingsChange}
      handleVibeGenerate={handleVibeGenerate}
      handleVibeGenerateAndRun={handleVibeGenerateAndRun}
      isVibeLoading={isVibeLoading}
      vibeError={vibeError}
      vibePreview={vibePreview}
      handleApplyVibePreview={handleApplyVibePreview}
      isConfigModalOpen={isConfigModalOpen}
      handleCloseConfigModal={handleCloseConfigModal}
      selectedTest={selectedTest}
      editingTest={editingTest}
      handleConfigSave={handleConfigSave}
      isSaveProtocolOpen={isSaveProtocolOpen}
      saveProtocolSeed={saveProtocolSeed}
      handleSaveProtocol={handleSaveProtocol}
      isProtocolLibraryOpen={isProtocolLibraryOpen}
      savedProtocols={savedProtocols}
      applySavedProtocol={applySavedProtocol}
      setSavedProtocols={setSavedProtocols}
      handleImportProtocol={handleImportProtocol}
      isShortcutsHelpOpen={isShortcutsHelpOpen}
      setIsShortcutsHelpOpen={setIsShortcutsHelpOpen}
    />
  );
};

export default AnalysisDesignLegacy;
