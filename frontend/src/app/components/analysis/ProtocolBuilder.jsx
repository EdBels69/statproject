import React, { useState } from 'react';
import {
  DocumentTextIcon,
  SparklesIcon,
  PlayIcon,
  TrashIcon,
  PencilIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowUturnLeftIcon,
  ArrowUturnRightIcon,
  ChevronUpIcon,
  ChevronDownIcon
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
  onSaveProtocol,
  onOpenProtocols,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
  isExecuting = false,
  isAIAnalyzing = false
}) => {
  const { t } = useTranslation();
  const [expandedTests, setExpandedTests] = useState({});
  const [leavingTestIds, setLeavingTestIds] = useState(() => ({}));

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

  const handleRemoveWithAnimation = (testId) => {
    setLeavingTestIds((prev) => ({ ...prev, [testId]: true }));
    window.setTimeout(() => {
      onRemoveTest(testId);
      setLeavingTestIds((prev) => {
        const next = { ...prev };
        delete next[testId];
        return next;
      });
    }, 160);
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
    if ((test.method === 'linear_regression' || test.method === 'logistic_regression') && test.config) {
      const outcome = test.config.outcome || test.config.target;
      const predictors = Array.isArray(test.config.predictors) ? test.config.predictors : [];
      const covariates = Array.isArray(test.config.covariates) ? test.config.covariates : [];
      const rhs = [...predictors, ...covariates].filter(Boolean).join(' + ');
      if (outcome && rhs) return `${outcome} ~ ${rhs}`;
      return '';
    }
    if (test.config?.outcome && test.config?.group) {
      return `${test.config.outcome} ~ ${test.config.group}`;
    }
    if (test.config?.target && test.config?.group) {
      return `${test.config.target} ~ ${test.config.group}`;
    }
    return '';
  };

  return (
    <div className="h-full flex flex-col bg-[color:var(--bg-secondary)]">
      <div className="p-4 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold text-[color:var(--text-primary)] flex items-center gap-2">
            <DocumentTextIcon className="w-5 h-5 text-[color:var(--accent)]" />
            {t('protocol_builder')}
          </h2>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onUndo}
              disabled={!canUndo || isExecuting}
              className="p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
              title="Отменить (Ctrl+Z)"
              aria-label="Отменить"
              aria-keyshortcuts="Control+Z Meta+Z"
            >
              <ArrowUturnLeftIcon className="w-5 h-5" />
            </button>
            <button
              type="button"
              onClick={onRedo}
              disabled={!canRedo || isExecuting}
              className="p-2 rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
              title="Повторить (Ctrl+Shift+Z)"
              aria-label="Повторить"
              aria-keyshortcuts="Control+Shift+Z Meta+Shift+Z"
            >
              <ArrowUturnRightIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
        
        {datasetName && (
          <div className="mt-2 p-2 bg-[color:var(--bg-secondary)] rounded-[2px]">
            <div className="text-xs text-[color:var(--accent)] font-medium">
              Dataset:
            </div>
            <div className="text-sm text-[color:var(--text-primary)] truncate">
              {datasetName}
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-3">
        {protocol.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[color:var(--text-muted)]">
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
              const isLeaving = Boolean(leavingTestIds?.[test.id]);

              return (
                <div
                  key={test.id}
                  className={`bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden transition-all duration-200 ease-out animate-slideUp ${isLeaving ? 'opacity-0 translate-x-2 scale-[0.99] pointer-events-none' : 'opacity-100 translate-x-0 scale-100'}`}
                >
                  <div className="p-3">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-[color:var(--text-muted)]">
                            {index + 1}.
                          </span>
                          <div className="font-medium text-[color:var(--text-primary)] text-sm">
                            {displayName}
                          </div>
                        </div>
                        
                        {description && (
                          <div className="text-xs text-[color:var(--text-muted)] mt-1 ml-6">
                            {description}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleMoveUp(index)}
                          disabled={index === 0}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98]"
                          title={t('move_up')}
                          aria-label={t('move_up')}
                        >
                          <ArrowUpIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleMoveDown(index)}
                          disabled={index === protocol.length - 1}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98]"
                          title={t('move_down')}
                          aria-label={t('move_down')}
                        >
                          <ArrowDownIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => onEditTest(test)}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] active:scale-[0.98]"
                          title={t('edit')}
                          aria-label={t('edit')}
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleRemoveWithAnimation(test.id)}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--error)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] active:scale-[0.98]"
                          title={t('remove')}
                          aria-label={t('remove')}
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {test.config && (
                      <button
                        onClick={() => toggleTestExpansion(test.id)}
                        className="flex items-center gap-1 text-xs text-[color:var(--accent)] hover:opacity-80 mt-2"
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
                      <div className="mt-2 p-2 bg-[color:var(--bg-secondary)] rounded-[2px] text-xs space-y-1">
                        {Object.entries(test.config).map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-[color:var(--text-muted)]">
                              {key}:
                            </span>
                            <span className="text-[color:var(--text-primary)] font-medium">
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

      <div className="p-3 border-t border-[color:var(--border-color)] bg-[color:var(--white)] space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={onSaveProtocol}
            disabled={isExecuting || protocol.length === 0}
            className="w-full px-3 py-2 rounded-[2px] text-sm font-semibold bg-[color:var(--accent)] text-[color:var(--white)] hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]"
            title="Сохранить протокол (Ctrl+S)"
            aria-keyshortcuts="Control+S Meta+S"
          >
            Сохранить протокол
          </button>
          <button
            type="button"
            onClick={onOpenProtocols}
            disabled={isExecuting}
            className="w-full px-3 py-2 rounded-[2px] text-sm font-semibold bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]"
            title="Открыть библиотеку протоколов (Ctrl+O)"
            aria-keyshortcuts="Control+O Meta+O"
          >
            Мои протоколы
          </button>
        </div>

        <button
          onClick={onAISuggest}
          disabled={isAIAnalyzing || protocol.length === 0}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] text-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm active:scale-[0.98]"
        >
          <SparklesIcon className="w-4 h-4" />
          {isAIAnalyzing ? t('ai_analyzing') : t('ai_suggest_tests')}
        </button>

        <button
          onClick={() => onExecuteProtocol(protocol)}
          disabled={isExecuting || protocol.length === 0}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-[color:var(--accent)] text-[color:var(--white)] hover:opacity-90 rounded-[2px] transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium active:scale-[0.98]"
          title="Выполнить протокол (Ctrl+Enter)"
          aria-keyshortcuts="Control+Enter Meta+Enter"
        >
          <PlayIcon className="w-5 h-5" />
          {isExecuting ? t('executing') : t('execute_protocol')}
        </button>
      </div>
    </div>
  );
};

export default ProtocolBuilder;
