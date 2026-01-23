import pandas as pd
import numpy as np
import os
from typing import List, Dict, Any, Optional
from app.stats.engine import run_analysis, select_test
from app.core.pipeline import PipelineManager
from app.stats.registry import get_method
from app.modules.text_generator import TextGenerator
from app.core.logging import logger
from app.stats.mixed_effects import MixedEffectsEngine
from app.stats.clustered_correlation import ClusteredCorrelationEngine

# Standard statistical methods for protocol fallback
STANDARD_METHODS = [
    "t_test_independent",
    "t_test_paired",
    "anova_one_way",
    "anova_repeated",
    "correlation_pearson",
    "correlation_spearman",
    "chi_square",
    "regression_linear",
    "regression_logistic"
]

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
        try:
            if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
                return self._sanitize(obj.model_dump())
            if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
                return self._sanitize(obj.dict())
        except Exception:
            pass

        try:
            import numpy as np
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                obj = float(obj)
        except Exception:
            pass

        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        return obj

    def execute_protocol(self, dataset_id: str, df: pd.DataFrame, protocol: Dict[str, Any], alpha: float = 0.05) -> str:
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
                    res = self._run_compare(df, step, alpha)
                elif step_type == "survival":
                    res = self._run_survival(df, step, alpha)
                elif step_type == "regression":
                    res = self._run_regression(df, step, alpha)
                elif step_type == "descriptive_compare":
                    res = self._run_desc_compare(df, step)
                elif step_type == "batch_compare_by_factor":
                    res = self._run_batch_compare_by_factor(df, step, alpha)
                elif step_type == "hypothesis_test":
                    res = self._run_hypothesis_test(df, step, alpha)
                elif step_type == "mixed_effects":
                    res = self._run_mixed_effects(df, step, alpha)
                elif step_type == "clustered_correlation":
                    res = self._run_clustered_correlation(df, step, alpha)
                elif step_type == "responders":
                    res = self._run_responders(df, step, alpha)
                else:
                    res = {"type": str(step_type), "error": f"Unknown step type: {step_type}"}
                
                results_map[step_id] = res
                log.append(f"Step {step_id} completed.")
                
                # Force garbage collection after each step for M1 8GB
                import gc
                gc.collect()
                
            except Exception as e:
                import traceback
                logger.error(f"Step {step_id} failed: {str(e)}", exc_info=True)
                error_msg = f"Step {step_id} failed: {str(e)}"
                log.append(error_msg)
                results_map[step_id] = {"type": str(step_type), "error": error_msg}

        # 3. Save Results
        sanitized_results = self._sanitize(results_map)
        
        full_output = {
            "protocol_name": protocol.get("name", "Unnamed Protocol"),
            "dataset_id": dataset_id,
            "alpha": alpha,
            "results": sanitized_results,
            "log": log
        }
        
        self.pipeline.save_run_results(run_dir, full_output)

        return os.path.basename(run_dir)

    def _run_responders(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
        outcome_label = step.get("outcome_label") or step.get("outcome") or step.get("target")
        group_col = step.get("group_column") or step.get("group")
        subject_col = step.get("subject_column") or step.get("subject")

        outcome_columns = step.get("outcome_columns")
        time_labels = step.get("time_labels")
        baseline_label = step.get("baseline_label") or step.get("baseline_time")
        baseline_index = step.get("baseline_index")

        threshold_raw = step.get("threshold")
        if threshold_raw is None:
            threshold_raw = step.get("response_threshold")
        try:
            threshold = float(threshold_raw) if threshold_raw is not None else 0.0
        except Exception:
            threshold = 0.0

        direction = str(step.get("direction") or step.get("improvement_direction") or "decrease").strip().lower()
        if direction not in {"decrease", "increase"}:
            direction = "decrease"

        if not group_col or not isinstance(group_col, str) or group_col not in df.columns:
            return {"type": "responders", "error": "Missing group column"}

        if not isinstance(outcome_columns, list) or not outcome_columns:
            return {"type": "responders", "error": "Missing outcome_columns"}
        outcome_columns = [c for c in outcome_columns if isinstance(c, str) and c in df.columns]
        if len(outcome_columns) < 2:
            return {"type": "responders", "error": "Insufficient outcome columns"}

        if not isinstance(time_labels, list) or len(time_labels) != len(outcome_columns):
            time_labels = [str(i) for i in range(len(outcome_columns))]

        baseline_idx = 0
        if isinstance(baseline_index, int) and 0 <= baseline_index < len(outcome_columns):
            baseline_idx = int(baseline_index)
        elif isinstance(baseline_label, str) and baseline_label in time_labels:
            baseline_idx = int(time_labels.index(baseline_label))

        baseline_col = outcome_columns[baseline_idx]
        baseline_time = str(time_labels[baseline_idx])

        group_merge = step.get("merge_groups") or step.get("group_merge") or step.get("group_map")
        mapping: Dict[str, str] = {}
        buckets: List[Dict[str, Any]] = []
        if isinstance(group_merge, dict):
            for k, v in group_merge.items():
                if k is None or v is None:
                    continue
                mapping[str(k)] = str(v)
        elif isinstance(group_merge, list):
            for item in group_merge:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                values = item.get("values")
                if isinstance(name, str) and isinstance(values, list) and values:
                    buckets.append({"name": name, "values": {str(v) for v in values if v is not None}})

        def _map_group(value: Any) -> str:
            raw = "-" if value is None else str(value)
            if raw in mapping:
                return mapping[raw]
            if buckets:
                for b in buckets:
                    if raw in b.get("values", set()):
                        return str(b.get("name"))
            return raw

        visits: List[Dict[str, str]] = []
        for idx, col in enumerate(outcome_columns):
            if idx == baseline_idx:
                continue
            visits.append({"time": str(time_labels[idx]), "column": str(col)})
        if not visits:
            return {"type": "responders", "error": "No follow-up visits"}

        by_visit: Dict[str, Any] = {}
        for v in visits:
            visit_time = v.get("time")
            visit_col = v.get("column")
            cols = [group_col, baseline_col, visit_col]
            if isinstance(subject_col, str) and subject_col in df.columns:
                cols = [subject_col, *cols]

            tmp = df[cols].copy()
            tmp[baseline_col] = pd.to_numeric(tmp[baseline_col], errors="coerce")
            tmp[visit_col] = pd.to_numeric(tmp[visit_col], errors="coerce")
            tmp = tmp.dropna(subset=[group_col, baseline_col, visit_col])
            if tmp.empty:
                continue

            tmp["__group__"] = tmp[group_col].map(_map_group)
            if direction == "increase":
                tmp["__delta__"] = tmp[visit_col] - tmp[baseline_col]
            else:
                tmp["__delta__"] = tmp[baseline_col] - tmp[visit_col]
            tmp["__responder__"] = (tmp["__delta__"] >= threshold).astype(int)

            group_stats: Dict[str, Any] = {}
            for g, sub in tmp.groupby("__group__", dropna=False):
                total = int(len(sub))
                responders = int(sub["__responder__"].sum())
                rate = (responders / total) if total else 0.0
                group_stats[str(g)] = {"responders": responders, "total": total, "rate": rate}

            test_res = None
            uniq_groups = [k for k, v in group_stats.items() if isinstance(v, dict) and v.get("total", 0) > 0]
            if len(uniq_groups) >= 2:
                try:
                    test_res = run_analysis(tmp[["__group__", "__responder__"]].copy(), "chi_square", "__group__", "__responder__", alpha=alpha)
                except Exception:
                    test_res = None

            by_visit[str(visit_time)] = {
                "visit": str(visit_time),
                "baseline": baseline_time,
                "threshold": threshold,
                "direction": direction,
                "groups": group_stats,
                "test": test_res,
            }

        if not by_visit:
            return {"type": "responders", "error": "No responder results computed"}

        return {
            "type": "responders",
            "outcome": outcome_label,
            "group_column": group_col,
            "subject_column": subject_col,
            "baseline": {"time": baseline_time, "column": baseline_col},
            "visits": visits,
            "threshold": threshold,
            "direction": direction,
            "group_merge": group_merge if group_merge is not None else None,
            "by_visit": by_visit,
        }

    def execute_v2_protocol(self, dataset_id: str, df: pd.DataFrame, protocol: List[Dict], alpha: float = 0.05) -> Dict[str, Any]:
        """
        Execute v2 protocol with support for mixed_effects and clustered_correlation.
        
        Args:
            dataset_id: Dataset identifier
            df: DataFrame to analyze
            protocol: List of analysis steps with method and config
            alpha: Significance level
        
        Returns:
            Dict with results, errors, and statistics
        """
        results = []
        errors = []
        
        for step in protocol:
            method_id = step.get("method")
            config = step.get("config", {})
            step_id = step.get("id", f"step_{len(results) + 1}")
            
            try:
                if method_id == "mixed_effects":
                    outcome = config.get("outcome")
                    time_col = config.get("time")
                    group_col = config.get("group")
                    subject_col = config.get("subject")
                    covariates = config.get("covariates", [])
                    random_slope = config.get("random_slope", False)
                    
                    engine = MixedEffectsEngine(max_memory_mb=800)
                    result = engine.fit(df, outcome, time_col, group_col, subject_col, covariates, random_slope, alpha)
                    
                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": result
                    })
                
                elif method_id == "clustered_correlation":
                    variables = config.get("variables", [])
                    method = config.get("method", "pearson")
                    linkage_method = config.get("linkage_method", "ward")
                    n_clusters = config.get("n_clusters")
                    distance_threshold = config.get("distance_threshold")
                    show_p_values = config.get("show_p_values", True)
                    
                    engine = ClusteredCorrelationEngine()
                    result = engine.analyze(
                        df, variables, method, linkage_method, n_clusters,
                        distance_threshold, show_p_values, alpha
                    )
                    
                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": result
                    })
                
                elif method_id in STANDARD_METHODS:
                    outcome = config.get("outcome")
                    group = config.get("group")
                    
                    if outcome and group:
                        raw_res = run_analysis(df, method_id, outcome, group, alpha)
                        
                        results.append({
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": raw_res
                        })
                    else:
                        raise ValueError(f"Missing required config for {method_id}")
                
                else:
                    raise ValueError(f"Method {method_id} not implemented")
                
                # Force garbage collection after each step
                import gc
                gc.collect()
                
            except Exception as e:
                logger.error(f"Step {step_id} failed: {e}", exc_info=True)
                errors.append({
                    "step_id": step_id,
                    "method": method_id,
                    "error": str(e)
                })
        
        return {
            "status": "completed" if not errors else "partial",
            "results": results,
            "errors": errors,
            "total_steps": len(protocol),
            "completed_steps": len(results),
            "failed_steps": len(errors)
        }

    def _run_desc_compare(self, df: pd.DataFrame, step: Dict) -> Dict:
        from app.stats.engine import compute_descriptive_compare
        return {
            "type": "table_1",
            "data": compute_descriptive_compare(df, step["target"], step["group"])
        }

    def _run_batch_compare_by_factor(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
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
            sub_step = {
                "target": target,
                "group": group,
                "method": step.get("method"),
                "auto_fallback": step.get("auto_fallback"),
                "is_paired": step.get("is_paired"),
            }
            
            # Re-use existing compare logic
            results[str(s)] = self._run_compare(sub_df, sub_step, alpha)
            
        return {
            "type": "longitudinal_comparison",
            "split_by": split_col,
            "slices": results
        }

    def _run_hypothesis_test(self, df: pd.DataFrame, step: Dict[str, Any], alpha: float = 0.05) -> Dict[str, Any]:
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
            step["alpha"] = alpha
            raw_res = run_analysis(df, method_id, target, group, **step)
            
            # Start with raw results (preserves AUC, custom stats)
            result_dict = raw_res.copy()
            
            # Standardize / Overlay
            result_dict["type"] = "hypothesis_test"
            result_dict["method"] = get_method(method_id)
            result_dict["target"] = target
            result_dict["group"] = group
            result_dict["alpha"] = alpha
            
            # Map common fields if names differ (run_analysis standardization usually matches)
            if "stat_value" in raw_res: result_dict["stats"] = raw_res["stat_value"] # Legacy mapping if needed
            
            # AI Interpretation
            # Check for AI Style per step (default Pro)
            ai_style = step.get("ai_style", "pro")
            result_dict["conclusion"] = self.ai.interpret_result(result_dict, {"target": target, "group": group}, style=ai_style)
            result_dict["ai_interpretation"] = self.ai.interpret_result(
                result_dict,
                {"target": target, "group": group},
                style="ru",
            )
            
            return result_dict
            
        except Exception as e:
            return {"error": str(e)}

    def _run_compare(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
        target = step.get("target")
        group = step.get("group") or step.get("predictor")
        target_label = step.get("target_label") or step.get("outcome_label") or target
        group_label = step.get("group_label") or step.get("group_column_label") or group
        unit = step.get("unit") or step.get("units")
        
        # Auto-detect method if not provided
        if not step.get("method"):
            def _infer_kind_for_select(col: str) -> str:
                if not col or col not in df.columns:
                    return "categorical"
                s = df[col]
                if not pd.api.types.is_numeric_dtype(s):
                    return "categorical"
                try:
                    non_na = s.dropna()
                    n = int(len(non_na))
                    u = int(non_na.nunique(dropna=True)) if n else 0
                except Exception:
                    return "numeric"

                name_l = str(col).strip().lower()
                looks_like_group = any(k in name_l for k in ["group", "группа", "treatment", "arm", "cohort", "рандом"])
                small_cardinality = u <= min(12, max(2, int(n * 0.2)))
                if looks_like_group or small_cardinality:
                    return "categorical"
                return "numeric"

            types = {
                target: "numeric" if pd.api.types.is_numeric_dtype(df[target]) else "categorical",
                group: _infer_kind_for_select(group),
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
            
        step["alpha"] = alpha
        raw_res = run_analysis(df, method_id, target, group, **step)
        
        # Format for storage
        result_dict = {
            "type": "compare",
            "method": get_method(method_id),
            "target": target,
            "target_label": target_label,
            "unit": unit,
            "group": group,
            "group_label": group_label,
            "alpha": alpha,
            "p_value": raw_res.get("p_value"),
            "significant": raw_res.get("significant"),
            "stats": raw_res.get("stat_value"),
            "effect_size": raw_res.get("effect_size"),
            "effect_size_name": raw_res.get("effect_size_name"),
            "effect_size_ci_lower": raw_res.get("effect_size_ci_lower"),
            "effect_size_ci_upper": raw_res.get("effect_size_ci_upper"),
            "effect_size_interpretation": raw_res.get("effect_size_interpretation"),
            "power": raw_res.get("power"),
            "bf10": raw_res.get("bf10"),
            "groups": raw_res.get("groups"),
            "plot_stats": raw_res.get("plot_stats"),
            "plot_data": raw_res.get("plot_data"),
            "assumptions": raw_res.get("assumptions"),
            "warnings": raw_res.get("warnings"),
            "post_hoc": raw_res.get("post_hoc"),
            "comparisons": raw_res.get("comparisons"),
        }
        
        # AI Interpretation
        result_dict["conclusion"] = self.ai.interpret_result(result_dict, {"target": target, "group": group})
        result_dict["ai_interpretation"] = self.ai.interpret_result(
            result_dict,
            {"target": target, "group": group},
            style="ru",
        )
        
        return result_dict

    def _run_survival(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
        time_col = step.get("time")
        event_col = step.get("event")
        group_col = step.get("group")
        
        raw_res = run_analysis(df, "survival_km", time_col, event_col, group_col=group_col, alpha=alpha)
        
        return {
            "method": get_method("survival_km"),
            "p_value": raw_res.get("p_value"),
            "significant": raw_res.get("significant"),
            "km_stats": raw_res.get("stat_value")
        }

    def _run_regression(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
        target = step.get("target")
        predictors = step.get("predictors", [])
        kind = step.get("kind", "linear") # linear or logistic
        
        method_id = "logistic_regression" if kind == "logistic" else "linear_regression"
        
        raw_res = run_analysis(df, method_id, target, predictors[0], predictors=predictors, alpha=alpha)
        
        return {
            "type": "regression",
            "method": get_method(method_id),
            "r_squared": raw_res.get("r_squared"),
            "coefficients": raw_res.get("coefficients"),
            "p_value": raw_res.get("p_value"),
            "significant": raw_res.get("significant"),
            "roc": raw_res.get("roc"),
        }

    def _run_mixed_effects(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
        """
        Run Linear Mixed Model (LMM) analysis.
        """
        outcome = step.get("outcome")
        time_col = step.get("time_column")
        group_col = step.get("group_column")
        subject_col = step.get("subject_column")
        covariates = step.get("covariates", [])
        random_slope = step.get("random_slopes", False)
        outcome_columns = step.get("outcome_columns")
        time_labels = step.get("time_labels")

        group_merge = step.get("merge_groups") or step.get("group_merge") or step.get("group_map")
        mapping: Dict[str, str] = {}
        buckets: List[Dict[str, Any]] = []
        if isinstance(group_merge, dict):
            for k, v in group_merge.items():
                if k is None or v is None:
                    continue
                mapping[str(k)] = str(v)
        elif isinstance(group_merge, list):
            for item in group_merge:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                values = item.get("values")
                if isinstance(name, str) and isinstance(values, list) and values:
                    buckets.append({"name": name, "values": {str(v) for v in values if v is not None}})

        def _map_group(value: Any) -> str:
            raw = "-" if value is None else str(value)
            if raw in mapping:
                return mapping[raw]
            if buckets:
                for b in buckets:
                    if raw in b.get("values", set()):
                        return str(b.get("name"))
            return raw
        
        try:
            analysis_df = df
            used_outcome = outcome
            used_time_col = time_col
            used_group_col = group_col
            if (not isinstance(time_col, str) or time_col not in df.columns) and isinstance(outcome_columns, list) and outcome_columns:
                id_vars = [c for c in [subject_col, group_col, *covariates] if isinstance(c, str) and c in df.columns]
                value_vars = [c for c in outcome_columns if isinstance(c, str) and c in df.columns]
                if not id_vars or not value_vars:
                    return {
                        "type": "mixed_effects",
                        "method": get_method("mixed_effects"),
                        "error": "Insufficient columns for wide mixed effects",
                    }

                used_time_col = time_col if isinstance(time_col, str) and time_col else "Time"
                wide_long = df[id_vars + value_vars].melt(
                    id_vars=id_vars,
                    value_vars=value_vars,
                    var_name=used_time_col,
                    value_name="Value",
                )
                wide_long["Value"] = pd.to_numeric(wide_long["Value"], errors="coerce")
                wide_long = wide_long.dropna(subset=["Value"])

                if isinstance(time_labels, list) and len(time_labels) == len(value_vars):
                    time_map = {v: str(t) for v, t in zip(value_vars, time_labels)}
                    wide_long[used_time_col] = wide_long[used_time_col].map(lambda x: time_map.get(x, str(x)))
                else:
                    import re

                    def _extract_visit(v: Any) -> str:
                        s = str(v)
                        m = re.search(r"\bV\s*(\d+)\b", s)
                        if m:
                            return str(int(m.group(1)))
                        m = re.search(r"(\d+)", s)
                        if m:
                            return str(int(m.group(1)))
                        return s

                    wide_long[used_time_col] = wide_long[used_time_col].map(_extract_visit)

                analysis_df = wide_long
                used_outcome = "Value"

            if isinstance(analysis_df, pd.DataFrame) and isinstance(used_group_col, str) and used_group_col in analysis_df.columns and (mapping or buckets):
                analysis_df = analysis_df.copy()
                analysis_df["__group__"] = analysis_df[used_group_col].map(_map_group)
                used_group_col = "__group__"

            if not isinstance(used_group_col, str) or used_group_col not in analysis_df.columns:
                return {
                    "type": "mixed_effects",
                    "method": get_method("mixed_effects"),
                    "error": "Missing group column",
                }

            if not isinstance(subject_col, str) or subject_col not in analysis_df.columns:
                return {
                    "type": "mixed_effects",
                    "method": get_method("mixed_effects"),
                    "error": "Missing subject column",
                }

            engine = MixedEffectsEngine(max_memory_mb=800)
            result = engine.fit(analysis_df, used_outcome, used_time_col, used_group_col, subject_col, covariates, random_slope, alpha)

            if isinstance(result, dict) and result.get("error"):
                return {
                    "type": "mixed_effects",
                    "method": get_method("mixed_effects"),
                    "error": str(result.get("error")),
                    "message": str(result.get("message")) if result.get("message") is not None else None,
                    "suggestion": str(result.get("suggestion")) if result.get("suggestion") is not None else None,
                }

            interaction_p_value = result.get("interaction_p_value")
            try:
                p = float(interaction_p_value)
                significant = bool(np.isfinite(p) and p < alpha)
            except Exception:
                significant = None

            interaction = result.get("interaction")
            conclusion = None
            if isinstance(interaction, dict):
                conclusion = interaction.get("interpretation")

            return {
                "type": "mixed_effects",
                "method": get_method("mixed_effects"),
                "p_value": interaction_p_value,
                "interaction_p_value": interaction_p_value,
                "significant": significant,
                "outcome": step.get("outcome_label") or result.get("outcome") or outcome,
                "group_column": group_col,
                "group_merge": group_merge if group_merge is not None else None,
                "formula": step.get("formula") or result.get("formula"),
                "n_observations": result.get("n_observations"),
                "n_subjects": result.get("n_subjects"),
                "model_statistics": result.get("model_statistics"),
                "estimated_means": result.get("estimated_means"),
                "coefficients": result.get("coefficients"),
                "conclusion": conclusion,
            }
        except Exception as e:
            logger.error(f"Mixed effects analysis failed: {e}", exc_info=True)
            return {"type": "mixed_effects", "method": get_method("mixed_effects"), "error": str(e)}

    def _run_clustered_correlation(self, df: pd.DataFrame, step: Dict, alpha: float = 0.05) -> Dict:
        """
        Run clustered correlation analysis with dendrogram.
        """
        variables = step.get("variables", [])
        method = step.get("method", "pearson")
        linkage_method = step.get("linkage_method", "ward")
        n_clusters = step.get("n_clusters")
        distance_threshold = step.get("distance_threshold")
        show_p_values = step.get("show_p_values", True)
        
        try:
            engine = ClusteredCorrelationEngine()
            result = engine.analyze(
                df, variables, method, linkage_method, n_clusters,
                distance_threshold, show_p_values, alpha
            )
            
            return {
                "type": "clustered_correlation",
                "method": get_method("clustered_correlation"),
                "correlation_matrix": result.get("correlation_matrix"),
                "p_values": result.get("p_values"),
                "cluster_assignments": result.get("cluster_assignments"),
                "dendrogram_data": result.get("dendrogram_data"),
                "optimal_n_clusters": result.get("optimal_n_clusters"),
                "cluster_stats": result.get("cluster_stats"),
                "plot_data": result.get("plot_data")
            }
        except Exception as e:
            logger.error(f"Clustered correlation analysis failed: {e}", exc_info=True)
            return {"error": str(e)}
