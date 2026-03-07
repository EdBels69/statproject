"""
Subgroup Analyzer: Performs stratified analysis by subgroup levels.

Example:
    Analyze by Age Group:
    - Young: Control vs Treatment
    - Old: Control vs Treatment
"""
from typing import Dict, Any, List
import pandas as pd
from scipy import stats
import numpy as np


class SubgroupAnalyzer:
    """
    Performs stratified comparisons within subgroup levels.
    """
    
    def analyze_by_subgroup(
        self,
        df: pd.DataFrame,
        group_col: str,
        subgroup_col: str,
        numeric_vars: List[str],
        categorical_vars: List[str],
        min_n: int = 10
    ) -> Dict[str, Any]:
        """
        Run analysis separately for each subgroup level.
        
        Args:
            df: DataFrame
            group_col: Main grouping variable (e.g., "Treatment")
            subgroup_col: Subgroup variable (e.g., "Age_Group")
            numeric_vars: Numeric variables to analyze
            categorical_vars: Categorical variables to analyze
            min_n: Minimum sample size per subgroup
            
        Returns:
            {
                "Young": {
                    "Variable1": {"method": "T-Test", "p_value": 0.023},
                    ...
                },
                "Old": {...},
                "summary": {...}
            }
        """
        results = {}
        subgroup_summary = []
        
        for subgroup_value in df[subgroup_col].dropna().unique():
            # Filter to this subgroup
            df_sub = df[df[subgroup_col] == subgroup_value]
            
            if len(df_sub) < min_n:
                continue
            
            subgroup_results = {
                "numeric": {},
                "categorical": {},
                "n_total": len(df_sub)
            }
            
            # Numeric variables
            for var in numeric_vars:
                if var not in df_sub.columns or var == group_col:
                    continue
                
                groups = df_sub[group_col].dropna().unique()
                
                if len(groups) != 2:
                    continue
                
                g1, g2 = groups
                data1 = pd.to_numeric(df_sub[df_sub[group_col] == g1][var], errors='coerce').dropna()
                data2 = pd.to_numeric(df_sub[df_sub[group_col] == g2][var], errors='coerce').dropna()
                
                if len(data1) < 3 or len(data2) < 3:
                    continue
                
                # Normality check
                try:
                    _, p_norm1 = stats.shapiro(data1) if len(data1) < 5000 else (0, 1.0)
                    _, p_norm2 = stats.shapiro(data2) if len(data2) < 5000 else (0, 1.0)
                    is_normal = p_norm1 > 0.05 and p_norm2 > 0.05
                except:
                    is_normal = False
                
                # Select test
                if is_normal:
                    t_stat, p_val = stats.ttest_ind(data1, data2)
                    method = "T-Test"
                else:
                    u_stat, p_val = stats.mannwhitneyu(data1, data2, alternative='two-sided')
                    method = "Mann-Whitney U"
                
                subgroup_results["numeric"][var] = {
                    "method": method,
                    "p_value": float(p_val),
                    "significant": p_val < 0.05,
                    "n1": len(data1),
                    "n2": len(data2),
                    "mean1": float(data1.mean()),
                    "mean2": float(data2.mean()),
                    "is_normal": is_normal
                }
            
            # Categorical variables
            for var in categorical_vars:
                if var not in df_sub.columns or var == group_col or var == subgroup_col:
                    continue
                
                try:
                    ct = pd.crosstab(df_sub[group_col], df_sub[var])
                    
                    if ct.shape == (2, 2) and ct.min().min() < 5:
                        odds_ratio, p_val = stats.fisher_exact(ct)
                        method = "Fisher Exact"
                    else:
                        chi2, p_val, dof, expected = stats.chi2_contingency(ct)
                        method = "Chi-Square"
                    
                    subgroup_results["categorical"][var] = {
                        "method": method,
                        "p_value": float(p_val),
                        "significant": p_val < 0.05,
                        "contingency_table": ct.to_dict()
                    }
                except:
                    pass
            
            results[str(subgroup_value)] = subgroup_results
            subgroup_summary.append({
                "subgroup": str(subgroup_value),
                "n": len(df_sub),
                "numeric_tests": len(subgroup_results["numeric"]),
                "categorical_tests": len(subgroup_results["categorical"])
            })
        
        return {
            "subgroups": results,
            "summary": {
                "subgroup_column": subgroup_col,
                "n_subgroups": len(results),
                "subgroup_details": subgroup_summary
            }
        }
