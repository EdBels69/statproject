import React, { useEffect, useMemo, useState } from 'react';
import {
  UserGroupIcon,
  ClockIcon,
  ChartBarIcon,
  BeakerIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PlusIcon,
  InformationCircleIcon,
  Cog6ToothIcon
} from '@heroicons/react/24/outline';
import { useTranslation } from '../../../hooks/useTranslation';
import { WhyThisTest } from '../education';
import { useLanguage } from '../../../contexts/LanguageContext';
import { checkAssumptions, getAlphaSetting } from '../../../lib/api';
import TestConfigModal from './TestConfigModal';

const TestSelectionPanel = ({
  onTestSelect,
  datasetId,
  suggestedConfig,
  disabled = false
}) => {
  const { t } = useTranslation();
  const { educationLevel } = useLanguage();
  const [expandedCategories, setExpandedCategories] = useState({
    group_comparison: true,
    paired_comparison: false,
    correlation: false,
    categorical: false,
    models: false,
    agreement: false,
    assumptions: false,
    factor_analysis: false,
    clustering: false,
    advanced: false
  });

  const [selectedTest, setSelectedTest] = useState(null);
  const [assumptionProfile, setAssumptionProfile] = useState(null);
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [testConfigs, setTestConfigs] = useState({}); // Store configs per test ID

  const shouldFetchAssumptions = Boolean(selectedTest?.id && datasetId);
  const effectiveDataProfile = useMemo(() => {
    const base = (assumptionProfile && typeof assumptionProfile === 'object') ? assumptionProfile : {};
    return { ...base, independence: base.independence !== false };
  }, [assumptionProfile]);

  const toggleCategory = (categoryId) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryId]: !prev[categoryId]
    }));
  };

  const handleTestClick = (test) => {
    if (disabled) return;
    setSelectedTest(test);
    onTestSelect(test);
  };

  useEffect(() => {
    if (!shouldFetchAssumptions) return;

    const controller = new AbortController();
    const timeout = setTimeout(() => {
      (async () => {
        try {
          setAssumptionProfile(null);
          const payload = await checkAssumptions({
            datasetId,
            methodId: selectedTest.id,
            config: (suggestedConfig && typeof suggestedConfig === 'object') ? suggestedConfig : {},
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
  }, [datasetId, selectedTest?.id, shouldFetchAssumptions, suggestedConfig]);

  const testCategories = [
    {
      id: 'group_comparison',
      name: t('group_comparison'),
      icon: UserGroupIcon,
      description: t('group_comparison_desc'),
      tests: [
        { id: 't_test_one', name: 'One-Sample T-Test', description: 'Сравнение среднего с известным значением' },
        { id: 'mann_whitney', name: 'Mann-Whitney U', description: 'Непараметрический тест для 2 независимых групп' },
        { id: 't_test_ind', name: 't-критерий Стьюдента', description: 'Параметрический тест для 2 независимых групп' },
        { id: 't_test_welch', name: 'Welch t-test', description: 'При неравных дисперсиях' },
        { id: 'anova', name: 'One-Way ANOVA', description: 'Сравнение 3+ групп (параметрический)' },
        { id: 'anova_welch', name: 'Welch ANOVA', description: 'ANOVA при неравных дисперсиях' },
        { id: 'kruskal', name: 'Kruskal-Wallis', description: 'Непараметрический аналог ANOVA' },
        { id: 'anova_twoway', name: 'Two-Way ANOVA', description: 'Два фактора + взаимодействие' },
        { id: 'ancova', name: 'ANCOVA', description: 'ANOVA с ковариатами' }
      ]
    },
    {
      id: 'paired_comparison',
      name: t('paired_comparison'),
      icon: ClockIcon,
      description: t('paired_comparison_desc'),
      tests: [
        { id: 'wilcoxon', name: 'Wilcoxon Signed-Rank', description: 'Непараметрический для парных данных' },
        { id: 't_test_rel', name: 'Paired t-test', description: 'Параметрический для парных данных' },
        { id: 'rm_anova', name: 'RM-ANOVA', description: 'Повторные измерения (параметрический)' },
        { id: 'friedman', name: 'Friedman Test', description: 'Непараметрический RM-ANOVA' },
        { id: 'mcnemar', name: "McNemar's Test", description: 'Парные бинарные данные (до/после)' },
        { id: 'cochran_q', name: "Cochran's Q", description: 'Парные бинарные, 3+ условий' }
      ]
    },
    {
      id: 'correlation',
      name: t('correlation'),
      icon: ChartBarIcon,
      description: t('correlation_desc'),
      tests: [
        { id: 'pearson', name: 'Pearson r', description: 'Линейная корреляция (параметрическая)' },
        { id: 'spearman', name: 'Spearman ρ', description: 'Ранговая корреляция (непараметрическая)' },
        { id: 'point_biserial', name: 'Point-Biserial', description: 'Корреляция с бинарной переменной' },
        { id: 'partial_correlation', name: 'Partial Correlation', description: 'С контролем третьей переменной' },
        { id: 'clustered_correlation', name: 'Correlation Matrix', description: 'Матрица с кластеризацией' }
      ]
    },
    {
      id: 'categorical',
      name: t('categorical') || 'Категориальные',
      icon: ChartBarIcon,
      description: 'Тесты для категориальных переменных',
      tests: [
        { id: 'chi_square', name: 'Chi-Square χ²', description: 'Независимость категориальных переменных' },
        { id: 'fisher', name: "Fisher's Exact", description: 'Для малых выборок (n < 20)' }
      ]
    },
    {
      id: 'models',
      name: t('models') || 'Регрессия',
      icon: ChartBarIcon,
      description: t('models_desc'),
      tests: [
        { id: 'linear_regression', name: 'Linear Regression', description: 'Предсказание непрерывной переменной' },
        { id: 'logistic_regression', name: 'Logistic Regression', description: 'Предсказание бинарного исхода' },
        { id: 'mixed_model', name: 'Mixed Effects (LMM)', description: 'Вложенные/кластеризованные данные' }
      ]
    },
    {
      id: 'agreement',
      name: 'Согласованность',
      icon: UserGroupIcon,
      description: 'Оценка согласия методов/экспертов',
      tests: [
        { id: 'bland_altman', name: 'Bland-Altman', description: 'Согласие двух методов измерения' },
        { id: 'icc', name: 'ICC', description: 'Внутриклассовая корреляция' },
        { id: 'cohens_kappa', name: "Cohen's Kappa", description: 'Согласие экспертов (категории)' },
        { id: 'cronbach_alpha', name: "Cronbach's α", description: 'Внутренняя согласованность шкалы' }
      ]
    },
    {
      id: 'assumptions',
      name: 'Проверка условий',
      icon: BeakerIcon,
      description: 'Тесты для проверки допущений',
      tests: [
        { id: 'shapiro_wilk', name: 'Shapiro-Wilk', description: 'Тест нормальности распределения' },
        { id: 'levene', name: "Levene's Test", description: 'Однородность дисперсий' }
      ]
    },
    {
      id: 'factor_analysis',
      name: 'Факторный анализ',
      icon: BeakerIcon,
      description: 'Снижение размерности и латентные факторы',
      tests: [
        { id: 'pca', name: 'PCA', description: 'Анализ главных компонент' },
        { id: 'efa', name: 'EFA', description: 'Эксплораторный факторный анализ' }
      ]
    },
    {
      id: 'clustering',
      name: 'Кластеризация',
      icon: BeakerIcon,
      description: 'Группировка наблюдений по сходству',
      tests: [
        { id: 'kmeans', name: 'K-Means', description: 'Разбиение на K кластеров' },
        { id: 'hierarchical_clustering', name: 'Hierarchical', description: 'Иерархическая кластеризация (дендрограмма)' }
      ]
    },
    {
      id: 'advanced',
      name: t('advanced'),
      icon: BeakerIcon,
      description: t('advanced_desc'),
      tests: [
        { id: 'survival_km', name: 'Kaplan-Meier', description: 'Анализ выживаемости + Log-Rank' },
        { id: 'roc_analysis', name: 'ROC Analysis', description: 'AUC и оптимальный порог' }
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
                    <div key={test.id} className="flex items-center gap-1">
                      <button
                        onClick={() => handleTestClick(test)}
                        disabled={disabled}
                        className={`flex-1 flex items-start gap-2 p-3 border rounded-[2px] transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed group ${selectedTest?.id === test.id
                          ? 'bg-[color:var(--bg-secondary)] border-[color:var(--accent)]'
                          : 'hover:bg-[color:var(--bg-secondary)] border-transparent hover:border-[color:var(--border-color)]'
                          }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <div className="font-medium text-[color:var(--text-primary)] text-sm">
                              {test.name}
                              {testConfigs[test.id] && <span className="ml-1 text-[color:var(--accent)]">⚙</span>}
                            </div>
                            <PlusIcon className="w-4 h-4 text-[color:var(--text-muted)] group-hover:text-[color:var(--accent)] transition-colors" />
                          </div>
                          <div className="text-xs text-[color:var(--text-muted)] mt-1">
                            {test.description}
                          </div>
                        </div>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedTest(test);
                          setIsConfigModalOpen(true);
                        }}
                        disabled={disabled}
                        className="p-2 hover:bg-[color:var(--bg-secondary)] rounded text-[color:var(--text-muted)] hover:text-[color:var(--accent)] disabled:opacity-50"
                        title="Настройки теста"
                      >
                        <Cog6ToothIcon className="w-4 h-4" />
                      </button>
                    </div>
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

      {selectedTest && (
        <div className="p-3 border-t border-[color:var(--border-color)] bg-[color:var(--white)]">
          <WhyThisTest
            testId={selectedTest.id}
            dataProfile={effectiveDataProfile}
            level={educationLevel || 'junior'}
            defaultExpanded={true}
          />
        </div>
      )}

      <TestConfigModal
        isOpen={isConfigModalOpen}
        onClose={() => setIsConfigModalOpen(false)}
        test={selectedTest}
        initialConfig={selectedTest ? testConfigs[selectedTest.id] : {}}
        onApply={(config) => {
          if (selectedTest) {
            setTestConfigs(prev => ({ ...prev, [selectedTest.id]: config }));
          }
        }}
      />
    </div>
  );
};

export default TestSelectionPanel;
