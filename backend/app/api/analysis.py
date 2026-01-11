
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import os
import pandas as pd
from pydantic import BaseModel
import json
import uuid

from app.schemas.analysis import AnalysisRequest, AnalysisResult, StatMethod
from app.stats.registry import get_method, METHODS
from app.stats.engine import select_test, run_analysis, compute_batch_descriptives
from app.modules.text_generator import TextGenerator
from app.core.pipeline import PipelineManager
from app.core.protocol_engine import ProtocolEngine
from app.modules.parsers import get_dataframe, get_dataset_path
from app.core.study_designer import StudyDesignEngine
from app.modules.reporting import generate_pdf_report
from app.core.logging import logger

from app.api.datasets import DATA_DIR, parse_file

router = APIRouter()
pipeline = PipelineManager(DATA_DIR)
protocol_engine = ProtocolEngine(pipeline)

# --- Schemas ---

class ProtocolRequest(BaseModel):
    dataset_id: str
    protocol: Dict[str, Any]

class DesignRequest(BaseModel):
    dataset_id: str
    goal: str # 'compare_groups', 'relationship', etc.
    variables: Dict[str, Any] # {'target': 'Hb', 'group': 'Treat'}

# --- Endpoints ---

@router.post("/design", response_model=Dict[str, Any])
def suggest_design(req: DesignRequest):
    """
    Uses StudyDesignEngine to generate an Analysis Protocol based on user inputs.
    """
    try:
        # 1. Load Dataset Metadata for Context (types, normality)
        # We assume the profile/scan_report exists or we quickly detect basic types
        # For MVP, we pass minimal metadata or load the scan report
        pipeline = PipelineManager("workspace/datasets")
        scan_path = os.path.join(pipeline.get_dataset_dir(req.dataset_id), "processed", "scan_report.json")
        
        if os.path.exists(scan_path):
             with open(scan_path) as f:
                 full_report = json.load(f)
                 metadata = full_report.get("columns", {})

        # 2. Generate Protocol
        designer = StudyDesignEngine()
        protocol = designer.suggest_protocol(req.goal, req.variables, metadata)
        return protocol
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Design generation failed: {str(e)}")

@router.get("/run/{run_id}")
def get_run_results(run_id: str, dataset_id: str):
    """
    Retrieves the results of a specific analysis run.
    """
    pipeline = PipelineManager("workspace/datasets")
    try:
        # We need dataset_id to find the run folder in the current hierarchy
        # Pipeline structure: datasets/{id}/analysis/{run_id}/results.json
        res = pipeline.get_run_results(dataset_id, run_id)
        if not res:
             raise HTTPException(status_code=404, detail="Results not found")
        return res
    except Exception as e:
         raise HTTPException(status_code=404, detail=f"Run not found: {str(e)}")

@router.get("/report/{run_id}/html")
def get_run_report_html(run_id: str, dataset_id: str):
    """
    Generates a printable HTML report for the analysis run.
    """
    from fastapi.responses import HTMLResponse
    from app.modules.reporting import render_protocol_report
    
    pipeline = PipelineManager("workspace/datasets")
    try:
        res = pipeline.get_run_results(dataset_id, run_id)
        if not res:
             raise HTTPException(status_code=404, detail="Results not found")
             
        # Generate HTML
        html = render_protocol_report(res, dataset_name=f"Dataset {dataset_id[:5]}...")
        return HTMLResponse(content=html)
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@router.post("/protocol/run")
async def run_protocol_api(request: ProtocolRequest):
    """
    Executes a multi-step analysis protocol.
    Returns the run_id (analysis container ID).
    """
    try:
        # Load Data using centralized helper (Processed > Raw)
        df = get_dataframe(request.dataset_id, DATA_DIR)
        
        # Run Engine
        run_id = protocol_engine.execute_protocol(request.dataset_id, df, request.protocol)
        
        return {"status": "success", "run_id": run_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol execution failed: {str(e)}")

@router.post("/run", response_model=AnalysisResult)
async def run_method_api(request: AnalysisRequest):
    # 1. Load Data
    file_path, upload_dir = get_dataset_path(request.dataset_id, DATA_DIR)
    if not file_path:
        raise HTTPException(status_code=404, detail="Dataset not found")
            
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r") as f:
            header_row = json.load(f).get("header_row", 0)
            
    # Load processed or raw
    processed_path = os.path.join(upload_dir, "processed.csv")
    if os.path.exists(processed_path):
        df = pd.read_csv(processed_path)
    else:
        df, _ = parse_file(file_path, header_row=header_row)
    
    col_a = request.target_column
    col_b = request.features[0] # Single feature for now
    
    # 2. Determine Method
    method_id = request.method_override
    if not method_id:
        # Auto-detect
        types = {}
        for col in [col_a, col_b]:
            if pd.api.types.is_numeric_dtype(df[col]):
                types[col] = "numeric"
            else:
                types[col] = "categorical"
        method_id = select_test(df, col_a, col_b, types, is_paired=request.is_paired)

    if not method_id:
         raise HTTPException(status_code=400, detail="Method determination failed.")

    # 3. Run
    try:
        results = run_analysis(df, method_id, col_a, col_b, is_paired=request.is_paired)
        
        # Build AnalysisResult
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
        
        # AI Conclusion
        ai_conclusion = await get_ai_conclusion(res)
        res.conclusion = ai_conclusion
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    
    # 4. Format Result
    # Use Rule-Based Generator for "Dissertation Style"
    variables_map = {"target": col_a, "feature": col_b, "group": col_b} # standardized map
    base_conclusion = TextGenerator.generate_conclusion(results, variables_map)
    
    analysis_res = AnalysisResult(
        method=method_info,
        p_value=result["p_value"],
        stat_value=result["stat_value"],
        significant=result["significant"],
        groups=result.get("groups"),
        plot_data=result.get("plot_data"),
        plot_stats=result.get("plot_stats"),
        conclusion=base_conclusion
    )

    # AI Enhancement
    from app.core.config import settings
    if settings.GLM_ENABLED and settings.GLM_API_KEY:
        from app.llm import get_ai_conclusion
        try:
            ai_text = await get_ai_conclusion(analysis_res)
            if ai_text:
                analysis_res.conclusion = ai_text
        except Exception:
            pass # Keep base conclusion
            
    return analysis_res

@router.get("/report/{dataset_id}")
async def download_report(
    dataset_id: str, 
    target_col: str, 
    group_col: str, 
    method_id: str = None
):
    from fastapi.responses import HTMLResponse
    from app.reporting import render_report
    
    # Re-run analysis logic to get results (similar to /run)
    # 1. Load Data
    # 1. Load Data
    file_path, upload_dir = get_dataset_path(dataset_id, DATA_DIR)
    if not file_path:
        raise HTTPException(status_code=404, detail="Dataset not found or file missing")
    
    # Load metadata
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)
            header_row = meta.get("header_row", 0)
            
    df, _ = parse_file(file_path, header_row=header_row)
    
    # 2. Determine Method (if not provided)
    col_a = target_col
    col_b = group_col
    
    if not method_id:
        # Mini auto-detect
        types = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical") for c in [col_a, col_b]}
        method_id = select_test(df, col_a, col_b, types)
    
    if not method_id:
        raise HTTPException(status_code=400, detail="Could not determine method for report.")

    
    # 3. Run Analysis
    try:
        res = run_analysis(df, method_id, col_a, col_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    method_info = get_method(method_id)
    
    # 4. Create Result Object
    # Initial conclusion
    conclusion = f"Statistically {'significant' if res['significant'] else 'insignificant'} difference found (p={res['p_value']:.4f})."
    
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

    # 5. Enhace with AI (Async)
    from app.core.config import settings
    if settings.GLM_ENABLED and settings.GLM_API_KEY:
        from app.llm import get_ai_conclusion
        try:
            ai_text = await get_ai_conclusion(analysis_result)
            if ai_text:
                analysis_result.conclusion = ai_text
        except Exception as e:
            logger.warning(f"AI Enhancement failed: {e}", exc_info=True)
            
    # 6. Render HTML
    html_content = render_report(analysis_result, target_col, group_col, dataset_name=files[0])
    
    return HTMLResponse(content=html_content)

from app.schemas.analysis import BatchAnalysisResponse, BatchAnalysisRequest

def _sanitize(obj):
    """Recursively replace NaN/Inf with None."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj

@router.post("/batch", response_model=BatchAnalysisResponse)
async def run_batch_analysis(request: BatchAnalysisRequest):
    from app.schemas.analysis import DescriptiveStat, BatchAnalysisResponse, AnalysisResult
    
    # 1. Load Data
    file_path, upload_dir = get_dataset_path(request.dataset_id, DATA_DIR)
    if not file_path:
        raise HTTPException(status_code=404, detail="Dataset not found or file missing")
    
    # Load metadata
    header_row = 0
    meta_path = os.path.join(upload_dir, "metadata.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path, "r") as f:
            meta = json.load(f)
            header_row = meta.get("header_row", 0)
            
    try:
        df, _ = parse_file(file_path, header_row=header_row)
    except:
        df = pd.read_csv(file_path)

    # 2. Compute Descriptives (Primary)
    from app.stats.engine import compute_descriptive_compare
    
    descriptives = []
    
    for col in request.target_columns:
        if col not in df.columns: continue
        
        # Get raw stats (returns dict keyed by group -> {mean, count...})
        raw_stats = compute_descriptive_compare(df, col, request.group_column)
        
        # Convert to DescriptiveStat objects
        for grp, stats in raw_stats.items():
            if grp == "overall" and len(raw_stats) > 1: continue # Skip overall for now or include? Schema has 'group' field.
            
            # handle nested structure if needed
            if not isinstance(stats, dict): continue
            
            ds = DescriptiveStat(
                variable=col,
                group=str(grp),
                count=stats.get("count", 0),
                mean=stats.get("mean"),
                median=stats.get("median"),
                sd=stats.get("std"),
                is_normal=False # Not computed here for performance
            )
            descriptives.append(ds)
            
    # Sanitize Descriptives
    descriptives = _sanitize(descriptives)
    
    # 3. Running Hypothesis Tests
    results = {}
    group_col = request.group_column
    
    # Pre-calculate types for test selection (assumes Group is categorical, Targets are numeric)
    # Verification:
    if not isinstance(df[group_col].dtype, pd.CategoricalDtype) and df[group_col].nunique() < 10:
         # Treat as categorical for purpose of test
         pass
         
    for col in request.target_columns:
        if col not in df.columns: 
            continue
            
        # Select Method
        types = {col: "numeric", group_col: "categorical"}
        method_id = select_test(df, col, group_col, types)
        
        if not method_id:
            continue
            
        try:
            # Run
            res = run_analysis(df, method_id, col, group_col)
            
            # SANITIZE RESULT
            res = _sanitize(res)
            
            # Format
            method_info = get_method(method_id)
            conclusion = f"P={res.get('p_value'):.4f}" if res.get('p_value') is not None else "P=N/A"
            
            result_obj = AnalysisResult(
                method=method_info,
                p_value=res.get("p_value"),
                stat_value=res.get("stat_value"),
                significant=res.get("significant", False),
                groups=res.get("groups"),
                plot_data=res.get("plot_data"),
                plot_stats=res.get("plot_stats"),
                conclusion=conclusion,
                adjusted_p_value=res.get("p_value_adj"),
                significant_adj=res.get("significant_adj")
            )
            
            results[col] = result_obj
            
        except Exception as e:
            logger.error(f"Batch analysis failed for {col}: {e}", exc_info=True)
            pass

    return BatchAnalysisResponse(descriptives=descriptives, results=results)
