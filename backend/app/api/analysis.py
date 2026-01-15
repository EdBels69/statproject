
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import os
import pandas as pd
from pydantic import BaseModel
import json
import uuid

from app.schemas.analysis import (
    AnalysisRequest, AnalysisResult, StatMethod, 
    ProtocolRequest, DesignRequest, BatchAnalysisRequest
)
from app.stats.registry import get_method, METHODS
from app.stats.engine import select_test, run_analysis
from app.modules.text_generator import TextGenerator
from app.core.pipeline import PipelineManager
from app.core.protocol_engine import ProtocolEngine
from app.modules.parsers import get_dataframe, get_dataset_path
from app.core.study_designer import StudyDesignEngine
from app.modules.reporting import generate_pdf_report, generate_protocol_pdf_report, generate_protocol_docx_report
from app.modules.docx_generator import create_results_document
from app.core.logging import logger

from app.api.datasets import DATA_DIR, parse_file

router = APIRouter()
pipeline = PipelineManager(DATA_DIR)
protocol_engine = ProtocolEngine(pipeline)


class ExportDocxRequest(BaseModel):
    results: Dict[str, Any]
    dataset_name: Optional[str] = None
    filename: Optional[str] = None

# --- Endpoints ---

@router.get("/templates", response_model=Dict[str, Any])
def list_design_templates(goal: Optional[str] = None):
    try:
        designer = StudyDesignEngine()
        return {"templates": designer.list_templates(goal=goal)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template listing failed: {str(e)}")

@router.post("/design", response_model=Dict[str, Any])
def suggest_design(req: DesignRequest):
    """
    Uses StudyDesignEngine to generate an Analysis Protocol based on user inputs.
    """
    try:
        metadata: Dict[str, Any] = {}
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
        protocol = designer.suggest_protocol(req.goal, req.variables, metadata, template_id=req.template_id)
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

@router.get("/protocol/report/{run_id}/html")
def get_protocol_report_html(run_id: str, dataset_id: str):
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


@router.get("/protocol/report/{run_id}/pdf")
def get_protocol_report_pdf(run_id: str, dataset_id: str):
    from fastapi.responses import Response

    pipeline = PipelineManager("workspace/datasets")
    try:
        res = pipeline.get_run_results(dataset_id, run_id)
        if not res:
            raise HTTPException(status_code=404, detail="Results not found")

        pdf_bytes = generate_protocol_pdf_report(res, dataset_name=f"Dataset {dataset_id[:5]}...")
        filename = f"protocol_report_{run_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF report generation failed: {str(e)}")

@router.get("/protocol/report/{run_id}/docx")
def get_protocol_report_docx(run_id: str, dataset_id: str):
    from fastapi.responses import Response

    pipeline = PipelineManager("workspace/datasets")
    try:
        res = pipeline.get_run_results(dataset_id, run_id)
        if not res:
            raise HTTPException(status_code=404, detail="Results not found")

        docx_bytes = generate_protocol_docx_report(res, dataset_name=f"Dataset {dataset_id[:5]}...")
        filename = f"protocol_report_{run_id}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DOCX report generation failed: {str(e)}")


@router.post("/export/docx")
async def export_docx(request: ExportDocxRequest):
    from fastapi.responses import StreamingResponse

    try:
        buffer = create_results_document(request.results, dataset_name=request.dataset_name)
        filename = request.filename or "results.docx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DOCX export failed: {str(e)}")

@router.post("/protocol/run")
async def run_protocol_api(request: ProtocolRequest):
    """
    Executes a multi-step analysis protocol.
    Returns the run_id (analysis container ID).
    """
    try:
        # Load Data using centralized helper (Processed > Raw)
        df = get_dataframe(request.dataset_id, DATA_DIR)
        
        # Run Engine with alpha parameter
        run_id = protocol_engine.execute_protocol(request.dataset_id, df, request.protocol, alpha=request.alpha)
        
        return {"status": "success", "run_id": run_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Protocol execution failed: {str(e)}")

@router.post("/run", response_model=AnalysisResult)
async def run_method_api(request: AnalysisRequest):
    from fastapi.concurrency import run_in_threadpool
    
    # 1. Load Data (async via threadpool)
    async def load_data():
        return get_dataframe(request.dataset_id, DATA_DIR)
    
    df = await run_in_threadpool(load_data)
    
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

    # 3. Run (async via threadpool for CPU-bound operations)
    async def execute_analysis():
        results = run_analysis(df, method_id, col_a, col_b, is_paired=request.is_paired)
        
        # Build AnalysisResult
        method_info = get_method(method_id)
        
        res = AnalysisResult(
            method=method_info,
            p_value=results["p_value"],
            effect_size=results.get("effect_size"),
            effect_size_name=results.get("effect_size_name"),
            effect_size_ci_lower=results.get("effect_size_ci_lower"),
            effect_size_ci_upper=results.get("effect_size_ci_upper"),
            power=results.get("power"),
            bf10=results.get("bf10"),
            stat_value=results["stat_value"],
            significant=results["significant"],
            groups=results.get("groups"),
            plot_data=results.get("plot_data"),
            plot_stats=results.get("plot_stats"),
            conclusion=""
        )
        return res
    
    try:
        res = await run_in_threadpool(execute_analysis)
        
        # AI Conclusion (already async)
        ai_conclusion = await get_ai_conclusion(res)
        res.conclusion = ai_conclusion
        return res
    except Exception as e:
        logger.error(f"Analysis execution failed: {e}", exc_info=True)
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
    from app.modules.reporting import render_report
    
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found or file missing")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dataset load failed: {str(e)}")

    dataset_name = f"Dataset {dataset_id[:8]}"
    meta_path = os.path.join(DATA_DIR, dataset_id, "source", "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
                dataset_name = meta.get("original_filename") or dataset_name
        except Exception:
            pass
    
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
        effect_size=res.get("effect_size"),
        effect_size_name=res.get("effect_size_name"),
        effect_size_ci_lower=res.get("effect_size_ci_lower"),
        effect_size_ci_upper=res.get("effect_size_ci_upper"),
        power=res.get("power"),
        bf10=res.get("bf10"),
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
    html_content = render_report(analysis_result, target_col, group_col, dataset_name=dataset_name)
    
    return HTMLResponse(content=html_content)


@router.get("/report/{dataset_id}/pdf")
async def download_report_pdf(
    dataset_id: str,
    target_col: str,
    group_col: str,
    method_id: str = None
):
    from fastapi.responses import Response

    try:
        df = get_dataframe(dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found or file missing")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Dataset load failed: {str(e)}")

    col_a = target_col
    col_b = group_col

    if not method_id:
        types = {c: ("numeric" if pd.api.types.is_numeric_dtype(df[c]) else "categorical") for c in [col_a, col_b]}
        method_id = select_test(df, col_a, col_b, types)

    if not method_id:
        raise HTTPException(status_code=400, detail="Could not determine method for report.")

    try:
        res = run_analysis(df, method_id, col_a, col_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    method_info = get_method(method_id)
    conclusion = f"Statistically {'significant' if res['significant'] else 'insignificant'} difference found (p={res['p_value']:.4f})."

    analysis_result = AnalysisResult(
        method=method_info,
        p_value=res["p_value"],
        effect_size=res.get("effect_size"),
        effect_size_name=res.get("effect_size_name"),
        effect_size_ci_lower=res.get("effect_size_ci_lower"),
        effect_size_ci_upper=res.get("effect_size_ci_upper"),
        power=res.get("power"),
        bf10=res.get("bf10"),
        stat_value=res["stat_value"],
        significant=res["significant"],
        groups=res.get("groups"),
        plot_data=res.get("plot_data"),
        plot_stats=res.get("plot_stats"),
        conclusion=conclusion
    )

    from app.core.config import settings
    if settings.GLM_ENABLED and settings.GLM_API_KEY:
        from app.llm import get_ai_conclusion
        try:
            ai_text = await get_ai_conclusion(analysis_result)
            if ai_text:
                analysis_result.conclusion = ai_text
        except Exception as e:
            logger.warning(f"AI Enhancement failed: {e}", exc_info=True)

    pdf_bytes = generate_pdf_report(
        analysis_result.model_dump(),
        {"target": target_col, "group": group_col},
        dataset_id
    )

    filename = f"report_{dataset_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


class PdfExportRequest(BaseModel):
    results: Dict[str, Any]
    variables: Dict[str, Any]
    dataset_id: str


@router.post("/report/pdf")
async def export_report_pdf(req: PdfExportRequest):
    from fastapi.responses import Response

    pdf_bytes = generate_pdf_report(req.results, req.variables, req.dataset_id)
    filename = f"report_{req.dataset_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

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
    from fastapi.concurrency import run_in_threadpool
    
    # 1. Load Data (async via threadpool)
    async def load_batch_data():
        return get_dataframe(request.dataset_id, DATA_DIR)
    
    df = await run_in_threadpool(load_batch_data)

    # 2. Compute Descriptives (async via threadpool)
    async def compute_descriptives_async():
        from app.stats.engine import compute_descriptive_compare
        
        descriptives = []
        
        for col in request.target_columns:
            if col not in df.columns: continue
            
            # Get raw stats (returns dict keyed by group -> {mean, count...})
            raw_stats = compute_descriptive_compare(df, col, request.group_column)
            
            # Convert to DescriptiveStat objects
            for grp, stats in raw_stats.items():
                if grp == "overall" and len(raw_stats) > 1: continue 
                
                if not isinstance(stats, dict): continue
                
                ds = DescriptiveStat(
                    variable=col,
                    group=str(grp),
                    count=stats.get("count", 0),
                    missing=stats.get("missing"),
                    mean=stats.get("mean"),
                    median=stats.get("median"),
                    mode=stats.get("mode"),
                    sd=stats.get("std"),
                    se=stats.get("se"),
                    variance=stats.get("variance"),
                    range=stats.get("range"),
                    iqr=stats.get("iqr"),
                    skewness=stats.get("skewness"),
                    kurtosis=stats.get("kurtosis"),
                    ci_95_low=stats.get("ci_95_low"),
                    ci_95_high=stats.get("ci_95_high"),
                    shapiro_w=stats.get("shapiro_w"),
                    shapiro_p=stats.get("shapiro_p"),
                    is_normal=(stats.get("shapiro_p") is not None and stats.get("shapiro_p") >= 0.05)
                )
                descriptives.append(ds)
        return descriptives
    
    descriptives = await run_in_threadpool(compute_descriptives_async)
    
    # Sanitize Descriptives
    descriptives = _sanitize(descriptives)
    
    # 3. Running Hypothesis Tests (async via threadpool)
    async def run_tests_async():
        results = {}
        group_col = request.group_column
        
        # Pre-calculate types for test selection
        if not isinstance(df[group_col].dtype, pd.CategoricalDtype) and df[group_col].nunique() < 10:
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
                # Run with alpha parameter
                res = run_analysis(df, method_id, col, group_col, alpha=request.alpha)
                
                # SANITIZE RESULT
                res = _sanitize(res)
                
                # Format
                method_info = get_method(method_id)
                conclusion = f"P={res.get('p_value'):.4f}" if res.get('p_value') is not None else "P=N/A"
                
                result_obj = AnalysisResult(
                    method=method_info,
                    p_value=res.get("p_value"),
                    effect_size=res.get("effect_size"),
                    effect_size_name=res.get("effect_size_name"),
                    effect_size_ci_lower=res.get("effect_size_ci_lower"),
                    effect_size_ci_upper=res.get("effect_size_ci_upper"),
                    power=res.get("power"),
                    bf10=res.get("bf10"),
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
        return results
    
    results = await run_in_threadpool(run_tests_async)

    return BatchAnalysisResponse(descriptives=descriptives, results=results)
