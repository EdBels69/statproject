export const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

async function request(url, options = {}, { timeoutMs = 30000, timeoutError } = {}) {
  const externalSignal = options?.signal;
  const controller = new AbortController();
  const signal = controller.signal;

  let timeoutId;
  if (typeof timeoutMs === 'number' && Number.isFinite(timeoutMs) && timeoutMs > 0) {
    timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  }

  const onAbort = () => controller.abort();
  if (externalSignal) {
    if (externalSignal.aborted) controller.abort();
    else externalSignal.addEventListener('abort', onAbort, { once: true });
  }

  try {
    return await fetch(url, { ...options, signal });
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw new Error(timeoutError || 'Запрос превысил лимит времени');
    }
    throw e;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
    if (externalSignal) externalSignal.removeEventListener('abort', onAbort);
  }
}

async function readError(response) {
  const ct = String(response?.headers?.get('content-type') || '').toLowerCase();
  if (ct.includes('application/json')) {
    const err = await response.json().catch(() => ({}));
    return err?.detail || err?.message || null;
  }
  const text = await response.text().catch(() => '');
  return text || null;
}

export function getAlphaSetting() {
  const savedAlpha = localStorage.getItem('statwizard_alpha');
  return savedAlpha ? parseFloat(savedAlpha) : 0.05;
}

export async function uploadDataset(file) {
  const formData = new FormData();
  formData.append("file", file);
  let response;
  try {
    response = await request(`${API_URL}/datasets`, {
      method: "POST",
      body: formData,
    }, { timeoutMs: 180000, timeoutError: 'Загрузка файла занимает слишком много времени' });
  } catch (e) {
    const message = e?.message ? String(e.message) : '';
    if (message && message !== 'Failed to fetch') {
      throw new Error(message);
    }
    throw new Error("Не удалось подключиться к серверу");
  }
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось загрузить файл");
  }
  return response.json();
}

export async function uploadPrimaryDataset() {
  let response;
  try {
    response = await request(`${API_URL}/datasets/demo/primary`, {
      method: "POST",
    }, { timeoutMs: 180000, timeoutError: 'Загрузка демо-файла занимает слишком много времени' });
  } catch (e) {
    const message = e?.message ? String(e.message) : '';
    if (message && message !== 'Failed to fetch') {
      throw new Error(message);
    }
    throw new Error("Не удалось подключиться к серверу");
  }
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось загрузить демо-файл данных");
  }
  return response.json();
}

export async function getDatasets() {
  let response;
  try {
    response = await request(`${API_URL}/datasets`, {}, { timeoutMs: 30000 });
  } catch {
    throw new Error("Не удалось подключиться к серверу");
  }
  if (!response.ok) {
    throw new Error("Не удалось загрузить список файлов данных");
  }
  return response.json();
}

export async function deleteDataset(id) {
  let response;
  try {
    response = await request(`${API_URL}/datasets/${id}`, {
      method: "DELETE",
    }, { timeoutMs: 60000 });
  } catch {
    throw new Error("Не удалось подключиться к серверу");
  }
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось удалить файл данных");
  }
  return response.json();
}

export async function getWizardRecommendation(data) {
  const response = await request(`${API_URL}/wizard/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }, { timeoutMs: 60000, timeoutError: 'Рекомендация строится слишком долго' });
  if (!response.ok) throw new Error("Не удалось получить рекомендацию");
  return response.json();
}

export async function applyStrategy(data) {
  const response = await request(`${API_URL}/wizard/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  }, { timeoutMs: 240000, timeoutError: 'Анализ занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось применить стратегию");
  return response.json();
}

export async function listDatasets() {
  const response = await request(`${API_URL}/datasets`, {}, { timeoutMs: 30000 });
  if (!response.ok) throw new Error("Не удалось загрузить список файлов данных");
  return response.json();
}

export async function getDataset(id, page = 1, limit = 100) {
  const params = new URLSearchParams();
  if (page !== undefined && page !== null) params.set('page', String(page));
  if (limit !== undefined && limit !== null) params.set('limit', String(limit));

  const response = await request(`${API_URL}/datasets/${id}?${params.toString()}`, {}, { timeoutMs: 60000, timeoutError: 'Загрузка данных занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось загрузить файл данных");
  return response.json();
}

export async function listDatasetColumns(datasetId, opts = {}) {
  const params = new URLSearchParams();
  if (opts?.q) params.set('q', String(opts.q));
  if (opts?.offset !== undefined && opts?.offset !== null) params.set('offset', String(opts.offset));
  if (opts?.limit !== undefined && opts?.limit !== null) params.set('limit', String(opts.limit));

  const qs = params.toString();
  const response = await request(`${API_URL}/datasets/${datasetId}/columns${qs ? `?${qs}` : ''}`, {}, { timeoutMs: 60000 });
  if (!response.ok) throw new Error('Не удалось загрузить список колонок');
  return response.json();
}

export async function exportReport(payload) {
  const response = await request(`${API_URL}/analysis/report/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, { timeoutMs: 240000, timeoutError: 'Экспорт PDF занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось экспортировать отчёт");
  return await response.blob();
}

export async function exportDocx(payload) {
  const response = await request(`${API_URL}/analysis/export/docx`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, { timeoutMs: 240000, timeoutError: 'Экспорт DOCX занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось экспортировать DOCX");
  return await response.blob();
}

export async function getSheets(datasetId) {
  const response = await request(`${API_URL}/datasets/${datasetId}/sheets`, {}, { timeoutMs: 60000 });
  if (!response.ok) throw new Error("Не удалось загрузить листы");
  return response.json();
}

export async function getDatasetContent(datasetId, opts = {}) {
  const params = new URLSearchParams();
  if (opts?.sheet) params.set('sheet', String(opts.sheet));
  if (opts?.page !== undefined && opts?.page !== null) params.set('page', String(opts.page));
  if (opts?.limit !== undefined && opts?.limit !== null) params.set('limit', String(opts.limit));
  if (opts?.colOffset !== undefined && opts?.colOffset !== null) params.set('col_offset', String(opts.colOffset));
  if (opts?.colLimit !== undefined && opts?.colLimit !== null) params.set('col_limit', String(opts.colLimit));

  const qs = params.toString();
  const url = `${API_URL}/datasets/${datasetId}/content${qs ? `?${qs}` : ''}`;

  const response = await request(url, {}, { timeoutMs: 60000, timeoutError: 'Загрузка таблицы занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось загрузить содержимое файла данных");
  return response.json();
}

export async function cleanColumn(id, column, action) {
  const response = await request(`${API_URL}/datasets/${id}/clean_column`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ column, action }),
  }, { timeoutMs: 120000, timeoutError: 'Операция очистки занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось очистить колонку");
  return response.json();
}

export async function imputeMice(id, columns, options = {}) {
  const response = await request(`${API_URL}/datasets/${id}/impute_mice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ columns, ...options }),
  }, { timeoutMs: 240000, timeoutError: 'Импутация занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось выполнить импутацию MICE");
  return response.json();
}

export async function cloneDatasetForPreparation(datasetId) {
  const response = await request(`${API_URL}/datasets/${datasetId}/prepare/clone`, {
    method: 'POST',
  }, { timeoutMs: 180000, timeoutError: 'Подготовка копии занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось создать подготовленную копию');
  }
  return response.json();
}

export async function getPrepareHistory(datasetId) {
  const response = await request(`${API_URL}/datasets/${datasetId}/prepare/history`, {}, { timeoutMs: 30000 });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось загрузить историю подготовки');
  }
  return response.json();
}

export async function undoPrepare(datasetId, opts = {}) {
  const params = new URLSearchParams();
  if (opts?.page !== undefined && opts?.page !== null) params.set('page', String(opts.page));
  if (opts?.limit !== undefined && opts?.limit !== null) params.set('limit', String(opts.limit));
  const qs = params.toString();

  const response = await request(`${API_URL}/datasets/${datasetId}/prepare/undo${qs ? `?${qs}` : ''}`, {
    method: 'POST',
  }, { timeoutMs: 120000, timeoutError: 'Откат занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось откатить изменения');
  }
  return response.json();
}

export async function computeDatasetColumn(datasetId, payload) {
  const response = await request(`${API_URL}/datasets/${datasetId}/compute_column`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  }, { timeoutMs: 120000, timeoutError: 'Расчёт колонки занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось добавить колонку');
  }
  return response.json();
}

/* -- ANALYSIS PROTOCOL API -- */

export async function suggestAnalysisDesign(datasetId, goal, variables) {
  const response = await request(`${API_URL}/analysis/design`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, goal, variables }),
  }, { timeoutMs: 60000, timeoutError: 'Формирование протокола занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось предложить дизайн анализа");
  return response.json();
}

export async function runAnalysisProtocol(datasetId, protocol) {
  const response = await request(`${API_URL}/analysis/protocol/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, protocol, alpha: getAlphaSetting() }),
  }, { timeoutMs: 240000, timeoutError: 'Запуск протокола занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось запустить протокол анализа");
  return response.json();
}

export async function checkAssumptions({ datasetId, methodId, config, alpha, signal } = {}) {
  const payload = {
    dataset_id: datasetId,
    method_id: methodId,
    config: config || {},
    alpha: (alpha ?? getAlphaSetting())
  };

  const response = await request(`${API_URL}/analysis/assumptions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  }, { timeoutMs: 60000, timeoutError: 'Проверка предпосылок занимает слишком много времени' });

  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось проверить предпосылки");
  }

  return response.json();
}

export async function getAnalysisResults(datasetId, runId) {
  const response = await request(`${API_URL}/analysis/run/${runId}?dataset_id=${datasetId}`, {}, { timeoutMs: 240000, timeoutError: 'Получение результатов занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось получить результаты анализа");
  return response.json();
}

export function getProtocolReportUrl(datasetId, runId, format, opts = {}) {
  const params = new URLSearchParams();
  params.set('dataset_id', String(datasetId));
  if (opts?.style) params.set('style', String(opts.style));
  if (opts?.density) params.set('density', String(opts.density));
  if (opts?.accent) params.set('accent', String(opts.accent));
  if (Array.isArray(opts?.sections) && opts.sections.length) params.set('sections', opts.sections.join(','));
  if (Array.isArray(opts?.order) && opts.order.length) params.set('order', opts.order.join(','));
  return `${API_URL}/analysis/protocol/report/${encodeURIComponent(String(runId))}/${encodeURIComponent(String(format))}?${params.toString()}`;
}

export async function downloadProtocolReport(datasetId, runId, format, opts = {}) {
  const url = getProtocolReportUrl(datasetId, runId, format, opts);
  const response = await request(url, {}, { timeoutMs: 240000, timeoutError: 'Экспорт отчёта занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось скачать отчёт');
  }
  if (String(format).toLowerCase() === 'html') return response.text();
  return response.blob();
}

export async function listProtocolArtifacts(datasetId, runId) {
  const response = await request(`${API_URL}/analysis/protocol/artifacts/${encodeURIComponent(String(runId))}?dataset_id=${encodeURIComponent(String(datasetId))}`, {}, { timeoutMs: 60000 });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось получить список файлов');
  }
  return response.json();
}

export async function downloadProtocolArtifact(datasetId, runId, name) {
  const params = new URLSearchParams();
  params.set('dataset_id', String(datasetId));
  params.set('name', String(name));
  const response = await request(`${API_URL}/analysis/protocol/artifacts/${encodeURIComponent(String(runId))}/download?${params.toString()}`, {}, { timeoutMs: 240000, timeoutError: 'Скачивание файла занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось скачать файл');
  }
  return response.blob();
}

export async function modifyDataset(id, modifications, options = {}) {
  const params = new URLSearchParams();
  if (options?.page !== undefined && options?.page !== null) params.set('page', String(options.page));
  if (options?.limit !== undefined && options?.limit !== null) params.set('limit', String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await request(`${API_URL}/datasets/${id}/modify${suffix}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actions: modifications }),
  }, { timeoutMs: 180000, timeoutError: 'Применение изменений занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось изменить файл данных");
  return response.json();
}

export async function reparseDataset(id, headerRow = 0, sheetName, options = {}) {
  const params = new URLSearchParams();
  if (options?.page !== undefined && options?.page !== null) params.set('page', String(options.page));
  if (options?.limit !== undefined && options?.limit !== null) params.set('limit', String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const response = await request(`${API_URL}/datasets/${id}/reparse${suffix}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ header_row: headerRow, sheet_name: sheetName ?? null }),
  }, { timeoutMs: 180000, timeoutError: 'Перепарсивание занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось перепарсить файл данных");
  return response.json();
}

export async function scanDataset(id) {
  const response = await request(`${API_URL}/quality/${id}/scan`, {}, { timeoutMs: 240000, timeoutError: 'Проверка качества занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось выполнить проверку качества");
  return response.json();
}

export async function getScanReport(id) {
  const response = await request(`${API_URL}/datasets/${id}/scan_report`, {}, { timeoutMs: 60000 });
  if (!response.ok) throw new Error("Не удалось загрузить отчёт проверки качества");
  return response.json();
}

export async function getVariableMapping(datasetId) {
  const response = await request(`${API_URL}/datasets/${datasetId}/variable_mapping`, {}, { timeoutMs: 60000 });
  if (!response.ok) throw new Error("Не удалось загрузить сопоставление переменных");
  return response.json();
}

export async function putVariableMapping(datasetId, mapping) {
  const response = await request(`${API_URL}/datasets/${datasetId}/variable_mapping`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping: mapping || {} })
  }, { timeoutMs: 60000 });
  if (!response.ok) throw new Error("Не удалось сохранить сопоставление переменных");
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
        method: varResult.method?.name || 'Статистический тест',
        conclusion: varResult.conclusion || 'Анализ завершён',
        groups: varResult.groups || [],
        plot_stats: varResult.plot_stats || {}
      }
      : {
        p_value: 0,
        stat_value: 0,
        significant: false,
        method: 'Пакетный анализ',
        conclusion: 'Проанализировано несколько переменных',
        groups: [],
        plot_stats: {}
      };

    const payload = {
      results,
      variables: { target: selectedVar || 'Несколько', group: 'Группа' },
      dataset_id: datasetId
    };

    const response = await request(`${API_URL}/analysis/report/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, { timeoutMs: 240000, timeoutError: 'Экспорт PDF занимает слишком много времени' });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Экспорт не удался: ${errorText}`);
    }

    return response.blob();
  } catch (error) {
    console.error('Download report error:', error);
    throw new Error(error.message || 'Не удалось экспортировать отчёт');
  }
}

/* -- KNOWLEDGE API -- */

export async function getKnowledgeTerms() {
  const response = await request(`${API_URL}/v2/knowledge/terms`, {}, { timeoutMs: 30000 });
  if (!response.ok) throw new Error("Не удалось загрузить термины справки");
  return response.json();
}

export async function getKnowledgeTerm(term, level = 'junior') {
  const params = new URLSearchParams();
  if (level) params.set('level', level);

  const response = await request(`${API_URL}/v2/knowledge/terms/${encodeURIComponent(term)}?${params.toString()}`, {}, { timeoutMs: 30000 });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось загрузить объяснение термина");
  }
  return response.json();
}

export async function getKnowledgeTests() {
  const response = await request(`${API_URL}/v2/knowledge/tests`, {}, { timeoutMs: 30000 });
  if (!response.ok) throw new Error("Не удалось загрузить список тестов справки");
  return response.json();
}

export async function getKnowledgeManual(lang = 'ru') {
  const params = new URLSearchParams();
  if (lang) params.set('lang', lang);
  const response = await request(`${API_URL}/v2/knowledge/manual?${params.toString()}`, {}, { timeoutMs: 30000 });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось загрузить мануал');
  }
  return response.json();
}

export async function getKnowledgeTest(testId, { level = 'junior', shapiro_p, levene_p, signal } = {}) {
  const params = new URLSearchParams();
  if (level) params.set('level', level);
  if (shapiro_p !== undefined && shapiro_p !== null) params.set('shapiro_p', String(shapiro_p));
  if (levene_p !== undefined && levene_p !== null) params.set('levene_p', String(levene_p));

  const response = await request(`${API_URL}/v2/knowledge/tests/${encodeURIComponent(testId)}?${params.toString()}`, { signal }, { timeoutMs: 30000 });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось загрузить объяснение теста");
  }
  return response.json();
}

export async function interpretEffectSize(type, value) {
  const params = new URLSearchParams();
  params.set('type', type);
  params.set('value', String(value));

  const response = await request(`${API_URL}/v2/knowledge/effect-size?${params.toString()}`, {}, { timeoutMs: 30000 });
  if (!response.ok) throw new Error("Не удалось интерпретировать размер эффекта");
  return response.json();
}

export async function getPowerInfo(power) {
  const params = new URLSearchParams();
  params.set('power', String(power));

  const response = await request(`${API_URL}/v2/knowledge/power?${params.toString()}`, {}, { timeoutMs: 30000 });
  if (!response.ok) throw new Error("Не удалось загрузить справку по мощности");
  return response.json();
}

export function getPDFExportUrl(datasetId, variable, groupColumn = 'Group') {
  return `${API_URL}/analysis/report/${datasetId}/pdf?target_col=${encodeURIComponent(variable)}&group_col=${encodeURIComponent(groupColumn)}`;
}

export async function reprocessDataset(id) {
  const response = await request(`${API_URL}/datasets/${id}/reprocess`, {
    method: "POST"
  }, { timeoutMs: 180000, timeoutError: 'Переработка занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось переработать файл данных");
  return response.json();
}

export async function runBatchAnalysis(datasetId, targets, groupColumn) {
  const response = await request(`${API_URL}/analysis/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dataset_id: datasetId, target_columns: targets, group_column: groupColumn, alpha: getAlphaSetting() }),
  }, { timeoutMs: 240000, timeoutError: 'Пакетный анализ занимает слишком много времени' });
  if (!response.ok) throw new Error("Не удалось выполнить пакетный анализ");
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
  const response = await request(`${API_V2_URL}/mixed-effects`, {
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
  }, { timeoutMs: 240000, timeoutError: 'Анализ смешанных эффектов занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось выполнить анализ смешанных эффектов");
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
  const response = await request(`${API_V2_URL}/clustered-correlation`, {
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
  }, { timeoutMs: 240000, timeoutError: 'Корреляционный анализ занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось выполнить кластерный корреляционный анализ");
  }
  return response.json();
}

/**
 * Execute v2 analysis protocol (supports advanced methods)
 */
export async function executeProtocolV2(datasetId, protocol, alpha = null) {
  const response = await request(`${API_V2_URL}/analysis/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      protocol,
      alpha: alpha ?? getAlphaSetting()
    }),
  }, { timeoutMs: 240000, timeoutError: 'Выполнение протокола занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось выполнить протокол");
  }
  return response.json();
}

/**
 * Get AI-powered test suggestions
 */
export async function getAISuggestions(datasetId, currentProtocol = []) {
  const response = await request(`${API_V2_URL}/ai/suggest-tests`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      protocol: currentProtocol
    }),
  }, { timeoutMs: 60000, timeoutError: 'AI-подсказки строятся слишком долго' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось получить AI-подсказки");
  }
  return response.json();
}

export async function aiAnalyzeDesign(datasetId, text, { protocol = null, preferences = null } = {}) {
  const response = await request(`${API_V2_URL}/ai/analyze-design`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: datasetId,
      text,
      protocol,
      preferences,
    }),
  }, { timeoutMs: 60000, timeoutError: 'ИИ слишком долго собирает дизайн исследования' });

  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || 'Не удалось разобрать дизайн исследования');
  }

  return response.json();
}

/**
 * Get available analysis templates
 */
export async function getAnalysisTemplates(goal = null) {
  const params = goal ? `?goal=${encodeURIComponent(goal)}` : '';
  const response = await request(`${API_V2_URL}/analysis/templates${params}`, {}, { timeoutMs: 30000 });
  if (!response.ok) throw new Error("Не удалось загрузить шаблоны");
  return response.json();
}

/**
 * Design analysis from template
 */
export async function designAnalysisFromTemplate(datasetId, goal, variables, templateId = null) {
  const response = await request(`${API_V2_URL}/analysis/design`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      goal,
      template_id: templateId,
      variables
    }),
  }, { timeoutMs: 60000, timeoutError: 'Формирование протокола занимает слишком много времени' });
  if (!response.ok) {
    const detail = await readError(response);
    throw new Error(detail || "Не удалось собрать анализ из шаблона");
  }
  return response.json();
}
