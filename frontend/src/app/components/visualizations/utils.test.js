import { describe, it, expect } from 'vitest';
import { formatMultiplicityTrace } from './utils';

describe('formatMultiplicityTrace', () => {
  it('returns empty string for invalid trace', () => {
    expect(formatMultiplicityTrace(null)).toBe('');
    expect(formatMultiplicityTrace(undefined)).toBe('');
    expect(formatMultiplicityTrace('x')).toBe('');
  });

  it('formats method, counts and alpha', () => {
    const trace = { method: 'holm', n_valid: 3, n_total: 5, alpha: 0.05 };
    expect(formatMultiplicityTrace(trace)).toBe('Correction: Holm · tests=3/5 · alpha=0.050');
  });

  it('falls back to provided method label', () => {
    const trace = { n_valid: 2, n_total: 2 };
    expect(formatMultiplicityTrace(trace, 'FDR(BH)')).toBe('Correction: FDR(BH) · tests=2/2');
  });
});
