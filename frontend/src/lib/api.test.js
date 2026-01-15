import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { getAlphaSetting, exportDocx, exportReport } from './api';

describe('getAlphaSetting', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns default alpha when not set', () => {
    expect(getAlphaSetting()).toBe(0.05);
  });

  it('parses stored alpha', () => {
    localStorage.setItem('statwizard_alpha', '0.1');
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

    await expect(exportDocx({ results: {} })).rejects.toThrow('Failed to export DOCX');
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
