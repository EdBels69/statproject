import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  getAlphaSetting,
  exportDocx,
  exportReport,
  getStudyDesign,
  putStudyDesign,
  executeProtocolV2,
  runBatchAnalysis,
  getDatasetDesignReview,
  confirmDatasetDesignReview,
  revokeDatasetDesignReview,
  applyInteractiveCleaning,
} from './api';

describe('getAlphaSetting', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns default alpha when not set', () => {
    expect(getAlphaSetting()).toBe(0.05);
  });

  it('parses stored alpha', () => {
    localStorage.setItem('clinimetria_alpha', '0.1');
    expect(getAlphaSetting()).toBe(0.1);
  });
});

describe('exportDocx', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('posts to /analysis/export/docx and returns blob', async () => {
    const fakeBlob = new Blob(['docx'], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
    fetch.mockResolvedValue({ ok: true, blob: async () => fakeBlob });

    const payload = { dataset_name: 'ds', filename: 'x.docx', results: { results: {} } };
    const res = await exportDocx(payload);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/analysis\/export\/docx$/),
      expect.objectContaining({ method: 'POST' })
    );
    expect(res).toBe(fakeBlob);
  });

  it('throws when response not ok', async () => {
    fetch.mockResolvedValue({ ok: false, text: async () => 'nope' });

    await expect(exportDocx({ results: {} })).rejects.toThrow('Не удалось экспортировать DOCX');
  });
});

describe('exportReport', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('posts to /analysis/report/pdf and returns blob', async () => {
    const fakeBlob = new Blob(['pdf'], { type: 'application/pdf' });
    fetch.mockResolvedValue({ ok: true, blob: async () => fakeBlob });

    const payload = { dataset_id: 'ds', results: {}, variables: {} };
    const res = await exportReport(payload);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/analysis\/report\/pdf$/),
      expect.objectContaining({ method: 'POST' })
    );
    expect(res).toBe(fakeBlob);
  });
});

describe('getStudyDesign', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('loads study design from dataset endpoint', async () => {
    const payload = { design: { design_type: 'cross_sectional' } };
    fetch.mockResolvedValue({ ok: true, json: async () => payload });

    const res = await getStudyDesign('dataset-1');

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/datasets\/dataset-1\/study_design$/),
      expect.any(Object)
    );
    expect(res).toEqual(payload);
  });
});

describe('putStudyDesign', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('updates study design via dataset endpoint', async () => {
    const payload = { revision: 3, design: { group_column: 'group' } };
    fetch.mockResolvedValue({ ok: true, json: async () => payload });

    const res = await putStudyDesign('dataset-1', {
      expected_revision: 2,
      design: { group_column: 'group' },
      source: 'frontend-test',
      actor: 'qa',
    });

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/datasets\/dataset-1\/study_design$/),
      expect.objectContaining({ method: 'PUT' })
    );
    expect(res).toEqual(payload);
  });
});

describe('design review api', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('loads design review artifact status', async () => {
    const payload = { dataset_id: 'dataset-1', confirmed: true, artifact_exists: true };
    fetch.mockResolvedValue({ ok: true, json: async () => payload });

    const res = await getDatasetDesignReview('dataset-1');

    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/datasets\/dataset-1\/design_review$/),
      expect.any(Object)
    );
    expect(res).toEqual(payload);
  });

  it('confirms design review via dataset endpoint', async () => {
    const payload = { dataset_id: 'dataset-1', confirmed: true, artifact_exists: true };
    fetch.mockResolvedValue({ ok: true, json: async () => payload });

    const res = await confirmDatasetDesignReview('dataset-1', { actor: 'ui', source: 'test' });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/datasets\/dataset-1\/design_review\/confirm$/),
      expect.objectContaining({ method: 'POST' })
    );
    expect(res.confirmed).toBe(true);
  });

  it('revokes design review via dataset endpoint', async () => {
    const payload = { dataset_id: 'dataset-1', confirmed: false, artifact_exists: true };
    fetch.mockResolvedValue({ ok: true, json: async () => payload });

    const res = await revokeDatasetDesignReview('dataset-1', { reason: 'changed' });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/datasets\/dataset-1\/design_review\/revoke$/),
      expect.objectContaining({ method: 'POST' })
    );
    expect(res.confirmed).toBe(false);
  });
});

describe('interactive cleaning api', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('applies interactive cleaning via dataset endpoint', async () => {
    const payload = { dataset_id: 'dataset-1', applied_count: 2, skipped_count: 1, operations: [], profile: { row_count: 10, col_count: 3, columns: [], head: [] } };
    fetch.mockResolvedValue({ ok: true, json: async () => payload });

    const res = await applyInteractiveCleaning('dataset-1', {
      operations: [{ column: 'glucose', action: 'fill_median', enabled: true }],
    }, { page: 1, limit: 500 });

    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/datasets\/dataset-1\/prepare\/cleaning\/interactive\/apply\?page=1&limit=500$/),
      expect.objectContaining({ method: 'POST' })
    );
    expect(res).toEqual(payload);
  });
});

describe('executeProtocolV2', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('sends design review globals when provided', async () => {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ run_id: 'run_1' }) });

    await executeProtocolV2(
      'dataset-1',
      [{ id: 's1', method: 'descriptive_compare', config: { outcome: 'x', group: 'g' } }],
      0.05,
      'Protocol',
      { design_confirmed: true, source: 'analysis_design_ai' }
    );

    expect(fetch).toHaveBeenCalledTimes(1);
    const options = fetch.mock.calls[0][1];
    const body = JSON.parse(options.body);
    expect(body.dataset_id).toBe('dataset-1');
    expect(body.globals).toEqual(
      expect.objectContaining({
        design_confirmed: true,
        source: 'analysis_design_ai',
      })
    );
  });
});

describe('runBatchAnalysis', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('uses canonical execute endpoint and normalizes legacy shape', async () => {
    fetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        run_id: 'run_batch_1',
        results: [
          {
            step_id: 'legacy_batch',
            results: {
              method_id: 'batch_analysis',
              type: 'batch_analysis',
              items: [
                {
                  target: 'score',
                  method: 't_test_ind',
                  p_value: 0.01,
                  stat_value: 2.3,
                  significant: true,
                  groups: [
                    { group: 'A', n: 12, mean: 10.1, sd: 2.0, shapiro_p: 0.2 },
                    { group: 'B', n: 11, mean: 12.4, sd: 2.1, shapiro_p: 0.1 },
                  ],
                },
              ],
            },
          },
        ],
      }),
    });

    const res = await runBatchAnalysis('dataset-1', ['score'], 'group', { designConfirmed: true });

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/v2\/analysis\/execute$/),
      expect.objectContaining({ method: 'POST' })
    );

    const options = fetch.mock.calls[0][1];
    const body = JSON.parse(options.body);
    expect(body.protocol?.[0]?.method).toBe('batch_analysis');
    expect(body.globals?.design_confirmed).toBe(true);

    expect(res.run_id).toBe('run_batch_1');
    expect(res.results.score?.method?.id).toBe('t_test_ind');
    expect(Array.isArray(res.descriptives)).toBe(true);
    expect(res.descriptives.length).toBe(2);
  });
});
