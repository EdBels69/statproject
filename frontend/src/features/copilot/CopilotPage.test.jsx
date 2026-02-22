import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import CopilotPage from './CopilotPage';
import {
  getDatasets,
  getDataset,
  getDatasetReport,
  analysisPlan,
  executeProtocolV2,
  uploadKnowledgeFile,
  listKnowledgeDocs,
  listKnowledgeCatalog,
  deleteKnowledgeDoc,
  generatePromptBrief,
  getStudyDesign,
  getDatasetDesignReview,
  getDatasetAnalysisSet,
  confirmDatasetDesignReview,
  revokeDatasetDesignReview,
  freezeDatasetAnalysisSet,
  getVariableMapping,
  putVariableMapping,
  downloadProtocolReport,
  downloadCopilotReportPdf,
} from '../../lib/api';

vi.mock('react-router-dom', () => ({
  Link: ({ children, to = '#', ...rest }) => <a href={to} {...rest}>{children}</a>,
  useLocation: () => ({ pathname: '/copilot', state: {} }),
}));

vi.mock('../../lib/api', () => ({
  getDatasets: vi.fn(),
  getDataset: vi.fn(),
  getDatasetReport: vi.fn(),
  analysisPlan: vi.fn(),
  executeProtocolV2: vi.fn(),
  downloadProtocolReport: vi.fn(),
  uploadKnowledgeFile: vi.fn(),
  listKnowledgeDocs: vi.fn(),
  listKnowledgeCatalog: vi.fn(),
  deleteKnowledgeDoc: vi.fn(),
  generatePromptBrief: vi.fn(),
  getStudyDesign: vi.fn(),
  getDatasetDesignReview: vi.fn(),
  getDatasetAnalysisSet: vi.fn(),
  confirmDatasetDesignReview: vi.fn(),
  revokeDatasetDesignReview: vi.fn(),
  freezeDatasetAnalysisSet: vi.fn(),
  getVariableMapping: vi.fn(),
  putVariableMapping: vi.fn(),
  downloadCopilotReportPdf: vi.fn(),
}));

describe('CopilotPage publication flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getDatasets.mockResolvedValue([
      { id: 'ds_pub', filename: 'publication.csv', rows: 100, columns: 3 },
    ]);
    getDataset.mockResolvedValue({
      row_count: 100,
      col_count: 3,
      columns: [
        { name: 'group', type: 'categorical' },
        { name: 'outcome', type: 'numeric' },
        { name: 'x1', type: 'numeric' },
      ],
    });
    getDatasetReport.mockResolvedValue({
      profile: { row_count: 100, col_count: 3 },
      scan_report: {
        columns: {
          group: { type: 'object' },
          outcome: { type: 'float64' },
          x1: { type: 'float64' },
        },
        issues: [],
        missing_report: { total_rows: 100, columns_with_missing: 0, by_column: [] },
      },
    });
    listKnowledgeDocs.mockResolvedValue({ docs: [] });
    listKnowledgeCatalog.mockResolvedValue({ docs: [] });
    getStudyDesign.mockResolvedValue({
      design: {
        design_type: 'parallel_groups',
        group_column: 'group',
        outcomes: ['outcome'],
        categorical_outcomes: [],
        endpoint_groups: [],
      },
      analysis_policy: { multiplicity_correction: 'fdr_bh' },
    });
    getVariableMapping.mockResolvedValue({ mapping: {} });
    getDatasetDesignReview.mockResolvedValue({
      confirmed: true,
      confirmed_at: '2026-02-10T12:00:00',
    });
    getDatasetAnalysisSet.mockResolvedValue({
      artifact_exists: false,
      analysis_set_id: null,
    });
    freezeDatasetAnalysisSet.mockResolvedValue({
      artifact_exists: true,
      analysis_set_id: 'set_public_1',
      mode: 'complete_case',
      enforce: 'models',
      n_selected: 95,
    });
    analysisPlan.mockResolvedValue({
      status: 'completed',
      protocol_name: 'Publication Plan',
      analysis_mode: 'publication',
      globals: { analysis_mode: 'publication' },
      protocol: [
        {
          id: 's1',
          method: 't_test_ind',
          config: { outcome: 'outcome', group: 'group' },
        },
      ],
      notes: [],
      cleaning_plan: { required: true, operations: [{ type: 'normalize_missing_tokens' }] },
      cohort_plan: {
        required: true,
        mode: 'complete_case',
        enforce: 'models',
        strict: true,
        required_non_missing: ['outcome', 'group'],
        impute_columns: [],
      },
      report_spec: {
        style: 'publication',
        sections: [{ id: 'methods', title: 'Methods', required: true }],
      },
    });
    executeProtocolV2.mockResolvedValue({
      run_id: 'run_1001',
      status: 'completed',
      result_ir: { blocks: [] },
      errors: [],
    });

    uploadKnowledgeFile.mockResolvedValue({});
    deleteKnowledgeDoc.mockResolvedValue({});
    generatePromptBrief.mockResolvedValue({ prompt: 'stub' });
    confirmDatasetDesignReview.mockResolvedValue({ confirmed: true, confirmed_at: '2026-02-10T12:00:00' });
    revokeDatasetDesignReview.mockResolvedValue({ confirmed: false });
    putVariableMapping.mockResolvedValue({ ok: true });
    downloadProtocolReport.mockResolvedValue(new Blob());
    downloadCopilotReportPdf.mockResolvedValue(new Blob());
  });

  afterEach(() => {
    cleanup();
  });

  it('auto-freezes cohort in publication mode and forwards analysis_set_id to execute', async () => {
    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    const datasetSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(datasetSelect, { target: { value: 'ds_pub' } });

    await waitFor(() => {
      expect(getDatasetDesignReview).toHaveBeenCalledWith('ds_pub');
    });

    fireEvent.click(screen.getByRole('button', { name: /Publication \/ Manuscript/i }));

    fireEvent.change(
      screen.getByPlaceholderText(/Например: Сравни группы по исходу/i),
      { target: { value: 'Сформируй publication протокол и выполни.' } }
    );

    fireEvent.click(screen.getByRole('button', { name: /Анализировать/i }));

    await waitFor(() => {
      expect(analysisPlan).toHaveBeenCalled();
      expect(screen.getByRole('button', { name: /Выполнить анализ/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /Выполнить анализ/i }));

    await waitFor(() => {
      expect(freezeDatasetAnalysisSet).toHaveBeenCalledWith(
        'ds_pub',
        expect.objectContaining({
          mode: 'complete_case',
          enforce: 'models',
          required_non_missing: ['outcome', 'group'],
        })
      );
      expect(executeProtocolV2).toHaveBeenCalled();
    });

    const globalsArg = executeProtocolV2.mock.calls[0][4];
    expect(globalsArg).toEqual(
      expect.objectContaining({
        analysis_mode: 'publication',
        analysis_set_id: 'set_public_1',
        analysis_set_strict: true,
      })
    );
  });

  it('uses root-level report.columns shape and keeps design override selects populated', async () => {
    getDatasetReport.mockResolvedValueOnce({
      columns: {
        group: { type: 'categorical' },
        outcome: { type: 'numeric' },
        id: { type: 'text' },
      },
      issues: [],
      missing_report: { total_rows: 100, columns_with_missing: 0, by_column: [] },
    });

    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    const datasetSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(datasetSelect, { target: { value: 'ds_pub' } });

    await waitFor(() => {
      expect(getDatasetReport).toHaveBeenCalledWith('ds_pub');
      expect(getStudyDesign).toHaveBeenCalledWith('ds_pub');
    });

    const primaryLabel = screen.getByText(/Primary outcome \(override\)/i);
    const primarySelect = primaryLabel.parentElement.querySelector('select');
    expect(primarySelect).toBeTruthy();
    expect(primarySelect.disabled).toBe(false);

    const optionValues = Array.from(primarySelect.options).map((opt) => opt.value);
    expect(optionValues).toContain('outcome');

    const groupLabel = screen.getByText(/Group column \(override\)/i);
    const groupSelect = groupLabel.parentElement.querySelector('select');
    expect(groupSelect).toBeTruthy();
    expect(groupSelect.disabled).toBe(false);
    const groupOptionValues = Array.from(groupSelect.options).map((opt) => opt.value);
    expect(groupOptionValues).toContain('group');
  });

  it('allows editing numeric and categorical outcome sets from full column lists', async () => {
    getStudyDesign.mockResolvedValueOnce({
      design: {
        design_type: 'parallel_groups',
        group_column: 'group',
        outcomes: ['outcome'],
        categorical_outcomes: ['group'],
        endpoint_groups: [],
      },
      analysis_policy: { multiplicity_correction: 'fdr_bh' },
    });

    getDatasetReport.mockResolvedValueOnce({
      columns: {
        group: { type: 'object' },
        outcome: { type: 'numeric' },
        comorbidity: { type: 'object' },
        treatment: { type: 'string' },
      },
      issues: [],
      missing_report: { total_rows: 100, columns_with_missing: 0, by_column: [] },
    });

    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    const datasetSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(datasetSelect, { target: { value: 'ds_pub' } });

    await waitFor(() => {
      expect(getStudyDesign).toHaveBeenCalledWith('ds_pub');
    });

    const numericLabel = screen.getByText(/Числовые исходы \(ручной выбор\)/i);
    const numericSelect = numericLabel.parentElement.querySelector('select[multiple]');
    expect(numericSelect).toBeTruthy();
    const numericValues = Array.from(numericSelect.options).map((opt) => opt.value);
    expect(numericValues).toContain('outcome');

    const categoricalLabel = screen.getByText(/Категориальные исходы \(ручной выбор\)/i);
    const categoricalSelect = categoricalLabel.parentElement.querySelector('select[multiple]');
    expect(categoricalSelect).toBeTruthy();
    const categoricalValues = Array.from(categoricalSelect.options).map((opt) => opt.value);
    expect(categoricalValues).toContain('group');
    expect(categoricalValues).toContain('comorbidity');
    expect(categoricalValues).toContain('treatment');
  });
});
