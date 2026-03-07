"""
Advanced Statistics Module: Bayesian factors, p-value corrections, effect sizes.

Ported from run_diamag_full.py to bring expert-level statistics to AI system.
"""
import math
import numpy as np
import pandas as pd
from scipy import stats
from typing import List, Dict, Any, Optional, Tuple


# ============================================================
# BAYESIAN FACTORS
# ============================================================

def bayes_factor_from_p(p_value: float) -> float:
    """
    Calculate BF10 from p-value using Sellke bound.
    
    The Sellke bound provides a lower bound for Bayes factor.
    
    Interpretation:
        BF10 > 100: Extreme evidence for H1
        BF10 > 30: Very strong evidence
        BF10 > 10: Strong evidence
        BF10 > 3: Moderate evidence
        BF10 > 1: Anecdotal evidence
        BF10 < 1: Evidence for H0
    """
    if p_value is None or not np.isfinite(p_value) or p_value <= 0 or p_value >= 1:
        return float('nan')
    try:
        bf = min(-1 / (np.e * p_value * np.log(p_value)), 1000)
        return float(bf)
    except:
        return float('nan')


def interpret_bf10(bf10: float) -> str:
    """Interpret Bayes factor strength."""
    if not np.isfinite(bf10):
        return "неопределённо"
    if bf10 > 100:
        return "крайне сильно за H1"
    if bf10 > 30:
        return "очень сильно за H1"
    if bf10 > 10:
        return "сильно за H1"
    if bf10 > 3:
        return "умеренно за H1"
    if bf10 > 1:
        return "слабо за H1"
    if bf10 > 0.33:
        return "неопределённо"
    if bf10 > 0.1:
        return "умеренно за H0"
    if bf10 > 0.03:
        return "сильно за H0"
    return "очень сильно за H0"


# ============================================================
# MULTIPLE COMPARISON CORRECTIONS
# ============================================================

def holm_adjust(p_values: List[float]) -> List[float]:
    """
    Holm-Bonferroni step-down correction for multiple comparisons.
    
    More powerful than Bonferroni while still controlling FWER.
    """
    n = len(p_values)
    if n == 0:
        return []
    
    # Create index-value pairs and sort by p-value
    indexed = [(i, p) for i, p in enumerate(p_values)]
    sorted_indexed = sorted(indexed, key=lambda x: x[1])
    
    adjusted = [0.0] * n
    cumulative_max = 0.0
    
    for rank, (original_idx, p) in enumerate(sorted_indexed):
        # Holm multiplier: m - rank (1-indexed)
        multiplier = n - rank
        adj_p = p * multiplier
        
        # Ensure monotonicity
        cumulative_max = max(cumulative_max, adj_p)
        adjusted[original_idx] = min(cumulative_max, 1.0)
    
    return adjusted


def bonferroni_adjust(p_values: List[float]) -> List[float]:
    """Simple Bonferroni correction."""
    n = len(p_values)
    return [min(p * n, 1.0) for p in p_values]


def fdr_adjust(p_values: List[float]) -> List[float]:
    """
    Benjamini-Hochberg FDR correction.
    
    Less conservative than Holm, controls False Discovery Rate.
    """
    n = len(p_values)
    if n == 0:
        return []
    
    indexed = [(i, p) for i, p in enumerate(p_values)]
    sorted_indexed = sorted(indexed, key=lambda x: x[1], reverse=True)
    
    adjusted = [0.0] * n
    cumulative_min = 1.0
    
    for rank_from_end, (original_idx, p) in enumerate(sorted_indexed):
        rank = n - rank_from_end  # 1-indexed rank from smallest
        adj_p = p * n / rank
        cumulative_min = min(cumulative_min, adj_p)
        adjusted[original_idx] = min(cumulative_min, 1.0)
    
    return adjusted


# ============================================================
# EFFECT SIZES
# ============================================================

def cohens_d(group1: pd.Series, group2: pd.Series) -> float:
    """
    Cohen's d effect size for two independent groups.
    
    Uses pooled standard deviation.
    """
    g1 = group1.dropna()
    g2 = group2.dropna()
    
    n1, n2 = len(g1), len(g2)
    if n1 < 2 or n2 < 2:
        return float('nan')
    
    mean_diff = g1.mean() - g2.mean()
    pooled_var = ((n1 - 1) * g1.var() + (n2 - 1) * g2.var()) / (n1 + n2 - 2)
    pooled_std = np.sqrt(pooled_var)
    
    if pooled_std == 0:
        return float('nan')
    
    return float(mean_diff / pooled_std)


def hedges_g(group1: pd.Series, group2: pd.Series) -> float:
    """
    Hedges' g - bias-corrected Cohen's d for small samples.
    """
    d = cohens_d(group1, group2)
    if not np.isfinite(d):
        return float('nan')
    
    n1, n2 = len(group1.dropna()), len(group2.dropna())
    df = n1 + n2 - 2
    
    # Correction factor
    j = 1 - (3 / (4 * df - 1))
    return float(d * j)


def rank_biserial_r(group1: pd.Series, group2: pd.Series) -> float:
    """
    Rank-biserial correlation effect size for Mann-Whitney U.
    
    Range: -1 to +1
    """
    g1 = group1.dropna()
    g2 = group2.dropna()
    
    n1, n2 = len(g1), len(g2)
    if n1 < 2 or n2 < 2:
        return float('nan')
    
    try:
        U, _ = stats.mannwhitneyu(g1, g2, alternative='two-sided')
        r = 1 - (2 * U) / (n1 * n2)
        return float(r)
    except:
        return float('nan')


def epsilon_squared(H_statistic: float, n_total: int, k_groups: int) -> float:
    """
    Epsilon squared effect size for Kruskal-Wallis test.
    
    Range: 0 to 1
    """
    if n_total <= k_groups:
        return float('nan')
    
    eps_sq = (H_statistic - k_groups + 1) / (n_total - k_groups)
    return float(max(0, eps_sq))


def interpret_effect_size(es: float, es_type: str = "d") -> str:
    """
    Interpret effect size magnitude.
    
    Args:
        es: Effect size value
        es_type: 'd' (Cohen's d), 'r' (correlation), 'eta' (eta squared)
    """
    if not np.isfinite(es):
        return "неопределённо"
    
    abs_es = abs(es)
    
    if es_type in ("d", "g"):  # Cohen's d / Hedges' g
        if abs_es >= 0.8:
            return "большой"
        if abs_es >= 0.5:
            return "средний"
        if abs_es >= 0.2:
            return "малый"
        return "незначительный"
    
    elif es_type == "r":  # Correlation
        if abs_es >= 0.5:
            return "большой"
        if abs_es >= 0.3:
            return "средний"
        if abs_es >= 0.1:
            return "малый"
        return "незначительный"
    
    elif es_type in ("eta", "eta_sq", "epsilon_sq"):  # Variance explained
        if abs_es >= 0.14:
            return "большой"
        if abs_es >= 0.06:
            return "средний"
        if abs_es >= 0.01:
            return "малый"
        return "незначительный"
    
    return "неопределённо"


# ============================================================
# FULL DESCRIPTIVE STATISTICS
# ============================================================

def descriptive_stats(values: pd.Series) -> Dict[str, Any]:
    """
    Comprehensive descriptive statistics.
    
    Returns all standard measures for clinical reporting.
    """
    clean = values.dropna()
    n = len(clean)
    
    if n == 0:
        return {"n": 0, "error": "No data"}
    
    result = {
        "n": n,
        "mean": float(clean.mean()),
        "sd": float(clean.std()),
        "se": float(clean.std() / np.sqrt(n)) if n > 1 else float('nan'),
        "median": float(clean.median()),
        "q1": float(clean.quantile(0.25)),
        "q3": float(clean.quantile(0.75)),
        "iqr": float(clean.quantile(0.75) - clean.quantile(0.25)),
        "min": float(clean.min()),
        "max": float(clean.max()),
        "range": float(clean.max() - clean.min()),
    }
    
    # Additional stats for larger samples
    if n > 2:
        result["skewness"] = float(clean.skew())
    if n > 3:
        result["kurtosis"] = float(clean.kurtosis())
    
    # 95% CI for mean
    if n > 1:
        ci_margin = 1.96 * result["se"]
        result["ci_95_lower"] = result["mean"] - ci_margin
        result["ci_95_upper"] = result["mean"] + ci_margin
    
    return result


# ============================================================
# PAIRWISE COMPARISONS WITH FULL STATS
# ============================================================

def pairwise_mann_whitney(
    df: pd.DataFrame,
    value_col: str,
    group_col: str
) -> Dict[str, Dict[str, Any]]:
    """
    All pairwise Mann-Whitney U tests with effect sizes and BF10.
    
    Returns p-values (raw and Holm-adjusted), effect sizes, and Bayes factors.
    """
    groups = df[group_col].dropna().unique()
    if len(groups) < 2:
        return {"error": "Need at least 2 groups"}
    
    results = {}
    raw_p_values = []
    pair_keys = []
    
    # First pass: collect all p-values
    for i, g1 in enumerate(groups):
        for g2 in groups[i+1:]:
            data1 = df[df[group_col] == g1][value_col].dropna()
            data2 = df[df[group_col] == g2][value_col].dropna()
            
            if len(data1) < 2 or len(data2) < 2:
                continue
            
            try:
                U, p = stats.mannwhitneyu(data1, data2, alternative='two-sided')
                
                # Effect size
                n1, n2 = len(data1), len(data2)
                r = 1 - (2 * U) / (n1 * n2)
                
                # Difference metrics
                diff_median = float(data1.median() - data2.median())
                baseline = data2.median() if data2.median() != 0 else 1
                diff_pct = float((diff_median / baseline) * 100)
                
                pair_key = f"{g1}_vs_{g2}"
                pair_keys.append(pair_key)
                raw_p_values.append(p)
                
                results[pair_key] = {
                    "U": float(U),
                    "p_raw": float(p),
                    "n1": n1,
                    "n2": n2,
                    "r": float(r),
                    "r_interpretation": interpret_effect_size(r, "r"),
                    "diff_median": diff_median,
                    "diff_pct": diff_pct,
                    "bf10": bayes_factor_from_p(p),
                    "bf10_interpretation": interpret_bf10(bayes_factor_from_p(p)),
                    "group1_median": float(data1.median()),
                    "group2_median": float(data2.median()),
                }
            except Exception as e:
                results[f"{g1}_vs_{g2}"] = {"error": str(e)}
    
    # Apply Holm correction
    if raw_p_values:
        adjusted = holm_adjust(raw_p_values)
        for i, key in enumerate(pair_keys):
            if key in results and "error" not in results[key]:
                results[key]["p_adj"] = adjusted[i]
                results[key]["significant"] = adjusted[i] < 0.05
    
    return results


# ============================================================
# KRUSKAL-WALLIS WITH EFFECT SIZE
# ============================================================

def kruskal_wallis_test(
    df: pd.DataFrame,
    value_col: str,
    group_col: str
) -> Dict[str, Any]:
    """
    Kruskal-Wallis H-test with epsilon squared effect size.
    """
    # Get unique groups and their data
    groups = df[group_col].dropna().unique()
    valid_groups = []
    
    for g in groups:
        data = df[df[group_col] == g][value_col].dropna()
        if len(data) > 0:
            valid_groups.append(data)
    
    if len(valid_groups) < 2:
        return {"error": "Not enough groups"}
    
    try:
        H, p = stats.kruskal(*valid_groups)
        
        n_total = sum(len(g) for g in valid_groups)
        k = len(valid_groups)
        eps_sq = epsilon_squared(H, n_total, k)
        
        return {
            "H": float(H),
            "p": float(p),
            "epsilon_sq": eps_sq,
            "epsilon_interpretation": interpret_effect_size(eps_sq, "epsilon_sq"),
            "significant": p < 0.05,
            "n_groups": k,
            "n_total": n_total,
            "bf10": bayes_factor_from_p(p),
            "bf10_interpretation": interpret_bf10(bayes_factor_from_p(p)),
        }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# WILCOXON PAIRED TEST
# ============================================================

def wilcoxon_paired(
    before: pd.Series,
    after: pd.Series,
    threshold_pct: float = 0.20
) -> Dict[str, Any]:
    """
    Wilcoxon signed-rank test for paired data with responder analysis.
    
    Args:
        threshold_pct: Threshold for responder (default 20% improvement)
    """
    # Align data
    combined = pd.DataFrame({"before": before, "after": after}).dropna()
    
    if len(combined) < 5:
        return {"error": "Need at least 5 paired observations"}
    
    b = combined["before"]
    a = combined["after"]
    diff = a - b
    
    try:
        W, p = stats.wilcoxon(b, a)
        
        # Effect size: r = Z / sqrt(N)
        n = len(combined)
        z = stats.norm.ppf(p / 2) if p > 0 else 0
        r = abs(z) / np.sqrt(n)
        
        # Responder analysis
        pct_change = ((a - b) / b.abs().replace(0, 1)) * 100
        responders = (pct_change <= -threshold_pct * 100).sum()  # Improvement = decrease
        responder_rate = responders / n * 100
        
        return {
            "W": float(W),
            "p": float(p),
            "r": float(r),
            "r_interpretation": interpret_effect_size(r, "r"),
            "significant": p < 0.05,
            "n_pairs": n,
            "mean_diff": float(diff.mean()),
            "median_diff": float(diff.median()),
            "sd_diff": float(diff.std()),
            "bf10": bayes_factor_from_p(p),
            "bf10_interpretation": interpret_bf10(bayes_factor_from_p(p)),
            "responders": {
                "n": int(responders),
                "rate_pct": float(responder_rate),
                "threshold": f"≥{int(threshold_pct*100)}% improvement",
            },
        }
    except Exception as e:
        return {"error": str(e)}
