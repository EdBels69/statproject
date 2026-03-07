import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import Button from '../../components/ui/Button';
import TestSelectionPanel from '../../components/analysis/TestSelectionPanel';
import ProtocolBuilder from '../../components/analysis/ProtocolBuilder';
import TestConfigModal from '../../components/TestConfigModal';
import AISuggestionsPane from '../../components/analysis/AISuggestionsPane';
import ProtocolTemplateSelector from '../../components/analysis/ProtocolTemplateSelector';
import ResearchFlowNav from '../../components/ResearchFlowNav';
import VariableWorkspace from '../../components/VariableWorkspace';
import SaveProtocolModal, { ProtocolLibraryModal, exportProtocolAsJsonFile } from '../../components/SaveProtocolModal';
import KeyboardShortcutsHelp from '../../components/KeyboardShortcutsHelp';
import VariablePreview from './VariablePreview';
import StepPreviewPanel from './StepPreviewPanel';
import VibeDesignModal from './VibeDesignModal';
import MassDynamicsModal from './MassDynamicsModal';
import StepResultRenderer from './StepResultRenderer';

export default function AnalysisDesignWorkspaceLayout({
  t,
  mode,
  onBack,
  datasetName,
  navigate,
  datasetIdResolved,
  columns,
  flowStepData,
  designReviewConfirmed,
  designReviewTimestamp,
  designReviewError,
  designReviewSaving,
  isExecuting,
  handleToggleDesignReview,
  protocol,
  handleTestSelect,
  workspaceRoles,
  setMassDynamicsSeed,
  setIsMassDynamicsOpen,
  templates,
  templatesLoading,
  templatesError,
  selectedTemplateId,
  setSelectedTemplateId,
  setTemplateVars,
  selectedTemplate,
  templateVars,
  columnNames,
  columnStatsByName,
  canApplyTemplate,
  handleApplyTemplate,
  selectedStepId,
  setSelectedStepId,
  handleToggleTest,
  handleEditTest,
  resetProtocolHistory,
  setResults,
  formatMethodName,
  handleMoveTest,
  handleExecuteProtocol,
  handleAISuggest,
  openVibe,
  setSaveProtocolSeed,
  setIsSaveProtocolOpen,
  setIsProtocolLibraryOpen,
  undoProtocol,
  redoProtocol,
  canUndo,
  canRedo,
  isAIAnalyzing,
  results,
  isResultsOpen,
  setIsResultsOpen,
  humanizeError,
  rightPane,
  setRightPane,
  aiRecommendations,
  aiError,
  handleAddRecommendation,
  roleByName,
  handleWorkspaceRolesChange,
  templateSecondaryKey,
  previewSteps,
  selectedStepMeta,
  handleRemoveTest,
  massDynamicsSeed,
  isMassDynamicsOpen,
  handleAppendMassSteps,
  isVibeOpen,
  setIsVibeOpen,
  vibeText,
  setVibeText,
  globalDefaults,
  handleGlobalSettingsChange,
  handleVibeGenerate,
  handleVibeGenerateAndRun,
  isVibeLoading,
  vibeError,
  vibePreview,
  handleApplyVibePreview,
  isConfigModalOpen,
  handleCloseConfigModal,
  selectedTest,
  editingTest,
  handleConfigSave,
  isSaveProtocolOpen,
  saveProtocolSeed,
  handleSaveProtocol,
  isProtocolLibraryOpen,
  savedProtocols,
  applySavedProtocol,
  setSavedProtocols,
  handleImportProtocol,
  isShortcutsHelpOpen,
  setIsShortcutsHelpOpen,
}) {
  return (
    <>
      <div className="-mx-6 -my-6 min-h-[calc(100vh-56px)] flex flex-col bg-[color:var(--bg-secondary)]">
        <div className="bg-[color:var(--white)] border-b border-[color:var(--border-color)] px-6 py-4">
          <div className="max-w-7xl mx-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={onBack}
                  className="h-9 w-9 inline-flex items-center justify-center rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-black hover:text-black active:scale-[0.98]"
                  type="button"
                  aria-label={t('back')}
                >
                  <ArrowLeftIcon className="w-5 h-5" />
                </button>
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('analysis')}</div>
                  <h1 className="text-xl font-bold text-[color:var(--text-primary)] truncate">{datasetName || t('dataset')}</h1>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <div className="h-9 p-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => navigate(datasetIdResolved ? `/tests/${datasetIdResolved}` : '/tests')}
                    className={`h-7 px-3 rounded-[2px] text-xs font-semibold ${mode === 'tests' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                  >
                    {t('tests')}
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(datasetIdResolved ? `/${mode === 'protocol' ? 'protocol' : 'design'}/${datasetIdResolved}` : (mode === 'protocol' ? '/protocol' : '/design'))}
                    className={`h-7 px-3 rounded-[2px] text-xs font-semibold ${mode !== 'tests' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                  >
                    Конструктор
                  </button>
                </div>
                <Button
                  onClick={() => {
                    if (!datasetIdResolved) return;
                    navigate(`/prep/${datasetIdResolved}`);
                  }}
                  disabled={!columns.length}
                  variant="ghost"
                  className="gap-2 min-w-[160px] justify-start"
                  type="button"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                  </svg>
                  <span className="tabular-nums">{t('variables')} ({columns.length})</span>
                </Button>
              </div>
            </div>

            <ResearchFlowNav active="design" datasetId={datasetIdResolved} className="mt-3" stepData={flowStepData} showMenu={false} />

            {datasetIdResolved ? (
              <div className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-4 py-3 flex items-center justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <div className="text-[10px] font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Design Review</div>
                  <div className={`mt-1 text-sm font-semibold ${designReviewConfirmed ? 'text-[color:var(--success)]' : 'text-[color:var(--accent)]'}`}>
                    {designReviewConfirmed ? 'Подтверждено' : 'Не подтверждено'}
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--text-secondary)]">
                    {designReviewTimestamp ? `Подтверждено: ${designReviewTimestamp}` : 'Перед запуском анализа подтвердите дизайн исследования.'}
                  </div>
                  {designReviewError ? (
                    <div className="mt-1 text-xs text-[color:var(--accent)]">{designReviewError}</div>
                  ) : null}
                </div>
                <div className="flex items-center gap-3">
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={designReviewConfirmed}
                      onChange={(e) => handleToggleDesignReview(e.target.checked)}
                      disabled={designReviewSaving || isExecuting}
                      className="h-4 w-4 accent-black"
                    />
                    Подтверждаю Design Review
                  </label>
                  <button
                    type="button"
                    onClick={() => navigate(`/design/${datasetIdResolved}`)}
                    className="h-9 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-black"
                  >
                    Открыть Design Review
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {mode === 'tests' ? (
            <div className="w-[420px] max-w-[48vw] shrink-0 border-r border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
              <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('tests')}</div>
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{protocol.length} шаг(ов)</div>
              </div>

              <div className="flex-1 overflow-hidden">
                <TestSelectionPanel
                  variant="compact"
                  onTestSelect={handleTestSelect}
                  datasetId={datasetIdResolved}
                  suggestedConfig={workspaceRoles}
                  disabled={isExecuting}
                />
              </div>
            </div>
          ) : (
            <div className="w-[360px] max-w-[45vw] shrink-0 border-r border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
              <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('templates')}</div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setMassDynamicsSeed(Date.now());
                      setIsMassDynamicsOpen(true);
                    }}
                    disabled={!datasetIdResolved || columns.length === 0}
                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Массовая динамика
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/tests/${datasetIdResolved}`)}
                    className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                  >
                    {t('tests')}
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-hidden">
                <div className="h-full overflow-y-auto bg-[color:var(--bg-secondary)]">
                  <ProtocolTemplateSelector
                    templates={templates}
                    templatesLoading={templatesLoading}
                    templatesError={templatesError}
                    selectedTemplateId={selectedTemplateId}
                    onSelectedTemplateIdChange={(nextId) => {
                      setSelectedTemplateId(nextId);
                      setTemplateVars((v) => ({ ...v, group: '', predictor: '' }));
                    }}
                    selectedTemplate={selectedTemplate}
                    templateVars={templateVars}
                    onTemplateVarsChange={setTemplateVars}
                    columnNames={columnNames}
                    columns={columns}
                    columnStatsByName={columnStatsByName}
                    canApplyTemplate={canApplyTemplate}
                    onApplyTemplate={handleApplyTemplate}
                    disabled={isExecuting}
                  />
                </div>
              </div>
            </div>
          )}

          {mode === 'tests' ? (
            <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
              <div className="h-12 px-4 flex items-center justify-between border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                <div className="min-w-0">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase truncate">Очередь</div>
                  <div className="text-xs text-[color:var(--text-secondary)] truncate">Собери шаги, затем открой конструктор.</div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (protocol.length === 0) return;
                      if (!confirm('Очистить список шагов?')) return;
                      resetProtocolHistory([]);
                      setResults(null);
                      setSelectedStepId(null);
                    }}
                    disabled={protocol.length === 0}
                    className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Очистить
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/design/${datasetIdResolved}`)}
                    className="h-9 px-4 rounded-[2px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold uppercase tracking-[0.18em] hover:opacity-90"
                  >
                    Конструктор
                  </button>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 bg-[color:var(--bg-secondary)]">
                {protocol.length === 0 ? (
                  <div className="h-full rounded-[2px] border border-dashed border-[color:var(--border-color)] bg-[color:var(--white)] flex items-center justify-center text-sm text-[color:var(--text-secondary)]">
                    Выбери тест слева — он появится здесь.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {protocol.map((step, idx) => (
                      <div key={step.id} className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] px-4 py-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Шаг {idx + 1}</div>
                            <div className="mt-1 text-sm font-bold text-[color:var(--text-primary)] truncate">{step.name || formatMethodName(step.method)}</div>
                            <div className="mt-1 text-xs text-[color:var(--text-secondary)] font-mono truncate">{step.method}</div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <label className="h-8 px-3 inline-flex items-center gap-2 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:border-black">
                              <input
                                type="checkbox"
                                checked={step?.enabled !== false}
                                onChange={(e) => handleToggleTest(step.id, e.target.checked)}
                                className="h-4 w-4 accent-black"
                                aria-label="Включить в анализ"
                              />
                              <span className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-secondary)] uppercase">Включить в анализ</span>
                            </label>
                            <button
                              type="button"
                              onClick={() => handleEditTest(step)}
                              className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                            >
                              {t('edit')}
                            </button>
                          </div>
                        </div>
                        {step.config && typeof step.config === 'object' ? (
                          <div className="mt-3 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-2">
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1">
                              {Object.entries(step.config).slice(0, 8).map(([k, v]) => (
                                <div key={k} className="flex items-baseline justify-between gap-3">
                                  <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{k}</div>
                                  <div className="text-xs text-[color:var(--text-primary)] font-mono truncate">{Array.isArray(v) ? v.filter(Boolean).join(', ') : String(v ?? '')}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
                <div className="flex-1 overflow-hidden">
                  <ProtocolBuilder
                    protocol={protocol}
                    selectedStepId={selectedStepId}
                    onSelectStep={(id) => setSelectedStepId(id)}
                    onToggleTest={handleToggleTest}
                    onEditTest={handleEditTest}
                    onMoveTest={handleMoveTest}
                    onExecuteProtocol={handleExecuteProtocol}
                    onAISuggest={handleAISuggest}
                    onVibeDesign={openVibe}
                    onSaveProtocol={() => {
                      if (protocol.length === 0) return;
                      setSaveProtocolSeed(Date.now());
                      setIsSaveProtocolOpen(true);
                    }}
                    onOpenProtocols={() => setIsProtocolLibraryOpen(true)}
                    onUndo={undoProtocol}
                    onRedo={redoProtocol}
                    canUndo={canUndo}
                    canRedo={canRedo}
                    isExecuting={isExecuting}
                    isAIAnalyzing={isAIAnalyzing}
                  />
                </div>

                {results && (
                  <div className={`border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex-shrink-0 ${isResultsOpen ? 'h-[46vh]' : 'h-12'} transition-[height] duration-200 overflow-hidden`}>
                    <div className="h-12 px-4 flex items-center justify-between bg-[color:var(--white)] border-b border-[color:var(--border-color)]">
                      <div className="min-w-0">
                        <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase truncate">
                          {t('analysis_results')}
                        </div>
                        <div className="text-xs text-[color:var(--text-secondary)] truncate">
                          {results?.status || t('not_available_short')} · {results?.completed_steps ?? 0}/{results?.total_steps ?? 0}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setIsResultsOpen((v) => !v)}
                        className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-black"
                      >
                        {isResultsOpen ? t('hide_results') : t('view_results')}
                      </button>
                    </div>

                    {isResultsOpen && (
                      <div className="h-[calc(46vh-3rem)] overflow-y-auto p-4 space-y-4" aria-live="polite">
                        {Array.isArray(results?.errors) && results.errors.length > 0 && (
                          <div className="bg-[color:var(--white)] border border-[color:var(--black)] text-[color:var(--text-primary)] rounded-[2px] p-4 text-sm">
                            <div className="text-xs font-semibold tracking-[0.18em] uppercase text-[color:var(--accent)]">{t('errors')}</div>
                            <div className="mt-2 space-y-2">
                              {results.errors.map((e, idx) => {
                                const h = humanizeError(e?.error);
                                return (
                                  <div key={`${e?.step_id || 'step'}_${idx}`} className="rounded-[2px] bg-[color:var(--bg-tertiary)] border border-[color:var(--border-color)] p-3">
                                    <div className="flex items-baseline justify-between gap-3">
                                      <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">
                                        {e?.method || t('unknown')}
                                      </div>
                                      <div className="text-[10px] text-[color:var(--text-secondary)] font-mono truncate">
                                        {h.details ? h.details : (e?.error || t('unknown_error'))}
                                      </div>
                                    </div>
                                    <div className="mt-2 text-sm font-semibold text-[color:var(--text-primary)]">
                                      {h.title}
                                    </div>
                                    {Array.isArray(h.actions) && h.actions.length > 0 && (
                                      <div className="mt-2 text-xs text-[color:var(--text-secondary)]">
                                        <div className="text-[10px] font-semibold tracking-[0.18em] uppercase text-[color:var(--text-muted)]">Что делать:</div>
                                        <ul className="mt-1 list-disc pl-4 space-y-0.5">
                                          {h.actions.map((a, i) => (
                                            <li key={`${idx}_a_${i}`}>{a}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {Array.isArray(results?.results) && results.results.length > 0 ? (
                          results.results.map((step, idx) => (
                            <div key={step?.step_id || `${step?.method || 'step'}_${idx}`} className="space-y-3">
                              <div className="flex items-baseline justify-between">
                                <div className="text-sm font-bold text-[color:var(--text-primary)] truncate">
                                  {formatMethodName(step?.method)}
                                </div>
                                <div className="text-xs text-[color:var(--text-secondary)] font-mono">
                                  {step?.status || t('not_available_short')}
                                </div>
                              </div>
                              <StepResultRenderer step={step} t={t} formatMethodName={formatMethodName} />
                            </div>
                          ))
                        ) : (
                          <div className="text-sm text-[color:var(--text-secondary)]">{t('no_results_yet')}</div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="w-[420px] max-w-[48vw] shrink-0 border-l border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
                <div className="h-12 px-3 flex items-center justify-between border-b border-[color:var(--border-color)]">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setRightPane('inspector')}
                      className={`h-8 px-3 rounded-[2px] text-xs font-semibold ${rightPane === 'inspector' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                    >
                      Инспектор
                    </button>
                    <button
                      type="button"
                      onClick={() => setRightPane('ai')}
                      className={`h-8 px-3 rounded-[2px] text-xs font-semibold ${rightPane === 'ai' ? 'bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)]'}`}
                    >
                      ИИ
                    </button>
                  </div>

                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{protocol.length} шаг(ов)</div>
                </div>

                <div className="flex-1 overflow-y-auto p-3 bg-[color:var(--bg-secondary)]">
                  {rightPane === 'ai' ? (
                    <AISuggestionsPane
                      t={t}
                      protocol={protocol}
                      recommendations={aiRecommendations}
                      isAnalyzing={isAIAnalyzing}
                      error={aiError}
                      onSuggest={handleAISuggest}
                      onAddRecommendation={handleAddRecommendation}
                      onClose={() => setRightPane('inspector')}
                    />
                  ) : (
                    <div className="space-y-3">
                      <div className="h-[540px]">
                        <VariableWorkspace
                          columns={columns}
                          columnStatsByName={columnStatsByName}
                          roleByName={roleByName}
                          roles={workspaceRoles}
                          onRolesChange={handleWorkspaceRolesChange}
                          secondaryRoleLabel={templateSecondaryKey === 'predictor' ? t('predictor') : t('group')}
                        />
                      </div>

                      {(workspaceRoles?.target || workspaceRoles?.group) ? (
                        <VariablePreview
                          t={t}
                          targetVar={workspaceRoles?.target}
                          groupVar={workspaceRoles?.group}
                          groupLabel={templateSecondaryKey === 'predictor' ? t('predictor') : t('group')}
                          statsByName={columnStatsByName}
                        />
                      ) : null}

                      <StepPreviewPanel title={t('preview')} steps={previewSteps} />

                      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                        <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Шаг</div>
                            <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">
                              {selectedStepMeta.step ? (selectedStepMeta.step.name || formatMethodName(selectedStepMeta.step.method)) : 'Не выбран'}
                            </div>
                          </div>

                          {selectedStepMeta.step ? (
                            <div className="flex items-center gap-1 flex-shrink-0">
                              <button
                                type="button"
                                onClick={() => {
                                  if (selectedStepMeta.index > 0) handleMoveTest(selectedStepMeta.index, selectedStepMeta.index - 1);
                                }}
                                disabled={selectedStepMeta.index <= 0}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-[2px] border border-transparent text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)] disabled:opacity-40 disabled:cursor-not-allowed"
                                title={t('move_up')}
                              >
                                ↑
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (selectedStepMeta.index >= 0 && selectedStepMeta.index < protocol.length - 1) handleMoveTest(selectedStepMeta.index, selectedStepMeta.index + 1);
                                }}
                                disabled={selectedStepMeta.index < 0 || selectedStepMeta.index >= protocol.length - 1}
                                className="h-8 w-8 inline-flex items-center justify-center rounded-[2px] border border-transparent text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--border-color)] disabled:opacity-40 disabled:cursor-not-allowed"
                                title={t('move_down')}
                              >
                                ↓
                              </button>
                              <button
                                type="button"
                                onClick={() => handleEditTest(selectedStepMeta.step)}
                                className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                              >
                                {t('edit')}
                              </button>
                            </div>
                          ) : null}
                        </div>

                        <div className="p-3">
                          {protocol.length > 0 && !selectedStepMeta.step ? (
                            <div className="text-xs text-[color:var(--text-secondary)]">Выбери шаг в центре — здесь будет его конфиг.</div>
                          ) : null}

                          {protocol.length === 0 ? (
                            <div className="text-xs text-[color:var(--text-secondary)]">Добавь шаг через «Тесты».</div>
                          ) : null}

                          {selectedStepMeta.step ? (
                            <div className="space-y-3">
                              <div className="text-xs text-[color:var(--text-secondary)] font-mono">{selectedStepMeta.step.method}</div>

                              {selectedStepMeta.step.config && typeof selectedStepMeta.step.config === 'object' ? (
                                <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-2">
                                  <div className="space-y-1">
                                    {Object.entries(selectedStepMeta.step.config).map(([k, v]) => (
                                      <div key={k} className="flex items-baseline justify-between gap-3">
                                        <div className="text-[10px] font-semibold tracking-[0.18em] text-[color:var(--text-muted)] uppercase">{k}</div>
                                        <div className="text-xs text-[color:var(--text-primary)] font-mono truncate">
                                          {Array.isArray(v) ? v.filter(Boolean).join(', ') : String(v ?? '')}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ) : null}

                              <button
                                type="button"
                                onClick={() => {
                                  if (!confirm('Удалить шаг?')) return;
                                  handleRemoveTest(selectedStepMeta.step.id);
                                  setSelectedStepId(null);
                                }}
                                className="h-9 w-full rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--accent)] hover:border-black"
                              >
                                {t('remove')}
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      <MassDynamicsModal
        key={massDynamicsSeed}
        isOpen={isMassDynamicsOpen}
        onClose={() => setIsMassDynamicsOpen(false)}
        columns={columns}
        statsByName={columnStatsByName}
        defaultGroupCol={workspaceRoles?.group || ''}
        defaultSubjectCol=""
        formatMethodName={formatMethodName}
        onAppendSteps={handleAppendMassSteps}
      />

      <VibeDesignModal
        isOpen={isVibeOpen}
        onClose={() => setIsVibeOpen(false)}
        value={vibeText}
        onValueChange={setVibeText}
        globalSettings={globalDefaults}
        onGlobalSettingsChange={handleGlobalSettingsChange}
        onGenerate={handleVibeGenerate}
        onGenerateAndRun={handleVibeGenerateAndRun}
        isLoading={isVibeLoading}
        error={vibeError}
        preview={vibePreview}
        onApply={handleApplyVibePreview}
      />

      <TestConfigModal
        isOpen={isConfigModalOpen}
        onClose={handleCloseConfigModal}
        method={selectedTest?.id}
        initialConfig={editingTest?.config || {}}
        onConfigSave={handleConfigSave}
        columns={columns}
        suggestedConfig={workspaceRoles}
        datasetId={datasetIdResolved}
      />

      <SaveProtocolModal
        key={saveProtocolSeed}
        isOpen={isSaveProtocolOpen}
        onClose={() => setIsSaveProtocolOpen(false)}
        onSave={handleSaveProtocol}
        defaultName={datasetName ? `Протокол: ${datasetName}` : 'Мой протокол'}
        defaultDescription=""
      />

      <ProtocolLibraryModal
        isOpen={isProtocolLibraryOpen}
        onClose={() => setIsProtocolLibraryOpen(false)}
        protocols={savedProtocols}
        onLoad={applySavedProtocol}
        onDelete={(id) => {
          setSavedProtocols((prev) => (Array.isArray(prev) ? prev.filter((p) => p.id !== id) : []));
        }}
        onImport={handleImportProtocol}
        onExport={(p) => exportProtocolAsJsonFile(p)}
      />

      <KeyboardShortcutsHelp
        isOpen={isShortcutsHelpOpen}
        onClose={() => setIsShortcutsHelpOpen(false)}
      />
    </>
  );
}
