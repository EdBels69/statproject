import React from 'react';

export default function StepPreviewPanel({ title, steps }) {
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  if (safeSteps.length === 0) return null;

  return (
    <div className="px-6">
      <div className="max-w-7xl mx-auto">
        <div className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
          <div className="px-4 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)]">
            <div className="text-[10px] font-semibold uppercase tracking-[0.22em] text-[color:var(--text-muted)]">
              {title}
            </div>
          </div>

          <div className="divide-y divide-[color:var(--border-color)]">
            {safeSteps.map((step, idx) => (
              <div key={`${step.label}_${idx}`} className="px-4 py-3">
                <div className="text-xs text-[color:var(--text-secondary)]">{step.label}</div>
                <div className="mt-1 text-sm text-[color:var(--text-primary)] font-mono">{step.summary}</div>
                {step.warning ? (
                  <div className="mt-1 text-xs text-amber-700"><span className="font-semibold">!</span> {step.warning}</div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
