import React, { useState } from 'react';
import { XMarkIcon, CogIcon, InformationCircleIcon } from '@heroicons/react/24/outline';

const TestConfigModal = ({ 
  isOpen, 
  onClose, 
  method, 
  initialConfig = {}, 
  onConfigSave 
}) => {
  if (!isOpen) return null;

  return (
    <TestConfigModalContent
      key={`${method}-${JSON.stringify(initialConfig || {})}`}
      method={method}
      initialConfig={initialConfig}
      onClose={onClose}
      onConfigSave={onConfigSave}
    />
  );
};

const TestConfigModalContent = ({ method, initialConfig, onClose, onConfigSave }) => {
  const [config, setConfig] = useState(() => initialConfig || {});
  const [activeTab, setActiveTab] = useState('basic');

  // Method-specific configuration templates
  const methodTemplates = {
    // Mixed Effects Models
    mixed_model: {
      basic: [
        {
          id: 'random_slope',
          type: 'boolean',
          label: 'Случайные наклоны',
          description: 'Включить случайные наклоны в модель',
          default: false
        },
        {
          id: 'covariates',
          type: 'multiselect',
          label: 'Ковариаты',
          description: 'Дополнительные переменные для коррекции',
          default: []
        }
      ],
      advanced: [
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
          id: 'convergence_tol',
          type: 'number',
          label: 'Допуск сходимости',
          description: 'Критерий сходимости для итеративных методов',
          default: 1e-6,
          min: 1e-8,
          max: 1e-4,
          step: 1e-6
        }
      ]
    },

    mixed_effects: {
      basic: [
        {
          id: 'random_slope',
          type: 'boolean',
          label: 'Случайные наклоны',
          description: 'Включить случайные наклоны в модель',
          default: false
        },
        {
          id: 'covariates',
          type: 'multiselect',
          label: 'Ковариаты',
          description: 'Дополнительные переменные для коррекции',
          default: []
        }
      ],
      advanced: [
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
          id: 'convergence_tol',
          type: 'number',
          label: 'Допуск сходимости',
          description: 'Критерий сходимости для итеративных методов',
          default: 1e-6,
          min: 1e-8,
          max: 1e-4,
          step: 1e-6
        }
      ]
    },
    
    // Clustered Correlation
    clustered_correlation: {
      basic: [
        {
          id: 'method',
          type: 'select',
          label: 'Метод корреляции',
          description: 'Тип корреляционного коэффициента',
          default: 'pearson',
          options: [
            { value: 'pearson', label: 'Пирсон' },
            { value: 'spearman', label: 'Спирмен' }
          ]
        },
        {
          id: 'linkage_method',
          type: 'select',
          label: 'Метод кластеризации',
          description: 'Алгоритм иерархической кластеризации',
          default: 'ward',
          options: [
            { value: 'ward', label: 'Ward' },
            { value: 'complete', label: 'Complete' },
            { value: 'average', label: 'Average' },
            { value: 'single', label: 'Single' }
          ]
        }
      ],
      advanced: [
        {
          id: 'n_clusters',
          type: 'number',
          label: 'Количество кластеров',
          description: 'Фиксированное количество кластеров (автоопределение если 0)',
          default: 0,
          min: 0,
          max: 20,
          step: 1
        },
        {
          id: 'distance_threshold',
          type: 'number',
          label: 'Порог расстояния',
          description: 'Порог для определения кластеров',
          default: 0.0,
          min: 0.0,
          max: 2.0,
          step: 0.1
        },
        {
          id: 'show_p_values',
          type: 'boolean',
          label: 'Показывать p-значения',
          description: 'Включить p-значения в результаты',
          default: true
        }
      ]
    },
    
    // Repeated Measures ANOVA
    rm_anova: {
      basic: [
        {
          id: 'sphericity_correction',
          type: 'select',
          label: 'Коррекция сферичности',
          description: 'Метод коррекции для нарушения сферичности',
          default: 'greenhouse-geisser',
          options: [
            { value: 'none', label: 'Нет' },
            { value: 'greenhouse-geisser', label: 'Гринхаус-Гейссер' },
            { value: 'huynh-feldt', label: 'Хюин-Фельдт' }
          ]
        }
      ],
      advanced: [
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
    
    // Default template for other methods
    default: {
      basic: [
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
      ],
      advanced: []
    }
  };

  const getMethodTemplate = () => {
    return methodTemplates[method] || methodTemplates.default;
  };

  const handleConfigChange = (fieldId, value) => {
    setConfig(prev => ({
      ...prev,
      [fieldId]: value
    }));
  };

  const handleSave = () => {
    onConfigSave(config);
    onClose();
  };

  const renderField = (field) => {
    const value = config[field.id] ?? field.default;
    
    switch (field.type) {
      case 'boolean':
        return (
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={value}
              onChange={(e) => handleConfigChange(field.id, e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">{field.label}</span>
          </label>
        );
      
      case 'number':
        return (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <input
              type="number"
              value={value}
              onChange={(e) => handleConfigChange(field.id, parseFloat(e.target.value))}
              min={field.min}
              max={field.max}
              step={field.step}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        );
      
      case 'select':
        return (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <select
              value={value}
              onChange={(e) => handleConfigChange(field.id, e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {field.options.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        );
      
      case 'multiselect':
        return (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.label}
            </label>
            <select
              multiple
              value={value}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, option => option.value);
                handleConfigChange(field.id, selected);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              size={4}
            >
              {/* Options would be populated from available columns */}
              <option value="age">Возраст</option>
              <option value="gender">Пол</option>
              <option value="baseline">Базовый уровень</option>
            </select>
          </div>
        );
      
      default:
        return null;
    }
  };

  const template = getMethodTemplate();
  const basicFields = template.basic || [];
  const advancedFields = template.advanced || [];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-96 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center">
            <CogIcon className="w-6 h-6 text-blue-600 mr-2" />
            <h2 className="text-xl font-semibold text-gray-800">
              Настройки {getMethodName(method)}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8 px-6">
            <button
              onClick={() => setActiveTab('basic')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'basic'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              Основные
            </button>
            {advancedFields.length > 0 && (
              <button
                onClick={() => setActiveTab('advanced')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'advanced'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                Дополнительные
              </button>
            )}
          </nav>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-64">
          {activeTab === 'basic' && (
            <div className="space-y-4">
              {basicFields.map(field => (
                <div key={field.id} className="border-l-4 border-blue-100 pl-4">
                  {renderField(field)}
                  {field.description && (
                    <p className="text-sm text-gray-500 mt-1 flex items-center">
                      <InformationCircleIcon className="w-4 h-4 mr-1" />
                      {field.description}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === 'advanced' && (
            <div className="space-y-4">
              {advancedFields.map(field => (
                <div key={field.id} className="border-l-4 border-purple-100 pl-4">
                  {renderField(field)}
                  {field.description && (
                    <p className="text-sm text-gray-500 mt-1 flex items-center">
                      <InformationCircleIcon className="w-4 h-4 mr-1" />
                      {field.description}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {basicFields.length === 0 && advancedFields.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              <InformationCircleIcon className="w-12 h-12 mx-auto mb-4" />
              <p>Нет доступных настроек для этого метода</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-100"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
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
    mixed_model: 'Смешанной модели',
    clustered_correlation: 'Кластерного анализа корреляций',
    rm_anova: 'Повторных измерений ANOVA',
    friedman: 'Теста Фридмана',
    t_test_ind: 't-теста независимых выборок',
    anova: 'ANOVA',
    pearson: 'Корреляции Пирсона',
    spearman: 'Корреляции Спирмена'
  };
  
  return methodNames[methodId] || methodId;
};

export default TestConfigModal;
