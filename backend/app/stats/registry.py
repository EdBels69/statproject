from app.schemas.analysis import StatMethod

METHODS = {
    "t_test_one": StatMethod(
        id="t_test_one",
        name="One-Sample T-Test",
        description="Compares the mean of a single group to a known value.",
        type="parametric",
        min_groups=1,
        max_groups=1
    ),
    "t_test_ind": StatMethod(
        id="t_test_ind",
        name="Student's t-test (Independent)",
        description="Compares means of two independent groups. Assumes normal distribution.",
        type="parametric",
        min_groups=2,
        max_groups=2
    ),
    "t_test_welch": StatMethod(
        id="t_test_welch",
        name="Welch's T-Test",
        description="Compares means of two independent groups with unequal variances. More robust than Student's t-test.",
        type="parametric",
        min_groups=2,
        max_groups=2
    ),
    "mann_whitney": StatMethod(
        id="mann_whitney",
        name="Mann-Whitney U Test",
        description="Compares distributions of two independent groups. Non-parametric (does not assume normality).",
        type="non-parametric",
        min_groups=2,
        max_groups=2
    ),
    "t_test_rel": StatMethod(
        id="t_test_rel",
        name="Paired t-test",
        description="Compares means of two dependent (paired) groups. Assumes normal distribution of differences.",
        type="parametric",
        min_groups=2,
        max_groups=2
    ),
    "wilcoxon": StatMethod(
        id="wilcoxon",
        name="Wilcoxon Signed-Rank Test",
        description="Compares two dependent (paired) groups. Non-parametric.",
        type="non-parametric",
        min_groups=2,
        max_groups=2
    ),
    "chi_square": StatMethod(
        id="chi_square",
        name="Chi-Square Test of Independence",
        description="Tests association between two categorical variables.",
        type="categorical",
        min_groups=2,
        max_groups=100
    ),
    "fisher": StatMethod(
        id="fisher",
        name="Fisher's Exact Test",
        description="Tests association between two categorical variables (better for small samples).",
        type="categorical",
        min_groups=2,
        max_groups=2
    ),
    "pearson": StatMethod(
        id="pearson",
        name="Pearson Correlation",
        description="Measures linear correlation between two numeric variables. Assumes normality.",
        type="correlation",
        min_groups=0,
        max_groups=0
    ),
    "spearman": StatMethod(
        id="spearman",
        name="Spearman Correlation",
        description="Measures monotonic correlation (rank-based). Non-parametric.",
        type="correlation",
        min_groups=0,
        max_groups=0
    ),
    "anova": StatMethod(
        id="anova",
        name="One-Way ANOVA",
        description="Compares means of three or more independent groups. Assumes normal distribution and homogeneity of variances.",
        type="parametric",
        min_groups=3,
        max_groups=100
    ),
    "anova_welch": StatMethod(
        id="anova_welch",
        name="Welch's ANOVA",
        description="Robust ANOVA for unequal variances (heteroscedasticity).",
        type="parametric",
        min_groups=3,
        max_groups=100
    ),
    "kruskal": StatMethod(
        id="kruskal",
        name="Kruskal-Wallis H-test",
        description="Non-parametric alternative to ANOVA. Compares distributions of three or more independent groups.",
        type="non-parametric",
        min_groups=3,
        max_groups=100
    ),
    "rm_anova": StatMethod(
        id="rm_anova",
        name="Repeated Measures ANOVA",
        description="Compares means of the same subjects across three or more time points/conditions.",
        type="parametric",
        min_groups=3,
        max_groups=100
    ),
    "friedman": StatMethod(
        id="friedman",
        name="Friedman Test",
        description="Non-parametric alternative to RM-ANOVA. Compares distributions of the same subjects across multiple conditions.",
        type="non-parametric",
        min_groups=3,
        max_groups=100
    ),
    "mixed_model": StatMethod(
        id="mixed_model",
        name="Linear Mixed Models (LMM)",
        description="Advanced model for nested/clustered data and unbalanced designs. Essential for complex clinical trials.",
        type="parametric",
        min_groups=2,
        max_groups=100
    ),
    "survival_km": StatMethod(
        id="survival_km",
        name="Kaplan-Meier Survival Analysis",
        description="Estimates survival probability over time. Includes Log-Rank test to compare groups.",
        type="non-parametric",
        min_groups=2,
        max_groups=20
    ),
    "linear_regression": StatMethod(
        id="linear_regression",
        name="Linear Regression",
        description="Predicts a continuous outcome based on one or more predictors.",
        type="parametric",
        min_groups=1,
        max_groups=20
    ),
    "logistic_regression": StatMethod(
        id="logistic_regression",
        name="Logistic Regression",
        description="Predicts a binary outcome (Yes/No) based on one or more predictors.",
        type="parametric",
        min_groups=1,
        max_groups=20
    ),
    "roc_analysis": StatMethod(
        id="roc_analysis",
        name="ROC Analysis",
        description="Evaluates diagnostic accuracy of a continuous predictor against a binary outcome. Calculates AUC and optimal cut-off.",
        type="diagnostic",
        min_groups=2,
        max_groups=2
    ),
    # === ASSUMPTION TESTS ===
    "shapiro_wilk": StatMethod(
        id="shapiro_wilk",
        name="Shapiro-Wilk Test",
        description="Tests whether a sample comes from a normally distributed population. Essential before using parametric tests.",
        type="assumption",
        min_groups=1,
        max_groups=1
    ),
    "levene": StatMethod(
        id="levene",
        name="Levene's Test",
        description="Tests equality of variances across groups (homogeneity of variance). Required assumption for ANOVA.",
        type="assumption",
        min_groups=2,
        max_groups=100
    ),
    # === AGREEMENT & RELIABILITY ===
    "bland_altman": StatMethod(
        id="bland_altman",
        name="Bland-Altman Analysis",
        description="Assesses agreement between two measurement methods. Shows systematic bias and limits of agreement.",
        type="agreement",
        min_groups=2,
        max_groups=2
    ),
    "icc": StatMethod(
        id="icc",
        name="Intraclass Correlation (ICC)",
        description="Measures reliability/agreement for continuous outcomes. Essential for inter-rater reliability studies.",
        type="agreement",
        min_groups=2,
        max_groups=100
    ),
    "cohens_kappa": StatMethod(
        id="cohens_kappa",
        name="Cohen's Kappa",
        description="Measures agreement between two raters for categorical outcomes, adjusted for chance agreement.",
        type="agreement",
        min_groups=2,
        max_groups=2
    ),
    # === ADDITIONAL CATEGORICAL ===
    "mcnemar": StatMethod(
        id="mcnemar",
        name="McNemar's Test",
        description="Tests for changes in paired binary outcomes (before/after treatment). Like chi-square for paired data.",
        type="categorical",
        min_groups=2,
        max_groups=2
    ),
    "cochran_q": StatMethod(
        id="cochran_q",
        name="Cochran's Q Test",
        description="Extension of McNemar to 3+ related groups. Tests if proportions differ across conditions.",
        type="categorical",
        min_groups=3,
        max_groups=100
    ),
    # === ADVANCED ANOVA ===
    "anova_twoway": StatMethod(
        id="anova_twoway",
        name="Two-Way ANOVA",
        description="Tests effects of two factors and their interaction. Essential for factorial designs.",
        type="parametric",
        min_groups=4,
        max_groups=100
    ),
    "ancova": StatMethod(
        id="ancova",
        name="ANCOVA",
        description="ANOVA with covariates. Controls for confounding variables when comparing groups.",
        type="parametric",
        min_groups=2,
        max_groups=100
    ),
    # === FACTOR ANALYSIS ===
    "pca": StatMethod(
        id="pca",
        name="Principal Component Analysis (PCA)",
        description="Reduces dimensionality by finding components that explain maximum variance. Great for exploratory analysis.",
        type="dimension_reduction",
        min_groups=0,
        max_groups=0
    ),
    "efa": StatMethod(
        id="efa",
        name="Exploratory Factor Analysis (EFA)",
        description="Discovers latent factors underlying observed variables. Essential for questionnaire validation.",
        type="dimension_reduction",
        min_groups=0,
        max_groups=0
    ),
    "cronbach_alpha": StatMethod(
        id="cronbach_alpha",
        name="Cronbach's Alpha",
        description="Measures internal consistency of a scale. Standard for questionnaire reliability.",
        type="reliability",
        min_groups=0,
        max_groups=0
    ),
    # === CLUSTERING ===
    "kmeans": StatMethod(
        id="kmeans",
        name="K-Means Clustering",
        description="Partitions data into K clusters based on similarity. Requires specifying number of clusters.",
        type="clustering",
        min_groups=0,
        max_groups=0
    ),
    "hierarchical_clustering": StatMethod(
        id="hierarchical_clustering",
        name="Hierarchical Clustering",
        description="Creates a tree of clusters (dendrogram). Good when number of clusters is unknown.",
        type="clustering",
        min_groups=0,
        max_groups=0
    ),
    # === ADDITIONAL CORRELATION ===
    "point_biserial": StatMethod(
        id="point_biserial",
        name="Point-Biserial Correlation",
        description="Correlation between a continuous and a binary variable. Special case of Pearson.",
        type="correlation",
        min_groups=2,
        max_groups=2
    ),
    "partial_correlation": StatMethod(
        id="partial_correlation",
        name="Partial Correlation",
        description="Correlation between two variables while controlling for a third. Removes confounding effects.",
        type="correlation",
        min_groups=0,
        max_groups=0
    )
}

def get_method(method_id: str) -> StatMethod:
    return METHODS.get(method_id)

