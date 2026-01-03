from app.schemas.analysis import StatMethod

METHODS = {
    "t_test_ind": StatMethod(
        id="t_test_ind",
        name="Student's t-test (Independent)",
        description="Compares means of two independent groups. Assumes normal distribution.",
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
    )
}

def get_method(method_id: str) -> StatMethod:
    return METHODS.get(method_id)
