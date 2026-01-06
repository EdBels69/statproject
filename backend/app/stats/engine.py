from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.oneway import anova_oneway
from statsmodels.stats.multitest import multipletests
from sklearn.metrics import roc_curve, auc, roc_auc_score
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.statistics import logrank_test
from lifelines.statistics import logrank_test
from app.stats.registry import METHODS
from app.modules.narrative import NarrativeGenerator

GROUP_TESTS = ["t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon", "anova", "anova_welch", "kruskal"]

def calc_cohens_d(d1, d2):
    n1, n2 = len(d1), len(d2)
    s1, s2 = np.var(d1, ddof=1), np.var(d2, ddof=1)
    # Pooled SD
    s_pool = np.sqrt(((n1-1)*s1 + (n2-1)*s2) / (n1+n2-2))
    return (np.mean(d1) - np.mean(d2)) / s_pool if s_pool > 0 else 0


def validate_group_column(df: pd.DataFrame, group_col: str) -> dict:
    """
    Validates group column for common data issues.
    Returns dict with 'valid' bool and optional 'error' or 'warnings'.
    """
    if group_col not in df.columns:
        return {"valid": False, "error": f"Column '{group_col}' not found"}
    
    groups = df[group_col].dropna().unique()
    warnings = []
    
    # Check assumptions
    # Normality (Shapiro-Wilk) - strict, maybe too strict for small N
    # Homogeneity (Levene)
    
    post_hoc_results = []
    # Check for suspicious group values (concatenated strings)
    for g in groups:
        g_str = str(g)
        # Detect repeated patterns (e.g., "мужскоймужской")
        if len(g_str) > 20:
            warnings.append(f"Group value '{g_str[:30]}...' is unusually long")
        # Detect potential concatenation
        if len(g_str) > 10:
            half = len(g_str) // 2
            if g_str[:half] == g_str[half:half*2]:
                warnings.append(f"Group '{g_str[:30]}...' appears to contain repeated values")
    
    # Check number of groups
    if len(groups) > 50:
        warnings.append(f"Too many groups ({len(groups)}). Consider using fewer categories.")
    
    if len(groups) < 2:
        return {"valid": False, "error": "Need at least 2 groups for comparison"}
    
    return {
        "valid": True,
        "groups": [str(g) for g in groups],
        "n_groups": len(groups),
        "warnings": warnings if warnings else None
    }

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

def select_test(df: pd.DataFrame, col_a: str, col_b: str, types: Dict[str, str], is_paired: bool = False) -> str:
    """
    Auto-selects the appropriate statistical test.
    """
    type_a = types.get(col_a)
    type_b = types.get(col_b)
    
    # 1. Two Numeric (Correlation)
    if type_a == "numeric" and type_b == "numeric":
        if is_paired: 
             # Paired usually implies Mean Difference, but double numeric args usually means correlation
             # unless the user explicitly requested "Paired T-Test" logic which uses "Group" column?
             # If "Group" column is used, type_b would be categorical.
             pass
        
        # Check normality for Pearson vs Spearman
        # Simple sample check
        is_norm_a, _, _ = check_normality(df[col_a])
        is_norm_b, _, _ = check_normality(df[col_b])
        if is_norm_a and is_norm_b:
            return "pearson"
        return "spearman"
        
    # 2. One Numeric, One Categorical (Group Comparison)
    # Determine which is target (numeric) and which is group (categorical)
    if type_a == "numeric" and type_b == "categorical":
        target, group = col_a, col_b
    elif type_a == "categorical" and type_b == "numeric":
        target, group = col_b, col_a
    else:
        # This case should be handled by correlation or chi-square
        # Or if one is numeric and the other is None (e.g., one-sample test)
        # For now, return None and let the caller handle it or raise error
        if type_a == "categorical" and type_b == "categorical":
            return "chi_square"
        return None # Or raise an error if no suitable test found

    if not group or group not in df.columns:
        return None
        
    groups = df[group].dropna().unique()
    n_groups = len(groups)
    
    if n_groups < 2: 
        # If only one group, it might be a one-sample test if target is numeric
        # But select_test is for comparing two columns.
        # For now, return None, let run_analysis handle one-sample if method_id is explicitly "t_test_one"
        return None 
    
    # 2.1 Paired Analysis (Group indicates Timepoint/Condition)
    if is_paired:
        if n_groups == 2:
            # Check Normality of Difference?
            # Hard to do without reshaping. Assume Wilcoxon if unsure.
            # Simplified: T-test Paired if > 30 obs, else Wilcoxon
            return "t_test_rel" # Let internal logic switch if needed
        elif n_groups >= 3:
            # For paired 3+ groups, select the independent equivalent,
            # and run_analysis will transform it to RM ANOVA or Friedman.
            # Check normality for each group
            all_normal = True
            groups_data = []
            for g in groups:
                subset = df[df[group] == g][target].dropna()
                is_normal, _, _ = check_normality(subset)
                if not is_normal:
                    all_normal = False
                groups_data.append(subset)
            
            if all_normal:
                return "anova" # Will be transformed to rm_anova
            else:
                return "kruskal" # Will be transformed to friedman
            
    # 2.2 Independent Analysis
    if n_groups == 2:
        # Check Normality
        # Extract data
        g1 = df[df[group] == groups[0]][target].dropna()
        g2 = df[df[group] == groups[1]][target].dropna()
        
        norm1, _, _ = check_normality(g1)
        norm2, _, _ = check_normality(g2)
        homo, _, _ = check_homogeneity([g1, g2])
        
        if norm1 and norm2:
             if homo: return "t_test_ind"
             else: return "t_test_welch"
        else:
             return "mann_whitney"
             
    if n_groups >= 3:
         # Check Normality
        data_groups = [df[df[group] == g][target].dropna() for g in groups]
        all_norm = all(check_normality(d)[0] for d in data_groups)
        homo, _, _ = check_homogeneity(data_groups)
        
        if all_norm:
             if homo: return "anova"
             else: return "anova_welch"
        else:
             return "kruskal"
             
    # 3. Two Categorical (Chi-Square)
    if type_a == "categorical" and type_b == "categorical":
        # Check sample size constraints for Fisher?
        # Default Chi-Square, switch internally
        return "chi_square"
        
    return None

def run_analysis(
    df: pd.DataFrame, 
    method_id: str, 
    col_a: str, 
    col_b: str,
    is_paired: bool = False,
    **kwargs
) -> Dict[str, Any]:
    """
    Executes a specific statistical test.
    """
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
    
    # Dispatcher
    handlers = {
        "t_test_ind": _handle_t_test_ind,
        "t_test_welch": _handle_t_test_ind,
        "t_test_rel": _handle_paired_comparison,
        "mann_whitney": _handle_mann_whitney, # Customized Handler
        "wilcoxon": _handle_paired_comparison,
        "anova": _handle_group_comparison_v2,
        "anova_welch": _handle_group_comparison_v2,
        "kruskal": _handle_group_comparison_v2,
        "rm_anova": _handle_rm_anova,
        "friedman": _handle_friedman_test,
        "pearson": _handle_correlation,
        "spearman": _handle_correlation,
        "kendall": _handle_correlation,
        "chi_square": _handle_chi_square,
        "fisher": _handle_chi_square, # Fisher is handled by chi_square internally
        "t_test_one": _handle_one_sample,
        "linear_regression": _handle_regression,
        "logistic_regression": _handle_regression,
        "survival_km": _handle_survival,
        "roc_analysis": _handle_roc_analysis,
        "cox_regression": _handle_cox_regression,
    }
    
    if method_id not in handlers:
        raise ValueError(f"Method {method_id} not supported.")
        
    # Check Paired Overrides
    if is_paired:
        if method_id == "t_test_ind": method_id = "t_test_rel"
        elif method_id == "mann_whitney": method_id = "wilcoxon"
        elif method_id == "anova": method_id = "rm_anova"
        elif method_id == "kruskal": method_id = "friedman"

    # Execute matched handler
    if method_id in handlers:
        result = handlers[method_id](clean_df, method_id, col_a, col_b, kwargs)
    else:
        raise ValueError(f"Method {method_id} not implemented")
        
    # Inject Narrative
    if result and "error" not in result:
        try:
            narrator = NarrativeGenerator()
            result["narrative"] = narrator.generate_narrative(result)
        except Exception as e:
            # Do not fail analysis if narrative fails
            result["narrative"] = f"Narrative generation failed: {str(e)}"
            
    return result


def _handle_cox_regression(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    """
    col_a = Duration (Numeric)
    col_b = Event (Binary)
    kwargs['predictors'] = List of covariates
    """
    # 1. Setup
    duration = col_a
    event = col_b
    predictors = kwargs.get("predictors", [])
    
    if not predictors:
        return {"error": "Cox Regression requires at least one covariate/predictor."}
    
    # 2. Prepare Data
    cols = [duration, event] + predictors
    data = df[cols].dropna() 
    
    # Check minimum samples
    if len(data) < 10:
        return {"error": f"Not enough data (n={len(data)}) for Cox Regression."}
    
    # One-Hot Encode Categorical Predictors
    # But Keep Duration/Event as is
    # We let pandas auto-detect categorical columns (object/category/bool)
    # If we pass columns=predictors, it forces encoding even for numeric predictors (BAD!)
    data_encoded = pd.get_dummies(data, drop_first=True)
    
    # 3. Fit Model
    cph = CoxPHFitter(penalizer=0.01) # Add slight penalizer to handle collinearity/convergence
    
    try:
        cph.fit(data_encoded, duration_col=duration, event_col=event)
        
        # 4. Extract Results
        summary = cph.summary # DataFrame
        # columns: coef, exp(coef) (=HR), se(coef), coef lower 95%, coef upper 95%, exp(coef) lower 95%, exp(coef) upper 95%, z, p, -log2(p)
        
        coef_data = []
        plot_data = [] # Forest plot data
        
        for idx, row in summary.iterrows():
            hr = row['exp(coef)']
            lower = row['exp(coef) lower 95%']
            upper = row['exp(coef) upper 95%']
            p_val = row['p']
            
            coef_data.append({
                "variable": str(idx),
                "hazard_ratio": float(hr),
                "ci_lower": float(lower),
                "ci_upper": float(upper),
                "p_value": float(p_val),
                "significant": float(p_val) < 0.05
            })
            
            # Forest Plot Format
            plot_data.append({
                "variable": str(idx),
                "hr": float(hr),
                "lower": float(lower),
                "upper": float(upper)
            })
            
        return {
            "method": method_id,
            "stat_value": float(cph.log_likelihood_), # Log-Likelihood as 'stat'
            "p_value": float(cph.log_likelihood_ratio_test().p_value), # Overall Model P-value
            "significant": float(cph.log_likelihood_ratio_test().p_value) < 0.05,
            "coefficients": coef_data,
            "concordance_index": float(cph.concordance_index_),
            "plot_data": plot_data,
            "plot_config": {
                "type": "forest", 
                "title": "Hazard Ratios (95% CI)",
                "x_label": "Hazard Ratio (log scale)"
            }
        }
        
    except Exception as e:
        return {"error": f"Cox Fit Failed: {str(e)}", "method": method_id}


def _handle_group_comparison(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    """
    col_a = Target numeric variable
    col_b = Grouping factor
    """
    # 1. Validate Group Column
    validation = validate_group_column(df, col_b)
    if not validation["valid"]:
        return {
            "error": validation.get("error", "Invalid group column"),
            "method": method_id,
            "p_value": None,
            "significant": False
        }
    
    # 2. Get Data by Group
    groups = validation["groups"]
    data_groups = [df[df[col_b].astype(str) == g][col_a].dropna() for g in groups]
    
    # Check for empty groups
    msg_empty = []
    data_groups_clean = []
    groups_clean = []
    
    for g, d in zip(groups, data_groups):
        if len(d) < 2:
            msg_empty.append(g)
        else:
            data_groups_clean.append(d)
            groups_clean.append(g)
            
    if len(data_groups_clean) < 2:
        return {
            "error": f"Not enough valid groups. Groups {msg_empty} have fewer than 2 samples.",
            "method": method_id,
            "p_value": None
        }
        
    data_groups = data_groups_clean
    groups = groups_clean
    
    stat_val, p_val = 0, 1.0
    eff_size = None
    post_hoc_results = []
    
    # 3. Warn about validation issues
    warnings = validation.get("warnings") or []

    # Map kwargs
    alt = kwargs.get("alternative", "two-sided")
    
    if method_id == "t_test_ind" and len(groups) == 2:
        stat_val, p_val = stats.ttest_ind(data_groups[0], data_groups[1], equal_var=True, alternative=alt)
        eff_size = calc_cohens_d(data_groups[0], data_groups[1])
        
    elif method_id == "t_test_welch" and len(groups) == 2:
        stat_val, p_val = stats.ttest_ind(data_groups[0], data_groups[1], equal_var=False, alternative=alt)
        eff_size = calc_cohens_d(data_groups[0], data_groups[1])
        
    elif method_id == "mann_whitney" and len(groups) == 2:
        stat_val, p_val = stats.mannwhitneyu(data_groups[0], data_groups[1], alternative=alt)
        
    elif method_id == "anova":
        stat_val, p_val = stats.f_oneway(*data_groups) 
        
        # Post-hoc Tukey HSD if significant
        if p_val < 0.05:
            post_hoc_results = _run_tukey_posthoc(data_groups, groups)

    elif method_id == "anova_welch":
        # Welch's ANOVA via statsmodels
        # Flatten data for statsmodels input
        res = anova_oneway(
            data=pd.concat(data_groups), 
            groups=np.concatenate([[g]*len(d) for g,d in zip(groups, data_groups)]), 
            use_var="unequal"
        )
        stat_val = res.statistic
        p_val = res.pvalue
        
        # Post-hoc Games-Howell (Tukey is for equal var)
        # Statsmodels doesn't natively have Games-Howell in multicomp easily accessible,
        # usually people use pingouin or implement it manually.
        # Fallback: We'll list Tukey but warn user, or simpler: just show Tukey for MVP.
        # Ideally, we should add Games-Howell. But for now let's reuse Tukey logic with a warning note if we can't easily add Games-Howell.
        # Actually, let's omit post-hoc for Welch ANOVA in this MVP iteration to avoid misleading results.
        if p_val < 0.05:
             # Just run Tukey for now as a "best effort" with warning in description if possible
             post_hoc_results = _run_tukey_posthoc(data_groups, groups)
             warnings.append("Used Tukey post-hoc; Games-Howell recommended for unequal variances.")

    elif method_id == "kruskal":
        stat_val, p_val = stats.kruskal(*data_groups)
        
    elif method_id == "t_test_rel" and len(groups) == 2:
         stat_val, p_val = stats.ttest_rel(data_groups[0], data_groups[1], alternative=alt)
         diff = np.array(data_groups[0]) - np.array(data_groups[1])
         eff_size = np.mean(diff) / np.std(diff, ddof=1) if len(diff) > 1 else 0

    elif method_id == "wilcoxon" and len(groups) == 2:
         stat_val, p_val = stats.wilcoxon(data_groups[0], data_groups[1], alternative=alt)
         
    # Prepare Plot Data
    plot_data, plot_stats, qq_data = _prepare_group_plot_data(groups, data_groups)

    # Calculate Assumptions
    assumptions = _check_assumptions(groups, data_groups)
    
    # Generate Smart Warnings
    warnings = _generate_warnings(method_id, path_type="group", assumptions=assumptions)

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "significant": p_val < 0.05,
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "qq_data": qq_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "post_hoc": post_hoc_results
    }


def _handle_t_test_ind(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    # 1. Split Data
    groups = df[col_b].unique()
    if len(groups) != 2:
        return {"error": f"T-test requires exactly 2 groups. Found {len(groups)}."}
        
    g1 = str(groups[0])
    g2 = str(groups[1])
    
    d1 = df[df[col_b] == g1][col_a].dropna()
    d2 = df[df[col_b] == g2][col_a].dropna()
    
    data_groups = [d1, d2]
    
    # Options
    alternative = kwargs.get("alternative", "two-sided") # two-sided, less, greater
    conf_level = float(kwargs.get("conf_level", 0.95))
    method_force = kwargs.get("method_force", "auto") # auto, student, welch
    use_permutation = kwargs.get("use_permutation", False)
    use_bootstrap = kwargs.get("use_bootstrap", False)
    
    # method_id might be "t_test_ind" or "t_test_welch" from auto-select
    # Override if forced
    equal_var = True
    if method_force == "welch":
        equal_var = False
        method_id = "t_test_welch"
    elif method_force == "student":
        equal_var = True
        method_id = "t_test_ind"
    else:
        # Auto: Use Levene
        stat_lev, p_lev = stats.levene(d1, d2)
        if p_lev < 0.05:
            equal_var = False
            method_id = "t_test_welch"
            
    # Run Test
    permutations = 10000 if use_permutation else None
    
    try:
        if permutations:
            # New SciPy support for permutations in ttest_ind
            # Check version or use try/except fallback? SciPy > 1.7 supports it.
            # Assuming env has recent scipy.
            res = stats.ttest_ind(d1, d2, equal_var=equal_var, alternative=alternative, permutations=permutations, random_state=42)
            stat_val, p_val = res.statistic, res.pvalue
        else:
            stat_val, p_val = stats.ttest_ind(d1, d2, equal_var=equal_var, alternative=alternative)
    except TypeError:
        # Fallback if permutations not supported by installed scipy
        stat_val, p_val = stats.ttest_ind(d1, d2, equal_var=equal_var, alternative=alternative)
        
    # Effect Size (Cohen's d)
    # d = (m1 - m2) / pooled_std
    n1, n2 = len(d1), len(d2)
    var1, var2 = np.var(d1, ddof=1), np.var(d2, ddof=1)
    
    if equal_var:
        pooled_var = ((n1 - 1)*var1 + (n2 - 1)*var2) / (n1 + n2 - 2)
        denom = np.sqrt(pooled_var)
    else:
        # For Welch, Cohen's d is tricky. Usually use root mean square of stds or just pooled.
        # Simple approach:
        denom = np.sqrt((var1 + var2) / 2)
        
    eff_size = (np.mean(d1) - np.mean(d2)) / denom if denom > 0 else 0
    
    # Confidence Interval for Difference
    # ttest_ind doesn't return CI directly in older versions, but let's calculate manually or use bootstrap
    ci_diff_low, ci_diff_high = None, None
    
    if use_bootstrap:
        # Bootstrap CI for mean difference
        try:
            def diff_means(x, y): return np.mean(x) - np.mean(y)
            res_boot = stats.bootstrap((d1, d2), diff_means, confidence_level=conf_level, n_resamples=5000, random_state=42, method='percentile')
            ci_diff_low = res_boot.confidence_interval.low
            ci_diff_high = res_boot.confidence_interval.high
        except Exception as e:
            print(f"Bootstrap failed: {e}")
    else:
        # Parametric CI
        # standard error of difference
        diff_mean = np.mean(d1) - np.mean(d2)
        if equal_var:
             se_diff = np.sqrt(pooled_var * (1/n1 + 1/n2))
             df_val = n1 + n2 - 2
        else:
             se_diff = np.sqrt(var1/n1 + var2/n2)
             # Welch-Satterthwaite df
             num = (var1/n1 + var2/n2)**2
             den = ( (var1/n1)**2 / (n1-1) ) + ( (var2/n2)**2 / (n2-1) )
             df_val = num/den if den > 0 else n1+n2-2
             
        # Critical t
        alpha = 1 - conf_level
        if alternative == "two-sided":
            crit_t = stats.t.ppf(1 - alpha/2, df_val)
            ci_diff_low = diff_mean - crit_t * se_diff
            ci_diff_high = diff_mean + crit_t * se_diff
        elif alternative == "less":
            # CI is (-inf, upper)
            crit_t = stats.t.ppf(1 - alpha, df_val)
            ci_diff_low = -np.inf
            ci_diff_high = diff_mean + crit_t * se_diff
        elif alternative == "greater":
            # CI is (lower, inf)
            crit_t = stats.t.ppf(1 - alpha, df_val)
            ci_diff_low = diff_mean - crit_t * se_diff
            ci_diff_high = np.inf
            
    # Prepare Plot Data (Pass params for correct visualization later if needed)
    plot_data, plot_stats, qq_data = _prepare_group_plot_data(groups, data_groups, conf_level=conf_level)

    # Calculate Assumptions
    assumptions = _check_assumptions(groups, data_groups)
    
    # Generate Smart Warnings
    warnings = _generate_warnings(method_id, path_type="group", assumptions=assumptions)
    if method_force == "auto" and not equal_var:
         warnings.append("Auto-switched to Welch's T-test due to unequal variances (Levene's test p < 0.05).")
    if method_force == "student" and not equal_var: 
         warnings.append("Forced Student's T-test used despite unequal variances! Results may be unreliable.")

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "significant": p_val < (1 - conf_level), # Significance depends on alpha
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "qq_data": qq_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "extra": {
            "ci_diff_low": float(ci_diff_low) if ci_diff_low is not None else None,
            "ci_diff_high": float(ci_diff_high) if ci_diff_high is not None else None,
            "conf_level": conf_level,
            "alternative": alternative,
            "used_permutation": bool(permutations) if permutations else False,
            "used_bootstrap": use_bootstrap
        }
    }


def _handle_mann_whitney(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    groups = df[col_b].unique()
    if len(groups) != 2:
        return {"error": f"Mann-Whitney requires exactly 2 groups. Found {len(groups)}."}

    g1, g2 = str(groups[0]), str(groups[1])
    d1 = df[df[col_b] == g1][col_a].dropna()
    d2 = df[df[col_b] == g2][col_a].dropna()
    
    data_groups = [d1, d2]

    alt = kwargs.get("alternative", "two-sided")
    use_continuity = kwargs.get("use_continuity", True)
    exact = kwargs.get("method_exact", False)
    
    method_arg = "exact" if exact else "auto"
    
    try:
        res = stats.mannwhitneyu(d1, d2, alternative=alt, use_continuity=use_continuity, method=method_arg)
        stat_val, p_val = res.statistic, res.pvalue
    except Exception as e:
        # Fallback
        res = stats.mannwhitneyu(d1, d2, alternative=alt, use_continuity=use_continuity, method="auto")
        stat_val, p_val = res.statistic, res.pvalue

    # Effect Size: Rank-Biserial
    n1, n2 = len(d1), len(d2)
    u = stat_val
    r_rb = 1 - (2 * u) / (n1 * n2)
    
    # Hodges-Lehmann (Median Difference)
    med_diff = None
    if n1 * n2 < 5000000: # Limit for performance
        try:
             # Only calculate if feasible
             diffs = np.subtract.outer(d1, d2).flatten()
             med_diff = float(np.median(diffs))
        except: pass

    plot_data, plot_stats, qq_data = _prepare_group_plot_data(groups, data_groups)
    assumptions = _check_assumptions(groups, data_groups)
    warnings = _generate_warnings(method_id, path_type="group", assumptions=assumptions)
    
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(r_rb),
        "significant": p_val < 0.05,
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "qq_data": qq_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "extra": {
             "hodges_lehmann": med_diff,
             "rank_biserial": float(r_rb)
        }
    }

def _handle_paired_comparison(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    """
    col_a = Variable 1
    col_b = Variable 2 (if wide) OR Group Column (if long)
    
    If Long Format (Target, Group): We need Subject ID?
    MVP: Assume paired T-Test is called on two NUMERIC columns (Wide Format) OR
    it is called on (Target, Group) with exactly 2 groups of equal length (implicit pairing).
    """
    
    # 1. Determine Data Structure
    d1, d2 = None, None
    g1_label, g2_label = "Var A", "Var B"
    groups = []
    
    if col_b in df.columns and df[col_b].dtype == 'object': # Likely Group Column (Long Format)
        groups_val = df[col_b].unique()
        if len(groups_val) == 2:
            g1_label, g2_label = str(groups_val[0]), str(groups_val[1])
            groups = [g1_label, g2_label]
            d1 = df[df[col_b] == g1_label][col_a]
            d2 = df[df[col_b] == g2_label][col_a]
            # Check lengths
            if len(d1) != len(d2):
                return {"error": "Paired tests require equal group sizes (implicit pairing)."}
            d1 = d1.reset_index(drop=True)
            d2 = d2.reset_index(drop=True)
        else:
             return {"error": "Paired comparison requires exactly 2 groups."} # Should be handled by rm_anova/friedman
    else:
        # Wide Format (Col A vs Col B)
        d1 = df[col_a]
        d2 = df[col_b]
        g1_label, g2_label = col_a, col_b
        groups = [g1_label, g2_label]

    # Clean NaNs pairwise
    valid_mask = ~d1.isna() & ~d2.isna()
    d1 = d1[valid_mask]
    d2 = d2[valid_mask]
    
    if len(d1) < 2:
        return {"error": "Not enough valid paired data points."}
        
    diff = d1 - d2
    
    # Options
    alternative = kwargs.get("alternative", "two-sided")
    conf_level = float(kwargs.get("conf_level", 0.95))
    
    # Paired T-Test Logic
    if method_id == "t_test_rel":
        use_permutation = kwargs.get("use_permutation", False)
        
        try:
             # Check permutation support
             res = stats.ttest_rel(d1, d2, alternative=alternative)
             # Basic SciPy doesn't have permutation for ttest_rel directly in all versions?
             # Check doc: ttest_rel(a, b, axis=0, nan_policy='propagate', alternative='two-sided')
             # It DOES NOT seem to have 'permutations' arg in standard scipy 1.7?
             # Actually `ttest_ind` does, `ttest_rel` might not yet?
             # Let's check: scipy 1.10+ has `permutations` for `ttest_rel`.
             # We will try it.
             if use_permutation:
                 try:
                     res = stats.ttest_rel(d1, d2, alternative=alternative, permutations=10000, random_state=42)
                 except TypeError:
                     # Fallback
                     res = stats.ttest_rel(d1, d2, alternative=alternative)
             else:
                 res = stats.ttest_rel(d1, d2, alternative=alternative)
                 
             stat_val, p_val = res.statistic, res.pvalue
             
        except Exception:
             stat_val, p_val = stats.ttest_rel(d1, d2, alternative=alternative) # basic fallback
             
        # Effect Size (Cohen's d for paired)
        # d = mean(diff) / std(diff)
        mean_diff = np.mean(diff)
        std_diff = np.std(diff, ddof=1)
        eff_size = mean_diff / std_diff if std_diff > 0 else 0
        
        # CI for Mean Difference
        # Standard SE = std_diff / sqrt(n)
        se_diff = std_diff / np.sqrt(len(diff))
        df_val = len(diff) - 1
        alpha = 1 - conf_level
        
        ci_low, ci_high = None, None
        if alternative == "two-sided":
            crit_t = stats.t.ppf(1 - alpha/2, df_val)
            ci_low = mean_diff - crit_t * se_diff
            ci_high = mean_diff + crit_t * se_diff
        elif alternative == "less":
            crit_t = stats.t.ppf(1 - alpha, df_val)
            ci_low = -np.inf
            ci_high = mean_diff + crit_t * se_diff
        elif alternative == "greater":
            crit_t = stats.t.ppf(1 - alpha, df_val)
            ci_low = mean_diff - crit_t * se_diff
            ci_high = np.inf

    # Wilcoxon Logic
    elif method_id == "wilcoxon":
        zero_method = kwargs.get("zero_method", "wilcox") # wilcox (discard), pratt, zsplit
        correction = kwargs.get("correction", True)
        mode = kwargs.get("mode", "auto")
        
        try:
            res = stats.wilcoxon(d1, d2, zero_method=zero_method, correction=correction, alternative=alternative, mode=mode)
            stat_val, p_val = res.statistic, res.pvalue
        except ValueError as e:
            # e.g. "zero_method 'exact' not valid..."
            return {"error": f"Wilcoxon Error: {e}"}
            
        # Effect Size (Rank-Biserial for Paired)
        # r = W / sum_ranks?
        # Simple r = Z / sqrt(N)? (Rosenthal)
        # Or standard r approx using W. 
        # For Wilcoxon, standard is r = Z / sqrt(N_pairs * 2) ?
        # Often r = Z / sqrt(N) where N is total observations?
        # Let's use simple matched-pairs rank biserial if possible.
        # r_rb = 1 - (2W / (N*(N+1)/2))? (Simpler for signed rank)
        # For signed rank W (sum of positive ranks?):
        # Total sum of ranks = N(N+1)/2. 
        # r = (Pos - Neg) / Total ?
        # This is a good proxy.
        # stats.wilcoxon returns W (smaller of sums?). No, recent scipy returns standardized or sum of signed.
        # Actually it returns a statistic.
        # Let's calculate effect size manually to be safe.
        abs_diff = np.abs(diff)
        ranks = stats.rankdata(abs_diff)
        pos_ranks = np.sum(ranks[diff > 0])
        neg_ranks = np.sum(ranks[diff < 0])
        total_ranks = pos_ranks + neg_ranks
        r_rb = (pos_ranks - neg_ranks) / total_ranks if total_ranks > 0 else 0
        eff_size = r_rb
        
        ci_low, ci_high = None, None # Hodges-Lehmann for Wilcoxon? (Median of Walsh Averages)
        # diff[i] + diff[j] / 2
        # Expensive to compute O(N^2). Skip for now or MVP like MannWhitney.
        if len(diff) < 1000:
             # Calculate Walsh averages
             walsh = []
             vals = diff.values
             n = len(vals)
             for i in range(n):
                 for j in range(i, n):
                     walsh.append((vals[i] + vals[j]) / 2)
             hl_est = np.median(walsh)
             # CI? Harder.
        else:
             hl_est = np.median(diff) # Simple median of differences
             
    else:
        return {"error": "Unknown paired method."}
        
    # Plots
    # Prepare plot data for paired (Difference plot?)
    # or just show the two distributions + Lines?
    plot_data, plot_stats, qq_data = _prepare_group_plot_data(groups, [d1, d2], conf_level=conf_level)
    
    # Add Difference Distribution for QQ
    qq_diff = []
    try:
        (osm, osr), _ = stats.probplot(diff, dist="norm", plot=None)
        if len(osm) > 200:
            indices = np.linspace(0, len(osm) - 1, 200).astype(int)
            osm = osm[indices]
            osr = osr[indices]
        for x, y in zip(osm, osr):
            qq_diff.append({"group": "Difference", "x": float(x), "y": float(y)})
    except: pass
    
    # Merge QQ data
    qq_data.extend(qq_diff)

    assumptions = _check_assumptions(groups, [d1, d2])
    warnings = _generate_warnings(method_id, path_type="group", assumptions=assumptions) # Paired specific warnings needed?

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size),
        "significant": p_val < (1 - conf_level),
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "qq_data": qq_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "extra": {
            "ci_low": float(ci_low) if ci_low is not None else None,
            "ci_high": float(ci_high) if ci_high is not None else None,
            "conf_level": conf_level,
            "alternative": alternative,
            "used_permutation": kwargs.get("use_permutation", False) if method_id == "t_test_rel" else False,
            "zero_method": kwargs.get("zero_method") if method_id == "wilcoxon" else None
        }
    }

def _handle_rm_anova(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    return {"error": "Repeated Measures ANOVA not fully implemented yet.", "method": method_id}

def _handle_friedman_test(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    return {"error": "Friedman Test not fully implemented yet.", "method": method_id}

def _run_tukey_posthoc(data_groups, groups):
    try:
        all_vals = []
        all_groups = []
        for i, g in enumerate(groups):
            vals = data_groups[i]
            all_vals.extend(vals)
            all_groups.extend([g]*len(vals))
        
        tukey = pairwise_tukeyhsd(endog=all_vals, groups=all_groups, alpha=0.05)
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
        print(f"Post-hoc failed: {e}")
        return []

def _handle_one_sample(df, method_id, col_a, kwargs):
    data = df[col_a]
    test_val = float(kwargs.get("test_value", 0))
    alt = kwargs.get("alternative", "two-sided")
    
    stat_val, p_val = stats.ttest_1samp(data, test_val, alternative=alt)
    eff_size = (data.mean() - test_val) / data.std(ddof=1) if len(data) > 1 else 0
    
    plot_data = [{"value": float(v)} for v in data]
    mean = float(data.mean())
    std = float(data.std())
    
    # QQ
    qq_data = []
    try:
        (osm, osr), _ = stats.probplot(data.dropna(), dist="norm", plot=None)
        if len(osm) > 200:
            indices = np.linspace(0, len(osm) - 1, 200).astype(int)
            osm = osm[indices]
            osr = osr[indices]
        for x, y in zip(osm, osr):
            qq_data.append({"group": "Sample", "x": float(x), "y": float(y)})
    except:
        pass

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < 0.05,
        "groups": ["Sample"],
        "plot_data": plot_data,
        "qq_data": qq_data,
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

def _handle_correlation(df, method_id, col_a, col_b, kwargs=None):
    if kwargs is None: kwargs = {}
    x, y = df[col_a], df[col_b] # Already cleaned in run_analysis? Yes clean_df passed.
    
    # Double check cleaning (NaNs) just to be safe if not strictly enforced before
    valid_mask = ~np.isnan(x) & ~np.isnan(y)
    x = x[valid_mask]
    y = y[valid_mask]
    
    if len(x) < 2:
        return {"error": "Not enough data points for correlation."}

    # Extract Options
    # If method_id in ["pearson", "spearman"], user might still override via kwargs?
    # Or prioritize kwargs['method'] if provided (from UI selector).
    method = kwargs.get("method", method_id)
    if method not in ["pearson", "spearman", "kendall"]:
        method = "pearson" # Default
        
    alternative = kwargs.get("alternative", "two-sided")
    conf_level = float(kwargs.get("conf_level", 0.95))
    
    stat_val, p_val = 0, 0
    ci_low, ci_high = None, None
    
    try:
        if method == "pearson":
            # SciPy 1.7+ supports alternative
            res = stats.pearsonr(x, y, alternative=alternative)
            stat_val, p_val = res.statistic, res.pvalue
            
            # Fisher Z Transformation for CI
            # r = stat_val
            # z = arctanh(r)
            # se = 1/sqrt(N-3)
            # CI_z = z +/- Z_crit * se
            # CI_r = tanh(CI_z)
            
            if len(x) > 3:
                r = stat_val
                # Clip r to [-1, 1] to avoid math domain error in arctanh
                r = max(min(r, 0.999999), -0.999999)
                z = np.arctanh(r)
                se = 1 / np.sqrt(len(x) - 3)
                
                alpha = 1 - conf_level
                if alternative == "two-sided":
                    z_crit = stats.norm.ppf(1 - alpha/2)
                    ci_z_low = z - z_crit * se
                    ci_z_high = z + z_crit * se
                elif alternative == "less":
                    z_crit = stats.norm.ppf(1 - alpha)
                    ci_z_low = -np.inf
                    ci_z_high = z + z_crit * se
                elif alternative == "greater":
                    z_crit = stats.norm.ppf(1 - alpha)
                    ci_z_low = z - z_crit * se
                    ci_z_high = np.inf
                
                ci_low = np.tanh(ci_z_low) if ci_z_low != -np.inf else -1.0
                ci_high = np.tanh(ci_z_high) if ci_z_high != np.inf else 1.0
                
        elif method == "spearman":
            res = stats.spearmanr(x, y, alternative=alternative)
            stat_val, p_val = res.statistic, res.pvalue
            
        elif method == "kendall":
            res = stats.kendalltau(x, y, alternative=alternative)
            stat_val, p_val = res.statistic, res.pvalue
            
    except Exception as e:
        return {"error": f"Correlation Analysis Failed: {str(e)}"}

    slope, intercept, r_value, _, _ = stats.linregress(x, y)
    
    # Plot Data (Sampled)
    plot_data = []
    sample_indices = np.random.choice(df.index[valid_mask], min(len(x), 1000), replace=False)
    # Re-index to match clean data
    
    # Actually 'x' and 'y' are Series with original indices. 
    # Just iterate valid pairs
    if len(x) > 1000:
       # subsample for plot
       indices = np.random.choice(len(x), 1000, replace=False)
       x_plot = x.iloc[indices]
       y_plot = y.iloc[indices]
    else:
       x_plot = x
       y_plot = y
       
    for i in range(len(x_plot)):
        plot_data.append({"x": float(x_plot.iloc[i]), "y": float(y_plot.iloc[i])})

    data_col_a = df[col_a].dropna()
    data_col_b = df[col_b].dropna()
    
    qq_data = [] # Add if needed, or minimal
    
    return {
        "method": method,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < (1 - conf_level),
        "groups": ["Sample"],
        "plot_data": plot_data,
        "qq_data": [],
        "plot_stats": {
            "group": {
                "mean_x": float(np.mean(x)),
                "mean_y": float(np.mean(y)),
                "count": len(x)
            }
        },
        "extra": {
            "ci_low": float(ci_low) if ci_low is not None else None,
            "ci_high": float(ci_high) if ci_high is not None else None,
            "slope": float(slope),
            "intercept": float(intercept),
            "conf_level": conf_level,
            "alternative": alternative
        }
    }



def _handle_chi_square(df, method_id, col_a, col_b):
    ct = pd.crosstab(df[col_a], df[col_b])
    
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
        "significant": p_val < 0.05,
        "warning": warning
    }

def _handle_survival(df, method_id, col_a, col_b, kwargs):
    duration = df[col_a]
    event = df[col_b]
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
        "significant": p_val < 0.05,
        "groups": groups,
        "plot_data": plot_data
    }

def _handle_regression(df, method_id, col_a, col_b, kwargs):
    predictors = kwargs.get("predictors", [col_b])
    cols_to_clean = [col_a] + predictors
    clean_df = df[cols_to_clean].dropna() # Re-clean locally for predictors
    
    outcome = clean_df[col_a]
    X = pd.get_dummies(clean_df[predictors], drop_first=True).astype(float)
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
        
    return {
        "method": method_id,
        "stat_value": float(model.fvalue) if hasattr(model, 'fvalue') else 0.0,
        "p_value": float(model.f_pvalue) if hasattr(model, 'f_pvalue') else float(model.pvalues.min()),
        "significant": any(model.pvalues < 0.05),
        "r_squared": float(r_squared),
        "coefficients": coef_data
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
        
    # Bootstrap for AUC CI
    n_bootstraps = 1000
    rng = np.random.RandomState(42)
    bootstrapped_scores = []
    
    y_true_np = np.array(y_true_bin)
    y_score_np = np.array(y_score)
    
    # Simple bootstrap (resample indices)
    for i in range(n_bootstraps):
        indices = rng.randint(0, len(y_true_np), len(y_true_np))
        if len(np.unique(y_true_np[indices])) < 2:
            continue
        sc = roc_auc_score(y_true_np[indices], y_score_np[indices])
        bootstrapped_scores.append(sc)
        
    sorted_scores = np.array(bootstrapped_scores)
    sorted_scores.sort()
    
    ci_lower = sorted_scores[int(0.025 * len(sorted_scores))]
    ci_upper = sorted_scores[int(0.975 * len(sorted_scores))]
    
    p_vs_05 = 0.0 # P-value vs AUC=0.5
    # Standard Error of AUC (Hanley & McNeil, 1982 approximation is faster but bootstrap is fine)
    # Using simple SE from bootstrap
    auc_se = np.std(sorted_scores)
    
    # Avoid div by zero if SE is 0 (perfect separation in all bootstraps)
    if auc_se > 0:
        z = (roc_auc - 0.5) / auc_se
        import scipy.stats as stats
        p_vs_05 = 2 * (1 - stats.norm.cdf(abs(z)))
    else:
        p_vs_05 = 0.0 if roc_auc > 0.5 else 1.0

    return {
        "method": method_id,
        "auc": float(roc_auc),
        "auc_ci_lower": float(ci_lower),
        "auc_ci_upper": float(ci_upper),
        "p_value": float(p_vs_05),
        "best_threshold": float(thresholds[best_idx]),
        "youden_index": float(j_scores[best_idx]),
        "sensitivity": float(tpr[best_idx]),
        "specificity": float(1 - fpr[best_idx]),
        "pos_label": str(pos_label),
        "neg_label": str(neg_label),
        "significant": float(p_vs_05) < 0.05,
        "plot_data": roc_data,
        "plot_config": {"x_label": "False Positive Rate", "y_label": "True Positive Rate", "type": "line"}
    }

def _prepare_group_plot_data(groups, data_groups):
    plot_data = []
    qq_data = [] # New Q-Q Data
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
            
        # Q-Q Data
        clean_vals = vals.dropna()
        if len(clean_vals) > 3:
            try:
                (osm, osr), _ = stats.probplot(clean_vals, dist="norm", plot=None)
                # Sample if too large
                if len(osm) > 200:
                    indices = np.linspace(0, len(osm) - 1, 200).astype(int)
                    osm = osm[indices]
                    osr = osr[indices]
                
                for x, y in zip(osm, osr):
                    qq_data.append({"group": str(g), "x": float(x), "y": float(y)})
            except:
                pass
                
    return plot_data, plot_stats, qq_data

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
        
    # Get Groups
    groups = df[group].dropna().unique()
    clean_df = df[[target, group]].dropna() # Ensure clean_df exists
    results = {}
    for g in groups:
        subset = clean_df[clean_df[group] == g][target]
        desc = {
            "count": int(len(subset)),
            "mean": float(subset.mean()),
            "median": float(subset.median()),
            "std": float(subset.std()) if len(subset) > 1 else 0.0,
            "min": float(subset.min()),
            "max": float(subset.max()),
            "q1": float(subset.quantile(0.25)),
            "q3": float(subset.quantile(0.75)),
        }
        # CI 95%
        if len(subset) > 1:
            sem = desc["std"] / np.sqrt(desc["count"])
            desc["ci_lower"] = float(desc["mean"] - 1.96 * sem)
            desc["ci_upper"] = float(desc["mean"] + 1.96 * sem)
            
        results[str(g)] = desc
        
    # Overall
    results["overall"] = {
        "mean": float(clean_df[target].mean()),
        "count": int(len(clean_df))
    }
    
    return results

def run_batch_analysis(df: pd.DataFrame, targets: List[str], group_col: str, method_id: str = "t_test_ind") -> List[Dict[str, Any]]:
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
                
            res = run_analysis(df, method_id, target, group_col)
            
            # Store raw result
            res["target"] = target
            results.append(res)
            p_values.append(res["p_value"])
            
        except Exception as e:
            print(f"Batch Error for {target}: {e}")
            results.append({"target": target, "error": str(e), "p_value": 1.0})
            p_values.append(1.0)
            
    # 2. FDR Correction
    if results:
        reject, pvals_corrected, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')
        
        for i, res in enumerate(results):
            res["p_value_adj"] = float(pvals_corrected[i])
            res["significant_adj"] = bool(reject[i])
            
    return results

def compute_batch_descriptives(df: pd.DataFrame, target_cols: List[str], group_col: str) -> List[Dict[str, Any]]:
    # Legacy wrapper
    return run_batch_analysis(df, target_cols, group_col, "t_test_ind")

def _handle_correlation_matrix(df: pd.DataFrame, variables: List[str], method: str = "pearson", cluster_variables: bool = False):
    # Filter numeric
    cols = [c for c in variables if c in df.columns]
    data = df[cols].select_dtypes(include=[np.number])
    
    if data.shape[1] < 2:
        return {"error": "Need at least 2 numeric variables for correlation matrix."}
        
    # Correlation Matrix
    corr_matrix = data.corr(method=method)
    
    # P-values Matrix
    p_values = pd.DataFrame(np.ones(corr_matrix.shape), columns=corr_matrix.columns, index=corr_matrix.index)
    for c1 in corr_matrix.columns:
        for c2 in corr_matrix.columns:
            if c1 != c2:
                # dropna for pairwise
                valid = data[[c1, c2]].dropna()
                if len(valid) > 2:
                    if method == "pearson":
                        _, p = stats.pearsonr(valid[c1], valid[c2])
                    elif method == "spearman":
                        _, p = stats.spearmanr(valid[c1], valid[c2])
                    elif method == "kendall":
                        _, p = stats.kendalltau(valid[c1], valid[c2])
                    else:
                        _, p = stats.pearsonr(valid[c1], valid[c2])
                    p_values.loc[c1, c2] = p
                    
    # Plot Heatmap / Clustermap
    img_b64 = None
    reordered_cols = cols
    
    try:
        import seaborn as sns
        import matplotlib.pyplot as plt
        import io
        import base64
        plt.switch_backend('Agg')
        
        # Determine figure size
        n = len(corr_matrix)
        figsize = (max(8, n * 0.8), max(8, n * 0.8))
        
        buf = io.BytesIO()
        
        if cluster_variables and n > 2:
            # Clustermap
            # Fill NaNs for clustering (corr matrix default handles it, but just in case)
            cm_safe = corr_matrix.fillna(0)
            
            # Create clustermap
            g = sns.clustermap(cm_safe, 
                               method='average', 
                               metric='euclidean',
                               cmap="coolwarm", 
                               vmin=-1, vmax=1, 
                               annot=True, 
                               fmt=".2f",
                               figsize=figsize,
                               tree_kws=dict(linewidths=1.5))
            
            # Extract reordered columns
            reordered_ind = g.dendrogram_row.reordered_ind
            reordered_cols = [corr_matrix.columns[i] for i in reordered_ind]
            
            # Reorder matrices for return
            corr_matrix = corr_matrix.iloc[reordered_ind, reordered_ind]
            p_values = p_values.iloc[reordered_ind, reordered_ind]
            
            g.savefig(buf, format='png', dpi=100)
            plt.close() # g is a ClusterGrid, it manages its own fig usually, but safe to close plt
            
        else:
            # Regular Heatmap
            plt.figure(figsize=figsize)
            sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", vmin=-1, vmax=1, fmt=".2f")
            plt.title(f"{method.capitalize()} Correlation Matrix")
            plt.tight_layout()
            plt.savefig(buf, format='png', dpi=100)
            plt.close()
            
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
    except Exception as e:
        print(f"Heatmap error: {e}")
        import traceback
        traceback.print_exc()

    return {
        "method": method,
        "corr_matrix": corr_matrix.to_dict(), # Nested dict [col][row]
        "p_values": p_values.to_dict(),
        "plot_image": img_b64,
        "variables": reordered_cols,
        "clustered": cluster_variables and len(data.columns) > 2,
        "n_obs": len(data)
    }

def _handle_regression(df: pd.DataFrame, target: str, predictors: List[str], method: str = "auto"):
    """
    Perform OLS or Logit Regression using statsmodels.
    """
    import statsmodels.api as sm
    import numpy as np
    
    # 1. Prepare Data
    cols = [target] + predictors
    missing_cols = [c for c in cols if c not in df.columns]
    if missing_cols:
        return {"error": f"Missing columns: {missing_cols}"}
        
    data = df[cols].dropna()
    if len(data) < len(predictors) + 2:
        return {"error": "Not enough data for this model."}
        
    X = data[predictors]
    y = data[target]
    
    # Add constant (intercept)
    X = sm.add_constant(X)
    
    # 2. Determine Method
    if method == "auto":
        # Check if target is binary
        unique_vals = np.sort(y.unique())
        if len(unique_vals) == 2 and set(unique_vals).issubset({0, 1}):
            method = "logit"
        else:
            method = "ols"
            
    # 3. Fit Model
    res = None
    try:
        if method == "logit":
            model = sm.Logit(y, X)
            res = model.fit(disp=0)
        else:
            model = sm.OLS(y, X)
            res = model.fit()
    except Exception as e:
        return {"error": f"Model fit failed: {e}"}
        
    # 4. Extract Results
    # Coeff Table
    summary = res.summary2().tables[1]
    # Summary2 table cols: Coef., Std.Err., z/t, P>|z|, [0.025, 0.975]
    
    coef_table = []
    for idx, row in summary.iterrows():
        variable = idx
        coef = row.iloc[0]
        std_err = row.iloc[1]
        p_val = row.iloc[3] # 4th col usually p-value
        ci_lower = row.iloc[4]
        ci_upper = row.iloc[5]
        
        # Odds ratio for Logit
        or_val = np.exp(coef) if method == "logit" and variable != "const" else None
        
        coef_table.append({
            "variable": variable,
            "coef": float(coef),
            "std_err": float(std_err),
            "p_value": float(p_val),
            "ci_lower": float(ci_lower),
            "ci_upper": float(ci_upper),
            "odds_ratio": float(or_val) if or_val else None
        })
        
    # Model Fit Stats
    fit_stats = {
        "aic": float(res.aic),
        "bic": float(res.bic),
        "n_obs": int(res.nobs),
        "r_squared": float(res.rsquared) if hasattr(res, "rsquared") else float(res.prsquared) # Pseudo R2 for logit
    }
    
    # 5. Diagnostic Plot (Actual vs Predicted)
    img_b64 = None
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        import io
        import base64
        
        plt.figure(figsize=(6, 6))
        
        if method == "logit":
            # ROC Curve?
            from sklearn.metrics import roc_curve, auc
            y_pred = res.predict(X)
            fpr, tpr, _ = roc_curve(y, y_pred)
            roc_auc = auc(fpr, tpr)
            
            plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.2f})')
            plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title('Receiver Operating Characteristic')
            plt.legend(loc="lower right")
            
        else: # OLS
            # Actual vs Predicted
            y_pred = res.predict(X)
            sns.scatterplot(x=y, y=y_pred, alpha=0.6)
            # Perfect fit line
            mn, mx = min(y.min(), y_pred.min()), max(y.max(), y_pred.max())
            plt.plot([mn, mx], [mn, mx], color='red', linestyle='--')
            plt.xlabel("Actual")
            plt.ylabel("Predicted")
            plt.title("Actual vs Predicted")
            
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Regression plot error: {e}")

    return {
        "method": method,
        "coef_table": coef_table,
        "fit_stats": fit_stats,
        "plot_image": img_b64,
        "target": target,
        "predictors": predictors,
        "plot_data": { 
            "type": "roc" if method == "logit" else "scatter",
            "x": fpr.tolist() if method == "logit" else y.tolist(),
            "y": tpr.tolist() if method == "logit" else y_pred.tolist(),
            "auc": roc_auc if method == "logit" else None
        }
    }

def _handle_survival(df: pd.DataFrame, time_col: str, event_col: str, group_col: str = None):
    """
    Kaplan-Meier Survival Analysis using lifelines.
    """
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    import seaborn as sns
    from lifelines import KaplanMeierFitter
    from lifelines.statistics import logrank_test
    import io
    import base64
    
    T = df[time_col]
    E = df[event_col]
    
    kmf = KaplanMeierFitter()
    
    plot_data = [] # For optional frontend interactive chart
    median_survival = {}
    p_value = None
    
    img_b64 = None
    try:
        plt.figure(figsize=(10, 6))
        
        if group_col and group_col in df.columns:
            groups = df[group_col].unique()
            for g in groups:
                 mask = (df[group_col] == g)
                 kmf.fit(T[mask], event_observed=E[mask], label=str(g))
                 kmf.plot_survival_function(ci_show=False) # Plot on same axis
                 median_survival[str(g)] = float(kmf.median_survival_time_) if not np.isinf(kmf.median_survival_time_) else "Not Reached"
                 
                 # Save raw data for re-plotting
                 plot_data.append({
                     "group": str(g),
                     "time": kmf.survival_function_.index.tolist(),
                     "prob": kmf.survival_function_.iloc[:, 0].tolist()
                 })
            
            plt.title(f"Survival Analysis by {group_col}")
            
            # Log-rank test if 2 groups (or pairwise? Logrank handles k groups?)
            # lifelines logrank_test is for 2 groups. multivariate_logrank_test for >2.
            if len(groups) >= 2:
                 from lifelines.statistics import multivariate_logrank_test
                 res = multivariate_logrank_test(T, df[group_col], E)
                 p_value = float(res.p_value)

        else:
            kmf.fit(T, event_observed=E, label="Overall")
            kmf.plot_survival_function()
            median_survival["Overall"] = float(kmf.median_survival_time_)
            plt.title(f"Overall Survival Analysis")
            
            plot_data.append({
                 "group": "Overall",
                 "time": kmf.survival_function_.index.tolist(),
                 "prob": kmf.survival_function_.iloc[:, 0].tolist()
             })
            
        plt.xlabel(f"Time ({time_col})")
        plt.ylabel("Survival Probability")
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
    except Exception as e:
        return {"error": f"Survival plot failed: {e}"}
        
    return {
        "method": "Kaplan-Meier",
        "median_survival": median_survival,
        "p_value": p_value,
        "plot_image": img_b64,
        "time_col": time_col,
        "event_col": event_col,
        "plot_data": plot_data
    }

def _handle_group_comparison_v2(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict):
    """
    Advanced Handler for ANOVA / Kruskal / Welch
    """
    # 1. Validate Group Column
    validation = validate_group_column(df, col_b)
    if not validation["valid"]:
        return {
            "error": validation.get("error", "Invalid group column"),
            "method": method_id,
            "p_value": None,
            "significant": False
        }
    
    # 2. Get Data by Group
    groups = validation["groups"]
    data_groups = [df[df[col_b].astype(str) == g][col_a].dropna() for g in groups]
    
    # Check for empty groups
    msg_empty = []
    data_groups_clean = []
    groups_clean = []
    
    for g, d in zip(groups, data_groups):
        if len(d) < 2:
            msg_empty.append(g)
        else:
            data_groups_clean.append(d)
            groups_clean.append(g)
            
    if len(data_groups_clean) < 2:
        return {
            "error": f"Not enough valid groups. Groups {msg_empty} have fewer than 2 samples.",
            "method": method_id,
            "p_value": None
        }
        
    data_groups = data_groups_clean
    groups = groups_clean
    
    stat_val, p_val = 0, 1.0
    eff_size = None
    post_hoc_results = []
    warnings = validation.get("warnings") or []
    assumptions = {}

    # Options
    post_hoc_method = kwargs.get("post_hoc", "tukey")
    eff_size_type = kwargs.get("effect_size_type", "eta_sq")
    homogeneity_test = kwargs.get("homogeneity_test", "levene")
    method_force = kwargs.get("method_force", "auto")
    
    # Homogeneity Check
    homo_p = 0.0
    if homogeneity_test == "bartlett":
        try:
             _, homo_val = stats.bartlett(*data_groups)
             homo_p = homo_val
             assumptions["homogeneity_bartlett"] = {"p_value": float(homo_p), "passed": homo_p > 0.05}
        except: pass
    else:
        try:
             _, homo_val = stats.levene(*data_groups)
             homo_p = homo_val
             # update assumptions later
        except: pass

    # Auto-Switch Logic
    if method_id == "anova" and method_force == "auto":
        if homo_p < 0.05 and homo_p > 0:
            method_id = "anova_welch"
            warnings.append("Auto-switched to Welch ANOVA due to unequal variances.")
            
    if method_force == "welch": method_id = "anova_welch"
    if method_force == "anova": method_id = "anova"
    
    # Run Test
    if method_id == "anova":
        stat_val, p_val = stats.f_oneway(*data_groups) 
        
        # Effect Size (Eta/Omega Squared)
        try:
            k = len(data_groups)
            all_data = np.concatenate(data_groups)
            N = len(all_data)
            grand_mean = np.mean(all_data)
            ss_total = np.sum((all_data - grand_mean)**2)
            ss_within = sum(np.sum((d - np.mean(d))**2) for d in data_groups)
            ss_between = ss_total - ss_within
            
            if eff_size_type == "eta_sq":
                eff_size = ss_between / ss_total if ss_total > 0 else 0
            elif eff_size_type == "omega_sq":
                df_between = k - 1
                df_within = N - k
                ms_within = ss_within / df_within if df_within > 0 else 0
                eff_size = (ss_between - df_between * ms_within) / (ss_total + ms_within) if (ss_total + ms_within) > 0 else 0
        except: pass
        
        # Post-hoc
        if p_val < 0.05:
            if post_hoc_method == "tukey":
                post_hoc_results = _run_tukey_posthoc(data_groups, groups)
            else:
                 post_hoc_results = _run_pairwise_posthoc(data_groups, groups, method=post_hoc_method, parametric=True)

    elif method_id == "anova_welch":
        try:
            res = stats.alexandergovern(*data_groups)
            stat_val, p_val = res.statistic, res.pvalue
        except (AttributeError, ImportError):
             try:
                 from statsmodels.stats.oneway import anova_oneway
                 res = anova_oneway(pd.concat(data_groups), groups=np.concatenate([[g]*len(d) for g,d in zip(groups, data_groups)]), use_var="unequal")
                 stat_val, p_val = res.statistic, res.pvalue
             except:
                 stat_val, p_val = stats.f_oneway(*data_groups)
                 warnings.append("Welch ANOVA not supported, used standard ANOVA.")

        if p_val < 0.05:
             if post_hoc_method == "tukey":
                 post_hoc_results = _run_tukey_posthoc(data_groups, groups)
                 warnings.append("Tukey HSD assumes equal variances.")
             else:
                 post_hoc_results = _run_pairwise_posthoc(data_groups, groups, method=post_hoc_method, parametric=True, equal_var=False)

    elif method_id == "kruskal":
        stat_val, p_val = stats.kruskal(*data_groups)
        # Eta Squared on Ranks
        try:
            k = len(data_groups)
            N = sum(len(d) for d in data_groups)
            if N > k:
                 eff_size = (stat_val - k + 1) / (N - k)
                 eff_size = max(0, min(1, eff_size))
        except: pass
        
        if p_val < 0.05:
             post_hoc_results = _run_pairwise_posthoc(data_groups, groups, method=post_hoc_method, parametric=False)

    # Plot Data & Assumptions
    plot_data, plot_stats, qq_data = _prepare_group_plot_data(groups, data_groups)
    assumptions.update(_check_assumptions(groups, data_groups))
    warnings.extend(_generate_warnings(method_id, path_type="group", assumptions=assumptions))
    
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "significant": p_val < 0.05,
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "qq_data": qq_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "post_hoc": post_hoc_results,
        "extra": {"eff_size_type": eff_size_type, "post_hoc_method": post_hoc_method}
    }

def _run_pairwise_posthoc(data_groups, groups, method="fdr_bh", parametric=True, equal_var=True):
    import itertools
    from statsmodels.stats.multitest import multipletests
    
    pairs = list(itertools.combinations(range(len(groups)), 2))
    p_vals_raw = []
    pair_names = []
    
    for i1, i2 in pairs:
         g1, g2 = data_groups[i1], data_groups[i2]
         if parametric:
             _, pp = stats.ttest_ind(g1, g2, equal_var=equal_var)
         else:
             _, pp = stats.mannwhitneyu(g1, g2)
         p_vals_raw.append(pp)
         pair_names.append(f"{groups[i1]} vs {groups[i2]}")
         
    results = []
    if p_vals_raw:
         sm_method = "fdr_bh"
         if method == "bonferroni": sm_method = "bonferroni"
         if method == "holm": sm_method = "holm"
         if method == "sidak": sm_method = "sidak"
         if method == "fdr_bh" or method == "benjamini-hochberg": sm_method = "fdr_bh"
         if method == "fdr_tsbky" or method == "benjamini-krieger-yekutieli": sm_method = "fdr_tsbky"
         
         try:
            reject, pvals_corrected, _, _ = multipletests(p_vals_raw, alpha=0.05, method=sm_method)
         except Exception as e:
            # Fallback if method not found (e.g. tsbky might need statsmodels version?)
            # or if TSBKY failing on small p-values?
            print(f"Correction {sm_method} failed: {e}. Falling back to fdr_bh.")
            reject, pvals_corrected, _, _ = multipletests(p_vals_raw, alpha=0.05, method='fdr_bh')
         
         for name, raw, adj, sig in zip(pair_names, p_vals_raw, pvals_corrected, reject):
             results.append({
                 "comparison": name,
                 "p_value": float(adj),
                 "raw_p": float(raw),
                 "significant": bool(sig)
             })
    return results 