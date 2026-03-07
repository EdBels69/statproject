import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import CopilotPage from './CopilotPage';
import {
  getDatasets,
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
  downloadProtocolReleaseBundle,
  getModelRouterBenchmarkSnapshot,
} from '../../lib/api';

vi.mock('react-router-dom', () => ({
  Link: ({ children, to = '#', ...rest }) => <a href={to} {...rest}>{children}</a>,
  useLocation: () => ({ pathname: '/copilot', state: {} }),
}));

vi.mock('../../lib/api', () => ({
  getDatasets: vi.fn(),
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
  downloadProtocolReleaseBundle: vi.fn(),
  getModelRouterBenchmarkSnapshot: vi.fn(),
}));

describe('CopilotPage publication flow', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getDatasets.mockResolvedValue([
      { id: 'ds_pub', filename: 'publication.csv', rows: 100, columns: 3 },
    ]);
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
      globals: { analysis_mode: 'publication', validation_profile: 'focused' },
      validation_policy: {
        profile: 'focused',
        validator_enabled: true,
        validator_strict: false,
        reflection_enabled: true,
        reflection_max_rounds: 2,
        repair_correction: 'fdr_bh',
      },
      multiplicity_policy: {
        correction: 'fdr_bh',
        post_hoc_correction: 'fdr_bh',
        n_applied_steps: 1,
      },
      hypotheses: {
        schema: 'clinimetria.hypothesis_discovery',
        analysis_mode: 'publication',
        count: 2,
        items: [
          {
            id: 'h_group_numeric',
            title: 'Сравнить outcome между группами group',
            suggested_method: 't_test_ind / mann_whitney / anova',
          },
          {
            id: 'h_group_cat',
            title: 'Оценить связь group и responder',
            suggested_method: 'chi_square / fisher_exact',
          },
        ],
      },
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
    generatePromptBrief.mockResolvedValue({
      prompt: 'stub',
      validation_policy: {
        profile: 'focused',
        validator_enabled: true,
        validator_strict: false,
        reflection_enabled: true,
        reflection_max_rounds: 2,
        repair_correction: 'fdr_bh',
      },
      hypotheses: {
        schema: 'clinimetria.hypothesis_discovery',
        count: 1,
        items: [
          {
            id: 'h_group_numeric',
            title: 'Сравнить outcome между группами group',
            suggested_method: 't_test_ind / mann_whitney / anova',
          },
        ],
      },
    });
    confirmDatasetDesignReview.mockResolvedValue({ confirmed: true, confirmed_at: '2026-02-10T12:00:00' });
    revokeDatasetDesignReview.mockResolvedValue({ confirmed: false });
    putVariableMapping.mockResolvedValue({ ok: true });
    downloadProtocolReport.mockResolvedValue(new Blob());
    downloadCopilotReportPdf.mockResolvedValue(new Blob());
    downloadProtocolReleaseBundle.mockResolvedValue(new Blob(['zip'], { type: 'application/zip' }));
    getModelRouterBenchmarkSnapshot.mockResolvedValue({
      summary: { runs_total: 0, variants_total: 0, distinct_variants: 0 },
      coverage_gate: { meets_threshold: false, runs_total: 0, min_runs: 10 },
      winners_by_profile: {},
      variants: [],
    });
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
    const policyTitle = screen.getByText(/Validation policy/i);
    expect(policyTitle).toBeInTheDocument();
    expect(policyTitle.closest('div')).toHaveTextContent(/focused/i);
    expect(screen.getByText(/Multiplicity policy/i)).toBeInTheDocument();
    expect(screen.getByText(/Hypothesis discovery/i)).toBeInTheDocument();
    expect(screen.getByText(/Сравнить outcome между группами group/i)).toBeInTheDocument();

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
        validation_profile: 'focused',
        analysis_set_id: 'set_public_1',
        analysis_set_strict: true,
      })
    );
  });

  it('shows brief validation policy returned by backend', async () => {
    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    const datasetSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(datasetSelect, { target: { value: 'ds_pub' } });

    await waitFor(() => {
      expect(getDatasetDesignReview).toHaveBeenCalledWith('ds_pub');
    });

    fireEvent.click(screen.getByRole('button', { name: /Publication \/ Manuscript/i }));
    fireEvent.click(screen.getByRole('button', { name: /Сгенерировать бриф из метаданных/i }));

    await waitFor(() => {
      expect(generatePromptBrief).toHaveBeenCalledWith('ds_pub', expect.any(Object));
    });

    expect(screen.getByDisplayValue('stub')).toBeInTheDocument();
    const briefPolicyLabel = screen.getByText(/Brief policy:/i);
    expect(briefPolicyLabel).toBeInTheDocument();
    expect(briefPolicyLabel.closest('div')).toHaveTextContent(/focused/i);
    expect(briefPolicyLabel.closest('div')).toHaveTextContent(/FDR \(Benjamini-Hochberg\)/i);
    expect(screen.getByText(/Auto hypotheses \(brief\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Сравнить outcome между группами group/i)).toBeInTheDocument();
  });

  it('runs model benchmark against multiple presets from request block', async () => {
    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    const datasetSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(datasetSelect, { target: { value: 'ds_pub' } });

    await waitFor(() => {
      expect(getDatasetDesignReview).toHaveBeenCalledWith('ds_pub');
    });

    fireEvent.change(
      screen.getByPlaceholderText(/Например: Сравни группы по исходу/i),
      { target: { value: 'Сравнить модели на одном запросе.' } }
    );

    fireEvent.click(screen.getByRole('button', { name: /Сравнить MiniMax \/ GLM-5 \/ Qwen \/ Gemini/i }));

    await waitFor(() => {
      expect(analysisPlan).toHaveBeenCalledTimes(5);
    });

    expect(screen.getByText(/Gemini Flash 2.5 \(single\)/i)).toBeInTheDocument();
    expect(screen.getByText(/MiniMax M2.5 \(single\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Policy/i)).toBeInTheDocument();
    expect(screen.getAllByText(/focused/i).length).toBeGreaterThan(0);
  });

  it('loads historical benchmark snapshot and renders winners', async () => {
    getModelRouterBenchmarkSnapshot.mockResolvedValue({
      summary: { runs_total: 14, variants_total: 68, distinct_variants: 5 },
      coverage_gate: { meets_threshold: true, runs_total: 14, min_runs: 10 },
      capture_last: {
        available: true,
        status: 'completed',
        generated_at: '2026-03-02T10:00:00Z',
        dataset_id: 'ds_pub',
        run_id: 'run_capture_20260302',
        recommended_id: 'qwen_single',
        skip_reason: null,
        snapshot: {
          coverage_gate: { meets_threshold: true, runs_total: 14, min_runs: 10 },
        },
      },
      winners_by_profile: {
        publication: { variant_id: 'gemini_single', share: 0.6, total_runs: 5 },
        focused: { variant_id: 'minimax_single', share: 0.5, total_runs: 4 },
        exploratory: { variant_id: 'qwen_single', share: 0.8, total_runs: 5 },
      },
      variants: [
        {
          id: 'qwen_single',
          recommendation_share: 0.357,
          success_rate: 0.93,
          mean_auto_score: 0.881,
          fallback_rate: 0.02,
        },
      ],
    });

    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    fireEvent.click(screen.getByRole('button', { name: /^Обновить$/i }));

    await waitFor(() => {
      expect(getModelRouterBenchmarkSnapshot).toHaveBeenCalledWith(
        expect.objectContaining({ minRuns: 10, includeMarkdown: false, topN: 8 })
      );
    });

    expect(screen.getByText(/Исторический benchmark моделей/i)).toBeInTheDocument();
    expect(screen.getByText(/^Coverage: PASS/i)).toBeInTheDocument();
    expect(screen.getByText(/Live capture: COMPLETED/i)).toBeInTheDocument();
    expect(screen.getByText(/Capture run:/i)).toBeInTheDocument();
    expect(screen.getAllByText(/qwen_single/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Active profile winner \(exploratory\):/i)).toBeInTheDocument();
  });

  it('downloads release bundle after execute', async () => {
    render(<CopilotPage />);

    await screen.findByText(/publication\.csv/i);
    const datasetSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(datasetSelect, { target: { value: 'ds_pub' } });

    await waitFor(() => {
      expect(getDatasetDesignReview).toHaveBeenCalledWith('ds_pub');
    });

    fireEvent.change(
      screen.getByPlaceholderText(/Например: Сравни группы по исходу/i),
      { target: { value: 'Сформируй publication протокол и выполни.' } }
    );

    fireEvent.click(screen.getByRole('button', { name: /Анализировать/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Выполнить анализ/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /Выполнить анализ/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Release ZIP/i })).toBeInTheDocument();
    });

    const prevCreateObjectURL = URL.createObjectURL;
    const prevRevokeObjectURL = URL.revokeObjectURL;
    const createObjectURLMock = vi.fn(() => 'blob:release');
    const revokeObjectURLMock = vi.fn(() => {});
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      writable: true,
      value: createObjectURLMock,
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      writable: true,
      value: revokeObjectURLMock,
    });
    const anchorClickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    fireEvent.click(screen.getByRole('button', { name: /Release ZIP/i }));
    await waitFor(() => {
      expect(downloadProtocolReleaseBundle).toHaveBeenCalledWith('ds_pub', 'run_1001');
    });

    if (typeof prevCreateObjectURL === 'function') {
      Object.defineProperty(URL, 'createObjectURL', {
        configurable: true,
        writable: true,
        value: prevCreateObjectURL,
      });
    }
    if (typeof prevRevokeObjectURL === 'function') {
      Object.defineProperty(URL, 'revokeObjectURL', {
        configurable: true,
        writable: true,
        value: prevRevokeObjectURL,
      });
    }
    anchorClickSpy.mockRestore();
  });
});
