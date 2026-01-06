const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

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

export async function getDatasets() {
  const response = await fetch(`${API_URL}/datasets`);
  if (!response.ok) {
    throw new Error("Failed to fetch datasets");
  }
  return response.json();
}

export async function deleteDataset(id: string) {
  const response = await fetch(`${API_URL}/datasets/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete dataset");
  }
  return response.json();
}

export async function autoClassifyVariables(id: string) {
  const response = await fetch(`${API_URL}/datasets/${id}/auto_classify`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error("Failed to auto-classify variables");
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

export async function cleanColumn(id: string, column: string, action: string) {
  const response = await fetch(`${API_URL}/datasets/${id}/clean_column`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ column, action }),
  });
  if (!response.ok) throw new Error("Failed to clean column");
  return response.json();
}

/* -- ANALYSIS PROTOCOL API -- */

export async function suggestAnalysisDesign(datasetId: string, goal: string, variables: any) {
  const response = await fetch(`${API_URL}/analysis/design`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, goal, variables }),
  });
  if (!response.ok) throw new Error("Failed to suggest analysis design");
  return response.json();
}

export async function runAnalysisProtocol(datasetId: string, protocol: any) {
  const response = await fetch(`${API_URL}/analysis/protocol/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, protocol }),
  });
  if (!response.ok) throw new Error("Failed to run analysis protocol");
  return response.json(); // Expected { run_id: "...", status: "completed" }
}

export async function getAnalysisResults(datasetId: string, runId: string) {
  // Note: backend requires dataset_id param for hierarchy lookup
  const response = await fetch(`${API_URL}/analysis/run/${runId}?dataset_id=${datasetId}`);
  if (!response.ok) throw new Error("Failed to get analysis results");
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

export async function getReportHtmlPreview(datasetId: string, batchResult: any, selectedVar: string | null) {
  // Construct payload similar to export
  const results = {};

  // Transform batchResult.results (Map) into Report JSON Structure
  if (batchResult && batchResult.results) {
    Object.entries(batchResult.results).forEach(([key, val]) => {
      results[`test_${key}`] = {
        ...val,
        type: "hypothesis_test",
        target: key
      };
    });
  }

  if (batchResult && batchResult.descriptives) {
    // Group descriptives by variable
    const groups = [...new Set(batchResult.descriptives.map(d => d.group))];
    const vars = [...new Set(batchResult.descriptives.map(d => d.variable))];

    vars.forEach(v => {
      const stats = {};
      batchResult.descriptives.filter(d => d.variable === v).forEach(d => {
        stats[d.group] = d;
      });
      results[`desc_${v}`] = {
        type: "descriptive_compare",
        target: v,
        stats: stats
      };
    });
  }

  const payload = {
    dataset_name: `Dataset ${datasetId}`,
    results: results,
    export_settings: { selected_var: selectedVar } // Optional
  };

  const response = await fetch(`${API_URL}/analysis/report/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error("Failed to generate HTML report");
  return response.text();
}

export async function downloadBatchReport(datasetId: string, batchResult: any, selectedVar: string | null) {
  try {
    // Identical payload construction as HTML Preview
    // Construct payload similar to export
    const results = {};

    // Transform batchResult.results (Map) into Report JSON Structure
    if (batchResult && batchResult.results) {
      Object.entries(batchResult.results).forEach(([key, val]) => {
        results[`test_${key}`] = {
          ...val,
          type: "hypothesis_test",
          target: key
        };
      });
    }

    if (batchResult && batchResult.descriptives) {
      // Group descriptives by variable
      const vars = [...new Set(batchResult.descriptives.map(d => d.variable))];

      vars.forEach(v => {
        const stats = {};
        batchResult.descriptives.filter(d => d.variable === v).forEach(d => {
          stats[d.group] = d;
        });
        results[`desc_${v}`] = {
          type: "descriptive_compare",
          target: v,
          stats: stats
        };
      });
    }

    const payload = {
      dataset_name: `Dataset ${datasetId}`,
      results: results,
      export_settings: {}
    };

    const response = await fetch(`${API_URL}/analysis/report/word/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error("Failed to generate report word preview");
    }
    return response.blob();
  } catch (error) {
    console.error("Preview failed:", error);
    throw error;
  }
}

export async function runCorrelationMatrix(datasetId: string, features: string[], method: string, cluster: boolean) {
  const response = await fetch(`${API_URL}/analysis/correlation_matrix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      features: features,
      method: method,
      cluster_variables: cluster
    }),
  });

  if (!response.ok) {
    const err = await response.json();
    throw new Error(err.detail || "Correlation Matrix Analysis failed");
  }
  return response.json();
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

export async function runBatchAnalysis(datasetId: string, targets: string[], groupColumn: string, options: any = {}) {
  const response = await fetch(`${API_URL}/analysis/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      target_columns: targets,
      group_column: groupColumn,
      options: options
    }),
  });
  if (!response.ok) throw new Error("Batch analysis failed");
  return response.json();
}

export async function downloadWordReport(datasetId: string, runId: string): Promise<Blob> {
  const response = await fetch(`${API_URL}/analysis/report/${runId}/word?dataset_id=${datasetId}`);
  if (!response.ok) throw new Error("Failed to download Word report");
  return response.blob();
}

export function getWordReportUrl(datasetId: string, runId: string): string {
  return `${API_URL}/analysis/report/${runId}/word?dataset_id=${datasetId}`;
}

export async function analyzeDatasetPrep(id: string) {
  const response = await fetch(`${API_URL}/datasets/${id}/prep/analyze`);
  if (!response.ok) throw new Error("Prep analysis failed");
  return response.json();
}

export async function applyDatasetPrep(id: string, action: string, params: any = {}) {
  const response = await fetch(`${API_URL}/datasets/${id}/prep/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, params }),
  });
  if (!response.ok) throw new Error("Prep apply failed");
  return response.json();
}

export async function generateProtocol(description: string) {
  const response = await fetch(`${API_URL}/protocol/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!response.ok) throw new Error("Failed to generate protocol");
  return response.json();
}

export async function previewData(datasetId: string, limit: number, offset: number, filters: any[]) {
  const response = await fetch(`${API_URL}/datasets/${datasetId}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ limit, offset, filters }),
  });
  if (!response.ok) throw new Error("Preview failed");
  return response.json();
}

export async function createSubset(datasetId: string, newName: string, filters: any[]) {
  const response = await fetch(`${API_URL}/datasets/${datasetId}/subset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_name: newName, filters }),
  });
  if (!response.ok) throw new Error("Subset creation failed");
  return response.json();
}