from typing import List

from app.schemas.analysis import IODescriptor, StatMethod

METHODS = {
    "t_test_ind": StatMethod(
        id="t_test_ind",
        name="Student's t-test (Independent)",
        description="Compares means of two independent groups. Assumes normal distribution.",
        type="parametric",
        min_groups=2,
        max_groups=2,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "mann_whitney": StatMethod(
        id="mann_whitney",
        name="Mann-Whitney U Test",
        description="Compares distributions of two independent groups. Non-parametric (does not assume normality).",
        type="non-parametric",
        min_groups=2,
        max_groups=2,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "t_test_rel": StatMethod(
        id="t_test_rel",
        name="Paired t-test",
        description="Compares means of two dependent (paired) groups. Assumes normal distribution of differences.",
        type="parametric",
        min_groups=2,
        max_groups=2,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "wilcoxon": StatMethod(
        id="wilcoxon",
        name="Wilcoxon Signed-Rank Test",
        description="Compares two dependent (paired) groups. Non-parametric.",
        type="non-parametric",
        min_groups=2,
        max_groups=2,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "chi_square": StatMethod(
        id="chi_square",
        name="Chi-Square Test of Independence",
        description="Tests association between two categorical variables.",
        type="categorical",
        min_groups=2,
        max_groups=100,
        status="ready",
        inputs=[
            IODescriptor(name="feature_a", kind="target", dtype="numeric_or_categorical"),
            IODescriptor(name="feature_b", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "fisher": StatMethod(
        id="fisher",
        name="Fisher's Exact Test",
        description="Tests association between two categorical variables (better for small samples).",
        type="categorical",
        min_groups=2,
        max_groups=2,
        status="disabled",
        inputs=[
            IODescriptor(name="feature_a", kind="target", dtype="numeric_or_categorical"),
            IODescriptor(name="feature_b", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "pearson": StatMethod(
        id="pearson",
        name="Pearson Correlation",
        description="Measures linear correlation between two numeric variables. Assumes normality.",
        type="correlation",
        min_groups=0,
        max_groups=0,
        status="ready",
        inputs=[
            IODescriptor(name="x", kind="feature", dtype="numeric"),
            IODescriptor(name="y", kind="feature", dtype="numeric"),
        ],
    ),
    "spearman": StatMethod(
        id="spearman",
        name="Spearman Correlation",
        description="Measures monotonic correlation (rank-based). Non-parametric.",
        type="correlation",
        min_groups=0,
        max_groups=0,
        status="ready",
        inputs=[
            IODescriptor(name="x", kind="feature", dtype="numeric_or_categorical"),
            IODescriptor(name="y", kind="feature", dtype="numeric_or_categorical"),
        ],
    ),
    "anova": StatMethod(
        id="anova",
        name="One-Way ANOVA",
        description="Compares means of three or more independent groups. Assumes normal distribution and homogeneity of variances.",
        type="parametric",
        min_groups=3,
        max_groups=100,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "kruskal": StatMethod(
        id="kruskal",
        name="Kruskal-Wallis H-test",
        description="Non-parametric alternative to ANOVA. Compares distributions of three or more independent groups.",
        type="non-parametric",
        min_groups=3,
        max_groups=100,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "rm_anova": StatMethod(
        id="rm_anova",
        name="Repeated Measures ANOVA",
        description="Compares means of the same subjects across three or more time points/conditions.",
        type="parametric",
        min_groups=3,
        max_groups=100,
        status="disabled",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical"),
        ],
    ),
    "mixed_model": StatMethod(
        id="mixed_model",
        name="Linear Mixed Models (LMM)",
        description="Advanced model for nested/clustered data and unbalanced designs. Essential for complex clinical trials.",
        type="parametric",
        min_groups=2,
        max_groups=100,
        status="disabled",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="predictor", kind="predictor", dtype="numeric_or_categorical", multiple=True),
        ],
    ),
    "survival_km": StatMethod(
        id="survival_km",
        name="Kaplan-Meier Survival Analysis",
        description="Estimates survival probability over time. Includes Log-Rank test to compare groups.",
        type="non-parametric",
        min_groups=2,
        max_groups=20,
        status="ready",
        inputs=[
            IODescriptor(name="duration", kind="duration", dtype="numeric"),
            IODescriptor(name="event", kind="event", dtype="binary"),
            IODescriptor(name="group", kind="group", dtype="numeric_or_categorical", required=False),
        ],
    ),
    "linear_regression": StatMethod(
        id="linear_regression",
        name="Linear Regression",
        description="Predicts a continuous outcome based on one or more predictors.",
        type="parametric",
        min_groups=1,
        max_groups=20,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="numeric"),
            IODescriptor(name="predictor", kind="predictor", dtype="numeric_or_categorical", multiple=True),
        ],
    ),
    "logistic_regression": StatMethod(
        id="logistic_regression",
        name="Logistic Regression",
        description="Predicts a binary outcome (Yes/No) based on one or more predictors.",
        type="parametric",
        min_groups=1,
        max_groups=20,
        status="ready",
        inputs=[
            IODescriptor(name="target", kind="target", dtype="binary"),
            IODescriptor(name="predictor", kind="predictor", dtype="numeric_or_categorical", multiple=True),
        ],
    )
}

def get_method(method_id: str, allow_disabled: bool = False) -> StatMethod:
    method = METHODS.get(method_id)
    if not method:
        return None
    if allow_disabled:
        return method
    return method if method.status == "ready" else None


def list_methods(include_experimental: bool = False) -> List[StatMethod]:
    if include_experimental:
        return [m for m in METHODS.values() if m.status != "disabled"]
    return [m for m in METHODS.values() if m.status == "ready"]
