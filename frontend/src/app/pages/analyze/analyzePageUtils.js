export function deriveAnalyzeMode(pathname, modeOverride) {
  if (modeOverride) return modeOverride;
  if (pathname.startsWith('/report')) return 'report';
  if (pathname.startsWith('/graphs')) return 'graphs';
  if (pathname.startsWith('/results')) return 'results';
  return 'results';
}

export function buildAnalyzeFlowStepData({ designReviewConfirmed, batchResult }) {
  const ready = Boolean(batchResult);
  return {
    dataLoaded: true,
    variablesSet: true,
    designReady: Boolean(designReviewConfirmed),
    resultsReady: ready,
    graphsReady: ready,
    reportReady: ready,
    results_summary: ready ? 'готово' : '',
    graphs_summary: ready ? 'готово' : '',
    report_summary: ready ? 'готово' : '',
  };
}

export function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
