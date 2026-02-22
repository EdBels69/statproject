import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import ProtocolSorcerer from './ProtocolSorcerer';
import {
  listDatasets,
  getDataset,
  listDatasetColumns,
  getScanReport,
  getSemantics,
  getStudyDesign,
  getDatasetDesignReview,
  getDatasetAnalysisSet,
  aiAnalyzeDesign,
} from '../../lib/api';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/sorcerer', state: null }),
}));

vi.mock('../../lib/api', () => ({
  getSorcererRecommendation: vi.fn(),
  listDatasets: vi.fn(),
  getDataset: vi.fn(),
  listDatasetColumns: vi.fn(),
  getAlphaSetting: vi.fn(() => 0.05),
  aiAnalyzeDesign: vi.fn(),
  executeProtocolV2: vi.fn(),
  cleanColumn: vi.fn(),
  getScanReport: vi.fn(),
  getSemantics: vi.fn(),
  getStudyDesign: vi.fn(),
  putStudyDesign: vi.fn(),
  getDatasetDesignReview: vi.fn(),
  confirmDatasetDesignReview: vi.fn(),
  revokeDatasetDesignReview: vi.fn(),
  getDatasetAnalysisSet: vi.fn(),
  freezeDatasetAnalysisSet: vi.fn(),
  clearDatasetAnalysisSet: vi.fn(),
}));

describe('ProtocolSorcerer planning preferences', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();
    listDatasets.mockResolvedValue([
      { id: 'dataset-1', filename: 'primary.csv' },
      { id: 'dataset-2', filename: 'external.csv' },
    ]);
    getDataset.mockResolvedValue({
      columns: [
        { name: 'group', type: 'categorical' },
        { name: 'age', type: 'numeric' },
        { name: 'crp', type: 'numeric' },
        { name: 'event', type: 'categorical' },
      ],
    });
    listDatasetColumns.mockResolvedValue({
      columns: ['group', 'age', 'crp', 'event', 'hba1c_raw_text'],
      total: 5,
      offset: 0,
      limit: 2000,
    });
    getScanReport.mockResolvedValue({
      columns: {
        group: { type: 'categorical', unique_count: 2 },
        age: { type: 'numeric' },
        crp: { type: 'numeric' },
        event: { type: 'categorical', unique_count: 2 },
      },
      missing_report: { total_rows: 120 },
    });
    getSemantics.mockResolvedValue({});
    getStudyDesign.mockResolvedValue({
      revision: 1,
      design: {
        design_type: 'cross_sectional',
        group_column: 'group',
        time_column: '',
        subject_column: '',
        outcomes: ['age', 'crp'],
        categorical_outcomes: ['event'],
      },
    });
    getDatasetDesignReview.mockResolvedValue({ confirmed: false });
    getDatasetAnalysisSet.mockResolvedValue({ artifact_exists: false });
    aiAnalyzeDesign.mockResolvedValue({
      status: 'completed',
      protocol_name: 'Expert protocol',
      protocol: [
        {
          id: 'step_1',
          method: 'batch_analysis',
          config: { group: 'group', targets: ['age', 'crp'] },
        },
      ],
      notes: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('passes allow_data_mining and external_validation_dataset_id to planner', async () => {
    render(<ProtocolSorcerer />);

    await waitFor(() => {
      expect(listDatasets).toHaveBeenCalled();
      expect(screen.getByText('primary.csv')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('primary.csv'));

    await waitFor(() => {
      expect(screen.getByText('ИИ: всё‑на‑всё по группам')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('ИИ: всё‑на‑всё по группам'));

    await waitFor(() => {
      expect(screen.getByText('Настройка анализа')).toBeInTheDocument();
      expect(screen.getByText('Deep mining')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText('Расширить охват (allow_data_mining)'));

    fireEvent.change(
      screen.getByLabelText('External validation dataset (опционально)'),
      { target: { value: 'dataset-2' } },
    );

    fireEvent.change(screen.getByPlaceholderText('Опишите дизайн…'), {
      target: { value: 'Построй глубокий протокол с внешней валидацией модели исхода' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Собрать протокол' }));

    await waitFor(() => {
      expect(aiAnalyzeDesign).toHaveBeenCalled();
    });

    const call = aiAnalyzeDesign.mock.calls.at(-1);
    expect(call?.[0]).toBe('dataset-1');
    expect(call?.[2]?.preferences).toEqual(
      expect.objectContaining({
        allow_data_mining: true,
        external_validation_dataset_id: 'dataset-2',
      }),
    );
  });

  it('loads full dataset column catalog into design outcome selectors', async () => {
    render(<ProtocolSorcerer />);

    await waitFor(() => {
      expect(screen.getByText('primary.csv')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('primary.csv'));

    await waitFor(() => {
      expect(listDatasetColumns).toHaveBeenCalledWith('dataset-1', { offset: 0, limit: 2000 });
      expect(screen.getByText('ИИ: всё‑на‑всё по группам')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('ИИ: всё‑на‑всё по группам'));

    const numericOutcomes = await screen.findByLabelText('Numeric outcomes');
    expect(
      within(numericOutcomes).getByRole('option', { name: 'hba1c_raw_text' }),
    ).toBeInTheDocument();
  });
});
