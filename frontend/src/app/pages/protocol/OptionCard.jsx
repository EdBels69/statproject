import React from 'react';

export default function OptionCard({ icon, title, desc, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-left p-6 border rounded-[2px] transition-colors relative overflow-hidden group ${disabled
        ? 'opacity-40 border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] cursor-not-allowed'
        : 'border-[color:var(--border-color)] hover:border-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)]'
        }`}
    >
      <div className="flex items-start gap-4">
        <div className={`w-12 h-12 rounded-[2px] border border-[color:var(--border-color)] flex items-center justify-center text-2xl transition-colors ${disabled ? 'bg-[color:var(--bg-secondary)]' : 'bg-[color:var(--bg-secondary)] group-hover:border-[color:var(--accent)]'}`}>
          {icon}
        </div>
        <div className="flex-1">
          <h3 className={`font-black text-lg ${disabled ? 'text-[color:var(--text-secondary)]' : 'text-[color:var(--text-primary)]'}`}>
            {title}
          </h3>
          <p className="text-sm text-[color:var(--text-secondary)] leading-tight mt-1">
            {desc}
          </p>
        </div>
      </div>
    </button>
  );
}
