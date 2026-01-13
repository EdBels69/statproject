import { createInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';

// Translation resources
const resources = {
  ru: {
    translation: {
      // Common UI
      "analysis": "Анализ",
      "dataset": "Набор данных",
      "variables": "Переменные",
      "groups": "Группы",
      "time_points": "Временные точки",
      "run_analysis": "Запустить анализ",
      "save": "Сохранить",
      "cancel": "Отмена",
      "close": "Закрыть",
      "loading": "Загрузка...",
      "error": "Ошибка",
      "success": "Успешно",
      
      // Analysis types
      "analysis_type": "Тип анализа",
      "group_comparison": "Сравнение групп",
      "time_analysis": "Анализ времени",
      "correlation": "Корреляция",
      "prediction": "Прогнозирование",
      
      // Statistical methods
      "t_test": "t-тест",
      "anova": "ANOVA",
      "mixed_model": "Смешанная модель",
      "rm_anova": "Повторные измерения ANOVA",
      "friedman": "Тест Фридмана",
      "pearson": "Корреляция Пирсона",
      "spearman": "Корреляция Спирмена",
      "clustered_correlation": "Кластерный анализ корреляций",
      
      // Configuration
      "configuration": "Конфигурация",
      "basic_settings": "Основные настройки",
      "advanced_settings": "Дополнительные настройки",
      "significance_level": "Уровень значимости",
      "confidence_level": "Доверительный уровень",
      "random_slopes": "Случайные наклоны",
      "covariates": "Ковариаты",
      "correlation_method": "Метод корреляции",
      "clustering_method": "Метод кластеризации",
      "number_of_clusters": "Количество кластеров",
      "distance_threshold": "Порог расстояния",
      "show_p_values": "Показывать p-значения",
      "sphericity_correction": "Коррекция сферичности",
      
      // Results
      "results": "Результаты",
      "p_value": "p-значение",
      "effect_size": "Размер эффекта",
      "confidence_interval": "Доверительный интервал",
      "statistical_significance": "Статистическая значимость",
      "not_significant": "Не значимо",
      "significant": "Значимо",
      "highly_significant": "Высоко значимо",
      "estimated_means": "Оцененные средние",
      "fixed_effects": "Фиксированные эффекты",
      "random_effects": "Случайные эффекты",
      "model_statistics": "Статистика модели",
      "cluster_statistics": "Статистика кластеризации",
      
      // Tooltips and descriptions
      "select_variables_tooltip": "Выберите переменные для анализа",
      "select_groups_tooltip": "Выберите группирующую переменную",
      "select_time_tooltip": "Выберите переменную времени",
      "mixed_model_description": "Линейная смешанная модель для анализа повторных измерений с учетом случайных эффектов",
      "clustered_corr_description": "Иерархическая кластеризация корреляционной матрицы с переупорядочиванием переменных",
      
      // Error messages
      "no_data_selected": "Не выбраны данные для анализа",
      "invalid_configuration": "Неверная конфигурация анализа",
      "computation_error": "Ошибка вычислений",
      "timeout_error": "Таймаут вычислений",
      "memory_error": "Недостаточно памяти для анализа",

      // Test Selection Panel
      "select_test": "Выбрать тест",
      "group_comparison_desc": "Тесты для сравнения независимых групп",
      "paired_comparison_desc": "Тесты для парных измерений",
      "correlation_tests_desc": "Анализ связей между переменными",
      "advanced_tests_desc": "Продвинутые методы анализа",
      "mann_whitney_desc": "Непараметрический тест для независимых выборок",
      "t_test_desc": "Параметрический тест для независимых выборок",
      "welch_t_test_desc": "Альтернатива t-test при неравных дисперсиях",
      "anova_desc": "Однофакторный дисперсионный анализ",
      "kruskal_wallis_desc": "Непараметрическая ANOVA",
      "paired_t_test_desc": "Параметрический тест для парных выборок",
      "wilcoxon_desc": "Непараметрический тест для парных выборок",
      "friedman_test_desc": "Непараметрический тест для повторных измерений",
      "pearson_correlation_desc": "Параметрическая корреляция",
      "spearman_correlation_desc": "Непараметрическая корреляция",
      "kendall_correlation_desc": "Ранговая корреляция",
      "mixed_effects_desc": "Линейная смешанная модель",
      "clustered_correlation_desc": "Кластерная корреляция с дендрограммой",
      "rm_anova_desc": "Дисперсионный анализ с повторными измерениями",

      // Protocol Builder
      "analysis_protocol": "Протокол анализа",
      "add_test": "Добавить тест",
      "remove_test": "Удалить тест",
      "move_up": "Переместить вверх",
      "move_down": "Переместить вниз",
      "protocol_empty": "Протокол пуст. Добавьте тесты из левой панели.",
      "run_protocol": "Выполнить протокол",
      "clear_protocol": "Очистить протокол",
      "step": "Шаг",
      "no_tests_added": "Нет добавленных тестов",

      // AI Recommendations Panel
      "ai_recommendations": "Рекомендации AI",
      "get_ai_suggestions": "Получить рекомендации",
      "no_suggestions": "Нет доступных рекомендаций",
      "confidence": "Уверенность",
      "reason": "Причина",
      "add_to_protocol": "Добавить в протокол",
      "ai_suggestion_title": "AI предлагает следующий тест:",
      "ai_analyzing": "Анализ данных...",
      "ai_ready": "Рекомендации готовы",
      "ai_error": "Ошибка при получении рекомендаций",

      // Analysis Design (JAMOVI style)
      "welcome_to_analysis": "Добро пожаловать в анализ данных",
      "select_dataset_first": "Сначала выберите набор данных",
      "design_your_analysis": "Разработайте свой анализ",
      "left_panel_tests": "Доступные тесты",
      "right_panel_protocol": "Протокол анализа",
      "optional_ai": "Опционально: AI рекомендации",
      "analysis_results": "Результаты анализа",
      "view_results": "Просмотреть результаты",
      "hide_results": "Скрыть результаты"
    }
  },
  en: {
    translation: {
      // Common UI
      "analysis": "Analysis",
      "dataset": "Dataset",
      "variables": "Variables",
      "groups": "Groups",
      "time_points": "Time points",
      "run_analysis": "Run analysis",
      "save": "Save",
      "cancel": "Cancel",
      "close": "Close",
      "loading": "Loading...",
      "error": "Error",
      "success": "Success",
      
      // Analysis types
      "analysis_type": "Analysis type",
      "group_comparison": "Group comparison",
      "time_analysis": "Time analysis",
      "correlation": "Correlation",
      "prediction": "Prediction",
      
      // Statistical methods
      "t_test": "t-test",
      "anova": "ANOVA",
      "mixed_model": "Mixed model",
      "rm_anova": "Repeated measures ANOVA",
      "friedman": "Friedman test",
      "pearson": "Pearson correlation",
      "spearman": "Spearman correlation",
      "clustered_correlation": "Clustered correlation analysis",
      
      // Configuration
      "configuration": "Configuration",
      "basic_settings": "Basic settings",
      "advanced_settings": "Advanced settings",
      "significance_level": "Significance level",
      "confidence_level": "Confidence level",
      "random_slopes": "Random slopes",
      "covariates": "Covariates",
      "correlation_method": "Correlation method",
      "clustering_method": "Clustering method",
      "number_of_clusters": "Number of clusters",
      "distance_threshold": "Distance threshold",
      "show_p_values": "Show p-values",
      "sphericity_correction": "Sphericity correction",
      
      // Results
      "results": "Results",
      "p_value": "p-value",
      "effect_size": "Effect size",
      "confidence_interval": "Confidence interval",
      "statistical_significance": "Statistical significance",
      "not_significant": "Not significant",
      "significant": "Significant",
      "highly_significant": "Highly significant",
      "estimated_means": "Estimated means",
      "fixed_effects": "Fixed effects",
      "random_effects": "Random effects",
      "model_statistics": "Model statistics",
      "cluster_statistics": "Cluster statistics",
      
      // Tooltips and descriptions
      "select_variables_tooltip": "Select variables for analysis",
      "select_groups_tooltip": "Select grouping variable",
      "select_time_tooltip": "Select time variable",
      "mixed_model_description": "Linear mixed model for repeated measures analysis with random effects",
      "clustered_corr_description": "Hierarchical clustering of correlation matrix with variable reordering",
      
      // Error messages
      "no_data_selected": "No data selected for analysis",
      "invalid_configuration": "Invalid analysis configuration",
      "computation_error": "Computation error",
      "timeout_error": "Computation timeout",
      "memory_error": "Insufficient memory for analysis",

      // Test Selection Panel
      "select_test": "Select test",
      "group_comparison_desc": "Tests for comparing independent groups",
      "paired_comparison_desc": "Tests for paired measurements",
      "correlation_tests_desc": "Analysis of relationships between variables",
      "advanced_tests_desc": "Advanced analysis methods",
      "mann_whitney_desc": "Non-parametric test for independent samples",
      "t_test_desc": "Parametric test for independent samples",
      "welch_t_test_desc": "Alternative to t-test for unequal variances",
      "anova_desc": "One-way analysis of variance",
      "kruskal_wallis_desc": "Non-parametric ANOVA",
      "paired_t_test_desc": "Parametric test for paired samples",
      "wilcoxon_desc": "Non-parametric test for paired samples",
      "friedman_test_desc": "Non-parametric test for repeated measures",
      "pearson_correlation_desc": "Parametric correlation",
      "spearman_correlation_desc": "Non-parametric correlation",
      "kendall_correlation_desc": "Rank correlation",
      "mixed_effects_desc": "Linear mixed model",
      "clustered_correlation_desc": "Clustered correlation with dendrogram",
      "rm_anova_desc": "Repeated measures analysis of variance",

      // Protocol Builder
      "analysis_protocol": "Analysis Protocol",
      "add_test": "Add test",
      "remove_test": "Remove test",
      "move_up": "Move up",
      "move_down": "Move down",
      "protocol_empty": "Protocol is empty. Add tests from the left panel.",
      "run_protocol": "Run protocol",
      "clear_protocol": "Clear protocol",
      "step": "Step",
      "no_tests_added": "No tests added",

      // AI Recommendations Panel
      "ai_recommendations": "AI Recommendations",
      "get_ai_suggestions": "Get suggestions",
      "no_suggestions": "No suggestions available",
      "confidence": "Confidence",
      "reason": "Reason",
      "add_to_protocol": "Add to protocol",
      "ai_suggestion_title": "AI suggests the following test:",
      "ai_analyzing": "Analyzing data...",
      "ai_ready": "Suggestions ready",
      "ai_error": "Error getting suggestions",

      // Analysis Design (JAMOVI style)
      "welcome_to_analysis": "Welcome to data analysis",
      "select_dataset_first": "Please select a dataset first",
      "design_your_analysis": "Design your analysis",
      "left_panel_tests": "Available tests",
      "right_panel_protocol": "Analysis protocol",
      "optional_ai": "Optional: AI recommendations",
      "analysis_results": "Analysis results",
      "view_results": "View results",
      "hide_results": "Hide results"
    }
  }
};

// Create i18n instance
const i18n = createInstance();

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: 'ru', // default language
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false // React already protects from XSS
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage']
    }
  });

export default i18n;