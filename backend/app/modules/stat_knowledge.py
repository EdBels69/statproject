"""
Statistical Knowledge Base for Contextual Education.

Provides explanations at different levels (junior/mid/senior) for:
- Statistical terms (p-value, effect size, power, etc.)
- Test selection rationale
- Assumptions and their implications
- Common mistakes
- Academic citations for methodology

Key References for Methodological Rigor:
---------------------------------------
1. de Smith, M. J. (2018). Statistical Analysis Handbook. 
   A comprehensive online reference: https://www.statsref.com/
   
2. Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences (2nd ed.).
   Lawrence Erlbaum Associates. [Effect size conventions: d=0.2, 0.5, 0.8]
   
3. Field, A. (2018). Discovering Statistics Using IBM SPSS Statistics (5th ed.).
   SAGE Publications. [Accessible explanations with practical examples]
   
4. Lakens, D. (2013). Calculating and reporting effect sizes to facilitate cumulative 
   science: a practical primer for t-tests and ANOVAs. Frontiers in Psychology, 4, 863.
   https://doi.org/10.3389/fpsyg.2013.00863
   
5. Delacre, M., Lakens, D., & Leys, C. (2017). Why Psychologists Should by Default Use 
   Welch's t-test Instead of Student's t-test. International Review of Social Psychology.
   https://doi.org/10.5334/irsp.82
   
6. Wasserstein, R. L., & Lazar, N. A. (2016). The ASA Statement on p-Values: 
   Context, Process, and Purpose. The American Statistician, 70(2), 129-133.
   https://doi.org/10.1080/00031305.2016.1154108
   
7. American Psychological Association. (2020). Publication Manual of the APA (7th ed.).
   [Reporting standards for statistical results]

8. Faul, F., Erdfelder, E., Lang, A.-G., & Buchner, A. (2007). G*Power 3: 
   A flexible statistical power analysis program. Behavior Research Methods, 39, 175-191.
   [Power analysis methodology]

9. Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate.
   Journal of the Royal Statistical Society B, 57(1), 289-300.
   [FDR correction for multiple comparisons]

10. Tukey, J. W. (1977). Exploratory Data Analysis. Addison-Wesley.
    [Box plots, data visualization principles]

Usage:
    from app.modules.stat_knowledge import get_explanation, get_test_rationale
    
    explanation = get_explanation("p_value", level="junior")
    rationale = get_test_rationale("t_test_ind", data_profile)
    
    # Get citation for academic writing
    citation = get_citation("cohens_d")
"""

from typing import Dict, List, Optional, Any


# =============================================================================
# ACADEMIC REFERENCES (for citation in reports and papers)
# =============================================================================

ACADEMIC_REFERENCES: Dict[str, Dict[str, str]] = {
    "effect_size_conventions": {
        "citation": "Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences (2nd ed.). Lawrence Erlbaum Associates.",
        "bibtex": "@book{cohen1988,author={Cohen, Jacob},title={Statistical Power Analysis for the Behavioral Sciences},edition={2nd},publisher={Lawrence Erlbaum Associates},year={1988}}",
        "note": "Conventions for effect size interpretation: d=0.2 (small), d=0.5 (medium), d=0.8 (large)"
    },
    "welch_default": {
        "citation": "Delacre, M., Lakens, D., & Leys, C. (2017). Why Psychologists Should by Default Use Welch's t-test Instead of Student's t-test. International Review of Social Psychology, 30(1), 92-101.",
        "doi": "10.5334/irsp.82",
        "note": "Recommends Welch's t-test as default due to better performance under variance heterogeneity"
    },
    "p_value_statement": {
        "citation": "Wasserstein, R. L., & Lazar, N. A. (2016). The ASA Statement on p-Values: Context, Process, and Purpose. The American Statistician, 70(2), 129-133.",
        "doi": "10.1080/00031305.2016.1154108",
        "note": "Official ASA guidance on p-value interpretation and reporting"
    },
    "fdr_correction": {
        "citation": "Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing. Journal of the Royal Statistical Society B, 57(1), 289-300.",
        "note": "FDR procedure for multiple comparison correction"
    },
    "effect_size_primer": {
        "citation": "Lakens, D. (2013). Calculating and reporting effect sizes to facilitate cumulative science: a practical primer for t-tests and ANOVAs. Frontiers in Psychology, 4, 863.",
        "doi": "10.3389/fpsyg.2013.00863",
        "note": "Practical guide for calculating and reporting effect sizes"
    },
    "power_analysis": {
        "citation": "Faul, F., Erdfelder, E., Lang, A.-G., & Buchner, A. (2007). G*Power 3: A flexible statistical power analysis program. Behavior Research Methods, 39, 175-191.",
        "note": "Reference for power analysis methodology and G*Power software"
    },
    "apa_reporting": {
        "citation": "American Psychological Association. (2020). Publication Manual of the American Psychological Association (7th ed.). APA.",
        "note": "Standard for reporting statistical results in social sciences"
    },
    "de_smith_handbook": {
        "citation": "de Smith, M. J. (2018). Statistical Analysis Handbook. Drumlin Security Ltd.",
        "url": "https://www.statsref.com/",
        "note": "Comprehensive statistical reference with formulas and explanations"
    },
    "field_spss": {
        "citation": "Field, A. (2018). Discovering Statistics Using IBM SPSS Statistics (5th ed.). SAGE Publications.",
        "note": "Comprehensive statistics textbook with accessible explanations"
    },
    "tukey_eda": {
        "citation": "Tukey, J. W. (1977). Exploratory Data Analysis. Addison-Wesley.",
        "note": "Foundational work on data visualization and exploratory analysis"
    },
    "normality_tests": {
        "citation": "Shapiro, S. S., & Wilk, M. B. (1965). An analysis of variance test for normality. Biometrika, 52(3-4), 591-611.",
        "note": "Original Shapiro-Wilk test paper"
    },
    "levene_test": {
        "citation": "Levene, H. (1960). Robust tests for equality of variances. In Contributions to Probability and Statistics (pp. 278-292). Stanford University Press.",
        "note": "Original Levene's test for homogeneity of variances"
    },
    "mann_whitney": {
        "citation": "Mann, H. B., & Whitney, D. R. (1947). On a test of whether one of two random variables is stochastically larger than the other. The Annals of Mathematical Statistics, 18(1), 50-60.",
        "note": "Original Mann-Whitney U test paper"
    },
    "kruskal_wallis": {
        "citation": "Kruskal, W. H., & Wallis, W. A. (1952). Use of ranks in one-criterion variance analysis. Journal of the American Statistical Association, 47(260), 583-621.",
        "note": "Original Kruskal-Wallis test paper"
    },
    "bonferroni": {
        "citation": "Dunn, O. J. (1961). Multiple comparisons among means. Journal of the American Statistical Association, 56(293), 52-64.",
        "note": "Bonferroni correction for multiple comparisons"
    },
    "hedges_g": {
        "citation": "Hedges, L. V. (1981). Distribution theory for Glass's estimator of effect size and related estimators. Journal of Educational Statistics, 6(2), 107-128.",
        "note": "Hedges' g correction for small sample bias in Cohen's d"
    }
}


# =============================================================================
# STATISTICAL TERMS KNOWLEDGE BASE
# =============================================================================

STAT_TERMS: Dict[str, Dict[str, Any]] = {
    
    # -------------------------------------------------------------------------
    # Core Concepts
    # -------------------------------------------------------------------------
    
    "p_value": {
        "term": "P-value",
        "term_ru": "P-значение",
        "definition": {
            "junior": "Чем меньше p-value, тем сильнее доказательства против нулевой гипотезы. Обычно сравнивают с 0.05.",
            "mid": "Вероятность получить статистику ≥ наблюдаемой при условии, что H0 верна. Зависит от размера выборки.",
            "senior": "P(data|H0). Не путать с P(H0|data). При большом n даже trivial эффекты дают p < 0.05. Рассматривать вместе с effect size и CI."
        },
        "common_mistakes": [
            "p-value ≠ вероятность что H0 верна",
            "p < 0.05 ≠ практическая значимость",
            "p > 0.05 ≠ 'эффекта нет' (может быть недостаток мощности)"
        ],
        "what_to_check": ["effect_size", "confidence_interval", "power"],
        "emoji": "📊"
    },
    
    "effect_size": {
        "term": "Effect Size",
        "term_ru": "Размер эффекта",
        "definition": {
            "junior": "Насколько большой эффект мы нашли. Не зависит от размера выборки.",
            "mid": "Стандартизированная мера силы эффекта. Cohen's d = разница средних / pooled SD.",
            "senior": "Позволяет сравнивать результаты между исследованиями. Для метаанализа важнее p-value."
        },
        "thresholds": {
            "cohens_d": {
                "negligible": {"max": 0.2, "label": "незначительный"},
                "small": {"max": 0.5, "label": "малый"},
                "medium": {"max": 0.8, "label": "средний"},
                "large": {"min": 0.8, "label": "большой"}
            },
            "eta_squared": {
                "small": {"max": 0.06, "label": "малый"},
                "medium": {"max": 0.14, "label": "средний"},
                "large": {"min": 0.14, "label": "большой"}
            },
            "partial_eta_squared": {
                "small": {"max": 0.06, "label": "малый"},
                "medium": {"max": 0.14, "label": "средний"},
                "large": {"min": 0.14, "label": "большой"}
            },
            "r": {
                "weak": {"max": 0.3, "label": "слабая связь"},
                "moderate": {"max": 0.5, "label": "умеренная связь"},
                "strong": {"min": 0.5, "label": "сильная связь"}
            },
            "rho": {
                "weak": {"max": 0.3, "label": "слабая связь"},
                "moderate": {"max": 0.5, "label": "умеренная связь"},
                "strong": {"min": 0.5, "label": "сильная связь"}
            },
            "cramers_v": {
                "small": {"max": 0.1, "label": "малый"},
                "medium": {"max": 0.3, "label": "средний"},
                "large": {"min": 0.5, "label": "большой"}
            },
            "epsilon_squared": {
                "small": {"max": 0.06, "label": "малый"},
                "medium": {"max": 0.14, "label": "средний"},
                "large": {"min": 0.14, "label": "большой"}
            },
            "rank_biserial": {
                "small": {"max": 0.3, "label": "малый"},
                "medium": {"max": 0.5, "label": "средний"},
                "large": {"min": 0.5, "label": "большой"}
            },
            "auc": {
                "poor": {"max": 0.6, "label": "слабая дискриминация"},
                "fair": {"max": 0.7, "label": "удовлетворительно"},
                "good": {"max": 0.8, "label": "хорошо"},
                "excellent": {"min": 0.9, "label": "отлично"}
            }
        },
        "common_mistakes": [
            "Игнорирование effect size при significant p-value",
            "Использование только p-value для выводов"
        ],
        "emoji": "📏"
    },
    
    "power": {
        "term": "Statistical Power",
        "term_ru": "Мощность теста",
        "definition": {
            "junior": "Вероятность обнаружить эффект, если он реально существует. Рекомендуется ≥ 80%.",
            "mid": "Power = 1 - β, где β — вероятность ошибки II рода (пропустить реальный эффект). Зависит от n, effect size, alpha.",
            "senior": "При power = 0.8 и реальном эффекте — 20% шанс получить p > 0.05. Post-hoc power analysis имеет ограничения."
        },
        "recommendations": {
            "low": {"max": 0.5, "message": "Критически низкая мощность. Увеличьте выборку."},
            "insufficient": {"max": 0.8, "message": "Недостаточная мощность. Рекомендуется ≥ 80%."},
            "adequate": {"max": 0.95, "message": "Адекватная мощность."},
            "high": {"min": 0.95, "message": "Высокая мощность. Возможно, выборка избыточна."}
        },
        "emoji": "⚡"
    },
    
    "alpha": {
        "term": "Alpha Level",
        "term_ru": "Уровень значимости",
        "definition": {
            "junior": "Порог для принятия решения. Обычно 0.05 (5%). Если p < alpha — результат значимый.",
            "mid": "Вероятность ошибки I рода (ложноположительный результат). При alpha = 0.05 в 5% случаев отвергаем верную H0.",
            "senior": "При множественных сравнениях нужна коррекция (Bonferroni, FDR). В некоторых областях используют alpha = 0.005."
        },
        "emoji": "🎯"
    },
    
    "confidence_interval": {
        "term": "Confidence Interval",
        "term_ru": "Доверительный интервал",
        "definition": {
            "junior": "Диапазон, в котором с 95% уверенностью находится истинное значение параметра.",
            "mid": "При повторении эксперимента 100 раз, ~95 CI из 100 захватят истинное значение.",
            "senior": "CI для effect size важнее CI для mean. Если CI не включает 0 — эффект значим на данном alpha."
        },
        "emoji": "📐"
    },

    "type_i_error": {
        "term": "Type I Error",
        "term_ru": "Ошибка I рода",
        "definition": {
            "junior": "Ложноположительный результат: решили, что эффект есть, хотя его нет.",
            "mid": "Вероятность ошибки I рода равна α (уровню значимости).",
            "senior": "Контроль Type I Error — часть дизайна. При множественных проверках без поправки общий риск растёт."
        },
        "what_to_check": ["alpha", "multiple_comparison"],
        "emoji": "🎯"
    },

    "type_ii_error": {
        "term": "Type II Error",
        "term_ru": "Ошибка II рода",
        "definition": {
            "junior": "Ложноотрицательный результат: пропустили реальный эффект.",
            "mid": "Вероятность ошибки II рода — β. Мощность = 1 − β.",
            "senior": "Снижается при большем n и/или большем эффекте. Нельзя «починить» β после факта без увеличения данных."
        },
        "what_to_check": ["power", "sample_size"],
        "emoji": "⚡"
    },

    "beta": {
        "term": "Beta",
        "term_ru": "β (бета)",
        "definition": {
            "junior": "β — шанс пропустить эффект (ошибка II рода).",
            "mid": "β = 1 − power. Например power=0.80 → β=0.20.",
            "senior": "В power analysis обычно задают power, а не β напрямую."
        },
        "what_to_check": ["power"],
        "emoji": "⚡"
    },

    "one_tailed": {
        "term": "One-tailed test",
        "term_ru": "Односторонний тест",
        "definition": {
            "junior": "Проверяем эффект только в одном направлении (только ↑ или только ↓).",
            "mid": "Даёт меньший порог для p в выбранном направлении, но запрещает считать значимым эффект в обратную сторону.",
            "senior": "Выбор должен быть до анализа и обоснован. Если направление заранее не гарантировано — используйте двусторонний."
        },
        "common_mistakes": ["Выбирать односторонний после того, как увидели данные"],
        "emoji": "➡️"
    },

    "two_tailed": {
        "term": "Two-tailed test",
        "term_ru": "Двусторонний тест",
        "definition": {
            "junior": "Проверяем эффект в обе стороны (↑ или ↓).",
            "mid": "Стандарт по умолчанию: контролирует ошибки при любом направлении эффекта.",
            "senior": "Честнее, когда направление заранее не закреплено. В power analysis требует большего n, чем one-tailed при прочих равных."
        },
        "emoji": "↔️"
    },

    "sample_size": {
        "term": "Sample Size",
        "term_ru": "Размер выборки (n)",
        "definition": {
            "junior": "Сколько наблюдений нужно, чтобы с высокой вероятностью найти эффект.",
            "mid": "n зависит от effect size, α, power и дизайна (баланс групп, повторные измерения, кластеры).",
            "senior": "Планируйте n под первичную гипотезу. Делайте sensitivity analysis (коридор по эффекту/SD/dropout)."
        },
        "what_to_check": ["effect_size", "alpha", "power", "multiple_comparison"],
        "emoji": "🧮"
    },

    "allocation_ratio": {
        "term": "Allocation ratio",
        "term_ru": "Соотношение групп (N2/N1)",
        "definition": {
            "junior": "Как делим участников по группам: 1:1, 1:2 и т.д.",
            "mid": "Дисбаланс увеличивает общий n при фиксированном power, особенно если редкая группа маленькая.",
            "senior": "Если одна группа дороже/редче — дисбаланс может быть оправдан, но закладывайте рост n и анализируйте причину."
        },
        "emoji": "⚖️"
    },

    "dropout": {
        "term": "Dropout / Attrition",
        "term_ru": "Выбывание (dropout)",
        "definition": {
            "junior": "Часть людей не дойдёт до анализа (потеря данных).",
            "mid": "Если нужно n для анализа, то набрать обычно нужно больше: n_recruit = n / (1 − dropout).",
            "senior": "Dropout часто неслучаен. Планируйте стратегии работы с пропусками и критерии включения заранее."
        },
        "formula": "n_recruit = n_analyzed / (1 − dropout)",
        "emoji": "🧷"
    },

    "minimal_detectable_effect": {
        "term": "Minimal Detectable Effect",
        "term_ru": "Минимально обнаружимый эффект (MDE)",
        "definition": {
            "junior": "Самый маленький эффект, который вы хотите уметь обнаружить.",
            "mid": "Если заложить слишком маленький эффект — n вырастет сильно. Если слишком большой — велик риск «не увидеть» реальность.",
            "senior": "Опирайтесь на клиническую значимость (MCID), литературу и пилот. Делайте диапазон (sensitivity)."
        },
        "what_to_check": ["effect_size", "confidence_interval"],
        "emoji": "📏"
    },

    "sensitivity_analysis": {
        "term": "Sensitivity analysis",
        "term_ru": "Сенситивити-анализ",
        "definition": {
            "junior": "Проверка «а если параметры другие?»",
            "mid": "Пересчитывают n для нескольких сценариев: эффект меньше/больше, dropout выше, α строже.",
            "senior": "Лучший способ не «заблудиться»: фиксируйте базовый сценарий и 2–4 стресс-сценария с выводом по рискам."
        },
        "emoji": "🧭"
    },

    "standard_deviation": {
        "term": "Standard deviation",
        "term_ru": "Стандартное отклонение (SD)",
        "definition": {
            "junior": "Показывает, насколько значения разбросаны вокруг среднего.",
            "mid": "Для расчёта n по средним SD критичен: завысите SD — получите больший n. Занижите — риск недомощности.",
            "senior": "SD берите из пилота, прошлых исследований или консервативной оценки. Учитывайте, что SD зависит от популяции и измерения."
        },
        "emoji": "📐"
    },

    "delta": {
        "term": "Delta",
        "term_ru": "Δ (разница)",
        "definition": {
            "junior": "Разница между группами/условиями, которую вы ожидаете.",
            "mid": "В расчёте по средним часто удобнее задавать Δ и SD, а не d.",
            "senior": "Δ лучше якорить на клинической значимости (MCID) и измеримой шкале."
        },
        "emoji": "Δ"
    },
    
    # -------------------------------------------------------------------------
    # Assumptions
    # -------------------------------------------------------------------------
    
    "normality": {
        "term": "Normality Assumption",
        "term_ru": "Допущение нормальности",
        "definition": {
            "junior": "Данные должны быть примерно нормально распределены для t-test и ANOVA.",
            "mid": "Благодаря ЦПТ, при n > 30 распределение средних приближается к нормальному. Для малых n — проверяйте Shapiro-Wilk.",
            "senior": "T-test устойчив к нарушениям нормальности при равных n и симметричных распределениях. Критичнее для малых выборок."
        },
        "how_to_check": "Shapiro-Wilk test (p > 0.05 → нормальность), Q-Q plot",
        "if_violated": "Используйте непараметрические тесты (Mann-Whitney, Kruskal-Wallis) или bootstrap",
        "emoji": "📈"
    },
    
    "homogeneity": {
        "term": "Homogeneity of Variance",
        "term_ru": "Гомогенность дисперсий",
        "definition": {
            "junior": "Дисперсии в сравниваемых группах должны быть примерно одинаковыми.",
            "mid": "Levene's test проверяет равенство дисперсий. При нарушении — используйте Welch's correction.",
            "senior": "ANOVA устойчив к нарушениям при равных n. При неравных n и гетероскедастичности — Welch ANOVA или Games-Howell post-hoc."
        },
        "how_to_check": "Levene's test (p > 0.05 → дисперсии равны)",
        "if_violated": "Welch's t-test или Welch's ANOVA",
        "emoji": "⚖️"
    },
    
    "independence": {
        "term": "Independence of Observations",
        "term_ru": "Независимость наблюдений",
        "definition": {
            "junior": "Каждое наблюдение не должно зависеть от других.",
            "mid": "Нарушается при repeated measures, кластерных данных, временных рядах.",
            "senior": "Для зависимых данных — paired tests, mixed models, GEE. При сетевых эффектах — cluster-robust SE."
        },
        "examples_violated": [
            "Несколько измерений от одного пациента",
            "Студенты из одного класса",
            "Временные ряды"
        ],
        "emoji": "🔗"
    },
    
    "linearity": {
        "term": "Linearity",
        "term_ru": "Линейность",
        "definition": {
            "junior": "Связь между переменными должна быть примерно линейной.",
            "mid": "Для регрессии важна линейность связи предикторов с исходом или с логит-преобразованием.",
            "senior": "Проверяйте остатки и добавляйте нелинейные члены (полиномы, сплайны), если нужно."
        },
        "how_to_check": "График остатков, partial residual plots, Box-Tidwell test",
        "if_violated": "Используйте нелинейные модели, трансформации или сплайны",
        "emoji": "📈"
    },
    
    "homoscedasticity": {
        "term": "Homoscedasticity",
        "term_ru": "Гомоскедастичность",
        "definition": {
            "junior": "Разброс остатков должен быть примерно одинаковым по всему диапазону.",
            "mid": "Гетероскедастичность искажает SE и p-value в регрессии.",
            "senior": "Используйте robust SE, трансформации или модели с гетероскедастичностью."
        },
        "how_to_check": "Residuals vs fitted, Breusch-Pagan test",
        "if_violated": "Robust SE, трансформации, взвешенная регрессия",
        "emoji": "⚖️"
    },
    
    "monotonic_relationship": {
        "term": "Monotonic Relationship",
        "term_ru": "Монотонная связь",
        "definition": {
            "junior": "Когда одна переменная растёт, другая либо растёт, либо падает, но не меняет направление.",
            "mid": "Требуется для корреляции Спирмена.",
            "senior": "При немонотонности лучше использовать нелинейные меры зависимости."
        },
        "how_to_check": "Scatterplot, loess smoothing",
        "if_violated": "Используйте нелинейные меры или сегментируйте данные",
        "emoji": "📉"
    },
    
    "expected_count_>=5": {
        "term": "Expected Count ≥ 5",
        "term_ru": "Ожидаемые частоты ≥ 5",
        "definition": {
            "junior": "В таблице частот ожидаемые значения не должны быть слишком малы.",
            "mid": "Для χ² при ожидаемых < 5 результат искажается.",
            "senior": "При малых ожидаемых используйте Fisher's exact или объединение категорий."
        },
        "emoji": "🔢"
    },
    
    "sphericity": {
        "term": "Sphericity",
        "term_ru": "Сферичность",
        "definition": {
            "junior": "Разницы между всеми парами повторных измерений должны иметь одинаковую дисперсию.",
            "mid": "Проверяется тестом Мочли. При нарушении нужны корректировки.",
            "senior": "Используйте Greenhouse-Geisser или Huynh-Feldt корректировки."
        },
        "how_to_check": "Mauchly's test",
        "if_violated": "Greenhouse-Geisser или Huynh-Feldt корректировка",
        "emoji": "🧭"
    },
    
    "multicollinearity": {
        "term": "Multicollinearity",
        "term_ru": "Мультиколлинеарность",
        "definition": {
            "junior": "Предикторы слишком похожи друг на друга.",
            "mid": "Высокая коллинеарность раздувает SE и делает коэффициенты нестабильными.",
            "senior": "Проверяйте VIF и удаляйте/объединяйте предикторы."
        },
        "how_to_check": "VIF, корреляционная матрица",
        "if_violated": "Сократить предикторы, регуляризация",
        "emoji": "🧩"
    },
    
    "proportional_hazards": {
        "term": "Proportional Hazards",
        "term_ru": "Пропорциональные риски",
        "definition": {
            "junior": "Отношение рисков между группами должно быть постоянным во времени.",
            "mid": "Ключевое допущение для моделей выживаемости типа Cox.",
            "senior": "Проверяйте Schoenfeld residuals или time-varying effects."
        },
        "how_to_check": "Schoenfeld residuals",
        "if_violated": "Временные взаимодействия или стратификация",
        "emoji": "⏱️"
    },
    
    # -------------------------------------------------------------------------
    # Effect Size Types
    # -------------------------------------------------------------------------
    
    "cohens_d": {
        "term": "Cohen's d",
        "term_ru": "d Коэна",
        "definition": {
            "junior": "Разница между группами в единицах стандартного отклонения.",
            "mid": "d = (M1 - M2) / SD_pooled. Интерпретация: 0.2 малый, 0.5 средний, 0.8 большой.",
            "senior": "Hedges' g — коррекция для малых выборок. Glass's Δ — когда SD групп различаются существенно."
        },
        "formula": "d = (M₁ - M₂) / SD_pooled",
        "practical_meaning": {
            0.2: "~58% группы A выше среднего группы B",
            0.5: "~69% группы A выше среднего группы B",
            0.8: "~79% группы A выше среднего группы B"
        },
        "emoji": "📊"
    },
    
    "eta_squared": {
        "term": "Eta-squared (η²)",
        "term_ru": "Эта-квадрат",
        "definition": {
            "junior": "Доля дисперсии, объясняемая фактором. Аналог R² для ANOVA.",
            "mid": "η² = SS_between / SS_total. Partial η² учитывает только relevant variance.",
            "senior": "η² переоценивает effect в выборке. ω² — менее смещённая оценка для популяции."
        },
        "formula": "η² = SS_between / SS_total",
        "emoji": "📐"
    },
    
    "epsilon_squared": {
        "term": "Epsilon-squared (ε²)",
        "term_ru": "Эпсилон-квадрат",
        "definition": {
            "junior": "Оценка размера эффекта для непараметрических тестов.",
            "mid": "Часто используется для Kruskal-Wallis.",
            "senior": "Интерпретируется похоже на η²."
        },
        "emoji": "📐"
    },
    
    "cramers_v": {
        "term": "Cramer's V",
        "term_ru": "V Крамера",
        "definition": {
            "junior": "Сила связи между категориальными переменными.",
            "mid": "От 0 до 1, ближе к 1 — сильнее связь.",
            "senior": "Зависит от размера таблицы; интерпретация должна учитывать df."
        },
        "emoji": "📊"
    },
    
    "rank_biserial": {
        "term": "Rank-biserial correlation",
        "term_ru": "Рангово-бисериальная корреляция",
        "definition": {
            "junior": "Размер эффекта для Mann-Whitney и Wilcoxon.",
            "mid": "Показывает вероятность, что наблюдение из группы A больше, чем из группы B.",
            "senior": "Интерпретируется аналогично r."
        },
        "emoji": "📈"
    },
    
    "rho": {
        "term": "Spearman's ρ",
        "term_ru": "Спирмен ρ",
        "definition": {
            "junior": "Сила монотонной связи между переменными.",
            "mid": "Корреляция по рангам, устойчива к выбросам.",
            "senior": "Интерпретация по шкале r."
        },
        "emoji": "📈"
    },
    
    "auc": {
        "term": "AUC",
        "term_ru": "Площадь под ROC-кривой",
        "definition": {
            "junior": "Насколько хорошо модель различает классы.",
            "mid": "Минимальная (0.5) — как случайно, 1.0 — идеально.",
            "senior": "Интерпретация зависит от контекста и клинической значимости."
        },
        "emoji": "🎯"
    },
    
    "odds_ratio": {
        "term": "Odds Ratio",
        "term_ru": "Отношение шансов",
        "definition": {
            "junior": "Во сколько раз шансы события выше/ниже при изменении фактора.",
            "mid": "OR > 1 — повышение шансов, OR < 1 — снижение.",
            "senior": "Интерпретируйте вместе с CI и базовой частотой."
        },
        "emoji": "⚖️"
    },

    "multiple_comparison": {
        "term": "Multiple Comparison Correction",
        "term_ru": "Коррекция на множественные сравнения",
        "definition": {
            "junior": "Когда делаешь много тестов, шанс ложной находки растёт. Коррекция это исправляет.",
            "mid": "При 20 тестах с α=0.05 ожидается 1 ложноположительный. FDR контролирует долю ложных среди значимых.",
            "senior": "FWER vs FDR. Bonferroni: α/n, очень консервативен. BH: step-up, контролирует E[V/R]. BY: для зависимых тестов."
        },
        "methods": {
            "bonferroni": {
                "name": "Bonferroni",
                "formula": "α_adj = α / n",
                "description_ru": "Самый строгий. Делит α на число тестов.",
                "when_to_use": "Когда ложноположительный результат недопустим"
            },
            "holm": {
                "name": "Holm-Bonferroni",
                "description_ru": "Чуть мягче Bonferroni. Step-down процедура.",
                "when_to_use": "Когда Bonferroni слишком консервативен"
            },
            "bh": {
                "name": "Benjamini-Hochberg",
                "description_ru": "FDR контроль. Контролирует долю ложных находок.",
                "when_to_use": "Исследовательский анализ, много тестов"
            },
            "by": {
                "name": "Benjamini-Yekutieli",
                "description_ru": "FDR для зависимых тестов.",
                "when_to_use": "Когда тесты коррелируют между собой"
            },
            "bky": {
                "name": "Benjamini-Krieger-Yekutieli (two-stage)",
                "description_ru": "Двухшаговая FDR-процедура, часто мощнее BH при неизвестных/неравных дисперсиях и в поисковых анализах.",
                "when_to_use": "Поисковые исследования, много тестов, хочется больше мощности чем BH"
            }
        },
        "recommendation": "Для исследовательского анализа: BH-FDR. Для подтверждающего: Bonferroni или Holm.",
        "common_mistakes": [
            "Не корректировать при множественных сравнениях",
            "Использовать Bonferroni когда BH достаточно",
            "Путать FWER и FDR"
        ],
        "emoji": "🔢"
    }
}


# =============================================================================
# TEST SELECTION RATIONALE
# =============================================================================

TEST_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    
    "t_test_ind": {
        "name": "Independent Samples t-test",
        "name_ru": "T-test для независимых выборок",
        "when_to_use": [
            "2 независимые группы",
            "Numeric outcome (непрерывная переменная)",
            "Нормальное распределение (или n > 30)",
            "Примерно равные дисперсии"
        ],
        "assumptions": ["normality", "homogeneity", "independence"],
        "why_it_works": {
            "junior": "Сравнивает средние двух групп и проверяет, значима ли разница.",
            "mid": "Использует t-распределение. При n → ∞ приближается к z-test благодаря ЦПТ.",
            "senior": "Pooled variance estimate предполагает σ₁ = σ₂. При нарушении — Welch's correction с Satterthwaite df."
        },
        "alternatives": {
            "non_normal": {"test": "mann_whitney", "reason": "если данные ненормальные"},
            "unequal_variance": {"test": "t_test_welch", "reason": "если дисперсии различаются"},
            "small_n": {"test": "mann_whitney", "reason": "если n < 15 и ненормально"}
        },
        "effect_size": "cohens_d",
        "emoji": "📊"
    },
    
    "mann_whitney": {
        "name": "Mann-Whitney U test",
        "name_ru": "U-тест Манна-Уитни",
        "when_to_use": [
            "2 независимые группы",
            "Ненормальное распределение",
            "Ordinal или skewed numeric данные"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Сравнивает ранги (порядок) вместо средних. Не требует нормальности.",
            "mid": "Тестирует H0: P(X > Y) = 0.5. Эквивалентен Wilcoxon rank-sum test.",
            "senior": "Чувствителен к различиям в форме распределений. При разных формах интерпретация ≠ 'разница медиан'."
        },
        "effect_size": "rank_biserial",
        "emoji": "📊"
    },
    
    "anova": {
        "name": "One-way ANOVA",
        "name_ru": "Однофакторный дисперсионный анализ",
        "when_to_use": [
            "3+ независимых групп",
            "Нормальное распределение",
            "Равные дисперсии"
        ],
        "assumptions": ["normality", "homogeneity", "independence"],
        "why_it_works": {
            "junior": "Проверяет, есть ли различия между группами. Если p < 0.05 — хотя бы одна пара различается.",
            "mid": "F = MS_between / MS_within. Сравнивает вариацию между группами с вариацией внутри групп.",
            "senior": "ANOVA = special case of linear regression. Robust к нарушениям нормальности при равных n."
        },
        "post_hoc": ["tukey", "bonferroni", "holm"],
        "alternatives": {
            "unequal_variance": {"test": "anova_welch", "reason": "если дисперсии различаются"},
            "non_normal": {"test": "kruskal", "reason": "если данные ненормальные"}
        },
        "effect_size": "eta_squared",
        "emoji": "📈"
    },
    
    "chi_square": {
        "name": "Chi-squared test",
        "name_ru": "Хи-квадрат тест",
        "when_to_use": [
            "Две категориальные переменные",
            "Таблица частот",
            "Expected count ≥ 5 в каждой ячейке"
        ],
        "assumptions": ["independence", "expected_count_>=5"],
        "why_it_works": {
            "junior": "Проверяет связь между двумя категориальными переменными.",
            "mid": "χ² = Σ(O - E)² / E. Сравнивает наблюдаемые частоты с ожидаемыми при независимости.",
            "senior": "При 2×2 — Yates correction или Fisher's exact. При large samples — χ² robust."
        },
        "alternatives": {
            "small_sample": {"test": "fisher", "reason": "если expected count < 5"}
        },
        "effect_size": "cramers_v",
        "emoji": "📊"
    },
    
    "pearson": {
        "name": "Pearson correlation",
        "name_ru": "Корреляция Пирсона",
        "when_to_use": [
            "Две непрерывные переменные",
            "Линейная связь",
            "Bivariate normality"
        ],
        "assumptions": ["normality", "linearity", "homoscedasticity"],
        "why_it_works": {
            "junior": "Измеряет силу линейной связи от -1 до +1.",
            "mid": "r = cov(X,Y) / (SD_X × SD_Y). Чувствителен к outliers.",
            "senior": "r² = доля объяснённой дисперсии. Не улавливает нелинейные связи."
        },
        "alternatives": {
            "non_linear": {"test": "spearman", "reason": "для монотонных нелинейных связей"},
            "outliers": {"test": "spearman", "reason": "более robust к выбросам"}
        },
        "effect_size": "r",
        "emoji": "📈"
    },
    
    "spearman": {
        "name": "Spearman correlation",
        "name_ru": "Корреляция Спирмена",
        "when_to_use": [
            "Ordinal данные",
            "Ненормальное распределение",
            "Монотонная (не обязательно линейная) связь"
        ],
        "assumptions": ["monotonic_relationship"],
        "why_it_works": {
            "junior": "Корреляция по рангам. Более устойчив к выбросам.",
            "mid": "ρ = Pearson r для рангов. Улавливает монотонные нелинейные связи.",
            "senior": "При tied ranks — коррекция. Для ordinal данных предпочтительнее Pearson."
        },
        "effect_size": "rho",
        "emoji": "📈"
    },
    
    "t_test_one": {
        "name": "One-sample t-test",
        "name_ru": "T-test для одной выборки",
        "when_to_use": [
            "Одна группа",
            "Сравнение среднего с заданным значением",
            "Нормальное распределение (или n > 30)"
        ],
        "assumptions": ["normality", "independence"],
        "why_it_works": {
            "junior": "Проверяет, отличается ли среднее от заданного значения.",
            "mid": "Использует t-распределение для среднего одной выборки.",
            "senior": "Устойчив при умеренных отклонениях нормальности при n > 30."
        },
        "effect_size": "cohens_d",
        "emoji": "📊"
    },
    
    "t_test_rel": {
        "name": "Paired t-test",
        "name_ru": "Парный t-test",
        "when_to_use": [
            "Две зависимые выборки",
            "До/после для одних и тех же участников",
            "Нормальность разностей"
        ],
        "assumptions": ["normality", "independence"],
        "why_it_works": {
            "junior": "Сравнивает средние различий внутри пар.",
            "mid": "Тестирует среднее разностей на отличия от 0.",
            "senior": "Чувствителен к выбросам в разностях; при нарушении используйте Wilcoxon."
        },
        "alternatives": {
            "non_normal": {"test": "wilcoxon", "reason": "если разности не нормальны"}
        },
        "effect_size": "cohens_d",
        "emoji": "📊"
    },
    
    "t_test_welch": {
        "name": "Welch's t-test",
        "name_ru": "T-test Уэлча",
        "when_to_use": [
            "2 независимые группы",
            "Дисперсии различаются",
            "Более robust чем Student's t-test"
        ],
        "assumptions": ["normality", "independence"],
        "why_it_works": {
            "junior": "Сравнивает средние без требования равных дисперсий.",
            "mid": "Использует Satterthwaite approximation для df.",
            "senior": "Рекомендуется по умолчанию при сомнениях в равенстве дисперсий."
        },
        "effect_size": "cohens_d",
        "emoji": "📊"
    },
    
    "wilcoxon": {
        "name": "Wilcoxon signed-rank test",
        "name_ru": "Критерий Вилкоксона",
        "when_to_use": [
            "Две зависимые выборки",
            "Ненормальные разности",
            "Ordinal или skewed данные"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Сравнивает ранги разностей вместо средних.",
            "mid": "Проверяет медиану разностей.",
            "senior": "Не требует нормальности, но предполагает симметрию распределения разностей."
        },
        "effect_size": "rank_biserial",
        "emoji": "📊"
    },
    
    "kruskal": {
        "name": "Kruskal-Wallis H test",
        "name_ru": "H-тест Краскела-Уоллиса",
        "when_to_use": [
            "3+ независимых групп",
            "Ненормальное распределение",
            "Ordinal или skewed данные"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Непараметрический аналог ANOVA. Сравнивает ранги вместо средних.",
            "mid": "H-статистика основана на сумме квадратов рангов.",
            "senior": "Post-hoc: Dunn's test с коррекцией на множественные сравнения."
        },
        "effect_size": "epsilon_squared",
        "emoji": "📈"
    },
    
    "anova_welch": {
        "name": "Welch's ANOVA",
        "name_ru": "ANOVA Уэлча",
        "when_to_use": [
            "3+ независимых групп",
            "Дисперсии различаются",
            "Неравные размеры групп"
        ],
        "assumptions": ["normality", "independence"],
        "why_it_works": {
            "junior": "Сравнивает группы без требования равных дисперсий.",
            "mid": "Использует корректировки df для устойчивости.",
            "senior": "Пост-хок: Games-Howell."
        },
        "effect_size": "eta_squared",
        "emoji": "📈"
    },
    
    "rm_anova": {
        "name": "Repeated Measures ANOVA",
        "name_ru": "ANOVA для повторных измерений",
        "when_to_use": [
            "Одна группа с несколькими измерениями",
            "Нормальность остатков",
            "Сферичность"
        ],
        "assumptions": ["normality", "sphericity", "independence"],
        "why_it_works": {
            "junior": "Сравнивает средние в нескольких временных точках.",
            "mid": "Учитывает внутригрупповые корреляции.",
            "senior": "При нарушении сферичности используйте корректировки или mixed models."
        },
        "effect_size": "partial_eta_squared",
        "emoji": "📈"
    },
    
    "friedman": {
        "name": "Friedman test",
        "name_ru": "Тест Фридмана",
        "when_to_use": [
            "Повторные измерения",
            "Ненормальные данные",
            "Ordinal шкала"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Непараметрический аналог RM-ANOVA.",
            "mid": "Сравнивает ранги внутри субъекта.",
            "senior": "Post-hoc: Wilcoxon с коррекцией на множественные сравнения."
        },
        "effect_size": "epsilon_squared",
        "emoji": "📈"
    },
    
    "fisher": {
        "name": "Fisher's Exact Test",
        "name_ru": "Точный критерий Фишера",
        "when_to_use": [
            "2×2 таблица частот",
            "Малые выборки",
            "Expected count < 5"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Точный тест для маленьких таблиц.",
            "mid": "Основан на гипергеометрическом распределении.",
            "senior": "Предпочтителен при малых ожидаемых частотах."
        },
        "effect_size": "cramers_v",
        "emoji": "📊"
    },
    
    "mcnemar": {
        "name": "McNemar's Test",
        "name_ru": "Тест МакНемара",
        "when_to_use": [
            "Парные бинарные исходы",
            "До/после",
            "2×2 таблица" 
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Проверяет, изменились ли пропорции в парных данных.",
            "mid": "Использует discordant pairs.",
            "senior": "Для малых sample используйте exact-версию."
        },
        "effect_size": "cramers_v",
        "emoji": "📊"
    },
    
    "cochran_q": {
        "name": "Cochran's Q Test",
        "name_ru": "Q-тест Кокрана",
        "when_to_use": [
            "3+ связанных бинарных условий",
            "Повторные измерения",
            "Дихотомические исходы"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Проверяет различия в пропорциях между несколькими условиями.",
            "mid": "Обобщение McNemar для k условий.",
            "senior": "Post-hoc: McNemar с коррекцией."
        },
        "effect_size": "cramers_v",
        "emoji": "📊"
    },
    
    "point_biserial": {
        "name": "Point-Biserial Correlation",
        "name_ru": "Точечно-бисериальная корреляция",
        "when_to_use": [
            "Одна переменная бинарная",
            "Другая непрерывная",
            "Линейная связь"
        ],
        "assumptions": ["normality", "linearity"],
        "why_it_works": {
            "junior": "Частный случай Pearson для бинарной переменной.",
            "mid": "Эквивалентна t-test для групп 0/1.",
            "senior": "Чувствительна к дисбалансу классов."
        },
        "effect_size": "r",
        "emoji": "📈"
    },
    
    "partial_correlation": {
        "name": "Partial Correlation",
        "name_ru": "Частная корреляция",
        "when_to_use": [
            "Нужно контролировать ковариату",
            "Оценка чистой связи двух переменных",
            "Линейность"
        ],
        "assumptions": ["normality", "linearity"],
        "why_it_works": {
            "junior": "Убирает влияние третьей переменной.",
            "mid": "Работает через регрессию остатков.",
            "senior": "Проверяйте мультиколлинеарность."
        },
        "effect_size": "r",
        "emoji": "📈"
    },
    
    "linear_regression": {
        "name": "Linear Regression",
        "name_ru": "Линейная регрессия",
        "when_to_use": [
            "Непрерывный исход",
            "Несколько предикторов",
            "Линейная связь"
        ],
        "assumptions": ["linearity", "homoscedasticity", "normality", "independence", "multicollinearity"],
        "why_it_works": {
            "junior": "Объясняет, как предикторы влияют на исход.",
            "mid": "Минимизирует сумму квадратов ошибок.",
            "senior": "Проверяйте остатки и leverage points."
        },
        "effect_size": "r",
        "emoji": "📐"
    },
    
    "logistic_regression": {
        "name": "Logistic Regression",
        "name_ru": "Логистическая регрессия",
        "when_to_use": [
            "Бинарный исход",
            "Несколько предикторов",
            "Оценка вероятностей"
        ],
        "assumptions": ["linearity", "independence", "multicollinearity"],
        "why_it_works": {
            "junior": "Предсказывает вероятность события.",
            "mid": "Моделирует логит-вероятность как линейную функцию предикторов.",
            "senior": "Интерпретируйте коэффициенты как odds ratio."
        },
        "effect_size": "odds_ratio",
        "emoji": "📐"
    },
    
    "roc_analysis": {
        "name": "ROC Analysis",
        "name_ru": "ROC-анализ",
        "when_to_use": [
            "Бинарный исход",
            "Непрерывный предиктор",
            "Оценка качества классификации"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Сравнивает чувствительность и специфичность на всех порогах.",
            "mid": "AUC показывает качество классификации.",
            "senior": "Сравнивайте ROC-кривые, учитывая клинические пороги."
        },
        "effect_size": "auc",
        "emoji": "🎯"
    },
    
    "survival_km": {
        "name": "Kaplan-Meier Survival Analysis",
        "name_ru": "Каплан–Майер",
        "when_to_use": [
            "Время до события",
            "Цензурированные данные",
            "Сравнение групп"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Оценивает вероятность выживания во времени.",
            "mid": "Учитывает цензурирование и шаговые изменения.",
            "senior": "Сравнение групп через log-rank тест."
        },
        "effect_size": "r",
        "emoji": "⏱️"
    },
    
    "mixed_model": {
        "name": "Linear Mixed Models",
        "name_ru": "Линейные смешанные модели",
        "when_to_use": [
            "Кластерные данные",
            "Повторные измерения",
            "Неравные размеры групп"
        ],
        "assumptions": ["normality", "independence"],
        "why_it_works": {
            "junior": "Учитывает случайные эффекты для группировки.",
            "mid": "Разделяет фиксированные и случайные эффекты.",
            "senior": "Устойчив к несбалансированным дизайнам."
        },
        "effect_size": "r",
        "emoji": "🧩"
    },
    
    "mixed_effects": {
        "name": "Linear Mixed Effects",
        "name_ru": "Смешанные эффекты",
        "when_to_use": [
            "Повторные измерения",
            "Случайные эффекты",
            "Time×Group взаимодействия"
        ],
        "assumptions": ["normality", "independence"],
        "why_it_works": {
            "junior": "Позволяет моделировать зависимые наблюдения.",
            "mid": "Добавляет случайные эффекты для субъектов/кластеров.",
            "senior": "Удобно для продольных и иерархических данных."
        },
        "effect_size": "r",
        "emoji": "🧩"
    },
    
    "clustered_correlation": {
        "name": "Clustered Correlation",
        "name_ru": "Кластерная корреляция",
        "when_to_use": [
            "Много переменных",
            "Нужно выявить структуры",
            "Корреляционная матрица"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Группирует похожие переменные по корреляции.",
            "mid": "Использует иерархическую кластеризацию.",
            "senior": "Чувствителен к масштабу и выбросам."
        },
        "effect_size": "r",
        "emoji": "🗺️"
    },
    
    "shapiro_wilk": {
        "name": "Shapiro-Wilk Test",
        "name_ru": "Тест Шапиро–Уилка",
        "when_to_use": [
            "Проверка нормальности",
            "Малые и средние выборки",
            "Перед t-test/ANOVA"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Проверяет, похожи ли данные на нормальное распределение.",
            "mid": "Сравнивает упорядоченные данные с ожидаемыми квантилями.",
            "senior": "Чувствителен к отклонениям при больших n."
        },
        "emoji": "🧪"
    },
    
    "levene": {
        "name": "Levene's Test",
        "name_ru": "Тест Левена",
        "when_to_use": [
            "Проверка равенства дисперсий",
            "Перед ANOVA",
            "Сравнение групп"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Проверяет, одинаков ли разброс в группах.",
            "mid": "Сравнивает отклонения от медианы/среднего.",
            "senior": "Устойчив к отклонениям от нормальности."
        },
        "emoji": "🧪"
    },
    
    "bland_altman": {
        "name": "Bland-Altman Analysis",
        "name_ru": "Анализ Бланда–Олтмана",
        "when_to_use": [
            "Сравнение двух методов измерения",
            "Непрерывные данные",
            "Оценка согласия"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Показывает смещение и пределы согласия.",
            "mid": "Анализирует разности и средние измерений.",
            "senior": "Проверяйте тренд разностей от уровня измерений."
        },
        "effect_size": "r",
        "emoji": "🧭"
    },
    
    "icc": {
        "name": "Intraclass Correlation (ICC)",
        "name_ru": "Внутриклассовая корреляция",
        "when_to_use": [
            "Оценка надежности измерений",
            "Несколько оценщиков",
            "Непрерывные данные"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Показывает, насколько согласованы измерения.",
            "mid": "Разделяет вариацию между объектами и внутри.",
            "senior": "Выбор типа ICC зависит от дизайна."
        },
        "effect_size": "r",
        "emoji": "🤝"
    },
    
    "cohens_kappa": {
        "name": "Cohen's Kappa",
        "name_ru": "Каппа Коэна",
        "when_to_use": [
            "Согласие категориальных оценок",
            "Два оценщика",
            "Бинарные или категориальные данные"
        ],
        "assumptions": ["independence"],
        "why_it_works": {
            "junior": "Корректирует согласие на случайность.",
            "mid": "Сравнивает наблюдаемое и ожидаемое согласие.",
            "senior": "Чувствителен к дисбалансу классов."
        },
        "effect_size": "r",
        "emoji": "🤝"
    },
    
    "anova_twoway": {
        "name": "Two-Way ANOVA",
        "name_ru": "Двухфакторный ANOVA",
        "when_to_use": [
            "Два фактора",
            "Интеракции факторов",
            "Нормальность и гомогенность"
        ],
        "assumptions": ["normality", "homogeneity", "independence"],
        "why_it_works": {
            "junior": "Проверяет влияние двух факторов и их взаимодействие.",
            "mid": "Оценивает главные эффекты и interaction.",
            "senior": "Пост-хок и simple effects при значимой interaction."
        },
        "effect_size": "eta_squared",
        "emoji": "📈"
    },
    
    "ancova": {
        "name": "ANCOVA",
        "name_ru": "ANCOVA",
        "when_to_use": [
            "Сравнение групп",
            "Есть ковариата",
            "Нужно контролировать смещение"
        ],
        "assumptions": ["normality", "homogeneity", "independence", "linearity"],
        "why_it_works": {
            "junior": "Сравнивает группы, учитывая ковариату.",
            "mid": "Удаляет влияние ковариаты на исход.",
            "senior": "Проверяйте homogeneity of regression slopes."
        },
        "effect_size": "partial_eta_squared",
        "emoji": "📐"
    },
    
    "pca": {
        "name": "Principal Component Analysis",
        "name_ru": "PCA",
        "when_to_use": [
            "Снижение размерности",
            "Много коррелированных переменных",
            "Визуализация структуры"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Находит направления максимальной дисперсии.",
            "mid": "Компоненты ортогональны и упорядочены по объясненной дисперсии.",
            "senior": "Стандартизируйте переменные перед PCA."
        },
        "emoji": "🧭"
    },
    
    "efa": {
        "name": "Exploratory Factor Analysis",
        "name_ru": "Эксплораторный факторный анализ",
        "when_to_use": [
            "Латентные факторы",
            "Вопросники",
            "Структура переменных"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Находит скрытые факторы.",
            "mid": "Разделяет общую и уникальную дисперсию.",
            "senior": "Проверяйте KMO и Bartlett перед EFA."
        },
        "emoji": "🧭"
    },
    
    "cronbach_alpha": {
        "name": "Cronbach's Alpha",
        "name_ru": "Альфа Кронбаха",
        "when_to_use": [
            "Надежность шкалы",
            "Несколько пунктов измеряют одно",
            "Оценка внутренней согласованности"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Показывает согласованность пунктов.",
            "mid": "Основана на межпунктовых корреляциях.",
            "senior": "Очень высокая alpha может означать дублирование пунктов."
        },
        "effect_size": "r",
        "emoji": "🧩"
    },
    
    "kmeans": {
        "name": "K-Means Clustering",
        "name_ru": "K-means",
        "when_to_use": [
            "Поиск кластеров",
            "Нужно задать K",
            "Однородные группы"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Группирует по близости к центрам.",
            "mid": "Минимизирует внутрикластерную сумму квадратов.",
            "senior": "Чувствителен к масштабам и выбросам."
        },
        "emoji": "🧠"
    },
    
    "hierarchical_clustering": {
        "name": "Hierarchical Clustering",
        "name_ru": "Иерархическая кластеризация",
        "when_to_use": [
            "Неизвестное число кластеров",
            "Нужна дендрограмма",
            "Структура данных"
        ],
        "assumptions": [],
        "why_it_works": {
            "junior": "Постепенно объединяет похожие объекты.",
            "mid": "Связь зависит от выбранного linkage.",
            "senior": "Чувствительна к метрике и масштабу."
        },
        "emoji": "🌲"
    }
}


# =============================================================================
# API FUNCTIONS
# =============================================================================

def get_explanation(term: str, level: str = "junior") -> Optional[Dict[str, Any]]:
    """
    Get explanation for a statistical term at specified level.
    
    Args:
        term: Term key (e.g., "p_value", "effect_size")
        level: "junior", "mid", or "senior"
    
    Returns:
        Dictionary with term, definition, common_mistakes, etc.
    """
    if term not in STAT_TERMS:
        return None
    
    knowledge = STAT_TERMS[term]
    definition = knowledge.get("definition", {})
    
    return {
        "term": knowledge.get("term", term),
        "term_ru": knowledge.get("term_ru", term),
        "definition": definition.get(level, definition.get("junior", "")),
        "common_mistakes": knowledge.get("common_mistakes", []),
        "what_to_check": knowledge.get("what_to_check", []),
        "how_to_check": knowledge.get("how_to_check"),
        "if_violated": knowledge.get("if_violated"),
        "recommendation": knowledge.get("recommendation"),
        "recommendations": knowledge.get("recommendations"),
        "formula": knowledge.get("formula"),
        "thresholds": knowledge.get("thresholds"),
        "methods": knowledge.get("methods"),
        "examples": knowledge.get("examples"),
        "emoji": knowledge.get("emoji", "📊")
    }


def get_test_rationale(
    test_id: str, 
    data_profile: Optional[Dict[str, Any]] = None,
    level: str = "junior"
) -> Optional[Dict[str, Any]]:
    """
    Get rationale for why a test was chosen.
    
    Args:
        test_id: Test identifier (e.g., "t_test_ind", "anova")
        data_profile: Data characteristics (n_groups, normality checks, etc.)
        level: Explanation depth
    
    Returns:
        Dictionary with test info, rationale, assumptions, alternatives
    """
    if test_id not in TEST_KNOWLEDGE:
        return None
    
    knowledge = TEST_KNOWLEDGE[test_id]
    why = knowledge.get("why_it_works", {})
    
    result = {
        "test_id": test_id,
        "name": knowledge.get("name", test_id),
        "name_ru": knowledge.get("name_ru", test_id),
        "when_to_use": knowledge.get("when_to_use", []),
        "why_it_works": why.get(level, why.get("junior", "")),
        "assumptions": knowledge.get("assumptions", []),
        "assumption_details": [
            {
                "key": a,
                "term": STAT_TERMS.get(a, {}).get("term", a),
                "term_ru": STAT_TERMS.get(a, {}).get("term_ru", a),
                "definition": STAT_TERMS.get(a, {}).get("definition", {}).get(level, STAT_TERMS.get(a, {}).get("definition", {}).get("junior", "")),
                "how_to_check": STAT_TERMS.get(a, {}).get("how_to_check"),
                "if_violated": STAT_TERMS.get(a, {}).get("if_violated"),
            }
            for a in knowledge.get("assumptions", [])
        ],
        "alternatives": knowledge.get("alternatives", {}),
        "references": get_references_for_test(test_id),
        "reporting": knowledge.get("reporting"),
        "effect_size": knowledge.get("effect_size"),
        "emoji": knowledge.get("emoji", "📊")
    }
    
    # Add assumption checks if data_profile provided
    if data_profile:
        result["assumption_checks"] = _check_assumptions(
            knowledge.get("assumptions", []),
            data_profile
        )
    
    return result


def get_effect_size_interpretation(
    effect_type: str, 
    value: float
) -> Dict[str, Any]:
    """
    Get interpretation of effect size value.
    
    Args:
        effect_type: "cohens_d", "eta_squared", "r", etc.
        value: Numeric effect size value
    
    Returns:
        Dictionary with interpretation, label, percentile info
    """
    if "effect_size" not in STAT_TERMS:
        return {"label": "unknown", "interpretation": ""}
    
    thresholds = STAT_TERMS["effect_size"].get("thresholds", {})
    
    if effect_type == "eta_squared":
        effect_type = "partial_eta_squared" if "partial_eta_squared" in thresholds else effect_type

    if effect_type not in thresholds:
        return {"label": "unknown", "interpretation": ""}
    
    type_thresholds = thresholds[effect_type]
    abs_value = abs(value)
    
    # Find the appropriate category
    label = "unknown"
    for category, bounds in type_thresholds.items():
        max_val = bounds.get("max", float("inf"))
        min_val = bounds.get("min", 0)
        
        if min_val <= abs_value <= max_val:
            label = bounds.get("label", category)
            break
        elif "min" in bounds and abs_value >= min_val:
            label = bounds.get("label", category)
            break
    
    # Practical meaning for Cohen's d
    practical = ""
    if effect_type == "cohens_d":
        cohens_practical = STAT_TERMS.get("cohens_d", {}).get("practical_meaning", {})
        closest = min(cohens_practical.keys(), key=lambda x: abs(x - abs_value), default=None)
        if closest:
            practical = cohens_practical[closest]
    
    return {
        "value": value,
        "abs_value": abs_value,
        "type": effect_type,
        "label": label,
        "label_ru": label,  # Already in Russian from thresholds
        "practical_meaning": practical,
        "direction": "positive" if value > 0 else "negative" if value < 0 else "none"
    }


def get_power_recommendation(power: float) -> Dict[str, Any]:
    """
    Get recommendation based on power value.
    
    Args:
        power: Statistical power (0-1)
    
    Returns:
        Dictionary with status, message, recommendation
    """
    if power < 0.5:
        return {
            "status": "critical",
            "status_ru": "критически низкая",
            "message": "Критически низкая мощность. Высокий риск пропустить реальный эффект.",
            "recommendation": "Увеличьте размер выборки значительно.",
            "icon": "🔴"
        }
    elif power < 0.8:
        return {
            "status": "insufficient",
            "status_ru": "недостаточная",
            "message": f"Мощность {power:.0%} ниже рекомендуемых 80%.",
            "recommendation": "Рассмотрите увеличение выборки для более надёжных выводов.",
            "icon": "🟡"
        }
    elif power < 0.95:
        return {
            "status": "adequate",
            "status_ru": "адекватная",
            "message": f"Мощность {power:.0%} — адекватна для обнаружения эффекта.",
            "recommendation": None,
            "icon": "🟢"
        }
    else:
        return {
            "status": "high",
            "status_ru": "высокая",
            "message": f"Мощность {power:.0%} — высокая.",
            "recommendation": "Выборка может быть избыточной для данного effect size.",
            "icon": "🟢"
        }


def _check_assumptions(
    assumptions: List[str], 
    data_profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Check assumptions against data profile."""
    results = []
    
    for assumption in assumptions:
        check = {
            "assumption": assumption,
            "term": STAT_TERMS.get(assumption, {}).get("term", assumption),
            "passed": None,
            "p_value": None,
            "note": ""
        }
        
        if assumption == "normality":
            shapiro_p = data_profile.get("shapiro_p")
            if shapiro_p is not None:
                check["passed"] = shapiro_p > 0.05
                check["p_value"] = shapiro_p
                check["note"] = "Shapiro-Wilk test"
                if not check["passed"]:
                    check["recommendation"] = STAT_TERMS.get("normality", {}).get("if_violated", "")
        
        elif assumption == "homogeneity":
            levene_p = data_profile.get("levene_p")
            if levene_p is not None:
                check["passed"] = levene_p > 0.05
                check["p_value"] = levene_p
                check["note"] = "Levene's test"
                if not check["passed"]:
                    check["recommendation"] = STAT_TERMS.get("homogeneity", {}).get("if_violated", "")
        
        elif assumption == "independence":
            check["passed"] = data_profile.get("independence", True)
            check["note"] = "Assumed based on study design"
        
        results.append(check)
    
    return results


def get_all_terms() -> List[Dict[str, str]]:
    """Get list of all available statistical terms."""
    return [
        {
            "key": key,
            "term": val.get("term", key),
            "term_ru": val.get("term_ru", key),
            "emoji": val.get("emoji", "📊")
        }
        for key, val in STAT_TERMS.items()
    ]


def get_all_tests() -> List[Dict[str, str]]:
    """Get list of all available statistical tests with info."""
    return [
        {
            "key": key,
            "name": val.get("name", key),
            "name_ru": val.get("name_ru", key),
            "emoji": val.get("emoji", "📊")
        }
        for key, val in TEST_KNOWLEDGE.items()
    ]


def get_citation(reference_key: str) -> Optional[Dict[str, str]]:
    """
    Get academic citation for a statistical concept.
    
    Args:
        reference_key: Key from ACADEMIC_REFERENCES (e.g., "effect_size_conventions")
    
    Returns:
        Dictionary with citation, doi, bibtex, note
    
    Example:
        >>> get_citation("effect_size_conventions")
        {"citation": "Cohen, J. (1988)...", "bibtex": "@book{cohen1988,...}"}
    """
    return ACADEMIC_REFERENCES.get(reference_key)


def get_all_references() -> Dict[str, Dict[str, str]]:
    """
    Get all academic references for methodology documentation.
    
    Useful for:
    - Generating bibliography
    - Adding citations to reports
    - Justifying methodological choices
    
    Returns:
        Dictionary of all academic references
    """
    return ACADEMIC_REFERENCES


def get_references_for_test(test_id: str) -> List[Dict[str, str]]:
    """
    Get relevant references for a specific statistical test.
    
    Args:
        test_id: Test identifier (e.g., "t_test_ind", "mann_whitney")
    
    Returns:
        List of relevant citations
    """
    test_to_refs = {
        "t_test_ind": ["effect_size_conventions", "welch_default", "effect_size_primer"],
        "t_test_welch": ["welch_default", "effect_size_conventions"],
        "mann_whitney": ["mann_whitney", "effect_size_primer"],
        "anova": ["effect_size_conventions", "bonferroni", "effect_size_primer"],
        "kruskal": ["kruskal_wallis", "bonferroni"],
        "chi_square": ["de_smith_handbook", "field_spss"],
        "pearson": ["de_smith_handbook", "field_spss"],
        "spearman": ["de_smith_handbook", "field_spss"]
    }
    
    ref_keys = test_to_refs.get(test_id, ["de_smith_handbook"])
    return [
        {"key": key, **ACADEMIC_REFERENCES[key]}
        for key in ref_keys
        if key in ACADEMIC_REFERENCES
    ]


def get_reporting_template(test_id: str, result: Dict[str, Any]) -> str:
    """
    Generate APA-style reporting template for statistical result.
    
    Args:
        test_id: Test identifier
        result: Dictionary with p_value, effect_size, etc.
    
    Returns:
        APA-formatted result string (Russian)
    
    Example:
        >>> get_reporting_template("t_test_ind", {"t": 2.45, "df": 48, "p_value": 0.018, "effect_size": 0.71})
        "t(48) = 2.45, p = .018, d = 0.71 [средний эффект]"
    """
    templates = {
        "t_test_ind": "t({df}) = {stat:.2f}, p {p_str}, d = {effect:.2f} [{effect_label}]",
        "t_test_welch": "t({df:.1f}) = {stat:.2f}, p {p_str}, d = {effect:.2f} [{effect_label}]",
        "mann_whitney": "U = {stat:.0f}, p {p_str}, r = {effect:.2f}",
        "anova": "F({df_between}, {df_within}) = {stat:.2f}, p {p_str}, η² = {effect:.3f} [{effect_label}]",
        "kruskal": "H({df}) = {stat:.2f}, p {p_str}",
        "chi_square": "χ²({df}) = {stat:.2f}, p {p_str}, V = {effect:.2f}",
        "pearson": "r({df}) = {stat:.2f}, p {p_str}",
        "spearman": "ρ({df}) = {stat:.2f}, p {p_str}"
    }
    
    if test_id not in templates:
        return ""
    
    # Format p-value
    p = result.get("p_value", 1.0)
    if p < 0.001:
        p_str = "< .001"
    else:
        p_str = f"= {p:.3f}".lstrip("0")
    
    # Get effect size label
    effect = result.get("effect_size", 0)
    effect_type = result.get("effect_size_type", "cohens_d")
    effect_info = get_effect_size_interpretation(effect_type, effect)
    effect_label = effect_info.get("label_ru", "")
    
    try:
        return templates[test_id].format(
            stat=result.get("stat_value", result.get("t", result.get("statistic", 0))),
            df=result.get("df", result.get("dof", 0)),
            df_between=result.get("df_between", 0),
            df_within=result.get("df_within", 0),
            p_str=p_str,
            effect=abs(effect),
            effect_label=effect_label
        )
    except (KeyError, ValueError):
        return ""


# =============================================================================
# RECOMMENDED READING BY TOPIC
# =============================================================================

RECOMMENDED_READING = {
    "effect_sizes": [
        "Cohen, J. (1988). Statistical Power Analysis — классика, обязательно для понимания d, r, f",
        "Lakens, D. (2013). Frontiers in Psychology — практический туториал с формулами",
        "Field, A. (2018). Discovering Statistics — доступное объяснение"
    ],
    "p_values": [
        "ASA Statement (Wasserstein & Lazar, 2016) — официальная позиция по p-value",
        "Greenland et al. (2016). European Journal of Epidemiology — 25 мифов о p-value"
    ],
    "power_analysis": [
        "G*Power manual (Faul et al., 2007) — методология расчёта мощности",
        "Cohen, J. (1992). Psychological Bulletin — 'A Power Primer'"
    ],
    "multiple_comparisons": [
        "Benjamini & Hochberg (1995) — FDR коррекция",
        "Dunn (1961) — Bonferroni коррекция"
    ],
    "nonparametric": [
        "Mann & Whitney (1947) — оригинальная статья U-теста",
        "Kruskal & Wallis (1952) — H-тест для 3+ групп"
    ],
    "general_reference": [
        "de Smith, M. J. (2018). statsref.com — онлайн справочник",
        "APA Publication Manual (7th ed.) — стандарты отчётности"
    ]
}


def get_recommended_reading(topic: str = "general_reference") -> List[str]:
    """
    Get recommended reading list for a topic.
    
    Args:
        topic: "effect_sizes", "p_values", "power_analysis", 
               "multiple_comparisons", "nonparametric", "general_reference"
    
    Returns:
        List of recommended sources
    """
    return RECOMMENDED_READING.get(topic, RECOMMENDED_READING["general_reference"])
