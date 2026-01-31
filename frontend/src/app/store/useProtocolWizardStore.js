import { create } from 'zustand';
import { getAlphaSetting } from '../../lib/api';

const useProtocolWizardStore = create((set) => ({
  // Navigation State
  step: 0,
  setStep: (step) => set({ step }),

  // Dataset State
  datasets: [],
  setDatasets: (datasets) => set({ datasets }),
  
  selectedDataset: null,
  setSelectedDataset: (selectedDataset) => set({ selectedDataset }),
  
  columns: [],
  setColumns: (columns) => set({ columns }),

  // Selection/Goal State
  selections: {
    goal: '',
    structure: '',
    data_type: '',
    groups: '',
    normal_distribution: true
  },
  setSelections: (update) => set((state) => ({ 
    selections: { ...state.selections, ...update } 
  })),

  // Variable Configuration State
  variables: {
    target: '',
    group: '',
    outcome_cols: [],
    subject_col: '',
    event: '',
    timepoint: '',
    timepoint_value: '',
    all_numeric: true,
    multiplicity_correction: 'fdr_bh',
    post_hoc: 'none',
    post_hoc_correction: 'none',
    alpha: getAlphaSetting()
  },
  setVariables: (update) => {
    if (typeof update === 'function') {
      set((state) => ({ variables: update(state.variables) }));
    } else {
      set((state) => ({ variables: { ...state.variables, ...update } }));
    }
  },

  // Analysis/Method State
  recommendation: null,
  setRecommendation: (recommendation) => set({ recommendation }),
  
  loading: false,
  setLoading: (loading) => set({ loading }),
  
  showApplyForm: false,
  setShowApplyForm: (showApplyForm) => set({ showApplyForm }),
  
  analysisResult: null,
  setAnalysisResult: (analysisResult) => set({ analysisResult }),
  
  inspector: null,
  setInspector: (inspector) => set({ inspector }),
  
  drilldownResult: null,
  setDrilldownResult: (drilldownResult) => set({ drilldownResult }),
  
  resultsOpen: false,
  setResultsOpen: (resultsOpen) => set({ resultsOpen }),
  
  drilldownSort: 'alpha',
  setDrilldownSort: (drilldownSort) => set({ drilldownSort }),

  // Visualization/Report State
  resultsSections: {
    article: true,
    details: true,
    chart: true,
    significant: true,
  },
  setResultsSections: (update) => set((state) => ({ 
    resultsSections: { ...state.resultsSections, ...update } 
  })),

  articleMetrics: {
    n: true,
    mean: true,
    sd: true,
    sem: false,
    median: true,
    iqr: true,
    min: true,
    max: true,
    cv: true,
    ci: true,
  },
  setArticleMetrics: (update) => set((state) => ({ 
    articleMetrics: { ...state.articleMetrics, ...update } 
  })),

  articleUi: {
    showColumns: false,
    showSignificantOnly: false,
    query: '',
  },
  setArticleUi: (update) => set((state) => ({ 
    articleUi: { ...state.articleUi, ...update } 
  })),

  // Report Preferences
  reportStyle: 'apa7',
  reportDensity: 'comfortable',
  reportAccent: '',
  setReportStyle: (style) => set({ reportStyle: style }),
  setReportDensity: (density) => set({ reportDensity: density }),
  setReportAccent: (accent) => set({ reportAccent: accent }),
  
  // Repeated Measures State
  rmBaseKey: '',
  setRmBaseKey: (key) => set({ rmBaseKey: key }),
}));

export default useProtocolWizardStore;
