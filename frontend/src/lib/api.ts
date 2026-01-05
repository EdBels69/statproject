const API_URL = "http://localhost:8000/api/v1";

export async function uploadDataset(file: File) {
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

export async function getWizardRecommendation(data: any) {
  const response = await fetch(`${API_URL}/wizard/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) throw new Error("Recommendation failed");
  return response.json();
}

export async function listMethods(includeExperimental: boolean = false) {
  const params = includeExperimental ? "?include_experimental=true" : "";
  const response = await fetch(`${API_URL}/analyze/methods${params}`);
  if (!response.ok) throw new Error("Failed to list methods");
  return response.json();
}

export async function applyStrategy(data: any) {
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

export async function getDataset(id: string) {
  const response = await fetch(`${API_URL}/datasets/${id}`);
  if (!response.ok) throw new Error("Failed to fetch dataset");
  return response.json();
}

export async function exportReport(payload: { results: any, variables: any, dataset_id: string }) {
  const response = await fetch(`${API_URL}/wizard/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to export report");
  return await response.blob();
}

export async function getSheets(datasetId: string) {
  const response = await fetch(`${API_URL}/datasets/${datasetId}/sheets`);
  if (!response.ok) throw new Error("Failed to fetch sheets");
  return response.json();
}

export async function getDatasetContent(datasetId: string, sheetName?: string) {
  const url = sheetName
    ? `${API_URL}/datasets/${datasetId}/content?sheet=${encodeURIComponent(sheetName)}`
    : `${API_URL}/datasets/${datasetId}/content`;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch dataset content");
  return response.json();
}

export async function modifyDataset(id: string, modifications: any) {
  const response = await fetch(`${API_URL}/datasets/${id}/modify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(modifications),
  });
  if (!response.ok) throw new Error("Failed to modify dataset");
  return response.json();
}

export async function reparseDataset(id: string, something: any, sheetName: string) {
  const response = await fetch(`${API_URL}/datasets/${id}/reparse?sheet=${encodeURIComponent(sheetName)}`, {
    method: "POST"
  });
  if (!response.ok) throw new Error("Reparse failed");
  return response.json();
}

export async function scanDataset(id: string) {
  const response = await fetch(`${API_URL}/quality/scan/${id}`);
  if (!response.ok) throw new Error("Scan failed");
  return response.json();
}

export async function downloadBatchReport(datasetId: string, batchResult: any, selectedVar: string | null) {
  try {
    // Prepare export data from batch results
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

export function getPDFExportUrl(datasetId: string, variable: string, groupColumn: string = 'Group') {
  return `${API_URL}/wizard/export/${datasetId}/${encodeURIComponent(variable)}?group_column=${encodeURIComponent(groupColumn)}`;
}

export async function reprocessDataset(id: string) {
  const response = await fetch(`${API_URL}/datasets/${id}/reprocess`, {
    method: "POST"
  });
  if (!response.ok) throw new Error("Reprocess failed");
  return response.json();
}

export async function runBatchAnalysis(datasetId: string, targets: string[], groupColumn: string) {
  const response = await fetch(`${API_URL}/analyze/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, target_columns: targets, group_column: groupColumn }),
  });
  if (!response.ok) throw new Error("Batch analysis failed");
  return response.json();
}
