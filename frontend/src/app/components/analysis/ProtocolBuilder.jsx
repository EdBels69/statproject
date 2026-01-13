import React, { useState } from 'react';
import {
  DocumentTextIcon,
  SparklesIcon,
  PlayIcon,
  TrashIcon,
  PencilIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';
import { useTranslation } from '../../../hooks/useTranslation';

const ProtocolBuilder = ({
  protocol,
  datasetName,
  onRemoveTest,
  onEditTest,
  onMoveTest,
  onExecuteProtocol,
  onAISuggest,
  isExecuting = false,
  isAIAnalyzing = false
}) => {
  const { t } = useTranslation();
  const [expandedTests, setExpandedTests] = useState({});

  const toggleTestExpansion = (testId) => {
    setExpandedTests(prev => ({
      ...prev,
      [testId]: !prev[testId]
    }));
  };

  const handleMoveUp = (index) => {
    if (index > 0) {
      onMoveTest(index, index - 1);
    }
  };

  const handleMoveDown = (index) => {
    if (index < protocol.length - 1) {
      onMoveTest(index, index + 1);
    }
  };

  const getTestDisplayName = (test) => {
    if (test.method === 'mixed_effects') {
      return 'Mixed Effects (LMM)';
    }
    if (test.method === 'clustered_correlation') {
      return 'Clustered Correlation';
    }
    return test.method.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const getTestDescription = (test) => {
    if (test.method === 'mixed_effects' && test.config) {
      const { outcome, time, group } = test.config;
      return `${outcome} ~ ${time} * ${group}`;
    }
    if (test.method === 'clustered_correlation' && test.config) {
      const variables = test.config.variables || [];
      return `${variables.length} переменных`;
    }
    if (test.config?.outcome && test.config?.group) {
      return `${test.config.outcome} ~ ${test.config.group}`;
    }
    return '';
  };

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="p-4 border-b border-gray-200 bg-white">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <DocumentTextIcon className="w-5 h-5 text-green-600" />
          {t('protocol_builder')}
        </h2>
        
        {datasetName && (
          <div className="mt-2 p-2 bg-blue-50 rounded-lg">
            <div className="text-xs text-blue-700 font-medium">
              Dataset:
            </div>
            <div className="text-sm text-blue-900 truncate">
              {datasetName}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {protocol.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <DocumentTextIcon className="w-12 h-12 mb-3 opacity-50" />
            <p className="text-sm text-center">
              {t('protocol_empty')}
            </p>
            <p className="text-xs text-center mt-1">
              {t('protocol_empty_hint')}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {protocol.map((test, index) => {
              const isExpanded = expandedTests[test.id];
              const displayName = getTestDisplayName(test);
              const description = getTestDescription(test);

              return (
                <div
                  key={test.id}
                  className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow"
                >
                  <div className="p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-gray-500">
                            {index + 1}.
                          </span>
                          <div className="font-medium text-gray-900 text-sm">
                            {displayName}
                          </div>
                        </div>
                        
                        {description && (
                          <div className="text-xs text-gray-600 mt-1 ml-6">
                            {description}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleMoveUp(index)}
                          disabled={index === 0}
                          className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                          title={t('move_up')}
                        >
                          <ArrowUpIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleMoveDown(index)}
                          disabled={index === protocol.length - 1}
                          className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                          title={t('move_down')}
                        >
                          <ArrowDownIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => onEditTest(test)}
                          className="p-1 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
                          title={t('edit')}
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => onRemoveTest(test.id)}
                          className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                          title={t('remove')}
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {test.config && (
                      <button
                        onClick={() => toggleTestExpansion(test.id)}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 mt-2"
                      >
                        {isExpanded ? (
                          <ChevronUpIcon className="w-3 h-3" />
                        ) : (
                          <ChevronDownIcon className="w-3 h-3" />
                        )}
                        {isExpanded ? t('hide_details') : t('show_details')}
                      </button>
                    )}

                    {isExpanded && test.config && (
                      <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1">
                        {Object.entries(test.config).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-gray-600">
                              {key}:
                            </span>
                            <span className="text-gray-900 font-medium">
                              {Array.isArray(value) ? value.join(', ') : String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="p-3 border-t border-gray-200 bg-white space-y-2">
        <button
          onClick={onAISuggest}
          disabled={isAIAnalyzing || protocol.length === 0}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-purple-50 text-purple-700 hover:bg-purple-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm"
        >
          <SparklesIcon className="w-4 h-4" />
          {isAIAnalyzing ? t('ai_analyzing') : t('ai_suggest_tests')}
        </button>

        <button
          onClick={() => onExecuteProtocol(protocol)}
          disabled={isExecuting || protocol.length === 0}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          <PlayIcon className="w-5 h-5" />
          {isExecuting ? t('executing') : t('execute_protocol')}
        </button>
      </div>
    </div>
  );
};

export default ProtocolBuilder;
