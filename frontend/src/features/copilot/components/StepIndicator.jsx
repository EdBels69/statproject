import React from 'react';

export default function StepIndicator({ currentStep, steps }) {
    return (
        <div style={{ display: 'flex', gap: '4px', marginBottom: '24px', padding: '0 4px' }}>
            {steps.map((label, i) => {
                const stepNum = i + 1;
                const isActive = stepNum === currentStep;
                const isDone = stepNum < currentStep;
                return (
                    <div key={i} style={{ flex: 1, textAlign: 'center' }}>
                        <div style={{
                            height: '4px',
                            borderRadius: '2px',
                            background: isDone ? '#22c55e' : isActive ? '#f97316' : '#27272a',
                            transition: 'background 0.3s'
                        }} />
                        <span style={{
                            fontSize: '11px',
                            color: isActive ? '#f97316' : isDone ? '#22c55e' : '#71717a',
                            marginTop: '4px',
                            display: 'block'
                        }}>
                            {stepNum}. {label}
                        </span>
                    </div>
                );
            })}
        </div>
    );
}
