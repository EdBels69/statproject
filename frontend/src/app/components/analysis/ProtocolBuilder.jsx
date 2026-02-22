import React, { useState } from 'react';
import {
  DocumentTextIcon,
  SparklesIcon,
  PlayIcon,
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
  onToggleTest,
  onEditTest,
  onMoveTest,
  onExecuteProtocol,
  onAISuggest,
  onVibeDesign,
  onSaveProtocol,
  onOpenProtocols,
  onUndo,
  onRedo,
  selectedStepId,
  onSelectStep,
  canUndo = false,
  canRedo = false,
  isExecuting = false,
  isAIAnalyzing = false
}) => {
  const { t } = useTranslation();
  const [expandedTests, setExpandedTests] = useState({});
  const enabledProtocol = (Array.isArray(protocol) ? protocol : []).filter((s) => s?.enabled !== false);

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
    const translated = t(test.method);
    if (translated && translated !== test.method) return translated;
    if (test.method === 'mixed_effects') return 'Смешанные эффекты (LMM)';
    if (test.method === 'clustered_correlation') return 'Кластерная корреляция';
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
      <div className="h-12 px-4 border-b border-[color:var(--border-color)] bg-[color:var(--white)] flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <DocumentTextIcon className="w-5 h-5 text-[color:var(--accent)]" />
          <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase truncate">{t('protocol_builder')}</div>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onUndo}
            disabled={!canUndo || isExecuting}
            className="h-8 w-8 inline-flex items-center justify-center rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
            title="Отменить (Ctrl+Z)"
            aria-label="Отменить"
            aria-keyshortcuts="Control+Z Meta+Z"
          >
            <ArrowUturnLeftIcon className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={onRedo}
            disabled={!canRedo || isExecuting}
            className="h-8 w-8 inline-flex items-center justify-center rounded-[2px] text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98]"
            title="Повторить (Ctrl+Shift+Z)"
            aria-label="Повторить"
            aria-keyshortcuts="Control+Shift+Z Meta+Shift+Z"
          >
            <ArrowUturnRightIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {protocol.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="max-w-sm text-center">
              <div className="text-xs font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">{t('protocol_empty')}</div>
              <div className="mt-2 text-sm text-[color:var(--text-secondary)]">{t('protocol_empty_hint')}</div>
              <div className="mt-4 text-xs text-[color:var(--text-muted)]">Добавь тест слева — он появится здесь как шаг.</div>
            </div>
          </div>
        ) : (
          <div className="relative pl-6 space-y-3">
            <div className="absolute left-2 top-1 bottom-1 w-px bg-[color:var(--border-color)]" />
            {protocol.map((test, index) => {
              const isExpanded = expandedTests[test.id];
              const displayName = getTestDisplayName(test);
              const description = getTestDescription(test);
              const isSelected = selectedStepId === test.id;
              const isEnabled = test?.enabled !== false;

              return (
                <div
                  key={test.id}
                  className={`relative bg-[color:var(--white)] border rounded-[2px] overflow-hidden transition-all duration-200 ease-out ${isSelected ? 'border-black' : 'border-[color:var(--border-color)]'} ${isEnabled ? '' : 'opacity-55'}`}
                >
                  <button
                    type="button"
                    onClick={() => onSelectStep?.(test.id)}
                    className="absolute inset-0 z-10 cursor-pointer"
                    aria-label={displayName}
                  />
                  <div className="absolute -left-[22px] top-4 h-3 w-3 rounded-full border border-[color:var(--border-color)] bg-[color:var(--white)]" />

                  <div className="relative z-20 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2 min-w-0">
                          <span className="text-[10px] font-semibold tracking-[0.2em] text-[color:var(--text-muted)] uppercase tabular-nums">{index + 1}</span>
                          <div className="font-semibold text-[color:var(--text-primary)] text-sm truncate">{displayName}</div>
                        </div>
                        
                        {description && (
                          <div className="text-xs text-[color:var(--text-secondary)] mt-1 font-mono truncate">
                            {description}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-1 flex-shrink-0 relative">
                        <label className="flex items-center gap-2 p-1 rounded-[2px] hover:bg-[color:var(--bg-secondary)]">
                          <input
                            type="checkbox"
                            checked={isEnabled}
                            onChange={(e) => onToggleTest?.(test.id, e.target.checked)}
                            className="h-4 w-4 accent-black"
                            aria-label="Включить в анализ"
                          />
                        </label>
                        <button
                          type="button"
                          onClick={() => handleMoveUp(index)}
                          disabled={index === 0}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98]"
                          title={t('move_up')}
                          aria-label={t('move_up')}
                        >
                          <ArrowUpIcon className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleMoveDown(index)}
                          disabled={index === protocol.length - 1}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.98]"
                          title={t('move_down')}
                          aria-label={t('move_down')}
                        >
                          <ArrowDownIcon className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => onEditTest(test)}
                          className="p-1 text-[color:var(--text-muted)] hover:text-[color:var(--accent)] hover:bg-[color:var(--bg-secondary)] rounded-[2px] active:scale-[0.98]"
                          title={t('edit')}
                          aria-label={t('edit')}
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {test.config ? (
                      <button
                        type="button"
                        onClick={() => toggleTestExpansion(test.id)}
                        className="relative mt-2 flex items-center gap-1 text-[10px] font-semibold tracking-[0.2em] uppercase text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                      >
                        {isExpanded ? (
                          <ChevronUpIcon className="w-3 h-3" />
                        ) : (
                          <ChevronDownIcon className="w-3 h-3" />
                        )}
                        {isExpanded ? t('hide_details') : t('show_details')}
                      </button>
                    ) : null}

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

      <div className="p-3 border-t border-[color:var(--border-color)] bg-[color:var(--white)]">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onExecuteProtocol(enabledProtocol)}
            disabled={isExecuting || enabledProtocol.length === 0}
            className="flex-1 h-10 inline-flex items-center justify-center gap-2 px-4 rounded-[2px] bg-[color:var(--accent)] text-[color:var(--white)] hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
            title="Выполнить протокол (Ctrl+Enter)"
            aria-keyshortcuts="Control+Enter Meta+Enter"
          >
            <PlayIcon className="w-5 h-5" />
            {isExecuting ? t('executing') : t('execute_protocol')}
          </button>

          <button
            type="button"
            onClick={onAISuggest}
            disabled={isAIAnalyzing || enabledProtocol.length === 0}
            className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--accent)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
            title={t('ai_suggest_tests')}
          >
            <SparklesIcon className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={() => onVibeDesign?.()}
            disabled={isExecuting}
            className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
            title="Собрать протокол из текста"
          >
            <span className="text-[10px] font-black tracking-[0.24em]">TXT</span>
          </button>

          <button
            type="button"
            onClick={onSaveProtocol}
            disabled={isExecuting || protocol.length === 0}
            className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
            title="Сохранить протокол (Ctrl+S)"
            aria-keyshortcuts="Control+S Meta+S"
          >
            <DocumentTextIcon className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={onOpenProtocols}
            disabled={isExecuting}
            className="h-10 px-3 rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-primary)] bg-[color:var(--white)] hover:bg-[color:var(--bg-secondary)] disabled:opacity-50 disabled:cursor-not-allowed"
            title="Мои протоколы (Ctrl+O)"
            aria-keyshortcuts="Control+O Meta+O"
          >
            <DocumentTextIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProtocolBuilder;
