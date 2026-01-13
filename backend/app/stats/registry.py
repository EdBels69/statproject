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
    )
}

def get_method(method_id: str) -> StatMethod:
    return METHODS.get(method_id)
