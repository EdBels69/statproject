import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import AnalysisDesign from './AnalysisDesign';
import {
  getDataset,
  listDatasetColumns,
  getScanReport,
  getVariableMapping,
  getDatasetDesignReview,
} from '../../lib/api';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: 'dataset-1' }),
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/ai/dataset-1', state: {} }),
}));

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    t: (key) => {
      const map = {
        loading: 'loading',
        loading_dataset: 'loading dataset',
        no_datasets_found: 'no datasets found',
        datasets: 'datasets',
        upload_dataset: 'upload dataset',
        back: 'back',
        dataset: 'dataset',
      };
      return map[key] || key;
    },
  }),
}));

vi.mock('../components/ResearchFlowNav', () => ({
  default: () => <div data-testid="research-flow-nav" />,
}));

vi.mock('../components/VariableWorkspace', () => ({
  default: ({ columns }) => {
    const names = Array.isArray(columns)
      ? columns
        .map((c) => (typeof c === 'string' ? c : c?.name))
        .filter(Boolean)
      : [];
    return (
    <div data-testid="variable-workspace">
      {names.includes('hba1c_raw_text') ? 'has-hba1c' : 'no-hba1c'}
    </div>
    );
  },
}));

vi.mock('../components/analysis/TestSelectionPanel', () => ({
  default: () => <div data-testid="test-selection-panel" />,
}));

vi.mock('../components/TestConfigModal', () => ({
  default: () => null,
}));

vi.mock('../components/ClusteredHeatmap', () => ({
  default: () => null,
}));

vi.mock('../components/InteractionPlot', () => ({
  default: () => null,
}));

vi.mock('../components/VisualizePlot', () => ({
  default: () => null,
}));

vi.mock('../../lib/api', () => ({
  getAISuggestions: vi.fn(),
  getAlphaSetting: vi.fn(() => 0.05),
  getDataset: vi.fn(),
  listDatasetColumns: vi.fn(),
  getDatasets: vi.fn(),
  getScanReport: vi.fn(),
  getVariableMapping: vi.fn(),
  getAnalysisTemplates: vi.fn(),
  analysisPlan: vi.fn(),
  designAnalysisFromTemplate: vi.fn(),
  executeProtocolV2: vi.fn(),
  getDatasetDesignReview: vi.fn(),
  confirmDatasetDesignReview: vi.fn(),
  revokeDatasetDesignReview: vi.fn(),
}));

describe('AnalysisDesign full column catalog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();

    getDataset.mockResolvedValue({
      name: 'primary.csv',
      columns: [
        { name: 'group', type: 'categorical' },
        { name: 'age', type: 'numeric' },
      ],
    });
    listDatasetColumns.mockResolvedValue({
      columns: ['group', 'age', 'hba1c_raw_text'],
      total: 3,
      offset: 0,
      limit: 2000,
    });
    getScanReport.mockResolvedValue({
      missing_report: { total_rows: 120 },
      column_stats: {
        age: { type: 'numeric' },
      },
    });
    getVariableMapping.mockResolvedValue({ mapping: {} });
    getDatasetDesignReview.mockResolvedValue({ confirmed: false });
  });

  afterEach(() => {
    cleanup();
  });

  it('loads full catalog and shows non-profile column in selectors', async () => {
    render(<AnalysisDesign mode="ai" />);

    await waitFor(() => {
      expect(getDataset).toHaveBeenCalledWith('dataset-1');
      expect(listDatasetColumns).toHaveBeenCalledWith('dataset-1', { offset: 0, limit: 2000 });
    });

    const matchedOptions = await screen.findAllByRole('option', { name: 'hba1c_raw_text' });
    expect(matchedOptions.length).toBeGreaterThan(0);
  });

  it('passes full catalog to legacy /design workspace', async () => {
    render(<AnalysisDesign />);

    await waitFor(() => {
      expect(getDataset).toHaveBeenCalledWith('dataset-1');
      expect(listDatasetColumns).toHaveBeenCalledWith('dataset-1', { offset: 0, limit: 2000 });
    });

    expect(await screen.findByText('has-hba1c')).toBeInTheDocument();
  });
});
