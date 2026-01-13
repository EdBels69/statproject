import React, { useState } from 'react';
import { 
  UserGroupIcon,
  ClockIcon,
  ChartBarIcon,
  BeakerIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PlusIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline';
import { useTranslation } from '../../../hooks/useTranslation';

const TestSelectionPanel = ({ 
  onTestSelect, 
  disabled = false 
}) => {
  const { t } = useTranslation();
  const [expandedCategories, setExpandedCategories] = useState({
    group_comparison: true,
    paired_comparison: false,
    correlation: false,
    advanced: false
  });

  const toggleCategory = (categoryId) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryId]: !prev[categoryId]
    }));
  };

  const handleTestClick = (test) => {
    if (disabled) return;
    onTestSelect(test);
  };

  const testCategories = [
    {
      id: 'group_comparison',
      name: t('group_comparison'),
      icon: UserGroupIcon,
      description: t('group_comparison_desc'),
      tests: [
        { id: 'mann_whitney', name: 'Mann-Whitney U', description: 'Непараметрический тест для независимых выборок' },
        { id: 't_test', name: 't-критерий Стьюдента', description: 'Параметрический тест для независимых выборок' },
        { id: 'welch_t_test', name: 'Welch t-test', description: 'Альтернатива t-test при неравных дисперсиях' },
        { id: 'anova', name: 'ANOVA', description: 'Однофакторный дисперсионный анализ' },
        { id: 'kruskal_wallis', name: 'Kruskal-Wallis', description: 'Непараметрическая ANOVA' }
      ]
    },
    {
      id: 'paired_comparison',
      name: t('paired_comparison'),
      icon: ClockIcon,
      description: t('paired_comparison_desc'),
      tests: [
        { id: 'wilcoxon', name: 'Wilcoxon Signed-Rank', description: 'Непараметрический тест для парных выборок' },
        { id: 'paired_t_test', name: 'Парный t-test', description: 'Параметрический тест для парных выборок' },
        { id: 'rm_anova', name: 'RM-ANOVA', description: 'Дисперсионный анализ с повторными измерениями' }
      ]
    },
    {
      id: 'correlation',
      name: t('correlation'),
      icon: ChartBarIcon,
      description: t('correlation_desc'),
      tests: [
        { id: 'pearson', name: 'Pearson Correlation', description: 'Параметрическая корреляция Пирсона' },
        { id: 'spearman', name: 'Spearman Correlation', description: 'Непараметрическая корреляция Спирмена' },
        { id: 'clustered_correlation', name: 'Кластерная корреляция', description: 'Автоматическая кластеризация переменных' }
      ]
    },
    {
      id: 'advanced',
      name: t('advanced'),
      icon: BeakerIcon,
      description: t('advanced_desc'),
      tests: [
        { id: 'mixed_effects', name: 'Mixed Effects (LMM)', description: 'Линейные смешанные модели' },
        { id: 'chi_square', name: 'Chi-Square Test', description: 'Тест хи-квадрат' },
        { id: 'survival', name: 'Survival Analysis', description: 'Анализ выживаемости (Kaplan-Meier)' }
      ]
    }
  ];

  return (
    <div className="h-full flex flex-col bg-white border-r border-gray-200">
      <div className="p-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <BeakerIcon className="w-5 h-5 text-blue-600" />
          {t('statistical_tests')}
        </h2>
        <p className="text-sm text-gray-600 mt-1">
          {t('select_tests_tooltip')}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {testCategories.map(category => {
          const Icon = category.icon;
          const isExpanded = expandedCategories[category.id];

          return (
            <div key={category.id} className="mb-2">
              <button
                onClick={() => toggleCategory(category.id)}
                className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Icon className="w-5 h-5 text-gray-700" />
                  <div className="text-left">
                    <div className="font-medium text-gray-900 text-sm">
                      {category.name}
                    </div>
                    <div className="text-xs text-gray-500">
                      {category.tests.length} {t('tests')}
                    </div>
                  </div>
                </div>
                {isExpanded ? (
                  <ChevronDownIcon className="w-5 h-5 text-gray-500" />
                ) : (
                  <ChevronRightIcon className="w-5 h-5 text-gray-500" />
                )}
              </button>

              {isExpanded && (
                <div className="mt-1 ml-2 space-y-1">
                  {category.tests.map(test => (
                    <button
                      key={test.id}
                      onClick={() => handleTestClick(test)}
                      disabled={disabled}
                      className="w-full flex items-start gap-2 p-3 hover:bg-blue-50 rounded-lg transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed group"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <div className="font-medium text-gray-900 text-sm">
                            {test.name}
                          </div>
                          <PlusIcon className="w-4 h-4 text-gray-400 group-hover:text-blue-600 transition-colors" />
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {test.description}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="p-3 border-t border-gray-200 bg-gray-50">
        <div className="flex items-start gap-2 text-xs text-gray-600">
          <InformationCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <p>
            {t('tests_selection_info')}
          </p>
        </div>
      </div>
    </div>
  );
};

export default TestSelectionPanel;
