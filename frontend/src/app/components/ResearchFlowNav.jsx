import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const FLOW_STEPS = [
  { id: 'data', icon: '📁', label: 'Данные', completeKey: 'dataLoaded' },
  { id: 'variables', icon: '📊', label: 'Переменные', completeKey: 'variablesSet' },
  { id: 'design', icon: '🧩', label: 'Дизайн', completeKey: 'designReady' },
  { id: 'results', icon: '📋', label: 'Результат', completeKey: 'resultsReady' },
  { id: 'graphs', icon: '📈', label: 'Графики', completeKey: 'graphsReady' },
  { id: 'report', icon: '📄', label: 'Отчет', completeKey: 'reportReady' }
];

export default function ResearchFlowNav({
  active = 'data',
  datasetId = null,
  className = '',
  stepData = null,
  onStepClick = null,
  variant = 'page',
  showMenu = true,
  showNextButton = true,
  topLabel = 'Данные',
  highlight = false,
  designBasePath = null,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const rootRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);

  const canUseDataset = Boolean(datasetId);

  const items = useMemo(() => FLOW_STEPS.map((step, idx) => {
    const isActive = step.id === active;
    const isDisabled = step.id !== 'data' && !canUseDataset;

    const isComplete = Boolean(stepData?.[step.completeKey]);
    const isRunning = isActive && !isComplete;

    const status = isComplete ? 'done' : isRunning ? 'running' : 'idle';
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

  const activeLabel = useMemo(() => {
    const hit = items.find((s) => s.isActive);
    return hit?.label || 'Результат';
  }, [items]);

  useEffect(() => {
    if (!isOpen) return;
    const onPointerDown = (e) => {
      const root = rootRef.current;
      if (!root) return;
      if (root.contains(e.target)) return;
      setIsOpen(false);
    };
    window.addEventListener('mousedown', onPointerDown);
    window.addEventListener('touchstart', onPointerDown, { passive: true });
    return () => {
      window.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('touchstart', onPointerDown);
    };
  }, [isOpen]);

  const go = (stepId) => {
    const resolvedDesignBasePath = designBasePath || (location.state?.origin === 'ai' ? '/ai' : '/design');

    if (stepId === 'data') {
      navigate('/datasets');
      return;
    }

    if (!datasetId) {
      navigate('/datasets');
      return;
    }

    if (stepId === 'variables') {
      navigate(`/prepare/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'design') {
      navigate(`${resolvedDesignBasePath}/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'results') {
      navigate(`/results/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'graphs') {
      navigate(`/graphs/${datasetId}`, { state: location.state });
      return;
    }

    if (stepId === 'report') {
      navigate(`/report/${datasetId}`, { state: location.state });
    }
  };

  const nextStep = useMemo(() => {
    const idx = FLOW_STEPS.findIndex((s) => s.id === active);
    if (idx < 0) return null;
    return FLOW_STEPS[idx + 1] || null;
  }, [active]);

  if (variant === 'topnav') {
    const triggerClasses = highlight
      ? 'text-[color:var(--accent)]'
      : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]';

    return (
      <div className={`relative ${className}`} ref={rootRef}>
        <button
          type="button"
          onClick={() => setIsOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={isOpen}
          className={`text-sm font-semibold transition ${triggerClasses}`}
        >
          {topLabel}
        </button>

        {isOpen ? (
          <div
            role="menu"
            className="absolute left-0 mt-3 w-[260px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] shadow-xl overflow-hidden z-30"
          >
            <div className="py-1">
              {items.map((step) => {
                const meta = step.status === 'done' ? 'готово' : step.status === 'running' ? 'в процессе' : '';
                return (
                  <button
                    key={step.id}
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setIsOpen(false);
                      if (typeof onStepClick === 'function') {
                        onStepClick(step.id);
                        return;
                      }
                      go(step.id);
                    }}
                    disabled={step.isDisabled}
                    className={`w-full px-4 py-3 text-left transition ${step.isActive ? 'bg-[color:var(--bg-tertiary)]' : 'hover:bg-[color:var(--bg-tertiary)]'} disabled:opacity-40 disabled:cursor-not-allowed`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className={`text-sm font-semibold truncate ${step.isActive ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}`}>{step.label}</div>
                        {step.summary ? (
                          <div className="mt-0.5 text-[10px] text-[color:var(--text-muted)] font-mono truncate">{step.summary}</div>
                        ) : null}
                      </div>
                      {meta ? (
                        <div className="text-[10px] font-semibold tracking-[0.16em] uppercase text-[color:var(--text-muted)] whitespace-nowrap">{meta}</div>
                      ) : null}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  const layoutClasses = showMenu && showNextButton
    ? 'justify-between'
    : showNextButton
      ? 'justify-end'
      : 'justify-start';

  return (
    <nav aria-label="Research flow" className={className} ref={rootRef}>
      <div className={`flex items-center gap-2 ${layoutClasses}`}>
        {showMenu ? (
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={isOpen}
              className="h-9 px-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-left hover:border-black transition"
            >
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Анализ</div>
              <div className="text-sm font-black tracking-tight text-[color:var(--text-primary)] truncate max-w-[220px]">{activeLabel}</div>
            </button>

            {isOpen ? (
              <div
                role="menu"
                className="absolute left-0 mt-2 w-[260px] rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] shadow-xl overflow-hidden z-20"
              >
                <div className="py-1">
                  {items.map((step) => {
                    const meta = step.status === 'done' ? 'готово' : step.status === 'running' ? 'в процессе' : '';
                    return (
                      <button
                        key={step.id}
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setIsOpen(false);
                          if (typeof onStepClick === 'function') {
                            onStepClick(step.id);
                            return;
                          }
                          go(step.id);
                        }}
                        disabled={step.isDisabled}
                        className={`w-full px-4 py-3 text-left transition ${step.isActive ? 'bg-[color:var(--bg-tertiary)]' : 'hover:bg-[color:var(--bg-tertiary)]'} disabled:opacity-40 disabled:cursor-not-allowed`}
                      >
                        <div className="flex items-center justify-between gap-4">
                          <div className="min-w-0">
                            <div className={`text-sm font-semibold truncate ${step.isActive ? 'text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}`}>{step.label}</div>
                            {step.summary ? (
                              <div className="mt-0.5 text-[10px] text-[color:var(--text-muted)] font-mono truncate">{step.summary}</div>
                            ) : null}
                          </div>
                          {meta ? (
                            <div className="text-[10px] font-semibold tracking-[0.16em] uppercase text-[color:var(--text-muted)] whitespace-nowrap">{meta}</div>
                          ) : null}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {showNextButton ? (
          <button
            type="button"
            onClick={() => {
              if (!nextStep) return;
              if (typeof onStepClick === 'function') {
                onStepClick(nextStep.id);
                return;
              }
              go(nextStep.id);
            }}
            disabled={!nextStep || (nextStep.id !== 'data' && !canUseDataset)}
            className={`h-9 px-4 rounded-[2px] text-xs font-bold uppercase tracking-[0.18em] border transition-colors ${(!nextStep || (nextStep.id !== 'data' && !canUseDataset))
              ? 'bg-[color:var(--bg-tertiary)] text-[color:var(--text-muted)] border-[color:var(--border-color)] opacity-60 cursor-not-allowed'
              : 'bg-[color:var(--black)] text-[color:var(--white)] border-[color:var(--black)] hover:opacity-90'
              }`}
          >
            Далее
          </button>
        ) : null}
      </div>
    </nav>
  );
}
