from typing import Any, Dict, List

import numpy as np
from scipy import stats


def check_normality(data, alpha: float = 0.05) -> Dict[str, Any]:
    clean = [x for x in data if x is not None and np.isfinite(x)]
    n = len(clean)
    if n < 3 or n > 5000:
        return {"test": "shapiro", "passed": None, "n": n}
    stat, p = stats.shapiro(clean)
    return {"test": "shapiro", "stat": round(float(stat), 4), "p": round(float(p), 4), "passed": bool(p > alpha)}


def check_homogeneity(groups: List, alpha: float = 0.05) -> Dict[str, Any]:
    clean = [[x for x in g if x is not None and np.isfinite(x)] for g in groups]
    if any(len(g) < 2 for g in clean):
        return {"test": "levene", "passed": None}
    stat, p = stats.levene(*clean)
    return {"test": "levene", "stat": round(float(stat), 4), "p": round(float(p), 4), "passed": bool(p > alpha)}


def recommend_test(n_groups: int, paired: bool, norm_ok: bool, homo_ok: bool) -> str:
    if n_groups == 2:
        if paired:
            return "wilcoxon" if not norm_ok else "t_test_rel"
        if norm_ok and homo_ok:
            return "t_test_ind"
        return "mann_whitney" if not norm_ok else "t_test_welch"
    if paired:
        return "friedman" if not norm_ok else "rm_anova"
    return "kruskal" if not norm_ok else "anova"
