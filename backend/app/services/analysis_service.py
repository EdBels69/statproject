import os
import json
import pandas as pd
import math
from fastapi import HTTPException
from typing import List, Dict, Any, Optional

from app.schemas.analysis import (
    AnalysisRequest, AnalysisResult, BatchAnalysisResponse, BatchAnalysisRequest,
    ProtocolRequest, DesignRequest, PlotUpdateParams, SelectiveExportRequest, DescriptiveStat,
    RiskAnalysisRequest, RiskAnalysisResponse, CorrelationMatrixRequest, CorrelationMatrixResponse
)
from app.stats.registry import get_method, METHODS
from app.stats.engine import select_test, run_analysis, compute_descriptive_compare
from app.stats.risk_engine import calculate_risk_metrics
from app.stats.plotter import render_custom_plot
from app.modules.text_generator import TextGenerator
from app.core.pipeline import PipelineManager
from app.core.protocol_engine import ProtocolEngine
from app.modules.parsers import get_dataframe, get_dataset_path, parse_file
from app.core.study_designer import StudyDesignEngine
from app.modules.reporting import render_protocol_report, render_report
from app.modules.word_report import generate_word_report, generate_selective_word_report
from app.core.config import settings
import numpy as np

def sanitize_for_json(obj):
    """Recursively convert NaN/Infinity to None for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.integer)):
        val = float(obj) if isinstance(obj, np.floating) else int(obj)
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    elif isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    return obj


class AnalysisService:
    def __init__(self):
        self.workspace_dir = "workspace"
        self.data_dir = os.path.join(self.workspace_dir, "datasets")
        self.pipeline = PipelineManager(self.data_dir)
        self.protocol_engine = ProtocolEngine(self.pipeline)
        
    def _load_data(self, dataset_id: str):
        file_path, upload_dir = get_dataset_path(dataset_id, self.data_dir)
        if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
        
        header_row = 0
        original_filename = None
        
        # Priority: Pipeline Source Meta
        source_meta = os.path.join(upload_dir, "source", "meta.json")
        legacy_meta = os.path.join(upload_dir, "metadata.json")
        
        meta_to_read = None
        if os.path.exists(source_meta): meta_to_read = source_meta
        elif os.path.exists(legacy_meta): meta_to_read = legacy_meta
        
        if meta_to_read:
            with open(meta_to_read, "r") as f: 
                meta = json.load(f)
                header_row = meta.get("header_row", 0)
                original_filename = meta.get("original_filename")
            
        processed_path = os.path.join(upload_dir, "processed.csv")
        if os.path.exists(processed_path): df = pd.read_csv(processed_path)
        else: df, _ = parse_file(file_path, header_row=header_row, original_filename=original_filename)
        return df, upload_dir

    async def run_risk_analysis(self, req: RiskAnalysisRequest) -> RiskAnalysisResponse:
        """
        Runs Epidemiology Risk Analysis (RR, OR).
        """
        # 1. Load Data
        df, _ = self._load_data(req.dataset_id)
        
        # 2. Validate Columns
        if req.target_column not in df.columns or req.group_column not in df.columns:
            raise ValueError(f"Columns not found: {req.target_column}, {req.group_column}")
            
        # 3. Determine 'Positive' values if not provided
        target_pos = req.target_positive_val
        exposure_pos = req.group_exposure_val
        
        # Auto-detect if missing (take 2nd distinct value, usually 1 or 'Yes' if sorted)
        if not target_pos:
            uniques = sorted(df[req.target_column].dropna().unique())
            if len(uniques) == 2: target_pos = str(uniques[1])
            else: raise ValueError("Target column must be binary or 'Positive Value' must be specified.")
            
        if not exposure_pos:
            uniques = sorted(df[req.group_column].dropna().unique())
            if len(uniques) == 2: exposure_pos = str(uniques[1])
            else: raise ValueError("Exposure column must be binary or 'Exposure Value' must be specified.")
            
        # 4. Run Calc
        res = calculate_risk_metrics(df, req.target_column, req.group_column, target_pos, exposure_pos)
        
        # 5. Format Conclusion
        conclusion = ""
        rr = next((m for m in res["metrics"] if "Relative Risk" in m.name), None)
        if rr:
            conclusion = f"Relative Risk is {rr.value:.2f} (95% CI: {rr.ci_lower:.2f}-{rr.ci_upper:.2f}). "
            if rr.significant: conclusion += "The association is statistically significant."
            else: conclusion += "The association is not significant."
            
        return RiskAnalysisResponse(
            metrics=res["metrics"],
            contingency_table=res["contingency_table"],
            conclusion=conclusion
        )
        
    def _sanitize(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj): return None
            return obj
        if isinstance(obj, dict): return {k: self._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list): return [self._sanitize(v) for v in obj]
        return obj

    async def _get_ai_conclusion(self, res: AnalysisResult) -> Optional[str]:
        if settings.GLM_ENABLED and settings.GLM_API_KEY:
            from app.llm import get_ai_conclusion
            try: return await get_ai_conclusion(res)
            except: pass
        return None

    def suggest_design(self, req: DesignRequest) -> Dict[str, Any]:
        try:
            scan_path = os.path.join(self.pipeline.get_dataset_dir(req.dataset_id), "processed", "scan_report.json")
            metadata = {}
            if os.path.exists(scan_path):
                 with open(scan_path) as f:
                     full_report = json.load(f)
                     metadata = full_report.get("columns", {})
            
            designer = StudyDesignEngine()
            return designer.suggest_protocol(req.goal, req.variables, metadata)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Design failed: {str(e)}")

    def get_run_results(self, dataset_id: str, run_id: str) -> dict:
        try:
            res = self.pipeline.get_run_results(dataset_id, run_id)
            if not res: raise HTTPException(status_code=404, detail="Results not found")
            return res
        except Exception as e:
             raise HTTPException(status_code=404, detail=f"Run not found: {str(e)}")

    def get_run_report_html(self, dataset_id: str, run_id: str) -> str:
        res = self.get_run_results(dataset_id, run_id)
        return render_protocol_report(res, dataset_name=f"Dataset {dataset_id[:5]}...")

    def update_step_plot(self, dataset_id: str, run_id: str, step_id: str, params: PlotUpdateParams) -> dict:
        try:
            res = self.get_run_results(dataset_id, run_id)
            if "results" not in res: raise HTTPException(status_code=404, detail="Run invalid")
            
            step_data = res["results"].get(step_id)
            if not step_data: raise HTTPException(status_code=404, detail="Step not found")
            
            plot_data = step_data.get("plot_data")
            if not plot_data: raise HTTPException(status_code=400, detail="No plot data")
            
            new_img = render_custom_plot(plot_data, params.dict())
            
            res["results"][step_id]["plot_image"] = new_img
            res["results"][step_id]["plot_params"] = params.dict()
            
            run_dir = self.pipeline.get_run_dir(dataset_id, run_id)
            with open(os.path.join(run_dir, "results.json"), "w") as f:
                json.dump(res, f, indent=2)
                
            return {"plot_image": new_img}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Plot update failed: {str(e)}")

    def get_run_report_word(self, dataset_id: str, run_id: str) -> bytes:
        res = self.get_run_results(dataset_id, run_id)
        return generate_word_report(res, dataset_name=f"Dataset {dataset_id[:8]}")

    def get_selective_word_report(self, dataset_id: str, run_id: str, req: SelectiveExportRequest) -> bytes:
        res = self.get_run_results(dataset_id, run_id)
        
        filtered_results = {}
        for key, value in res.get("results", {}).items():
            var_name = key.replace("test_", "").replace("desc_", "")
            if var_name in req.variables:
                filtered_results[key] = value
                
        filtered_res = {
            **res,
            "results": filtered_results,
            "export_settings": {
                "show_mean": req.show_mean,
                "show_median": req.show_median,
                "show_quartiles": req.show_quartiles
            }
        }
        
        return generate_selective_word_report(
            filtered_res, 
            dataset_name=f"Dataset {dataset_id[:8]}",
            selected_vars=req.variables
        )

    async def run_protocol(self, req: ProtocolRequest) -> str:
        try:
            df = get_dataframe(req.dataset_id, self.data_dir)
            return self.protocol_engine.execute_protocol(req.dataset_id, df, req.protocol)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Protocol failed: {str(e)}")

    async def run_single_analysis(self, req: AnalysisRequest) -> AnalysisResult:
        file_path, upload_dir = get_dataset_path(req.dataset_id, self.data_dir)
        if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load Logic
        header_row = 0
        original_filename = None
        
        # Priority: Pipeline Source Meta
        source_meta = os.path.join(upload_dir, "source", "meta.json")
        legacy_meta = os.path.join(upload_dir, "metadata.json")
        
        meta_to_read = None
        if os.path.exists(source_meta): meta_to_read = source_meta
        elif os.path.exists(legacy_meta): meta_to_read = legacy_meta
        
        if meta_to_read:
            with open(meta_to_read, "r") as f: 
                meta = json.load(f)
                header_row = meta.get("header_row", 0)
                original_filename = meta.get("original_filename")
            
        processed_path = os.path.join(upload_dir, "processed.csv")
        if os.path.exists(processed_path): df = pd.read_csv(processed_path)
        else: df, _ = parse_file(file_path, header_row=header_row, original_filename=original_filename)
        
        col_a = req.target_column
        col_b = req.features[0]
        
        method_id = req.method_override
        if not method_id:
            types = {}
            for col in [col_a, col_b]:
                types[col] = "numeric" if pd.api.types.is_numeric_dtype(df[col]) else "categorical"
            method_id = select_test(df, col_a, col_b, types, is_paired=req.is_paired)
            
        if not method_id: raise HTTPException(status_code=400, detail="Method failed")
        
        try:
            results = run_analysis(df, method_id, col_a, col_b, is_paired=req.is_paired)
            method_info = get_method(method_id)
            
            res = AnalysisResult(
                method=method_info,
                p_value=results["p_value"],
                stat_value=results["stat_value"],
                significant=results["significant"],
                groups=results.get("groups"),
                plot_data=results.get("plot_data"),
                plot_stats=results.get("plot_stats"),
                conclusion=""
            )
            
            variables_map = {"target": col_a, "feature": col_b, "group": col_b}
            
            # Prioritize Rule-Based Narrative
            if results.get("narrative"):
                res.conclusion = results["narrative"]
            else:
                res.conclusion = TextGenerator.generate_conclusion(results, variables_map)
            
            ai_conc = await self._get_ai_conclusion(res)
            if ai_conc: res.conclusion = ai_conc
            
            return res
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    async def download_report_html(self, dataset_id: str, target_col: str, group_col: str, method_id: str = None) -> str:
        file_path, upload_dir = get_dataset_path(dataset_id, self.data_dir)
        if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
        
        header_row = 0
        meta_path = os.path.join(upload_dir, "metadata.json")
        if os.path.exists(meta_path):
             with open(meta_path, "r") as f: header_row = json.load(f).get("header_row", 0)
        df, _ = parse_file(file_path, header_row=header_row)
        
        if not method_id:
            types = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical") for c in [target_col, group_col]}
            method_id = select_test(df, target_col, group_col, types)
        if not method_id: raise HTTPException(status_code=400, detail="Method determination failed")
        
        try:
             res = run_analysis(df, method_id, target_col, group_col)
        except Exception as e: raise HTTPException(status_code=500, detail=str(e))
        
        method_info = get_method(method_id)
        conclusion = f"P={res['p_value']:.4f}"
        
        analysis_result = AnalysisResult(
            method=method_info,
            p_value=res["p_value"],
            stat_value=res["stat_value"],
            significant=res["significant"],
            groups=res.get("groups"),
            plot_data=res.get("plot_data"),
            plot_stats=res.get("plot_stats"),
            conclusion=conclusion
        )
        
        ai_conc = await self._get_ai_conclusion(analysis_result)
        if ai_conc: analysis_result.conclusion = ai_conc
        
        return render_report(analysis_result, target_col, group_col, dataset_name="Dataset Report")

    async def run_batch_analysis(self, req: BatchAnalysisRequest) -> BatchAnalysisResponse:
        file_path, upload_dir = get_dataset_path(req.dataset_id, self.data_dir)
        if not file_path: raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Load processed data (check multiple possible locations)
        processed_path = os.path.join(upload_dir, "processed", "data.csv")
        legacy_processed = os.path.join(upload_dir, "processed.csv")
        
        df = None
        
        if os.path.exists(processed_path):
            df = pd.read_csv(processed_path)
        elif os.path.exists(legacy_processed):
            df = pd.read_csv(legacy_processed)
        else:
            # Fallback to parsing original file
            header_row = 0
            
            # Check for meta.json in various locations
            for meta_loc in [os.path.join(upload_dir, "source", "meta.json"), 
                             os.path.join(upload_dir, "metadata.json")]:
                if os.path.exists(meta_loc):
                    with open(meta_loc, "r") as f: 
                        meta = json.load(f)
                        header_row = meta.get("header_row", 0)
                    break
            
            # Try to find readable file in multiple locations
            search_dirs = [
                os.path.join(upload_dir, "source"),  # New structure
                upload_dir,  # Legacy structure (files in root)
            ]
            
            found = False
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                for filename in os.listdir(search_dir):
                    if filename.endswith(('.csv', '.xlsx', '.xls')) and not filename.startswith('.'):
                        candidate = os.path.join(search_dir, filename)
                        try:
                            df, _ = parse_file(candidate, header_row=header_row)
                            found = True
                            break
                        except:
                            continue
                if found:
                    break
            
            if df is None:
                raise HTTPException(status_code=400, detail="Cannot find readable dataset file")



        descriptives = []
        for col in req.target_columns:
            if col not in df.columns: continue
            raw_stats = compute_descriptive_compare(df, col, req.group_column)
            for grp, stats in raw_stats.items():
                if grp == "overall" and len(raw_stats) > 1: continue
                if not isinstance(stats, dict): continue
                descriptives.append(DescriptiveStat(
                    variable=col, 
                    group=str(grp), 
                    count=stats.get("count", 0),
                    mean=stats.get("mean"), 
                    median=stats.get("median"), 
                    sd=stats.get("std")
                ))
        
        descriptives = self._sanitize(descriptives)
        
        results = {} # Map[target_col, AnalysisResult]
        raw_results_list = [] # List[(col, p_value, AnalysisResultObj)]
        
        for col in req.target_columns:
            if col not in df.columns: continue
            types = {col: "numeric", req.group_column: "categorical"}
            method_id = select_test(df, col, req.group_column, types)
            if not method_id: continue
            
            try:
                res = run_analysis(df, method_id, col, req.group_column)
                res = self._sanitize(res)
                method_info = get_method(method_id)
                p_val = res.get("p_value")
                
                conclusion = f"P={p_val:.4f}" if p_val is not None else "P=N/A"
                
                # Check for warnings (Friedman)
                if res.get("warning"):
                    conclusion += f" [Warning: {res['warning']}]"

                ar = AnalysisResult(
                    method=method_info,
                    p_value=p_val,
                    stat_value=res.get("stat_value"),
                    significant=res.get("significant", False),
                    groups=res.get("groups"),
                    conclusion=conclusion,
                    plot_data=res.get("plot_data"),
                    plot_stats=res.get("plot_stats"),
                    qq_data=res.get("qq_data")
                )
                
                results[col] = ar
                # Store for correction if p-value exists
                if p_val is not None and not math.isnan(p_val):
                    raw_results_list.append({"col": col, "p": p_val})
                    
            except Exception: pass
            
        # Apply Correction
        correction_method = req.options.get("correction", "none")
        valid_methods = ["bonferroni", "holm", "holm-sidak", "simes-hochberg", "hommel", "fdr_bh", "fdr_by", "fdr_tsbh", "fdr_tsbky"]
        
        if correction_method in valid_methods and len(raw_results_list) > 1:
            try:
                from statsmodels.stats.multitest import multipletests
                pvals = [r["p"] for r in raw_results_list]
                reject, pvals_corrected, _, _ = multipletests(pvals, alpha=0.05, method=correction_method)
                
                # Map back
                for i, r in enumerate(raw_results_list):
                    col = r["col"]
                    res_obj = results[col]
                    res_obj.adjusted_p_value = float(pvals_corrected[i])
                    res_obj.significant_adj = bool(reject[i])
            except Exception as e:
                print(f"Correction failed: {e}")
            
        # Sanitize all results for JSON serialization (remove NaN/Infinity)
        clean_results = {}
        for col, res_obj in results.items():
            clean_results[col] = sanitize_for_json(res_obj.dict() if hasattr(res_obj, 'dict') else res_obj)
        
        clean_descriptives = [sanitize_for_json(d.dict() if hasattr(d, 'dict') else d) for d in descriptives]
            
        return {"descriptives": clean_descriptives, "results": clean_results}


    async def run_correlation_matrix(self, req: CorrelationMatrixRequest) -> CorrelationMatrixResponse:
        fpath = os.path.join(settings.DATA_DIR, f"{req.dataset_id}.csv")
        if not os.path.exists(fpath):
            raise ValueError(f"Dataset {req.dataset_id} not found")
            
        df = pd.read_csv(fpath)
        
        # Determine engine method
        from app.stats.engine import _handle_correlation_matrix, clean_dataframe
        
        # Clean dataframe for selected variables
        df_clean = clean_dataframe(df, req.features) # Basic numeric check
        
        # Run Matrix
        res = _handle_correlation_matrix(df_clean, req.features, req.method, req.cluster_variables)
        
        if "error" in res:
             raise ValueError(res["error"])
             
        return CorrelationMatrixResponse(
            method=res["method"],
            corr_matrix=res["corr_matrix"],
            p_values=res["p_values"],
            plot_image=res["plot_image"],
            variables=res["variables"],
            clustered=res["clustered"],
            n_obs=res["n_obs"]
        )
