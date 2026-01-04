from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import pandas as pd
from app.schemas.analysis import AnalysisRequest, AnalysisResult, StatMethod
from app.stats.registry import get_method, run_registered_method
from app.stats.engine import select_test
from app.llm import get_ai_conclusion

from app.api.datasets import DATA_DIR
from app.modules.parsers import get_dataframe

router = APIRouter()


def _execute_registered(method_id: str, df: pd.DataFrame, col_a: str, col_b: str, *, is_paired: bool, predictors: List[str] = None):
    predictors = predictors or []
    if method_id in ["pearson", "spearman"]:
        return run_registered_method(method_id, df, x=col_a, y=col_b)
    if method_id in ["linear_regression", "logistic_regression"]:
        return run_registered_method(method_id, df, target=col_a, predictors=predictors or [col_b])
    if method_id == "survival_km":
        return run_registered_method(method_id, df, duration=col_a, event=col_b, group=None)
    return run_registered_method(method_id, df, target=col_a, group=col_b, is_paired=is_paired)

@router.post("/recommend", response_model=StatMethod)
async def recommend_method(request: AnalysisRequest):
    # 1. Load Data
    # Assuming dataset_id is valid
    try:
        df = get_dataframe(request.dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset file not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load dataset: {exc}")

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
    try:
        df = get_dataframe(request.dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load dataset: {exc}")
    
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
        predictors = request.features if request.features else [col_b]
        results = _execute_registered(method_id, df, col_a, col_b, is_paired=request.is_paired, predictors=predictors)
        
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
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load dataset: {exc}")
    
    # 2. Determine Method (if not provided)
    col_a = target_col
    col_b = group_col
    dataset_name = dataset_id
    
    if not method_id:
        # Mini auto-detect
        types = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical") for c in [col_a, col_b]}
        method_id = select_test(df, col_a, col_b, types)
    
    if not method_id:
        raise HTTPException(status_code=400, detail="Could not determine method for report.")

    
    # 3. Run Analysis
    try:
        res = _execute_registered(method_id, df, col_a, col_b, is_paired=False)
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
        try:
            ai_text = await get_ai_conclusion(analysis_result)
            if ai_text:
                analysis_result.conclusion = ai_text
        except Exception as e:
            print(f"AI Enhancement failed: {e}")
            
    # 6. Render HTML
    html_content = render_report(analysis_result, target_col, group_col, dataset_name=dataset_name)
    
    return HTMLResponse(content=html_content)

from app.schemas.analysis import BatchAnalysisResponse, BatchAnalysisRequest

@router.post("/batch", response_model=BatchAnalysisResponse)
async def run_batch_analysis(request: BatchAnalysisRequest):

    # 1. Load Data
    try:
        df = get_dataframe(request.dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dataset load failed: {exc}")

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
            res = _execute_registered(method_id, df, col, group_col, is_paired=False)
            
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
