from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import os
import pandas as pd
from app.schemas.analysis import AnalysisRequest, AnalysisResult, StatMethod
from app.stats.registry import get_method
from app.stats.engine import select_test, run_analysis

from app.api.datasets import DATA_DIR, parse_file

router = APIRouter()

@router.post("/recommend", response_model=StatMethod)
async def recommend_method(request: AnalysisRequest):
    # 1. Load Data
    # Assuming dataset_id is valid
    upload_dir = os.path.join(DATA_DIR, request.dataset_id)
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json')]
    if not files:
        raise HTTPException(status_code=404, detail="Dataset file not found")
    
    file_path = os.path.join(upload_dir, files[0])
    
    # Load metadata if exists to get header_row
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
        df = pd.read_csv(file_path) # Fallback

    # 2. Analyze Types
    # Request gives us `target_column` and `features`. 
    # For MVP, let's assume 1 feature vs 1 target or just 2 columns in `features`.
    
    col_a = request.target_column
    col_b = request.features[0]
    
    if col_a not in df.columns or col_b not in df.columns:
         raise HTTPException(status_code=400, detail=f"Columns not found. Available: {list(df.columns)}")

    # Simple type check
    # We should reuse the `dtect_type` from datasets but it's not exported.
    # Let's just rely on pandas types for the engine
    types = {}
    for col in [col_a, col_b]:
        if pd.api.types.is_numeric_dtype(df[col]):
            types[col] = "numeric"
        else:
            types[col] = "categorical"

    # 3. Select Test
    method_id = select_test(df, col_a, col_b, types, is_paired=request.is_paired)
    
    if not method_id:
        raise HTTPException(status_code=400, detail="No suitable method found for these variables.")
        
    return get_method(method_id)

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
    base_conclusion = f"Statistically {'significant' if result['significant'] else 'insignificant'} difference found (p={result['p_value']:.4f})."
    
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
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json')]
    if not files:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    file_path = os.path.join(upload_dir, files[0])
    
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
            print(f"AI Enhancement failed: {e}")
            
    # 6. Render HTML
    html_content = render_report(analysis_result, target_col, group_col, dataset_name=files[0])
    
    return HTMLResponse(content=html_content)

from app.schemas.analysis import BatchAnalysisResponse, BatchAnalysisRequest

@router.post("/batch", response_model=BatchAnalysisResponse)
async def run_batch_analysis(request: BatchAnalysisRequest):

    # 1. Load Data
    upload_dir = os.path.join(DATA_DIR, request.dataset_id)
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json')]
    if not files:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    file_path = os.path.join(upload_dir, files[0])
    
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
    from app.stats.engine import compute_batch_descriptives
    descriptives_data = compute_batch_descriptives(df, request.target_columns, request.group_column)
    
    # Convert to schema
    from app.schemas.analysis import DescriptiveStat, BatchAnalysisResponse, AnalysisResult
    
    descriptives = [DescriptiveStat(**d) for d in descriptives_data]
    
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
            
            # Format
            method_info = get_method(method_id)
            conclusion = f"P={res['p_value']:.4f}"
            
            result_obj = AnalysisResult(
                method=method_info,
                p_value=res["p_value"],
                stat_value=res["stat_value"],
                significant=res["significant"],
                groups=res.get("groups"),
                plot_data=res.get("plot_data"),
                plot_stats=res.get("plot_stats"),
                conclusion=conclusion
            )
            
            results[col] = result_obj
            
        except Exception as e:
            print(f"Batch analysis failed for {col}: {e}")
            pass

    return BatchAnalysisResponse(descriptives=descriptives, results=results)
