const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

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

export async function getDataset(id) {
  const response = await fetch(`${API_URL}/datasets/${id}`);
  if (!response.ok) throw new Error("Failed to fetch dataset");
  return response.json();
}

export async function exportReport(payload) {
  const response = await fetch(`${API_URL}/wizard/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to export report");
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

export async function getAnalysisResults(datasetId, runId) {
  const response = await fetch(`${API_URL}/analysis/run/${runId}?dataset_id=${datasetId}`);
  if (!response.ok) throw new Error("Failed to get analysis results");
  return response.json();
}

export async function modifyDataset(id, modifications) {
  const response = await fetch(`${API_URL}/datasets/${id}/modify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actions: modifications }),
  });
  if (!response.ok) throw new Error("Failed to modify dataset");
  return response.json();
}

export async function reparseDataset(id, something, sheetName) {
  const response = await fetch(`${API_URL}/datasets/${id}/reparse?sheet=${encodeURIComponent(sheetName)}`, {
    method: "POST"
  });
  if (!response.ok) throw new Error("Reparse failed");
  return response.json();
}

export async function scanDataset(id) {
  const response = await fetch(`${API_URL}/quality/scan/${id}`);
  if (!response.ok) throw new Error("Scan failed");
  return response.json();
}

export async function getScanReport(id) {
  const response = await fetch(`${API_URL}/datasets/${id}/scan_report`);
  if (!response.ok) throw new Error("Scan report failed");
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

    const response = await fetch(`${API_URL}/wizard/export`, {
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

export function getPDFExportUrl(datasetId, variable, groupColumn = 'Group') {
  return `${API_URL}/wizard/export/${datasetId}/${encodeURIComponent(variable)}?group_column=${encodeURIComponent(groupColumn)}`;
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
