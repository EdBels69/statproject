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


def _normalize_auto_impute(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"0", "false", "no", "off", "none", "disabled"}:
        return "none"
    if s in {"mice", "iterative"}:
        return "mice"
    return "simple"


def _auto_clean_and_impute(
    df: pd.DataFrame,
    scan_report: Dict[str, Any],
    *,
    auto_clean: bool,
    auto_impute: str,
) -> tuple[pd.DataFrame, Dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    stats = {
        "auto_clean": bool(auto_clean),
        "auto_impute": str(auto_impute),
        "actions": actions,
    }

    if not auto_clean or not isinstance(df, pd.DataFrame) or df.empty:
        return df, stats

    cols = scan_report.get("columns") if isinstance(scan_report, dict) else None
    cols = cols if isinstance(cols, dict) else {}
    for col, rep in cols.items():
        if col not in df.columns or not isinstance(rep, dict):
            continue
        if rep.get("mixed_type_suspected") is True:
            pct = rep.get("numeric_convertible_percent")
            try:
                pct_f = float(pct)
            except Exception:
                pct_f = None
            if pct_f is not None and pct_f >= 90:
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                    actions.append({"type": "to_numeric", "column": str(col)})
                except Exception:
                    pass

    missing_report = scan_report.get("missing_report") if isinstance(scan_report, dict) else None
    by_col = missing_report.get("by_column") if isinstance(missing_report, dict) else None
    if isinstance(by_col, list) and by_col:
        for row in by_col:
            if not isinstance(row, dict):
                continue
            col = row.get("column")
            if not isinstance(col, str) or col not in df.columns:
                continue
            try:
                missing_percent = float(row.get("missing_percent") or 0.0)
            except Exception:
                missing_percent = 0.0
            if missing_percent <= 0:
                continue

            s = df[col]
            try:
                if not bool(s.isna().any()):
                    continue
            except Exception:
                continue

            if pd.api.types.is_numeric_dtype(s.dtype):
                if missing_percent <= 20.0:
                    try:
                        v = s.median(skipna=True)
                        if v is not None and pd.notna(v):
                            df[col] = s.fillna(v)
                            actions.append({"type": "fill_median", "column": col})
                    except Exception:
                        pass
                continue

            if missing_percent <= 10.0:
                try:
                    mode = s.mode(dropna=True)
                    if mode is not None and len(mode) > 0:
                        v = mode.iloc[0]
                        if v is not None and pd.notna(v):
                            df[col] = s.fillna(v)
                            actions.append({"type": "fill_mode", "column": col})
                except Exception:
                    pass

    if auto_impute == "mice":
        try:
            from sklearn.experimental import enable_iterative_imputer  # noqa: F401
            from sklearn.impute import IterativeImputer
        except Exception:
            return df, stats

        n_rows = int(len(df))
        if n_rows <= 20000:
            numeric_cols: list[str] = []
            for c in df.columns:
                try:
                    if pd.api.types.is_numeric_dtype(df[c].dtype) and bool(df[c].isna().any()):
                        numeric_cols.append(str(c))
                except Exception:
                    continue

            numeric_cols = numeric_cols[:25]
            if len(numeric_cols) >= 2:
                try:
                    numeric_df = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
                    if bool(numeric_df.isna().any().any()):
                        imputer = IterativeImputer(
                            max_iter=10,
                            random_state=42,
                            sample_posterior=False,
                            skip_complete=True,
                        )
                        imputed = imputer.fit_transform(numeric_df)
                        df.loc[:, numeric_cols] = imputed
                        actions.append({"type": "mice", "columns": numeric_cols, "max_iter": 10})
                except Exception:
                    pass

    return df, stats


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
        job = job_store.get(job_id)
        payload = job.get("payload") if isinstance(job, dict) else None
        payload = payload if isinstance(payload, dict) else {}
        auto_clean = payload.get("auto_clean")
        auto_clean = True if auto_clean is None else bool(auto_clean)
        auto_impute = _normalize_auto_impute(payload.get("auto_impute"))

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

        job_store.update(job_id, stage="auto_clean", progress=55, message="auto cleaning")
        scan_before = await run_in_threadpool(scanner.scan_dataset, df)
        scan_report_before = scan_before.get("scan_report") or {}

        df, auto_stats = await run_in_threadpool(
            lambda: _auto_clean_and_impute(
                df,
                scan_report_before,
                auto_clean=auto_clean,
                auto_impute=auto_impute,
            )
        )

        if auto_stats.get("actions"):
            df = await run_in_threadpool(scanner.optimize_dtypes, df)

        job_store.update(job_id, stage="parquet", progress=70, message="writing parquet")
        parquet_path = await run_in_threadpool(
            lambda: pipeline.create_processed_snapshot(
                dataset_id,
                df,
                cleaning_log={"header_row": used_header, "normalization": normalization, "auto": auto_stats},
            )
        )

        job_store.update(job_id, stage="scan", progress=80, message="scanning")
        if auto_stats.get("actions"):
            scan_result = await run_in_threadpool(scanner.scan_dataset, df)
        else:
            scan_result = scan_before
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
