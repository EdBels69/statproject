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
        return 'text-blue-600 bg-blue-50';
      case 'mixed_effects':
        return 'text-purple-600 bg-purple-50';
      case 'clustered_correlation':
        return 'text-green-600 bg-green-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  if (recommendations.length === 0 && !isAnalyzing) {
    return null;
  }

  return (
    <div className="bg-gradient-to-br from-purple-50 to-blue-50 border border-purple-200 rounded-lg shadow-lg overflow-hidden">
      <div className="p-4 border-b border-purple-200 bg-white/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SparklesIcon className="w-5 h-5 text-purple-600" />
            <h3 className="font-semibold text-gray-900">
              {t('ai_recommendations')}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>
        <p className="text-sm text-gray-600 mt-1">
          {t('ai_recommendations_desc')}
        </p>
      </div>

      <div className="p-4 space-y-3 max-h-96 overflow-y-auto">
        {isAnalyzing ? (
          <div className="flex flex-col items-center justify-center py-8 text-gray-500">
            <SparklesIcon className="w-8 h-8 mb-3 text-purple-400 animate-pulse" />
            <p className="text-sm">{t('ai_analyzing_dataset')}</p>
          </div>
        ) : recommendations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-gray-500">
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
                className={`bg-white border ${isAdded ? 'border-green-300' : 'border-gray-200'} rounded-lg p-4 hover:shadow-md transition-shadow ${isAdded ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${colorClass} flex-shrink-0`}>
                    {icon}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="font-medium text-gray-900 text-sm">
                          {test.name}
                        </h4>
                        {confidence && (
                          <div className="text-xs text-gray-500 mt-1">
                            {t('confidence')}: {Math.round(confidence * 100)}%
                          </div>
                        )}
                      </div>

                      {!isAdded && (
                        <button
                          onClick={() => handleAddTest(recommendation)}
                          className="p-1 text-green-600 hover:text-green-700 hover:bg-green-50 rounded transition-colors flex-shrink-0"
                          title={t('add_to_protocol')}
                        >
                          <PlusIcon className="w-5 h-5" />
                        </button>
                      )}

                      {isAdded && (
                        <div className="flex items-center gap-1 text-xs text-green-600 flex-shrink-0">
                          <CheckCircleIcon className="w-4 h-4" />
                          <span>{t('added')}</span>
                        </div>
                      )}
                    </div>

                    {reason && (
                      <p className="text-xs text-gray-600 mt-2 leading-relaxed">
                        {reason}
                      </p>
                    )}

                    {test.config && (
                      <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
                        <div className="text-gray-500 mb-1">{t('suggested_config')}:</div>
                        <div className="space-y-1">
                          {Object.entries(test.config).map(([key, value]) => (
                            <div key={key} className="flex justify-between">
                              <span className="text-gray-600">{key}:</span>
                              <span className="text-gray-900 font-medium">
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
        <div className="p-3 bg-white/50 border-t border-purple-200">
          <div className="flex items-start gap-2 text-xs text-gray-600">
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
