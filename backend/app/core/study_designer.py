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
        
        # Extract common variables
        target = variables.get("target")
        targets_str = variables.get("targets")  # Comma-separated string from batch mode
        group = variables.get("group")
        subgroup = variables.get("subgroup") # New: Extract subgroup
        time_col = variables.get("time")  # Optional for dynamic

        # Convert targets_str to a list if present
        targets_list = []
        if targets_str:
            targets_list = [t.strip() for t in targets_str.split(",") if t.strip()]
        
        if goal == "compare_groups":
            # Batch mode: multiple targets
            if targets_list:
                name = f"Batch Comparison of {len(targets_list)} variables by {group}"
                steps = self._design_batch_comparison(targets_list, group, subgroup, metadata)
            elif time_col:
                # DYNAMIC (Repeated Measures)
                name = f"Dynamic Analysis of {target} by {group}"
                steps = self._design_dynamic_comparison(target, group, time_col, metadata)
            else:
                # STATIC (Cross-sectional)
                name = f"Comparison of {target} by {group}"
                steps = self._design_static_comparison(target, group, metadata)

        elif goal == "compare_paired":
            target1 = variables.get("target1")
            target2 = variables.get("target2")
            if target1 and target2:
                name = f"Paired Comparison: {target1} vs {target2}"
                steps = self._design_paired_comparison(target1, target2, metadata)

        elif goal == "relationship":
            target = variables.get("target")
            predictor = variables.get("predictor")
            name = f"Correlation: {target} vs {predictor}"
            steps = self._design_correlation(target, predictor, metadata)

        elif goal == "correlation":
            if targets_list:
                name = f"Correlation Matrix ({len(targets_list)} variables)"
                steps = self._design_correlation_matrix(targets_list, metadata)
                
        elif goal == "prediction":
            target = variables.get("target")
            predictors_str = variables.get("predictors")
            predictors = [p.strip() for p in predictors_str.split(",") if p.strip()] if predictors_str else []
            
            if target and predictors:
                name = f"Prediction Model: {target} ~ {len(predictors)} Predictors"
                steps = self._design_regression(target, predictors, metadata)
                
        elif goal == "survival":
            time = variables.get("duration")
            event = variables.get("event")
            group = variables.get("group")
            
            if time and event:
                name = f"Survival Analysis: {time}"
                steps = self._design_survival(time, event, group, metadata)

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

    def _design_batch_comparison(self, targets: List[str], group: str, subgroup: str, meta: Dict) -> List[Dict]:
        """
        Batch comparison: multiple target variables vs one group.
        Generates steps for each variable with FDR correction.
        """
        steps = []
        
        # For each target, add desc + hypothesis steps
        for i, target in enumerate(targets):
            # Descriptive stats for this variable
            steps.append({
                "id": f"desc_{target}",
                "type": "descriptive_compare",
                "target": target,
                "group": group,
                "subgroup": subgroup
            })
            
            # Hypothesis test for this variable
            steps.append({
                "id": f"test_{target}",
                "type": "compare",
                "target": target,
                "group": group,
                "subgroup": subgroup,
                "method": {"id": "auto", "name": "Auto-Detect"},
                "batch_index": i,
                "total_tests": len(targets)
            })
        
        return steps

    def _design_correlation(self, target: str, predictor: str, meta: Dict) -> List[Dict]:
        return [{
            "id": "corr_analysis",
            "type": "correlation",
            "target": target,
            "predictor": predictor
        }]

    def _design_paired_comparison(self, t1: str, t2: str, meta: Dict) -> List[Dict]:
        return [
            {
                "id": "desc_paired",
                "type": "descriptive_paired",
                "target_a": t1,
                "target_b": t2
            },
            {
                "id": "test_paired",
                "type": "compare_paired",
                "target_a": t1,
                "target_b": t2,
                "method": "auto"
            }
        ]

    def _design_correlation_matrix(self, variables: List[str], meta: Dict) -> List[Dict]:
        return [{
            "id": "corr_matrix",
            "type": "correlation_matrix",
            "variables": variables,
            "method": "pearson" # Default, engine can switch to spearman
        }]

    def _design_regression(self, target: str, predictors: List[str], meta: Dict) -> List[Dict]:
        return [{
            "id": "regression_model",
            "type": "regression",
            "target": target,
            "predictors": predictors,
            "method": "auto" # Engine decides Linear vs Logistic
        }]

    def _design_survival(self, time: str, event: str, group: Optional[str], meta: Dict) -> List[Dict]:
        return [{
            "id": "survival_curve",
            "type": "survival",
            "time_col": time,
            "event_col": event,
            "group_col": group,
            "method": "kaplan_meier"
        }]
