import pandas as pd
from typing import List, Dict, Any, Optional

class StudyDesignEngine:
    """
    Expert System that translates high-level 'Study Goals' into executable 'Analysis Protocols'.
    Acts as the 'Methodologist' role.
    """

    def suggest_protocol(self, goal: str, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point.
        goal: 'compare_groups', 'relationship', 'survival', 'prediction'
        variables: { 'target': 'Hb', 'group': 'Treatment', 'time': 'Month' }
        metadata: { 'Hb': { 'is_normal': False, 'type': 'numeric' } }
        
        Returns: A fully-formed Protocol JSON ready for the Engine.
        """
        steps = []
        name = "Generated Study"
        
        if goal == "compare_groups":
            target = variables.get("target")
            group = variables.get("group")
            time_col = variables.get("time") # Optional for dynamic
            
            if time_col:
                # DYNAMIC (Repeated Measures)
                name = f"Dynamic Analysis of {target} by {group}"
                steps = self._design_dynamic_comparison(target, group, time_col, metadata)
            else:
                # STATIC (Cross-sectional)
                name = f"Comparison of {target} by {group}"
                steps = self._design_static_comparison(target, group, metadata)

        elif goal == "relationship":
            target = variables.get("target")
            predictor = variables.get("predictor")
            name = f"Correlation: {target} vs {predictor}"
            steps = self._design_correlation(target, predictor, metadata)

        return {
            "name": name,
            "goal": goal,
            "steps": steps,
            "required_visualization": "dashboard_v1"
        }

    def _design_static_comparison(self, target: str, group: str, meta: Dict) -> List[Dict]:
        """
        Logic for T-Test / ANOVA / Non-parametric equivalents.
        """
        steps = []
        
        # 1. Descriptive Stats (Table 1 equivalent)
        steps.append({
            "id": "desc_stats",
            "type": "descriptive_compare",
            "target": target,
            "group": group
        })
        
        # 2. Hypothesis Testing
        # Check normalization from metadata to suggest method
        target_meta = meta.get(target, {})
        is_normal = target_meta.get("normality", {}).get("is_normal", True) # Default to True if unknown
        
        # Note: We can force a method, or let engine.select_test decide dynamically.
        # "Methodological Brain" prefers to be explicit here if possible, but engine.py has good runtime logic.
        # Let's rely on engine.py's robust 'compare' dispatch for now, but generic 'compare' is enough.
        
        method_category = "parametric" if is_normal else "non_parametric"
        
        steps.append({
            "id": "hypothesis_test",
            "type": "compare",
            "target": target,
            "group": group,
            "assumptions_checked": ["normality", "homogeneity"],
            "method": {
                "id": "auto",
                "name": "Auto-Detect Test",
                "category": method_category,
                "params": {"target": target, "group": group}
            }
        })
        
        return steps

    def _design_dynamic_comparison(self, target: str, group: str, time_col: str, meta: Dict) -> List[Dict]:
        """
        Logic for Longitudinal Analysis (Repeated Measures).
        """
        steps = []
        
        # 1. Overall Trend (All Groups) - e.g. RM ANOVA or Friedmann
        steps.append({
            "id": "time_trend_overall",
            "type": "compare_dynamic", # New capability needed in Engine
            "target": target,
            "time": time_col,
            "group": group
        })
        
        # 2. Post-hoc: Compare groups at EACH timepoint
        # We generate a sub-step for the Engine to expand, or hardcode generic instruction
        steps.append({
             "id": "timepoint_comparison",
             "type": "batch_compare_by_factor", # "Loop over Time"
             "target": target,
             "group": group,
             "split_by": time_col
        })
        
        return steps

    def _design_correlation(self, target: str, predictor: str, meta: Dict) -> List[Dict]:
        return [{
            "id": "corr_analysis",
            "type": "correlation",
            "target": target,
            "predictor": predictor
        }]
