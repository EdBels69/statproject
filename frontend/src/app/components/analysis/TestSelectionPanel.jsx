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
  variant = 'full',
  disabled = false
}) => {
  const { t } = useTranslation();
  const { educationLevel } = useLanguage();
  const isCompact = variant === 'compact';
  const [expandedCategories, setExpandedCategories] = useState({
    compare_2: true,
    compare_3_plus: false,
    paired: false,
    correlation: false,
    categorical: false,
    models: false,
    agreement: false,
    assumptions: false,
    bayesian: false,
    time_series: false,
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
      id: 'compare_2',
      name: t('compare_2_groups'),
      icon: UserGroupIcon,
      description: t('compare_2_groups_desc'),
      tests: [
        { id: 'mann_whitney', name: 'Манна—Уитни (U)', description: 'Непараметрический тест для 2 независимых групп' },
        { id: 't_test_ind', name: 't-тест (независимые)', description: 'Параметрический тест для 2 независимых групп' },
        { id: 't_test_welch', name: 't-тест Уэлча', description: 'При неравных дисперсиях' },
      ]
    },
    {
      id: 'compare_3_plus',
      name: t('compare_3plus_groups'),
      icon: ChartBarIcon,
      description: t('compare_3plus_groups_desc'),
      tests: [
        { id: 'anova', name: 'ANOVA (однофакторная)', description: 'Сравнение 3+ независимых групп (параметрический)' },
        { id: 'anova_welch', name: 'ANOVA Уэлча', description: 'При неравных дисперсиях' },
        { id: 'kruskal', name: 'Краскела—Уоллиса', description: 'Непараметрический аналог ANOVA' },
        { id: 'anova_twoway', name: 'ANOVA (двухфакторная)', description: 'Два фактора + взаимодействие' },
        { id: 'ancova', name: 'ANCOVA', description: 'С учетом ковариат' }
      ]
    },
    {
      id: 'paired',
      name: t('paired_repeated'),
      icon: ClockIcon,
      description: t('paired_repeated_desc'),
      tests: [
        { id: 'wilcoxon', name: 'Уилкоксона (парные)', description: 'Непараметрический для парных данных' },
        { id: 't_test_rel', name: 't-тест (парный)', description: 'Параметрический для парных данных' },
        { id: 'rm_anova', name: 'ANOVA повторных измерений', description: 'Повторные измерения (параметрический)' },
        { id: 'friedman', name: 'Фридмана', description: 'Непараметрический RM-ANOVA' },
        { id: 'mcnemar', name: 'Мак-Немара', description: 'Парные бинарные данные (до/после)' },
        { id: 'cochran_q', name: 'Q Кохрана', description: 'Парные бинарные, 3+ условий' }
      ]
    },
    {
      id: 'correlation',
      name: t('correlation'),
      icon: ChartBarIcon,
      description: t('correlation_desc'),
      tests: [
        { id: 'pearson', name: 'Пирсона (r)', description: 'Линейная корреляция (параметрическая)' },
        { id: 'spearman', name: 'Спирмена (ρ)', description: 'Ранговая корреляция (непараметрическая)' },
        { id: 'point_biserial', name: 'Точечно-бисериальная', description: 'Корреляция с бинарной переменной' },
        { id: 'partial_correlation', name: 'Частная корреляция', description: 'С контролем третьей переменной' },
        { id: 'clustered_correlation', name: 'Матрица корреляций', description: 'Матрица с кластеризацией' }
      ]
    },
    {
      id: 'categorical',
      name: t('categorical') || 'Категориальные',
      icon: ChartBarIcon,
      description: 'Тесты для категориальных переменных',
      tests: [
        { id: 'chi_square', name: 'χ² Пирсона', description: 'Независимость категориальных переменных' },
        { id: 'fisher', name: 'Точный тест Фишера', description: 'Для малых выборок (n < 20)' }
      ]
    },
    {
      id: 'models',
      name: t('models') || 'Регрессия',
      icon: ChartBarIcon,
      description: t('models_desc'),
      tests: [
        { id: 'linear_regression', name: 'Линейная регрессия', description: 'Предсказание непрерывной переменной' },
        { id: 'logistic_regression', name: 'Логистическая регрессия', description: 'Предсказание бинарного исхода' },
        { id: 'mixed_model', name: 'Смешанные эффекты (LMM)', description: 'Вложенные/кластеризованные данные' }
      ]
    },
    {
      id: 'agreement',
      name: 'Согласованность',
      icon: UserGroupIcon,
      description: 'Оценка согласия методов/экспертов',
      tests: [
        { id: 'bland_altman', name: 'Бланд—Олтман', description: 'Согласие двух методов измерения' },
        { id: 'icc', name: 'ICC', description: 'Внутриклассовая корреляция' },
        { id: 'cohens_kappa', name: 'Каппа Коэна', description: 'Согласие экспертов (категории)' },
        { id: 'cronbach_alpha', name: 'α Кронбаха', description: 'Внутренняя согласованность шкалы' }
      ]
    },
    {
      id: 'assumptions',
      name: 'Проверка условий',
      icon: BeakerIcon,
      description: 'Тесты для проверки допущений',
      tests: [
        { id: 'shapiro_wilk', name: 'Шапиро—Уилка', description: 'Тест нормальности распределения' },
        { id: 'levene', name: 'Левена', description: 'Однородность дисперсий' }
      ]
    },
    {
      id: 'bayesian',
      name: 'Байесовская статистика',
      icon: BeakerIcon,
      description: 'Bayes Factor и вероятности гипотез',
      tests: [
        { id: 'bayes_t_test_one', name: 'Bayes t-test (1 выборка)', description: 'Байесовский t-тест для одной выборки' },
        { id: 'bayes_t_test_ind', name: 'Bayes t-test (2 независимые)', description: 'Байесовский t-тест для двух независимых групп' },
        { id: 'bayes_t_test_rel', name: 'Bayes t-test (парный)', description: 'Байесовский t-тест для парных данных' },
        { id: 'bayes_correlation', name: 'Bayes correlation', description: 'Байесовская корреляция (Pearson/Spearman/Kendall)' },
        { id: 'bayes_anova', name: 'Bayes ANOVA', description: 'Байесовский дисперсионный анализ для 2+ групп' },
        { id: 'bayes_linear_regression', name: 'Bayes linear regression', description: 'Байесовская линейная регрессия (BF10/BF01)' },
        { id: 'bayes_chi_square', name: 'Bayes chi-square', description: 'Байесовская проверка связи категориальных переменных' }
      ]
    },
    {
      id: 'time_series',
      name: 'Временные ряды',
      icon: ClockIcon,
      description: 'Тренд, стационарность, автокорреляция и сезонность',
      tests: [
        { id: 'time_series_analysis', name: 'Time Series Analysis', description: 'ADF + ACF + декомпозиция ряда' }
      ]
    },
    {
      id: 'factor_analysis',
      name: 'Факторный анализ',
      icon: BeakerIcon,
      description: 'Снижение размерности и латентные факторы',
      tests: [
        { id: 'pca', name: 'PCA (компоненты)', description: 'Анализ главных компонент' },
        { id: 'efa', name: 'EFA (факторы)', description: 'Эксплораторный факторный анализ' }
      ]
    },
    {
      id: 'clustering',
      name: 'Кластеризация',
      icon: BeakerIcon,
      description: 'Группировка наблюдений по сходству',
      tests: [
        { id: 'kmeans', name: 'K-Means', description: 'Разбиение на K кластеров' },
        { id: 'hierarchical_clustering', name: 'Иерархическая', description: 'Иерархическая кластеризация (дендрограмма)' }
      ]
    },
    {
      id: 'advanced',
      name: t('advanced'),
      icon: BeakerIcon,
      description: t('advanced_desc'),
      tests: [
        { id: 'survival_km', name: 'Каплана—Майера', description: 'Анализ выживаемости + Log-Rank' },
        { id: 'roc_analysis', name: 'ROC-анализ', description: 'AUC и оптимальный порог' }
      ]
    }
  ];

  return (
    <div className="h-full flex flex-col bg-[color:var(--white)]">
      <div className={isCompact ? 'p-3 border-b border-[color:var(--border-color)]' : 'p-4 border-b border-[color:var(--border-color)]'}>
        <h2 className={isCompact ? 'text-sm font-semibold text-[color:var(--text-primary)] flex items-center gap-2' : 'text-lg font-semibold text-[color:var(--text-primary)] flex items-center gap-2'}>
          <BeakerIcon className="w-5 h-5 text-[color:var(--accent)]" />
          {t('statistical_tests')}
        </h2>
        {!isCompact ? (
          <p className="text-sm text-[color:var(--text-muted)] mt-1">
            {t('select_tests_tooltip')}
          </p>
        ) : null}
      </div>

      <div className={isCompact ? 'flex-1 overflow-y-auto p-1' : 'flex-1 overflow-y-auto p-2'}>
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
                <div className={isCompact ? 'mt-1 ml-2 space-y-1' : 'mt-1 ml-2 space-y-1'}>
                  {category.tests.map(test => (
                    <div key={test.id} className="flex items-center gap-1">
                      <button
                        onClick={() => handleTestClick(test)}
                        disabled={disabled}
                        className={`flex-1 flex items-start gap-2 ${isCompact ? 'p-2' : 'p-3'} border rounded-[2px] transition-colors text-left disabled:opacity-50 disabled:cursor-not-allowed group ${selectedTest?.id === test.id
                          ? 'bg-[color:var(--bg-secondary)] border-[color:var(--accent)]'
                          : 'hover:bg-[color:var(--bg-secondary)] border-transparent hover:border-[color:var(--border-color)]'
                          }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <div className="font-medium text-[color:var(--text-primary)] text-sm">
                              {test.name}
                              {testConfigs[test.id] && <span className="ml-1 text-[color:var(--accent)] font-semibold">•</span>}
                            </div>
                            <PlusIcon className="w-4 h-4 text-[color:var(--text-muted)] group-hover:text-[color:var(--accent)] transition-colors" />
                          </div>
                          {!isCompact ? (
                            <div className="text-xs text-[color:var(--text-muted)] mt-1">
                              {test.description}
                            </div>
                          ) : null}
                        </div>
                      </button>
                      {!isCompact ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedTest(test);
                            setIsConfigModalOpen(true);
                          }}
                          disabled={disabled}
                          className="p-2 hover:bg-[color:var(--bg-secondary)] rounded text-[color:var(--text-muted)] hover:text-[color:var(--accent)] disabled:opacity-50"
                          title="Настройки теста"
                          type="button"
                        >
                          <Cog6ToothIcon className="w-4 h-4" />
                        </button>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!isCompact ? (
        <div className="p-3 border-t border-[color:var(--border-color)] bg-[color:var(--bg-secondary)]">
          <div className="flex items-start gap-2 text-xs text-[color:var(--text-muted)]">
            <InformationCircleIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <p>
              {t('tests_selection_info')}
            </p>
          </div>
        </div>
      ) : null}

      {!isCompact && selectedTest && (
        <div className="p-3 border-t border-[color:var(--border-color)] bg-[color:var(--white)]">
          <WhyThisTest
            testId={selectedTest.id}
            dataProfile={effectiveDataProfile}
            level={educationLevel || 'junior'}
            defaultExpanded={true}
          />
        </div>
      )}

      {!isCompact ? (
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
      ) : null}
    </div>
  );
};

export default TestSelectionPanel;
