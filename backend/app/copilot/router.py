"""
Copilot API Router - Simple, chat-first endpoints.

Endpoints:
    POST /analyze - Start analysis from natural language
    POST /refine  - Refine existing analysis
    POST /report  - Generate DOCX report
    GET  /session/{id} - Get session state
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import os

from app.api.datasets import DATA_DIR, get_dataframe, _load_dataset_meta
from .engine import CopilotEngine
from .report import generate_report

router = APIRouter()
engine = CopilotEngine()


class AnalyzeRequest(BaseModel):
    """Request to start new analysis."""
    dataset_id: str
    request: str  # Natural language: "Compare groups by outcome..."
    model: Optional[str] = None  # Specific model ID (e.g. "google/gemini-2.5-flash")
    advanced: bool = False
    consent: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "dataset_id": "abc123",
                "request": "Сравни группы по исходу, проверь динамику лабораторных V1→V2, найди предикторы летальности",
                "model": "google/gemini-2.5-flash"
            }
        }


class RefineRequest(BaseModel):
    session_id: str
    refinement: str
    advanced: bool = False
    consent: bool = False


class ReportRequest(BaseModel):
    session_id: str
    include_code: bool = True
    include_interpretation: bool = True


from app.modules.ai_context import build_ai_context

def get_dataset_info(dataset_id: str) -> Dict[str, Any]:
    """Prepare dataset info for Copilot Engine."""
    try:
        dataset_meta = build_ai_context(dataset_id=dataset_id, base_dir=DATA_DIR, df=None)
    except Exception:
        dataset_meta = {}
    
    summary = dataset_meta.get("summary") or {}
    columns = [c.get("name") for c in dataset_meta.get("columns", []) if c.get("name")]
    
    return {
        "filename": dataset_meta.get("filename") or dataset_id,
        "n_rows": summary.get("n_rows"),
        "n_cols": summary.get("n_cols"),
        "columns": columns,
        "dataset_meta": dataset_meta
    }


@router.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """
    🎯 Main endpoint: Natural language → Statistical analysis.
    """
    # Get dataset path
    dataset_dir = os.path.join(DATA_DIR, req.dataset_id)
    parquet_path = os.path.join(dataset_dir, "processed", f"{req.dataset_id}.parquet")
    
    if not os.path.exists(parquet_path):
        raise HTTPException(404, f"Dataset {req.dataset_id} not found")

    if not req.advanced or not req.consent:
        raise HTTPException(400, "Codegen is available only in Advanced mode with explicit consent.")

    # Get metadata
    dataset_info = get_dataset_info(req.dataset_id)

    # Run analysis
    result = await engine.analyze(
        dataset_path=parquet_path,
        user_request=req.request,
        dataset_info=dataset_info,
        model_id=req.model,
        advanced=req.advanced
    )
    
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Analysis failed"))
    
    return result


@router.post("/plan")
async def create_plan(req: AnalyzeRequest):
    """
    📝 Stage 1: Create Analysis Plan (No Execution).
    """
    # Get dataset path
    dataset_dir = os.path.join(DATA_DIR, req.dataset_id)
    parquet_path = os.path.join(dataset_dir, "processed", f"{req.dataset_id}.parquet")
    
    if not os.path.exists(parquet_path):
        raise HTTPException(404, f"Dataset {req.dataset_id} not found")

    if not req.advanced or not req.consent:
        raise HTTPException(400, "Codegen planning is available only in Advanced mode with explicit consent.")

    # Get metadata
    dataset_info = get_dataset_info(req.dataset_id)
    
    import uuid
    session_id = str(uuid.uuid4())

    # Run planning
    result = await engine.create_plan(
        session_id=session_id,
        dataset_path=parquet_path,
        user_request=req.request,
        dataset_info=dataset_info,
        model_id=req.model,
        advanced=req.advanced
    )
    
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Planning failed"))
    
    return result


class ExecuteRequest(BaseModel):
    session_id: str
    plan_override: Optional[Dict[str, Any]] = None
    advanced: bool = False
    consent: bool = False


@router.post("/execute")
async def execute_plan(req: ExecuteRequest):
    """
    🚀 Stage 2: Execute Analysis Plan.
    """
    if not req.advanced or not req.consent:
        raise HTTPException(400, "Codegen execution is available only in Advanced mode with explicit consent.")

    result = await engine.execute_plan(
        session_id=req.session_id,
        plan_override=req.plan_override
    )
    
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Execution failed"))
        
    return result


from fastapi.responses import StreamingResponse
import asyncio

async def sse_generator(session_id: str, plan_override=None):
    """Generate SSE events from execute_plan_stream."""
    async for event in engine.execute_plan_stream(session_id, plan_override):
        event_type = event.get("type", "log")
        data = event.get("data", "")
        
        # Format as SSE
        if isinstance(data, dict):
            import json
            data = json.dumps(data, ensure_ascii=False, default=str)
        
        yield f"event: {event_type}\ndata: {data}\n\n"
        
        # Small delay to avoid overwhelming client
        await asyncio.sleep(0.01)


@router.post("/execute_stream")
async def execute_plan_stream(req: ExecuteRequest):
    """
    🚀 Stage 2: Execute Analysis Plan with STREAMING output.
    Returns Server-Sent Events (SSE) for real-time progress.
    """
    if not req.advanced or not req.consent:
        raise HTTPException(400, "Codegen execution is available only in Advanced mode with explicit consent.")

    return StreamingResponse(
        sse_generator(req.session_id, req.plan_override),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/refine")
async def refine(req: RefineRequest):
    """
    🔄 Refine existing analysis.
    
    Example:
    ```
    POST /api/v2/copilot/refine
    {
        "session_id": "xxx",
        "refinement": "Добавь ROC-анализ для CRP"
    }
    ```
    """
    if not req.advanced or not req.consent:
        raise HTTPException(400, "Codegen refinement is available only in Advanced mode with explicit consent.")

    result = await engine.refine(
        session_id=req.session_id,
        refinement_request=req.refinement
    )
    
    if not result["success"]:
        raise HTTPException(500, result.get("error", "Refinement failed"))
    
    return result


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    📋 Get session state for debugging/inspection.
    """
    session = engine.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@router.post("/report")
async def download_report(req: ReportRequest):
    """
    📄 Generate DOCX report from session results.
    """
    session = engine.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    try:
        docx_bytes = generate_report(
            results=session.get("results", {}),
            plan=session.get("plan", {}),
            code=session.get("code") if req.include_code else None,
            interpretation=session.get("interpretation") if req.include_interpretation else None,
            dataset_info=session.get("dataset_info")
        )
        
        filename = f"copilot_report_{req.session_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
        
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(500, f"Report generation failed: {e}")


@router.post("/report/pdf")
async def download_report_pdf(req: ReportRequest):
    """📄 Generate PDF report from session results."""
    from .pdf_exporter import docx_to_pdf
    
    session = engine.get_session(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    
    try:
        docx_bytes = generate_report(
            results=session.get("results", {}),
            plan=session.get("plan", {}),
            code=session.get("code") if req.include_code else None,
            interpretation=session.get("interpretation") if req.include_interpretation else None,
            dataset_info=session.get("dataset_info")
        )
        
        pdf_bytes = docx_to_pdf(docx_bytes)
        filename = f"copilot_report_{req.session_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(500, f"PDF generation failed: {e}")
