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
    if name_lower in ["cohen_d", "cohens_d", "hedges_g", "glass_delta", "d"]:
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
        
        return {
            "label": label,
            "label_ru": label_ru,
            "thresholds": {"small": 0.2, "medium": 0.5, "large": 0.8},
            "description": f"Cohen's d = {effect_size:.2f} indicates a {label} effect",
            "description_ru": f"Cohen's d = {effect_size:.2f} указывает на {label_ru} эффект"
        }
    
    # Eta-squared, Partial eta-squared, Epsilon-squared
    elif name_lower in ["eta2", "eta_sq", "eta_squared", "np2", "partial_eta2", "eps_sq", "epsilon_squared"]:
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

def check_normality(data: pd.Series) -> tuple[bool, float, float]:
    """
    Shapiro-Wilk test for normality.
    Returns (is_normal, p_value, statistic).
    """
    clean_data = data.dropna()
    if len(clean_data) < 3:
        return False, 0.0, 0.0
    # Shapiro-Wilk is sensitive to large samples; limit to 5000
    if len(clean_data) > 5000:
        clean_data = clean_data.sample(5000, random_state=42)
    
    try:
        stat, p_value = stats.shapiro(clean_data)
        return p_value > 0.05, p_value, stat
    except:
        return False, 0.0, 0.0

def check_homogeneity(groups_data: List[pd.Series]) -> tuple[bool, float, float]:
    """
    Levene's test for homogeneity of variances.
    Returns (equal_var, p_value, statistic).
    """
    if len(groups_data) < 2:
        return True, 1.0, 0.0
        
    try:
        stat, p_value = stats.levene(*groups_data)
        return p_value > 0.05, p_value, stat
    except:
        return False, 0.0, 0.0

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
        norm_a = check_normality(df[col_a])
        norm_b = check_normality(df[col_b])
        return "pearson" if norm_a and norm_b else "spearman"

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
        if not is_normal:
            all_normal = False
        groups_data.append(subset)
            
    if len(groups) == 2:
        if is_paired:
            return "t_test_rel" if all_normal else "wilcoxon"
        
        # Check Homogeneity for Independent
        equal_var, _, _ = check_homogeneity(groups_data)
        
        if not all_normal:
            return "mann_whitney"
        elif not equal_var:
            return "t_test_welch"
        else:
            return "t_test_ind"
    else:
        # 3+ groups
        return "anova" if all_normal else "kruskal"

def run_analysis(
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
    
    # Handle 'auto' method selection
    if method_id == "auto":
        # Infer column types
        types = {}
        for col in [col_a, col_b]:
            if col and col in df.columns:
                dtype_str = str(df[col].dtype)
                if "int" in dtype_str or "float" in dtype_str:
                    types[col] = "numeric"
                else:
                    types[col] = "categorical"
        
        # Auto-select the best test
        method_id = select_test(df, col_a, col_b, types, is_paired)
        if method_id is None:
            raise ValueError("Could not auto-detect appropriate statistical test. Please select manually.")

    requested_method_id = method_id

    if method_id in GROUP_TESTS:
        auto_fallback = bool(kwargs.get("auto_fallback", True))

        groups = sorted(clean_df[col_b].unique()) if col_b in clean_df.columns else []
        data_groups = [clean_df[clean_df[col_b] == g][col_a] for g in groups] if groups else []
        assumptions = _check_assumptions(groups, data_groups) if groups else {}
        warnings = _generate_warnings(str(requested_method_id).strip(), path_type="group", assumptions=assumptions)

        normality_ok = True
        norm_res = assumptions.get("normality") if isinstance(assumptions, dict) else None
        if isinstance(norm_res, dict) and norm_res:
            normality_ok = all(bool(v.get("passed")) for v in norm_res.values())

        homogeneity_ok = True
        homo_res = assumptions.get("homogeneity") if isinstance(assumptions, dict) else None
        if isinstance(homo_res, dict) and ("passed" in homo_res):
            homogeneity_ok = bool(homo_res.get("passed"))

        recommended = _recommend_group_test(len(groups), bool(is_paired), normality_ok, homogeneity_ok)
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

    elif method_id == "survival_km":
        return _handle_survival(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id in ["linear_regression", "logistic_regression"]:
        return _handle_regression(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "roc_analysis":
        return _handle_roc_analysis(clean_df, method_id, col_a, col_b)

    elif method_id == "mixed_model":
        return _handle_mixed_effects(df, col_a, col_b, kwargs)

    elif method_id == "rm_anova":
        return _handle_rm_anova(df, col_a, kwargs)

    elif method_id == "friedman":
        return _handle_friedman(df, col_a, kwargs)

    elif method_id == "clustered_correlation":
        return _handle_clustered_correlation(df, kwargs)

    raise ValueError(f"Method {method_id} not implemented")


def _handle_group_comparison(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    groups = df[col_b].unique()
    groups = sorted(groups)
    data_groups = [df[df[col_b] == g][col_a] for g in groups]
    
    stat_val, p_val = 0.0, 1.0
    alt = kwargs.get("alternative", "two-sided")
    eff_size = None
    eff_size_name = None
    eff_ci_lower = None
    eff_ci_upper = None
    power = None
    bf10 = None
    post_hoc_results = None
    method_str = str(method_id).strip()

    if method_str == "t_test_ind" and len(groups) == 2:
        res = pg.ttest(data_groups[0], data_groups[1], paired=False, alternative=alt, correction=False)
        stat_val = float(res["T"].iloc[0])
        p_val = float(res["p-val"].iloc[0])
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
        if "np2" in row:
            eff_size = float(row.get("np2"))
            eff_size_name = "np2"
        elif "eta2" in row:
            eff_size = float(row.get("eta2"))
            eff_size_name = "eta2"

        alpha = kwargs.get("alpha", 0.05)
        if p_val < alpha:
            try:
                post = pg.pairwise_tukey(data=df, dv=col_a, between=col_b)
                post_hoc_results = _format_posthoc_results(post, alpha)
            except Exception:
                post_hoc_results = None

            if post_hoc_results is None:
                post_hoc_results = _run_tukey_posthoc(data_groups, groups, alpha=alpha)

    elif method_id == "anova_welch":
        welch = pg.welch_anova(data=df, dv=col_a, between=col_b)
        row = welch.iloc[0]
        stat_val = float(row.get("F"))
        p_val = float(row.get("p-unc"))
        if "np2" in row:
            eff_size = float(row.get("np2"))
            eff_size_name = "np2"

        alpha = kwargs.get("alpha", 0.05)
        if p_val < alpha:
            post = pg.pairwise_gameshowell(data=df, dv=col_a, between=col_b)
            post_hoc_results = _format_posthoc_results(post, alpha)

    elif method_id == "kruskal":
        kr = pg.kruskal(data=df, dv=col_a, between=col_b)
        row = kr.iloc[0]
        stat_val = float(row.get("H"))
        p_val = float(row.get("p-unc"))
        if "eps-sq" in row:
            eff_size = float(row.get("eps-sq"))
            eff_size_name = "eps-sq"
        elif "eta2" in row:
            eff_size = float(row.get("eta2"))
            eff_size_name = "eta2"
        
    elif method_id == "t_test_rel" and len(groups) == 2:
         res = pg.ttest(data_groups[0], data_groups[1], paired=True, alternative=alt)
         stat_val = float(res["T"].iloc[0])
         p_val = float(res["p-val"].iloc[0])
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
         
    # Prepare Plot Data
    plot_data, plot_stats = _prepare_group_plot_data(groups, data_groups)

    # Calculate Assumptions
    assumptions = _check_assumptions(groups, data_groups)
    
    # Generate Smart Warnings
    warnings = _generate_warnings(method_str, path_type="group", assumptions=assumptions)

    alpha = kwargs.get("alpha", 0.05)
    
    # Interpret effect size for user
    effect_interpretation = interpret_effect_size(eff_size, eff_size_name) if eff_size is not None else None

    comparisons: Optional[List[Dict[str, Any]]] = None
    try:
        comparisons = []
        if isinstance(post_hoc_results, list) and post_hoc_results:
            for r in post_hoc_results:
                a = r.get("group1")
                b = r.get("group2")
                p = r.get("p_value")
                if a is None or b is None or p is None:
                    continue
                comparisons.append({"a": str(a), "b": str(b), "p_value": float(p)})
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
        "comparisons": comparisons
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
    
    effect_interpretation = interpret_effect_size(eff_size, "cohen-d") if eff_size is not None else None
    
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "effect_size_name": "cohen-d" if eff_size is not None else None,
        "effect_size_interpretation": effect_interpretation,
        "effect_size_ci_lower": eff_ci_lower,
        "effect_size_ci_upper": eff_ci_upper,
        "power": power,
        "bf10": bf10,
        "significant": p_val < alpha,
        "groups": ["Sample"],
        "plot_data": plot_data,
        "plot_stats": {
            "group": {
                "mean": mean,
                "sd": std,
                "count": len(data),
                "sem": std/np.sqrt(len(data))
            }
        },
        "extra": {"test_value": test_val}
    }

def _handle_correlation(df, method_id, col_a, col_b, kwargs):
    x, y = df[col_a], df[col_b]
    alpha = kwargs.get("alpha", 0.05)
    
    if method_id == "pearson":
        stat_val, p_val = stats.pearsonr(x, y)
    else:
        stat_val, p_val = stats.spearmanr(x, y)
        
    slope, intercept, r_value, _, _ = stats.linregress(x, y)
    
    # Interpret correlation as effect size
    effect_interpretation = interpret_effect_size(stat_val, method_id)
    
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
    
    if ct.shape == (2, 2) and min_expected < 5:
        # Switch to Fisher's Exact Test
        odds_ratio, p_val_fisher = stats.fisher_exact(ct)
        p_val = p_val_fisher
        warning = f"Low expected count ({min_expected:.2f} < 5). Auto-switched to Fisher's Exact Test."
        method_id = "fisher_exact" # Or just annotation? Let's keep ID but note switch
        
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < alpha,
        "warning": warning
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
    
    outcome = clean_df[col_a]
    X = pd.get_dummies(clean_df[model_terms], drop_first=True).astype(float)
    X = sm.add_constant(X)
    
    if method_id == "linear_regression":
        model = sm.OLS(outcome, X).fit()
        r_squared = model.rsquared
    else:
        # Logistic
        if outcome.dtype == 'object' or len(outcome.unique()) > 2:
             unique_vals = sorted(outcome.unique())
             outcome = (outcome == unique_vals[-1]).astype(int)
        model = sm.Logit(outcome, X).fit(disp=0)
        r_squared = model.prsquared
        
    coef_data = []
    for name in model.params.index:
        entry = {
            "variable": name,
            "coefficient": float(model.params[name]),
            "p_value": float(model.pvalues[name]),
            "std_err": float(model.bse[name]),
            "ci_lower": float(model.conf_int().loc[name][0]),
            "ci_upper": float(model.conf_int().loc[name][1])
        }
        if method_id == "logistic_regression":
             entry["odds_ratio"] = float(np.exp(model.params[name]))
             entry["or_ci_lower"] = float(np.exp(model.conf_int().loc[name][0]))
             entry["or_ci_upper"] = float(np.exp(model.conf_int().loc[name][1]))
        coef_data.append(entry)

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
        "roc": roc_out
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
             norm_results[str(g)] = {"p_value": float(p_norm), "passed": is_norm}
         assumptions["normality"] = norm_results
         is_homo, p_homo, _ = check_homogeneity(data_groups)
         assumptions["homogeneity"] = {"p_value": float(p_homo), "passed": is_homo}
    return assumptions

def _generate_warnings(method_str, path_type="group", assumptions=None):
    warnings = []
    if path_type == "group":
        parametric_methods = ["t_test_ind", "t_test_welch", "t_test_rel", "anova", "rm_anova"]
        if method_str in parametric_methods:
            norm_res = assumptions.get("normality", {})
            failed_groups = [g for g, res in norm_res.items() if not res["passed"]]
            if failed_groups:
                warnings.append(f"Normality assumption failed for groups: {', '.join(failed_groups)}. Consider using a non-parametric test.")
        
        strict_homogeneity = ["t_test_ind", "anova"]
        if method_str in strict_homogeneity:
            homo_res = assumptions.get("homogeneity")
            if homo_res and not homo_res["passed"]:
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
                shapiro_w = _safe_float(w)
                shapiro_p = _safe_float(p)
            except Exception:
                shapiro_w = None
                shapiro_p = None

        ci_95_low = None
        ci_95_high = None
        if se is not None:
            ci_95_low = _safe_float(mean - 1.96 * se)
            ci_95_high = _safe_float(mean + 1.96 * se)

        return {
            "count": n,
            "missing": missing,
            "mean": _safe_float(mean),
            "median": _safe_float(valid.median()),
            "mode": _safe_float(mode_val),
            "std": _safe_float(std),
            "se": _safe_float(se),
            "variance": _safe_float(valid.var(ddof=1) if n > 1 else 0.0),
            "min": _safe_float(valid.min()),
            "max": _safe_float(valid.max()),
            "range": _safe_float(valid.max() - valid.min()),
            "q1": _safe_float(q1),
            "q3": _safe_float(q3),
            "iqr": _safe_float(iqr),
            "skewness": _safe_float(valid.skew()),
            "kurtosis": _safe_float(valid.kurt()),
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

def run_batch_analysis(df: pd.DataFrame, targets: List[str], group_col: str, method_id: str = "t_test_ind", alpha: float = 0.05) -> List[Dict[str, Any]]:
    """
    Runs analysis for multiple targets against a group column.
    Applies Benjamini-Hochberg (FDR) correction to p-values.
    """
    results = []
    p_values = []
    
    # 1. Run Analysis for each target
    for target in targets:
        try:
            # Auto-detect method if needed, but usually batch implies same method
            # For MVP assume same method or auto-detect based on target type?
            # Let's enforce method_id for consistency in batch
            
            # Skip if target not in df
            if target not in df.columns:
                continue
                
            res = run_analysis(df, method_id, target, group_col, alpha=alpha)
            
            # Store raw result
            res["target"] = target
            results.append(res)
            p_values.append(res["p_value"])
            
        except Exception as e:
            logger.error(f"Batch Error for {target}: {e}", exc_info=True)
            results.append({"target": target, "error": str(e), "p_value": 1.0})
            p_values.append(1.0)
            
    # 2. FDR Correction
    if results:
        reject, pvals_corrected, _, _ = multipletests(p_values, alpha=alpha, method='fdr_bh')
        
        for i, res in enumerate(results):
            res["p_value_adj"] = float(pvals_corrected[i])
            res["significant_adj"] = bool(reject[i])
            
    return results


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
        return {"error": "time_col is required for mixed_model"}
    if not subject_col:
        return {"error": "subject_col is required for mixed_model"}
    
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
        result["method"] = "mixed_model"
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
        
        return {
            "method": "friedman",
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < alpha,
            "n_subjects": len(data),
            "n_timepoints": len(outcome_cols)
        }
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
        return {"error": "At least 2 variables are required"}
    
    available_vars = [v for v in variables if v in df.columns]
    if len(available_vars) < 2:
        return {"error": f"Only {len(available_vars)} variables found in dataset"}
    
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
    
    return result
