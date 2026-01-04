import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.datasets import DATA_DIR
from app.modules.job_runner import JobManager
from app.modules.parsers import get_dataframe
from app.stats.engine import select_test
from app.stats.registry import run_registered_method, get_method
from app.modules.reporting import generate_pdf_report, cleanup_old_reports

router = APIRouter(prefix="/jobs", tags=["jobs"])

job_manager = JobManager(DATA_DIR)


class AnalysisJobRequest(BaseModel):
    dataset_id: str
    target_column: str
    feature_column: str
    method_id: Optional[str] = None
    is_paired: bool = False
    job_type: str = "analysis"  # analysis or report


@router.post("/analysis")
async def enqueue_analysis(request: AnalysisJobRequest):
    try:
        df = get_dataframe(request.dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to load dataset: {exc}")

    method_id = request.method_id
    if not method_id:
        types = {
            request.target_column: "numeric" if df[request.target_column].dtype.kind in "fcmiu" else "categorical",
            request.feature_column: "numeric" if df[request.feature_column].dtype.kind in "fcmiu" else "categorical",
        }
        method_id = select_test(df, request.target_column, request.feature_column, types, is_paired=request.is_paired)

    if not method_id:
        raise HTTPException(status_code=400, detail="Unable to determine method")

    job_key = f"{request.dataset_id}:{method_id}:{request.target_column}:{request.feature_column}:{request.job_type}"

    def _runner():
        if method_id in ["pearson", "spearman"]:
            result = run_registered_method(method_id, df, x=request.target_column, y=request.feature_column)
        elif method_id in ["linear_regression", "logistic_regression"]:
            result = run_registered_method(method_id, df, target=request.target_column, predictors=[request.feature_column])
        elif method_id == "survival_km":
            result = run_registered_method(method_id, df, duration=request.target_column, event=request.feature_column, group=None)
        else:
            result = run_registered_method(method_id, df, target=request.target_column, group=request.feature_column, is_paired=request.is_paired)
        if request.job_type == "report":
            method = get_method(method_id)
            result_payload = {
                "p_value": result.get("p_value", 0),
                "stat_value": result.get("stat_value", 0),
                "significant": result.get("significant", False),
                "method": method.name if method else method_id,
                "conclusion": result.get("conclusion", ""),
                "groups": result.get("groups", []),
                "plot_stats": result.get("plot_stats", {}),
            }
            filepath = generate_pdf_report(result_payload, {"target": request.target_column, "group": request.feature_column}, request.dataset_id)
            cleanup_old_reports()
            return {"result": result, "artifact": filepath}
        return result

    status = job_manager.submit(
        dataset_id=request.dataset_id,
        task_type=request.job_type,
        job_key=job_key,
        runner=_runner,
        payload=request.model_dump(),
    )
    return status


@router.get("/{dataset_id}/{job_id}")
async def get_job_status(dataset_id: str, job_id: str):
    status = job_manager.get(dataset_id, job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    return status
