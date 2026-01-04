const API_URL = "http://localhost:8000/api/v1";

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || response.statusText || "Request failed");
  }
  return response.json() as Promise<T>;
}

export interface ColumnInfo {
  name: string;
  type: string;
  missing_count: number;
  unique_count: number;
  example?: unknown;
}

export interface DatasetProfile {
  row_count: number;
  col_count: number;
  columns: ColumnInfo[];
  head: Record<string, unknown>[];
  page: number;
  total_pages: number;
}

export interface DatasetUploadResponse {
  id: string;
  filename: string;
  profile: DatasetProfile;
}

export interface AnalysisJobPayload {
  dataset_id: string;
  target_column: string;
  feature_column: string;
  method_id?: string | null;
  is_paired?: boolean;
  job_type?: "analysis" | "report";
}

export interface JobStatus {
  id: string;
  dataset_id: string;
  task_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  result_path?: string | null;
  log_path?: string | null;
  error?: string | null;
  payload?: Record<string, unknown>;
}

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
  return request(`${API_URL}/wizard/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function applyStrategy(data: any) {
  return request(`${API_URL}/wizard/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function listDatasets() {
  return request<{ id: string; filename: string }[]>(`${API_URL}/datasets`);
}

export async function getDataset(id: string, page?: number, limit?: number) {
  const query = new URLSearchParams();
  if (page) query.append("page", page.toString());
  if (limit) query.append("limit", limit.toString());
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<DatasetProfile>(`${API_URL}/datasets/${id}${suffix}`);
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
  return request<DatasetProfile>(`${API_URL}/datasets/${id}/modify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(modifications),
  });
}

export async function reparseDataset(id: string, headerRow: number, sheetName?: string) {
  return request<DatasetProfile>(`${API_URL}/datasets/${id}/reparse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ header_row: headerRow, sheet_name: sheetName })
  });
}

export async function scanDataset(id: string) {
  return request(`${API_URL}/quality/scan/${id}`);
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
  return request(`${API_URL}/datasets/${id}/reprocess`, {
    method: "POST"
  });
}

export async function runBatchAnalysis(datasetId: string, targets: string[], groupColumn: string) {
  return request(`${API_URL}/analyze/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, target_columns: targets, group_column: groupColumn }),
  });
}

export async function enqueueAnalysisJob(payload: AnalysisJobPayload): Promise<JobStatus> {
  return request<JobStatus>(`${API_URL}/jobs/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getJobStatus(datasetId: string, jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`${API_URL}/jobs/${datasetId}/${jobId}`);
}
