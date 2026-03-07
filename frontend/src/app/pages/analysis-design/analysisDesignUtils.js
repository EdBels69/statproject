// Utility functions extracted from AnalysisDesign.jsx
// These are pure JS helpers (no JSX) shared across analysis-design components.

export const PROTOCOL_STORAGE_KEY = 'clinimetria_protocols_v1';
export const GLOBAL_SETTINGS_STORAGE_KEY = 'clinimetria_global_settings_v1';

export function safeString(value) {
  return String(value ?? '').trim();
}

export function safeJsonParse(value, fallback) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function normalizeWorkspaceRoles(next) {
  if (!next || typeof next !== 'object') {
    return { target: '', group: '', covariates: [] };
  }
  return {
    target: safeString(next?.target || ''),
    group: safeString(next?.group || ''),
    covariates: Array.isArray(next?.covariates) ? next.covariates.filter(Boolean) : [],
  };
}

export function buildRoleByName(roles) {
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

export function mergeTemplateVarsFromRoles(prev, roles, templateSecondaryKey) {
  const base = prev && typeof prev === 'object' ? prev : { target: '', group: '', predictor: '' };
  const mapped = { ...base, target: roles.target };
  if (templateSecondaryKey === 'predictor') mapped.predictor = roles.group;
  else mapped.group = roles.group;
  return mapped;
}

export function makeId() {
  const fn = globalThis?.crypto?.randomUUID;
  if (typeof fn === 'function') return fn.call(globalThis.crypto);
  return `p_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

export function normalizeDesignReviewStatus(payload) {
  const confirmed = Boolean(payload?.confirmed);
  const confirmedAt = confirmed && typeof payload?.confirmed_at === 'string' ? payload.confirmed_at : null;
  return { confirmed, confirmedAt };
}

export function buildDesignReviewGlobals({ source, confirmed, confirmedAt, extra }) {
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

export function normalizeSavedProtocol(raw) {
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
      .filter((s) => s.method),
  };
}

export function loadSavedProtocols() {
  const text = localStorage.getItem(PROTOCOL_STORAGE_KEY);
  const parsed = safeJsonParse(text, []);
  if (!Array.isArray(parsed)) return [];
  return parsed.map(normalizeSavedProtocol).filter(Boolean);
}

export function normalizeGlobalSettings(raw) {
  const alternative = raw?.alternative;
  const postH = raw?.post_hoc;
  const corr = raw?.post_hoc_correction;
  const altOk = alternative === 'two-sided' || alternative === 'less' || alternative === 'greater' ? alternative : 'two-sided';
  const postOk = postH === 'tukey' || postH === 'dunn' || postH === 'none' ? postH : 'none';
  const corrOk = corr === 'bh' || corr === 'bky' || corr === 'none' ? corr : 'none';
  return { alternative: altOk, post_hoc: postOk, post_hoc_correction: corrOk };
}

export function loadGlobalSettings() {
  const text = localStorage.getItem(GLOBAL_SETTINGS_STORAGE_KEY);
  const parsed = safeJsonParse(text, null);
  return normalizeGlobalSettings(parsed);
}

export function saveGlobalSettings(value) {
  localStorage.setItem(GLOBAL_SETTINGS_STORAGE_KEY, JSON.stringify(normalizeGlobalSettings(value)));
}

export function saveSavedProtocols(protocols) {
  localStorage.setItem(PROTOCOL_STORAGE_KEY, JSON.stringify(protocols));
}

export function baseKey(raw) {
  const s = String(raw || '').trim();
  const stripped = s
    .replace(/\s+/g, ' ')
    .replace(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?\d+)$/i, '')
    .replace(/[_\-\s]+$/g, '')
    .trim();
  return stripped || s;
}

export function timeIndex(raw) {
  const s = String(raw || '').trim();
  const m = s.match(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?)(\d+)$/i);
  if (!m) return null;
  const n = Number.parseInt(m[1], 10);
  return Number.isFinite(n) ? n : null;
}
