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

  const [isVarPickerOpen, setIsVarPickerOpen] = useState(false);
  const [varPickerField, setVarPickerField] = useState(null);
  const [varPickerDraft, setVarPickerDraft] = useState(null);
  const [varPickerSearch, setVarPickerSearch] = useState('');
  const [varPickerRoleFilter, setVarPickerRoleFilter] = useState('all');
  const [rmPointCap, setRmPointCap] = useState(null);
  const [rmPointMode, setRmPointMode] = useState('cap');
  const [rmPointIndices, setRmPointIndices] = useState(null);
  const [rmPointSpec, setRmPointSpec] = useState('');

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
        },
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы (95%)',
          default: true
        }
      ]
    },

    // Group Comparison (t-test, etc.)
    t_test_ind: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы',
          default: true
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'cohen', label: "Cohen's d" },
            { value: 'hedges', label: "Hedges' g" },
            { value: 'glass', label: "Glass's Δ" }
          ],
          default: 'cohen'
        },
        {
          id: 'missing_values',
          type: 'select',
          label: 'Пропущенные значения',
          options: [
            { value: 'exclude_analysis', label: 'Исключить для анализа (pairwise)' },
            { value: 'exclude_listwise', label: 'Исключить целиком (listwise)' }
          ],
          default: 'exclude_analysis'
        }
      ]
    },
    mann_whitney: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы',
          default: true
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'rank_biserial', label: 'Rank-Biserial' }
          ],
          default: 'rank_biserial'
        }
      ]
    },
    anova: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05,
          min: 0.01,
          max: 0.10,
          step: 0.01
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'eta_squared', label: 'η² (Eta-squared)' },
            { value: 'partial_eta_squared', label: 'η²p (Partial Eta-squared)' },
            { value: 'omega_squared', label: 'ω² (Omega-squared)' }
          ],
          default: 'eta_squared'
        }
      ],
      postHoc: [
        {
          id: 'post_hoc',
          type: 'select',
          label: 'Post-hoc тест',
          options: [
            { value: 'tukey', label: 'Tukey' },
            { value: 'bonferroni', label: 'Bonferroni' },
            { value: 'holm', label: 'Holm' },
            { value: 'scheffe', label: 'Scheffe' },
            { value: 'none', label: 'Нет' }
          ],
          default: 'tukey'
        }
      ]
    },
    anova_twoway: {
      variables: [
        targetField,
        {
          id: 'group1',
          type: 'variable_single',
          label: 'Фактор A (Group 1)',
          description: 'Первый фактор',
          default: ''
        },
        {
          id: 'group2',
          type: 'variable_single',
          label: 'Фактор B (Group 2)',
          description: 'Второй фактор',
          default: ''
        }
      ],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05,
          min: 0.01,
          max: 0.10,
          step: 0.01
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'partial_eta_squared', label: 'η²p (Partial Eta-squared)' }
          ],
          default: 'partial_eta_squared'
        }
      ]
    },
    kruskal: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'epsilon_squared', label: 'ε² (Epsilon-squared)' },
            { value: 'eta_squared', label: 'η² (Eta-squared)' }
          ],
          default: 'epsilon_squared'
        }
      ],
      postHoc: [{
        id: 'post_hoc',
        type: 'select',
        label: 'Post-hoc тест',
        options: [{ value: 'dunn', label: 'Dunn (rank)' }, { value: 'none', label: 'Нет' }],
        default: 'dunn'
      },
      {
        id: 'post_hoc_correction',
        type: 'select',
        label: 'Поправка для post-hoc',
        options: [{ value: 'bonferroni', label: 'Bonferroni' }, { value: 'holm', label: 'Holm' }, { value: 'bh', label: 'Benjamini-Hochberg' }, { value: 'none', label: 'Нет' }],
        default: 'holm'
      }]
    },
    anova_welch: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'eta_squared', label: 'η² (Eta-squared)' },
            { value: 'omega_squared', label: 'ω² (Omega-squared)' }
          ],
          default: 'eta_squared'
        }
      ],
      postHoc: [{
        id: 'post_hoc',
        type: 'select',
        label: 'Post-hoc тест',
        options: [{ value: 'games_howell', label: 'Games-Howell' }, { value: 'none', label: 'Нет' }],
        default: 'games_howell'
      }]
    },

    // Paired
    t_test_rel: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы',
          default: true
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'cohen', label: "Cohen's d" },
            { value: 'hedges', label: "Hedges' g" }
          ],
          default: 'cohen'
        }
      ]
    },
    wilcoxon: {
      variables: [targetField, groupField],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'rank_biserial', label: 'Rank-Biserial' }
          ],
          default: 'rank_biserial'
        }
      ]
    },
    rm_anova: {
      variables: [
        {
          id: 'outcome_cols',
          type: 'variable_multi',
          label: 'Повторные измерения (Outcome columns)',
          description: 'Выберите 2+ связанных колонок (временные точки/условия)',
          minItems: 2,
          default: []
        },
        {
          id: 'subject_col',
          type: 'variable_single',
          label: 'Субъект (ID)',
          description: 'Идентификатор пациента/образца',
          default: ''
        },
        {
          id: 'group_col',
          type: 'variable_single',
          label: 'Межгрупповой фактор (опц.)',
          description: 'Дополнительная группировка (если есть)',
          default: ''
        }
      ],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'partial_eta_squared', label: 'η²p (Partial Eta-squared)' },
            { value: 'eta_squared', label: 'η² (Eta-squared)' }
          ],
          default: 'partial_eta_squared'
        },
        {
          id: 'sphericity',
          type: 'boolean',
          label: 'Test Sphericity (Mauchly)',
          default: true
        }
      ]
    },

    friedman: {
      variables: [
        {
          id: 'outcome_cols',
          type: 'variable_multi',
          label: 'Связанные измерения (Outcome columns)',
          description: 'Выберите 3+ связанных колонок (одни и те же субъекты)',
          minItems: 3,
          default: []
        }
      ],
      advanced: [
        {
          id: 'alpha',
          type: 'number',
          label: 'Уровень значимости',
          default: 0.05,
          min: 0.01,
          max: 0.10,
          step: 0.01
        },
        {
          id: 'effect_size',
          type: 'select',
          label: 'Размер эффекта',
          options: [
            { value: 'kendall_w', label: "Kendall's W" }
          ],
          default: 'kendall_w'
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
      advanced: [
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы',
          default: true
        },
        {
          id: 'descriptives',
          type: 'boolean',
          label: 'Описательные статистики',
          default: true
        }
      ]
    },
    spearman: {
      variables: [targetsField],
      advanced: [
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы (Bootstrapped)',
          default: false
        }
      ]
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
      advanced: [
        {
          id: 'confidence_type',
          type: 'select',
          label: 'Тип доверительного интервала',
          options: [
            { value: 'log', label: 'Log (Greenwood)' },
            { value: 'log-log', label: 'Log-Log' },
            { value: 'linear', label: 'Linear' }
          ],
          default: 'log'
        }
      ]
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
        },
        {
          id: 'ci',
          type: 'boolean',
          label: 'Доверительные интервалы коэффициентов',
          default: true
        },
        {
          id: 'vif',
          type: 'boolean',
          label: 'Диагностика коллинеарности (VIF)',
          default: true
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
        },
        {
          id: 'ci',
          type: 'boolean',
          label: 'CI для Odds Ratio',
          default: true
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

  const roleByName = useMemo(() => {
    const map = {};
    const t0 = String(suggestedConfig?.target || '').trim();
    const g0 = String(suggestedConfig?.group || '').trim();
    const cov = Array.isArray(suggestedConfig?.covariates) ? suggestedConfig.covariates : [];
    if (t0) map[t0] = 'target';
    if (g0) map[g0] = 'group';
    cov.filter(Boolean).forEach((n) => {
      map[String(n)] = 'covariate';
    });
    return map;
  }, [suggestedConfig]);

  const columnMetaByName = useMemo(() => {
    const map = {};
    const all = Array.isArray(columns) ? columns : [];
    for (const c of all) {
      if (!c) continue;
      if (typeof c === 'string') {
        map[c] = { name: c, type: null };
        continue;
      }
      const name = String(c?.name || '').trim();
      if (!name) continue;
      map[name] = { name, type: c?.type || null };
    }
    return map;
  }, [columns]);

  const openVarPicker = (field) => {
    const current = effectiveConfig[field.id] ?? field.default;
    setVarPickerField(field);
    setVarPickerSearch('');
    if ((method === 'friedman' || method === 'rm_anova') && field.id === 'outcome_cols') {
      setRmPointCap(null);
      setRmPointMode('cap');
      setRmPointIndices(null);
      setRmPointSpec('');
    }
    if (field.id === 'target' || field.id === 'outcome' || field.id === 'outcome_cols') setVarPickerRoleFilter('target');
    else if (field.id === 'group' || field.id === 'group1' || field.id === 'group2' || field.id === 'group_col') setVarPickerRoleFilter('group');
    else if (field.id === 'covariates') setVarPickerRoleFilter('covariate');
    else setVarPickerRoleFilter('all');

    if (field.type === 'variable_multi') {
      setVarPickerDraft(Array.isArray(current) ? current : []);
    } else {
      setVarPickerDraft(String(current || '').trim());
    }
    setIsVarPickerOpen(true);
  };

  const applyVarPicker = () => {
    if (!varPickerField) return;
    handleConfigChange(varPickerField.id, varPickerDraft);
    setIsVarPickerOpen(false);
    setVarPickerField(null);
  };

  const resetVarPickerDraft = () => {
    if (!varPickerField) return;
    const field = varPickerField;
    const current = effectiveConfig[field.id] ?? field.default;
    if (field.type === 'variable_multi') {
      setVarPickerDraft(Array.isArray(current) ? current : []);
    } else {
      setVarPickerDraft(String(current || '').trim());
    }
  };

  const handleSave = () => {
    // Ensure all fields have at least their default values
    const defaults = {};
    const allFields = [
      ...(methodTemplate.variables || []),
      ...(methodTemplate.advanced || []),
      ...(methodTemplate.postHoc || [])
    ];

    allFields.forEach(field => {
      if (field.default !== undefined) {
        defaults[field.id] = field.default;
      }
    });

    const finalConfig = { ...defaults, ...effectiveConfig };
    onConfigSave(finalConfig);
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
        const displayValue = (() => {
          if (field.type === 'variable_multi') {
            const arr = Array.isArray(value) ? value : [];
            return arr.length > 0 ? arr.join(', ') : '—';
          }
          return String(value || '').trim() || '—';
        })();

        return (
          <div>
            <label className="block text-sm font-medium text-[color:var(--text-primary)] mb-1">
              {field.label}
            </label>
            <div className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--white)] overflow-hidden">
              <div className="px-3 py-2 flex items-center justify-between gap-3">
                <div className="min-w-0 text-sm text-[color:var(--text-secondary)] truncate" title={displayValue}>
                  {displayValue}
                </div>
                <button
                  type="button"
                  onClick={() => openVarPicker(field)}
                  className="shrink-0 px-3 py-1 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold tracking-[0.12em] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)] active:scale-[0.98]"
                >
                  Выбор переменных
                </button>
              </div>
            </div>
          </div>
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

      {isVarPickerOpen && varPickerField ? (
        <div
          className="fixed inset-0 z-[60] bg-black/40 p-4 flex items-center justify-center"
          role="dialog"
          aria-modal="true"
          aria-label="Выбор переменных"
          onMouseDown={(e) => {
            if (e.target !== e.currentTarget) return;
            setIsVarPickerOpen(false);
            setVarPickerField(null);
          }}
        >
          <div className="w-full max-w-5xl h-[82vh] bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] overflow-hidden flex flex-col">
            <div className="px-5 py-4 border-b border-[color:var(--border-color)] flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Выбор переменных</div>
                <div className="mt-1 text-lg font-black text-[color:var(--text-primary)] truncate">{varPickerField.label}</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setIsVarPickerOpen(false);
                  setVarPickerField(null);
                }}
                className="text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)] active:scale-[0.98]"
                aria-label="Закрыть"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>

            <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-[minmax(360px,1fr)_minmax(280px,420px)]">
              <div className="overflow-hidden flex flex-col">
                <div className="px-5 pt-4 flex items-center gap-3">
                  <div className="flex-1 border border-[color:var(--border-color)] rounded-[2px] overflow-hidden bg-[color:var(--white)] flex items-center gap-2 px-3 h-10">
                    <MagnifyingGlassIcon className="w-4 h-4 text-[color:var(--text-muted)]" />
                    <input
                      value={varPickerSearch}
                      onChange={(e) => setVarPickerSearch(e.target.value)}
                      placeholder="Поиск"
                      className="w-full bg-transparent outline-none border-none text-sm"
                    />
                  </div>

                  <div className="border border-[color:var(--border-color)] rounded-[2px] overflow-hidden bg-[color:var(--white)] h-10 flex items-center px-2">
                    <select
                      value={varPickerRoleFilter}
                      onChange={(e) => setVarPickerRoleFilter(e.target.value)}
                      className="bg-transparent outline-none border-none text-sm text-[color:var(--text-secondary)]"
                    >
                      <option value="all">Все роли</option>
                      <option value="target">Исход</option>
                      <option value="group">Группа</option>
                      <option value="covariate">Ковариата</option>
                      <option value="unused">Не назначено</option>
                    </select>
                  </div>
                </div>

                <div className="px-5 pt-3 flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => {
                      const all = Array.isArray(columns) ? columns : [];
                      const names = all
                        .map((c) => (typeof c === 'string' ? c : c?.name))
                        .filter(Boolean);
                      const byRole = names.filter((n) => (roleByName?.[n] || 'unused') === 'target');
                      const byType = names.filter((n) => (columnMetaByName?.[n]?.type || '') === 'numeric');
                      const picked = byRole.length > 0 ? byRole : byType;
                      if (picked.length === 0) return;
                      if (varPickerField.type === 'variable_multi') setVarPickerDraft(picked);
                      else setVarPickerDraft(picked[0]);
                    }}
                    className="px-3 py-1.5 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold tracking-[0.12em] hover:border-[color:var(--text-primary)]"
                  >
                    Взять все исходы
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      const all = Array.isArray(columns) ? columns : [];
                      const names = all
                        .map((c) => (typeof c === 'string' ? c : c?.name))
                        .filter(Boolean);
                      const byRole = names.filter((n) => (roleByName?.[n] || 'unused') === 'covariate');
                      const taken = new Set([
                        String(effectiveConfig?.outcome || effectiveConfig?.target || '').trim(),
                        ...(Array.isArray(effectiveConfig?.outcome_cols) ? effectiveConfig.outcome_cols : []),
                      ].filter(Boolean));
                      const byType = names
                        .filter((n) => (columnMetaByName?.[n]?.type || '') === 'numeric')
                        .filter((n) => !taken.has(n));
                      const picked = byRole.length > 0 ? byRole : byType;
                      if (picked.length === 0) return;
                      if (varPickerField.type === 'variable_multi') setVarPickerDraft(picked);
                      else setVarPickerDraft(picked[0]);
                    }}
                    className="px-3 py-1.5 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold tracking-[0.12em] hover:border-[color:var(--text-primary)]"
                  >
                    Взять все ковариаты
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto px-5 pb-5 pt-4">
                  {(() => {
                    const all = Array.isArray(columns) ? columns : [];
                    let names = all
                      .map((c) => (typeof c === 'string' ? c : c?.name))
                      .filter(Boolean);

                    const isMulti = varPickerField.type === 'variable_multi';
                    const currentMulti = isMulti ? (Array.isArray(varPickerDraft) ? varPickerDraft : []) : [];

                    const isOutcomeMulti = isMulti
                      && (method === 'friedman' || method === 'rm_anova')
                      && varPickerField.id === 'outcome_cols';

                    let outcomeGroups = null;
                    if (isOutcomeMulti) {
                      const min = method === 'friedman' ? 3 : 2;

                      const baseKey = (raw) => {
                        const s = String(raw || '').trim();
                        const stripped = s
                          .replace(/\s+/g, ' ')
                          .replace(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?\d+)$/i, '')
                          .replace(/[_\-\s]+$/g, '')
                          .trim();
                        return stripped.toLowerCase() || s.toLowerCase();
                      };

                      const timeIndex = (raw) => {
                        const s = String(raw || '').trim();
                        const m = s.match(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?)(\d+)$/i);
                        if (!m) return null;
                        const n = Number.parseInt(m[1], 10);
                        return Number.isFinite(n) ? n : null;
                      };

                      const numericCandidates = names.filter((n) => {
                        const t = columnMetaByName?.[n]?.type;
                        return !t || t === 'numeric';
                      });

                      const groupByBase = {};
                      for (const n of numericCandidates) {
                        const k = baseKey(n);
                        if (!groupByBase[k]) groupByBase[k] = [];
                        groupByBase[k].push(n);
                      }

                      outcomeGroups = Object.entries(groupByBase)
                        .filter(([, vals]) => vals.length >= min)
                        .map(([k, vals]) => ({
                          key: k,
                          cols: [...vals].sort((a, b) => {
                            const ia = timeIndex(a);
                            const ib = timeIndex(b);
                            if (ia == null && ib == null) return String(a).localeCompare(String(b), 'ru');
                            if (ia == null) return 1;
                            if (ib == null) return -1;
                            return ia - ib;
                          })
                        }))
                        .sort((a, b) => b.cols.length - a.cols.length || a.key.localeCompare(b.key, 'ru'));

                      const basesAllowed = new Set(
                        Object.entries(groupByBase)
                          .filter(([, vals]) => vals.length >= min)
                          .map(([k]) => k)
                      );

                      const allowed = new Set(
                        numericCandidates.filter((n) => basesAllowed.has(baseKey(n)))
                      );
                      currentMulti.forEach((n) => allowed.add(n));
                      names = names.filter((n) => allowed.has(n));
                    }

                    const filtered = names.filter((n) => {
                      if (varPickerSearch.trim()) {
                        const q = varPickerSearch.trim().toLowerCase();
                        if (!String(n).toLowerCase().includes(q)) return false;
                      }
                      if (varPickerRoleFilter && varPickerRoleFilter !== 'all') {
                        const r = roleByName?.[n] || 'unused';
                        if (r !== varPickerRoleFilter) return false;
                      }
                      return true;
                    });

                    const currentSingle = !isMulti ? String(varPickerDraft || '').trim() : '';
                    const multiSet = new Set(currentMulti);

                    const toggle = (name) => {
                      if (!name) return;
                      if (isMulti) {
                        setVarPickerDraft((prev) => {
                          const arr = Array.isArray(prev) ? prev : [];
                          return arr.includes(name) ? arr.filter((x) => x !== name) : [...arr, name];
                        });
                        return;
                      }
                      setVarPickerDraft((prev) => (prev === name ? '' : name));
                    };

                    const selectAllFiltered = () => {
                      if (!isMulti) return;
                      setVarPickerDraft(filtered);
                    };

                    const clearAllSelected = () => {
                      if (!isMulti) return;
                      setVarPickerDraft([]);
                    };

                    const clearFilteredSelected = () => {
                      if (!isMulti) return;
                      const toRemove = new Set(filtered);
                      setVarPickerDraft((prev) => {
                        const arr = Array.isArray(prev) ? prev : [];
                        return arr.filter((x) => !toRemove.has(x));
                      });
                    };

                    const addOutcomeGroup = (cols) => {
                      if (!isMulti) return;
                      const list = Array.isArray(cols) ? cols.filter(Boolean) : [];
                      if (list.length === 0) return;
                      setVarPickerDraft((prev) => {
                        const arr = Array.isArray(prev) ? prev : [];
                        const set = new Set(arr);
                        list.forEach((x) => set.add(x));
                        return Array.from(set);
                      });
                    };

                    const setOutcomeGroupOnly = (cols) => {
                      if (!isMulti) return;
                      const list = Array.isArray(cols) ? cols.filter(Boolean) : [];
                      setVarPickerDraft(list);
                    };

                    return (
                      <div className="border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
                        {isOutcomeMulti && Array.isArray(outcomeGroups) && outcomeGroups.length > 0 ? (
                          <div className="border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
                            <div className="px-3 py-2 flex items-center justify-between gap-3">
                              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Группы повторений</div>
                              <div className="text-xs text-[color:var(--text-muted)] font-mono">{outcomeGroups.length}</div>
                            </div>
                            <div className="px-3 pb-3 grid grid-cols-1 gap-2">
                              {outcomeGroups.slice(0, 10).map((g) => (
                                <div key={g.key} className="border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)] px-3 py-2 flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <div className="text-sm font-semibold text-[color:var(--text-primary)] truncate">{g.key}</div>
                                    <div className="mt-1 text-[10px] tracking-[0.22em] uppercase text-[color:var(--text-muted)]">{g.cols.length} точек · {g.cols.slice(0, 4).join(', ')}{g.cols.length > 4 ? '…' : ''}</div>
                                  </div>
                                  <div className="flex items-center gap-2 shrink-0">
                                    <button
                                      type="button"
                                      onClick={() => setOutcomeGroupOnly(g.cols)}
                                      className="h-8 px-3 rounded-[2px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black"
                                    >
                                      Выбрать
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => addOutcomeGroup(g.cols)}
                                      className="h-8 px-3 rounded-[2px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold uppercase tracking-[0.18em] hover:opacity-90"
                                    >
                                      Добавить
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
                          <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Список</div>
                          <div className="flex items-center gap-2">
                            {isMulti ? (
                              <>
                                <button
                                  type="button"
                                  onClick={selectAllFiltered}
                                  className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                                >
                                  Выбрать все (по фильтру)
                                </button>
                                <button
                                  type="button"
                                  onClick={clearFilteredSelected}
                                  className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                                >
                                  Снять (по фильтру)
                                </button>
                                <button
                                  type="button"
                                  onClick={clearAllSelected}
                                  className="text-xs font-semibold text-[color:var(--accent)] hover:text-[color:var(--text-primary)]"
                                >
                                  Снять все
                                </button>
                              </>
                            ) : null}
                            <div className="text-xs text-[color:var(--text-muted)] font-mono">{filtered.length}</div>
                          </div>
                        </div>
                        <div className="max-h-[52vh] overflow-y-auto">
                          {filtered.length > 0 ? filtered.map((name) => {
                            const role = roleByName?.[name] || 'unused';
                            const roleLabel = role === 'target' ? 'Исход' : role === 'group' ? 'Группа' : role === 'covariate' ? 'Ковариата' : '—';
                            const checked = isMulti ? multiSet.has(name) : currentSingle === name;
                            return (
                              <label
                                key={name}
                                className={`flex items-center gap-3 px-3 py-2 border-b border-[color:var(--border-color)] cursor-pointer ${checked ? 'bg-[color:var(--bg-secondary)]' : 'hover:bg-[color:var(--bg-secondary)]'}`}
                              >
                                <input
                                  type={isMulti ? 'checkbox' : 'radio'}
                                  name="var_picker"
                                  checked={checked}
                                  onChange={() => toggle(name)}
                                  className="text-[color:var(--accent)] rounded-[2px]"
                                />
                                <div className="min-w-0 flex-1">
                                  <div className={`text-sm truncate ${checked ? 'font-semibold text-[color:var(--text-primary)]' : 'text-[color:var(--text-secondary)]'}`}>{name}</div>
                                  <div className="mt-0.5 text-[10px] tracking-[0.22em] uppercase text-[color:var(--text-muted)]">{roleLabel}</div>
                                </div>
                              </label>
                            );
                          }) : (
                            <div className="p-6 text-sm text-[color:var(--text-muted)] text-center italic">Ничего не найдено</div>
                          )}
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>

              <aside className="border-t md:border-t-0 md:border-l border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden flex flex-col">
                <div className="px-5 pt-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Выбрано</div>
                    <div className="flex items-center gap-2">
                      {varPickerField.type === 'variable_multi' ? (
                        <button
                          type="button"
                          onClick={() => setVarPickerDraft([])}
                          className="text-xs font-semibold text-[color:var(--accent)] hover:text-[color:var(--text-primary)]"
                        >
                          Очистить
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={resetVarPickerDraft}
                        className="text-xs font-semibold text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]"
                      >
                        Сбросить
                      </button>
                    </div>
                  </div>
                  <div className="mt-2 border border-[color:var(--border-color)] rounded-[2px] bg-[color:var(--bg-secondary)] p-3 max-h-[56vh] overflow-y-auto pr-1">
                    {(() => {
                      if (varPickerField.type !== 'variable_multi') {
                        const v = String(varPickerDraft || '').trim();
                        return (
                          <div className="text-xs font-mono text-[color:var(--text-primary)] break-words">{v || '—'}</div>
                        );
                      }

                      const arr = Array.isArray(varPickerDraft) ? varPickerDraft.filter(Boolean) : [];
                      const isOutcomeMulti = (method === 'friedman' || method === 'rm_anova') && varPickerField.id === 'outcome_cols';
                      if (arr.length === 0) return <div className="text-xs text-[color:var(--text-muted)] italic">—</div>;

                      const baseKey = (raw) => {
                        const s = String(raw || '').trim();
                        const stripped = s
                          .replace(/\s+/g, ' ')
                          .replace(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?\d+)$/i, '')
                          .replace(/[_\-\s]+$/g, '')
                          .trim();
                        return stripped || s;
                      };

                      const timeIndex = (raw) => {
                        const s = String(raw || '').trim();
                        const m = s.match(/(?:[_\-\s]?(?:t|time|tp|visit|day|week|month|m|w|d)?)(\d+)$/i);
                        if (!m) return null;
                        const n = Number.parseInt(m[1], 10);
                        return Number.isFinite(n) ? n : null;
                      };

                      const removeOne = (name) => {
                        setVarPickerDraft((prev) => {
                          const p = Array.isArray(prev) ? prev : [];
                          return p.filter((x) => x !== name);
                        });
                      };

                      if (!isOutcomeMulti) {
                        return (
                          <div className="flex flex-wrap gap-2">
                            {arr.map((name) => (
                              <div key={name} className="inline-flex items-center gap-2 px-2.5 py-1 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)]">
                                <div className="text-xs font-mono text-[color:var(--text-primary)] truncate max-w-[240px]">{name}</div>
                                <button
                                  type="button"
                                  onClick={() => removeOne(name)}
                                  className="text-xs font-semibold text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                  aria-label="Удалить"
                                >
                                  ×
                                </button>
                              </div>
                            ))}
                          </div>
                        );
                      }

                      const byBase = new Map();
                      for (const n of arr) {
                        const k = baseKey(n);
                        if (!byBase.has(k)) byBase.set(k, []);
                        byBase.get(k).push(n);
                      }
                      const groups = Array.from(byBase.entries())
                        .map(([k, cols]) => ({
                          key: k,
                          cols: [...cols].sort((a, b) => {
                            const ia = timeIndex(a);
                            const ib = timeIndex(b);
                            if (ia == null && ib == null) return String(a).localeCompare(String(b), 'ru');
                            if (ia == null) return 1;
                            if (ib == null) return -1;
                            return ia - ib;
                          })
                        }))
                        .sort((a, b) => b.cols.length - a.cols.length || a.key.localeCompare(b.key, 'ru'));

                      const removeGroup = (k) => {
                        setVarPickerDraft((prev) => {
                          const p = Array.isArray(prev) ? prev : [];
                          const rm = new Set((byBase.get(k) || []).map(String));
                          return p.filter((x) => !rm.has(String(x)));
                        });
                      };

                      const minPoints = method === 'friedman' ? 3 : 2;
                      const bases = new Set(groups.map((g) => g.key));
                      const all = Array.isArray(columns) ? columns : [];
                      const allNames = all
                        .map((c) => (typeof c === 'string' ? c : c?.name))
                        .filter(Boolean);
                      const numericCandidates = allNames.filter((n) => {
                        const t = columnMetaByName?.[n]?.type;
                        return !t || t === 'numeric';
                      });
                      const universeByBase = new Map();
                      for (const n of numericCandidates) {
                        const k = baseKey(n);
                        if (!bases.has(k)) continue;
                        if (!universeByBase.has(k)) universeByBase.set(k, []);
                        universeByBase.get(k).push(n);
                      }
                      for (const [k, cols] of universeByBase.entries()) {
                        universeByBase.set(
                          k,
                          [...cols].sort((a, b) => {
                            const ia = timeIndex(a);
                            const ib = timeIndex(b);
                            if (ia == null && ib == null) return String(a).localeCompare(String(b), 'ru');
                            if (ia == null) return 1;
                            if (ib == null) return -1;
                            return ia - ib;
                          })
                        );
                      }
                      const maxPoints = Math.max(
                        0,
                        ...Array.from(universeByBase.values()).map((cols) => (Array.isArray(cols) ? cols.length : 0))
                      );

                      const availableIndices = (() => {
                        const set = new Set();
                        for (const cols of universeByBase.values()) {
                          const list = Array.isArray(cols) ? cols : [];
                          for (const name of list) {
                            const ti = timeIndex(name);
                            if (ti != null) set.add(ti);
                          }
                        }
                        return Array.from(set).sort((a, b) => a - b);
                      })();

                      const inferredCap = Math.max(
                        minPoints,
                        ...groups.map((g) => (Array.isArray(g?.cols) ? g.cols.length : 0))
                      );
                      const cap = Math.max(
                        minPoints,
                        Math.min(maxPoints || inferredCap, Number.isFinite(rmPointCap) ? rmPointCap : inferredCap)
                      );

                      const presetCaps = (() => {
                        const out = [];
                        const end = Math.min(maxPoints, minPoints + 6);
                        for (let n = minPoints; n <= end; n += 1) out.push(n);
                        if (maxPoints > end) out.push(maxPoints);
                        return Array.from(new Set(out));
                      })();

                      const applyCapToSelection = (nextCap) => {
                        const v = Number(nextCap);
                        const safe = Number.isFinite(v) ? v : minPoints;
                        const nCap = Math.max(minPoints, Math.min(maxPoints || safe, safe));
                        setRmPointCap(nCap);
                        setRmPointMode('cap');
                        setVarPickerDraft((prev) => {
                          const p = Array.isArray(prev) ? prev : [];
                          const out = [];
                          const seenBase = new Set();
                          for (const x of p) {
                            const k = baseKey(x);
                            if (!bases.has(k)) continue;
                            if (seenBase.has(k)) continue;
                            seenBase.add(k);
                            const u = universeByBase.get(k) || [];
                            const take = u.length > 0 ? u.slice(0, Math.min(nCap, u.length)) : [x];
                            take.forEach((name) => out.push(name));
                          }
                          const uniq = [];
                          const seen = new Set();
                          for (const x of out) {
                            const s = String(x);
                            if (seen.has(s)) continue;
                            seen.add(s);
                            uniq.push(x);
                          }
                          return uniq;
                        });
                      };

                      const parsePointSpec = (raw) => {
                        const s = String(raw || '').trim();
                        if (!s) return null;
                        const m = s.match(/^\s*(\d+)\s*-\s*(\d+)\s*$/);
                        if (m) {
                          let a = Number.parseInt(m[1], 10);
                          let b = Number.parseInt(m[2], 10);
                          if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
                          if (a > b) [a, b] = [b, a];
                          const out = [];
                          for (let i = a; i <= b; i += 1) out.push(i);
                          return out;
                        }
                        const nums = s
                          .split(/[^0-9]+/g)
                          .filter(Boolean)
                          .map((x) => Number.parseInt(x, 10))
                          .filter((n) => Number.isFinite(n));
                        if (nums.length === 0) return null;
                        return Array.from(new Set(nums)).sort((a, b) => a - b);
                      };

                      const applyIndicesToSelection = (next) => {
                        const arr0 = Array.isArray(next) ? next : [];
                        const uniq = Array.from(
                          new Set(arr0.map((x) => Number.parseInt(String(x), 10)).filter((n) => Number.isFinite(n)))
                        ).sort((a, b) => a - b);
                        if (uniq.length === 0) return;
                        setRmPointMode('indices');
                        setRmPointIndices(uniq);
                        const wanted = new Set(uniq);
                        setVarPickerDraft((prev) => {
                          const p = Array.isArray(prev) ? prev : [];
                          const out = [];
                          const seenBase = new Set();
                          for (const x of p) {
                            const k = baseKey(x);
                            if (!bases.has(k)) continue;
                            if (seenBase.has(k)) continue;
                            seenBase.add(k);
                            const u = universeByBase.get(k) || [];
                            const take = u.filter((name) => {
                              const ti = timeIndex(name);
                              return ti != null && wanted.has(ti);
                            });
                            take.forEach((name) => out.push(name));
                          }
                          const uniqOut = [];
                          const seen = new Set();
                          for (const x of out) {
                            const ss = String(x);
                            if (seen.has(ss)) continue;
                            seen.add(ss);
                            uniqOut.push(x);
                          }
                          return uniqOut;
                        });
                      };

                      return (
                        <div className="space-y-2">
                          {maxPoints >= minPoints ? (
                            <div className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                              <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
                                <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">Точки</div>
                                <div className="text-xs font-mono text-[color:var(--text-secondary)]">
                                  {rmPointMode === 'indices' && Array.isArray(rmPointIndices) && rmPointIndices.length > 0
                                    ? rmPointIndices.join('·')
                                    : `${cap}/${maxPoints}`}
                                </div>
                              </div>
                              <div className="px-3 py-3 space-y-2">
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setRmPointMode('cap');
                                      setRmPointIndices(null);
                                      setRmPointSpec('');
                                    }}
                                    className={
                                      rmPointMode === 'cap'
                                        ? 'h-7 px-2.5 rounded-[999px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-semibold'
                                        : 'h-7 px-2.5 rounded-[999px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black'
                                    }
                                  >
                                    Первые N
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      const next = (() => {
                                        const fromExisting = Array.isArray(rmPointIndices) && rmPointIndices.length > 0 ? rmPointIndices : null;
                                        if (fromExisting) return fromExisting;
                                        if (availableIndices.length > 0) return availableIndices.slice(0, Math.min(cap, availableIndices.length));
                                        return [];
                                      })();
                                      setRmPointMode('indices');
                                      if (next.length > 0) setRmPointIndices(next);
                                    }}
                                    className={
                                      rmPointMode === 'indices'
                                        ? 'h-7 px-2.5 rounded-[999px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-semibold'
                                        : 'h-7 px-2.5 rounded-[999px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black'
                                    }
                                  >
                                    Набор
                                  </button>
                                  <div className="ml-auto text-[10px] tracking-[0.22em] uppercase text-[color:var(--text-muted)]">для всех групп</div>
                                </div>

                                {rmPointMode === 'indices' ? (
                                  <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                      <input
                                        type="text"
                                        value={rmPointSpec}
                                        onChange={(e) => setRmPointSpec(e.target.value)}
                                        placeholder="2-5 или 1,3,6"
                                        className="h-8 flex-1 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-sm font-mono text-[color:var(--text-primary)]"
                                        aria-label="Точки (список или диапазон)"
                                      />
                                      <button
                                        type="button"
                                        onClick={() => {
                                          const parsed = parsePointSpec(rmPointSpec);
                                          if (!parsed) return;
                                          applyIndicesToSelection(parsed);
                                        }}
                                        className="h-8 px-3 rounded-[2px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-bold uppercase tracking-[0.18em] hover:opacity-90"
                                      >
                                        Применить
                                      </button>
                                    </div>

                                    {availableIndices.length > 0 ? (
                                      <div className="flex flex-wrap gap-2">
                                        {availableIndices.slice(0, 24).map((n) => {
                                          const chosen = Array.isArray(rmPointIndices) && rmPointIndices.includes(n);
                                          return (
                                            <button
                                              key={n}
                                              type="button"
                                              onClick={() => {
                                                const next = (() => {
                                                  const curr = Array.isArray(rmPointIndices) ? rmPointIndices : [];
                                                  const set = new Set(curr);
                                                  if (set.has(n)) set.delete(n);
                                                  else set.add(n);
                                                  return Array.from(set).sort((a, b) => a - b);
                                                })();
                                                applyIndicesToSelection(next);
                                              }}
                                              className={
                                                chosen
                                                  ? 'h-7 px-2.5 rounded-[999px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-semibold'
                                                  : 'h-7 px-2.5 rounded-[999px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black'
                                              }
                                              aria-label={`Переключить точку ${n}`}
                                            >
                                              {n}
                                            </button>
                                          );
                                        })}
                                      </div>
                                    ) : null}
                                  </div>
                                ) : (
                                  <div className="space-y-2">
                                    <div className="flex items-center gap-2">
                                      <button
                                        type="button"
                                        onClick={() => applyCapToSelection(cap - 1)}
                                        disabled={cap <= minPoints}
                                        className="h-8 w-8 rounded-[2px] border border-[color:var(--border-color)] text-sm font-semibold text-[color:var(--text-primary)] disabled:opacity-40"
                                        aria-label="Минус точка"
                                      >
                                        −
                                      </button>
                                      <input
                                        type="number"
                                        min={minPoints}
                                        max={maxPoints}
                                        value={cap}
                                        onChange={(e) => applyCapToSelection(e.target.value)}
                                        className="h-8 w-20 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] px-2 text-sm font-mono text-[color:var(--text-primary)]"
                                        aria-label="Количество точек"
                                      />
                                      <button
                                        type="button"
                                        onClick={() => applyCapToSelection(cap + 1)}
                                        disabled={cap >= maxPoints}
                                        className="h-8 w-8 rounded-[2px] border border-[color:var(--border-color)] text-sm font-semibold text-[color:var(--text-primary)] disabled:opacity-40"
                                        aria-label="Плюс точка"
                                      >
                                        +
                                      </button>
                                    </div>

                                    <div className="flex flex-wrap gap-2">
                                      {presetCaps.map((n) => (
                                        <button
                                          key={n}
                                          type="button"
                                          onClick={() => applyCapToSelection(n)}
                                          className={
                                            n === cap
                                              ? 'h-7 px-2.5 rounded-[999px] bg-[color:var(--black)] text-[color:var(--white)] text-xs font-semibold'
                                              : 'h-7 px-2.5 rounded-[999px] border border-[color:var(--border-color)] text-xs font-semibold text-[color:var(--text-primary)] hover:border-black'
                                          }
                                          aria-label={`Выбрать ${n} точек`}
                                        >
                                          {n}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : null}
                          {groups.map((g) => (
                            <div key={g.key} className="rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--white)] overflow-hidden">
                              <div className="px-3 py-2 bg-[color:var(--bg-secondary)] border-b border-[color:var(--border-color)] flex items-center justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="text-xs font-semibold text-[color:var(--text-primary)] truncate">{g.key}</div>
                                  <div className="mt-0.5 text-[10px] tracking-[0.22em] uppercase text-[color:var(--text-muted)]">{g.cols.length} точек</div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => removeGroup(g.key)}
                                  className="text-xs font-semibold text-[color:var(--accent)] hover:text-[color:var(--text-primary)]"
                                >
                                  Удалить группу
                                </button>
                              </div>
                              <div className="p-3 flex flex-wrap gap-2">
                                {g.cols.map((name) => (
                                  <div key={name} className="inline-flex items-center gap-2 px-2.5 py-1 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
                                    <div className="text-xs font-mono text-[color:var(--text-primary)] truncate max-w-[240px]">{name}</div>
                                    <button
                                      type="button"
                                      onClick={() => removeOne(name)}
                                      className="text-xs font-semibold text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                      aria-label="Удалить"
                                    >
                                      ×
                                    </button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      );
                    })()}
                  </div>
                </div>

                <div className="flex-1" />

                <div className="px-5 py-4 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] flex items-center justify-between gap-3">
                  <div className="text-xs text-[color:var(--text-secondary)]">
                    {(() => {
                      if (varPickerField.type !== 'variable_multi') return null;
                      const arr = Array.isArray(varPickerDraft) ? varPickerDraft : [];
                      const min = typeof varPickerField.minItems === 'number' ? varPickerField.minItems : 0;
                      if (min > 0 && arr.length < min) return `Нужно минимум: ${min}`;
                      return `Кол-во: ${arr.length}`;
                    })()}
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => {
                        setIsVarPickerOpen(false);
                        setVarPickerField(null);
                      }}
                      className="btn-secondary px-3.5 py-2 text-xs"
                    >
                      Отмена
                    </button>
                    <button
                      type="button"
                      onClick={applyVarPicker}
                      disabled={(() => {
                        if (varPickerField.type !== 'variable_multi') return false;
                        const arr = Array.isArray(varPickerDraft) ? varPickerDraft : [];
                        const min = typeof varPickerField.minItems === 'number' ? varPickerField.minItems : 0;
                        return min > 0 && arr.length < min;
                      })()}
                      className="btn-primary px-3.5 py-2 text-xs"
                    >
                      Применить
                    </button>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        </div>
      ) : null}
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
    anova_twoway: 'Двухфакторной ANOVA',
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
