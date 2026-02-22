import { describe, it, expect } from 'vitest';

import { extractRegressionColumns, buildAnalysisSetFreezeSpec } from './analysisSet';

describe('analysisSet utils', () => {
  it('extracts outcomes and predictors from regression protocol steps', () => {
    const protocol = [
      {
        id: 's1',
        method: 'logistic_regression',
        config: {
          outcome: 'death',
          predictors: ['age', 'glucose_last'],
          covariates: ['spo2'],
          group: 'sex',
        },
      },
      { id: 's2', method: 'spearman', config: { outcome: 'a', group: 'b' } },
    ];

    const res = extractRegressionColumns(protocol);
    expect(new Set(res.outcomes)).toEqual(new Set(['death']));
    expect(new Set(res.predictors)).toEqual(new Set(['age', 'glucose_last', 'spo2', 'sex']));
  });

  it('builds complete-case freeze spec (union) by default', () => {
    const protocol = [
      {
        method: 'linear_regression',
        config: { outcome: 'los', predictors: ['age'], covariates: ['spo2'] },
      },
    ];
    const spec = buildAnalysisSetFreezeSpec(protocol);
    expect(spec).not.toBeNull();
    expect(new Set(spec.required_non_missing)).toEqual(new Set(['los', 'age', 'spo2']));
    expect(spec.impute_columns).toEqual([]);
  });

  it('builds simple-impute freeze spec (outcome required, predictors imputed)', () => {
    const protocol = [
      {
        method: 'logistic_regression',
        config: { outcome: 'death', predictors: ['age', 'glucose_last'], covariates: ['spo2'] },
      },
    ];
    const spec = buildAnalysisSetFreezeSpec(protocol, { mode: 'simple_impute' });
    expect(spec).not.toBeNull();
    expect(spec.required_non_missing).toEqual(['death']);
    expect(new Set(spec.impute_columns)).toEqual(new Set(['age', 'glucose_last', 'spo2']));
  });

  it('returns null when protocol has no regression steps', () => {
    const protocol = [{ method: 'spearman', config: { outcome: 'a', group: 'b' } }];
    const spec = buildAnalysisSetFreezeSpec(protocol, { mode: 'complete_case' });
    expect(spec).toBeNull();
  });
});

