import React, { useMemo } from 'react';
import AIRecommendationsPanel from './AIRecommendationsPanel';

export default function AISuggestionsPane({
  t,
  protocol,
  recommendations,
  isAnalyzing,
  error,
  onSuggest,
  onAddRecommendation,
  onClose,
}) {
  const safeT = useMemo(() => {
    return typeof t === 'function' ? t : (k) => String(k);
  }, [t]);

  const canSuggest = Array.isArray(protocol);

  return (
    <div className="space-y-3">
      <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Рекомендации</div>
          <button
            type="button"
            onClick={onSuggest}
            disabled={isAnalyzing || !canSuggest}
            className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isAnalyzing ? safeT('ai_analyzing') : safeT('ai_suggest_tests')}
          </button>
        </div>
        <div className="mt-2 text-xs text-[color:var(--text-secondary)]">ИИ предлагает шаги поверх твоего текущего пайплайна.</div>
        {error ? (
          <div className="mt-2 text-xs text-[color:var(--error)]">
            {String(error)}
          </div>
        ) : null}
      </div>

      <AIRecommendationsPanel
        recommendations={Array.isArray(recommendations) ? recommendations : []}
        onAddRecommendation={(rec) => {
          if (!rec?.test?.id) return;
          onAddRecommendation?.(rec);
        }}
        onClose={onClose}
        isAnalyzing={Boolean(isAnalyzing)}
      />

      {!isAnalyzing && (!Array.isArray(recommendations) || recommendations.length === 0) ? (
        <div className="text-xs text-[color:var(--text-muted)]">Нажми «{safeT('ai_suggest_tests')}» чтобы получить предложения.</div>
      ) : null}
    </div>
  );
}
