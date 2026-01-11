import pandas as pd
from typing import List, Dict, Any
from app.stats.engine import run_analysis, select_test
from app.core.pipeline import PipelineManager
from app.stats.registry import get_method
from app.modules.text_generator import TextGenerator
from app.core.logging import logger

class ProtocolEngine:
    """
    Executes a Study Protocol (batch of analysis steps) on a dataset.
    Isolates the run in a unique container via PipelineManager.
    """
    
    def __init__(self, pipeline: PipelineManager):
        self.pipeline = pipeline
        self.ai = TextGenerator()

    def _sanitize(self, obj):
        """Recursively replace NaN/Inf with None for JSON safety."""
        import math
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        return obj

    def execute_protocol(self, dataset_id: str, df: pd.DataFrame, protocol: Dict[str, Any]) -> str:
        """
        Runs the full protocol.
        """
        # 1. Create Analysis Container
        run_dir = self.pipeline.create_analysis_run(dataset_id, protocol)
        
        results_map = {}
        log = []
        
        # 2. Iterate Steps
        for step in protocol.get("steps", []):
            step_id = step.get("id")
            step_type = step.get("type", "compare")
            
            try:
                log.append(f"Starting step {step_id}...")
                
                # Dynamic Dispatch based on step type
                if step_type == "compare" or step_type == "correlation":
                    res = self._run_compare(df, step)
                elif step_type == "survival":
                    res = self._run_survival(df, step)
                elif step_type == "regression":
                    res = self._run_regression(df, step)
                elif step_type == "descriptive_compare":
                    res = self._run_desc_compare(df, step)
                elif step_type == "batch_compare_by_factor":
                    res = self._run_batch_compare_by_factor(df, step)
                elif step_type == "hypothesis_test":
                    res = self._run_hypothesis_test(df, step)
                else:
                    res = {"error": f"Unknown step type: {step_type}"}
                
                results_map[step_id] = res
                log.append(f"Step {step_id} completed.")
                
            except Exception as e:
                import traceback
                logger.error(f"Step {step_id} failed: {str(e)}", exc_info=True)
                error_msg = f"Step {step_id} failed: {str(e)}"
                log.append(error_msg)
                results_map[step_id] = {"error": error_msg}

        # 3. Save Results
        sanitized_results = self._sanitize(results_map)
        
        full_output = {
            "protocol_name": protocol.get("name", "Unnamed Protocol"),
            "dataset_id": dataset_id,
            "results": sanitized_results,
            "log": log
        }
        
        self.pipeline.save_run_results(run_dir, full_output)
        
        return run_dir.split("/")[-1]

    def _run_desc_compare(self, df: pd.DataFrame, step: Dict) -> Dict:
        from app.stats.engine import compute_descriptive_compare
        return {
            "type": "table_1",
            "data": compute_descriptive_compare(df, step["target"], step["group"])
        }

    def _run_batch_compare_by_factor(self, df: pd.DataFrame, step: Dict) -> Dict:
        """
        Iterates over a splitting factor (e.g. Timepoint) and runs comparison for each slice.
        """
        split_col = step.get("split_by")
        target = step.get("target")
        group = step.get("group")
        
        results = {}
        if split_col not in df.columns:
            return {"error": f"Split column {split_col} not found"}
            
        slices = sorted(df[split_col].dropna().unique())
        
        for s in slices:
            # Filter Data
            sub_df = df[df[split_col] == s]
            # Create a mini-step for this slice
            sub_step = {"target": target, "group": group, "method": step.get("method")}
            
            # Re-use existing compare logic
            results[str(s)] = self._run_compare(sub_df, sub_step)
            
        return {
            "type": "longitudinal_comparison",
            "split_by": split_col,
            "slices": results
        }

    def _run_hypothesis_test(self, df: pd.DataFrame, step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs a statistical test (T-test, ANOVA, etc.)
        """
        from app.stats.engine import run_analysis, select_test, check_normality
        import pandas as pd
        
        target = step.get("target")
        group = step.get("group")
        method = step.get("method") # Optional override
        
        # 1. Auto-detect method if missing
        if not method:
            # Quick check types
            types = {
                target: "numeric" if pd.api.types.is_numeric_dtype(df[target]) else "categorical",
                group: "categorical" # Group is usually categorical
            }
            method = select_test(df, target, group, types)
        
        # Helper to extract ID
        method_id = method.get("id") if isinstance(method, dict) else method
            
        if not method_id:
            return {"error": f"Could not determine test for {target} vs {group}"}
            
        # 2. Run
        try:
            # Pass full step config as kwargs (allows 'test_value' for one-sample, 'detailed' flags, etc.)
            raw_res = run_analysis(df, method_id, target, group, **step)
            
            # Start with raw results (preserves AUC, custom stats)
            result_dict = raw_res.copy()
            
            # Standardize / Overlay
            result_dict["type"] = "hypothesis_test"
            result_dict["method"] = get_method(method_id)
            
            # Map common fields if names differ (run_analysis standardization usually matches)
            if "stat_value" in raw_res: result_dict["stats"] = raw_res["stat_value"] # Legacy mapping if needed
            
            # AI Interpretation
            # Check for AI Style per step (default Pro)
            ai_style = step.get("ai_style", "pro")
            result_dict["conclusion"] = self.ai.interpret_result(result_dict, {"target": target, "group": group}, style=ai_style)
            
            return result_dict
            
        except Exception as e:
            return {"error": str(e)}

    def _run_compare(self, df: pd.DataFrame, step: Dict) -> Dict:
        target = step.get("target")
        group = step.get("group")
        
        # Auto-detect method if not provided
        if not step.get("method"):
            types = {
                target: "numeric" if pd.api.types.is_numeric_dtype(df[target]) else "categorical",
                group: "categorical" # Assumed for compare
            }
            method_id = select_test(df, target, group, types)
        else:
            method_val = step.get("method")
            if isinstance(method_val, dict):
                method_id = method_val.get("id")
            else:
                method_id = method_val
            
        if not method_id:
            return {"error": "Could not select method"}
            
        raw_res = run_analysis(df, method_id, target, group, **step)
        
        # Format for storage
        result_dict = {
            "method": get_method(method_id),
            "p_value": raw_res.get("p_value"),
            "significant": raw_res.get("significant"),
            "stats": raw_res.get("stat_value"),
            "effect_size": raw_res.get("effect_size"),
            "groups": raw_res.get("groups"),
            "plot_stats": raw_res.get("plot_stats"), 
            "plot_data": raw_res.get("plot_data")
        }
        
        # AI Interpretation
        result_dict["conclusion"] = self.ai.interpret_result(result_dict, {"target": target, "group": group})
        
        return result_dict

    def _run_survival(self, df: pd.DataFrame, step: Dict) -> Dict:
        time_col = step.get("time")
        event_col = step.get("event")
        group_col = step.get("group")
        
        raw_res = run_analysis(df, "survival_km", time_col, event_col, group_col=group_col)
        
        return {
            "method": get_method("survival_km"),
            "p_value": raw_res.get("p_value"),
            "significant": raw_res.get("significant"),
            "km_stats": raw_res.get("stat_value")
        }

    def _run_regression(self, df: pd.DataFrame, step: Dict) -> Dict:
        target = step.get("target")
        predictors = step.get("predictors", [])
        kind = step.get("kind", "linear") # linear or logistic
        
        method_id = "logistic_regression" if kind == "logistic" else "linear_regression"
        
        raw_res = run_analysis(df, method_id, target, predictors[0], predictors=predictors)
        
        return {
            "method": get_method(method_id),
            "r_squared": raw_res.get("r_squared"),
            "coefficients": raw_res.get("coefficients"),
            "p_value": raw_res.get("p_value")
        }
