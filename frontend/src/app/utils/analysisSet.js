function toStr(value) {
  return String(value ?? '').trim();
}

function uniq(list) {
  const out = [];
  const seen = new Set();
  for (const item of (Array.isArray(list) ? list : [])) {
    const s = toStr(item);
    if (!s || seen.has(s)) continue;
    seen.add(s);
    out.push(s);
  }
  return out;
}

export function extractRegressionColumns(protocolSteps = []) {
  const outcomes = new Set();
  const predictors = new Set();

  for (const step of (Array.isArray(protocolSteps) ? protocolSteps : [])) {
    if (!step || typeof step !== 'object') continue;
    const method = toStr(step.method || step.test || step.type).toLowerCase();
    if (method !== 'linear_regression' && method !== 'logistic_regression') continue;
    const cfg = step.config && typeof step.config === 'object' ? step.config : {};

    const outcome = toStr(cfg.outcome || cfg.target);
    if (outcome) outcomes.add(outcome);

    const group = toStr(cfg.group);
    if (group) predictors.add(group);

    const predList = Array.isArray(cfg.predictors) ? cfg.predictors : [];
    for (const p of predList) {
      const s = toStr(p);
      if (s) predictors.add(s);
    }

    const covList = Array.isArray(cfg.covariates) ? cfg.covariates : [];
    for (const c of covList) {
      const s = toStr(c);
      if (s) predictors.add(s);
    }
  }

  return {
    outcomes: Array.from(outcomes),
    predictors: Array.from(predictors),
  };
}

export function buildAnalysisSetFreezeSpec(protocolSteps = [], { mode = 'complete_case' } = {}) {
  const modeNorm = toStr(mode) || 'complete_case';
  const { outcomes, predictors } = extractRegressionColumns(protocolSteps);
  const outcomesU = uniq(outcomes);
  const predictorsU = uniq(predictors);

  if (!outcomesU.length) return null;

  if (modeNorm === 'simple_impute') {
    const outcomeSet = new Set(outcomesU);
    return {
      required_non_missing: outcomesU,
      impute_columns: predictorsU.filter((c) => !outcomeSet.has(c)),
      notes: ['from_protocol', 'require_outcome_only', 'impute_predictors_median_mode'],
    };
  }

  const required = uniq([...outcomesU, ...predictorsU]);
  return {
    required_non_missing: required,
    impute_columns: [],
    notes: ['from_protocol', 'complete_case_union'],
  };
}

