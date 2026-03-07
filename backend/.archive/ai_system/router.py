from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
from .coordinator import AIAnalysisCoordinator
from .docx_generator import AIAnalysisReportGenerator
from app.api.datasets import DATA_DIR, get_dataframe, _load_dataset_meta

router = APIRouter()
coordinator = AIAnalysisCoordinator()

class AnalyzeRequest(BaseModel):
    dataset_id: str

class RunRequest(BaseModel):
    dataset_id: str
    config: Dict[str, Any]
    selected_columns: Optional[List[str]] = None  # User's variable selection

class DownloadRequest(BaseModel):
    dataset_id: str
    results: Dict[str, Any]
    config: Dict[str, Any]

@router.post("/analyze")
async def analyze_initial(req: AnalyzeRequest):
    """
    Step 1: Scans the dataset and returns a Draft Plan (DraftConfig).
    """
    try:
        result = await coordinator.analyze_initial(req.dataset_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run")
async def run_analysis(req: RunRequest):
    """
    Step 2: Executes the confirmed plan.
    """
    try:
        results = await coordinator.run_analysis(req.dataset_id, req.config, req.selected_columns)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/download-report")
async def download_report(req: DownloadRequest):
    """
    Step 3: Generates and downloads DOCX report.
    """
    try:
        # Get dataset metadata
        meta = _load_dataset_meta(req.dataset_id)
        dataset_info = {
            "filename": meta.get("filename", "Unknown") if meta else "Unknown",
            "id": req.dataset_id
        }
        
        # Generate report
        generator = AIAnalysisReportGenerator(
            results=req.results,
            config=req.config,
            dataset_info=dataset_info
        )
        docx_bytes = generator.generate()
        
        # Return as downloadable file
        filename = f"analysis_report_{req.dataset_id[:8]}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run-with-script")
async def run_analysis_with_script(req: RunRequest):
    """
    NEW: Script-based transparent analysis.
    
    Returns:
        - results: statistical test results
        - audit_log: full transparency log
        - verification: anomaly detection results
        - script_code: reproducible Python script
    """
    try:
        result = await coordinator.run_analysis_with_script(
            req.dataset_id, 
            req.config, 
            req.selected_columns
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze-expert")
async def analyze_with_expert(req: AnalyzeRequest):
    """
    NEW: Advanced AI Expert Analysis
    
    Uses metadata extraction + LLM to:
    - Extract smart patterns (handles 10000×10000 tables)
    - Standardize column names
    - Recommend optimal design
    
    Returns:
        - metadata: extracted patterns
        - standardized_columns: cleaned names
        - design_recommendation: expert plan
    """
    try:
        result = await coordinator.analyze_with_ai_expert(req.dataset_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-diamag-analysis")
async def run_diamag_analysis(req: RunRequest):
    """
    DiaMag-Level Comprehensive Analysis.
    
    Features:
    - Kruskal-Wallis with epsilon² effect size
    - Pairwise Mann-Whitney with Holm correction and BF10
    - Responder analysis with NNT
    - Wilcoxon paired tests
    - LMM Time×Group interaction
    - AI-generated discussion and conclusions
    
    Config format:
        {
            "group_col": "Группа",
            "subject_col": "ID пациента",  # Optional, for LMM
            "endpoints": [
                {
                    "family_name": "UPDRS III",
                    "baseline_col": "УШОБП часть 3 V2",
                    "followup_cols": {"V3": "col_v3", "V6": "col_v6"},
                    "direction": "lower_is_better"
                }
            ],
            "responder_threshold": 0.20
        }
    """
    try:
        result = await coordinator.run_diamag_analysis(req.dataset_id, req.config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DiaMagDownloadRequest(BaseModel):
    dataset_id: str
    results: Dict[str, Any]
    config: Dict[str, Any]


@router.post("/download-diamag-report")
async def download_diamag_report(req: DiaMagDownloadRequest):
    """
    Download enhanced DiaMag-style DOCX report.
    
    Features:
    - Table of Contents
    - BF10 interpretation table
    - Responder summary table
    - LMM results table
    - Significance coloring
    - AI-generated discussion/conclusions
    """
    from .diamag_report import DiaMagReportGenerator
    
    try:
        generator = DiaMagReportGenerator(req.results, req.config)
        docx_bytes = generator.generate()
        
        filename = f"diamag_report_{req.dataset_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M')}.docx"
        
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
