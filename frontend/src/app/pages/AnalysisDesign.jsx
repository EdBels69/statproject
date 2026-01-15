import React, { useCallback, useEffect, useMemo, useState, lazy, Suspense } from 'react';
import {
  ArrowLeftIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';
import { useNavigate, useParams } from 'react-router-dom';
import Button from '../components/ui/Button';
import TestSelectionPanel from '../components/analysis/TestSelectionPanel';
import ProtocolBuilder from '../components/analysis/ProtocolBuilder';
import TestConfigModal from '../components/TestConfigModal';
import AIRecommendationsPanel from '../components/analysis/AIRecommendationsPanel';
import ProtocolTemplateSelector from '../components/analysis/ProtocolTemplateSelector';
import VariableWorkspace from '../components/VariableWorkspace';
import ResearchFlowNav from '../components/ResearchFlowNav';
import SaveProtocolModal, { ProtocolLibraryModal, exportProtocolAsJsonFile } from '../components/SaveProtocolModal';
import KeyboardShortcutsHelp from '../components/KeyboardShortcutsHelp';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useUndoRedo } from '../hooks/useUndoRedo';
import { useTranslation } from '../../hooks/useTranslation';
import { API_URL, getAlphaSetting, getDataset, getDatasets, getScanReport } from '../../lib/api';

const ClusteredHeatmap = lazy(() => import('../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../components/InteractionPlot'));
const VisualizePlot = lazy(() => import('../components/VisualizePlot'));

const PROTOCOL_STORAGE_KEY = 'statwizard_protocols_v1';

function safeString(value) {
  return String(value ?? '').trim();
}

function safeJsonParse(value, fallback) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

function makeId() {
  const fn = globalThis?.crypto?.randomUUID;
  if (typeof fn === 'function') return fn.call(globalThis.crypto);
  return `p_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function VariablePreview({ t, targetVar, groupVar, groupLabel, statsByName }) {
  const payloadTarget = statsByName?.[targetVar] || null;
  const payloadGroup = statsByName?.[groupVar] || null;

  const targetStats = useMemo(() => {
    if (!targetVar || !payloadTarget || typeof payloadTarget !== 'object') return null;
    const total = Number(payloadTarget.total);
    const missing = Number(payloadTarget.missing_count);
    const n = (Number.isFinite(total) ? total : 0) - (Number.isFinite(missing) ? missing : 0);

    const warnings = [];
    if (Number.isFinite(n) && n > 0 && n < 30) warnings.push(`${t('sample_size_short')} n=${n}`);
    if (Number.isFinite(n) && n <= 1) warnings.push(t('no_variation_warning'));
    if (Number.isFinite(missing) && missing > 0) warnings.push(`${t('missing')}: ${missing}`);

    const mean = typeof payloadTarget.mean === 'number' ? payloadTarget.mean : null;
    const min = typeof payloadTarget.min === 'number' ? payloadTarget.min : null;
    const max = typeof payloadTarget.max === 'number' ? payloadTarget.max : null;
    const normalityP = payloadTarget?.normality?.p_value;

    return {
      n: Number.isFinite(n) ? n : null,
      mean,
      min,
      max,
      normalityP: typeof normalityP === 'number' ? normalityP : null,
      warnings,
    };
  }, [payloadTarget, t, targetVar]);

  const groupStats = useMemo(() => {
    if (!groupVar || !payloadGroup || typeof payloadGroup !== 'object') return null;
    const unique = typeof payloadGroup.unique_count === 'number' ? payloadGroup.unique_count : null;
    const missing = typeof payloadGroup.missing_count === 'number' ? payloadGroup.missing_count : null;
    const topValues = Array.isArray(payloadGroup.top_values) ? payloadGroup.top_values : [];

    const warnings = [];
    if (typeof unique === 'number' && unique < 2) warnings.push(t('groups_too_few_warning'));
    if (typeof unique === 'number' && unique > 20) warnings.push(t('groups_too_many_warning'));
    if (typeof missing === 'number' && missing > 0) warnings.push(`${t('missing')}: ${missing}`);

    return {
      unique,
      topValues,
      warnings,
    };
  }, [groupVar, payloadGroup, t]);

  if (!targetStats && !groupStats) return null;

  const warningLine = [...(targetStats?.warnings || []), ...(groupStats?.warnings || [])]
    .filter(Boolean)
    .slice(0, 4);

  return (
    <div className="px-6">
      <div className="max-w-7xl mx-auto">
        <div className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="text-[10px] uppercase tracking-[0.22em] text-[color:var(--text-muted)] font-semibold">
              {t('preview')}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
            {targetStats ? (
              <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--text-muted)] font-semibold">{t('target')}</div>
                <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{targetVar}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--text-secondary)]">
                  {typeof targetStats.n === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">n = </span><span className="font-mono font-semibold text-[color:var(--text-primary)]">{targetStats.n}</span></div>
                  ) : null}
                  {typeof targetStats.mean === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">M = </span><span className="font-mono font-semibold text-[color:var(--text-primary)]">{targetStats.mean.toFixed(2)}</span></div>
                  ) : null}
                  {typeof targetStats.min === 'number' && typeof targetStats.max === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">Range: </span><span className="font-mono">{targetStats.min.toFixed(2)}–{targetStats.max.toFixed(2)}</span></div>
                  ) : null}
                  {typeof targetStats.normalityP === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">{t('normality')} p = </span><span className="font-mono">{targetStats.normalityP < 0.001 ? '<0.001' : targetStats.normalityP.toFixed(3)}</span></div>
                  ) : null}
                </div>
              </div>
            ) : null}

            {groupStats ? (
              <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] p-3">
                <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--text-muted)] font-semibold">{groupLabel}</div>
                <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)] truncate">{groupVar}</div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--text-secondary)]">
                  {typeof groupStats.unique === 'number' ? (
                    <div><span className="text-[color:var(--text-muted)]">{t('groups')} = </span><span className="font-mono font-semibold text-[color:var(--text-primary)]">{groupStats.unique}</span></div>
                  ) : null}
                  {Array.isArray(groupStats.topValues) && groupStats.topValues.length > 0 ? (
                    <div className="min-w-0"><span className="text-[color:var(--text-muted)]">Top: </span><span className="font-mono">{groupStats.topValues.slice(0, 3).map((tv) => tv?.value).filter(Boolean).join(', ')}</span></div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          {warningLine.length > 0 ? (
            <div className="mt-3 text-xs text-[color:var(--text-secondary)]">
              <span className="text-[color:var(--accent)] font-semibold">{t('warnings')}:</span> {warningLine.join(' • ')}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function StepPreviewPanel({ title, steps }) {
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  if (safeSteps.length === 0) return null;

  return (
    <div className="px-6">
      <div className="max-w-7xl mx-auto">
        <div className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
          <div className="px-4 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)]">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--text-muted)]">
              {title}
            </div>
          </div>

          <div className="divide-y divide-[color:var(--border-color)]">
            {safeSteps.map((step, idx) => (
              <div key={`${step.label}_${idx}`} className="px-4 py-3">
                <div className="text-xs text-[color:var(--text-secondary)]">{step.label}</div>
                <div className="mt-1 text-sm text-[color:var(--text-primary)] font-mono">{step.summary}</div>
                {step.warning ? (
                  <div className="mt-1 text-xs text-amber-700">⚠️ {step.warning}</div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function normalizeSavedProtocol(raw) {
  const name = safeString(raw?.name);
  const steps = Array.isArray(raw?.steps) ? raw.steps : [];
  if (!name || steps.length === 0) return null;

  return {
    id: safeString(raw?.id) || makeId(),
    name,
    description: safeString(raw?.description),
    tags: Array.isArray(raw?.tags) ? raw.tags.map(safeString).filter(Boolean) : [],
    created_at: safeString(raw?.created_at) || new Date().toISOString(),
    steps: steps
      .map((s) => ({ method: safeString(s?.method), config: (s?.config && typeof s.config === 'object') ? s.config : {} }))
      .filter((s) => s.method)
  };
}

function loadSavedProtocols() {
  const text = localStorage.getItem(PROTOCOL_STORAGE_KEY);
  const parsed = safeJsonParse(text, []);
  if (!Array.isArray(parsed)) return [];
  return parsed.map(normalizeSavedProtocol).filter(Boolean);
}

function saveSavedProtocols(protocols) {
  localStorage.setItem(PROTOCOL_STORAGE_KEY, JSON.stringify(protocols));
}

const AnalysisDesign = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id: datasetIdFromRoute } = useParams();

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
  const [isSaveProtocolOpen, setIsSaveProtocolOpen] = useState(false);
  const [isProtocolLibraryOpen, setIsProtocolLibraryOpen] = useState(false);
  const [saveProtocolSeed, setSaveProtocolSeed] = useState(0);
  const [isShortcutsHelpOpen, setIsShortcutsHelpOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [editingTest, setEditingTest] = useState(null);
  const [showAI, setShowAI] = useState(false);
  const [showVariables, setShowVariables] = useState(false);
  const [selectedVars, setSelectedVars] = useState([]);
  const [workspaceRoles, setWorkspaceRoles] = useState({ target: '', group: '', covariates: [] });
  const [aiRecommendations, setAIRecommendations] = useState([]);
  const [isAIAnalyzing, setIsAIAnalyzing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [results, setResults] = useState(null);

  const chartFallback = useMemo(() => (
    <div className="animate-pulse h-[360px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-center text-[color:var(--text-muted)] text-xs">
      {t('loading')}
    </div>
  ), [t]);
  const [isResultsOpen, setIsResultsOpen] = useState(false);

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

  const totalRows = useMemo(() => {
    const n = scanReport?.missing_report?.total_rows;
    return typeof n === 'number' ? n : 0;
  }, [scanReport]);

  useEffect(() => {
    saveSavedProtocols(savedProtocols);
  }, [savedProtocols]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setDatasetError(null);

      if (!datasetIdFromRoute) {
        setDatasetId(null);
        setDatasetName(null);
        setColumns([]);
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
        const response = await fetch(`${API_URL}/v2/analysis/templates`);
        if (!response.ok) {
          const text = await response.text().catch(() => '');
          throw new Error(text || 'Failed to load templates');
        }
        const data = await response.json();
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
      setProtocol(prev =>
        prev.map(test =>
          test.id === editingTest.id
            ? { ...test, config: { ...test.config, ...config } }
            : test
        )
      );
    } else {
      const newTest = {
        id: `test_${Date.now()}`,
        method: selectedTest.id,
        name: selectedTest.name,
        config: config
      };
      setProtocol(prev => [...prev, newTest]);
    }
    setIsConfigModalOpen(false);
    setSelectedTest(null);
    setEditingTest(null);
  };

  const handleRemoveTest = (testId) => {
    setProtocol(prev => prev.filter(test => test.id !== testId));
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

  const handleAISuggest = async () => {
    if (protocol.length === 0) return;

    setIsAIAnalyzing(true);
    setShowAI(true);

    try {
      const response = await fetch(`${API_URL}/v2/ai/suggest-tests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: datasetIdResolved,
          protocol: protocol.map((test) => ({
            id: test.id,
            method: test.method,
            config: test.config
          }))
        })
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        throw new Error(text || 'AI suggestion failed');
      }

      const data = await response.json();
      setAIRecommendations(Array.isArray(data?.recommendations) ? data.recommendations : []);
    } catch (error) {
      console.error('AI suggestion failed:', error);
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
      config: recommendation.test.config || {}
    };
    setProtocol(prev => [...prev, newTest]);
  };

  const handleExecuteProtocol = useCallback(async (protocolToExecute) => {
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
      const response = await fetch(`${API_URL}/v2/analysis/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: datasetIdResolved,
          alpha: getAlphaSetting(),
          protocol: protocolToExecute.map((test) => {
            const normalized = normalizeStepForBackend(test);
            return {
              id: normalized.id,
              method: normalized.method,
              config: normalized.config
            };
          })
        })
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        const err = text || 'Protocol execution failed';
        setResults({
          status: 'error',
          completed_steps: 0,
          total_steps: protocolToExecute.length,
          errors: [{ method: 'protocol', error: err }],
          results: []
        });
        setIsResultsOpen(true);
        return;
      }

      const data = await response.json();
      setResults(data);
      setIsResultsOpen(true);
    } catch (error) {
      console.error('Protocol execution failed:', error);
    } finally {
      setIsExecuting(false);
    }
  }, [datasetIdResolved]);

  const columnNames = Array.isArray(columns)
    ? columns
      .map((c) => {
        if (!c) return null;
        if (typeof c === 'string') return c;
        return c.name || c.column || c.id || null;
      })
      .filter(Boolean)
    : [];

  const selectedTemplate = templates.find((tpl) => tpl.id === selectedTemplateId) || null;

  const formatMethodName = useCallback((methodId) => {
    if (!methodId) return '';
    if (methodId === 'mixed_effects') return t('mixed_effects');
    if (methodId === 'clustered_correlation') return t('clustered_correlation');
    return String(methodId).replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  }, [t]);

  const humanizeError = (raw) => {
    const text = String(raw || '').trim();
    if (!text) {
      return {
        title: 'Неизвестная ошибка',
        details: '',
        actions: ['Попробуйте запустить анализ ещё раз.', 'Если ошибка повторяется — проверьте выбранные переменные.']
      };
    }

    const patterns = [
      {
        re: /could not convert string to float|cannot convert|invalid literal for int/i,
        title: 'В данных есть текст там, где ожидаются числа',
        actions: ['Выберите числовую переменную для Target.', 'Преобразуйте колонку в числовую на шаге подготовки данных.']
      },
      {
        re: /KeyError|column.*not found|not in index/i,
        title: 'Колонка не найдена в данных',
        actions: ['Проверьте, что колонка существует и не была переименована.', 'Откройте «Variables» и выберите переменные заново.']
      },
      {
        re: /singular matrix|LinAlgError|nan.*infs?|perfect separation/i,
        title: 'Модель не может быть оценена на этих данных',
        actions: ['Проверьте, что в данных есть вариативность (нет константных колонок).', 'Уберите лишние ковариаты или коллинеарные признаки.']
      },
      {
        re: /not enough data|at least|insufficient|too few/i,
        title: 'Недостаточно данных для выбранного метода',
        actions: ['Проверьте размер выборки в группах.', 'Упростите модель или выберите другой тест.']
      },
      {
        re: /shapiro|normality|levene|homogeneity|assumption/i,
        title: 'Нарушены статистические предпосылки',
        actions: ['Используйте непараметрический тест или трансформации.', 'Проверьте выбросы и пропуски.']
      }
    ];

    const hit = patterns.find((p) => p.re.test(text));
    if (!hit) {
      return {
        title: 'Ошибка выполнения анализа',
        details: text,
        actions: ['Проверьте настройки теста и выбранные переменные.', 'Если не помогает — попробуйте другой тест или шаблон.']
      };
    }

    return {
      title: hit.title,
      details: text,
      actions: hit.actions
    };
  };

  const templateGoal = selectedTemplate?.goal;
  const templateSecondaryKey = templateGoal === 'relationship' ? 'predictor' : 'group';

  const applySavedProtocol = (p) => {
    const normalized = normalizeSavedProtocol(p);
    if (!normalized) return;

    const steps = Array.isArray(normalized.steps) ? normalized.steps : [];
    setProtocol(
      steps.map((step, idx) => ({
        id: step?.id || `saved_${Date.now()}_${idx}`,
        method: step?.method,
        name: formatMethodName(step?.method),
        config: step?.config || {}
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

  const roleByName = useMemo(() => {
    const map = {};
    if (workspaceRoles?.target) map[workspaceRoles.target] = 'target';
    if (workspaceRoles?.group) map[workspaceRoles.group] = 'group';
    if (Array.isArray(workspaceRoles?.covariates)) {
      workspaceRoles.covariates.forEach((n) => {
        if (n) map[n] = 'covariate';
      });
    }
    return map;
  }, [workspaceRoles]);

  const flowStepData = useMemo(() => {
    const dataLoaded = Boolean(datasetIdResolved) && Array.isArray(columns) && columns.length > 0;
    const variablesSet = Boolean(workspaceRoles?.target) && Boolean(workspaceRoles?.group);

    const analysisRunning = Boolean(isExecuting);
    const analysisDone = Boolean(results) && results?.status !== 'error';
    const resultsReady = Boolean(results) && results?.status !== 'error';

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
      analysisRunning,
      analysisDone,
      resultsReady,
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
      const response = await fetch(`${API_URL}/v2/analysis/design`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: datasetIdResolved,
          goal,
          template_id: selectedTemplate.id,
          variables
        })
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        throw new Error(text || 'Template design failed');
      }

      const data = await response.json();
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

  const renderStepResult = (step) => {
    const payload = step?.results;
    const method = step?.method;

    if (method === 'mixed_effects') {
      return (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
            <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('interaction')}</div>
            <div className="mt-2 flex items-baseline gap-3">
              <div className="text-2xl font-black text-[color:var(--text-primary)] font-mono">
                {typeof payload?.interaction_p_value === 'number'
                  ? payload.interaction_p_value < 0.001
                    ? '< 0.001'
                    : payload.interaction_p_value.toFixed(4)
                  : t('not_available_short')}
              </div>
              <div className="text-xs text-[color:var(--text-secondary)]">{t('time_group_p_value')}</div>
            </div>
          </div>

          <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
            <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('interaction_plot')}</div>
            <div className="mt-3 overflow-x-auto">
              <Suspense fallback={chartFallback}>
                <InteractionPlot data={payload} width={640} height={380} />
              </Suspense>
            </div>
          </div>
        </div>
      );
    }

    if (method === 'clustered_correlation') {
      return (
        <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
          <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('clustered_heatmap')}</div>
          <div className="mt-3 overflow-x-auto">
            <Suspense fallback={chartFallback}>
              <ClusteredHeatmap data={payload} width={760} height={560} />
            </Suspense>
          </div>
        </div>
      );
    }

    if (Array.isArray(payload?.plot_data) && payload.plot_data.length > 0) {
      const comparisons = payload?.comparisons || payload?.pairwise_comparisons || payload?.plot_comparisons;
      return (
        <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4 overflow-hidden">
          <div className="text-xs font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('plot')}</div>
          <div className="mt-3">
            <Suspense fallback={chartFallback}>
              <VisualizePlot data={payload.plot_data} stats={payload.plot_stats} groups={payload.groups} comparisons={comparisons} />
            </Suspense>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('p_value')}</div>
            <div className="mt-1 font-mono text-sm text-[color:var(--text-primary)]">
              {typeof payload?.p_value === 'number'
                ? payload.p_value < 0.001
                  ? '< 0.001'
                  : payload.p_value.toFixed(4)
                : t('not_available_short')}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('statistic')}</div>
            <div className="mt-1 font-mono text-sm text-[color:var(--text-primary)]">
              {typeof payload?.stat_value === 'number' ? payload.stat_value.toFixed(3) : t('not_available_short')}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('statistical_significance')}</div>
            <div className={`mt-1 text-sm font-semibold ${payload?.significant ? 'text-[color:var(--accent)]' : 'text-[color:var(--text-secondary)]'}`}>
              {payload?.significant ? t('yes') : t('no')}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{t('method')}</div>
            <div className="mt-1 text-sm text-[color:var(--text-secondary)] truncate">
              {formatMethodName(method)}
            </div>
          </div>
        </div>
      </div>
    );
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
  }, [handleCloseConfigModal, isConfigModalOpen, isProtocolLibraryOpen, isSaveProtocolOpen, isShortcutsHelpOpen]);

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

  const canRun = Boolean(datasetIdResolved) && !datasetLoading && !datasetError;

  const onBack = () => {
    navigate('/datasets');
  };

  const datasetPicker = (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-8">
          <ResearchFlowNav active="data" />
        </div>
        <div className="mb-8">
          <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('analysis_protocol')}</div>
          <h1 className="mt-3 text-3xl font-black text-[color:var(--text-primary)] leading-tight">{t('test_selection')}</h1>
          <p className="mt-2 text-sm text-[color:var(--text-secondary)] max-w-2xl">{t('select_tests_tooltip')}</p>
        </div>

        {datasetsError && (
          <div className="mb-6 p-4 bg-[color:var(--white)] border border-[color:var(--black)] text-[color:var(--text-primary)] rounded-[2px] text-sm">{datasetsError}</div>
        )}

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
                    onClick={() => navigate(`/design/${ds.id}`)}
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

  if (!datasetIdFromRoute) {
    return datasetPicker;
  }

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
            <button type="button" onClick={onBack} className="text-[color:var(--text-primary)] font-semibold underline underline-offset-4">{t('back')}</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="h-screen flex flex-col bg-[color:var(--bg-secondary)]">
        <div className="bg-[color:var(--white)] border-b border-[color:var(--border-color)] px-6 py-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={onBack}
                  className="h-9 w-9 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-black hover:text-black active:scale-[0.98]"
                  type="button"
                  aria-label={t('back')}
                >
                  <ArrowLeftIcon className="w-5 h-5" />
                </button>
                <div>
                  <h1 className="text-xl font-bold text-[color:var(--text-primary)]">
                    StatWizard
                  </h1>
                  {datasetName && (
                    <p className="text-sm text-[color:var(--text-secondary)] mt-1">
                      {datasetName}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  onClick={() => setShowVariables(!showVariables)}
                  disabled={!columns.length}
                  variant={showVariables ? 'secondary' : 'ghost'}
                  className="gap-2"
                  type="button"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                  </svg>
                  Variables ({columns.length})
                </Button>
                <Button
                  onClick={() => setShowAI(!showAI)}
                  disabled={!canRun}
                  variant={showAI ? 'primary' : 'ghost'}
                  className="gap-2"
                  type="button"
                >
                  <SparklesIcon className="w-4 h-4" />
                  {t('ai_assistant')}
                </Button>
              </div>
            </div>

            <ResearchFlowNav active="variables" datasetId={datasetIdResolved} className="mt-3" stepData={flowStepData} />
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          <div className="w-96 flex-shrink-0">
            <TestSelectionPanel
              onTestSelect={handleTestSelect}
              datasetId={datasetIdResolved}
              suggestedConfig={workspaceRoles}
              disabled={isExecuting}
            />
          </div>

          <div className="flex-1 flex flex-col overflow-hidden">
            <ProtocolTemplateSelector
              templates={templates}
              templatesLoading={templatesLoading}
              templatesError={templatesError}
              selectedTemplateId={selectedTemplateId}
              onSelectedTemplateIdChange={(nextId) => {
                setSelectedTemplateId(nextId);
                setTemplateVars((v) => ({ ...v, group: '', predictor: '' }));
              }}
              selectedTemplate={selectedTemplate}
              templateVars={templateVars}
              onTemplateVarsChange={setTemplateVars}
              columnNames={columnNames}
              columns={columns}
              columnStatsByName={columnStatsByName}
              canApplyTemplate={canApplyTemplate}
              onApplyTemplate={handleApplyTemplate}
              disabled={isExecuting}
            />

            {(workspaceRoles?.target || workspaceRoles?.group) ? (
              <VariablePreview
                t={t}
                targetVar={workspaceRoles?.target}
                groupVar={workspaceRoles?.group}
                groupLabel={templateSecondaryKey === 'predictor' ? t('predictor') : t('group')}
                statsByName={columnStatsByName}
              />
            ) : null}

            <StepPreviewPanel title="📊 PREVIEW" steps={previewSteps} />

            {showAI && (
              <div className="flex-shrink-0 p-4 border-b border-[color:var(--border-color)]">
                <AIRecommendationsPanel
                  datasetId={datasetId}
                  columns={columns}
                  recommendations={aiRecommendations}
                  onAddRecommendation={handleAddRecommendation}
                  onClose={() => setShowAI(false)}
                  isAnalyzing={isAIAnalyzing}
                />
              </div>
            )}

            <div className="flex-1 overflow-hidden flex flex-col">
              <div className="flex-1 overflow-hidden">
                <ProtocolBuilder
                  protocol={protocol}
                  datasetName={datasetName}
                  onRemoveTest={handleRemoveTest}
                  onEditTest={handleEditTest}
                  onMoveTest={handleMoveTest}
                  onExecuteProtocol={handleExecuteProtocol}
                  onAISuggest={handleAISuggest}
                  onSaveProtocol={() => {
                    if (protocol.length === 0) return;
                    setSaveProtocolSeed(Date.now());
                    setIsSaveProtocolOpen(true);
                  }}
                  onOpenProtocols={() => setIsProtocolLibraryOpen(true)}
                  onUndo={undoProtocol}
                  onRedo={redoProtocol}
                  canUndo={canUndo}
                  canRedo={canRedo}
                  isExecuting={isExecuting}
                  isAIAnalyzing={isAIAnalyzing}
                />
              </div>
            </div>

            {/* Variable Workspace Right Sidebar */}
            {showVariables && (
              <div className="w-80 flex-shrink-0 border-l border-[color:var(--border-color)]">
                <VariableWorkspace
                  columns={columns}
                  columnStatsByName={columnStatsByName}
                  roleByName={roleByName}
                  roles={workspaceRoles}
                  secondaryRoleLabel={templateSecondaryKey === 'predictor' ? t('predictor') : t('group')}
                  onRolesChange={(next) => {
                    setWorkspaceRoles(next);
                    setTemplateVars((prev) => {
                      const out = { ...prev, target: next.target || prev.target };
                      if (templateSecondaryKey === 'predictor') out.predictor = next.group || prev.predictor;
                      else out.group = next.group || prev.group;
                      return out;
                    });
                  }}
                  selectedVariables={selectedVars}
                  onSelectionChange={setSelectedVars}
                  onVariableClick={(name) => {
                    // Auto-fill template vars
                    if (!templateVars.target) {
                      setTemplateVars(prev => ({ ...prev, target: name }));
                    } else if (!templateVars.group && !templateVars.predictor) {
                      setTemplateVars(prev => ({ ...prev, group: name }));
                    }
                  }}
                  mode="multi"
                  showStats={true}
                />
              </div>
            )}
            {results && (
              <div className={`border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex-shrink-0 ${isResultsOpen ? 'h-[46vh]' : 'h-12'} transition-[height] duration-200 overflow-hidden`}>
                <div className="h-12 px-4 flex items-center justify-between bg-[color:var(--white)] border-b border-[color:var(--border-color)]">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase truncate">
                      {t('analysis_results')}
                    </div>
                    <div className="text-xs text-[color:var(--text-secondary)] truncate">
                      {results?.status || t('not_available_short')} · {results?.completed_steps ?? 0}/{results?.total_steps ?? 0}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsResultsOpen((v) => !v)}
                    className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-black"
                  >
                    {isResultsOpen ? t('hide_results') : t('view_results')}
                  </button>
                </div>

                {isResultsOpen && (
                  <div className="h-[calc(46vh-3rem)] overflow-y-auto p-4 space-y-4" aria-live="polite">
                    {Array.isArray(results?.errors) && results.errors.length > 0 && (
                      <div className="bg-[color:var(--white)] border border-[color:var(--black)] text-[color:var(--text-primary)] rounded-[2px] p-4 text-sm">
                        <div className="text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--accent)]">{t('errors')}</div>
                        <div className="mt-2 space-y-2">
                          {results.errors.map((e, idx) => {
                            const h = humanizeError(e?.error);
                            return (
                              <div key={`${e?.step_id || 'step'}_${idx}`} className="rounded-[2px] bg-[color:var(--bg-tertiary)] border border-[color:var(--border-color)] p-3">
                                <div className="flex items-baseline justify-between gap-3">
                                  <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">
                                    {e?.method || t('unknown')}
                                  </div>
                                  <div className="text-[10px] text-[color:var(--text-secondary)] font-mono truncate">
                                    {h.details ? h.details : (e?.error || t('unknown_error'))}
                                  </div>
                                </div>
                                <div className="mt-2 text-sm font-semibold text-[color:var(--text-primary)]">
                                  {h.title}
                                </div>
                                {Array.isArray(h.actions) && h.actions.length > 0 && (
                                  <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                                    <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">Что делать:</div>
                                    <ul className="mt-1 list-disc pl-4 space-y-0.5">
                                      {h.actions.map((a, i) => (
                                        <li key={`${idx}_a_${i}`}>{a}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {Array.isArray(results?.results) && results.results.length > 0 ? (
                      results.results.map((step, idx) => (
                        <div key={step?.step_id || `${step?.method || 'step'}_${idx}`} className="space-y-3">
                          <div className="flex items-baseline justify-between">
                            <div className="text-sm font-bold text-[color:var(--text-primary)] truncate">
                              {formatMethodName(step?.method)}
                            </div>
                            <div className="text-xs text-[color:var(--text-secondary)] font-mono">
                              {step?.status || t('not_available_short')}
                            </div>
                          </div>
                          {renderStepResult(step)}
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-[color:var(--text-secondary)]">{t('no_results_yet')}</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <TestConfigModal
        isOpen={isConfigModalOpen}
        onClose={handleCloseConfigModal}
        method={selectedTest?.id}
        initialConfig={editingTest?.config || {}}
        onConfigSave={handleConfigSave}
        columns={columns}
        suggestedConfig={workspaceRoles}
        datasetId={datasetIdResolved}
      />

      <SaveProtocolModal
        key={saveProtocolSeed}
        isOpen={isSaveProtocolOpen}
        onClose={() => setIsSaveProtocolOpen(false)}
        onSave={handleSaveProtocol}
        defaultName={datasetName ? `Протокол: ${datasetName}` : 'Мой протокол'}
        defaultDescription=""
      />

      <ProtocolLibraryModal
        isOpen={isProtocolLibraryOpen}
        onClose={() => setIsProtocolLibraryOpen(false)}
        protocols={savedProtocols}
        onLoad={applySavedProtocol}
        onDelete={(id) => {
          setSavedProtocols((prev) => (Array.isArray(prev) ? prev.filter((p) => p.id !== id) : []));
        }}
        onImport={handleImportProtocol}
        onExport={(p) => exportProtocolAsJsonFile(p)}
      />

      <KeyboardShortcutsHelp
        isOpen={isShortcutsHelpOpen}
        onClose={() => setIsShortcutsHelpOpen(false)}
      />
    </>
  );
};

export default AnalysisDesign;
