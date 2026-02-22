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
    "bootstrap_pipeline": {"python": True, "r": False},
    "cluster_profiles": {"python": True, "r": False},
    "external_validation": {"python": True, "r": False},
    "responders": {"python": True, "r": True},
    "anova_twoway": {"python": True, "r": True},
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
