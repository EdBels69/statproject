import os
import shutil
import uuid
from typing import Any, Dict, Optional

import aiofiles
import pandas as pd
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.logging import logger
from app.core.pipeline import PipelineManager
from app.modules.data_normalizer import DataNormalizer
from app.modules.parsers import parse_file
from app.modules.smart_scanner import SmartScanner
from app.services.job_store import JobStore


async def save_upload_source(pipeline: PipelineManager, dataset_id: str, file: UploadFile) -> str:
    raw_dir = pipeline.initialize_dataset(dataset_id)["source"]
    raw_path = os.path.join(raw_dir, "original.raw")

    meta = {
        "original_filename": file.filename,
        "content_type": getattr(file, "content_type", None),
    }
    meta_path = os.path.join(raw_dir, "meta.json")

    async with aiofiles.open(raw_path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            await out.write(chunk)

    pipeline.write_json_atomic(meta_path, meta, allow_nan=False)
    return raw_path


async def ingest_saved_raw_to_parquet_job(
    *,
    dataset_id: str,
    raw_path: str,
    original_filename: str,
    data_dir: str,
    job_store: JobStore,
    job_id: str,
    header_row: int = 0,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    pipeline = PipelineManager(str(data_dir))
    ds_dir = pipeline.get_dataset_dir(dataset_id)

    try:
        job_store.update(job_id, status="running", stage="parsing", progress=10, message="parsing")

        def parse_logic() -> pd.DataFrame:
            df, used_header = parse_file(
                raw_path,
                header_row=header_row,
                sheet_name=sheet_name,
                original_filename=original_filename,
            )
            return df, used_header

        df, used_header = await run_in_threadpool(parse_logic)

        job_store.update(job_id, stage="normalizing", progress=30, message="normalizing", extra={"header_row": used_header})
        normalizer = DataNormalizer()
        df, normalization = await run_in_threadpool(normalizer.normalize, df)

        job_store.update(job_id, stage="optimizing", progress=45, message="optimizing dtypes")
        scanner = SmartScanner()
        df = await run_in_threadpool(scanner.optimize_dtypes, df)

        job_store.update(job_id, stage="parquet", progress=65, message="writing parquet")
        parquet_path = await run_in_threadpool(
            lambda: pipeline.create_processed_snapshot(
                dataset_id,
                df,
                cleaning_log={"header_row": used_header, "normalization": normalization},
            )
        )

        job_store.update(job_id, stage="scan", progress=80, message="scanning")
        scan_result = await run_in_threadpool(scanner.scan_dataset, df)
        scan_report = scan_result.get("scan_report") or {}
        profile_data = scan_result.get("profile") or {}

        scan_path = os.path.join(ds_dir, "processed", "scan_report.json")
        await run_in_threadpool(lambda: pipeline.write_json_atomic(scan_path, scan_report, allow_nan=False))

        meta_path = os.path.join(ds_dir, "source", "meta.json")
        try:
            meta = {"header_row": used_header, "sheet_name": sheet_name, "original_filename": original_filename}
            await run_in_threadpool(lambda: pipeline.write_json_atomic(meta_path, meta, allow_nan=False))
        except Exception:
            pass

        artifacts = {
            "dataset_dir": ds_dir,
            "raw_path": raw_path,
            "parquet_path": parquet_path,
            "scan_report_path": scan_path,
        }
        job_store.complete(job_id, artifacts=artifacts)
        return {
            "status": "completed",
            "dataset_id": dataset_id,
            "filename": original_filename,
            "profile": profile_data,
            "job_id": job_id,
            "artifacts": artifacts,
        }
    except Exception as e:
        job_store.fail(job_id, stage=str(job_store.get(job_id).get("stage") or "failed"), error=str(e))
        shutil.rmtree(ds_dir, ignore_errors=True)
        raise


async def ingest_to_parquet_job(
    *,
    dataset_id: str,
    file: UploadFile,
    data_dir: str,
    job_store: JobStore,
    job_id: str,
    header_row: int = 0,
    sheet_name: Optional[str] = None,
) -> Dict[str, Any]:
    pipeline = PipelineManager(str(data_dir))
    ds_dir = pipeline.get_dataset_dir(dataset_id)

    try:
        job_store.update(job_id, status="running", stage="saving", progress=2, message="saving source")
        raw_path = await save_upload_source(pipeline, dataset_id, file)

        return await ingest_saved_raw_to_parquet_job(
            dataset_id=dataset_id,
            raw_path=raw_path,
            original_filename=str(file.filename or ""),
            data_dir=data_dir,
            job_store=job_store,
            job_id=job_id,
            header_row=header_row,
            sheet_name=sheet_name,
        )

    except Exception as e:
        job_store.fail(job_id, stage=str(job_store.get(job_id).get("stage") or "failed"), error=str(e))
        shutil.rmtree(ds_dir, ignore_errors=True)
        raise


async def create_ingest_job(
    *,
    data_dir: str,
    job_store: JobStore,
    dataset_id: Optional[str] = None,
    kind: str = "dataset_ingest",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    ds_id = dataset_id or str(uuid.uuid4())
    job = job_store.create(kind, dataset_id=ds_id, payload=payload)
    return {"job_id": job.id, "dataset_id": ds_id}
