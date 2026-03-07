function clamp01(value, fallback = 0) {
  if (!Number.isFinite(value)) return fallback;
  return Math.max(0, Math.min(1, value));
}

function normalizeAnalysisMode(value) {
  const mode = String(value || '').trim().toLowerCase();
  if (mode === 'publication') return 'publication';
  if (mode === 'focused') return 'focused';
  return 'exploratory';
}

function normalizeValidationProfile(value, analysisMode = 'exploratory') {
  const profile = String(value || '').trim().toLowerCase();
  if (profile === 'publication') return 'publication';
  if (profile === 'focused') return 'focused';
  if (profile === 'exploratory') return 'exploratory';
  if (analysisMode === 'publication') return 'publication';
  if (analysisMode === 'focused') return 'focused';
  return 'exploratory';
}

function resolveScoringProfile(options = {}) {
  const analysisMode = normalizeAnalysisMode(options.analysisMode);
  const validationProfile = normalizeValidationProfile(options.validationProfile, analysisMode);

  if (validationProfile === 'publication') {
    return {
      analysisMode,
      validationProfile,
      weights: { quality: 0.74, latency: 0.08, token: 0.03, step: 0.03, reliability: 0.12 },
      penalties: { fallback: 0.15, retryPerAttempt: 0.03, fallbackReliabilityFactor: 0.55 },
    };
  }
  if (validationProfile === 'focused') {
    return {
      analysisMode,
      validationProfile,
      weights: { quality: 0.70, latency: 0.10, token: 0.05, step: 0.03, reliability: 0.12 },
      penalties: { fallback: 0.13, retryPerAttempt: 0.025, fallbackReliabilityFactor: 0.60 },
    };
  }
  return {
    analysisMode,
    validationProfile,
    weights: { quality: 0.76, latency: 0.14, token: 0.07, step: 0.02, reliability: 0.01 },
    penalties: { fallback: 0.01, retryPerAttempt: 0.004, fallbackReliabilityFactor: 0.90 },
  };
}

function scoreLatencyMs(elapsedMs) {
  const ms = Number(elapsedMs);
  if (!Number.isFinite(ms) || ms < 0) return 0.5;
  return clamp01(1 / (1 + ms / 2000), 0.5);
}

function scoreTokenEfficiency(tokenTotal) {
  const tokens = Number(tokenTotal);
  if (!Number.isFinite(tokens) || tokens < 0) return 0.5;
  return clamp01(1 / (1 + tokens / 6000), 0.5);
}

function scoreStepCoverage(stepCount, expectedStepCount = 12) {
  const steps = Number(stepCount);
  const expected = Number(expectedStepCount);
  const denominator = Number.isFinite(expected) && expected > 0 ? expected : 12;
  if (!Number.isFinite(steps) || steps < 0) return 0.5;
  return clamp01(steps / denominator, 0.5);
}

function scoreRetryEfficiency(attemptCount) {
  const attempts = Number(attemptCount);
  if (!Number.isFinite(attempts) || attempts < 1) return 1;
  return clamp01(1 / (1 + Math.max(0, attempts - 1)), 1);
}

export function rankBenchmarkRows(rows, options = {}) {
  const source = Array.isArray(rows) ? rows : [];
  const successful = source.filter((row) => row?.status === 'ok');
  const profile = resolveScoringProfile(options);
  const expectedStepCountInput = Number(options.expectedStepCount);
  const expectedStepCounts = successful
    .map((row) => Number(row?.stepCount))
    .filter((value) => Number.isFinite(value) && value > 0);
  const expectedStepCount = Number.isFinite(expectedStepCountInput) && expectedStepCountInput > 0
    ? Math.max(1, Math.round(expectedStepCountInput))
    : (
      expectedStepCounts.length > 0
        ? Math.max(6, Math.round(expectedStepCounts.reduce((sum, value) => sum + value, 0) / expectedStepCounts.length))
        : 12
    );

  if (successful.length === 0) {
    return source.map((row) => ({
      ...row,
      benchmarkScore: null,
      recommended: false,
      scoringProfile: profile.validationProfile,
    }));
  }

  const scored = successful.map((row) => {
    const qualityRaw = Number(row?.qualityScore);
    const quality = Number.isFinite(qualityRaw) ? clamp01(qualityRaw / 100, 0) : 0;
    const latency = scoreLatencyMs(row?.elapsedMs);
    const tokenEfficiency = scoreTokenEfficiency(row?.tokenTotal);
    const stepCoverage = scoreStepCoverage(row?.stepCount, expectedStepCount);
    const retryEfficiency = scoreRetryEfficiency(row?.attemptCount);
    const fallbackUsed = Boolean(row?.fallbackUsed);
    const attemptCount = Number(row?.attemptCount);
    const reliability = Math.max(
      0,
      Math.min(
        1,
        (fallbackUsed ? profile.penalties.fallbackReliabilityFactor : 1.0) * 0.7 + retryEfficiency * 0.3
      ),
    );
    const fallbackPenalty = fallbackUsed ? profile.penalties.fallback : 0;
    const retryPenalty = Number.isFinite(attemptCount)
      ? Math.max(0, Math.min(0.12, Math.max(0, attemptCount - 1) * profile.penalties.retryPerAttempt))
      : 0;

    const benchmarkScore = Number(
      (
        quality * profile.weights.quality
        + latency * profile.weights.latency
        + tokenEfficiency * profile.weights.token
        + stepCoverage * profile.weights.step
        + reliability * profile.weights.reliability
        - fallbackPenalty
        - retryPenalty
      ).toFixed(4)
    );

    return {
      ...row,
      benchmarkScore,
      scoringProfile: profile.validationProfile,
    };
  });

  scored.sort((a, b) => {
    const sa = Number.isFinite(a?.benchmarkScore) ? a.benchmarkScore : -1;
    const sb = Number.isFinite(b?.benchmarkScore) ? b.benchmarkScore : -1;
    if (sa !== sb) return sb - sa;
    const qa = Number.isFinite(Number(a?.qualityScore)) ? Number(a.qualityScore) : -1;
    const qb = Number.isFinite(Number(b?.qualityScore)) ? Number(b.qualityScore) : -1;
    if (qa !== qb) return qb - qa;
    const fa = a?.fallbackUsed ? 1 : 0;
    const fb = b?.fallbackUsed ? 1 : 0;
    if (fa !== fb) return fa - fb;
    const aa = Number.isFinite(Number(a?.attemptCount)) ? Number(a.attemptCount) : Number.POSITIVE_INFINITY;
    const ab = Number.isFinite(Number(b?.attemptCount)) ? Number(b.attemptCount) : Number.POSITIVE_INFINITY;
    if (aa !== ab) return aa - ab;
    const la = Number.isFinite(Number(a?.elapsedMs)) ? Number(a.elapsedMs) : Number.POSITIVE_INFINITY;
    const lb = Number.isFinite(Number(b?.elapsedMs)) ? Number(b.elapsedMs) : Number.POSITIVE_INFINITY;
    if (la !== lb) return la - lb;
    const ta = Number.isFinite(Number(a?.tokenTotal)) ? Number(a.tokenTotal) : Number.POSITIVE_INFINITY;
    const tb = Number.isFinite(Number(b?.tokenTotal)) ? Number(b.tokenTotal) : Number.POSITIVE_INFINITY;
    return ta - tb;
  });

  const recommendedId = scored[0]?.id || null;

  return source.map((row) => {
    const scoreRow = scored.find((it) => it.id === row?.id) || null;
    return {
      ...row,
      benchmarkScore: scoreRow?.benchmarkScore ?? null,
      recommended: Boolean(recommendedId && row?.id === recommendedId),
      scoringProfile: profile.validationProfile,
    };
  });
}
