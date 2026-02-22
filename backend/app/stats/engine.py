from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import pingouin as pg
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.oneway import anova_oneway
from statsmodels.stats.multitest import multipletests
from sklearn.metrics import roc_curve, auc
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from app.stats.registry import METHODS
from app.core.logging import logger

# Import new engines
from app.stats.mixed_effects import MixedEffectsEngine, RepeatedMeasuresEngine
from app.stats.clustered_correlation import ClusteredCorrelationEngine
from app.stats.assumptions import recommend_test

GROUP_TESTS = ["t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon", "anova", "anova_welch", "kruskal"]

def _recommend_group_test(group_count: int, is_paired: bool, normality_ok: bool, homogeneity_ok: bool) -> Optional[str]:
    if group_count < 2:
        return None

    rec = recommend_test(group_count, bool(is_paired), bool(normality_ok), bool(homogeneity_ok))
    if rec == "anova" and not homogeneity_ok:
        return "anova_welch"
    return rec

def _extract_ci_bounds(ci_value):
    if ci_value is None:
        return None, None

    if isinstance(ci_value, (list, tuple, np.ndarray)) and len(ci_value) == 2:
        try:
            return float(ci_value[0]), float(ci_value[1])
        except Exception:
            return None, None

    if isinstance(ci_value, str):
        import re

        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", ci_value)
        if len(nums) >= 2:
            try:
                return float(nums[0]), float(nums[1])
            except Exception:
                return None, None

    return None, None


def _bf10_from_p_value_bound(p_value: Any) -> Optional[float]:
    try:
        if p_value is None:
            return None
        p = float(p_value)
        if not np.isfinite(p) or p <= 0.0 or p >= 1.0:
            return None
    except Exception:
        return None

    try:
        if p >= (1.0 / float(np.e)):
            return 1.0
        bf01_min = -float(np.e) * p * float(np.log(p))
        if not np.isfinite(bf01_min) or bf01_min <= 0.0:
            return None
        return float(1.0 / bf01_min)
    except Exception:
        return None


def interpret_effect_size(effect_size: float, effect_size_name: str) -> dict:
    """
    Interpret effect size with Cohen's thresholds.
    Returns dict with interpretation label and description.
    
    Thresholds based on Cohen (1988) and common conventions:
    - Cohen's d: 0.2 (small), 0.5 (medium), 0.8 (large)
    - Eta-squared/Partial η²: 0.01 (small), 0.06 (medium), 0.14 (large)
    - r/RBC: 0.1 (small), 0.3 (medium), 0.5 (large)
    - Cramér's V (df=1): 0.1 (small), 0.3 (medium), 0.5 (large)
    - Epsilon-squared: uses eta-squared thresholds
    """
    if effect_size is None or effect_size_name is None:
        return None
    
    abs_es = abs(effect_size)
    name_lower = effect_size_name.lower().replace("-", "_").replace(" ", "_")
    
    # Cohen's d and related (Hedges' g, Glass' delta)
    if name_lower in ["cohen_d", "cohens_d", "cohen", "hedges_g", "hedges", "glass_delta", "glass", "d"]:
        if abs_es < 0.2:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.5:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.8:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        es_label = "Cohen's d"
        if "hedges" in name_lower:
            es_label = "Hedges' g"
        elif "glass" in name_lower:
            es_label = "Glass's Δ"

        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.2, "medium": 0.5, "large": 0.8},
            "description": f"{es_label} = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"{es_label} = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Eta-squared, Partial eta-squared, Epsilon-squared
    elif name_lower in ["eta2", "eta_sq", "eta_squared", "np2", "partial_eta2", "partial_eta_squared", "eps_sq", "epsilon_squared", "omega_squared", "omega2"]:
        if abs_es < 0.01:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.06:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.14:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        metric_name = "η²" if "eta" in name_lower else "ε²"
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.01, "medium": 0.06, "large": 0.14},
            "description": f"{metric_name} = {effect_size:.3f} indicates a {label} effect",
            "description_ru": f"{metric_name} = {effect_size:.3f} указывает на {label_ru} эффект"
        }
    
    # Correlation coefficient (r), Rank-biserial (RBC), Point-biserial
    elif name_lower in ["r", "rbc", "rank_biserial", "point_biserial", "phi", "spearman", "pearson"]:
        if abs_es < 0.1:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.3:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.5:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.1, "medium": 0.3, "large": 0.5},
            "description": f"r = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"r = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Cramér's V
    elif name_lower in ["cramers_v", "cramer_v", "v"]:
        if abs_es < 0.1:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 0.3:
            label = "small"
            label_ru = "малый"
        elif abs_es < 0.5:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.1, "medium": 0.3, "large": 0.5},
            "description": f"Cramér's V = {effect_size:.2f} indicates a {label} association",
            "description_ru": f"Cramér's V = {effect_size:.2f} указывает на {label_ru} связь"
        }
    
    # Odds ratio (log scale interpretation)
    elif name_lower in ["odds_ratio", "or"]:
        # Odds ratio: 1.5 small, 2.5 medium, 4.3 large (Chen et al., 2010)
        if abs_es < 1.5:
            label = "trivial"
            label_ru = "пренебрежимо малый"
        elif abs_es < 2.5:
            label = "small"
            label_ru = "малый"
        elif abs_es < 4.3:
            label = "medium"
            label_ru = "средний"
        else:
            label = "large"
            label_ru = "большой"
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 1.5, "medium": 2.5, "large": 4.3},
            "description": f"OR = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"OR = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Unknown effect size type - provide generic interpretation
    else:
        return {
            "label": "unknown",
            "label_ru": "неизвестный",
            "thresholds": None,
            "description": f"{effect_size_name} = {effect_size:.3f}",
            "description_ru": f"{effect_size_name} = {effect_size:.3f}"
        }



def _format_posthoc_results(posthoc_df: pd.DataFrame, alpha: float) -> Optional[List[Dict[str, Any]]]:
    if posthoc_df is None or getattr(posthoc_df, "empty", True):
        return None

    out: List[Dict[str, Any]] = []
    for _, row in posthoc_df.iterrows():
        group1 = row.get("A", None)
        group2 = row.get("B", None)

        p_value = (
            row.get("p-tukey", None)
            if "p-tukey" in row
            else row.get("pval", None)
            if "pval" in row
            else row.get("p-unc", None)
            if "p-unc" in row
            else row.get("p-corr", None)
        )

        ci_lower, ci_upper = _extract_ci_bounds(row.get("CI95%", None))

        diff = row.get("diff", None)
        if diff is None and ("mean(A)" in row and "mean(B)" in row):
            try:
                diff = float(row["mean(A)"]) - float(row["mean(B)"])
            except Exception:
                diff = None

        try:
            p_value_f = float(p_value) if p_value is not None else None
        except Exception:
            p_value_f = None

        out.append(
            {
                "group1": str(group1) if group1 is not None else None,
                "group2": str(group2) if group2 is not None else None,
                "diff": float(diff) if diff is not None else None,
                "p_value": p_value_f,
                "ci_lower": ci_lower,
                "ci_upper": ci_upper,
                "significant": (p_value_f < alpha) if p_value_f is not None else None,
            }
        )

    return out


def _apply_posthoc_correction(post_hoc: Optional[List[Dict[str, Any]]], alpha: float, correction: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(post_hoc, list) or not post_hoc:
        return post_hoc
    corr = str(correction or '').strip().lower()
    if not corr or corr == 'none':
        return post_hoc

    method = None
    if corr in {'bh', 'fdr_bh'}:
        method = 'fdr_bh'
    elif corr in {'bky', 'fdr_tsbky'}:
        method = 'fdr_tsbky'
    elif corr in {'by', 'fdr_by'}:
        method = 'fdr_by'
    elif corr in {'bonferroni', 'bonf'}:
        method = 'bonferroni'
    elif corr in {'holm'}:
        method = 'holm'
    elif corr in {'sidak'}:
        method = 'sidak'
    elif corr in {'holm-sidak', 'holmsidak', 'holm_sidak'}:
        method = 'holm-sidak'

    if not method:
        return post_hoc

    pvals = []
    idxs = []
    for i, r in enumerate(post_hoc):
        try:
            p = r.get('p_value', None)
            pf = float(p)
            if not np.isfinite(pf):
                continue
            pvals.append(pf)
            idxs.append(i)
        except Exception:
            continue

    if not pvals:
        return post_hoc

    reject, pvals_corrected, _, _ = multipletests(pvals, alpha=alpha, method=method)
    out = [dict(r) for r in post_hoc]
    for j, i in enumerate(idxs):
        out[i]['p_value_adj'] = float(pvals_corrected[j])
        out[i]['significant_adj'] = bool(reject[j])
        out[i]['correction'] = method
    return out


def _run_dunn_posthoc(data_groups: List[pd.Series], groups: List[Any], alpha: float = 0.05) -> Optional[List[Dict[str, Any]]]:
    cleaned = []
    cleaned_groups = []
    for i, g in enumerate(groups):
        s = data_groups[i]
        if s is None:
            continue
        vals = pd.Series(s).dropna().to_numpy()
        if vals.size == 0:
            continue
        cleaned.append(vals)
        cleaned_groups.append(g)

    if len(cleaned) < 2:
        return None

    all_vals = np.concatenate(cleaned)
    labels = []
    for i, g in enumerate(cleaned_groups):
        labels.extend([g] * cleaned[i].size)
    labels = np.array(labels, dtype=object)

    n_total = int(all_vals.size)
    if n_total < 3:
        return None

    ranks = stats.rankdata(all_vals, method='average')

    _, counts = np.unique(all_vals, return_counts=True)
    tie_counts = counts[counts > 1]
    if tie_counts.size > 0:
        tie_sum = float(np.sum(np.power(tie_counts, 3) - tie_counts))
        denom = float(n_total ** 3 - n_total)
        tie_c = 1.0 - (tie_sum / denom if denom != 0 else 0.0)
    else:
        tie_c = 1.0

    base = (n_total * (n_total + 1) / 12.0) * tie_c
    if base <= 0:
        return None

    mean_ranks = {}
    ns = {}
    for g in cleaned_groups:
        mask = labels == g
        rg = ranks[mask]
        if rg.size == 0:
            continue
        mean_ranks[g] = float(np.mean(rg))
        ns[g] = int(rg.size)

    out: List[Dict[str, Any]] = []
    for i in range(len(cleaned_groups)):
        for j in range(i + 1, len(cleaned_groups)):
            a = cleaned_groups[i]
            b = cleaned_groups[j]
            na = ns.get(a, 0)
            nb = ns.get(b, 0)
            if na <= 0 or nb <= 0:
                continue
            se = np.sqrt(base * (1.0 / na + 1.0 / nb))
            if not np.isfinite(se) or se <= 0:
                continue
            z = (mean_ranks[a] - mean_ranks[b]) / se
            p = float(2.0 * stats.norm.sf(abs(float(z))))
            out.append(
                {
                    'group1': str(a),
                    'group2': str(b),
                    'diff': float(mean_ranks[a] - mean_ranks[b]),
                    'p_value': p,
                    'ci_lower': None,
                    'ci_upper': None,
                    'significant': bool(p < alpha),
                }
            )
    return out if out else None

def check_normality(data: pd.Series) -> tuple[Optional[bool], Optional[float], Optional[float]]:
    """
    Shapiro-Wilk test for normality.
    Returns (is_normal, p_value, statistic).
    """
    clean_data = data.replace([np.inf, -np.inf], np.nan).dropna()
    n = int(len(clean_data))
    if n < 3 or n > 5000:
        return None, None, None

    try:
        stat, p_value = stats.shapiro(clean_data)
        return bool(p_value > 0.05), float(p_value), float(stat)
    except Exception:
        return None, None, None

def check_homogeneity(groups_data: List[pd.Series]) -> tuple[Optional[bool], Optional[float], Optional[float]]:
    """
    Levene's test for homogeneity of variances.
    Returns (equal_var, p_value, statistic).
    """
    if len(groups_data) < 2:
        return None, None, None

    cleaned_groups: List[pd.Series] = []
    for g in groups_data:
        clean = g.replace([np.inf, -np.inf], np.nan).dropna()
        if len(clean) < 2:
            return None, None, None
        cleaned_groups.append(clean)

    try:
        stat, p_value = stats.levene(*cleaned_groups)
        return bool(p_value > 0.05), float(p_value), float(stat)
    except Exception:
        return None, None, None

def select_test(
    df: pd.DataFrame, 
    col_a: str, 
    col_b: str, 
    types: Dict[str, str],
    is_paired: bool = False
) -> str:
    """
    Auto-detects the best statistical test based on data properties.
    """
    type_a = types.get(col_a)
    type_b = types.get(col_b)
    
    # 1. Numeric vs Numeric -> Correlation
    if type_a == "numeric" and type_b == "numeric":
        is_norm_a, _, _ = check_normality(df[col_a])
        is_norm_b, _, _ = check_normality(df[col_b])
        return "pearson" if (is_norm_a is True and is_norm_b is True) else "spearman"

    # 2. Categorical vs Categorical -> Chi-Square
    if type_a == "categorical" and type_b == "categorical":
        return "chi_square"

    # 3. Numeric vs Categorical -> Group Comparison
    num_col = col_a if type_a == "numeric" else col_b
    cat_col = col_b if type_a == "numeric" else col_a
    
    groups = df[cat_col].dropna().unique()
    if len(groups) < 2:
        return None
        
    all_normal = True
    groups_data = []
    
    for g in groups:
        subset = df[df[cat_col] == g][num_col].dropna()
        is_normal, _, _ = check_normality(subset)
        if is_normal is False:
            all_normal = False
        groups_data.append(subset)
            
    if len(groups) == 2:
        if is_paired:
            return "t_test_rel" if all_normal else "wilcoxon"
        
        # Check Homogeneity for Independent
        equal_var, _, _ = check_homogeneity(groups_data)
        if equal_var is None:
            equal_var = True
        
        if not all_normal:
            return "mann_whitney"
        elif not equal_var:
            return "t_test_welch"
        else:
            return "t_test_ind"
    else:
        # 3+ groups
        return "anova" if all_normal else "kruskal"

def _run_analysis_python(
    df: pd.DataFrame, 
    method_id: str, 
    col_a: str, 
    col_b: str,
    is_paired: bool = False,
    alpha: float = 0.05,
    **kwargs
) -> Dict[str, Any]:
    """
    Executes a specific statistical test.
    alpha: significance level threshold (default 0.05)
    """
    kwargs["alpha"] = alpha
    # Robust numeric/categorical identification
    # Identify involved columns for cleaning
    input_cols = [col_a]
    if col_b: input_cols.append(col_b)
    if kwargs.get("group_col"): input_cols.append(kwargs.get("group_col"))
    if kwargs.get("predictors"): input_cols.extend(kwargs.get("predictors"))
    
    # Uniqify and Filter non-existent columns
    input_cols = list(set([c for c in input_cols if c and c in df.columns]))
    clean_df = df[input_cols].dropna()
    methods_using_full_df = {
        "mixed_model",
        "mixed_effects",
        "rm_anova",
        "friedman",
        "anova_twoway",
        "clustered_correlation",
        "cluster_profiles",
        "external_validation",
    }
    if clean_df.empty and method_id not in methods_using_full_df:
        raise ValueError("Недостаточно данных после очистки (все строки содержат пропуски).")
    
    # Handle 'auto' method selection
    if method_id == "auto":
        types = {}
        for col in [col_a, col_b]:
            if col and col in df.columns:
                s = df[col]
                name_l = str(col).strip().lower()
                if pd.api.types.is_numeric_dtype(s):
                    try:
                        non_na = s.dropna()
                        n = int(len(non_na))
                        unique = int(non_na.nunique(dropna=True)) if n else 0
                    except Exception:
                        n = int(len(s))
                        try:
                            unique = int(s.nunique(dropna=True))
                        except Exception:
                            unique = 0

                    ratio = float(unique) / float(max(1, n))
                    looks_like_group = any(
                        k in name_l
                        for k in [
                            "группа",
                            "group",
                            "treatment",
                            "arm",
                            "cohort",
                            "класс",
                            "категор",
                            "category",
                            "групп",
                            "рандом",
                        ]
                    )
                    if (unique and unique <= 12 and ratio <= 0.2) or (looks_like_group and unique and unique <= 50):
                        types[col] = "categorical"
                    else:
                        types[col] = "numeric"
                else:
                    types[col] = "categorical"
        
        # Auto-select the best test
        method_id = select_test(df, col_a, col_b, types, is_paired)
        if method_id is None:
            raise ValueError("Could not auto-detect appropriate statistical test. Please select manually.")

    requested_method_id = method_id

    if method_id in GROUP_TESTS:
        if col_a not in clean_df.columns or col_b not in clean_df.columns:
            raise ValueError("Не найдены колонки для группового сравнения.")
        if clean_df.shape[0] < 2:
            raise ValueError("Недостаточно наблюдений для группового сравнения.")
        auto_fallback = bool(kwargs.get("auto_fallback", True))

        groups = sorted(clean_df[col_b].unique()) if col_b in clean_df.columns else []
        data_groups = [clean_df[clean_df[col_b] == g][col_a] for g in groups] if groups else []
        assumptions = _check_assumptions(groups, data_groups) if groups else {}
        warnings = _generate_warnings(str(requested_method_id).strip(), path_type="group", assumptions=assumptions)

        norm_res = assumptions.get("normality") if isinstance(assumptions, dict) else None
        normality_state: str = "unknown"
        if isinstance(norm_res, dict) and norm_res:
            passed_vals = [v.get("passed") for v in norm_res.values() if isinstance(v, dict)]
            if any(v is False for v in passed_vals):
                normality_state = "failed"
            elif any(v is None for v in passed_vals):
                normality_state = "unknown"
            else:
                normality_state = "passed"

        homo_res = assumptions.get("homogeneity") if isinstance(assumptions, dict) else None
        homogeneity_state: str = "unknown"
        if isinstance(homo_res, dict) and ("passed" in homo_res):
            if homo_res.get("passed") is False:
                homogeneity_state = "failed"
            elif homo_res.get("passed") is True:
                homogeneity_state = "passed"
            else:
                homogeneity_state = "unknown"

        recommended: Optional[str] = None
        if normality_state != "unknown" and homogeneity_state != "unknown":
            recommended = _recommend_group_test(
                len(groups),
                bool(is_paired),
                normality_state == "passed",
                homogeneity_state == "passed",
            )

        method_used = recommended if (auto_fallback and recommended and recommended != requested_method_id) else requested_method_id

        if method_used != requested_method_id:
            warnings.append(f"Auto-fallback used: {requested_method_id} → {method_used}.")

        out = _handle_group_comparison(clean_df, method_used, col_a, col_b, kwargs)
        out["method_requested"] = requested_method_id
        out["method_used"] = method_used
        out["recommended_method"] = recommended
        out["assumptions"] = assumptions
        out["assumption_checks"] = assumptions
        out["warnings"] = warnings
        out["assumption_warning"] = " ".join([str(w) for w in warnings]) if warnings else None
        return out
    
    # Dispatcher
    if method_id in GROUP_TESTS:
        return _handle_group_comparison(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "t_test_one":
        return _handle_one_sample(clean_df, method_id, col_a, kwargs)

    elif method_id in ["pearson", "spearman"]:
        return _handle_correlation(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "chi_square":
        return _handle_chi_square(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id in ["fisher", "fisher_exact"]:
        return _handle_fisher_exact(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "survival_km":
        return _handle_survival(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id in ["linear_regression", "logistic_regression"]:
        return _handle_regression(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "roc_analysis":
        return _handle_roc_analysis(clean_df, method_id, col_a, col_b)

    elif method_id in ["random_forest", "gradient_boosting", "knn", "svm"]:
        return _handle_ml(df, method_id, col_a, col_b, kwargs)

    elif method_id in ["mixed_model", "mixed_effects"]:
        return _handle_mixed_effects(df, col_a, col_b, kwargs)

    elif method_id == "rm_anova":
        return _handle_rm_anova(df, col_a, kwargs)

    elif method_id == "friedman":
        return _handle_friedman(df, col_a, kwargs)

    elif method_id == "anova_twoway":
        return _handle_anova_twoway(df, col_a, kwargs)

    elif method_id == "clustered_correlation":
        return _handle_clustered_correlation(df, kwargs)

    elif method_id == "bootstrap_pipeline":
        return _handle_bootstrap_pipeline(df, col_a, col_b, kwargs)

    elif method_id == "cluster_profiles":
        return _handle_cluster_profiles(df, kwargs)

    elif method_id == "external_validation":
        return _handle_external_validation(df, col_a, col_b, kwargs)

    raise ValueError(f"Method {method_id} not implemented")


def _roc_payload(y_true_bin: np.ndarray, y_score: np.ndarray) -> Dict[str, Any]:
    fpr, tpr, thresholds = roc_curve(y_true_bin, y_score)
    roc_auc = auc(fpr, tpr)

    roc_data = []
    step = max(1, len(fpr) // 500)
    for i in range(0, len(fpr), step):
        roc_data.append({
            "x": float(fpr[i]),
            "y": float(tpr[i]),
            "threshold": float(thresholds[i]),
        })
    if roc_data and roc_data[-1]["x"] != float(fpr[-1]):
        roc_data.append({"x": float(fpr[-1]), "y": float(tpr[-1]), "threshold": float(thresholds[-1])})

    return {
        "auc": float(roc_auc),
        "plot_data": roc_data,
        "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"},
    }


def _handle_ml(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        r2_score,
        mean_absolute_error,
        mean_squared_error,
        accuracy_score,
        f1_score,
        precision_score,
        recall_score,
    )
    from sklearn.ensemble import (
        RandomForestRegressor,
        RandomForestClassifier,
        GradientBoostingRegressor,
        GradientBoostingClassifier,
    )
    from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
    from sklearn.svm import SVR, SVC
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    predictors = kwargs.get("predictors")
    if predictors is None:
        predictors = [col_b] if col_b else []
    if not isinstance(predictors, list):
        predictors = [col_b] if col_b else []
    predictors = [p for p in predictors if p]

    task = str(kwargs.get("task") or "regression").strip().lower()
    random_state = kwargs.get("random_state")
    test_size = float(kwargs.get("test_size") or 0.25)
    if not (0.05 <= test_size <= 0.8):
        test_size = 0.25

    cols = [c for c in [col_a, *predictors] if c and c in df.columns]
    clean_df = df[cols].dropna()

    if col_a not in clean_df.columns:
        raise ValueError(f"Target column '{col_a}' not found")
    if not predictors:
        raise ValueError("predictors is required for ML methods")

    y_raw = clean_df[col_a]
    X_raw = clean_df[predictors]
    X = pd.get_dummies(X_raw, drop_first=True)

    if task == "classification":
        y_non_na = y_raw.dropna()
        uniq = list(pd.unique(y_non_na))
        if len(uniq) != 2:
            raise ValueError(f"Classification requires a binary target. Found {len(uniq)} unique values.")

        if pd.api.types.is_numeric_dtype(y_non_na):
            y_as_float = y_raw.astype(float)
            uniq_num = sorted(set(float(v) for v in pd.unique(y_as_float.dropna())))
            if set(uniq_num) == {0.0, 1.0}:
                y_bin = y_as_float.to_numpy()
                neg_label = "0"
                pos_label = "1"
            else:
                mapping = {uniq_num[0]: 0.0, uniq_num[1]: 1.0}
                y_bin = y_as_float.map(mapping).to_numpy()
                neg_label = str(uniq_num[0])
                pos_label = str(uniq_num[1])
        else:
            uniq_str = sorted(str(v) for v in uniq)
            neg_label = uniq_str[0]
            pos_label = uniq_str[1]
            y_bin = y_raw.astype(str).map(lambda v: 1.0 if v == pos_label else 0.0).to_numpy()

        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y_bin,
            test_size=test_size,
            random_state=random_state,
            stratify=y_bin if len(np.unique(y_bin)) == 2 else None,
        )

        if method_id == "random_forest":
            model = RandomForestClassifier(n_estimators=200, random_state=random_state)
        elif method_id == "gradient_boosting":
            model = GradientBoostingClassifier(random_state=random_state)
        elif method_id == "knn":
            model = make_pipeline(StandardScaler(), KNeighborsClassifier(n_neighbors=int(kwargs.get("n_neighbors") or 5)))
        else:
            model = make_pipeline(
                StandardScaler(),
                SVC(
                    C=float(kwargs.get("C") or 1.0),
                    kernel=str(kwargs.get("kernel") or "rbf"),
                    probability=True,
                    random_state=random_state,
                ),
            )

        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        acc = float(accuracy_score(y_test, y_pred))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        precision = float(precision_score(y_test, y_pred, zero_division=0))
        recall = float(recall_score(y_test, y_pred, zero_division=0))

        y_score = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_test)
            if isinstance(proba, np.ndarray) and proba.ndim == 2 and proba.shape[1] >= 2:
                y_score = proba[:, 1]
        if y_score is None and hasattr(model, "decision_function"):
            y_score = model.decision_function(X_test)
        if y_score is None:
            y_score = y_pred

        roc_out = _roc_payload(np.asarray(y_test).astype(int), np.asarray(y_score, dtype=float))
        roc_out["pos_label"] = pos_label
        roc_out["neg_label"] = neg_label

        return {
            "method": method_id,
            "task": "classification",
            "accuracy": acc,
            "f1": f1,
            "precision": precision,
            "recall": recall,
            "roc": roc_out,
        }

    y = pd.to_numeric(y_raw, errors="coerce")
    if y.isna().any():
        raise ValueError("Regression requires a numeric target")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y.to_numpy(dtype=float),
        test_size=test_size,
        random_state=random_state,
    )

    if method_id == "random_forest":
        model = RandomForestRegressor(n_estimators=300, random_state=random_state)
    elif method_id == "gradient_boosting":
        model = GradientBoostingRegressor(random_state=random_state)
    elif method_id == "knn":
        model = make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=int(kwargs.get("n_neighbors") or 5)))
    else:
        model = make_pipeline(
            StandardScaler(),
            SVR(C=float(kwargs.get("C") or 1.0), kernel=str(kwargs.get("kernel") or "rbf")),
        )

    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    r2 = float(r2_score(y_test, y_pred))
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    return {
        "method": method_id,
        "task": "regression",
        "r_squared": r2,
        "mae": mae,
        "rmse": rmse,
    }


def _handle_bootstrap_pipeline(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    outcome = str(col_a or "").strip()
    if not outcome or outcome not in df.columns:
        raise ValueError("bootstrap_pipeline требует валидную outcome/target колонку")

    n_resamples = kwargs.get("n_resamples")
    if n_resamples is None:
        n_resamples = kwargs.get("n_bootstrap")
    try:
        n_boot = int(n_resamples) if n_resamples is not None else 2000
    except Exception:
        n_boot = 2000
    n_boot = int(np.clip(n_boot, 200, 20000))

    ci_level_raw = kwargs.get("ci_level")
    if ci_level_raw is None:
        ci_level_raw = kwargs.get("ci")
    try:
        ci_level = float(ci_level_raw) if ci_level_raw is not None else 0.95
    except Exception:
        ci_level = 0.95
    if not (0.5 < ci_level < 0.999):
        ci_level = 0.95

    alpha_ci = 1.0 - ci_level
    random_state = kwargs.get("random_state")
    rng = np.random.default_rng(random_state)
    statistic = str(kwargs.get("statistic") or "").strip().lower()

    if col_b and isinstance(col_b, str) and col_b in df.columns:
        local = df[[outcome, col_b]].dropna()
        groups = sorted(local[col_b].unique())
        if len(groups) != 2:
            raise ValueError("bootstrap_pipeline с group поддерживает только 2 группы")

        left = pd.to_numeric(local[local[col_b] == groups[0]][outcome], errors="coerce").dropna().to_numpy(dtype=float)
        right = pd.to_numeric(local[local[col_b] == groups[1]][outcome], errors="coerce").dropna().to_numpy(dtype=float)
        if len(left) < 3 or len(right) < 3:
            raise ValueError("Недостаточно наблюдений в одной из групп для bootstrap")

        use_median = statistic in {"median", "median_difference", "median_diff"}

        def _effect(sample_left: np.ndarray, sample_right: np.ndarray) -> float:
            if use_median:
                return float(np.nanmedian(sample_right) - np.nanmedian(sample_left))
            return float(np.nanmean(sample_right) - np.nanmean(sample_left))

        observed = _effect(left, right)
        draws = np.zeros(n_boot, dtype=float)
        for i in range(n_boot):
            res_left = rng.choice(left, size=len(left), replace=True)
            res_right = rng.choice(right, size=len(right), replace=True)
            draws[i] = _effect(res_left, res_right)

        q_low = float(np.quantile(draws, alpha_ci / 2.0))
        q_high = float(np.quantile(draws, 1.0 - alpha_ci / 2.0))
        p_left = float(np.mean(draws <= 0.0))
        p_right = float(np.mean(draws >= 0.0))
        p_value = float(min(1.0, max(0.0, 2.0 * min(p_left, p_right))))

        return {
            "method": "bootstrap_pipeline",
            "mode": "group_difference",
            "statistic": "median_difference" if use_median else "mean_difference",
            "groups": [str(groups[0]), str(groups[1])],
            "n_left": int(len(left)),
            "n_right": int(len(right)),
            "stat_value": float(observed),
            "effect_size": float(observed),
            "effect_ci_lower": q_low,
            "effect_ci_upper": q_high,
            "p_value": p_value,
            "significant": bool((q_low > 0.0) or (q_high < 0.0)),
            "bootstrap": {
                "n_resamples": int(n_boot),
                "ci_level": float(ci_level),
                "distribution_mean": float(np.mean(draws)),
                "distribution_std": float(np.std(draws, ddof=1)) if n_boot > 1 else 0.0,
                "observed_effect": float(observed),
            },
            "plot_stats": {
                str(groups[0]): {
                    "mean": float(np.mean(left)),
                    "sd": float(np.std(left, ddof=1)) if len(left) > 1 else 0.0,
                    "count": int(len(left)),
                },
                str(groups[1]): {
                    "mean": float(np.mean(right)),
                    "sd": float(np.std(right, ddof=1)) if len(right) > 1 else 0.0,
                    "count": int(len(right)),
                },
            },
        }

    values = pd.to_numeric(df[outcome], errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) < 5:
        raise ValueError("Недостаточно наблюдений для bootstrap single-sample")

    use_median = statistic in {"median", "median_single"}
    try:
        null_value = float(kwargs.get("null_value") or 0.0)
    except Exception:
        null_value = 0.0

    if use_median:
        observed_raw = float(np.nanmedian(values))
    else:
        observed_raw = float(np.nanmean(values))
    observed = float(observed_raw - null_value)

    draws = np.zeros(n_boot, dtype=float)
    for i in range(n_boot):
        sampled = rng.choice(values, size=len(values), replace=True)
        stat_val = float(np.nanmedian(sampled)) if use_median else float(np.nanmean(sampled))
        draws[i] = float(stat_val - null_value)

    q_low = float(np.quantile(draws, alpha_ci / 2.0))
    q_high = float(np.quantile(draws, 1.0 - alpha_ci / 2.0))
    p_left = float(np.mean(draws <= 0.0))
    p_right = float(np.mean(draws >= 0.0))
    p_value = float(min(1.0, max(0.0, 2.0 * min(p_left, p_right))))

    return {
        "method": "bootstrap_pipeline",
        "mode": "single_sample",
        "statistic": "median" if use_median else "mean",
        "n_observations": int(len(values)),
        "null_value": float(null_value),
        "stat_value": float(observed),
        "effect_size": float(observed),
        "effect_ci_lower": q_low,
        "effect_ci_upper": q_high,
        "p_value": p_value,
        "significant": bool((q_low > 0.0) or (q_high < 0.0)),
        "bootstrap": {
            "n_resamples": int(n_boot),
            "ci_level": float(ci_level),
            "distribution_mean": float(np.mean(draws)),
            "distribution_std": float(np.std(draws, ddof=1)) if n_boot > 1 else 0.0,
            "observed_effect": float(observed),
        },
        "plot_stats": {
            "sample": {
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
                "count": int(len(values)),
            }
        },
    }


def _handle_cluster_profiles(df: pd.DataFrame, kwargs: Dict) -> Dict[str, Any]:
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    variables = kwargs.get("variables")
    if not isinstance(variables, list):
        variables = []

    if not variables:
        variables = [str(c) for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    available = [str(v) for v in variables if isinstance(v, str) and v in df.columns]
    if len(available) < 2:
        raise ValueError("cluster_profiles требует минимум 2 числовые переменные")

    local = df[available].apply(pd.to_numeric, errors="coerce").dropna()
    if local.shape[0] < 10:
        raise ValueError("Недостаточно наблюдений для cluster_profiles")

    try:
        random_state = int(kwargs.get("random_state")) if kwargs.get("random_state") is not None else 42
    except Exception:
        random_state = 42

    scale = bool(kwargs.get("scale", True))
    matrix = local.to_numpy(dtype=float)
    if scale:
        matrix = StandardScaler().fit_transform(matrix)

    n_rows = int(local.shape[0])
    n_clusters_raw = kwargs.get("n_clusters")
    n_clusters: Optional[int] = None
    if n_clusters_raw is not None:
        try:
            n_clusters = int(n_clusters_raw)
        except Exception:
            n_clusters = None

    max_k = max(2, min(8, max(2, n_rows // 8)))
    best_score = None
    best_labels = None
    best_k = None

    if n_clusters is None:
        for k in range(2, max_k + 1):
            model = KMeans(n_clusters=k, random_state=random_state, n_init=20)
            labels = model.fit_predict(matrix)
            try:
                score = float(silhouette_score(matrix, labels))
            except Exception:
                score = None
            if score is None:
                continue
            if best_score is None or score > best_score:
                best_score = score
                best_labels = labels
                best_k = k
        if best_labels is None:
            best_k = 2
            model = KMeans(n_clusters=best_k, random_state=random_state, n_init=20)
            best_labels = model.fit_predict(matrix)
    else:
        n_clusters = int(np.clip(n_clusters, 2, max(2, min(20, n_rows // 3))))
        best_k = n_clusters
        model = KMeans(n_clusters=best_k, random_state=random_state, n_init=20)
        best_labels = model.fit_predict(matrix)
        try:
            best_score = float(silhouette_score(matrix, best_labels))
        except Exception:
            best_score = None

    labels = np.asarray(best_labels, dtype=int)
    unique_labels = sorted([int(v) for v in np.unique(labels)])
    clusters: List[Dict[str, Any]] = []
    plot_stats: Dict[str, Dict[str, Any]] = {}
    assignments: Dict[str, int] = {}

    index_list = list(local.index)
    for row_idx, cluster_id in zip(index_list, labels):
        assignments[str(row_idx)] = int(cluster_id)

    for cluster_id in unique_labels:
        mask = labels == cluster_id
        subset = local.loc[mask]
        size = int(mask.sum())
        profile: Dict[str, Dict[str, float]] = {}
        for var in available:
            values = pd.to_numeric(subset[var], errors="coerce").dropna().to_numpy(dtype=float)
            if len(values) == 0:
                continue
            profile[var] = {
                "mean": float(np.mean(values)),
                "median": float(np.median(values)),
                "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            }
        clusters.append(
            {
                "cluster": int(cluster_id),
                "size": size,
                "proportion": float(size / float(max(1, n_rows))),
                "profile": profile,
            }
        )
        plot_stats[f"Cluster {cluster_id}"] = {
            "mean": float(size),
            "sd": 0.0,
            "count": int(size),
        }

    embedding: List[Dict[str, Any]] = []
    if bool(kwargs.get("include_embedding", True)) and local.shape[1] >= 2:
        try:
            pca = PCA(n_components=2, random_state=random_state)
            xy = pca.fit_transform(matrix)
            for i in range(min(len(index_list), 2000)):
                embedding.append(
                    {
                        "row_id": str(index_list[i]),
                        "cluster": int(labels[i]),
                        "x": float(xy[i, 0]),
                        "y": float(xy[i, 1]),
                    }
                )
        except Exception:
            embedding = []

    return {
        "method": "cluster_profiles",
        "n_observations": int(n_rows),
        "n_variables": int(len(available)),
        "variables": available,
        "n_clusters": int(best_k or 0),
        "silhouette_score": float(best_score) if isinstance(best_score, (int, float)) else None,
        "stat_value": float(best_score) if isinstance(best_score, (int, float)) else None,
        "p_value": None,
        "significant": bool(isinstance(best_score, (int, float)) and best_score >= 0.25),
        "clusters": clusters,
        "cluster_assignments": assignments,
        "plot_stats": plot_stats,
        "embedding": embedding,
    }


def _handle_external_validation(df: pd.DataFrame, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    from sklearn.calibration import calibration_curve
    from sklearn.ensemble import (
        GradientBoostingClassifier,
        GradientBoostingRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
    )
    from sklearn.linear_model import LinearRegression, LogisticRegression
    from sklearn.metrics import (
        accuracy_score,
        brier_score_loss,
        confusion_matrix,
        f1_score,
        mean_absolute_error,
        mean_squared_error,
        precision_score,
        r2_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    outcome = str(col_a or "").strip()
    if not outcome or outcome not in df.columns:
        raise ValueError("external_validation требует валидную outcome/target колонку")

    external_df = kwargs.get("external_df")
    if not isinstance(external_df, pd.DataFrame):
        raise ValueError("external_validation требует внешний DataFrame (external_df)")

    predictors = kwargs.get("predictors")
    if predictors is None:
        predictors = [col_b] if col_b else []
    if not isinstance(predictors, list):
        predictors = [col_b] if col_b else []
    predictors = [str(p) for p in predictors if isinstance(p, str) and p.strip()]
    if not predictors:
        raise ValueError("external_validation требует predictors")

    missing_train = [p for p in predictors if p not in df.columns]
    missing_ext = [p for p in predictors if p not in external_df.columns]
    if missing_train:
        raise ValueError(f"В train dataset отсутствуют predictors: {', '.join(missing_train[:8])}")
    if missing_ext:
        raise ValueError(f"Во внешнем dataset отсутствуют predictors: {', '.join(missing_ext[:8])}")
    if outcome not in external_df.columns:
        raise ValueError(f"Во внешнем dataset отсутствует outcome: {outcome}")

    train_frame = df[[outcome, *predictors]].copy()
    ext_frame = external_df[[outcome, *predictors]].copy()
    train_frame = train_frame.dropna()
    ext_frame = ext_frame.dropna()
    if train_frame.shape[0] < 20:
        raise ValueError("Недостаточно наблюдений в train dataset для external_validation")
    if ext_frame.shape[0] < 10:
        raise ValueError("Недостаточно наблюдений во внешнем dataset для external_validation")

    task = str(kwargs.get("task") or "").strip().lower()
    if task not in {"classification", "regression"}:
        uniq = int(train_frame[outcome].nunique(dropna=True))
        task = "classification" if 1 < uniq <= 2 else "regression"

    model_method = str(kwargs.get("model_method") or kwargs.get("base_method") or "").strip().lower()
    if not model_method:
        model_method = "logistic_regression" if task == "classification" else "linear_regression"

    try:
        random_state = int(kwargs.get("random_state")) if kwargs.get("random_state") is not None else 42
    except Exception:
        random_state = 42
    try:
        test_size = float(kwargs.get("test_size") or 0.25)
    except Exception:
        test_size = 0.25
    if not (0.05 <= test_size <= 0.8):
        test_size = 0.25

    X_all = pd.get_dummies(train_frame[predictors], drop_first=True)
    X_ext = pd.get_dummies(ext_frame[predictors], drop_first=True)
    X_ext = X_ext.reindex(columns=X_all.columns, fill_value=0)

    if task == "classification":
        y_series = train_frame[outcome]
        ext_y_series = ext_frame[outcome]

        labels = list(pd.unique(y_series.dropna()))
        if len(labels) != 2:
            raise ValueError("external_validation(classification) требует бинарный outcome")
        labels = sorted(labels, key=lambda x: str(x))
        positive_label = kwargs.get("positive_label")
        if positive_label in labels and positive_label != labels[0]:
            labels = [labels[0], positive_label]
        neg_label = labels[0]
        pos_label = labels[1]

        mapper = {neg_label: 0, pos_label: 1}
        y_all = y_series.map(mapper)
        ext_mask = ext_y_series.isin(list(mapper.keys()))
        ext_y_series = ext_y_series[ext_mask]
        X_ext = X_ext.loc[ext_mask]
        y_ext = ext_y_series.map(mapper)

        valid_mask_train = y_all.notna()
        y_all = y_all.loc[valid_mask_train].astype(int)
        X_all = X_all.loc[valid_mask_train]
        if y_all.nunique(dropna=True) != 2:
            raise ValueError("train outcome после фильтрации перестал быть бинарным")
        if y_ext.empty:
            raise ValueError("во внешнем dataset нет валидных бинарных значений outcome")

        X_fit, X_val, y_fit, y_val = train_test_split(
            X_all,
            y_all.to_numpy(dtype=int),
            test_size=test_size,
            random_state=random_state,
            stratify=y_all.to_numpy(dtype=int),
        )

        if model_method == "random_forest":
            model = RandomForestClassifier(n_estimators=300, random_state=random_state)
        elif model_method == "gradient_boosting":
            model = GradientBoostingClassifier(random_state=random_state)
        else:
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(max_iter=2000, random_state=random_state),
            )
            model_method = "logistic_regression"

        model.fit(X_fit, y_fit)

        def _scores(matrix: pd.DataFrame) -> np.ndarray:
            if hasattr(model, "predict_proba"):
                p = model.predict_proba(matrix)
                if isinstance(p, np.ndarray) and p.ndim == 2 and p.shape[1] >= 2:
                    return np.asarray(p[:, 1], dtype=float)
            if hasattr(model, "decision_function"):
                return np.asarray(model.decision_function(matrix), dtype=float)
            pred = model.predict(matrix)
            return np.asarray(pred, dtype=float)

        y_val_score = _scores(X_val)
        y_ext_score = _scores(X_ext)
        y_val_pred = (y_val_score >= 0.5).astype(int)
        y_ext_pred = (y_ext_score >= 0.5).astype(int)

        def _auc_safe(y_true: np.ndarray, y_score: np.ndarray) -> Optional[float]:
            try:
                if len(np.unique(y_true)) < 2:
                    return None
                return float(roc_auc_score(y_true, y_score))
            except Exception:
                return None

        auc_val = _auc_safe(np.asarray(y_val, dtype=int), y_val_score)
        auc_ext = _auc_safe(np.asarray(y_ext, dtype=int), y_ext_score)

        roc_out = None
        if auc_ext is not None:
            try:
                roc_out = _roc_payload(np.asarray(y_ext, dtype=int), np.asarray(y_ext_score, dtype=float))
                roc_out["auc"] = float(auc_ext)
                roc_out["pos_label"] = str(pos_label)
                roc_out["neg_label"] = str(neg_label)
            except Exception:
                roc_out = {"auc": float(auc_ext)}

        calibration = None
        try:
            brier = float(brier_score_loss(np.asarray(y_ext, dtype=int), np.asarray(y_ext_score, dtype=float)))
            prob_true, prob_pred = calibration_curve(
                np.asarray(y_ext, dtype=int),
                np.asarray(y_ext_score, dtype=float),
                n_bins=min(10, max(3, int(len(y_ext) // 15))),
                strategy="uniform",
            )
            calibration = {
                "brier_score": brier,
                "curve": [
                    {"x": float(x), "y": float(y)}
                    for x, y in zip(prob_pred.tolist(), prob_true.tolist())
                ],
            }
        except Exception:
            calibration = None

        cm = confusion_matrix(np.asarray(y_ext, dtype=int), y_ext_pred, labels=[0, 1])

        internal_metrics = {
            "accuracy": float(accuracy_score(y_val, y_val_pred)),
            "precision": float(precision_score(y_val, y_val_pred, zero_division=0)),
            "recall": float(recall_score(y_val, y_val_pred, zero_division=0)),
            "f1": float(f1_score(y_val, y_val_pred, zero_division=0)),
            "auc": float(auc_val) if auc_val is not None else None,
        }
        external_metrics = {
            "accuracy": float(accuracy_score(y_ext, y_ext_pred)),
            "precision": float(precision_score(y_ext, y_ext_pred, zero_division=0)),
            "recall": float(recall_score(y_ext, y_ext_pred, zero_division=0)),
            "f1": float(f1_score(y_ext, y_ext_pred, zero_division=0)),
            "auc": float(auc_ext) if auc_ext is not None else None,
        }
        gap_auc = None
        if internal_metrics.get("auc") is not None and external_metrics.get("auc") is not None:
            gap_auc = float(external_metrics["auc"] - internal_metrics["auc"])

        return {
            "method": "external_validation",
            "task": "classification",
            "model_method": model_method,
            "external_dataset_id": str(kwargs.get("external_dataset_id") or ""),
            "predictors": predictors,
            "n_train": int(X_fit.shape[0]),
            "n_internal_test": int(X_val.shape[0]),
            "n_external": int(X_ext.shape[0]),
            "class_labels": {"negative": str(neg_label), "positive": str(pos_label)},
            "internal_metrics": internal_metrics,
            "external_metrics": external_metrics,
            "generalization_gap": {"auc_gap_external_minus_internal": gap_auc},
            "roc": roc_out,
            "confusion_matrix": {
                "labels": [str(neg_label), str(pos_label)],
                "values": cm.astype(int).tolist(),
            },
            "calibration": calibration,
            "stat_value": float(auc_ext) if auc_ext is not None else None,
            "p_value": None,
            "significant": bool(isinstance(auc_ext, float) and auc_ext >= 0.7),
        }

    y_train = pd.to_numeric(train_frame[outcome], errors="coerce")
    y_ext = pd.to_numeric(ext_frame[outcome], errors="coerce")
    valid_train = y_train.notna()
    valid_ext = y_ext.notna()
    y_train = y_train.loc[valid_train].astype(float)
    X_all = X_all.loc[valid_train]
    y_ext = y_ext.loc[valid_ext].astype(float)
    X_ext = X_ext.loc[valid_ext]
    if len(y_train) < 20 or len(y_ext) < 10:
        raise ValueError("Недостаточно наблюдений для regression external_validation")

    X_fit, X_val, y_fit, y_val = train_test_split(
        X_all,
        y_train.to_numpy(dtype=float),
        test_size=test_size,
        random_state=random_state,
    )

    if model_method == "random_forest":
        model = RandomForestRegressor(n_estimators=300, random_state=random_state)
    elif model_method == "gradient_boosting":
        model = GradientBoostingRegressor(random_state=random_state)
    else:
        model = LinearRegression()
        model_method = "linear_regression"

    model.fit(X_fit, y_fit)
    y_val_pred = np.asarray(model.predict(X_val), dtype=float)
    y_ext_pred = np.asarray(model.predict(X_ext), dtype=float)

    internal_metrics = {
        "r_squared": float(r2_score(y_val, y_val_pred)),
        "mae": float(mean_absolute_error(y_val, y_val_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_val, y_val_pred))),
    }
    external_metrics = {
        "r_squared": float(r2_score(y_ext, y_ext_pred)),
        "mae": float(mean_absolute_error(y_ext, y_ext_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_ext, y_ext_pred))),
    }

    plot_data = []
    n_plot = min(1000, len(y_ext_pred))
    for i in range(n_plot):
        plot_data.append({"x": float(y_ext.iloc[i]), "y": float(y_ext_pred[i])})

    return {
        "method": "external_validation",
        "task": "regression",
        "model_method": model_method,
        "external_dataset_id": str(kwargs.get("external_dataset_id") or ""),
        "predictors": predictors,
        "n_train": int(X_fit.shape[0]),
        "n_internal_test": int(X_val.shape[0]),
        "n_external": int(X_ext.shape[0]),
        "internal_metrics": internal_metrics,
        "external_metrics": external_metrics,
        "generalization_gap": {
            "r2_gap_external_minus_internal": float(external_metrics["r_squared"] - internal_metrics["r_squared"])
        },
        "plot_data": plot_data,
        "plot_config": {"x_label": "Observed", "y_label": "Predicted", "type": "scatter"},
        "stat_value": float(external_metrics["r_squared"]),
        "p_value": None,
        "significant": bool(external_metrics["r_squared"] > 0.0),
    }


def _handle_group_comparison(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    local = df[[col_a, col_b]].dropna()
    if local.empty:
        raise ValueError("Недостаточно данных для группового сравнения.")
    groups = sorted(local[col_b].unique())
    data_groups = [local[local[col_b] == g][col_a] for g in groups]
    group_counts = [int(g.dropna().shape[0]) for g in data_groups]
    nonempty_groups = sum(1 for c in group_counts if c > 0)
    if nonempty_groups < 2:
        raise ValueError("Недостаточно групп для сравнения.")
    if any(c < 2 for c in group_counts):
        raise ValueError("Недостаточно наблюдений в одной из групп.")
    
    stat_val, p_val = 0.0, 1.0
    alt = kwargs.get("alternative", "two-sided")
    eff_size = None
    eff_size_name = None
    eff_ci_lower = None
    eff_ci_upper = None
    power = None
    bf10 = None
    post_hoc_results = None
    anova_table = None
    method_str = str(method_id).strip()

    if method_str == "t_test_ind" and len(groups) == 2:
        res = pg.ttest(data_groups[0], data_groups[1], paired=False, alternative=alt, correction=False)
        stat_val = float(res["T"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        
        requested_es = kwargs.get("effect_size", "cohen")
        eff_size = None
        eff_size_name = requested_es
        
        if requested_es == "cohen":
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
        elif requested_es == "hedges":
             try:
                 eff_size = float(pg.compute_effsize(data_groups[0], data_groups[1], eftype='hedges'))
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        elif requested_es == "glass":
             try:
                 # Glass's delta: diff / sd of control group (assume group 2 is control)
                 # data_groups[1] is the second group
                 m1 = np.mean(data_groups[0])
                 m2 = np.mean(data_groups[1])
                 sd2 = np.std(data_groups[1], ddof=1)
                 eff_size = (m1 - m2) / sd2
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        else:
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
             eff_size_name = "cohen-d"

        eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
        power = float(res["power"].iloc[0]) if "power" in res.columns else None
        try:
            bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
        except Exception:
            bf10 = None
        
    elif method_str == "t_test_welch" and len(groups) == 2:
        res = pg.ttest(data_groups[0], data_groups[1], paired=False, alternative=alt, correction=True)
        stat_val = float(res["T"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        
        requested_es = kwargs.get("effect_size", "cohen")
        eff_size = None
        eff_size_name = requested_es
        
        if requested_es == "cohen":
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
        elif requested_es == "hedges":
             try:
                 eff_size = float(pg.compute_effsize(data_groups[0], data_groups[1], eftype='hedges'))
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        elif requested_es == "glass":
             try:
                 m1 = np.mean(data_groups[0])
                 m2 = np.mean(data_groups[1])
                 sd2 = np.std(data_groups[1], ddof=1)
                 eff_size = (m1 - m2) / sd2
             except Exception:
                 eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                 eff_size_name = "cohen-d" # Fallback
        else:
             eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
             eff_size_name = "cohen-d"

        eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
        power = float(res["power"].iloc[0]) if "power" in res.columns else None
        try:
            bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
        except Exception:
            bf10 = None
        
    elif method_id == "mann_whitney" and len(groups) == 2:
        res = pg.mwu(data_groups[0], data_groups[1], alternative=alt)
        stat_val = float(res["U-val"].iloc[0]) if "U-val" in res.columns else float(res["U"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        eff_size = float(res["RBC"].iloc[0]) if "RBC" in res.columns else eff_size
        eff_size_name = "rbc" if eff_size is not None else None
        
    elif method_id == "anova":
        aov = pg.anova(data=df, dv=col_a, between=col_b, detailed=True)
        row = aov[aov["Source"] == col_b].iloc[0] if "Source" in aov.columns and (aov["Source"] == col_b).any() else aov.iloc[0]
        stat_val = float(row.get("F"))
        p_val = float(row.get("p-unc"))
        
        # Calculate requested effect size
        requested_es = kwargs.get("effect_size", "eta_squared")
        eff_size = None
        eff_size_name = requested_es

        ss_between = float(row['SS'])
        ss_total = float(aov['SS'].sum()) if 'SS' in aov.columns else 0.0
        df_between = float(row['DF'])
        df_within = float(aov[aov["Source"] == "Within"]['DF'].iloc[0]) if "Within" in aov["Source"].values else float(aov['DF'].sum()) - df_between
        ms_within = float(aov[aov["Source"] == "Within"]['MS'].iloc[0]) if "Within" in aov["Source"].values else 1.0

        anova_table = aov.to_dict('records') # Added line
        
        if requested_es == "eta_squared":
             if ss_total > 0:
                 eff_size = ss_between / ss_total
        elif requested_es == "partial_eta_squared":
            # For one-way ANOVA, partial eta squared = eta squared
             if ss_total > 0:
                 eff_size = ss_between / ss_total
        elif requested_es == "omega_squared":
             if (ss_total + ms_within) > 0:
                 eff_size = (ss_between - (df_between * ms_within)) / (ss_total + ms_within)

        # Fallback if calculation failed or not requested type found in common logic
        if eff_size is None:
             if "np2" in row:
                 eff_size = float(row.get("np2"))
                 eff_size_name = "np2"
             elif "eta2" in row:
                 eff_size = float(row.get("eta2"))
                 eff_size_name = "eta2"

        alpha = kwargs.get("alpha", 0.05)
        post_hoc = str(kwargs.get('post_hoc', 'tukey') or '').strip().lower()
        post_hoc_correction = kwargs.get('post_hoc_correction', None)
        if p_val < alpha and post_hoc and post_hoc != 'none':
            if post_hoc == 'tukey':
                try:
                    post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None

                if post_hoc_results is None:
                    post_hoc_results = _run_tukey_posthoc(data_groups, groups, alpha=alpha)
            elif post_hoc == 'games_howell':
                try:
                    post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None
            elif post_hoc == 'dunn':
                post_hoc_results = _run_dunn_posthoc(data_groups, groups, alpha=alpha)
            elif post_hoc == 'bonferroni':
                 # Manual pairwise t-tests with Bonferroni
                 try:
                     post = pg.pairwise_tests(data=df, dv=col_a, between=col_b, padjust='bonf')
                     post_hoc_results = _format_posthoc_results(post, alpha)
                 except Exception:
                     post_hoc_results = None
            elif post_hoc == 'holm':
                 try:
                     post = pg.pairwise_tests(data=df, dv=col_a, between=col_b, padjust='holm')
                     post_hoc_results = _format_posthoc_results(post, alpha)
                 except Exception:
                     post_hoc_results = None
            elif post_hoc == 'scheffe':
                 # Scheffe is not directly in pg.pairwise_tests, simplify to none or generic
                 # Pingouin doesn't have built-in Scheffe. 
                 # We will skip or fallback to Tukey? 
                 # Let's fallback to uncorrected pairwise for now or just skip.
                 post_hoc_results = None

            post_hoc_results = _apply_posthoc_correction(post_hoc_results, alpha=alpha, correction=post_hoc_correction)

    elif method_id == "anova_welch":
        welch = pg.welch_anova(data=df, dv=col_a, between=col_b)
        anova_table = welch.to_dict('records')
        row = welch.iloc[0]
        stat_val = float(row.get("F"))
        p_val = float(row.get("p-unc"))
        
        # Welch ANOVA effect size is typically eta-squared or omega-squared estimated
        # Pingouin returns np2 sometimes?
        requested_es = kwargs.get("effect_size", "eta_squared")
        eff_size = None
        eff_size_name = requested_es
        
        if "np2" in row:
             eff_size = float(row.get("np2"))
             # Override name if user asked for specific one that matches
             if requested_es in ["eta_squared", "partial_eta_squared"]:
                 eff_size_name = requested_es # In one-way they are same
        
        # If strict calculation needed for Omega-squared in Welch, it's complex. 
        # For now rely on what we have + fallback.
        if eff_size is None and "eta2" in row:
            eff_size = float(row.get("eta2"))

        alpha = kwargs.get("alpha", 0.05)
        post_hoc = str(kwargs.get('post_hoc', 'games_howell') or '').strip().lower()
        post_hoc_correction = kwargs.get('post_hoc_correction', None)
        if p_val < alpha and post_hoc and post_hoc != 'none':
            if post_hoc == 'games_howell':
                post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
                post_hoc_results = _format_posthoc_results(post, alpha)
            elif post_hoc == 'tukey':
                try:
                    post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None
            elif post_hoc == 'dunn':
                post_hoc_results = _run_dunn_posthoc(data_groups, groups, alpha=alpha)

            post_hoc_results = _apply_posthoc_correction(post_hoc_results, alpha=alpha, correction=post_hoc_correction)

    elif method_id == "kruskal":
        kr = pg.kruskal(data=df, dv=col_a, between=col_b)
        anova_table = kr.to_dict('records')
        row = kr.iloc[0]
        stat_val = float(row.get("H"))
        p_val = float(row.get("p-unc"))
        if "eps-sq" in row:
            eff_size = float(row.get("eps-sq"))
            eff_size_name = "eps-sq"
        elif "eta2" in row:
            eff_size = float(row.get("eta2"))
            eff_size_name = "eta2"
        alpha = kwargs.get("alpha", 0.05)
        post_hoc = str(kwargs.get('post_hoc', 'none') or '').strip().lower()
        post_hoc_correction = kwargs.get('post_hoc_correction', None)
        if p_val < alpha and post_hoc and post_hoc != 'none':
            if post_hoc == 'dunn':
                post_hoc_results = _run_dunn_posthoc(data_groups, groups, alpha=alpha)
            elif post_hoc == 'games_howell':
                try:
                    post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None
            elif post_hoc == 'tukey':
                try:
                    post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                    post_hoc_results = _format_posthoc_results(post, alpha)
                except Exception:
                    post_hoc_results = None

            post_hoc_results = _apply_posthoc_correction(post_hoc_results, alpha=alpha, correction=post_hoc_correction)

    elif method_id == "t_test_rel" and len(groups) == 2:
         res = pg.ttest(data_groups[0], data_groups[1], paired=True, alternative=alt)
         stat_val = float(res["T"].iloc[0])
         p_val = float(res["p-val"].iloc[0])
         
         requested_es = kwargs.get("effect_size", "cohen")
         eff_size = None
         eff_size_name = requested_es
         
         if requested_es == "cohen":
              eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
         elif requested_es == "hedges":
              try:
                  eff_size = float(pg.compute_effsize(data_groups[0], data_groups[1], paired=True, eftype='hedges'))
              except Exception:
                  eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
                  eff_size_name = "cohen-d" # Fallback
         else:
              eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
              eff_size_name = "cohen-d"

         eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
         power = float(res["power"].iloc[0]) if "power" in res.columns else None
         try:
             bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
         except Exception:
             bf10 = None

    elif method_id == "wilcoxon" and len(groups) == 2:
         res = pg.wilcoxon(data_groups[0], data_groups[1], alternative=alt)
         stat_val = float(res["W-val"].iloc[0]) if "W-val" in res.columns else float(res["W"].iloc[0])
         p_val = float(res["p-val"].iloc[0])
         eff_size = float(res["RBC"].iloc[0]) if "RBC" in res.columns else eff_size
         eff_size_name = "rbc" if eff_size is not None else None
         
    if bf10 is None:
        bf10 = _bf10_from_p_value_bound(p_val)

    # Prepare Plot Data & Descriptives
    plot_data, plot_stats = _prepare_group_plot_data(groups, data_groups)
    
    # If descriptives not requested, clear the stats table data
    if not kwargs.get("descriptives", True):
        plot_stats = None

    # Calculate Assumptions
    assumptions = _check_assumptions(groups, data_groups)
    
    # Generate Smart Warnings
    warnings = _generate_warnings(method_str, path_type="group", assumptions=assumptions)

    alpha = kwargs.get("alpha", 0.05)
    
    # Interpret effect size for user
    effect_interpretation = interpret_effect_size(eff_size, eff_size_name) if eff_size is not None else None

    # Handle CI visibility
    if not kwargs.get("ci", True):
        eff_ci_lower = None
        eff_ci_upper = None

    comparisons: Optional[List[Dict[str, Any]]] = None
    try:
        comparisons = []
        if isinstance(post_hoc_results, list) and post_hoc_results:
            for r in post_hoc_results:
                a = r.get("group1")
                b = r.get("group2")
                raw_p = r.get("p_value")
                adj_p = r.get("p_value_adj")
                p = adj_p if isinstance(adj_p, (int, float)) else raw_p
                if a is None or b is None or p is None:
                    continue
                comparisons.append({"a": str(a), "b": str(b), "p_value": float(p), "p_value_raw": float(raw_p) if raw_p is not None else None, "p_value_adj": float(adj_p) if adj_p is not None else None})
        elif len(groups) == 2 and isinstance(p_val, (int, float)):
            comparisons.append({"a": str(groups[0]), "b": str(groups[1]), "p_value": float(p_val)})
    except Exception:
        comparisons = None
    
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "effect_size_name": eff_size_name,
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower,
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "bf10": bf10,
        "significant": p_val < alpha,
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "post_hoc": post_hoc_results,
        "comparisons": comparisons,
        "anova_table": anova_table
    }

def _run_tukey_posthoc(data_groups, groups, alpha=0.05):
    try:
        all_vals = []
        all_groups = []
        for i, g in enumerate(groups):
            vals = data_groups[i]
            all_vals.extend(vals)
            all_groups.extend([g]*len(vals))
        
        tukey = pairwise_tukeyhsd(endog=all_vals, groups=all_groups, alpha=alpha)
        summary_data = tukey.summary().data[1:]
        post_hoc = []
        for row in summary_data:
            post_hoc.append({
                "group1": str(row[0]),
                "group2": str(row[1]),
                "diff": float(row[2]),
                "p_value": float(row[3]),
                "ci_lower": float(row[4]),
                "ci_upper": float(row[5]),
                "significant": bool(row[6])
            })
        return post_hoc
    except Exception as e:
        logger.error(f"Post-hoc failed: {e}", exc_info=True)
        return None

def _handle_one_sample(df, method_id, col_a, kwargs):
    data = df[col_a]
    test_val = float(kwargs.get("test_value", 0))
    alt = kwargs.get("alternative", "two-sided")
    alpha = kwargs.get("alpha", 0.05)

    res = pg.ttest(data, test_val, paired=False, alternative=alt)
    stat_val = float(res["T"].iloc[0])
    p_val = float(res["p-val"].iloc[0])
    eff_size = float(res["cohen-d"].iloc[0]) if "cohen-d" in res.columns else None
    eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
    power = float(res["power"].iloc[0]) if "power" in res.columns else None
    try:
        bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
    except Exception:
        bf10 = None
    
    plot_data = [{"value": float(v)} for v in data]
    mean = float(data.mean())
    std = float(data.std())
    
    plot_stats = {
        "group": {
            "mean": mean,
            "sd": std,
            "count": len(data),
            "sem": std/np.sqrt(len(data))
        }
    }
    
    if not kwargs.get("descriptives", True):
        plot_stats = None

    effect_interpretation = interpret_effect_size(eff_size, "cohen-d") if eff_size is not None else None
    
    if not kwargs.get("ci", True):
         eff_ci_lower = None
         eff_ci_upper = None
         effect_size_ci_lower = None # 1-sample eff size CI not usually returned by pg.ttest
         effect_size_ci_upper = None
    else:
         effect_size_ci_lower = None
         effect_size_ci_upper = None

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "effect_size_name": "cohen-d" if eff_size is not None else None,
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower, # CI for mean diff
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "bf10": bf10,
        "significant": p_val < alpha,
        "groups": ["Sample"],
        "plot_data": plot_data,
        "plot_stats": plot_stats,
        "extra": {"test_value": test_val}
    }

def _handle_correlation(df, method_id, col_a, col_b, kwargs):
    x, y = df[col_a], df[col_b]
    alpha = kwargs.get("alpha", 0.05)
    alt = kwargs.get("alternative", "two-sided")

    stat_val = 0.0
    p_val = 1.0
    eff_ci_lower = None
    eff_ci_upper = None
    power = None
    bf10 = None

    try:
        method = "pearson" if method_id == "pearson" else "spearman"
        res = pg.corr(x=x, y=y, method=method, alternative=alt)
        stat_val = float(res["r"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
        eff_ci_lower, eff_ci_upper = _extract_ci_bounds(res["CI95%"].iloc[0] if "CI95%" in res.columns else None)
        power = float(res["power"].iloc[0]) if "power" in res.columns else None
        try:
            bf10 = float(res["BF10"].iloc[0]) if "BF10" in res.columns else None
        except Exception:
            bf10 = None
    except Exception:
        if method_id == "pearson":
            stat_val, p_val = stats.pearsonr(x, y)
        else:
            stat_val, p_val = stats.spearmanr(x, y)
        
    slope, intercept, r_value, _, _ = stats.linregress(x, y)
    
    # Interpret correlation as effect size
    effect_interpretation = interpret_effect_size(stat_val, method_id)
    
    if not kwargs.get("ci", True):
        eff_ci_lower = None
        eff_ci_upper = None
    
    # Plot Data (Sampled)
    plot_data = []
    sample_indices = np.random.choice(df.index, min(len(df), 1000), replace=False)
    for idx in sample_indices:
        plot_data.append({"x": float(df.loc[idx, col_a]), "y": float(df.loc[idx, col_b])})
        
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(stat_val),  # r is the effect size
        "effect_size_name": "r",
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower,
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "bf10": bf10 if bf10 is not None else _bf10_from_p_value_bound(p_val),
        "significant": p_val < alpha,
        "regression": {"slope": float(slope), "intercept": float(intercept), "r_squared": float(r_value**2)},
        "plot_data": plot_data
    }

def _handle_chi_square(df, method_id, col_a, col_b, kwargs):
    ct = pd.crosstab(df[col_a], df[col_b])
    alpha = kwargs.get("alpha", 0.05)
    
    # Check expected frequencies for Fisher's Rule (if < 5 in >20% of cells, or any < 1, usually)
    # Simple rule: if any expected cell < 5 and table is 2x2 -> Fisher
    stat_val, p_val, dof, expected = stats.chi2_contingency(ct)
    
    warning = None
    min_expected = np.min(expected)
    
    switched_to_fisher = False
    if ct.shape == (2, 2) and min_expected < 5:
        # Switch to Fisher's Exact Test
        odds_ratio, p_val_fisher = stats.fisher_exact(ct)
        p_val = p_val_fisher
        warning = f"Low expected count ({min_expected:.2f} < 5). Auto-switched to Fisher's Exact Test."
        method_id = "fisher_exact"
        switched_to_fisher = True

    n_total = int(ct.to_numpy().sum()) if hasattr(ct, "to_numpy") else None
    cramers_v = None
    try:
        if n_total and n_total > 0:
            r, c = ct.shape
            denom = min(r - 1, c - 1)
            if denom > 0:
                phi2 = float(stat_val) / float(n_total)
                cramers_v = float(np.sqrt(phi2 / float(denom))) if phi2 >= 0 else None
    except Exception:
        cramers_v = None

    effect_value = None
    effect_name = None
    effect_interpretation = None
    if switched_to_fisher:
        try:
            effect_value = float(odds_ratio) if "odds_ratio" in locals() and odds_ratio is not None else None
        except Exception:
            effect_value = None
        effect_name = "odds_ratio" if effect_value is not None else None
        try:
            if effect_value is not None:
                effect_interpretation = interpret_effect_size(effect_value, "odds_ratio")
        except Exception:
            effect_interpretation = None
    else:
        try:
            effect_value = float(cramers_v) if cramers_v is not None else None
        except Exception:
            effect_value = None
        effect_name = "cramers_v" if effect_value is not None else None
        try:
            if effect_value is not None:
                effect_interpretation = interpret_effect_size(effect_value, "cramers_v")
        except Exception:
            effect_interpretation = None

    contingency = {
        "rows": [str(x) for x in ct.index.tolist()],
        "cols": [str(x) for x in ct.columns.tolist()],
        "counts": ct.values.tolist(),
        "n": n_total,
    }

    try:
        groups = [str(x) for x in ct.columns.tolist()]
    except Exception:
        groups = None

    plot_stats = None
    try:
        row_sums = ct.sum(axis=1)
        col_sums = ct.sum(axis=0)
        total = float(n_total or 0)
        if total > 0:
            row_pct = (row_sums / total * 100.0).round(2).to_dict()
            col_pct = (col_sums / total * 100.0).round(2).to_dict()
        else:
            row_pct, col_pct = {}, {}

        plot_stats = {
            "row_totals": {str(k): int(v) for k, v in row_sums.to_dict().items()},
            "col_totals": {str(k): int(v) for k, v in col_sums.to_dict().items()},
            "row_pct_total": {str(k): float(v) for k, v in row_pct.items()},
            "col_pct_total": {str(k): float(v) for k, v in col_pct.items()},
        }
    except Exception:
        plot_stats = None

    out = {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < alpha,
        "warning": warning,
        "contingency": contingency,
        "expected_min": float(min_expected) if min_expected is not None else None,
        "odds_ratio": float(odds_ratio) if "odds_ratio" in locals() and odds_ratio is not None else None,
        "effect_size": effect_value,
        "effect_size_name": effect_name,
        "effect_size_interpretation": effect_interpretation,
        "groups": groups,
        "plot_stats": plot_stats,
    }

    return out

def _handle_fisher_exact(df, method_id, col_a, col_b, kwargs):
    ct = pd.crosstab(df[col_a], df[col_b])
    alpha = kwargs.get("alpha", 0.05)

    if ct.shape != (2, 2):
        raise ValueError("Fisher's Exact Test requires a 2×2 contingency table")

    odds_ratio, p_val = stats.fisher_exact(ct)

    expected_min = None
    try:
        _, _, _, expected = stats.chi2_contingency(ct)
        expected_min = float(np.min(expected))
    except Exception:
        expected_min = None

    n_total = int(ct.to_numpy().sum()) if hasattr(ct, "to_numpy") else None
    contingency = {
        "rows": [str(x) for x in ct.index.tolist()],
        "cols": [str(x) for x in ct.columns.tolist()],
        "counts": ct.values.tolist(),
        "n": n_total,
    }

    try:
        groups = [str(x) for x in ct.columns.tolist()]
    except Exception:
        groups = None

    plot_stats = None
    try:
        row_sums = ct.sum(axis=1)
        col_sums = ct.sum(axis=0)
        total = float(n_total or 0)
        if total > 0:
            row_pct = (row_sums / total * 100.0).round(2).to_dict()
            col_pct = (col_sums / total * 100.0).round(2).to_dict()
        else:
            row_pct, col_pct = {}, {}

        plot_stats = {
            "row_totals": {str(k): int(v) for k, v in row_sums.to_dict().items()},
            "col_totals": {str(k): int(v) for k, v in col_sums.to_dict().items()},
            "row_pct_total": {str(k): float(v) for k, v in row_pct.items()},
            "col_pct_total": {str(k): float(v) for k, v in col_pct.items()},
        }
    except Exception:
        plot_stats = None

    effect_value = None
    effect_interpretation = None
    try:
        effect_value = float(odds_ratio) if odds_ratio is not None else None
    except Exception:
        effect_value = None
    try:
        if effect_value is not None:
            effect_interpretation = interpret_effect_size(effect_value, "odds_ratio")
    except Exception:
        effect_interpretation = None

    return {
        "method": method_id,
        "stat_value": float(odds_ratio) if odds_ratio is not None else 0.0,
        "p_value": float(p_val),
        "significant": float(p_val) < float(alpha),
        "warning": None,
        "contingency": contingency,
        "expected_min": expected_min,
        "odds_ratio": float(odds_ratio) if odds_ratio is not None else None,
        "effect_size": effect_value,
        "effect_size_name": "odds_ratio" if effect_value is not None else None,
        "effect_size_interpretation": effect_interpretation,
        "groups": groups,
        "plot_stats": plot_stats,
    }

def _handle_survival(df, method_id, col_a, col_b, kwargs):
    duration = df[col_a]
    event = df[col_b]
    alpha = kwargs.get("alpha", 0.05)
    group_col = kwargs.get("group_col")
    
    plot_data = []
    groups = ["Overall"]
    p_val = 1.0
    
    if group_col and group_col in df.columns:
        groups = sorted(df[group_col].dropna().unique())
        for g in groups:
            subset = df[df[group_col] == g]
            kmf = KaplanMeierFitter()
            kmf.fit(subset[col_a], event_observed=subset[col_b], label=str(g))
            for time, prob in zip(kmf.survival_function_.index, kmf.survival_function_.values.flatten()):
                 plot_data.append({"time": float(time), "probability": float(prob), "group": str(g)})
        
        if len(groups) == 2:
            g1 = df[df[group_col] == groups[0]]
            g2 = df[df[group_col] == groups[1]]
            results = logrank_test(g1[col_a], g2[col_a], event_observed_A=g1[col_b], event_observed_B=g2[col_b])
            p_val = results.p_value
    else:
        kmf = KaplanMeierFitter()
        kmf.fit(duration, event_observed=event)
        for time, prob in zip(kmf.survival_function_.index, kmf.survival_function_.values.flatten()):
             plot_data.append({"time": float(time), "probability": float(prob), "group": "Overall"})

    return {
        "method": method_id,
        "stat_value": 0.0,
        "p_value": float(p_val),
        "significant": p_val < alpha,
        "groups": groups,
        "plot_data": plot_data
    }

def _handle_regression(df, method_id, col_a, col_b, kwargs):
    predictors = kwargs.get("predictors", [col_b])
    covariates = kwargs.get("covariates", [])
    alpha = kwargs.get("alpha", 0.05)
    if not isinstance(predictors, list):
        predictors = [col_b]
    if not isinstance(covariates, list):
        covariates = []
    model_terms = [c for c in [*predictors, *covariates] if c]
    cols_to_clean = [col_a] + model_terms
    clean_df = df[cols_to_clean].dropna() # Re-clean locally for predictors
    if clean_df.empty:
        raise ValueError("Недостаточно данных для регрессии после очистки.")
    if col_a not in clean_df.columns:
        raise ValueError("Outcome колонка не найдена.")

    outcome = clean_df[col_a]
    X = pd.get_dummies(clean_df[model_terms], drop_first=True).astype(float)
    X = sm.add_constant(X)
    if X.shape[0] < 3:
        raise ValueError("Слишком мало наблюдений для регрессии.")
    if X.shape[1] == 0:
        raise ValueError("Нет предикторов после кодирования.")
    
    if method_id == "linear_regression":
        model = sm.OLS(outcome, X).fit()
        r_squared = model.rsquared
    else:
        # Logistic
        one_vs_rest = bool(kwargs.get("one_vs_rest", False))
        positive_label = kwargs.get("positive_label")
        outcome_non_na = outcome.dropna()
        if outcome_non_na.empty:
            raise ValueError("Логистическая регрессия требует непустой исход.")
        unique_vals = list(pd.unique(outcome_non_na))
        if len(unique_vals) != 2:
            if not one_vs_rest:
                raise ValueError(f"Logistic regression requires a binary outcome. Found {len(unique_vals)} unique values.")
            if positive_label is None:
                raise ValueError("one_vs_rest требует positive_label для бинаризации")
            if isinstance(positive_label, (int, float)):
                pos_val = float(positive_label)
                outcome = pd.to_numeric(outcome, errors="coerce").map(lambda v: 1.0 if v == pos_val else 0.0)
            else:
                positive_label = str(positive_label)
                outcome = outcome.astype(str).map(lambda v: 1.0 if str(v) == positive_label else 0.0)
            outcome_non_na = outcome.dropna()
            unique_vals = list(pd.unique(outcome_non_na))
            if len(unique_vals) != 2:
                raise ValueError("one_vs_rest: после бинаризации не найдено двух классов")

        if pd.api.types.is_numeric_dtype(outcome_non_na):
            as_float = outcome_non_na.astype(float)
            unique_num = sorted(set(float(v) for v in pd.unique(as_float)))
            if set(unique_num) == {0.0, 1.0}:
                outcome = outcome.astype(float)
            else:
                mapping = {unique_num[0]: 0.0, unique_num[1]: 1.0}
                outcome = outcome.astype(float).map(mapping)
        else:
            unique_str = sorted(str(v) for v in unique_vals)
            positive = unique_str[-1]
            outcome = outcome.astype(str).map(lambda v: 1.0 if v == positive else 0.0)
        class_counts = outcome.value_counts(dropna=True)
        if class_counts.min() < 2:
            raise ValueError("Логистическая регрессия требует минимум 2 наблюдения в каждом классе.")
        model = sm.Logit(outcome, X).fit(disp=0)
        r_squared = model.prsquared
        
    # Calculate VIF if requested (Linear Regression only usually, but can be done for X matrix)
    vif_data = {}
    if kwargs.get("vif", True) and len(model_terms) > 1:
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        try:
            for i in range(X.shape[1]):
                col_name = X.columns[i]
                if col_name == 'const': continue
                v = variance_inflation_factor(X.values, i)
                vif_data[col_name] = v
        except Exception:
            pass

    show_ci = kwargs.get("ci", True)
    coef_data = []
    for name in model.params.index:
        entry = {
            "variable": name,
            "coefficient": float(model.params[name]),
            "p_value": float(model.pvalues[name]),
            "std_err": float(model.bse[name]),
            "ci_lower": float(model.conf_int().loc[name][0]) if show_ci else None,
            "ci_upper": float(model.conf_int().loc[name][1]) if show_ci else None,
            "vif": float(vif_data[name]) if name in vif_data else None
        }
        if method_id == "logistic_regression":
             entry["odds_ratio"] = float(np.exp(model.params[name]))
             # OR CI also respects show_ci? Yes usually.
             entry["or_ci_lower"] = float(np.exp(model.conf_int().loc[name][0])) if show_ci else None
             entry["or_ci_upper"] = float(np.exp(model.conf_int().loc[name][1])) if show_ci else None
        coef_data.append(entry)

    plot_data = []
    plot_config = None
    if len(model_terms) == 1 and model_terms[0] in clean_df.columns:
        predictor = model_terms[0]
        x_vals = pd.to_numeric(clean_df[predictor], errors="coerce")
        if method_id == "linear_regression":
            y_vals = pd.to_numeric(clean_df[col_a], errors="coerce")
        else:
            y_vals = pd.to_numeric(outcome, errors="coerce")
        mask = np.isfinite(x_vals) & np.isfinite(y_vals)
        idx = clean_df.index[mask]
        if len(idx) > 0:
            sample_idx = idx
            if len(sample_idx) > 1000:
                sample_idx = np.random.choice(sample_idx, 1000, replace=False)
            for i in sample_idx:
                plot_data.append({"x": float(x_vals.loc[i]), "y": float(y_vals.loc[i])})
            if plot_data:
                plot_config = {"x_label": predictor, "y_label": col_a}

    roc_out = None
    if method_id == "logistic_regression" and bool(kwargs.get("show_roc", True)):
        try:
            probs = model.predict(X)
            fpr, tpr, thresholds = roc_curve(outcome, probs)
            roc_auc = auc(fpr, tpr)
            roc_data = []
            step = max(1, len(fpr) // 500)
            for i in range(0, len(fpr), step):
                roc_data.append({
                    "x": float(fpr[i]),
                    "y": float(tpr[i]),
                    "threshold": float(thresholds[i])
                })
            if roc_data and roc_data[-1]["x"] != float(fpr[-1]):
                roc_data.append({"x": float(fpr[-1]), "y": float(tpr[-1]), "threshold": float(thresholds[-1])})
            roc_out = {
                "auc": float(roc_auc),
                "plot_data": roc_data,
                "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"},
            }
        except Exception:
            roc_out = None
        
    return {
        "method": method_id,
        "stat_value": float(model.fvalue) if hasattr(model, 'fvalue') else 0.0,
        "p_value": float(model.f_pvalue) if hasattr(model, 'f_pvalue') else float(model.pvalues.min()),
        "significant": any(model.pvalues < alpha),
        "r_squared": float(r_squared),
        "coefficients": coef_data,
        "aic": float(model.aic) if hasattr(model, 'aic') else None,
        "pseudo_r2": float(model.prsquared) if hasattr(model, 'prsquared') else None,
        "n_obs": int(model.nobs) if hasattr(model, 'nobs') else None,
        "roc": roc_out,
        "plot_data": plot_data,
        "plot_config": plot_config
    }

def _handle_roc_analysis(df, method_id, col_a, col_b):
    y_true = df[col_b]
    y_score = df[col_a]
    classes = sorted(y_true.unique())
    
    if len(classes) != 2:
        raise ValueError(f"ROC Analysis requires exactly 2 classes. Found {len(classes)}.")
        
    pos_label = classes[1]
    neg_label = classes[0]
    y_true_bin = (y_true == pos_label).astype(int)
    
    fpr, tpr, thresholds = roc_curve(y_true_bin, y_score)
    roc_auc = auc(fpr, tpr)
    
    j_scores = tpr - fpr
    best_idx = np.argmax(j_scores)
    
    roc_data = []
    step = max(1, len(fpr) // 500)
    for i in range(0, len(fpr), step):
        roc_data.append({
            "x": float(fpr[i]),
            "y": float(tpr[i]),
            "threshold": float(thresholds[i])
        })
    if roc_data[-1]["x"] != float(fpr[-1]):
         roc_data.append({"x": float(fpr[-1]), "y": float(tpr[-1]), "threshold": float(thresholds[-1])})
        
    return {
        "method": method_id,
        "auc": float(roc_auc),
        "best_threshold": float(thresholds[best_idx]),
        "youden_index": float(j_scores[best_idx]),
        "sensitivity": float(tpr[best_idx]),
        "specificity": float(1 - fpr[best_idx]),
        "pos_label": str(pos_label),
        "neg_label": str(neg_label),
        "significant": float(roc_auc) > 0.5,
        "plot_data": roc_data,
        "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"}
    }

def _prepare_group_plot_data(groups, data_groups):
    plot_data = []
    plot_stats = {}
    for i, g in enumerate(groups):
        vals = data_groups[i]
        mean = float(vals.mean())
        std = float(vals.std()) if len(vals) > 1 else 0
        n = len(vals)
        sem = std / np.sqrt(n) if n > 0 else 0
        ci_val = 1.96 * sem 
        
        plot_stats[str(g)] = {
            "mean": mean,
            "sd": std,
            "sem": sem,
            "ci_lower": mean - ci_val,
            "ci_upper": mean + ci_val,
            "median": float(vals.median()),
            "q1": float(vals.quantile(0.25)),
            "q3": float(vals.quantile(0.75)),
            "min": float(vals.min()),
            "max": float(vals.max()),
            "count": int(n)
        }
        sample_vals = vals.sample(min(len(vals), 500)) if len(vals) > 500 else vals
        for v in sample_vals:
            plot_data.append({"group": str(g), "value": float(v)})
    return plot_data, plot_stats

def _check_assumptions(groups, data_groups):
    assumptions = {}
    if len(groups) >= 2:
         norm_results = {}
         for i, g in enumerate(groups):
             is_norm, p_norm, _ = check_normality(data_groups[i])
             norm_results[str(g)] = {"p_value": float(p_norm) if p_norm is not None else None, "passed": is_norm}
         assumptions["normality"] = norm_results
         is_homo, p_homo, _ = check_homogeneity(data_groups)
         assumptions["homogeneity"] = {"p_value": float(p_homo) if p_homo is not None else None, "passed": is_homo}
    return assumptions

def _generate_warnings(method_str, path_type="group", assumptions=None):
    warnings = []
    if path_type == "group":
        parametric_methods = ["t_test_ind", "t_test_welch", "t_test_rel", "anova", "rm_anova"]
        if method_str in parametric_methods:
            norm_res = assumptions.get("normality", {})
            failed_groups = [g for g, res in norm_res.items() if isinstance(res, dict) and res.get("passed") is False]
            if failed_groups:
                warnings.append(f"Normality assumption failed for groups: {', '.join(failed_groups)}. Consider using a non-parametric test.")
        
        strict_homogeneity = ["t_test_ind", "anova"]
        if method_str in strict_homogeneity:
            homo_res = assumptions.get("homogeneity")
            if isinstance(homo_res, dict) and homo_res.get("passed") is False:
                warnings.append("Homogeneity of variances assumption failed. Consider using Welch's T-test or Welch's ANOVA.")
    return warnings

def compute_descriptive_compare(df: pd.DataFrame, target: str, group: str) -> Dict[str, Any]:
    """
    Detailed descriptive statistics for Study Design / Table 1.
    Includes: Count, Mean, Median, SD, SE, IQR, Shapiro-Wilk (Normality).
    """
    import numpy as np
    from scipy import stats
    
    if group not in df.columns or target not in df.columns:
        return {}
        
    groups = df[group].dropna().unique()
    results: Dict[str, Any] = {}

    def _safe_float(v):
        try:
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                return None
            return float(v)
        except Exception:
            return None

    def _safe_float3(v):
        out = _safe_float(v)
        if out is None:
            return None
        try:
            return float(round(out, 3))
        except Exception:
            return out

    def _compute(series_raw: pd.Series) -> Dict[str, Any]:
        series_num = pd.to_numeric(series_raw, errors="coerce")
        missing = int(series_num.isna().sum())
        valid = series_num.dropna()
        n = int(len(valid))

        if n == 0:
            return {
                "count": 0,
                "missing": missing,
                "mean": None,
                "median": None,
                "mode": None,
                "std": None,
                "se": None,
                "variance": None,
                "cv": None,
                "geometric_mean": None,
                "min": None,
                "max": None,
                "range": None,
                "q1": None,
                "q3": None,
                "iqr": None,
                "skewness": None,
                "kurtosis": None,
                "shapiro_w": None,
                "shapiro_p": None,
                "ci_95_low": None,
                "ci_95_high": None
            }

        mode_series = valid.mode(dropna=True)
        mode_val = mode_series.iloc[0] if not mode_series.empty else None

        mean = valid.mean()
        std = valid.std(ddof=1) if n > 1 else 0.0
        se = (std / np.sqrt(n)) if n > 1 else None

        cv = None
        try:
            mean_f = _safe_float(mean)
            std_f = _safe_float(std)
            if mean_f is not None and std_f is not None and mean_f != 0:
                cv = (std_f / mean_f) * 100
        except Exception:
            cv = None

        geometric_mean = None
        try:
            positives = valid[valid > 0]
            if int(len(positives)) > 0:
                geometric_mean = stats.gmean(positives.to_numpy(dtype=float))
        except Exception:
            geometric_mean = None

        q1 = valid.quantile(0.25)
        q3 = valid.quantile(0.75)
        iqr = q3 - q1

        shapiro_w = None
        shapiro_p = None
        if n >= 3:
            shapiro_sample = valid
            if n > 5000:
                shapiro_sample = valid.sample(5000, random_state=0)
            try:
                w, p = stats.shapiro(shapiro_sample)
                shapiro_w = _safe_float3(w)
                shapiro_p = _safe_float3(p)
            except Exception:
                shapiro_w = None
                shapiro_p = None

        ci_95_low = None
        ci_95_high = None
        if se is not None:
            ci_95_low = _safe_float3(mean - 1.96 * se)
            ci_95_high = _safe_float3(mean + 1.96 * se)

        return {
            "count": n,
            "missing": missing,
            "mean": _safe_float3(mean),
            "median": _safe_float3(valid.median()),
            "mode": _safe_float3(mode_val),
            "std": _safe_float3(std),
            "se": _safe_float3(se),
            "variance": _safe_float3(valid.var(ddof=1) if n > 1 else 0.0),
            "cv": _safe_float3(cv),
            "geometric_mean": _safe_float3(geometric_mean),
            "min": _safe_float3(valid.min()),
            "max": _safe_float3(valid.max()),
            "range": _safe_float3(valid.max() - valid.min()),
            "q1": _safe_float3(q1),
            "q3": _safe_float3(q3),
            "iqr": _safe_float3(iqr),
            "skewness": _safe_float3(valid.skew()),
            "kurtosis": _safe_float3(valid.kurt()),
            "shapiro_w": shapiro_w,
            "shapiro_p": shapiro_p,
            "ci_95_low": ci_95_low,
            "ci_95_high": ci_95_high
        }

    for g in groups:
        group_mask = df[group] == g
        series_raw = df.loc[group_mask, target]
        results[str(g)] = _compute(series_raw)

    results["overall"] = _compute(df[target])
    
    return results

def run_batch_analysis(
    df: pd.DataFrame,
    targets: List[str],
    group_col: str,
    method_id: str = "t_test_ind",
    alpha: float = 0.05,
    auto_fallback: bool = True,
    multiplicity_correction: str = "fdr_bh",
    **kwargs,
) -> List[Dict[str, Any]]:
    """
    Runs analysis for multiple targets against a group column.
    Applies Benjamini-Hochberg (FDR) correction to p-values.
    """
    results = []
    p_values = []
    corr = str(multiplicity_correction or "").strip().lower()
    if not corr:
        corr = "fdr_bh"
    
    # 1. Run Analysis for each target
    for target in targets:
        try:
            # Auto-detect method if needed, but usually batch implies same method
            # For MVP assume same method or auto-detect based on target type?
            # Let's enforce method_id for consistency in batch
            
            # Skip if target not in df
            if target not in df.columns:
                continue
                
            res = run_analysis(
                df,
                method_id,
                target,
                group_col,
                alpha=alpha,
                auto_fallback=auto_fallback,
                **kwargs,
            )
            
            # Store raw result
            res["target"] = target
            results.append(res)
            p_values.append(res.get("p_value") if res.get("p_value") is not None else 1.0)
            
        except Exception as e:
            logger.error(f"Batch Error for {target}: {e}", exc_info=True)
            results.append({"target": target, "error": str(e), "p_value": 1.0})
            p_values.append(1.0)
            
    # 2. FDR Correction
    if results:
        if corr in {"none", "off", "no"}:
            for res in results:
                res["multiplicity_correction"] = "none"
        else:
            reject, pvals_corrected, _, _ = multipletests(p_values, alpha=alpha, method=corr)
            for i, res in enumerate(results):
                res["p_value_adj"] = float(pvals_corrected[i])
                res["significant_adj"] = bool(reject[i])
                res["multiplicity_correction"] = corr
            
    return results


def _compute_wide_delta(
    df: pd.DataFrame,
    baseline_col: str,
    follow_col: str,
    group_col: Optional[str] = None,
    subject_col: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    cols = [baseline_col, follow_col]
    if subject_col:
        cols.append(subject_col)
    if group_col:
        cols.append(group_col)
    local = df[[c for c in cols if c in df.columns]].copy()
    if baseline_col not in local.columns or follow_col not in local.columns:
        return None
    local[baseline_col] = pd.to_numeric(local[baseline_col], errors='coerce')
    local[follow_col] = pd.to_numeric(local[follow_col], errors='coerce')
    local = local.dropna(subset=[baseline_col, follow_col])
    if local.empty:
        return None

    if subject_col and subject_col in local.columns:
        by_cols = [subject_col]
        if group_col and group_col in local.columns:
            by_cols.append(group_col)
        local = local.groupby(by_cols, dropna=True, observed=False)[[baseline_col, follow_col]].mean().reset_index()
        local = local.dropna(subset=[baseline_col, follow_col])
        if local.empty:
            return None

    def summarize(block: pd.DataFrame) -> Dict[str, Any]:
        base = block[baseline_col]
        fol = block[follow_col]
        d = fol - base
        dp = None
        try:
            denom = base.replace(0, np.nan)
            dp = (d / denom) * 100
        except Exception:
            dp = None

        n = int(d.shape[0])
        mean_d = float(d.mean()) if n else None
        sd_d = float(d.std(ddof=1)) if n > 1 else None
        med_d = float(d.median()) if n else None

        mean_dp = float(dp.mean()) if (isinstance(dp, pd.Series) and dp.shape[0] > 0) else None
        med_dp = float(dp.median()) if (isinstance(dp, pd.Series) and dp.shape[0] > 0) else None

        es = None
        if sd_d is not None and sd_d != 0 and mean_d is not None:
            es = float(mean_d / sd_d)
        es_name = 'cohen_d' if es is not None else None
        es_interp = interpret_effect_size(es, es_name) if es is not None else None

        return {
            'n': n,
            'baseline_mean': float(base.mean()) if n else None,
            'follow_mean': float(fol.mean()) if n else None,
            'delta_abs_mean': mean_d,
            'delta_abs_sd': sd_d,
            'delta_abs_median': med_d,
            'delta_pct_mean': mean_dp,
            'delta_pct_median': med_dp,
            'effect_size': es,
            'effect_size_name': es_name,
            'effect_size_interpretation': es_interp,
        }

    out: Dict[str, Any] = {
        'baseline_col': str(baseline_col),
        'follow_col': str(follow_col),
        'overall': summarize(local),
    }

    if group_col and group_col in local.columns:
        by_group: Dict[str, Any] = {}
        for g, block in local.groupby(group_col, dropna=True, observed=False):
            by_group[str(g)] = summarize(block)
        out['by_group'] = by_group

    return out


# ============================================================
# NEW HANDLERS: Mixed Effects, RM-ANOVA, Friedman, Clustered Correlation
# ============================================================

def _handle_mixed_effects(df: pd.DataFrame, outcome: str, group_col: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for Linear Mixed Model (Time × Group interaction).
    """
    time_col = kwargs.get("time_col")
    subject_col = kwargs.get("subject_col")
    covariates = kwargs.get("covariates", [])
    random_slope = kwargs.get("random_slope", False)
    alpha = kwargs.get("alpha", 0.05)
    
    if not time_col:
        return {"error": "time_col is required for mixed_effects"}
    if not subject_col:
        return {"error": "subject_col is required for mixed_effects"}
    
    engine = MixedEffectsEngine()
    result = engine.fit(
        df=df,
        outcome=outcome,
        time_col=time_col,
        group_col=group_col,
        subject_col=subject_col,
        covariates=covariates if covariates else None,
        random_slope=random_slope,
        alpha=alpha
    )
    
    if "error" not in result:
        result["method"] = "mixed_effects"
        result["significant"] = result.get("interaction", {}).get("significant", False)
        result["p_value"] = result.get("interaction", {}).get("min_p_value", 1.0)
    
    return result


def _handle_rm_anova(df: pd.DataFrame, outcome_prefix: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for Repeated Measures ANOVA.
    """
    outcome_cols = kwargs.get("outcome_cols", [])
    subject_col = kwargs.get("subject_col")
    group_col = kwargs.get("group_col")
    alpha = kwargs.get("alpha", 0.05)
    
    if not outcome_cols:
        return {"error": "outcome_cols is required for rm_anova"}
    if not subject_col:
        return {"error": "subject_col is required for rm_anova"}
    
    engine = RepeatedMeasuresEngine()
    result = engine.fit(
        df=df,
        outcome_cols=outcome_cols,
        subject_col=subject_col,
        group_col=group_col,
        alpha=alpha
    )

    try:
        if isinstance(outcome_cols, list) and len(outcome_cols) >= 2:
            baseline_col = outcome_cols[0]
            follow_col = outcome_cols[-1]
            delta = _compute_wide_delta(
                df,
                baseline_col=baseline_col,
                follow_col=follow_col,
                group_col=group_col,
                subject_col=subject_col,
            )
            if delta is not None:
                result['delta'] = delta
    except Exception:
        pass
    
    if "error" not in result:
        result["method"] = "rm_anova"
        if result.get("interaction") and result["interaction"].get("p_value"):
            result["p_value"] = result["interaction"]["p_value"]
            result["significant"] = result["interaction"]["significant"]
        elif result.get("time_effect"):
            result["p_value"] = result["time_effect"]["p_value"]
            result["significant"] = result["time_effect"]["significant"]
        else:
            result["p_value"] = 1.0
            result["significant"] = False
    
    return result


def _handle_anova_twoway(df: pd.DataFrame, outcome: str, kwargs: Dict) -> Dict[str, Any]:
    group1 = str(kwargs.get("group1") or kwargs.get("factor_a") or "").strip()
    group2 = str(kwargs.get("group2") or kwargs.get("factor_b") or "").strip()
    alpha = kwargs.get("alpha", 0.05)

    if not outcome or outcome not in df.columns:
        return {"error": "outcome column not found"}
    if not group1 or group1 not in df.columns:
        return {"error": "group1 column not found"}
    if not group2 or group2 not in df.columns:
        return {"error": "group2 column not found"}

    local = df[[outcome, group1, group2]].copy().dropna()
    if local.empty:
        return {"error": "No data after filtering missing values"}

    try:
        aov = pg.anova(data=local, dv=outcome, between=[group1, group2], detailed=True)
    except Exception as e:
        return {"error": str(e)}

    # Add anova_table to result
    anova_table = aov.to_dict('records')

    def row_for(source: str):
        if not isinstance(aov, pd.DataFrame) or aov.empty:
            return None
        if "Source" not in aov.columns:
            return None
        hit = aov[aov["Source"] == source]
        if hit.empty:
            return None
        return hit.iloc[0]

    def to_effect(row: Optional[pd.Series]) -> Dict[str, Any]:
        if row is None:
            return {"stat_value": None, "p_value": None, "significant": False, "effect_size": None, "effect_size_name": None}
        f = row.get("F")
        p = row.get("p-unc")
        np2 = row.get("np2") if "np2" in row else None
        eta2 = row.get("eta2") if "eta2" in row else None
        es = np2 if np2 is not None else eta2
        es_name = "np2" if np2 is not None else ("eta2" if eta2 is not None else None)
        p_num = float(p) if isinstance(p, (int, float, np.floating)) else None
        sig = bool(p_num is not None and p_num < alpha)
        es_interp = interpret_effect_size(es, es_name) if es is not None else None
        return {
            "stat_value": float(f) if isinstance(f, (int, float, np.floating)) else None,
            "p_value": p_num,
            "significant": sig,
            "effect_size": float(es) if isinstance(es, (int, float, np.floating)) else None,
            "effect_size_name": es_name,
            "effect_size_interpretation": es_interp,
        }

    eff_a = to_effect(row_for(group1))
    eff_b = to_effect(row_for(group2))
    row_ab = row_for(f"{group1} * {group2}")
    if row_ab is None:
        row_ab = row_for(f"{group1}*{group2}")
    eff_ab = to_effect(row_ab)

    p_vals = [p for p in [eff_a.get("p_value"), eff_b.get("p_value"), eff_ab.get("p_value")] if isinstance(p, (int, float))]
    primary_p = min(p_vals) if p_vals else 1.0

    return {
        "method": "anova_twoway",
        "stat_value": eff_ab.get("stat_value") if eff_ab.get("stat_value") is not None else (eff_a.get("stat_value") or 0.0),
        "p_value": float(primary_p),
        "significant": bool(primary_p < alpha),
        "effects": {
            "factor_a": eff_a,
            "factor_b": eff_b,
            "interaction": eff_ab,
        },
    }


def _handle_friedman(df: pd.DataFrame, dummy: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for Friedman test (non-parametric RM-ANOVA alternative).
    """
    outcome_cols = kwargs.get("outcome_cols", [])
    alpha = kwargs.get("alpha", 0.05)
    
    if not outcome_cols or len(outcome_cols) < 3:
        return {"error": "outcome_cols requires at least 3 columns for Friedman test"}
    
    data = df[outcome_cols].dropna()
    
    if len(data) < 3:
        return {"error": "Insufficient data for Friedman test"}
    
    try:
        stat_val, p_val = stats.friedmanchisquare(*[data[col] for col in outcome_cols])

        out: Dict[str, Any] = {
            "method": "friedman",
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < alpha,
            "n_subjects": len(data),
            "n_timepoints": len(outcome_cols)

        }

        try:
            baseline_col = outcome_cols[0]
            follow_col = outcome_cols[-1]
            delta = _compute_wide_delta(df, baseline_col=baseline_col, follow_col=follow_col, group_col=None)
            if delta is not None:
                out['delta'] = delta
        except Exception:
            pass

        return out
    except Exception as e:
        return {"error": str(e)}


def _handle_clustered_correlation(df: pd.DataFrame, kwargs: Dict) -> Dict[str, Any]:
    """
    Handler for clustered correlation analysis (jYS-style).
    """
    variables = kwargs.get("variables", [])
    method = kwargs.get("method", "pearson")
    linkage_method = kwargs.get("linkage_method", "ward")
    n_clusters = kwargs.get("n_clusters")
    alpha = kwargs.get("alpha", 0.05)
    
    if not variables or len(variables) < 2:
        return {"error": "Нужно выбрать минимум 2 переменные"}
    
    available_vars = [v for v in variables if v in df.columns]
    if len(available_vars) < 2:
        return {"error": f"В файле данных найдено только {len(available_vars)} переменных"}
    
    engine = ClusteredCorrelationEngine()
    result = engine.analyze(
        df=df,
        variables=available_vars,
        method=method,
        linkage_method=linkage_method,
        n_clusters=n_clusters,
        alpha=alpha
    )
    
    if "error" not in result:
        result["method"] = "clustered_correlation"
        p_values: List[float] = []
        heat = result.get("heatmap_data")
        if isinstance(heat, list):
            for cell in heat:
                if not isinstance(cell, dict):
                    continue
                if str(cell.get("row_var")) == str(cell.get("col_var")):
                    continue
                p_raw = cell.get("p")
                try:
                    p = float(p_raw)
                    if np.isfinite(p):
                        p_values.append(p)
                except Exception:
                    continue

        if p_values:
            min_p = float(min(p_values))
            result["p_value"] = min_p
            result["significant"] = bool(min_p < alpha)
        else:
            result["p_value"] = None
            result["significant"] = False

        corr_vals = []
        corr_m = result.get("correlation_matrix")
        if isinstance(corr_m, dict) and isinstance(corr_m.get("values"), list):
            values = corr_m.get("values")
            for i, row in enumerate(values):
                if not isinstance(row, list):
                    continue
                for j, item in enumerate(row):
                    if j <= i:
                        continue
                    try:
                        v = float(item)
                        if np.isfinite(v):
                            corr_vals.append(abs(v))
                    except Exception:
                        continue
        result["stat_value"] = float(max(corr_vals)) if corr_vals else None
    
    return result


def run_analysis(
    df: pd.DataFrame,
    method_id: str,
    col_a: str,
    col_b: str,
    is_paired: bool = False,
    alpha: float = 0.05,
    **kwargs,
) -> Dict[str, Any]:
    """
    Dispatch analysis to выбранному движку (python | r).
    """
    engine = kwargs.pop("engine", None)
    if engine is None:
        engine = kwargs.pop("stats_engine", None)
    if engine is None:
        engine = kwargs.pop("analysis_engine", None)
    plot_engine = kwargs.get("plot_engine")

    engine_norm = str(engine or "").strip().lower()
    if engine_norm in {"r", "r_engine", "rstats"}:
        try:
            from app.stats.r_engine import run_analysis_r
            return run_analysis_r(
                df,
                method_id,
                col_a,
                col_b,
                is_paired=is_paired,
                alpha=alpha,
                python_fallback=_run_analysis_python,
                plot_engine=plot_engine,
                **kwargs,
            )
        except Exception:
            # fallback to python engine if R fails
            return _run_analysis_python(
                df,
                method_id,
                col_a,
                col_b,
                is_paired=is_paired,
                alpha=alpha,
                **kwargs,
            )

    return _run_analysis_python(
        df,
        method_id,
        col_a,
        col_b,
        is_paired=is_paired,
        alpha=alpha,
        **kwargs,
    )
