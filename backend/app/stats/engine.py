from typing import Dict, Any, List
import pandas as pd
from scipy import stats
from app.stats.registry import METHODS

def check_normality(data: pd.Series) -> bool:
    """
    Shapiro-Wilk test for normality.
    Returns True if likely normal (p > 0.05), False otherwise.
    Limit to 5000 valid samples because Shapiro is sensitive to large N.
    """
    clean_data = data.dropna()
    if len(clean_data) < 3:
        return False # Can't say
    
    if len(clean_data) > 5000:
        clean_data = clean_data.sample(5000)
    
    stat, p_value = stats.shapiro(clean_data)
    return p_value > 0.05

def select_test(
    df: pd.DataFrame, 
    col_a: str, 
    col_b: str, 
    types: Dict[str, str],
    is_paired: bool = False
) -> str:
    """
    Returns the ID of the recommended method.
    types: {'col_a': 'numeric', 'col_b': 'categorical'}
    """
    type_a = types.get(col_a)
    type_b = types.get(col_b)
    
    # CASE 1: Numeric vs Numeric -> Correlation
    if type_a == "numeric" and type_b == "numeric":
        # Check normality for both
        norm_a = check_normality(df[col_a])
        norm_b = check_normality(df[col_b])
        
        if norm_a and norm_b:
            return "pearson"
        return "spearman"

    # CASE 2: Categorical vs Categorical -> Chi-Square
    if type_a == "categorical" and type_b == "categorical":
        # Check table size for Fisher? (Skip for MVP, default to Chi2)
        return "chi_square"

    # CASE 3: Numeric vs Categorical (Group comparison)
    # Identify which is which
    num_col = col_a if type_a == "numeric" else col_b
    cat_col = col_b if type_a == "numeric" else col_a
    
    # Check number of groups
    groups = df[cat_col].dropna().unique()
    if len(groups) != 2:
        return None # ANOVA/Kruskal not supported in MVP yet
    
    # Split data
    group1 = df[df[cat_col] == groups[0]][num_col]
    group2 = df[df[cat_col] == groups[1]][num_col]
    
    # Check normality
    norm1 = check_normality(group1)
    norm2 = check_normality(group2)
    
    if is_paired:
        if norm1 and norm2:
            return "t_test_rel"
        return "wilcoxon"
    else:
        if norm1 and norm2:
            return "t_test_ind"
        return "mann_whitney"

def run_analysis(
    df: pd.DataFrame, 
    method_id: str, 
    col_a: str, 
    col_b: str,
    target_groups: List[str] = None
) -> Dict[str, Any]:
    """
    Executes the specified statistical method.
    """
    # Prepare data
    clean_df = df[[col_a, col_b]].dropna()
    
    # 1. Split data (if simplified group comparison)
    # Heuristic: Find which column is the categorical grouper
    # In the API, we might be explicit, but for now let's reuse logic or assume col_b is group if categorical
    
    # Simple logic: If method implies groups, find the group col
    is_group_test = method_id in ["t_test_ind", "mann_whitney", "t_test_rel", "wilcoxon"]
    
    if is_group_test:
        # Assume col_a is numeric, col_b is grouping (simplification for MVP)
        # We need to robustly identify groups
        groups = clean_df[col_b].unique()
        if len(groups) != 2:
            raise ValueError(f"Method {method_id} requires exactly 2 groups, found {len(groups)}: {groups}")
            
        group1 = clean_df[clean_df[col_b] == groups[0]][col_a]
        group2 = clean_df[clean_df[col_b] == groups[1]][col_a]
        
        stat_val, p_val = 0, 1
        
        if method_id == "t_test_ind":
            stat_val, p_val = stats.ttest_ind(group1, group2)
        elif method_id == "mann_whitney":
            stat_val, p_val = stats.mannwhitneyu(group1, group2)
        # TODO: Paired tests require specific sorting/alignment
        
        # Prepare plot data (melted format) & Stats
        plot_data = []
        plot_stats = {}
        
        for g in groups:
            # Filter and take up to 200 points per group for performance/visuals if needed
            vals = clean_df[clean_df[col_b] == g][col_a].dropna()
            
            # Calc stats
            desc = vals.describe()
            plot_stats[str(g)] = {
                "mean": float(vals.mean()),
                "sd": float(vals.std()),
                "median": float(vals.median()),
                "q1": float(vals.quantile(0.25)),
                "q3": float(vals.quantile(0.75)),
                "min": float(vals.min()),
                "max": float(vals.max()),
                "count": int(len(vals))
            }
            
            for v in vals:
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
        
    elif method_id in ["pearson", "spearman"]:
        # Correlation
        stat_val, p_val = 0, 1
        if method_id == "pearson":
            stat_val, p_val = stats.pearsonr(clean_df[col_a], clean_df[col_b])
        elif method_id == "spearman":
            stat_val, p_val = stats.spearmanr(clean_df[col_a], clean_df[col_b])
            
        return {
            "method": method_id,
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < 0.05
        }
    
    elif method_id == "chi_square":
        # Crosstab
        crosstab = pd.crosstab(clean_df[col_a], clean_df[col_b])
        stat_val, p_val, dof, expected = stats.chi2_contingency(crosstab)
        return {
            "method": method_id,
            "stat_value": float(stat_val),
            "p_value": float(p_val),
            "significant": p_val < 0.05
        }

    raise ValueError(f"Method {method_id} not implemented yet")

def compute_batch_descriptives(df: pd.DataFrame, target_cols: List[str], group_col: str) -> List[Dict[str, Any]]:
    """
    Computes summary statistics for multiple columns split by a grouping column.
    """
    results = []
    
    # Ensure group column is treated as categorical (for splitting)
    groups = df[group_col].dropna().unique()
    
    for col in target_cols:
        if col not in df.columns:
            continue
            
        # Overall Stats (Optional, maybe later)
        
        # Per-Group Stats
        for g in groups:
            subset = df[df[group_col] == g][col].dropna()
            
            # Skip empty groups
            if len(subset) == 0:
                continue
                
            # Shapiro-Wilk
            is_normal = False
            sw_stat, sw_p = None, None
            if len(subset) >= 3:
                # Limit samples for Shapiro to avoid warnings/slowness on huge data
                sample_data = subset.sample(min(len(subset), 5000), random_state=42)
                try:
                    sw_stat, sw_p = stats.shapiro(sample_data)
                    is_normal = sw_p > 0.05
                except:
                    pass # Keep defaults if fails
            
            stats_entry = {
                "variable": str(col),
                "group": str(g),
                "count": int(len(subset)),
                "mean": float(subset.mean()),
                "median": float(subset.median()),
                "sd": float(subset.std()) if len(subset) > 1 else 0.0,
                "shapiro_w": float(sw_stat) if sw_stat else None,
                "shapiro_p": float(sw_p) if sw_p else None,
                "is_normal": is_normal
            }
            results.append(stats_entry)
            
    return results
