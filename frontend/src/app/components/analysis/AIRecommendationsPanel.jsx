import React, { useState } from 'react';
import {
  SparklesIcon,
  XMarkIcon,
  PlusIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';
import { useTranslation } from '../../../hooks/useTranslation';

const AIRecommendationsPanel = ({
  recommendations = [],
  onAddRecommendation,
  onClose,
  isAnalyzing = false
}) => {
  const { t } = useTranslation();
  const [addedTests, setAddedTests] = useState(new Set());

  const handleAddTest = (recommendation) => {
    onAddRecommendation(recommendation);
    setAddedTests(prev => new Set([...prev, recommendation.test.id]));
  };

  const getTestIcon = (testType) => {
    switch (testType) {
      case 'mann_whitney':
      case 't_test':
      case 'welch_t_test':
        return <InformationCircleIcon className="w-5 h-5" />;
      case 'mixed_effects':
        return <CheckCircleIcon className="w-5 h-5" />;
      case 'clustered_correlation':
        return <SparklesIcon className="w-5 h-5" />;
      default:
        return <ExclamationTriangleIcon className="w-5 h-5" />;
    }
  };

  const getTestColor = (testType) => {
    switch (testType) {
      case 'mann_whitney':
      case 't_test':
        return 'text-[color:var(--accent)] bg-[color:var(--bg-secondary)]';
      case 'mixed_effects':
        return 'text-[color:var(--accent)] bg-[color:var(--bg-secondary)]';
      case 'clustered_correlation':
        return 'text-[color:var(--accent)] bg-[color:var(--bg-secondary)]';
      default:
        return 'text-[color:var(--text-muted)] bg-[color:var(--bg-secondary)]';
    }
  };

  if (recommendations.length === 0 && !isAnalyzing) {
    return null;
  }

  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
      <div className="p-4 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SparklesIcon className="w-5 h-5 text-[color:var(--accent)]" />
            <h3 className="font-semibold text-[color:var(--text-primary)]">
              {t('ai_recommendations')}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--white)] rounded-[2px] border border-transparent hover:border-[color:var(--border-color)] transition-colors"
            type="button"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-[color:var(--text-muted)] mt-1">
          {t('ai_recommendations_desc')}
        </p>
      </div>

      <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
        {isAnalyzing ? (
          <div className="flex flex-col items-center justify-center py-8 text-[color:var(--text-muted)]">
            <SparklesIcon className="w-8 h-8 mb-3 text-[color:var(--accent)] animate-pulse" />
            <p className="text-sm">{t('ai_analyzing_dataset')}</p>
          </div>
        ) : recommendations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-[color:var(--text-muted)]">
            <InformationCircleIcon className="w-8 h-8 mb-3" />
            <p className="text-sm">{t('ai_no_recommendations')}</p>
          </div>
        ) : (
          recommendations.map((recommendation, index) => {
            const { test, reason, confidence } = recommendation;
            const isAdded = addedTests.has(test.id);
            const colorClass = getTestColor(test.id);
            const icon = getTestIcon(test.id);

            return (
              <div
                key={index}
                className={`bg-[color:var(--white)] border ${isAdded ? 'border-[color:var(--accent)]' : 'border-[color:var(--border-color)]'} rounded-[2px] p-4 transition-colors ${isAdded ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-[2px] border border-[color:var(--border-color)] ${colorClass} flex-shrink-0`}>
                    {icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="font-medium text-[color:var(--text-primary)] text-sm">
                          {test.name}
                        </h4>
                        {confidence && (
                          <div className="text-xs text-[color:var(--text-muted)] mt-1">
                            {t('confidence')}: {Math.round(confidence * 100)}%
                          </div>
                        )}
                      </div>

                      {!isAdded && (
                        <button
                          onClick={() => handleAddTest(recommendation)}
                          className="p-1 text-[color:var(--accent)] hover:opacity-80 hover:bg-[color:var(--bg-secondary)] rounded-[2px] border border-transparent hover:border-[color:var(--border-color)] transition-colors flex-shrink-0"
                          title={t('add_to_protocol')}
                          type="button"
                        >
                          <PlusIcon className="w-5 h-5" />
                        </button>
                      )}

                      {isAdded && (
                        <div className="flex items-center gap-1 text-xs text-[color:var(--accent)] flex-shrink-0">
                          <CheckCircleIcon className="w-4 h-4" />
                          <span>{t('added')}</span>
                        </div>
                      )}
                    </div>

                    {reason && (
                      <p className="text-xs text-[color:var(--text-muted)] mt-2 leading-relaxed">
                        {reason}
                      </p>
                    )}

                    {test.config && (
                      <div className="mt-2 p-2 bg-[color:var(--bg-secondary)] rounded-[2px] border border-[color:var(--border-color)] text-xs">
                        <div className="text-[color:var(--text-muted)] mb-1">{t('suggested_config')}:</div>
                        <div className="space-y-1">
                          {Object.entries(test.config).map(([key, value]) => (
                            <div key={key} className="flex justify-between">
                              <span className="text-[color:var(--text-muted)]">{key}:</span>
                              <span className="text-[color:var(--text-primary)] font-medium">
                                {Array.isArray(value) ? value.join(', ') : String(value)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {!isAnalyzing && recommendations.length > 0 && (
        <div className="p-3 bg-[color:var(--bg-secondary)] border-t border-[color:var(--border-color)]">
          <div className="flex items-start gap-2 text-xs text-[color:var(--text-muted)]">
            <InformationCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              {t('ai_disclaimer')}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIRecommendationsPanel;
