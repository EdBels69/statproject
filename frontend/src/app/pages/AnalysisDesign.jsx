import React, { useCallback, useEffect, useMemo, useRef, useState, lazy, Suspense } from 'react';
import {
  ArrowLeftIcon,
} from '@heroicons/react/24/outline';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import Button from '../components/ui/Button';
import TestSelectionPanel from '../components/analysis/TestSelectionPanel';
import ProtocolBuilder from '../components/analysis/ProtocolBuilder';
import TestConfigModal from '../components/TestConfigModal';
import AISuggestionsPane from '../components/analysis/AISuggestionsPane';
import ProtocolTemplateSelector from '../components/analysis/ProtocolTemplateSelector';
import ResearchFlowNav from '../components/ResearchFlowNav';
import VariableWorkspace from '../components/VariableWorkspace';
import SaveProtocolModal, { ProtocolLibraryModal, exportProtocolAsJsonFile } from '../components/SaveProtocolModal';
import KeyboardShortcutsHelp from '../components/KeyboardShortcutsHelp';
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts';
import { useUndoRedo } from '../hooks/useUndoRedo';
import { useTranslation } from '../../hooks/useTranslation';
import {
  getAISuggestions,
  getAlphaSetting,
  getDataset,
  listDatasetColumns,
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

const ClusteredHeatmap = lazy(() => import('../components/ClusteredHeatmap'));
const InteractionPlot = lazy(() => import('../components/InteractionPlot'));
const VisualizePlot = lazy(() => import('../components/VisualizePlot'));

const PROTOCOL_STORAGE_KEY = 'clinimetria_protocols_v1';
const GLOBAL_SETTINGS_STORAGE_KEY = 'clinimetria_global_settings_v1';

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

function dedupeNames(values) {
  const out = [];
  for (const item of (Array.isArray(values) ? values : [])) {
    const name = String(item || '').trim();
    if (!name) continue;
    if (!out.includes(name)) out.push(name);
  }
  return out;
}

function normalizeWorkspaceRoles(next) {
  if (!next || typeof next !== 'object') {
    return { target: '', group: '', covariates: [] };
  }

  return {
    target: safeString(next?.target || ''),
    group: safeString(next?.group || ''),
    covariates: Array.isArray(next?.covariates) ? next.covariates.filter(Boolean) : [],
  };
}

function buildRoleByName(roles) {
  const out = {};
  if (roles?.target) out[String(roles.target)] = 'target';
  if (roles?.group) out[String(roles.group)] = 'group';

  const covs = Array.isArray(roles?.covariates) ? roles.covariates : [];
  covs.forEach((n) => {
    const name = safeString(n || '');
    if (!name) return;
    out[name] = 'covariate';
  });

  return out;
}

function mergeTemplateVarsFromRoles(prev, roles, templateSecondaryKey) {
  const base = prev && typeof prev === 'object' ? prev : { target: '', group: '', predictor: '' };
  const mapped = {
    ...base,
    target: roles.target,
  };
  if (templateSecondaryKey === 'predictor') mapped.predictor = roles.group;
  else mapped.group = roles.group;
  return mapped;
}

function makeId() {
  const fn = globalThis?.crypto?.randomUUID;
  if (typeof fn === 'function') return fn.call(globalThis.crypto);
  return `p_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function normalizeDesignReviewStatus(payload) {
  const confirmed = Boolean(payload?.confirmed);
  const confirmedAt = confirmed && typeof payload?.confirmed_at === 'string'
    ? payload.confirmed_at
    : null;
  return { confirmed, confirmedAt };
}

function buildDesignReviewGlobals({ source, confirmed, confirmedAt, extra }) {
  const base = (extra && typeof extra === 'object') ? { ...extra } : {};
  base.design_confirmed = Boolean(confirmed);
  if (base.design_confirmed) {
    base.design_review_timestamp = base.design_review_timestamp || confirmedAt || new Date().toISOString();
  } else {
    delete base.design_review_timestamp;
  }
  if (!base.source) base.source = source;
  return base;
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
                  <div className="mt-1 text-xs text-amber-700"><span className="font-semibold">!</span> {step.warning}</div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function GlobalSettingsPanel({ value, onChange }) {
  const v = value && typeof value === 'object' ? value : normalizeGlobalSettings(null);

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
      <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)]">
        <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Глобальные настройки</div>
      </div>
      <div className="p-3 grid grid-cols-1 gap-3">
        <label className="grid gap-1">
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Альтернатива</div>
          <select
            value={v.alternative}
            onChange={(e) => onChange?.({ ...v, alternative: e.target.value })}
            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
          >
            <option value="two-sided">Двусторонняя</option>
            <option value="less">Односторонняя: меньше</option>
            <option value="greater">Односторонняя: больше</option>
          </select>
        </label>

        <label className="grid gap-1">
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Пост-хок</div>
          <select
            value={v.post_hoc}
            onChange={(e) => onChange?.({ ...v, post_hoc: e.target.value })}
            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
          >
            <option value="none">Нет</option>
            <option value="tukey">Tukey</option>
            <option value="dunn">Dunn</option>
          </select>
        </label>

        <label className="grid gap-1">
          <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">Поправка</div>
          <select
            value={v.post_hoc_correction}
            onChange={(e) => onChange?.({ ...v, post_hoc_correction: e.target.value })}
            className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm"
          >
            <option value="none">Нет</option>
            <option value="bh">BH (FDR)</option>
            <option value="bky">BKY</option>
          </select>
        </label>
      </div>
    </div>
  );
}

function VibeDesignModal({
  isOpen,
  onClose,
  value,
  onValueChange,
  globalSettings,
  onGlobalSettingsChange,
  onGenerate,
  onGenerateAndRun,
  isLoading,
  error,
  preview,
  onApply,
}) {
  if (!isOpen) return null;

  const steps = Array.isArray(preview?.protocol) ? preview.protocol : [];
  const notes = Array.isArray(preview?.notes) ? preview.notes : [];

  return (
    <div className="fixed inset-0 z-[70]">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 p-4 md:p-8 flex items-start justify-center overflow-y-auto">
        <div className="w-full max-w-4xl bg-[color:var(--white)] border border-black rounded-[2px] shadow-[0_30px_80px_rgba(0,0,0,0.45)]">
          <div className="px-4 py-3 border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Vibe</div>
              <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">Текст → протокол</div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold hover:border-black"
            >
              Закрыть
            </button>
          </div>

          <div className="p-4 grid grid-cols-1 lg:grid-cols-[1.2fr,0.8fr] gap-4">
            <div className="space-y-3">
              <div className="bg-[color:var(--bg-secondary)] border border-[color:var(--border-color)] rounded-[2px] p-3">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Описание</div>
                <textarea
                  value={value}
                  onChange={(e) => onValueChange?.(e.target.value)}
                  className="mt-2 w-full min-h-[180px] p-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-sm leading-relaxed"
                  placeholder="Вставь сюда абзац из протокола/статьи: дизайн, группы, исходы, ковариаты, время…"
                />
                {error ? (
                  <div className="mt-2 text-xs text-[color:var(--accent)] font-semibold">{error}</div>
                ) : null}
                <div className="mt-3 flex items-center justify-between gap-2">
                  <div className="text-xs text-[color:var(--text-secondary)]">ИИ вернёт черновик шагов; ты редактируешь как обычно.</div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      onClick={onGenerateAndRun}
                      disabled={isLoading || String(value || '').trim().length < 12}
                      variant="ghost"
                      size="sm"
                    >
                      {isLoading ? 'Собираю…' : 'Сразу отчёт'}
                    </Button>
                    <Button
                      type="button"
                      onClick={onGenerate}
                      disabled={isLoading || String(value || '').trim().length < 12}
                      variant="primary"
                      size="sm"
                    >
                      {isLoading ? 'Собираю…' : 'Собрать протокол'}
                    </Button>
                  </div>
                </div>
              </div>

              {steps.length > 0 ? (
                <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                  <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-2">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Превью</div>
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{steps.length} шаг(ов)</div>
                  </div>
                  <div className="divide-y divide-[color:var(--border-color)]">
                    {steps.slice(0, 20).map((s, idx) => (
                      <div key={`${s?.id || idx}`} className="px-3 py-2">
                        <div className="text-xs text-[color:var(--text-secondary)]">{String(s?.name || s?.method || '').trim() || `Шаг ${idx + 1}`}</div>
                        <div className="mt-1 text-xs font-mono text-[color:var(--text-primary)]">{String(s?.method || '')}</div>
                      </div>
                    ))}
                  </div>
                  <div className="p-3 border-t border-[color:var(--border-color)]">
                    <Button type="button" onClick={onApply} variant="ghost" className="w-full" disabled={steps.length === 0}>
                      Применить в конструктор
                    </Button>
                  </div>
                </div>
              ) : null}

              {notes.length > 0 ? (
                <div className="text-xs text-[color:var(--text-secondary)]">
                  {notes.slice(0, 4).map((n, i) => (
                    <div key={i}>{String(n)}</div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="space-y-3">
              <GlobalSettingsPanel value={globalSettings} onChange={onGlobalSettingsChange} />
            </div>
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

function normalizeGlobalSettings(raw) {
  const alternative = raw?.alternative;
  const postH = raw?.post_hoc;
  const corr = raw?.post_hoc_correction;

  const altOk = alternative === 'two-sided' || alternative === 'less' || alternative === 'greater' ? alternative : 'two-sided';
  const postOk = postH === 'tukey' || postH === 'dunn' || postH === 'none' ? postH : 'none';
  const corrOk = corr === 'bh' || corr === 'bky' || corr === 'none' ? corr : 'none';

  return {
    alternative: altOk,
    post_hoc: postOk,
    post_hoc_correction: corrOk,
  };
}

function loadGlobalSettings() {
  const text = localStorage.getItem(GLOBAL_SETTINGS_STORAGE_KEY);
  const parsed = safeJsonParse(text, null);
  return normalizeGlobalSettings(parsed);
}

function saveGlobalSettings(value) {
  localStorage.setItem(GLOBAL_SETTINGS_STORAGE_KEY, JSON.stringify(normalizeGlobalSettings(value)));
}

function saveSavedProtocols(protocols) {
  localStorage.setItem(PROTOCOL_STORAGE_KEY, JSON.stringify(protocols));
}

function baseKey(raw) {
  const s = String(raw || '').trim();
  const stripped = s
    .replace(/\s+/g, ' ')
    .replace(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?\d+)$/i, '')
    .replace(/[_\-\s]+$/g, '')
    .trim();
  return stripped || s;
}

function timeIndex(raw) {
  const s = String(raw || '').trim();
  const m = s.match(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?)(\d+)$/i);
  if (!m) return null;
  const n = Number.parseInt(m[1], 10);
  return Number.isFinite(n) ? n : null;
}

function MassDynamicsModal({
  isOpen,
  onClose,
  columns,
  statsByName,
  defaultGroupCol,
  defaultSubjectCol,
  formatMethodName,
  onAppendSteps,
}) {
  const normalizedCols = useMemo(() => {
    const list = Array.isArray(columns) ? columns : [];
    return list
      .map((c) => {
        if (typeof c === 'string') return { name: c, type: '' };
        return { name: String(c?.name || ''), type: String(c?.type || '') };
      })
      .filter((c) => c.name);
  }, [columns]);

  const [method, setMethod] = useState(() => 'rm_anova');
  const [groupCol, setGroupCol] = useState(() => defaultGroupCol || '');
  const [groupValues, setGroupValues] = useState(() => []);
  const [subjectCol, setSubjectCol] = useState(() => defaultSubjectCol || '');
  const [timeMin, setTimeMin] = useState(() => '1');
  const [timeMax, setTimeMax] = useState(() => '6');

  const groupColOptions = useMemo(() => {
    return normalizedCols
      .filter((c) => c.type === 'categorical' || c.type === 'text' || c.type === 'datetime' || !c.type)
      .map((c) => c.name);
  }, [normalizedCols]);

  const subjectColOptions = useMemo(() => {
    const names = normalizedCols.map((c) => c.name);
    const byHeuristic = names.filter((n) => /(^id$|_id$|\bid\b)/i.test(n));
    return byHeuristic.length > 0 ? byHeuristic : names;
  }, [normalizedCols]);

  const groupValueOptions = useMemo(() => {
    if (!groupCol) return [];
    const payload = statsByName?.[groupCol];
    if (!payload || typeof payload !== 'object') return [];
    const cats = Array.isArray(payload.categories) ? payload.categories : [];
    if (cats.length > 0) return cats;
    const top = Array.isArray(payload.top_values) ? payload.top_values : [];
    return top.map((tv) => String(tv?.value ?? '')).filter(Boolean);
  }, [groupCol, statsByName]);

  const numericCandidates = useMemo(() => {
    return normalizedCols
      .filter((c) => c.type === 'numeric' || !c.type)
      .map((c) => c.name);
  }, [normalizedCols]);

  const minNeeded = method === 'friedman' ? 3 : 2;

  const groupedByBase = useMemo(() => {
    const groups = new Map();
    for (const n of numericCandidates) {
      const k = baseKey(n);
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(n);
    }
    const minN = Number.parseInt(timeMin, 10);
    const maxN = Number.parseInt(timeMax, 10);
    const hasMin = Number.isFinite(minN);
    const hasMax = Number.isFinite(maxN);

    const out = [];
    for (const [k, names] of groups.entries()) {
      const sorted = [...names].sort((a, b) => {
        const ia = timeIndex(a);
        const ib = timeIndex(b);
        if (ia == null && ib == null) return String(a).localeCompare(String(b), 'ru');
        if (ia == null) return 1;
        if (ib == null) return -1;
        return ia - ib;
      });

      const inRange = sorted.filter((n) => {
        const idx = timeIndex(n);
        if (idx == null) return !(hasMin || hasMax);
        if (hasMin && idx < minN) return false;
        if (hasMax && idx > maxN) return false;
        return true;
      });

      const effective = inRange.length >= minNeeded ? inRange : sorted;
      if (effective.length < minNeeded) continue;

      out.push({ key: k, cols: effective });
    }

    out.sort((a, b) => a.key.localeCompare(b.key, 'ru'));
    return out;
  }, [minNeeded, numericCandidates, timeMax, timeMin]);

  const stepPreview = useMemo(() => {
    const bases = groupedByBase.length;
    const groupCount = groupValues.length > 0 ? groupValues.length : (groupCol ? 1 : 1);
    const steps = bases * groupCount;
    return { bases, steps };
  }, [groupCol, groupValues.length, groupedByBase.length]);

  const canGenerate = groupedByBase.length > 0
    && (method !== 'rm_anova' || Boolean(subjectCol));

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Массовая динамика"
      aria-hidden={!isOpen}
      onMouseDown={(e) => {
        if (!isOpen) return;
        if (e.target === e.currentTarget) onClose?.();
      }}
      onKeyDown={(e) => {
        if (!isOpen) return;
        if (e.key === 'Escape') {
          e.stopPropagation();
          onClose?.();
        }
      }}
    >
      <div className={`w-full max-w-2xl bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}>
        <div className="flex items-start justify-between gap-4 px-5 py-4 border-b border-[color:var(--border-color)]">
          <div className="min-w-0">
            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Конструктор</div>
            <div className="mt-1 text-lg font-bold text-[color:var(--text-primary)] truncate">Массовая динамика</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]"
            aria-label="Закрыть"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Метод</label>
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="rm_anova">{formatMethodName?.('rm_anova') || 'RM ANOVA'}</option>
                <option value="friedman">{formatMethodName?.('friedman') || 'Friedman'}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Субъект (ID){method === 'rm_anova' ? '' : ' (опц.)'}</label>
              <select
                value={subjectCol}
                onChange={(e) => setSubjectCol(e.target.value)}
                disabled={method !== 'rm_anova'}
                className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)] disabled:bg-[color:var(--bg-secondary)]"
              >
                <option value="">—</option>
                {subjectColOptions.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
              {method === 'rm_anova' && !subjectCol ? (
                <div className="mt-1 text-xs text-[color:var(--accent)]">Нужен ID для rm_anova</div>
              ) : null}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Группа (фильтр)</label>
              <select
                value={groupCol}
                onChange={(e) => {
                  setGroupCol(e.target.value);
                  setGroupValues([]);
                }}
                className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
              >
                <option value="">—</option>
                {groupColOptions.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">Точки от</label>
                <input
                  value={timeMin}
                  onChange={(e) => setTimeMin(e.target.value)}
                  inputMode="numeric"
                  className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[color:var(--text-secondary)]">до</label>
                <input
                  value={timeMax}
                  onChange={(e) => setTimeMax(e.target.value)}
                  inputMode="numeric"
                  className="mt-1 w-full h-10 px-3 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm focus:outline-none focus:border-[color:var(--accent)]"
                />
              </div>
            </div>
          </div>

          {groupCol ? (
            <div className="rounded-[2px] border border-[color:var(--border-color)] overflow-hidden">
              <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Значения</div>
                <div className="text-xs text-[color:var(--text-muted)] font-mono">{groupValueOptions.length}</div>
              </div>
              <div className="max-h-[240px] overflow-y-auto">
                {groupValueOptions.length > 0 ? groupValueOptions.map((v) => {
                  const checked = groupValues.includes(v);
                  return (
                    <label key={v} className={`flex items-center gap-3 px-3 py-2 border-b border-[color:var(--border-color)] cursor-pointer ${checked ? 'bg-[color:var(--bg-secondary)]' : 'hover:bg-[color:var(--bg-secondary)]'}`}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setGroupValues((prev) => {
                            const arr = Array.isArray(prev) ? prev : [];
                            return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
                          });
                        }}
                        className="text-[color:var(--accent)] rounded-[2px]"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm truncate text-[color:var(--text-primary)]">{v}</div>
                      </div>
                    </label>
                  );
                }) : (
                  <div className="p-4 text-sm text-[color:var(--text-muted)]">Нет доступных значений (для {groupCol})</div>
                )}
              </div>
              <div className="px-3 py-2 bg-[color:var(--white)] flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setGroupValues(groupValueOptions)}
                  className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                  disabled={groupValueOptions.length === 0}
                >
                  Выбрать все
                </button>
                <button
                  type="button"
                  onClick={() => setGroupValues([])}
                  className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                  disabled={groupValues.length === 0}
                >
                  Очистить
                </button>
              </div>
            </div>
          ) : null}

          <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-3">
            <div className="flex items-baseline justify-between gap-4">
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Объём</div>
              <div className="text-xs text-[color:var(--text-primary)] font-mono">{stepPreview.bases} переменных · ~{stepPreview.steps} шаг(ов)</div>
            </div>
          </div>
        </div>

        <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>Отмена</Button>
          <Button
            type="button"
            variant="primary"
            disabled={!canGenerate}
            onClick={() => {
              if (!canGenerate) return;

              const now = Date.now();
              const groups = groupCol && groupValues.length > 0 ? groupValues : [null];
              const steps = [];
              let idx = 0;

              for (const g of groups) {
                for (const item of groupedByBase) {
                  const outcome_cols = Array.isArray(item?.cols) ? item.cols : [];
                  if (method === 'friedman' && outcome_cols.length < 3) continue;
                  if (method === 'rm_anova' && outcome_cols.length < 2) continue;

                  const config = {
                    outcome_cols,
                    ...(method === 'rm_anova' ? { subject_col: subjectCol, group_col: '' } : {}),
                  };

                  if (groupCol && g != null) {
                    config.filter = { col: groupCol, value: g };
                  }

                  const baseLabel = baseKey(outcome_cols[0]);
                  const label = groupCol && g != null
                    ? `${formatMethodName?.(method) || method} · ${baseLabel} · ${groupCol}=${g}`
                    : `${formatMethodName?.(method) || method} · ${baseLabel}`;

                  steps.push({
                    id: `mass_${now}_${idx++}`,
                    method,
                    name: label,
                    config,
                  });
                }
              }

              if (steps.length > 0) onAppendSteps?.(steps);
              onClose?.();
            }}
          >
            Добавить шаги
          </Button>
        </div>
      </div>
    </div>
  );
}

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
  const [allDatasetColumns, setAllDatasetColumns] = useState([]);
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

  const chartFallback = useMemo(() => (
    <div className="animate-pulse h-[360px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)] flex items-center justify-center text-[color:var(--text-muted)] text-xs">
      {t('loading')}
    </div>
  ), [t]);
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

  const fetchAllColumnNames = useCallback(async (datasetId) => {
    const out = [];
    let offset = 0;
    const pageSize = 2000;
    let total = null;
    while (true) {
      const payload = await listDatasetColumns(datasetId, { offset, limit: pageSize });
      const chunk = Array.isArray(payload?.columns)
        ? payload.columns.map((c) => String(c || '').trim()).filter(Boolean)
        : [];
      if (!chunk.length) break;
      out.push(...chunk);

      const payloadTotal = Number(payload?.total);
      total = Number.isFinite(payloadTotal) && payloadTotal >= 0 ? payloadTotal : total;
      offset += chunk.length;
      if ((total != null && offset >= total) || chunk.length < pageSize) break;
    }
    return dedupeNames(out);
  }, []);

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
        setAllDatasetColumns([]);
        setDesignReviewConfirmed(false);
        setDesignReviewTimestamp(null);
        setDesignReviewError(null);
        return;
      }

      setDatasetLoading(true);
      try {
        const [profile, allCols] = await Promise.all([
          getDataset(datasetIdFromRoute),
          fetchAllColumnNames(datasetIdFromRoute).catch(() => []),
        ]);
        if (cancelled) return;
        setDatasetId(profile?.id || datasetIdFromRoute);
        const fallbackName = profile?.filename || profile?.name;
        setDatasetName(fallbackName || datasetIdFromRoute);
        const profileColumns = Array.isArray(profile?.columns) ? profile.columns : [];
        const fullColumnNames = Array.isArray(allCols) && allCols.length
          ? dedupeNames(allCols)
          : dedupeNames(profileColumns.map((c) => (typeof c === 'string' ? c : c?.name)));
        setAllDatasetColumns(fullColumnNames);

        const byName = new Map();
        for (const col of profileColumns) {
          const name = typeof col === 'string' ? String(col || '').trim() : String(col?.name || '').trim();
          if (!name) continue;
          if (!byName.has(name)) byName.set(name, col);
        }
        const mergedColumns = fullColumnNames.map((name) => byName.get(name) || { name, type: '' });
        setColumns(mergedColumns);

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
  }, [datasetIdFromRoute, fetchAllColumnNames, resetProtocolHistory]);

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
    const fullList = dedupeNames(allDatasetColumns);
    const profileList = Array.isArray(columns)
      ? columns
        .map((c) => {
          if (!c) return null;
          if (typeof c === 'string') return c;
          return c.name || c.column || c.id || null;
        })
        .filter(Boolean)
      : [];
    if (!fullList.length) return profileList;
    return dedupeNames([...fullList, ...profileList]);
  }, [allDatasetColumns, columns]);

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

  const onBack = () => {
    navigate('/datasets');
  };

  const datasetPicker = (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-8">
          <ResearchFlowNav active="data" showMenu={false} />
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
                    onClick={() => navigate(`${mode === 'tests' ? '/tests' : mode === 'protocol' ? '/protocol' : '/design'}/${ds.id}`)}
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
      <div className="-mx-6 -my-6 min-h-[calc(100vh-56px)] flex flex-col bg-[color:var(--bg-secondary)]">
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
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('analysis')}</div>
                  <h1 className="text-xl font-bold text-[color:var(--text-primary)] truncate">{datasetName || t('dataset')}</h1>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <div className="h-9 p-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => navigate(datasetIdResolved ? `/tests/${datasetIdResolved}` : '/tests')}
                    className={`h-7 px-3 rounded-[2px] text-xs font-semibold ${mode === 'tests' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                  >
                    {t('tests')}
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(datasetIdResolved ? `/${mode === 'protocol' ? 'protocol' : 'design'}/${datasetIdResolved}` : (mode === 'protocol' ? '/protocol' : '/design'))}
                    className={`h-7 px-3 rounded-[2px] text-xs font-semibold ${mode !== 'tests' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                  >
                    Конструктор
                  </button>
                </div>
                <Button
                  onClick={() => {
                    if (!datasetIdResolved) return;
                    navigate(`/prepare/${datasetIdResolved}`);
                  }}
                  disabled={!columns.length}
                  variant="ghost"
                  className="gap-2 min-w-[160px] justify-start"
                  type="button"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                  </svg>
                  <span className="tabular-nums">{t('variables')} ({columns.length})</span>
                </Button>
              </div>
            </div>

            <ResearchFlowNav active="design" datasetId={datasetIdResolved} className="mt-3" stepData={flowStepData} showMenu={false} />

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

        <div className="flex-1 flex overflow-hidden">
          {mode === 'tests' ? (
            <div className="w-[420px] max-w-[48vw] shrink-0 border-r border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
              <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('tests')}</div>
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{protocol.length} шаг(ов)</div>
              </div>

              <div className="flex-1 overflow-hidden">
                <TestSelectionPanel
                  variant="compact"
                  onTestSelect={handleTestSelect}
                  datasetId={datasetIdResolved}
                  suggestedConfig={workspaceRoles}
                  disabled={isExecuting}
                />
              </div>
            </div>
          ) : (
            <div className="w-[360px] max-w-[45vw] shrink-0 border-r border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
              <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('templates')}</div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setMassDynamicsSeed(Date.now());
                      setIsMassDynamicsOpen(true);
                    }}
                    disabled={!datasetIdResolved || columns.length === 0}
                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Массовая динамика
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/tests/${datasetIdResolved}`)}
                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                  >
                    {t('tests')}
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-hidden">
                <div className="h-full overflow-y-auto bg-[color:var(--bg-secondary)]">
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
                </div>
              </div>
            </div>
          )}

          {mode === 'tests' ? (
            <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
              <div className="h-12 px-4 flex items-center justify-between border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase truncate">Очередь</div>
                  <div className="text-xs text-[color:var(--text-secondary)] truncate">Собери шаги, затем открой конструктор.</div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (protocol.length === 0) return;
                      if (!confirm('Очистить список шагов?')) return;
                      resetProtocolHistory([]);
                      setResults(null);
                      setSelectedStepId(null);
                    }}
                    disabled={protocol.length === 0}
                    className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Очистить
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/design/${datasetIdResolved}`)}
                    className="h-9 px-4 rounded-[2px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold uppercase tracking-[0.18em] hover:opacity-90"
                  >
                    Конструктор
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 bg-[color:var(--bg-secondary)]">
                {protocol.length === 0 ? (
                  <div className="h-full rounded-[2px] border border-dashed border-[color:var(--border-color)] bg-[color:var(--white)] flex items-center justify-center text-sm text-[color:var(--text-secondary)]">
                    Выбери тест слева — он появится здесь.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {protocol.map((step, idx) => (
                      <div key={step.id} className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Шаг {idx + 1}</div>
                            <div className="mt-1 text-sm font-bold text-[color:var(--text-primary)] truncate">{step.name || formatMethodName(step.method)}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-secondary)] font-mono truncate">{step.method}</div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <label className="h-8 px-3 inline-flex items-center gap-2 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:border-black">
                              <input
                                type="checkbox"
                                checked={step?.enabled !== false}
                                onChange={(e) => handleToggleTest(step.id, e.target.checked)}
                                className="h-4 w-4 accent-black"
                                aria-label="Включить в анализ"
                              />
                              <span className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-secondary)] uppercase">Включить в анализ</span>
                            </label>
                            <button
                              type="button"
                              onClick={() => handleEditTest(step)}
                              className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                            >
                              {t('edit')}
                            </button>
                          </div>
                        </div>
                        {step.config && typeof step.config === 'object' ? (
                          <div className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-2">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1">
                              {Object.entries(step.config).slice(0, 8).map(([k, v]) => (
                                <div key={k} className="flex items-baseline justify-between gap-3">
                                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{k}</div>
                                  <div className="text-xs text-[color:var(--text-primary)] font-mono truncate">{Array.isArray(v) ? v.filter(Boolean).join(', ') : String(v ?? '')}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-hidden">
                  <ProtocolBuilder
                    protocol={protocol}
                    selectedStepId={selectedStepId}
                    onSelectStep={(id) => setSelectedStepId(id)}
                    onToggleTest={handleToggleTest}
                    onEditTest={handleEditTest}
                    onMoveTest={handleMoveTest}
                    onExecuteProtocol={handleExecuteProtocol}
                    onAISuggest={handleAISuggest}
                    onVibeDesign={openVibe}
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

              <div className="w-[420px] max-w-[48vw] shrink-0 border-l border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
                <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setRightPane('inspector')}
                      className={`h-8 px-3 rounded-[2px] text-xs font-semibold ${rightPane === 'inspector' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                    >
                      Инспектор
                    </button>
                    <button
                      type="button"
                      onClick={() => setRightPane('ai')}
                      className={`h-8 px-3 rounded-[2px] text-xs font-semibold ${rightPane === 'ai' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                    >
                      ИИ
                    </button>
                  </div>

                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{protocol.length} шаг(ов)</div>
                </div>

                <div className="flex-1 overflow-y-auto p-3 bg-[color:var(--bg-secondary)]">
                  {rightPane === 'ai' ? (
                    <AISuggestionsPane
                      t={t}
                      protocol={protocol}
                      recommendations={aiRecommendations}
                      isAnalyzing={isAIAnalyzing}
                      error={aiError}
                      onSuggest={handleAISuggest}
                      onAddRecommendation={handleAddRecommendation}
                      onClose={() => setRightPane('inspector')}
                    />
                  ) : (
                    <div className="space-y-3">
                      <div className="h-[540px]">
                        <VariableWorkspace
                          columns={columns}
                          columnStatsByName={columnStatsByName}
                          roleByName={roleByName}
                          roles={workspaceRoles}
                          onRolesChange={handleWorkspaceRolesChange}
                          secondaryRoleLabel={templateSecondaryKey === 'predictor' ? t('predictor') : t('group')}
                        />
                      </div>

                      {(workspaceRoles?.target || workspaceRoles?.group) ? (
                        <VariablePreview
                          t={t}
                          targetVar={workspaceRoles?.target}
                          groupVar={workspaceRoles?.group}
                          groupLabel={templateSecondaryKey === 'predictor' ? t('predictor') : t('group')}
                          statsByName={columnStatsByName}
                        />
                      ) : null}

                      <StepPreviewPanel title={t('preview')} steps={previewSteps} />

                      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                        <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Шаг</div>
                            <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">
                              {selectedStepMeta.step ? (selectedStepMeta.step.name || formatMethodName(selectedStepMeta.step.method)) : 'Не выбран'}
                            </div>
                          </div>

                          {selectedStepMeta.step ? (
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <button
                                type="button"
                                onClick={() => {
                                  if (selectedStepMeta.index > 0) handleMoveTest(selectedStepMeta.index, selectedStepMeta.index - 1);
                                }}
                                disabled={selectedStepMeta.index <= 0}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-[2px] border border-transparent text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)] disabled:opacity-40 disabled:cursor-not-allowed"
                                title={t('move_up')}
                              >
                                ↑
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (selectedStepMeta.index >= 0 && selectedStepMeta.index < protocol.length - 1) handleMoveTest(selectedStepMeta.index, selectedStepMeta.index + 1);
                                }}
                                disabled={selectedStepMeta.index < 0 || selectedStepMeta.index >= protocol.length - 1}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-[2px] border border-transparent text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)] disabled:opacity-40 disabled:cursor-not-allowed"
                                title={t('move_down')}
                              >
                                ↓
                              </button>
                              <button
                                type="button"
                                onClick={() => handleEditTest(selectedStepMeta.step)}
                                className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                              >
                                {t('edit')}
                              </button>
                            </div>
                          ) : null}
                        </div>

                        <div className="p-3">
                          {protocol.length > 0 && !selectedStepMeta.step ? (
                            <div className="text-xs text-[color:var(--text-secondary)]">Выбери шаг в центре — здесь будет его конфиг.</div>
                          ) : null}

                          {protocol.length === 0 ? (
                            <div className="text-xs text-[color:var(--text-secondary)]">Добавь шаг через «Тесты».</div>
                          ) : null}

                          {selectedStepMeta.step ? (
                            <div className="space-y-3">
                              <div className="text-xs text-[color:var(--text-secondary)] font-mono">{selectedStepMeta.step.method}</div>

                              {selectedStepMeta.step.config && typeof selectedStepMeta.step.config === 'object' ? (
                                <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-2">
                                  <div className="space-y-1">
                                    {Object.entries(selectedStepMeta.step.config).map(([k, v]) => (
                                      <div key={k} className="flex items-baseline justify-between gap-3">
                                        <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{k}</div>
                                        <div className="text-xs text-[color:var(--text-primary)] font-mono truncate">
                                          {Array.isArray(v) ? v.filter(Boolean).join(', ') : String(v ?? '')}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}

                              <button
                                type="button"
                                onClick={() => {
                                  if (!confirm('Удалить шаг?')) return;
                                  handleRemoveTest(selectedStepMeta.step.id);
                                  setSelectedStepId(null);
                                }}
                                className="h-9 w-full rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--accent)] hover:border-black"
                              >
                                {t('remove')}
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <MassDynamicsModal
        key={`mass_${massDynamicsSeed}`}
        isOpen={isMassDynamicsOpen}
        onClose={() => setIsMassDynamicsOpen(false)}
        columns={columns}
        statsByName={columnStatsByName}
        defaultGroupCol={workspaceRoles?.group || ''}
        defaultSubjectCol=""
        formatMethodName={formatMethodName}
        onAppendSteps={handleAppendMassSteps}
      />

      <VibeDesignModal
        isOpen={isVibeOpen}
        onClose={() => setIsVibeOpen(false)}
        value={vibeText}
        onValueChange={setVibeText}
        globalSettings={globalDefaults}
        onGlobalSettingsChange={handleGlobalSettingsChange}
        onGenerate={handleVibeGenerate}
        onGenerateAndRun={handleVibeGenerateAndRun}
        isLoading={isVibeLoading}
        error={vibeError}
        preview={vibePreview}
        onApply={handleApplyVibePreview}
      />

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
        key={`save_${saveProtocolSeed}`}
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
  const [allDatasetColumns, setAllDatasetColumns] = useState([]);
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
    const fullList = dedupeNames(allDatasetColumns);
    const list = Array.isArray(columns) ? columns : [];
    const profileList = list
      .map((c) => (typeof c === 'string' ? c : c?.name))
      .filter(Boolean)
      .map((n) => String(n));
    if (!fullList.length) return profileList;
    return dedupeNames([...fullList, ...profileList]);
  }, [allDatasetColumns, columns]);

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

  const selectableOutcomes = useMemo(() => {
    return dedupeNames([
      ...columnNames,
      ...numericOutcomes,
      ...(Array.isArray(selectedOutcomes) ? selectedOutcomes : []),
      String(roles?.target || '').trim(),
    ]);
  }, [columnNames, numericOutcomes, roles?.target, selectedOutcomes]);

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

  const fetchAllColumnNames = useCallback(async (datasetId) => {
    const out = [];
    let offset = 0;
    const pageSize = 2000;
    let total = null;
    while (true) {
      const payload = await listDatasetColumns(datasetId, { offset, limit: pageSize });
      const chunk = Array.isArray(payload?.columns)
        ? payload.columns.map((c) => String(c || '').trim()).filter(Boolean)
        : [];
      if (!chunk.length) break;
      out.push(...chunk);

      const payloadTotal = Number(payload?.total);
      total = Number.isFinite(payloadTotal) && payloadTotal >= 0 ? payloadTotal : total;
      offset += chunk.length;
      if ((total != null && offset >= total) || chunk.length < pageSize) break;
    }
    return dedupeNames(out);
  }, []);

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
      setAllDatasetColumns([]);
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
        setAllDatasetColumns([]);
        return;
      }

      setDatasetLoading(true);
      try {
        const [profile, allCols] = await Promise.all([
          getDataset(datasetIdResolved),
          fetchAllColumnNames(datasetIdResolved).catch(() => []),
        ]);
        if (cancelled) return;
        const fallbackName = profile?.filename || profile?.name;
        setDatasetName(fallbackName || datasetIdResolved);
        const profileColumns = Array.isArray(profile?.columns) ? profile.columns : [];
        setColumns(profileColumns);
        setAllDatasetColumns(
          Array.isArray(allCols) && allCols.length
            ? allCols
            : dedupeNames(profileColumns.map((c) => (typeof c === 'string' ? c : c?.name))),
        );

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
  }, [datasetIdResolved, fetchAllColumnNames]);

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

  const filteredSelectableOutcomes = useMemo(() => {
    const base = (Array.isArray(selectableOutcomes) ? selectableOutcomes : []).filter(Boolean);
    const q = String(outcomesQuery || '').trim().toLowerCase();
    const filtered = q ? base.filter((n) => String(n).toLowerCase().includes(q)) : base;
    return filtered.sort((a, b) => String(a).localeCompare(String(b), undefined, { sensitivity: 'base' }));
  }, [outcomesQuery, selectableOutcomes]);

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
  const outcomesUniverseSize = outcomeMode === 'selected'
    ? (Array.isArray(selectableOutcomes) ? selectableOutcomes.length : 0)
    : (Array.isArray(numericOutcomes) ? numericOutcomes.length : 0);

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
                  onClick={() => navigate(`/prepare/${datasetIdResolved}`, { state: { ...(location.state || {}), origin: 'ai' } })}
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
                        <div className="text-xs text-[color:var(--text-secondary)]">из {outcomesUniverseSize || 0}</div>
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
                              const next = filteredSelectableOutcomes.slice(0, Math.max(1, Number(outcomesLimit) || 1));
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
                          {filteredSelectableOutcomes.length === 0 ? (
                            <div className="p-3 text-sm text-[color:var(--text-secondary)]">Нет показателей</div>
                          ) : (
                            <div className="divide-y divide-[color:var(--border-color)]">
                              {filteredSelectableOutcomes.slice(0, 250).map((name) => {
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

const AnalysisDesign = ({ mode = 'design' }) => {
  if (mode === 'ai') return <AnalysisAIDesign />;
  if (mode === 'tests') return <AnalysisDesignLegacy mode="tests" />;
  if (mode === 'protocol') return <AnalysisDesignLegacy mode="protocol" />;
  return <AnalysisDesignLegacy mode="design" />;
};

export default AnalysisDesign;
