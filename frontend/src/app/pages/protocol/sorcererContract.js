// Protocol contract validation extracted from ProtocolSorcerer
// Validates that all required columns exist and are specified

function safeStr(v) {
  const s = String(v || '').trim();
  return s ? s : null;
}

function stepConfig(s) {
  return (s && typeof s === 'object' && s.config && typeof s.config === 'object') ? s.config : {};
}

function findOutcome(cfg) {
  return safeStr(cfg.outcome) || safeStr(cfg.target);
}

function findGroup(cfg) {
  return safeStr(cfg.group) || safeStr(cfg.group_col) || safeStr(cfg.predictor);
}

function validateStep(s, idx, existingCols, issues) {
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
}

export function buildContract({ columnNames, chatProtocol, hasChatProtocol, recommendation, variables }) {
  const existingCols = new Set(columnNames.map(String));
  const issues = [];

  if (hasChatProtocol) {
    chatProtocol.forEach((s, idx) => validateStep(s, idx, existingCols, issues));
    return { mode: 'chat', issues };
  }

  const baseIssues = [];
  const m = safeStr(recommendation?.method_id);

  if (m && m !== 'consult_statistician') {
    const needsGroup = m !== 'survival_km' && !(m?.includes('regression')) && !(m === 'rm_anova' || m === 'friedman');
    const needsTarget = m !== 'kw_timepoints_all_numeric' && !(Boolean(variables.all_numeric) && !['pearson', 'spearman', 'kendall', 'chi_square'].includes(m)) && !(m === 'rm_anova' || m === 'friedman');
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

  return { mode: 'sorcerer', issues: baseIssues };
}
