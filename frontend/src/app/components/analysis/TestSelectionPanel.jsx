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
    models: false,
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
        { id: 't_test_ind', name: 't-критерий Стьюдента', description: 'Параметрический тест для независимых выборок' },
        { id: 't_test_welch', name: 'Welch t-test', description: 'Альтернатива t-test при неравных дисперсиях' },
        { id: 'anova', name: 'ANOVA', description: 'Однофакторный дисперсионный анализ' },
        { id: 'kruskal', name: 'Kruskal-Wallis', description: 'Непараметрическая ANOVA' }
      ]
    },
    {
      id: 'paired_comparison',
      name: t('paired_comparison'),
      icon: ClockIcon,
      description: t('paired_comparison_desc'),
      tests: [
        { id: 'wilcoxon', name: 'Wilcoxon Signed-Rank', description: 'Непараметрический тест для парных выборок' },
        { id: 't_test_rel', name: 'Парный t-test', description: 'Параметрический тест для парных выборок' },
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
      id: 'models',
      name: t('models'),
      icon: ChartBarIcon,
      description: t('models_desc'),
      tests: [
        { id: 'linear_regression', name: 'Linear Regression', description: 'Линейная регрессия для непрерывного исхода' },
        { id: 'logistic_regression', name: 'Logistic Regression', description: 'Логистическая регрессия для бинарного исхода' }
      ]
    },
    {
      id: 'advanced',
      name: t('advanced'),
      icon: BeakerIcon,
      description: t('advanced_desc'),
      tests: [
        { id: 'mixed_model', name: 'Mixed Effects (LMM)', description: 'Линейные смешанные модели' },
        { id: 'chi_square', name: 'Chi-Square Test', description: 'Тест хи-квадрат' },
        { id: 'survival_km', name: 'Survival Analysis', description: 'Анализ выживаемости (Kaplan-Meier)' }
      ]
    }
  ];

  return (
    <div className="h-full flex flex-col bg-[color:var(--white)] border-r border-[color:var(--border-color)]">
      <div className="p-4 border-b border-[color:var(--border-color)]">
        <h2 className="text-lg font-semibold text-[color:var(--text-primary)] flex items-center gap-2">
          <BeakerIcon className="w-5 h-5 text-[color:var(--accent)]" />
          {t('statistical_tests')}
        </h2>
        <p className="text-sm text-[color:var(--text-muted)] mt-1">
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
                className="w-full flex items-center justify-between p-3 bg-[color:var(--bg-secondary)] hover:bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Icon className="w-5 h-5 text-[color:var(--text-secondary)]" />
                  <div className="text-left">
                    <div className="font-medium text-[color:var(--text-primary)] text-sm">
                      {category.name}
                    </div>
                    <div className="text-xs text-[color:var(--text-muted)]">
                      {category.tests.length} {t('tests')}
                    </div>
                  </div>
                </div>
                {isExpanded ? (
                  <ChevronDownIcon className="w-5 h-5 text-[color:var(--text-muted)]" />
                ) : (
                  <ChevronRightIcon className="w-5 h-5 text-[color:var(--text-muted)]" />
                )}
              </button>

              {isExpanded && (
                <div className="mt-1 ml-2 space-y-1">
                  {category.tests.map(test => (
                    <button
                      key={test.id}
                      onClick={() => handleTestClick(test)}
                      disabled={disabled}
                      className="w-full flex items-start gap-2 p-3 hover:bg-[color:var(--bg-secondary)] border border-transparent hover:border-[color:var(--border-color)] rounded-[2px] transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed group"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <div className="font-medium text-[color:var(--text-primary)] text-sm">
                            {test.name}
                          </div>
                          <PlusIcon className="w-4 h-4 text-[color:var(--text-muted)] group-hover:text-[color:var(--accent)] transition-colors" />
                        </div>
                        <div className="text-xs text-[color:var(--text-muted)] mt-1">
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

      <div className="p-3 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
        <div className="flex items-start gap-2 text-xs text-[color:var(--text-muted)]">
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
