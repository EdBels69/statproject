import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile

from app.api.datasets import DATA_DIR
from app.core.logging import logger
from app.core.paths import get_workspace_dir
from app.services.job_store import build_job_store
from app.core.pipeline import PipelineManager
from app.services.upload_service import create_ingest_job, ingest_saved_raw_to_parquet_job, save_upload_source


router = APIRouter(prefix="/datasets", tags=["datasets-v2"])

WORKSPACE_DIR = get_workspace_dir()
_job_store = build_job_store(WORKSPACE_DIR)


@router.post("/upload", response_model=Dict[str, Any])
async def upload_dataset_async(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    auto_clean: bool = Query(True),
    auto_impute: str = Query("simple"),
):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Файл не передан")

    ext = os.path.splitext(file.filename)[1].lower()
    supported = {".csv", ".xlsx", ".xls", ".json", ".xml", ".parquet"}
    if ext not in supported:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый формат: {ext}")

    meta = {
        "filename": file.filename,
        "content_type": getattr(file, "content_type", None),
        "auto_clean": bool(auto_clean),
        "auto_impute": str(auto_impute),
    }
    ids = await create_ingest_job(data_dir=DATA_DIR, job_store=_job_store, payload=meta)
    job_id = ids["job_id"]
    dataset_id = ids["dataset_id"]

    try:
        pipeline = PipelineManager(DATA_DIR)
        _job_store.update(job_id, status="running", stage="saving", progress=2, message="saving source")
        raw_path = await save_upload_source(pipeline, dataset_id, file)
    except Exception as e:
        _job_store.fail(job_id, stage="saving", error=str(e))
        raise HTTPException(status_code=400, detail=f"Не удалось сохранить файл: {str(e)}")

    original_filename = str(file.filename or "")
    try:
        await file.close()
    except Exception:
        pass

    async def run():
        await ingest_saved_raw_to_parquet_job(
            dataset_id=dataset_id,
            raw_path=raw_path,
            original_filename=original_filename,
            data_dir=DATA_DIR,
            job_store=_job_store,
            job_id=job_id,
        )

    background.add_task(run)
    return {"status": "queued", "job_id": job_id, "dataset_id": dataset_id, "filename": original_filename}


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job(job_id: str):
    try:
        return _job_store.get(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job не найден")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_jobs(dataset_id: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=200)):
    return _job_store.list(dataset_id=dataset_id, limit=limit)
