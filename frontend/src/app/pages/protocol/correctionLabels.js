// Correction label formatters extracted from ProtocolSorcerer

export function getMultiplicityLabel(correction) {
  const corr = String(correction || '').trim().toLowerCase();
  if (!corr || corr === 'fdr_bh') return 'FDR(BH)';
  if (corr === 'fdr_tsbky') return 'FDR(BKY)';
  if (corr === 'fdr_by') return 'FDR(BY)';
  if (corr === 'bonferroni') return 'Bonferroni';
  if (corr === 'holm-sidak') return 'Holm–Šidák';
  if (corr === 'sidak') return 'Šidák';
  if (corr === 'holm') return 'Holm';
  if (corr === 'none') return 'none';
  return corr;
}

export function getPostHocCorrectionLabel(correction) {
  const corr = String(correction || '').trim().toLowerCase();
  if (!corr || corr === 'none') return 'none';
  if (corr === 'bh' || corr === 'fdr_bh') return 'FDR(BH)';
  if (corr === 'bky' || corr === 'fdr_tsbky') return 'FDR(BKY)';
  if (corr === 'by' || corr === 'fdr_by') return 'FDR(BY)';
  if (corr === 'bonferroni') return 'Bonferroni';
  if (corr === 'holm-sidak') return 'Holm–Šidák';
  if (corr === 'sidak') return 'Šidák';
  if (corr === 'holm') return 'Holm';
  return corr;
}

export function getPostHocLabel(postHoc) {
  const ph = String(postHoc || '').trim().toLowerCase();
  if (!ph || ph === 'none') return 'none';
  if (ph === 'dunn') return 'Dunn';
  if (ph === 'games_howell') return 'Games–Howell';
  if (ph === 'tukey') return 'Tukey HSD';
  return ph;
}
