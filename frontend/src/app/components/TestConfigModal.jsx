import React, { useEffect, useMemo, useRef, useState } from 'react';
import { XMarkIcon, CogIcon, InformationCircleIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import WhyThisTest from './education/WhyThisTest';
import { useLanguage } from '../../contexts/LanguageContext';
import { checkAssumptions, getAlphaSetting } from '../../lib/api';

const TestConfigModal = ({
  isOpen,
  onClose,
  method,
  initialConfig = {},
  onConfigSave,
  columns = [],
  suggestedConfig,
  datasetId
}) => {
  return (
    <TestConfigModalContent
      key={`${method}-${isOpen ? 'open' : 'closed'}`}
      method={method}
      initialConfig={initialConfig}
      onClose={onClose}
      onConfigSave={onConfigSave}
      columns={columns}
      suggestedConfig={suggestedConfig}
      datasetId={datasetId}
      isOpen={isOpen}
    />
  );
};

const SearchableSelect = ({ field, value, onChange, options, multiple = false }) => {
  const [search, setSearch] = useState('');

  const filteredOptions = useMemo(() => {
    if (!search) return options;
    return options.filter(opt =>
      opt.label.toLowerCase().includes(search.toLowerCase())
    );
  }, [options, search]);

  const toggleOption = (optionValue) => {
    if (multiple) {
      const currentValues = Array.isArray(value) ? value : [];
      const newValue = currentValues.includes(optionValue)
        ? currentValues.filter(v => v !== optionValue)
        : [...currentValues, optionValue];
      onChange(newValue);
    } else {
      onChange(optionValue);
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium text-[color:var(--text-primary)] mb-1">
        {field.label}
      </label>
      <div className="border border-[color:var(--border-color)] rounded-[2px] overflow-hidden bg-[color:var(--white)]">
        <div className="p-2 border-b border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center gap-2">
          <MagnifyingGlassIcon className="w-4 h-4 text-[color:var(--text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={`Поиск: ${field.label.toLowerCase()}...`}
            className="bg-transparent border-none text-sm w-full p-0 outline-none"
          />
        </div>
        <div className="max-h-48 overflow-y-auto p-1">
          {filteredOptions.length > 0 ? (
            filteredOptions.map(option => {
              const isSelected = multiple
                ? Array.isArray(value) && value.includes(option.value)
                : value === option.value;

              return (
                <label
                  key={option.value}
                  className={`flex items-center p-2 cursor-pointer rounded-[2px] transition-colors ${isSelected ? 'bg-[color:var(--bg-secondary)]' : 'hover:bg-[color:var(--bg-secondary)]'
                    }`}
                >
                  <input
                    type={multiple ? "checkbox" : "radio"}
                    name={field.id}
                    checked={isSelected}
                    onChange={() => toggleOption(option.value)}
                    className="text-[color:var(--accent)] rounded-[2px]"
                  />
                  <div className="ml-2 flex-1 min-w-0">
                    <div className={`text-sm ${isSelected ? 'font-semibold text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}`}>
                      {option.label}
                    </div>
                    {option.type && (
                      <div className="text-xs text-[color:var(--text-muted)] mt-0.5 uppercase tracking-wider">
                        {option.type}
                      </div>
                    )}
                  </div>
                </label>
              );
            })
          ) : (
            <div className="p-4 text-sm text-[color:var(--text-muted)] text-center italic">
              Ничего не найдено
            </div>
          )}
        </div>
        {multiple && (
          <div className="p-2 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] text-xs text-[color:var(--text-secondary)] text-right">
            Выбрано: {Array.isArray(value) ? value.length : 0}
          </div>
        )}
      </div>
    </div>
  );
};


const TestConfigModalContent = ({ method, initialConfig, onClose, onConfigSave, columns, suggestedConfig, datasetId, isOpen }) => {
  const { educationLevel } = useLanguage();
  const [config, setConfig] = useState(() => initialConfig || {});
  const [activeTab, setActiveTab] = useState('basics');
  const [touchedFields, setTouchedFields] = useState(() => ({}));
  const dialogRef = useRef(null);
  const [assumptionProfile, setAssumptionProfile] = useState(null);

  const shouldFetchAssumptions = Boolean(isOpen && method && datasetId);
  const assumptionProfileForUI = shouldFetchAssumptions ? (assumptionProfile || {}) : {};

  useEffect(() => {
    if (!isOpen) return;
    const root = dialogRef.current;
    if (!root) return;
    const focusable = root.querySelectorAll(
      'button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])'
    );
    const first = focusable?.[0];
    if (first && typeof first.focus === 'function') first.focus();
  }, [isOpen]);

  // Common variable fields
  const targetField = {
    id: 'target',
    type: 'variable_single',
    label: 'Целевая переменная (Outcome)',
    description: 'Зависимая переменная для анализа',
    default: ''
  };

  const outcomeField = {
    id: 'outcome',
    type: 'variable_single',
    label: 'Исход (Outcome)',
    description: 'Зависимая переменная для анализа',
    default: ''
  };

  const groupField = {
    id: 'group',
    type: 'variable_single',
    label: 'Группировка (Group)',
    description: 'Независимая переменная (фактор)',
    default: ''
  };

  const targetsField = {
    id: 'targets',
    type: 'variable_multi',
    label: 'Переменные для анализа',
    description: 'Выберите две или более переменных',
    minItems: 2,
    default: []
  };

  const predictorsField = {
    id: 'predictors',
    type: 'variable_multi',
    label: 'Предикторы',
    description: 'Одна или несколько переменных-предикторов',
    minItems: 1,
    default: []
  };

  // Method-specific configuration templates
  const methodTemplates = {
    // Mixed Effects Models & Related
    mixed_model: {
      variables: [
        targetField,
        groupField,
        {
          id: 'time',
          type: 'variable_single',
          label: 'Время/Условие (Time)',
          description: 'Переменная повторных измерений',
          default: ''
        },
        {
          id: 'covariates',
          type: 'variable_multi',
          label: 'Ковариаты',
          description: 'Дополнительные переменные для коррекции',
          default: []
        }
      ],
      advanced: [
        {
          id: 'random_slope',
          type: 'boolean',
          label: 'Случайные наклоны',
          description: 'Включить случайные наклоны в модель',
          default: false
        },
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          description: 'Уровень альфа для статистической значимости',
          default: 0.05,
          min: 0.01,
          max: 0.10,
          step: 0.01
        }
      ]
    },

    // Group Comparison (t-test, etc.)
    t_test_ind: {
      variables: [targetField, groupField],
      advanced: [{
        id: 'alpha',
        type: 'number',
        label: 'Уровень значимости',
        default: 0.05
      }]
    },
    mann_whitney: {
      variables: [targetField, groupField],
      advanced: [{
        id: 'alpha',
        type: 'number',
        label: 'Уровень значимости',
        default: 0.05
      }]
    },
    anova: {
      variables: [targetField, groupField],
      advanced: [{
        id: 'alpha',
        type: 'number',
        label: 'Уровень значимости',
        default: 0.05,
        min: 0.01,
        max: 0.10,
        step: 0.01
      }],
      postHoc: [{
        id: 'post_hoc',
        type: 'select',
        label: 'Post-hoc тест',
        options: [{ value: 'tukey', label: 'Tukey HSD' }, { value: 'bonferroni', label: 'Bonferroni' }],
        default: 'tukey'
      }]
    },
    kruskal: {
      variables: [targetField, groupField],
      advanced: [{
        id: 'alpha',
        type: 'number',
        label: 'Уровень значимости',
        default: 0.05
      }]
    },

    // Paired
    t_test_rel: {
      variables: [targetField, groupField], // Assuming long format or change to paired inputs? keeping simple used case
      advanced: []
    },
    wilcoxon: {
      variables: [targetField, groupField],
      advanced: []
    },
    rm_anova: {
      variables: [targetField,
        {
          id: 'subject',
          type: 'variable_single',
          label: 'Субъект (ID)',
          description: 'Идентификатор пациента/образца',
          default: ''
        },
        {
          id: 'time',
          type: 'variable_single',
          label: 'Время (Time)',
          description: 'Точка времени измерения',
          default: ''
        }
      ],
      advanced: [
        {
          id: 'sphericity_correction',
          type: 'select',
          label: 'Коррекция сферичности',
          default: 'greenhouse-geisser',
          options: [
            { value: 'none', label: 'Нет' },
            { value: 'greenhouse-geisser', label: 'Гринхаус-Гейссер' },
            { value: 'huynh-feldt', label: 'Хюин-Фельдт' }
          ]
        }
      ]
    },

    // Correlation
    clustered_correlation: {
      variables: [targetsField],
      advanced: [
        {
          id: 'method',
          type: 'select',
          label: 'Метод корреляции',
          default: 'pearson',
          options: [
            { value: 'pearson', label: 'Пирсон' },
            { value: 'spearman', label: 'Спирмен' }
          ]
        },
        {
          id: 'n_clusters',
          type: 'number',
          label: 'Количество кластеров',
          default: 0,
          min: 0, max: 20
        }
      ]
    },
    pearson: {
      variables: [targetsField],
      advanced: []
    },
    spearman: {
      variables: [targetsField],
      advanced: []
    },

    // Survival
    survival_km: {
      variables: [
        {
          id: 'time',
          type: 'variable_single',
          label: 'Время (Time)',
          description: 'Время до события',
          default: ''
        },
        {
          id: 'event',
          type: 'variable_single',
          label: 'Событие (Event)',
          description: 'Колонка события (0/1)',
          default: ''
        },
        groupField
      ],
      advanced: []
    },

    linear_regression: {
      variables: [outcomeField, predictorsField, {
        id: 'covariates',
        type: 'variable_multi',
        label: 'Ковариаты',
        description: 'Дополнительные переменные для коррекции',
        default: []
      }],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05,
          min: 0.01,
          max: 0.10,
          step: 0.01
        }
      ]
    },

    logistic_regression: {
      variables: [
        {
          ...outcomeField,
          label: 'Исход (бинарный)',
          description: 'Бинарная переменная исхода (0/1 или Да/Нет)'
        },
        predictorsField,
        {
          id: 'covariates',
          type: 'variable_multi',
          label: 'Ковариаты',
          description: 'Дополнительные переменные для коррекции',
          default: []
        }
      ],
      advanced: [
        { id: 'show_or', type: 'boolean', label: 'Показать OR', default: true },
        { id: 'show_roc', type: 'boolean', label: 'ROC-кривая', default: true },
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05,
          min: 0.01,
          max: 0.10,
          step: 0.01
        }
      ]
    },

    // Default template for others
    default: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05,
          min: 0.01, max: 0.10, step: 0.01
        }
      ]
    }
  };

  const effectiveConfig = useMemo(() => {
    if (!suggestedConfig || typeof suggestedConfig !== 'object') return config;

    const next = { ...config };
    if (!touchedFields.target && !next.target && suggestedConfig.target) next.target = suggestedConfig.target;
    if (!touchedFields.outcome && !next.outcome && suggestedConfig.target) next.outcome = suggestedConfig.target;
    if (!touchedFields.group && !next.group && suggestedConfig.group) next.group = suggestedConfig.group;
    if (!touchedFields.covariates && Array.isArray(suggestedConfig.covariates) && suggestedConfig.covariates.length > 0) {
      const current = Array.isArray(next.covariates) ? next.covariates : [];
      if (current.length === 0) next.covariates = suggestedConfig.covariates;
    }

    return next;
  }, [config, suggestedConfig, touchedFields]);

  useEffect(() => {
    if (!shouldFetchAssumptions) return;

    const controller = new AbortController();
    const timeout = setTimeout(() => {
      (async () => {
        try {
          setAssumptionProfile(null);
          const payload = await checkAssumptions({
            datasetId,
            methodId: method,
            config: effectiveConfig,
            alpha: getAlphaSetting(),
            signal: controller.signal,
          });
          if (controller.signal.aborted) return;
          setAssumptionProfile(payload || null);
        } catch {
          if (controller.signal.aborted) return;
          setAssumptionProfile(null);
        }
      })();
    }, 120);

    return () => {
      controller.abort();
      clearTimeout(timeout);
    };
  }, [datasetId, effectiveConfig, method, shouldFetchAssumptions]);

  const methodTemplate = methodTemplates[method] || methodTemplates.default;

  const handleConfigChange = (fieldId, value) => {
    setTouchedFields((prev) => ({ ...prev, [fieldId]: true }));
    setConfig(prev => ({
      ...prev,
      [fieldId]: value
    }));
  };

  const handleSave = () => {
    onConfigSave(effectiveConfig);
    onClose();
  };

  const requiredFields = (() => {
    const fields = [];
    const vars = Array.isArray(methodTemplate?.variables) ? methodTemplate.variables : [];
    for (const f of vars) {
      if (f?.type === 'variable_single') fields.push({ ...f, required: true });
      if (f?.type === 'variable_multi') fields.push({ ...f, required: true });
    }
    return fields;
  })();

  const missingRequired = (() => {
    const missing = [];
    for (const f of requiredFields) {
      const v = effectiveConfig?.[f.id];
      if (f.type === 'variable_single') {
        if (!String(v || '').trim()) missing.push(f);
        continue;
      }
      if (f.type === 'variable_multi') {
        const arr = Array.isArray(v) ? v : [];
        const min = typeof f.minItems === 'number' ? f.minItems : 1;
        if (arr.length < min) missing.push(f);
      }
    }
    return missing;
  })();

  const canSave = missingRequired.length === 0;

  const previewBlocks = (() => {
    const vars = Array.isArray(methodTemplate?.variables) ? methodTemplate.variables : [];
    const adv = Array.isArray(methodTemplate?.advanced) ? methodTemplate.advanced : [];
    const postHoc = Array.isArray(methodTemplate?.postHoc) ? methodTemplate.postHoc : [];

    const fmtValue = (field) => {
      const v = effectiveConfig?.[field.id] ?? field.default;
      if (field.type === 'variable_single') return String(v || '').trim() || '—';
      if (field.type === 'variable_multi') {
        const arr = Array.isArray(v) ? v : [];
        return arr.length > 0 ? arr.join(', ') : '—';
      }
      if (field.type === 'boolean') return v ? 'ON' : 'OFF';
      if (field.type === 'select') {
        const hit = Array.isArray(field.options) ? field.options.find(o => o.value === v) : null;
        return hit?.label || String(v || '—');
      }
      if (field.type === 'number') return typeof v === 'number' && Number.isFinite(v) ? String(v) : '—';
      return String(v ?? '—');
    };

    const varsOut = vars
      .map((f) => ({
        id: f.id,
        label: f.label,
        value: fmtValue(f)
      }))
      .filter((x) => x.label);

    const advOut = adv
      .map((f) => ({
        id: f.id,
        label: f.label,
        value: fmtValue(f)
      }))
      .filter((x) => x.label);

    const postHocOut = postHoc
      .map((f) => ({
        id: f.id,
        label: f.label,
        value: fmtValue(f)
      }))
      .filter((x) => x.label);

    const outcome = String(effectiveConfig?.outcome || effectiveConfig?.target || '').trim();
    const group = String(effectiveConfig?.group || '').trim();
    const predictors = Array.isArray(effectiveConfig?.predictors) ? effectiveConfig.predictors : [];
    const covariates = Array.isArray(effectiveConfig?.covariates) ? effectiveConfig.covariates : [];

    const formula = outcome
      ? `${outcome} ~ ${[group, ...predictors, ...covariates].filter(Boolean).join(' + ') || '1'}`
      : null;

    return {
      varsOut,
      advOut,
      postHocOut,
      formula
    };
  })();

  const renderField = (field) => {
    const value = effectiveConfig[field.id] ?? field.default;

    switch (field.type) {
      case 'boolean':
        return (
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={value}
              onChange={(e) => handleConfigChange(field.id, e.target.checked)}
              className="rounded-[2px] border-[color:var(--border-color)] text-[color:var(--accent)]"
            />
            <span className="ml-2 text-sm text-[color:var(--text-primary)]">{field.label}</span>
          </label>
        );

      case 'number':
        return (
          <div>
            <label className="block text-sm font-medium text-[color:var(--text-primary)] mb-1">
              {field.label}
            </label>
            <input
              type="number"
              value={value}
              onChange={(e) => handleConfigChange(field.id, parseFloat(e.target.value))}
              min={field.min}
              max={field.max}
              step={field.step}
              className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] focus:outline-none focus:border-[color:var(--accent)]"
            />
          </div>
        );

      case 'select':
        return (
          <div>
            <label className="block text-sm font-medium text-[color:var(--text-primary)] mb-1">
              {field.label}
            </label>
            <select
              value={value}
              onChange={(e) => handleConfigChange(field.id, e.target.value)}
              className="w-full px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] focus:outline-none focus:border-[color:var(--accent)]"
            >
              {field.options.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        );

      case 'variable_multi':
      case 'variable_single': {
        const options = columns.map(c => ({
          value: typeof c === 'string' ? c : c.name,
          label: typeof c === 'string' ? c : c.name,
          type: typeof c === 'string' ? 'unknown' : c.type
        }));

        return (
          <SearchableSelect
            field={field}
            value={value}
            onChange={(newValue) => handleConfigChange(field.id, newValue)}
            options={options}
            multiple={field.type === 'variable_multi'}
          />
        );
      }

      default:
        return null;
    }
  };

  const variableFields = methodTemplate.variables || [];
  const advancedFields = methodTemplate.advanced || [];
  const postHocFields = methodTemplate.postHoc || [];

  const resolvedTab = (() => {
    if (activeTab === 'advanced' && advancedFields.length === 0) return 'basics';
    if (activeTab === 'posthoc' && postHocFields.length === 0) return 'basics';
    return activeTab;
  })();

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 transition-opacity duration-150 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
      role="dialog"
      aria-modal="true"
      aria-label="Настройки анализа"
      aria-hidden={!isOpen}
      onMouseDown={(e) => {
        if (!isOpen) return;
        if (e.target === e.currentTarget) onClose?.();
      }}
      onKeyDown={(e) => {
        if (!isOpen) return;
        if (e.key === 'Escape') {
          e.stopPropagation();
          onClose?.();
          return;
        }

        if (e.key !== 'Tab') return;

        const root = dialogRef.current;
        if (!root) return;
        const focusable = Array.from(
          root.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')
        ).filter((el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true');
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const active = document.activeElement;

        if (e.shiftKey) {
          if (active === first || !root.contains(active)) {
            e.preventDefault();
            last.focus();
          }
          return;
        }

        if (active === last) {
          e.preventDefault();
          first.focus();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={`bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] max-w-5xl w-full max-h-[82vh] overflow-hidden flex flex-col transition-all duration-150 ${isOpen ? 'opacity-100 translate-y-0 scale-100' : 'opacity-0 translate-y-2 scale-[0.98]'}`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-[color:var(--border-color)] flex-shrink-0">
          <div className="flex items-center">
            <CogIcon className="w-6 h-6 text-[color:var(--accent)] mr-2" />
            <div className="min-w-0">
              <h2 className="text-xl font-black text-black truncate">
                Настройки {getMethodName(method)}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] active:scale-[0.98]"
            aria-label="Закрыть"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-[minmax(320px,1fr)_minmax(280px,420px)]">
          <div className="overflow-hidden flex flex-col">
            <div className="flex-shrink-0 px-5 pt-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Настройка</div>
                <div className="flex items-center gap-2">
                  {[
                    { id: 'basics', label: 'Основные', visible: true },
                    { id: 'advanced', label: 'Дополнительно', visible: advancedFields.length > 0 },
                    { id: 'posthoc', label: 'Post-hoc', visible: postHocFields.length > 0 }
                  ].filter((t) => t.visible).map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setActiveTab(tab.id)}
                      className={`px-3 py-1 rounded-[2px] border text-xs font-semibold tracking-[0.12em] ${resolvedTab === tab.id
                        ? 'border-[color:var(--text-primary)] text-[color:var(--text-primary)]'
                        : 'border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)]'
                        }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {missingRequired.length > 0 && (
                <div className="mt-3 border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-2 rounded-[2px]">
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Нужно заполнить</div>
                  <div className="mt-1 text-sm text-[color:var(--text-primary)]">
                    {missingRequired.map((f) => f.label).join(' · ')}
                  </div>
                </div>
              )}
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-5 pt-4">
              {resolvedTab === 'basics' && (
                <div className="space-y-6">
                  {variableFields.length > 0 ? variableFields.map(field => (
                    <div key={field.id}>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-xs text-[color:var(--text-muted)] mt-2 flex items-center">
                          <InformationCircleIcon className="w-4 h-4 mr-1" />
                          {field.description}
                        </p>
                      )}
                    </div>
                  )) : (
                    <div className="text-center text-[color:var(--text-secondary)] py-4">
                      Переменные не требуются
                    </div>
                  )}
                </div>
              )}

              {resolvedTab === 'advanced' && (
                <div className="space-y-6">
                  {advancedFields.map(field => (
                    <div key={field.id}>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-xs text-[color:var(--text-muted)] mt-2 flex items-center">
                          <InformationCircleIcon className="w-4 h-4 mr-1" />
                          {field.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {resolvedTab === 'posthoc' && (
                <div className="space-y-6">
                  {postHocFields.map(field => (
                    <div key={field.id}>
                      {renderField(field)}
                      {field.description && (
                        <p className="text-xs text-[color:var(--text-muted)] mt-2 flex items-center">
                          <InformationCircleIcon className="w-4 h-4 mr-1" />
                          {field.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <aside className="border-t md:border-t-0 md:border-l border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
            <div className="flex-shrink-0 px-5 pt-4">
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Предпросмотр</div>
              <div className="mt-2">
                <div className="text-sm font-black text-[color:var(--text-primary)]">
                  {getMethodName(method)}
                </div>
                {previewBlocks.formula && (
                  <div className="mt-2 px-3 py-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)]">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Формула</div>
                    <div className="mt-1 text-xs font-mono text-[color:var(--text-primary)] break-words">{previewBlocks.formula}</div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-5 pt-4 space-y-4">
              {method && (
                <WhyThisTest
                  testId={method}
                  dataProfile={assumptionProfileForUI}
                  level={educationLevel}
                  defaultExpanded={true}
                />
              )}
              <div>
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Поля</div>
                <div className="mt-2 space-y-2">
                  {previewBlocks.varsOut.map((x) => (
                    <div key={x.id} className="flex items-baseline justify-between gap-3 border-b border-[color:var(--border-color)] py-2">
                      <div className="text-xs text-[color:var(--text-secondary)]">{x.label}</div>
                      <div className="text-xs font-semibold text-[color:var(--text-primary)] text-right">{x.value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {previewBlocks.advOut.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Опции</div>
                  <div className="mt-2 space-y-2">
                    {previewBlocks.advOut.map((x) => (
                      <div key={x.id} className="flex items-baseline justify-between gap-3 border-b border-[color:var(--border-color)] py-2">
                        <div className="text-xs text-[color:var(--text-secondary)]">{x.label}</div>
                        <div className="text-xs font-semibold text-[color:var(--text-primary)] text-right">{x.value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {previewBlocks.postHocOut.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Post-hoc</div>
                  <div className="mt-2 space-y-2">
                    {previewBlocks.postHocOut.map((x) => (
                      <div key={x.id} className="flex items-baseline justify-between gap-3 border-b border-[color:var(--border-color)] py-2">
                        <div className="text-xs text-[color:var(--text-secondary)]">{x.label}</div>
                        <div className="text-xs font-semibold text-[color:var(--text-primary)] text-right">{x.value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </aside>
        </div>

        {/* Footer */}
        <div className="bg-[color:var(--bg-secondary)] px-5 py-4 flex justify-end gap-3 flex-shrink-0 border-t border-[color:var(--border-color)]">
          <button
            onClick={onClose}
            className="btn-secondary px-3.5 py-2 text-xs"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            className="btn-primary px-3.5 py-2 text-xs"
            disabled={!canSave}
          >
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
};

// Helper function to get method display name
const getMethodName = (methodId) => {
  const methodNames = {
    // Basic
    t_test_ind: 't-критерия Стьюдента (независимые)',
    t_test_welch: 'Welch t-test',
    t_test_rel: 'Парного t-критерия',
    mann_whitney: 'Mann-Whitney U',
    wilcoxon: 'Wilcoxon Signed-Rank',

    // ANOVA family
    anova: 'ANOVA',
    kruskal: 'Kruskal-Wallis',
    rm_anova: 'RM-ANOVA (повторные измерения)',
    friedman: 'Теста Фридмана',

    // Correlation
    pearson: 'Корреляции Пирсона',
    spearman: 'Корреляции Спирмена',
    clustered_correlation: 'Кластерной корреляции',

    // Categorical
    chi_square: 'Хи-квадрат',
    fisher: 'Точного теста Фишера',

    // Advanced
    mixed_model: 'Смешанной модели (LMM)',
    survival_km: 'Анализа выживаемости (Kaplan-Meier)',
    linear_regression: 'Линейной регрессии',
    logistic_regression: 'Логистической регрессии'
  };

  return methodNames[methodId] || methodId;
};

export default TestConfigModal;
