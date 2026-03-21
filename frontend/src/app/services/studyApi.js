const API_URL = '/api/v1'; // Adjusted to match prefix in routes.py

async function fetchJSON(url, options = {}) {
    const res = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `Request failed with status ${res.status}`);
    }

    return res.json();
}

export const studyApi = {
    getConfig: (datasetId) => fetchJSON(`${API_URL}/study/${datasetId}/config`),

    saveConfig: (datasetId, config) => fetchJSON(`${API_URL}/study/${datasetId}/config`, {
        method: 'POST',
        body: JSON.stringify(config),
    }),

    suggestHypotheses: (datasetId) => fetchJSON(`${API_URL}/study/${datasetId}/suggest-hypotheses`, {
        method: 'POST',
    }),
};
