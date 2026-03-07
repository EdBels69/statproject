from typing import Dict, List


METHOD_COVERAGE: Dict[str, Dict[str, bool]] = {
    "t_test_ind": {"python": True, "r": True},
    "t_test_welch": {"python": True, "r": True},
    "mann_whitney": {"python": True, "r": True},
    "t_test_rel": {"python": True, "r": True},
    "wilcoxon": {"python": True, "r": True},
    "anova": {"python": True, "r": True},
    "anova_welch": {"python": True, "r": True},
    "kruskal": {"python": True, "r": True},
    "chi_square": {"python": True, "r": True},
    "fisher_exact": {"python": True, "r": True},
    "pearson": {"python": True, "r": True},
    "spearman": {"python": True, "r": True},
    "kendall": {"python": True, "r": True},
    "linear_regression": {"python": True, "r": True},
    "logistic_regression": {"python": True, "r": True},
    "roc_analysis": {"python": True, "r": True},
    "survival_km": {"python": True, "r": True},
    "rm_anova": {"python": True, "r": True},
    "friedman": {"python": True, "r": True},
    "batch_analysis": {"python": True, "r": True},
    "timepoint_batch_analysis": {"python": True, "r": True},
    "delta_batch_analysis": {"python": True, "r": True},
    "paired_wide": {"python": True, "r": True},
    "mixed_effects": {"python": True, "r": True},
    "clustered_correlation": {"python": True, "r": True},
    "responders": {"python": True, "r": True},
    "anova_twoway": {"python": True, "r": True},
    "ancova": {"python": True, "r": True},
    "pca": {"python": True, "r": True},
    "efa": {"python": True, "r": True},
    "kmeans": {"python": True, "r": True},
    "hierarchical_clustering": {"python": True, "r": True},
    "cronbach_alpha": {"python": True, "r": True},
    "shapiro_wilk": {"python": True, "r": True},
    "bland_altman": {"python": True, "r": True},
    "icc": {"python": True, "r": True},
    "cohens_kappa": {"python": True, "r": True},
    "mcnemar": {"python": True, "r": True},
    "point_biserial": {"python": True, "r": True},
    "cochran_q": {"python": True, "r": True},
    "partial_correlation": {"python": True, "r": True},
    "t_test_one": {"python": True, "r": True},
    "fisher": {"python": True, "r": True},
    "bayes_t_test_one": {"python": True, "r": False},
    "bayes_t_test_ind": {"python": True, "r": False},
    "bayes_t_test_rel": {"python": True, "r": False},
    "bayes_correlation": {"python": True, "r": False},
    "bayes_anova": {"python": True, "r": False},
    "bayes_linear_regression": {"python": True, "r": False},
    "bayes_chi_square": {"python": True, "r": False},
    "time_series_analysis": {"python": True, "r": False},
}


def normalize_engine_name(raw_engine: str) -> str:
    engine = str(raw_engine or "").strip().lower()
    if engine in {"", "python", "py", "python3"}:
        return "python"
    if engine in {"r", "r_engine", "rstats"}:
        return "r"
    return engine


def is_engine_supported(method_id: str, engine: str) -> bool:
    method = str(method_id or "").strip().lower()
    engine_norm = normalize_engine_name(engine)
    coverage = METHOD_COVERAGE.get(method)
    if not isinstance(coverage, dict):
        return True
    return bool(coverage.get(engine_norm, False))


def supported_engines(method_id: str) -> List[str]:
    method = str(method_id or "").strip().lower()
    coverage = METHOD_COVERAGE.get(method)
    if not isinstance(coverage, dict):
        return ["python", "r"]
    out: List[str] = []
    for name in ("python", "r"):
        if bool(coverage.get(name)):
            out.append(name)
    return out
