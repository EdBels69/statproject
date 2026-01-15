import React, { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

// 4-step flow: Data → Variables → Analysis → Results
const FLOW_STEPS = [
  { id: 'data', icon: '📁', label: 'Данные', completeKey: 'dataLoaded' },
  { id: 'variables', icon: '📊', label: 'Переменные', completeKey: 'variablesSet' },
  { id: 'analyze', icon: '🧪', label: 'Анализ', completeKey: 'analysisDone' },
  { id: 'report', icon: '📄', label: 'Результат', completeKey: 'resultsReady' }
];

export default function ResearchFlowNav({
  active = 'data',
  datasetId = null,
  className = '',
  stepData = null,
  onStepClick = null,
}) {
  const navigate = useNavigate();
  const location = useLocation();

  const canUseDataset = Boolean(datasetId);

  const items = useMemo(() => FLOW_STEPS.map((step, idx) => {
    const isActive = step.id === active;
    const isDisabled = step.id !== 'data' && !canUseDataset;

    const isComplete = Boolean(stepData?.[step.completeKey]);
    const isRunning = step.id === 'analyze'
      ? Boolean(stepData?.analysisRunning)
      : (isActive && !isComplete);

    const status = isComplete ? '✅' : isRunning ? '🔄' : '○';
    const summary = stepData?.[`${step.id}_summary`] ? String(stepData[`${step.id}_summary`]) : '';

    const activeClasses = isActive
      ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]'
      : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)]';

    return {
      ...step,
      idx,
      isActive,
      isDisabled,
      isComplete,
      isRunning,
      status,
      summary,
      className: `rounded-[2px] border bg-[color:var(--white)] px-3 py-2 text-left transition disabled:opacity-40 disabled:cursor-not-allowed ${activeClasses}`
    };
  }), [active, canUseDataset, stepData]);

  const go = (stepId) => {
    if (stepId === 'data') {
      navigate('/datasets');
      return;
    }

    if (!datasetId) {
      navigate('/datasets');
      return;
    }

    // 4-step flow: data → variables → analyze → report
    if (stepId === 'variables') {
      navigate(`/prep/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'analyze') {
      navigate(`/design/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'report') {
      navigate(`/report/${datasetId}`, { state: location.state });
    }
  };

  return (
    <nav aria-label="Research flow" className={className}>
      <div className="flex items-stretch justify-between gap-2">
        {items.map((step, idx) => (
          <React.Fragment key={step.id}>
            {idx > 0 && (
              <div className="flex items-center" aria-hidden="true">
                <div className={`h-px w-6 ${items[idx - 1]?.isComplete ? 'bg-[color:var(--accent)]' : 'bg-[color:var(--border-color)]'}`} />
              </div>
            )}
            <button
              type="button"
              onClick={() => {
                if (typeof onStepClick === 'function') {
                  onStepClick(step.id);
                  return;
                }
                go(step.id);
              }}
              disabled={step.isDisabled}
              aria-current={step.isActive ? 'step' : undefined}
              className={`${step.className} w-full`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-base" aria-hidden="true">{step.icon}</span>
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
                      {String(step.idx + 1).padStart(2, '0')}
                    </div>
                  </div>
                  <div className="mt-1 text-sm font-black tracking-tight truncate">
                    {step.label}
                  </div>
                  {step.summary ? (
                    <div className="mt-1 text-[10px] text-[color:var(--text-muted)] font-mono truncate">
                      {step.summary}
                    </div>
                  ) : null}
                </div>
                <div className="text-xs text-[color:var(--text-secondary)]" aria-label={step.isComplete ? 'Завершено' : step.isRunning ? 'В процессе' : 'Ожидает'}>
                  {step.status}
                </div>
              </div>
            </button>
          </React.Fragment>
        ))}
      </div>
    </nav>
  );
}
