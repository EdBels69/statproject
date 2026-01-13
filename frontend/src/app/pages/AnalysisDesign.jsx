import React, { useEffect, useState } from 'react';
import { 
  ArrowLeftIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';
import { useNavigate, useParams } from 'react-router-dom';
import TestSelectionPanel from '../components/analysis/TestSelectionPanel';
import ProtocolBuilder from '../components/analysis/ProtocolBuilder';
import TestConfigModal from '../components/TestConfigModal';
import AIRecommendationsPanel from '../components/analysis/AIRecommendationsPanel';
import ClusteredHeatmap from '../components/ClusteredHeatmap';
import InteractionPlot from '../components/InteractionPlot';
import VisualizePlot from '../components/VisualizePlot';
import { useTranslation } from '../../hooks/useTranslation';
import { getAlphaSetting, getDataset, getDatasets } from '../../lib/api';

const AnalysisDesign = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id: datasetIdFromRoute } = useParams();

  const [datasets, setDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(false);
  const [datasetsError, setDatasetsError] = useState(null);

  const [datasetId, setDatasetId] = useState(null);
  const [datasetName, setDatasetName] = useState(null);
  const [columns, setColumns] = useState([]);
  const [datasetLoading, setDatasetLoading] = useState(false);
  const [datasetError, setDatasetError] = useState(null);

  const [protocol, setProtocol] = useState([]);
  const [selectedTest, setSelectedTest] = useState(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [editingTest, setEditingTest] = useState(null);
  const [showAI, setShowAI] = useState(false);
  const [aiRecommendations, setAIRecommendations] = useState([]);
  const [isAIAnalyzing, setIsAIAnalyzing] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [results, setResults] = useState(null);
  const [isResultsOpen, setIsResultsOpen] = useState(false);

  const datasetIdResolved = datasetIdFromRoute || datasetId;

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setDatasetError(null);

      if (!datasetIdFromRoute) {
        setDatasetId(null);
        setDatasetName(null);
        setColumns([]);
        return;
      }

      setDatasetLoading(true);
      try {
        const profile = await getDataset(datasetIdFromRoute);
        if (cancelled) return;
        setDatasetId(profile?.id || datasetIdFromRoute);
        setDatasetName(profile?.filename || profile?.name || datasetIdFromRoute);
        setColumns(Array.isArray(profile?.columns) ? profile.columns : []);
      } catch (e) {
        if (cancelled) return;
        setDatasetError(e?.message || String(e));
      } finally {
        if (!cancelled) setDatasetLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [datasetIdFromRoute]);

  useEffect(() => {
    let cancelled = false;

    const loadDatasets = async () => {
      if (datasetIdFromRoute) return;
      setDatasetsError(null);
      setDatasetsLoading(true);
      try {
        const list = await getDatasets();
        if (cancelled) return;
        setDatasets(Array.isArray(list) ? list : []);
      } catch (e) {
        if (cancelled) return;
        setDatasetsError(e?.message || String(e));
      } finally {
        if (!cancelled) setDatasetsLoading(false);
      }
    };

    loadDatasets();

    return () => {
      cancelled = true;
    };
  }, [datasetIdFromRoute]);

  const handleTestSelect = (test) => {
    setSelectedTest(test);
    setEditingTest(null);
    setIsConfigModalOpen(true);
  };

  const handleConfigSave = (config) => {
    if (editingTest) {
      setProtocol(prev => 
        prev.map(test => 
          test.id === editingTest.id 
            ? { ...test, config: { ...test.config, ...config } }
            : test
        )
      );
    } else {
      const newTest = {
        id: `test_${Date.now()}`,
        method: selectedTest.id,
        name: selectedTest.name,
        config: config
      };
      setProtocol(prev => [...prev, newTest]);
    }
    setIsConfigModalOpen(false);
    setSelectedTest(null);
    setEditingTest(null);
  };

  const handleRemoveTest = (testId) => {
    setProtocol(prev => prev.filter(test => test.id !== testId));
  };

  const handleEditTest = (test) => {
    setEditingTest(test);
    setSelectedTest({ id: test.method, name: test.name });
    setIsConfigModalOpen(true);
  };

  const handleMoveTest = (fromIndex, toIndex) => {
    const newProtocol = [...protocol];
    const [movedTest] = newProtocol.splice(fromIndex, 1);
    newProtocol.splice(toIndex, 0, movedTest);
    setProtocol(newProtocol);
  };

  const handleAISuggest = async () => {
    if (protocol.length === 0) return;
    
    setIsAIAnalyzing(true);
    setShowAI(true);
    
    try {
      const response = await fetch('/api/v2/ai/suggest-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: datasetIdResolved,
          protocol: protocol.map((test) => ({
            method: test.method,
            config: test.config
          }))
        })
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        throw new Error(text || 'AI suggestion failed');
      }

      const data = await response.json();
      setAIRecommendations(Array.isArray(data?.recommendations) ? data.recommendations : []);
    } catch (error) {
      console.error('AI suggestion failed:', error);
      setAIRecommendations([]);
    } finally {
      setIsAIAnalyzing(false);
    }
  };

  const handleAddRecommendation = (recommendation) => {
    const newTest = {
      id: `test_${Date.now()}`,
      method: recommendation.test.id,
      name: recommendation.test.name,
      config: recommendation.test.config || {}
    };
    setProtocol(prev => [...prev, newTest]);
  };

  const handleExecuteProtocol = async (protocolToExecute) => {
    setIsExecuting(true);
    
    try {
      const response = await fetch('/api/v2/analysis/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset_id: datasetIdResolved,
          alpha: getAlphaSetting(),
          protocol: protocolToExecute.map((test) => ({
            method: test.method,
            config: test.config
          }))
        })
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        throw new Error(text || 'Protocol execution failed');
      }

      const data = await response.json();
      setResults(data);
      setIsResultsOpen(true);
    } catch (error) {
      console.error('Protocol execution failed:', error);
    } finally {
      setIsExecuting(false);
    }
  };

  const formatMethodName = (methodId) => {
    if (!methodId) return '';
    if (methodId === 'mixed_effects') return 'Mixed Effects (LMM)';
    if (methodId === 'clustered_correlation') return 'Clustered Correlation';
    return String(methodId).replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
  };

  const renderStepResult = (step) => {
    const payload = step?.results;
    const method = step?.method;

    if (method === 'mixed_effects') {
      return (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4 overflow-hidden">
            <div className="text-xs font-semibold tracking-[0.18em] text-gray-400 uppercase">Interaction</div>
            <div className="mt-2 flex items-baseline gap-3">
              <div className="text-2xl font-black text-gray-900 font-mono">
                {typeof payload?.interaction_p_value === 'number'
                  ? payload.interaction_p_value < 0.001
                    ? '< 0.001'
                    : payload.interaction_p_value.toFixed(4)
                  : '—'}
              </div>
              <div className="text-xs text-gray-500">Time × Group p-value</div>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4 overflow-hidden">
            <div className="text-xs font-semibold tracking-[0.18em] text-gray-400 uppercase">Interaction Plot</div>
            <div className="mt-3 overflow-x-auto">
              <InteractionPlot data={payload} width={640} height={380} />
            </div>
          </div>
        </div>
      );
    }

    if (method === 'clustered_correlation') {
      return (
        <div className="bg-white border border-gray-200 rounded-xl p-4 overflow-hidden">
          <div className="text-xs font-semibold tracking-[0.18em] text-gray-400 uppercase">Clustered Heatmap</div>
          <div className="mt-3 overflow-x-auto">
            <ClusteredHeatmap data={payload} width={760} height={560} />
          </div>
        </div>
      );
    }

    if (Array.isArray(payload?.plot_data) && payload.plot_data.length > 0) {
      return (
        <div className="bg-white border border-gray-200 rounded-xl p-4 overflow-hidden">
          <div className="text-xs font-semibold tracking-[0.18em] text-gray-400 uppercase">Plot</div>
          <div className="mt-3">
            <VisualizePlot data={payload.plot_data} stats={payload.plot_stats} groups={payload.groups} />
          </div>
        </div>
      );
    }

    return (
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-gray-400 uppercase">p-value</div>
            <div className="mt-1 font-mono text-sm text-gray-900">
              {typeof payload?.p_value === 'number'
                ? payload.p_value < 0.001
                  ? '< 0.001'
                  : payload.p_value.toFixed(4)
                : '—'}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-gray-400 uppercase">stat</div>
            <div className="mt-1 font-mono text-sm text-gray-900">
              {typeof payload?.stat_value === 'number' ? payload.stat_value.toFixed(3) : '—'}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-gray-400 uppercase">significant</div>
            <div className={`mt-1 text-sm font-semibold ${payload?.significant ? 'text-green-700' : 'text-gray-500'}`}>
              {payload?.significant ? 'Yes' : 'No'}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold tracking-[0.18em] text-gray-400 uppercase">method</div>
            <div className="mt-1 text-sm text-gray-700 truncate">
              {formatMethodName(method)}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const handleCloseConfigModal = () => {
    setIsConfigModalOpen(false);
    setSelectedTest(null);
    setEditingTest(null);
  };

  const canRun = Boolean(datasetIdResolved) && !datasetLoading && !datasetError;

  const onBack = () => {
    navigate('/datasets');
  };

  const datasetPicker = (
    <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-8">
          <div className="text-xs font-semibold tracking-[0.22em] text-gray-400 uppercase">{t('analysis_protocol')}</div>
          <h1 className="mt-3 text-3xl font-black text-gray-900 leading-tight">{t('test_selection')}</h1>
          <p className="mt-2 text-sm text-gray-600 max-w-2xl">{t('select_tests_tooltip')}</p>
        </div>

        {datasetsError && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{datasetsError}</div>
        )}

        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <div className="text-sm font-semibold text-gray-900">{t('datasets')}</div>
            <button
              onClick={() => navigate('/upload')}
              className="text-sm font-medium text-blue-700 hover:text-blue-800"
              type="button"
            >
              {t('upload_dataset')}
            </button>
          </div>

          <div className="p-3">
            {datasetsLoading ? (
              <div className="p-8 text-center text-gray-500 text-sm">Loading…</div>
            ) : datasets.length === 0 ? (
              <div className="p-8 text-center text-gray-500 text-sm">No datasets found</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {datasets.map((ds) => (
                  <button
                    key={ds.id}
                    type="button"
                    onClick={() => navigate(`/design/${ds.id}`)}
                    className="text-left p-4 rounded-xl border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition"
                  >
                    <div className="text-sm font-semibold text-gray-900 truncate">{ds.filename || ds.name || ds.id}</div>
                    <div className="mt-1 text-xs text-gray-500 font-mono truncate">{ds.id}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  if (!datasetIdFromRoute) {
    return datasetPicker;
  }

  if (datasetLoading) {
    return (
      <div className="min-h-[calc(100vh-120px)] flex items-center justify-center text-sm text-gray-500">Loading dataset…</div>
    );
  }

  if (datasetError) {
    return (
      <div className="min-h-[calc(100vh-120px)] flex items-center justify-center px-6">
        <div className="w-full max-w-xl p-6 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {datasetError}
          <div className="mt-4">
            <button type="button" onClick={onBack} className="text-red-700 font-semibold hover:underline">Back</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              type="button"
            >
              <ArrowLeftIcon className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                StatWizard
              </h1>
              {datasetName && (
                <p className="text-sm text-gray-600 mt-1">
                  {datasetName}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAI(!showAI)}
              disabled={!canRun}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                showAI 
                  ? 'bg-purple-600 text-white' 
                  : 'bg-purple-50 text-purple-700 hover:bg-purple-100'
              }`}
              type="button"
            >
              <SparklesIcon className="w-4 h-4" />
              {t('ai_assistant')}
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        <div className="w-96 flex-shrink-0">
          <TestSelectionPanel 
            onTestSelect={handleTestSelect}
            disabled={isExecuting}
          />
        </div>

        <div className="flex-1 flex flex-col overflow-hidden">
          {showAI && (
            <div className="flex-shrink-0 p-4 border-b border-gray-200">
              <AIRecommendationsPanel
                datasetId={datasetId}
                columns={columns}
                recommendations={aiRecommendations}
                onAddRecommendation={handleAddRecommendation}
                onClose={() => setShowAI(false)}
                isAnalyzing={isAIAnalyzing}
              />
            </div>
          )}

          <div className="flex-1 overflow-hidden flex flex-col">
            <div className="flex-1 overflow-hidden">
              <ProtocolBuilder
                protocol={protocol}
                datasetName={datasetName}
                onRemoveTest={handleRemoveTest}
                onEditTest={handleEditTest}
                onMoveTest={handleMoveTest}
                onExecuteProtocol={handleExecuteProtocol}
                onAISuggest={handleAISuggest}
                isExecuting={isExecuting}
                isAIAnalyzing={isAIAnalyzing}
              />
            </div>

            {results && (
              <div className={`border-t border-gray-200 bg-gray-100 flex-shrink-0 ${isResultsOpen ? 'h-[46vh]' : 'h-12'} transition-[height] duration-200 overflow-hidden`}>
                <div className="h-12 px-4 flex items-center justify-between bg-white border-b border-gray-200">
                  <div className="min-w-0">
                    <div className="text-xs font-semibold tracking-[0.22em] text-gray-400 uppercase truncate">
                      {t('analysis_results')}
                    </div>
                    <div className="text-xs text-gray-600 truncate">
                      {results?.status || '—'} · {results?.completed_steps ?? 0}/{results?.total_steps ?? 0}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsResultsOpen((v) => !v)}
                    className="text-xs font-semibold text-gray-700 hover:text-gray-900"
                  >
                    {isResultsOpen ? t('hide_results') : t('view_results')}
                  </button>
                </div>

                {isResultsOpen && (
                  <div className="h-[calc(46vh-3rem)] overflow-y-auto p-4 space-y-4">
                    {Array.isArray(results?.errors) && results.errors.length > 0 && (
                      <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl p-4 text-sm">
                        <div className="text-xs font-semibold tracking-[0.18em] uppercase text-red-500">Errors</div>
                        <div className="mt-2 space-y-1">
                          {results.errors.map((e, idx) => (
                            <div key={`${e?.step_id || 'step'}_${idx}`} className="font-mono text-xs">
                              {e?.method || 'unknown'}: {e?.error || 'Unknown error'}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {Array.isArray(results?.results) && results.results.length > 0 ? (
                      results.results.map((step, idx) => (
                        <div key={step?.step_id || `${step?.method || 'step'}_${idx}`} className="space-y-3">
                          <div className="flex items-baseline justify-between">
                            <div className="text-sm font-bold text-gray-900 truncate">
                              {formatMethodName(step?.method)}
                            </div>
                            <div className="text-xs text-gray-500 font-mono">
                              {step?.status || '—'}
                            </div>
                          </div>
                          {renderStepResult(step)}
                        </div>
                      ))
                    ) : (
                      <div className="text-sm text-gray-500">No results yet</div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <TestConfigModal
        isOpen={isConfigModalOpen}
        onClose={handleCloseConfigModal}
        method={selectedTest?.id}
        initialConfig={editingTest?.config || {}}
        onConfigSave={handleConfigSave}
      />
    </div>
  );
};

export default AnalysisDesign;
