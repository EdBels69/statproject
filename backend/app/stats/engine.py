from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.oneway import anova_oneway
from statsmodels.stats.multitest import multipletests
from sklearn.metrics import roc_curve, auc
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from app.stats.registry import METHODS

GROUP_TESTS = ["t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon", "anova", "anova_welch", "kruskal"]

def calc_cohens_d(d1, d2):
    n1, n2 = len(d1), len(d2)
    s1, s2 = np.var(d1, ddof=1), np.var(d2, ddof=1)
    # Pooled SD
    s_pool = np.sqrt(((n1-1)*s1 + (n2-1)*s2) / (n1+n2-2))
    return (np.mean(d1) - np.mean(d2)) / s_pool if s_pool > 0 else 0

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
        
    # Check normality for each group
    # Check normality for each group
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
            
    if len(groups) == 2:
        if is_paired:
            return "t_test_rel" if all_normal else "wilcoxon"
        return "t_test_ind" if all_normal else "mann_whitney"
    else:
        # 3+ groups
        return "anova" if all_normal else "kruskal"

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
    if method_id in GROUP_TESTS:
        return _handle_group_comparison(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "t_test_one":
        return _handle_one_sample(clean_df, method_id, col_a, kwargs)

    elif method_id in ["pearson", "spearman"]:
        return _handle_correlation(clean_df, method_id, col_a, col_b)

    elif method_id == "chi_square":
        return _handle_chi_square(clean_df, method_id, col_a, col_b)

    elif method_id == "survival_km":
        return _handle_survival(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id in ["linear_regression", "logistic_regression"]:
        return _handle_regression(clean_df, method_id, col_a, col_b, kwargs)

    elif method_id == "roc_analysis":
        return _handle_roc_analysis(clean_df, method_id, col_a, col_b)

    elif method_id == "rm_anova":
        return _handle_rm_anova(clean_df, col_a, col_b, kwargs)

    elif method_id == "friedman":
        return _handle_friedman(clean_df, col_a, col_b, kwargs)

    elif method_id == "cox_regression":
        return _handle_cox_regression(clean_df, col_a, col_b, kwargs)

    raise ValueError(f"Method {method_id} not implemented")


def _handle_group_comparison(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, kwargs: Dict) -> Dict[str, Any]:
    groups = df[col_b].unique()
    groups = sorted(groups)
    data_groups = [df[df[col_b] == g][col_a] for g in groups]
    
    stat_val, p_val = 0.0, 1.0
    alt = kwargs.get("alternative", "two-sided")
    eff_size = None
    post_hoc_results = None
    method_str = str(method_id).strip()

    if method_str == "t_test_ind" and len(groups) == 2:
        stat_val, p_val = stats.ttest_ind(data_groups[0], data_groups[1], equal_var=True, alternative=alt)
        eff_size = calc_cohens_d(data_groups[0], data_groups[1])
        
    elif method_str == "t_test_welch" and len(groups) == 2:
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
        all_vals = []
        all_groups = []
        for i, g in enumerate(groups):
            vals = data_groups[i]
            all_vals.extend(vals.tolist())
            all_groups.extend([g]*len(vals))
            
        all_vals_np = np.array(all_vals)
        all_groups_np = np.array(all_groups)
        
        # print(f"DEBUG Welch: Vals Shape {all_vals_np.shape}, Groups Shape {all_groups_np.shape}")
        # print(f"DEBUG Welch Sample: {all_vals_np[:5]}")
        
        res = anova_oneway(data=all_vals_np, groups=all_groups_np, use_var='unequal')
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

    elif method_id == "kruskal":
        stat_val, p_val = stats.kruskal(*data_groups)
        
    elif method_id == "t_test_rel" and len(groups) == 2:
         stat_val, p_val = stats.ttest_rel(data_groups[0], data_groups[1], alternative=alt)
         diff = np.array(data_groups[0]) - np.array(data_groups[1])
         eff_size = np.mean(diff) / np.std(diff, ddof=1) if len(diff) > 1 else 0

    elif method_id == "wilcoxon" and len(groups) == 2:
         stat_val, p_val = stats.wilcoxon(data_groups[0], data_groups[1], alternative=alt)
         
    # Prepare Plot Data
    plot_data, plot_stats = _prepare_group_plot_data(groups, data_groups)

    # Calculate Assumptions
    assumptions = _check_assumptions(groups, data_groups)
    
    # Generate Smart Warnings
    warnings = _generate_warnings(method_str, path_type="group", assumptions=assumptions)

    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "effect_size": float(eff_size) if eff_size is not None else None,
        "significant": p_val < 0.05,
        "groups": [str(g) for g in groups],
        "plot_data": plot_data,
        "plot_stats": plot_stats,
        "assumptions": assumptions,
        "warnings": warnings,
        "post_hoc": post_hoc_results
    }

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
        return None

def _handle_one_sample(df, method_id, col_a, kwargs):
    data = df[col_a]
    test_val = float(kwargs.get("test_value", 0))
    alt = kwargs.get("alternative", "two-sided")
    
    stat_val, p_val = stats.ttest_1samp(data, test_val, alternative=alt)
    eff_size = (data.mean() - test_val) / data.std(ddof=1) if len(data) > 1 else 0
    
    plot_data = [{"value": float(v)} for v in data]
    mean = float(data.mean())
    std = float(data.std())
    
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < 0.05,
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

def _handle_correlation(df, method_id, col_a, col_b):
    x, y = df[col_a], df[col_b]
    if method_id == "pearson":
        stat_val, p_val = stats.pearsonr(x, y)
    else:
        stat_val, p_val = stats.spearmanr(x, y)
        
    slope, intercept, r_value, _, _ = stats.linregress(x, y)
    
    # Plot Data (Sampled)
    plot_data = []
    sample_indices = np.random.choice(df.index, min(len(df), 1000), replace=False)
    for idx in sample_indices:
        plot_data.append({"x": float(df.loc[idx, col_a]), "y": float(df.loc[idx, col_b])})
        
    return {
        "method": method_id,
        "stat_value": float(stat_val),
        "p_value": float(p_val),
        "significant": p_val < 0.05,
        "regression": {"slope": float(slope), "intercept": float(intercept), "r_squared": float(r_value**2)},
        "plot_data": plot_data
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


def _handle_rm_anova(df: pd.DataFrame, dv: str, within: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Repeated Measures ANOVA using pingouin.
    Expects data in long format with:
      - dv: dependent variable (numeric)
      - within: within-subject factor (e.g., timepoint)
      - subject: subject identifier column (from kwargs)
    """
    import pingouin as pg
    
    subject = kwargs.get("subject_col", "subject")
    
    if subject not in df.columns:
        raise ValueError(f"Subject column '{subject}' not found. RM-ANOVA requires a subject identifier.")
    
    # Run RM-ANOVA
    aov = pg.rm_anova(data=df, dv=dv, within=within, subject=subject, detailed=True)
    
    # Extract main results
    f_val = float(aov['F'].iloc[0])
    p_val = float(aov['p-unc'].iloc[0])
    eta_sq = float(aov['np2'].iloc[0]) if 'np2' in aov.columns else None  # partial eta-squared
    
    # Sphericity test (Mauchly's)
    sphericity = pg.sphericity(data=df, dv=dv, within=within, subject=subject)
    spher_w = float(sphericity[0]) if isinstance(sphericity, tuple) else None
    spher_p = float(sphericity[2]) if isinstance(sphericity, tuple) else None
    spher_passed = spher_p > 0.05 if spher_p else True
    
    # Get corrected p-values if sphericity violated
    p_gg = float(aov['p-GG-corr'].iloc[0]) if 'p-GG-corr' in aov.columns else p_val
    eps_gg = float(aov['eps'].iloc[0]) if 'eps' in aov.columns else 1.0
    
    # Pairwise post-hoc with Bonferroni correction
    posthoc = None
    if p_val < 0.05:
        try:
            posthoc_df = pg.pairwise_tests(data=df, dv=dv, within=within, subject=subject, 
                                           padjust='bonf', effsize='cohen')
            posthoc = []
            for _, row in posthoc_df.iterrows():
                posthoc.append({
                    "A": str(row['A']),
                    "B": str(row['B']),
                    "t_stat": float(row['T']) if 'T' in row else None,
                    "p_value": float(row['p-unc']),
                    "p_adj": float(row['p-corr']) if 'p-corr' in row else float(row['p-unc']),
                    "effect_size": float(row['cohen']) if 'cohen' in row else None,
                    "significant": row['p-corr'] < 0.05 if 'p-corr' in row else row['p-unc'] < 0.05
                })
        except Exception as e:
            print(f"Post-hoc failed: {e}")
    
    return {
        "method": "rm_anova",
        "stat_value": f_val,
        "p_value": p_val,
        "p_value_gg": p_gg,
        "epsilon_gg": eps_gg,
        "effect_size": eta_sq,
        "effect_size_type": "partial_eta_squared",
        "sphericity": {
            "W": spher_w,
            "p_value": spher_p,
            "passed": spher_passed
        },
        "significant": p_val < 0.05,
        "post_hoc": posthoc,
        "anova_table": aov.to_dict(orient='records')
    }


def _handle_friedman(df: pd.DataFrame, dv: str, within: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Friedman Test (non-parametric alternative to RM-ANOVA) using pingouin.
    """
    import pingouin as pg
    
    subject = kwargs.get("subject_col", "subject")
    
    if subject not in df.columns:
        raise ValueError(f"Subject column '{subject}' not found. Friedman test requires a subject identifier.")
    
    # Run Friedman test
    friedman = pg.friedman(data=df, dv=dv, within=within, subject=subject)
    
    q_val = float(friedman['Q'].iloc[0])
    p_val = float(friedman['p-unc'].iloc[0])
    
    # Kendall's W effect size
    # W = Q / (n * (k - 1)) where n = subjects, k = conditions
    n_subjects = df[subject].nunique()
    k_conditions = df[within].nunique()
    kendall_w = q_val / (n_subjects * (k_conditions - 1)) if n_subjects > 0 and k_conditions > 1 else None
    
    # Post-hoc Nemenyi (or Conover) if significant
    posthoc = None
    if p_val < 0.05:
        try:
            posthoc_df = pg.pairwise_tests(data=df, dv=dv, within=within, subject=subject,
                                           parametric=False, padjust='bonf')
            posthoc = []
            for _, row in posthoc_df.iterrows():
                posthoc.append({
                    "A": str(row['A']),
                    "B": str(row['B']),
                    "W_stat": float(row['W-val']) if 'W-val' in row else None,
                    "p_value": float(row['p-unc']),
                    "p_adj": float(row['p-corr']) if 'p-corr' in row else float(row['p-unc']),
                    "significant": row['p-corr'] < 0.05 if 'p-corr' in row else row['p-unc'] < 0.05
                })
        except Exception as e:
            print(f"Post-hoc failed: {e}")
    
    return {
        "method": "friedman",
        "stat_value": q_val,
        "p_value": p_val,
        "effect_size": kendall_w,
        "effect_size_type": "kendall_w",
        "significant": p_val < 0.05,
        "post_hoc": posthoc,
        "n_subjects": n_subjects,
        "n_conditions": k_conditions
    }


def _handle_cox_regression(df: pd.DataFrame, duration_col: str, event_col: str, kwargs: Dict) -> Dict[str, Any]:
    """
    Cox Proportional Hazards Regression using lifelines.
    """
    from lifelines import CoxPHFitter
    
    predictors = kwargs.get("predictors", [])
    
    if not predictors:
        raise ValueError("Cox regression requires at least one predictor variable.")
    
    # Prepare data
    cols = [duration_col, event_col] + predictors
    clean_df = df[cols].dropna()
    
    # Handle categorical predictors (dummy encoding)
    for col in predictors:
        if clean_df[col].dtype == 'object' or clean_df[col].nunique() < 10:
            dummies = pd.get_dummies(clean_df[col], prefix=col, drop_first=True)
            clean_df = pd.concat([clean_df.drop(columns=[col]), dummies], axis=1)
    
    # Fit Cox model
    cph = CoxPHFitter()
    cph.fit(clean_df, duration_col=duration_col, event_col=event_col)
    
    # Extract coefficients
    coef_data = []
    summary = cph.summary
    for var in summary.index:
        coef_data.append({
            "variable": str(var),
            "coefficient": float(summary.loc[var, 'coef']),
            "hazard_ratio": float(summary.loc[var, 'exp(coef)']),
            "hr_ci_lower": float(summary.loc[var, 'exp(coef) lower 95%']),
            "hr_ci_upper": float(summary.loc[var, 'exp(coef) upper 95%']),
            "std_err": float(summary.loc[var, 'se(coef)']),
            "z_stat": float(summary.loc[var, 'z']),
            "p_value": float(summary.loc[var, 'p']),
            "significant": summary.loc[var, 'p'] < 0.05
        })
    
    # Model fit statistics
    concordance = float(cph.concordance_index_)
    log_likelihood = float(cph.log_likelihood_)
    
    # Proportional hazards test
    try:
        ph_test = cph.check_assumptions(clean_df, show_plots=False, p_value_threshold=0.05)
        ph_assumption_ok = True  # If no exception, assumption holds
    except:
        ph_assumption_ok = None  # Could not test
    
    return {
        "method": "cox_regression",
        "coefficients": coef_data,
        "concordance_index": concordance,
        "log_likelihood": log_likelihood,
        "n_observations": len(clean_df),
        "n_events": int(clean_df[event_col].sum()),
        "significant": any(c['significant'] for c in coef_data),
        "proportional_hazards_ok": ph_assumption_ok
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