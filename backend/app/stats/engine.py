from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from lifelines import KaplanMeierFitter
from lifelines.statistics import logrank_test
from app.stats.registry import METHODS

def check_normality(data: pd.Series) -> bool:
    """
    Shapiro-Wilk test for normality.
    Returns True if likely normal (p > 0.05).
    """
    clean_data = data.dropna()
    if len(clean_data) < 3:
        return False
    if len(clean_data) > 5000:
        clean_data = clean_data.sample(5000, random_state=42)
    
    try:
        _, p_value = stats.shapiro(clean_data)
        return p_value > 0.05
    except:
        return False

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
    all_normal = True
    for g in groups:
        subset = df[df[cat_col] == g][num_col].dropna()
        if not check_normality(subset):
            all_normal = False
            break
            
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
    
    # Group tests
    group_tests = ["t_test_ind", "mann_whitney", "t_test_rel", "wilcoxon", "anova", "kruskal"]
    
    if method_id in group_tests:
        groups = clean_df[col_b].unique()
        # Sort groups for consistency
        groups = sorted(groups)
        data_groups = [clean_df[clean_df[col_b] == g][col_a] for g in groups]
        
        stat_val, p_val = 0.0, 1.0
        
        if method_id == "t_test_ind" and len(groups) == 2:
            stat_val, p_val = stats.ttest_ind(data_groups[0], data_groups[1])
        elif method_id == "mann_whitney" and len(groups) == 2:
            stat_val, p_val = stats.mannwhitneyu(data_groups[0], data_groups[1])
        elif method_id == "anova":
            stat_val, p_val = stats.f_oneway(*data_groups)
        elif method_id == "kruskal":
            stat_val, p_val = stats.kruskal(*data_groups)
        elif method_id == "t_test_rel" and len(groups) == 2:
             # Requires matched pairs, for MVP we assume dataframe order is preserved
             stat_val, p_val = stats.ttest_rel(data_groups[0], data_groups[1])
        elif method_id == "wilcoxon" and len(groups) == 2:
             stat_val, p_val = stats.wilcoxon(data_groups[0], data_groups[1])

        # Prepare Plot Data
        plot_data = []
        plot_stats = {}
        for i, g in enumerate(groups):
            vals = data_groups[i]
            mean = float(vals.mean())
            std = float(vals.std()) if len(vals) > 1 else 0
            n = len(vals)
            sem = std / np.sqrt(n) if n > 0 else 0
            # 95% Confidence Interval
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
            # Limit points for visualization
            sample_vals = vals.sample(min(len(vals), 500)) if len(vals) > 500 else vals
            for v in sample_vals:
                plot_data.append({"group": str(g), "value": float(v)})

        return {
            "method": method_id,
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < 0.05,
            "groups": [str(g) for g in groups],
            "plot_data": plot_data,
            "plot_stats": plot_stats
        }

    # Correlation
    elif method_id in ["pearson", "spearman"]:
        x = clean_df[col_a]
        y = clean_df[col_b]
        
        if method_id == "pearson":
            stat_val, p_val = stats.pearsonr(x, y)
        else:
            stat_val, p_val = stats.spearmanr(x, y)
            
        # Linear Regression for trend line
        slope, intercept, r_value, _, _ = stats.linregress(x, y)
        
        # Sample points for visualization (scatter)
        plot_data = []
        # Limit to 1000 points for scatter
        sample_indices = np.random.choice(clean_df.index, min(len(clean_df), 1000), replace=False)
        for idx in sample_indices:
            plot_data.append({
                "x": float(clean_df.loc[idx, col_a]),
                "y": float(clean_df.loc[idx, col_b])
            })
            
        return {
            "method": method_id,
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < 0.05,
            "regression": {
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r_value**2)
            },
            "plot_data": plot_data
        }

    # Categorical
    elif method_id == "chi_square":
        ct = pd.crosstab(clean_df[col_a], clean_df[col_b])
        stat_val, p_val, _, _ = stats.chi2_contingency(ct)
        return {
            "method": method_id,
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < 0.05
        }

    # Survival Analysis
    elif method_id == "survival_km":
        
        # duration = col_a, event = col_b, group = col_extra (if provided)
        duration = clean_df[col_a]
        event = clean_df[col_b]
        
        # For survival, we need to know if there's a group column to compare
        # We'll assume the caller might pass a 3rd col or we use a global approach
        # Let's use 'group_col' if passed or default to single group
        group_col = kwargs.get("group_col")
        
        plot_data = [] # Will store line points for step plot
        groups = ["Overall"]
        p_val = 1.0
        
        if group_col and group_col in df.columns:
            groups = sorted(df[group_col].dropna().unique())
            kmfs = {}
            for g in groups:
                subset = df[df[group_col] == g]
                kmf = KaplanMeierFitter()
                kmf.fit(subset[col_a], event_observed=subset[col_b], label=str(g))
                kmfs[g] = kmf
                
                # Extract timeline points for Recharts step-plot
                for time, prob in zip(kmf.survival_function_.index, kmf.survival_function_.values.flatten()):
                     plot_data.append({"time": float(time), "probability": float(prob), "group": str(g)})
            
            # Log-rank test if 2 groups
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
            "stat_value": 0.0, # Log-rank stat can be added if needed
            "p_value": float(p_val),
            "significant": p_val < 0.05,
            "groups": groups,
            "plot_data": plot_data
        }

    # Predictive Analytics (Regression)
    elif method_id in ["linear_regression", "logistic_regression"]:
        
        # Outcome is col_a
        # Predictors are passed as a list in kwargs['predictors'] or inferred from col_b
        predictors = kwargs.get("predictors")
        if not predictors:
             predictors = [col_b]
             
        # Clean DF based on ALL involved columns
        cols_to_clean = [col_a] + predictors
        clean_df = df[cols_to_clean].dropna()
        
        outcome = clean_df[col_a]
        # Convert categorical predictors to dummies
        X = pd.get_dummies(clean_df[predictors], drop_first=True)
        # Ensure all columns are float/int
        X = X.astype(float)
        X = sm.add_constant(X) # Add intercept
        
        if method_id == "linear_regression":
            model = sm.OLS(outcome, X).fit()
            r_squared = model.rsquared
        else:
            # For logistic, outcome must be 0/1. We'll attempt to encode it if categorical.
            if outcome.dtype == 'object' or len(outcome.unique()) > 2:
                 # Very basic encoding for binary
                 unique_vals = sorted(outcome.unique())
                 outcome = (outcome == unique_vals[-1]).astype(int)
            
            model = sm.Logit(outcome, X).fit(disp=0)
            r_squared = model.prsquared # Pseudo R-squared
            
        # Extract coefficients
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

    raise ValueError(f"Method {method_id} not implemented")

def compute_batch_descriptives(df: pd.DataFrame, target_cols: List[str], group_col: str) -> List[Dict[str, Any]]:
    from scipy.stats import shapiro
    results = []
    groups = df[group_col].dropna().unique()
    for col in target_cols:
        if col not in df.columns: continue
        for g in groups:
            subset = df[df[group_col] == g][col].dropna()
            if len(subset) == 0: continue
            
            # Shapiro-Wilk test for normality
            shapiro_w, shapiro_p, is_normal = None, None, True
            if len(subset) >= 3 and len(subset) <= 5000:
                try:
                    shapiro_w, shapiro_p = shapiro(subset)
                    is_normal = shapiro_p > 0.05
                except:
                    pass
            
            results.append({
                "variable": str(col), 
                "group": str(g), 
                "count": int(len(subset)),
                "mean": float(subset.mean()), 
                "median": float(subset.median()),
                "sd": float(subset.std()) if len(subset) > 1 else 0.0,
                "shapiro_w": shapiro_w,
                "shapiro_p": shapiro_p,
                "is_normal": is_normal
            })
    return results