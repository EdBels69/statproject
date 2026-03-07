import { describe, expect, it } from 'vitest';
import { rankBenchmarkRows } from './benchmarkScoring';

describe('rankBenchmarkRows', () => {
  it('prefers higher quality score, then speed/token efficiency', () => {
    const rows = [
      {
        id: 'gemini_single',
        status: 'ok',
        qualityScore: 85,
        elapsedMs: 900,
        stepCount: 8,
        tokenTotal: 3800,
      },
      {
        id: 'minimax_single',
        status: 'ok',
        qualityScore: 93,
        elapsedMs: 1400,
        stepCount: 7,
        tokenTotal: 5200,
      },
      {
        id: 'qwen_single',
        status: 'ok',
        qualityScore: 83,
        elapsedMs: 700,
        stepCount: 9,
        tokenTotal: 3600,
      },
    ];

    const ranked = rankBenchmarkRows(rows);
    const recommended = ranked.find((r) => r.recommended);
    expect(recommended?.id).toBe('minimax_single');
    expect(typeof recommended?.benchmarkScore).toBe('number');
  });

  it('ignores error variants for recommendation and keeps score null', () => {
    const rows = [
      {
        id: 'gemini_single',
        status: 'ok',
        qualityScore: 80,
        elapsedMs: 1200,
        stepCount: 6,
        tokenTotal: 4000,
      },
      {
        id: 'glm5_single',
        status: 'error',
        error: 'timeout',
      },
    ];

    const ranked = rankBenchmarkRows(rows);
    const good = ranked.find((r) => r.id === 'gemini_single');
    const failed = ranked.find((r) => r.id === 'glm5_single');

    expect(good?.recommended).toBe(true);
    expect(typeof good?.benchmarkScore).toBe('number');
    expect(failed?.recommended).toBe(false);
    expect(failed?.benchmarkScore).toBe(null);
  });

  it('penalizes fallback-heavy variants when quality is close', () => {
    const rows = [
      {
        id: 'qwen_single',
        status: 'ok',
        qualityScore: 89,
        elapsedMs: 850,
        stepCount: 8,
        tokenTotal: 3900,
        fallbackUsed: true,
        attemptCount: 4,
      },
      {
        id: 'glm5_single',
        status: 'ok',
        qualityScore: 88,
        elapsedMs: 980,
        stepCount: 8,
        tokenTotal: 4100,
        fallbackUsed: false,
        attemptCount: 1,
      },
    ];

    const ranked = rankBenchmarkRows(rows);
    const recommended = ranked.find((r) => r.recommended);
    expect(recommended?.id).toBe('glm5_single');
  });

  it('uses stricter fallback penalties for publication profile', () => {
    const rows = [
      {
        id: 'minimax_single',
        status: 'ok',
        qualityScore: 91,
        elapsedMs: 900,
        stepCount: 10,
        tokenTotal: 4200,
        fallbackUsed: true,
        attemptCount: 3,
      },
      {
        id: 'gemini_single',
        status: 'ok',
        qualityScore: 89,
        elapsedMs: 1200,
        stepCount: 10,
        tokenTotal: 4600,
        fallbackUsed: false,
        attemptCount: 1,
      },
    ];

    const exploratoryRanked = rankBenchmarkRows(rows, { analysisMode: 'exploratory', validationProfile: 'exploratory' });
    const exploratoryRecommended = exploratoryRanked.find((r) => r.recommended);
    expect(exploratoryRecommended?.id).toBe('minimax_single');

    const publicationRanked = rankBenchmarkRows(rows, { analysisMode: 'publication', validationProfile: 'publication' });
    const publicationRecommended = publicationRanked.find((r) => r.recommended);
    expect(publicationRecommended?.id).toBe('gemini_single');
  });
});
