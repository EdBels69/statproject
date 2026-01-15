import React, { useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const FLOW_STEPS = [
  { id: 'data', label: 'DATA' },
  { id: 'design', label: 'DESIGN' },
  { id: 'analyze', label: 'ANALYZE' },
  { id: 'report', label: 'REPORT' }
];

export default function ResearchFlowNav({ active = 'data', datasetId = null, className = '' }) {
  const navigate = useNavigate();
  const location = useLocation();

  const canUseDataset = Boolean(datasetId);

  const items = useMemo(() => FLOW_STEPS.map((step, idx) => {
    const isActive = step.id === active;
    const isDisabled = step.id !== 'data' && !canUseDataset;

    const activeClasses = isActive
      ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]'
      : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)]';

    return {
      ...step,
      idx,
      isActive,
      isDisabled,
      className: `rounded-[2px] border bg-[color:var(--white)] px-3 py-2 text-left transition disabled:opacity-40 disabled:cursor-not-allowed ${activeClasses}`
    };
  }), [active, canUseDataset]);

  const go = (stepId) => {
    if (stepId === 'data') {
      navigate('/datasets');
      return;
    }

    if (!datasetId) {
      navigate('/datasets');
      return;
    }

    if (stepId === 'design') {
      navigate(`/design/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'analyze') {
      navigate(`/analyze/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'report') {
      navigate(`/report/${datasetId}`, { state: location.state });
    }
  };

  return (
    <nav aria-label="Research flow" className={className}>
      <div className="grid grid-cols-4 gap-2">
        {items.map((step) => (
          <button
            key={step.id}
            type="button"
            onClick={() => go(step.id)}
            disabled={step.isDisabled}
            aria-current={step.isActive ? 'step' : undefined}
            className={step.className}
          >
            <div className="flex items-baseline justify-between">
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)]">
                {String(step.idx + 1).padStart(2, '0')}
              </div>
              {step.isActive && (
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--accent)]">
                  ACTIVE
                </div>
              )}
            </div>
            <div className="mt-1 text-sm font-black tracking-tight">
              {step.label}
            </div>
          </button>
        ))}
      </div>
    </nav>
  );
}
