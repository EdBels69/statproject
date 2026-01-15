export const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

export function getAlphaSetting() {
  const savedAlpha = localStorage.getItem('statwizard_alpha');
  return savedAlpha ? parseFloat(savedAlpha) : 0.05;
}

export async function uploadDataset(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}/datasets`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return response.json();
}

export async function getDatasets() {
  const response = await fetch(`${API_URL}/datasets`);
  if (!response.ok) {
    throw new Error("Failed to fetch datasets");
  }
  return response.json();
}

export async function deleteDataset(id) {
  const response = await fetch(`${API_URL}/datasets/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete dataset");
  }
  return response.json();
}

export async function getWizardRecommendation(data) {
  const response = await fetch(`${API_URL}/wizard/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Recommendation failed");
  return response.json();
}

export async function applyStrategy(data) {
  const response = await fetch(`${API_URL}/wizard/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Apply strategy failed");
  return response.json();
}

export async function listDatasets() {
  const response = await fetch(`${API_URL}/datasets`);
  if (!response.ok) throw new Error("Failed to list datasets");
  return response.json();
}

export async function getDataset(id, page = 1, limit = 100) {
  const params = new URLSearchParams();
  if (page !== undefined && page !== null) params.set('page', String(page));
  if (limit !== undefined && limit !== null) params.set('limit', String(limit));

  const response = await fetch(`${API_URL}/datasets/${id}?${params.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch dataset");
  return response.json();
}

export async function exportReport(payload) {
  const response = await fetch(`${API_URL}/analysis/report/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to export report");
  return await response.blob();
}

export async function exportDocx(payload) {
  const response = await fetch(`${API_URL}/analysis/export/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to export DOCX");
  return await response.blob();
}

export async function getSheets(datasetId) {
  const response = await fetch(`${API_URL}/datasets/${datasetId}/sheets`);
  if (!response.ok) throw new Error("Failed to fetch sheets");
  return response.json();
}

export async function getDatasetContent(datasetId, sheetName) {
  const url = sheetName
    ? `${API_URL}/datasets/${datasetId}/content?sheet=${encodeURIComponent(sheetName)}`
    : `${API_URL}/datasets/${datasetId}/content`;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch dataset content");
  return response.json();
}

export async function cleanColumn(id, column, action) {
  const response = await fetch(`${API_URL}/datasets/${id}/clean_column`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ column, action }),
  });
  if (!response.ok) throw new Error("Failed to clean column");
  return response.json();
}

export async function imputeMice(id, columns, options = {}) {
  const response = await fetch(`${API_URL}/datasets/${id}/impute_mice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ columns, ...options }),
  });
  if (!response.ok) throw new Error("Failed to run MICE imputation");
  return response.json();
}

/* -- ANALYSIS PROTOCOL API -- */

export async function suggestAnalysisDesign(datasetId, goal, variables) {
  const response = await fetch(`${API_URL}/analysis/design`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, goal, variables }),
  });
  if (!response.ok) throw new Error("Failed to suggest analysis design");
  return response.json();
}

export async function runAnalysisProtocol(datasetId, protocol) {
  const response = await fetch(`${API_URL}/analysis/protocol/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, protocol, alpha: getAlphaSetting() }),
  });
  if (!response.ok) throw new Error("Failed to run analysis protocol");
  return response.json();
}

export async function checkAssumptions({ datasetId, methodId, config, alpha, signal } = {}) {
  const payload = {
    dataset_id: datasetId,
    method_id: methodId,
    config: config || {},
    alpha: (alpha ?? getAlphaSetting())
  };

  const response = await fetch(`${API_URL}/analysis/assumptions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to check assumptions");
  }

  return response.json();
}

export async function getAnalysisResults(datasetId, runId) {
  const response = await fetch(`${API_URL}/analysis/run/${runId}?dataset_id=${datasetId}`);
  if (!response.ok) throw new Error("Failed to get analysis results");
  return response.json();
}

export async function modifyDataset(id, modifications, options = {}) {
  const params = new URLSearchParams();
  if (options?.page !== undefined && options?.page !== null) params.set('page', String(options.page));
  if (options?.limit !== undefined && options?.limit !== null) params.set('limit', String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await fetch(`${API_URL}/datasets/${id}/modify${suffix}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actions: modifications }),
  });
  if (!response.ok) throw new Error("Failed to modify dataset");
  return response.json();
}

export async function reparseDataset(id, headerRow = 0, sheetName, options = {}) {
  const params = new URLSearchParams();
  if (options?.page !== undefined && options?.page !== null) params.set('page', String(options.page));
  if (options?.limit !== undefined && options?.limit !== null) params.set('limit', String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await fetch(`${API_URL}/datasets/${id}/reparse${suffix}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ header_row: headerRow, sheet_name: sheetName ?? null }),
  });
  if (!response.ok) throw new Error("Reparse failed");
  return response.json();
}

export async function scanDataset(id) {
  const response = await fetch(`${API_URL}/quality/${id}/scan`);
  if (!response.ok) throw new Error("Scan failed");
  return response.json();
}

export async function getScanReport(id) {
  const response = await fetch(`${API_URL}/datasets/${id}/scan_report`);
  if (!response.ok) throw new Error("Scan report failed");
  return response.json();
}

export async function getVariableMapping(datasetId) {
  const response = await fetch(`${API_URL}/datasets/${datasetId}/variable_mapping`);
  if (!response.ok) throw new Error("Variable mapping load failed");
  return response.json();
}

export async function putVariableMapping(datasetId, mapping) {
  const response = await fetch(`${API_URL}/datasets/${datasetId}/variable_mapping`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping: mapping || {} })
  });
  if (!response.ok) throw new Error("Variable mapping save failed");
  return response.json();
}

export async function downloadBatchReport(datasetId, batchResult, selectedVar) {
  try {
    const varResult = selectedVar && batchResult?.results?.[selectedVar];
    const results = varResult
      ? {
        p_value: varResult.p_value ?? 0,
        stat_value: varResult.stat_value ?? 0,
        significant: varResult.significant ?? false,
        method: varResult.method?.name || 'Statistical Test',
        conclusion: varResult.conclusion || 'Analysis completed',
        groups: varResult.groups || [],
        plot_stats: varResult.plot_stats || {}
      }
      : {
        p_value: 0,
        stat_value: 0,
        significant: false,
        method: 'Batch Analysis',
        conclusion: 'Multiple variables analyzed',
        groups: [],
        plot_stats: {}
      };

    const payload = {
      results,
      variables: { target: selectedVar || 'Multiple', group: 'Group' },
      dataset_id: datasetId
    };

    const response = await fetch(`${API_URL}/analysis/report/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Export failed: ${errorText}`);
    }

    return response.blob();
  } catch (error) {
    console.error('Download report error:', error);
    throw new Error(error.message || 'Failed to export report');
  }
}

/* -- KNOWLEDGE API -- */

export async function getKnowledgeTerms() {
  const response = await fetch(`${API_URL}/v2/knowledge/terms`);
  if (!response.ok) throw new Error("Failed to fetch knowledge terms");
  return response.json();
}

export async function getKnowledgeTerm(term, level = 'junior') {
  const params = new URLSearchParams();
  if (level) params.set('level', level);

  const response = await fetch(`${API_URL}/v2/knowledge/terms/${encodeURIComponent(term)}?${params.toString()}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch term explanation");
  }
  return response.json();
}

export async function getKnowledgeTests() {
  const response = await fetch(`${API_URL}/v2/knowledge/tests`);
  if (!response.ok) throw new Error("Failed to fetch knowledge tests");
  return response.json();
}

export async function getKnowledgeTest(testId, { level = 'junior', shapiro_p, levene_p, signal } = {}) {
  const params = new URLSearchParams();
  if (level) params.set('level', level);
  if (shapiro_p !== undefined && shapiro_p !== null) params.set('shapiro_p', String(shapiro_p));
  if (levene_p !== undefined && levene_p !== null) params.set('levene_p', String(levene_p));

  const response = await fetch(`${API_URL}/v2/knowledge/tests/${encodeURIComponent(testId)}?${params.toString()}`, { signal });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch test rationale");
  }
  return response.json();
}

export async function interpretEffectSize(type, value) {
  const params = new URLSearchParams();
  params.set('type', type);
  params.set('value', String(value));

  const response = await fetch(`${API_URL}/v2/knowledge/effect-size?${params.toString()}`);
  if (!response.ok) throw new Error("Failed to interpret effect size");
  return response.json();
}

export async function getPowerInfo(power) {
  const params = new URLSearchParams();
  params.set('power', String(power));

  const response = await fetch(`${API_URL}/v2/knowledge/power?${params.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch power info");
  return response.json();
}

export function getPDFExportUrl(datasetId, variable, groupColumn = 'Group') {
  return `${API_URL}/analysis/report/${datasetId}/pdf?target_col=${encodeURIComponent(variable)}&group_col=${encodeURIComponent(groupColumn)}`;
}

export async function reprocessDataset(id) {
  const response = await fetch(`${API_URL}/datasets/${id}/reprocess`, {
    method: "POST"
  });
  if (!response.ok) throw new Error("Reprocess failed");
  return response.json();
}

export async function runBatchAnalysis(datasetId, targets, groupColumn) {
  const response = await fetch(`${API_URL}/analysis/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, target_columns: targets, group_column: groupColumn, alpha: getAlphaSetting() }),
  });
  if (!response.ok) throw new Error("Batch analysis failed");
  return response.json();
}

/* ============================================================
   API v2: Advanced Statistical Methods
   ============================================================ */

const API_V2_URL = `${API_URL}/v2`;

/**
 * Run Linear Mixed Model with Time×Group interaction
 */
export async function runMixedEffects(datasetId, {
  outcome,
  timeCol,
  groupCol,
  subjectCol,
  covariates = [],
  randomSlope = false,
  alpha = null
}) {
  const response = await fetch(`${API_V2_URL}/mixed-effects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      outcome,
      time_col: timeCol,
      group_col: groupCol,
      subject_col: subjectCol,
      covariates,
      random_slope: randomSlope,
      alpha: alpha ?? getAlphaSetting()
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Mixed effects analysis failed");
  }
  return response.json();
}

/**
 * Run jYS-style clustered correlation analysis
 */
export async function runClusteredCorrelation(datasetId, {
  variables,
  method = "pearson",
  linkageMethod = "ward",
  nClusters = null,
  distanceThreshold = null,
  showPValues = true,
  alpha = null
}) {
  const response = await fetch(`${API_V2_URL}/clustered-correlation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      variables,
      method,
      linkage_method: linkageMethod,
      n_clusters: nClusters,
      distance_threshold: distanceThreshold,
      show_p_values: showPValues,
      alpha: alpha ?? getAlphaSetting()
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Clustered correlation failed");
  }
  return response.json();
}

/**
 * Execute v2 analysis protocol (supports advanced methods)
 */
export async function executeProtocolV2(datasetId, protocol, alpha = null) {
  const response = await fetch(`${API_V2_URL}/analysis/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      protocol,
      alpha: alpha ?? getAlphaSetting()
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Protocol execution failed");
  }
  return response.json();
}

/**
 * Get AI-powered test suggestions
 */
export async function getAISuggestions(datasetId, currentProtocol = []) {
  const response = await fetch(`${API_V2_URL}/ai/suggest-tests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      protocol: currentProtocol
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "AI suggestions failed");
  }
  return response.json();
}

/**
 * Get available analysis templates
 */
export async function getAnalysisTemplates(goal = null) {
  const params = goal ? `?goal=${encodeURIComponent(goal)}` : '';
  const response = await fetch(`${API_V2_URL}/analysis/templates${params}`);
  if (!response.ok) throw new Error("Failed to fetch templates");
  return response.json();
}

/**
 * Design analysis from template
 */
export async function designAnalysisFromTemplate(datasetId, goal, variables, templateId = null) {
  const response = await fetch(`${API_V2_URL}/analysis/design`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      goal,
      template_id: templateId,
      variables
    }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Template design failed");
  }
  return response.json();
}
