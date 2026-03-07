"""
Responder Analysis: Calculate responder rates and NNT for clinical trials.

Key feature from run_diamag_full.py.
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from scipy import stats


class ResponderAnalyzer:
    """
    Analyze clinical responders based on threshold improvement.
    
    Standard thresholds:
        - UPDRS: 20% improvement
        - DASS-21: 30% reduction
        - PDQ-39: 20% improvement
    """
    
    def __init__(self, default_threshold: float = 0.20):
        self.default_threshold = default_threshold
    
    def analyze_responders(
        self,
        df: pd.DataFrame,
        baseline_col: str,
        followup_col: str,
        group_col: str,
        threshold: Optional[float] = None,
        direction: str = "lower_is_better"
    ) -> Dict[str, Any]:
        """
        Calculate responder rates by group.
        
        Args:
            df: DataFrame with data
            baseline_col: Column name for baseline values
            followup_col: Column name for follow-up values
            group_col: Column name for group assignment
            threshold: Improvement threshold (default 20%)
            direction: 'lower_is_better' or 'higher_is_better'
            
        Returns:
            - groups: responder rates by group
            - test: Fisher exact or Chi-square test result
            - nnt: Number Needed to Treat
        """
        if threshold is None:
            threshold = self.default_threshold
        
        # Filter valid data
        cols = [group_col, baseline_col, followup_col]
        valid = df[cols].dropna()
        
        if len(valid) < 10:
            return {"error": "Insufficient data for responder analysis"}
        
        # Calculate percent change
        baseline = valid[baseline_col]
        followup = valid[followup_col]
        
        if direction == "lower_is_better":
            # Improvement = negative change (decrease)
            pct_change = (followup - baseline) / baseline.abs().replace(0, 1)
            is_responder = pct_change <= -threshold
        else:
            # Improvement = positive change (increase)
            pct_change = (followup - baseline) / baseline.abs().replace(0, 1)
            is_responder = pct_change >= threshold
        
        valid = valid.copy()
        valid["pct_change"] = pct_change
        valid["is_responder"] = is_responder
        
        # Calculate by group
        groups = valid[group_col].unique()
        group_results = {}
        
        for group in groups:
            group_data = valid[valid[group_col] == group]
            n = len(group_data)
            n_responders = group_data["is_responder"].sum()
            rate = n_responders / n if n > 0 else 0
            
            group_results[str(group)] = {
                "n": int(n),
                "n_responders": int(n_responders),
                "rate": float(rate),
                "rate_pct": round(float(rate * 100), 1),
                "mean_change_pct": round(float(group_data["pct_change"].mean() * 100), 1),
            }
        
        # Statistical test
        test_result = self._compare_groups(valid, group_col, groups)
        
        # NNT calculation (for 2-group comparison)
        nnt_result = self._calculate_nnt(group_results, groups)
        
        return {
            "threshold": f"{int(threshold * 100)}% improvement",
            "direction": direction,
            "groups": group_results,
            "test": test_result,
            "nnt": nnt_result,
        }
    
    def analyze_by_visit(
        self,
        df: pd.DataFrame,
        baseline_col: str,
        visit_cols: Dict[str, str],  # {"V3": "col_v3", "V4": "col_v4", ...}
        group_col: str,
        threshold: Optional[float] = None,
        direction: str = "lower_is_better"
    ) -> Dict[str, Any]:
        """
        Analyze responders at each visit compared to baseline.
        """
        results = {}
        
        for visit, col in visit_cols.items():
            if col in df.columns:
                result = self.analyze_responders(
                    df, baseline_col, col, group_col, threshold, direction
                )
                results[visit] = result
        
        # Summary across visits
        summary = self._summarize_visits(results)
        
        return {
            "visits": results,
            "summary": summary,
        }
    
    def _compare_groups(
        self,
        df: pd.DataFrame,
        group_col: str,
        groups: np.ndarray
    ) -> Dict[str, Any]:
        """Compare responder rates between groups."""
        if len(groups) < 2:
            return {"error": "Need at least 2 groups"}
        
        try:
            # Build contingency table
            ct = pd.crosstab(df[group_col], df["is_responder"])
            
            if ct.shape == (2, 2):
                # Fisher exact for 2x2
                odds_ratio, p_value = stats.fisher_exact(ct)
                return {
                    "method": "Fisher exact test",
                    "odds_ratio": float(odds_ratio),
                    "p_value": float(p_value),
                    "significant": p_value < 0.05,
                }
            else:
                # Chi-square for larger tables
                chi2, p_value, dof, expected = stats.chi2_contingency(ct)
                return {
                    "method": "Chi-square test",
                    "chi2": float(chi2),
                    "dof": int(dof),
                    "p_value": float(p_value),
                    "significant": p_value < 0.05,
                }
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_nnt(
        self,
        group_results: Dict[str, Dict],
        groups: np.ndarray
    ) -> Dict[str, Any]:
        """
        Calculate Number Needed to Treat (NNT).
        
        NNT = 1 / ARR
        ARR = Absolute Risk Reduction = rate_treatment - rate_control
        """
        if len(groups) != 2:
            return {"note": "NNT requires exactly 2 groups"}
        
        group_list = list(group_results.keys())
        rate1 = group_results[group_list[0]]["rate"]
        rate2 = group_results[group_list[1]]["rate"]
        
        # Assume higher rate is treatment
        if rate1 >= rate2:
            treatment, control = group_list[0], group_list[1]
            treatment_rate, control_rate = rate1, rate2
        else:
            treatment, control = group_list[1], group_list[0]
            treatment_rate, control_rate = rate2, rate1
        
        arr = treatment_rate - control_rate
        
        if arr <= 0:
            return {
                "note": "No benefit (treatment ≤ control)",
                "arr": float(arr),
            }
        
        nnt = 1 / arr
        
        return {
            "treatment_group": treatment,
            "control_group": control,
            "arr": round(float(arr * 100), 1),  # Percentage
            "nnt": round(float(nnt), 1),
            "interpretation": f"Need to treat {round(nnt)} patients for 1 additional responder",
        }
    
    def _summarize_visits(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize responder analysis across visits."""
        if not results:
            return {}
        
        significant_visits = []
        best_visit = None
        best_p = 1.0
        
        for visit, data in results.items():
            if "error" in data:
                continue
            
            test = data.get("test", {})
            p = test.get("p_value", 1.0)
            
            if test.get("significant"):
                significant_visits.append(visit)
            
            if p < best_p:
                best_p = p
                best_visit = visit
        
        return {
            "n_visits": len(results),
            "significant_visits": significant_visits,
            "best_visit": best_visit,
            "best_p_value": float(best_p) if best_p < 1.0 else None,
        }
