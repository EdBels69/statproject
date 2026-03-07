import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import Analyze from './Analyze';
import {
  runBatchAnalysis,
  getDataset,
  getVariableMapping,
  getDatasetDesignReview,
} from '../../lib/api';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useParams: () => ({ id: 'dataset-1' }),
  useLocation: () => ({ pathname: '/results/dataset-1', state: {} }),
  useNavigate: () => mockNavigate,
}));

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    t: (key) => {
      const map = {
        not_available_short: 'N/A',
        loading: 'loading',
        error: 'Error',
        select_variables_to_begin: 'Select variables to begin',
        analysis: 'Analysis',
        results: 'Results',
        back: 'Back',
      };
      return map[key] || key;
    },
  }),
}));

vi.mock('../components/VariableSelector', () => ({
  default: ({ onRun }) => (
    <button type="button" onClick={() => onRun(['outcome'], 'group')}>
      mock-run
    </button>
  ),
}));

vi.mock('../components/ResearchFlowNav', () => ({
  default: () => <div data-testid="research-flow-nav" />,
}));

vi.mock('../components/SearchableSelect', () => ({
  default: () => <div data-testid="searchable-select" />,
}));

vi.mock('../components/education', () => ({
  EffectSizeExplainer: () => null,
  StatTooltip: ({ children }) => <>{children}</>,
}));

vi.mock('../components/education/EffectSizeExplainer', () => ({
  getEffectSizeInterpretation: () => ({ key: 'small', label: 'Small' }),
}));

vi.mock('../../lib/api', () => ({
  runBatchAnalysis: vi.fn(),
  getDataset: vi.fn(),
  getVariableMapping: vi.fn(),
  exportDocx: vi.fn(),
  exportReport: vi.fn(),
  getDatasetDesignReview: vi.fn(),
  confirmDatasetDesignReview: vi.fn(),
  revokeDatasetDesignReview: vi.fn(),
}));

describe('Analyze Design Review Gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();
    getDataset.mockResolvedValue({
      columns: [
        { name: 'group', type: 'categorical' },
        { name: 'outcome', type: 'numeric' },
      ],
    });
    getVariableMapping.mockResolvedValue({ mapping: {} });
    runBatchAnalysis.mockResolvedValue({ results: {}, descriptives: [] });
  });

  afterEach(() => {
    cleanup();
  });

  it('blocks batch run when Design Review is not confirmed', async () => {
    getDatasetDesignReview.mockResolvedValue({ confirmed: false });

    render(<Analyze />);

    await waitFor(() => {
      expect(getDatasetDesignReview).toHaveBeenCalledWith('dataset-1');
    });

    fireEvent.click(screen.getByText('Выбрать переменные'));
    fireEvent.click(screen.getByText('mock-run'));

    await waitFor(() => {
      expect(screen.getByText('Перед запуском подтвердите Design Review')).toBeInTheDocument();
    });
    expect(runBatchAnalysis).not.toHaveBeenCalled();
  });

  it('passes designConfirmed=true to runBatchAnalysis when review is confirmed', async () => {
    getDatasetDesignReview.mockResolvedValue({ confirmed: true });

    render(<Analyze />);

    await waitFor(() => {
      expect(screen.getByText('Подтверждено в backend-артефакте')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Выбрать переменные'));
    fireEvent.click(screen.getByText('mock-run'));

    await waitFor(() => {
      expect(runBatchAnalysis).toHaveBeenCalledWith(
        'dataset-1',
        ['outcome'],
        'group',
        { designConfirmed: true },
      );
    });
  });
});
