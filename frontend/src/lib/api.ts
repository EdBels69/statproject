const API_URL = "http://localhost:8000/api/v1";

export async function uploadDataset(file) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_URL}/datasets`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = errorText;
        try {
            const errorJson = JSON.parse(errorText);
            if (errorJson.detail) {
                errorMessage = errorJson.detail;
            }
        } catch (e) {
            // Not JSON
        }
        throw new Error(errorMessage || "Upload failed");
    }

    return response.json();
}

export async function reparseDataset(id, headerRow, sheetName = null) {
    const body = { header_row: headerRow };
    if (sheetName) body.sheet_name = sheetName;

    const response = await fetch(`${API_URL}/datasets/${id}/reparse`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        const errorText = await response.text();
        let errorMessage = errorText;
        try {
            const errorJson = JSON.parse(errorText);
            if (errorJson.detail) {
                errorMessage = errorJson.detail;
            }
        } catch (e) {
            // Not JSON, use raw text
        }
        throw new Error(errorMessage || "Reparse failed");
    }

    return response.json();
}

export async function recommendMethod(datasetId, targetCol, features) {
    const response = await fetch(`${API_URL}/analyze/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            dataset_id: datasetId,
            target_column: targetCol,
            features: features
        }),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
}

export async function runAnalysis(datasetId, targetCol, features, methodOverride = null) {
    const response = await fetch(`${API_URL}/analyze/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            dataset_id: datasetId,
            target_column: targetCol,
            features: features,
            method_override: methodOverride
        }),
    });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
}
// Helper to get raw URL for GET request
export function getReportUrl(datasetId, targetCol, groupCol, methodId) {
    const params = new URLSearchParams({
        dataset_id: datasetId,
        target_col: targetCol,
        group_col: groupCol,
        method_id: methodId
    });
    return `${API_URL}/analyze/report/${datasetId}?${params.toString()}`;
}

export async function runBatchAnalysis(datasetId, targetCols, groupCol) {
    const response = await fetch(`${API_URL}/analyze/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            dataset_id: datasetId,
            target_columns: targetCols,
            group_column: groupCol
        }),
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || "Batch analysis failed");
    }
    return response.json();
}

export async function getDataset(datasetId, page = 1, limit = 50) {
    const response = await fetch(`${API_URL}/datasets/${datasetId}?page=${page}&limit=${limit}`);
    if (!response.ok) {
        throw new Error("Dataset not found");
    }
    return response.json();
}

export async function getSheets(id) {
    const response = await fetch(`${API_URL}/datasets/${id}/sheets`);
    if (!response.ok) return []; // fail silent
    return response.json();
}

export async function modifyDataset(id, actions) {
    const response = await fetch(`${API_URL}/datasets/${id}/modify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions })
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Failed to modify dataset' }));
        throw new Error(err.detail || 'Failed to modify dataset');
    }
    return response.json();
}

export async function scanDataset(id) {
    const response = await fetch(`${API_URL}/datasets/${id}/scan`, {
        method: "POST"
    });
    if (!response.ok) throw new Error("Quality scan failed");
    return response.json();
}

export async function getWizardRecommendation(params) {
    const response = await fetch(`${API_URL}/wizard/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
    });
    if (!response.ok) throw new Error("Wizard recommendation failed");
    return response.json();
}
