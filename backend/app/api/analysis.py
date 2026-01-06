from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from typing import List, Dict, Any, Optional

from app.schemas.analysis import (
    AnalysisRequest, AnalysisResult, BatchAnalysisResponse, BatchAnalysisRequest,
    ProtocolRequest, DesignRequest, PlotUpdateParams, SelectiveExportRequest,
    RiskAnalysisRequest, RiskAnalysisResponse, ReportPreviewRequest,
    CorrelationMatrixRequest, CorrelationMatrixResponse
)
from app.services.analysis_service import AnalysisService

router = APIRouter()

def get_service():
    return AnalysisService()

@router.post("/design", response_model=Dict[str, Any])
def suggest_design(req: DesignRequest, service: AnalysisService = Depends(get_service)):
    return service.suggest_design(req)

@router.get("/run/{run_id}")
def get_run_results(run_id: str, dataset_id: str, service: AnalysisService = Depends(get_service)):
    return service.get_run_results(dataset_id, run_id)

@router.get("/report/{run_id}/html")
def get_run_report_html(run_id: str, dataset_id: str, service: AnalysisService = Depends(get_service)):
    html = service.get_run_report_html(dataset_id, run_id)
    return HTMLResponse(content=html)

@router.post("/run/{run_id}/step/{step_id}/plot")
def update_step_plot(run_id: str, step_id: str, dataset_id: str, params: PlotUpdateParams, service: AnalysisService = Depends(get_service)):
    return service.update_step_plot(dataset_id, run_id, step_id, params)

@router.get("/report/{run_id}/word")
def get_run_report_word(run_id: str, dataset_id: str, service: AnalysisService = Depends(get_service)):
    doc_bytes = service.get_run_report_word(dataset_id, run_id)
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report_{run_id[:8]}.docx"}
    )

@router.post("/report/{run_id}/word/selective")
def get_selective_word_report(run_id: str, dataset_id: str, req: SelectiveExportRequest, service: AnalysisService = Depends(get_service)):
    doc_bytes = service.get_selective_word_report(dataset_id, run_id, req)
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report_selected_{run_id[:8]}.docx"}
    )

@router.post("/risk", response_model=RiskAnalysisResponse)
async def run_risk_analysis_api(req: RiskAnalysisRequest, service: AnalysisService = Depends(get_service)):
    return await service.run_risk_analysis(req)

@router.post("/protocol/run")
async def run_protocol_api(request: ProtocolRequest, service: AnalysisService = Depends(get_service)):
    run_id = await service.run_protocol(request)
    return {"status": "success", "run_id": run_id}

@router.post("/run", response_model=AnalysisResult)
async def run_single_analysis(request: AnalysisRequest, service: AnalysisService = Depends(get_service)):
    return await service.run_single_analysis(request)

@router.get("/report/{dataset_id}")
async def download_report(
    dataset_id: str, 
    target_col: str, 
    group_col: str, 
    method_id: str = None, 
    service: AnalysisService = Depends(get_service)
):
    html = await service.download_report_html(dataset_id, target_col, group_col, method_id)
    return HTMLResponse(content=html)

@router.post("/correlation_matrix", response_model=CorrelationMatrixResponse)
async def run_correlation_matrix(request: CorrelationMatrixRequest, service: AnalysisService = Depends(get_service)):
    return await service.run_correlation_matrix(request)

@router.post("/batch", response_model=BatchAnalysisResponse)
async def run_batch_analysis(request: BatchAnalysisRequest, service: AnalysisService = Depends(get_service)):
    return await service.run_batch_analysis(request)

@router.post("/report/preview")
def preview_report_html(req: ReportPreviewRequest, service: AnalysisService = Depends(get_service)):
    # Direct render without run_id lookup
    from app.modules.reporting import render_protocol_report
    html = render_protocol_report(req.dict(), dataset_name=req.dataset_name)
    return HTMLResponse(content=html)

@router.post("/report/word/preview")
def preview_report_word(req: ReportPreviewRequest, service: AnalysisService = Depends(get_service)):
    # Direct render without run_id lookup
    from app.modules.word_report import generate_word_report
    doc_bytes = generate_word_report(req.dict(), dataset_name=req.dataset_name)
    return Response(
        content=doc_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=report_preview.docx"}
    )

@router.post("/report/batch")
async def generate_batch_report(data: dict):
    """Generate Word report from batch analysis results."""
    from app.modules.word_report import generate_batch_report
    try:
        doc_bytes = generate_batch_report(
            results=data.get("results", {}),
            descriptives=data.get("descriptives", []),
            dataset_name=data.get("dataset_name", "Dataset"),
            options=data.get("options", {})
        )
        return Response(
            content=doc_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=batch_report.docx"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
