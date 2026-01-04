import os
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.modules.expert_system import WizardRequest, WizardRecommendation, recommend_method
from app.modules.parsers import get_dataframe
from app.stats.registry import run_registered_method, get_method
from app.modules.reporting import generate_pdf_report
from app.api.datasets import DATA_DIR # Reuse shared data dir constant

router = APIRouter()

@router.post("/recommend", response_model=WizardRecommendation)
async def recommend(request: WizardRequest):
    try:
        return recommend_method(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendation: {str(e)}"
        )

class ApplyRequest(BaseModel):
    recommendation: WizardRecommendation
    variables: Dict[str, str]
    dataset_id: str

@router.post("/apply")
async def apply_analysis(request: ApplyRequest):
    dataset_id = request.dataset_id
    method_id = request.recommendation.method_id
    vars = request.variables
    
    # 1. Load Data
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
    except FileNotFoundError:
         raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as e:
         raise HTTPException(status_code=400, detail=f"Failed to load dataset: {e}")

    # 2. Extract Variable Names
    # For survival, we need 3: duration, event, group
    # For others, we need 2: target, group
    target_col = vars.get("target") or vars.get("duration") or vars.get("y")
    group_col = vars.get("group") or vars.get("factor") or vars.get("x")
    event_col = vars.get("event") or vars.get("status")
    # Multiple predictors for regression
    predictors = vars.get("predictors", "").split(",") if vars.get("predictors") else []
    if not predictors and group_col:
        predictors = [group_col]

    if method_id == "survival_km":
        if not target_col or not event_col:
             raise HTTPException(status_code=400, detail="Survival analysis requires 'duration' and 'event' columns.")
    elif method_id in ["linear_regression", "logistic_regression"]:
        if not target_col or not predictors:
             raise HTTPException(status_code=400, detail="Regression requires an outcome and predictors.")
    else:
        if not target_col or not group_col:
            raise HTTPException(status_code=400, detail="Missing variable mapping. Need 'target' and 'group'.")
        
    # Validation
    valid_cols = [target_col, group_col, event_col] + predictors
    for c in valid_cols:
        if c and c not in df.columns:
             raise HTTPException(status_code=400, detail=f"Column '{c}' not found in dataset.")

    # 3. Run Real Analysis
    try:
        if method_id == "survival_km":
            results = run_registered_method(method_id, df, duration=target_col, event=event_col, group=group_col)
        elif method_id in ["linear_regression", "logistic_regression"]:
            results = run_registered_method(method_id, df, target=target_col, predictors=predictors)
        elif method_id in ["pearson", "spearman"]:
            results = run_registered_method(method_id, df, x=target_col, y=group_col)
        else:
            results = run_registered_method(method_id, df, target=target_col, group=group_col, is_paired=False)
        
        # AI Enhancement
        from app.llm import get_ai_conclusion
        from app.schemas.analysis import AnalysisResult
        
        method_info = get_method(method_id)
        
        temp_res = AnalysisResult(
            method=method_info,
            p_value=results.get("p_value", 0.0),
            stat_value=results.get("stat_value", 0.0),
            significant=results.get("significant", False),
            groups=results.get("groups"),
            plot_stats=results.get("plot_stats"),
            r_squared=results.get("r_squared"),
            coefficients=results.get("coefficients"),
            conclusion=""
        )
        
        ai_conclusion = await get_ai_conclusion(temp_res)
        results["conclusion"] = ai_conclusion

        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis execution failed: {str(e)}")

class ExportRequest(BaseModel):
    results: Dict[str, Any]
    variables: Dict[str, str]
    dataset_id: str

@router.get("/export/{dataset_id}/{variable}")
async def export_report_get(
    dataset_id: str,
    variable: str = "Multiple",
    group_column: str = "Group"
):
    """
    GET endpoint for PDF export - bypasses browser popup blocker.
    Opens in new tab without permission dialog.
    """
    try:
        # Simplified results for quick export
        results = {
            "p_value": 0,
            "stat_value": 0,
            "significant": False,
            "method": f"Batch Analysis: {variable}",
            "conclusion": f"Analysis results for {variable} grouped by {group_column}"
        }
        
        variables = {
            "target": variable,
            "group": group_column
        }
        
        from app.modules.reporting import generate_pdf_report
        filepath = generate_pdf_report(results, variables, dataset_id)
        
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=f"Report_{variable}_{dataset_id[:8]}.pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.post("/export")
async def export_report(request: ExportRequest):
    try:
        from app.modules.reporting import generate_pdf_report
        filepath = generate_pdf_report(request.results, request.variables, request.dataset_id)
        return FileResponse(
            filepath, 
            media_type='application/pdf', 
            filename=os.path.basename(filepath)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
