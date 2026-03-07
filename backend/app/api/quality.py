import os
import json
import pandas as pd
from fastapi import APIRouter, HTTPException
from typing import List

from app.modules.quality import (
    detect_constant_columns, 
    detect_near_constant_columns,
    calculate_skewness,
    detect_outliers_iqr,
    perform_auto_cleaning
)
from app.modules.parsers import get_dataframe
from app.api.datasets import DATA_DIR
from app.llm import scan_data_quality
from app.schemas.dataset import QualityReport
from app.core.pipeline import PipelineManager
from app.modules.semantics import rebuild_and_save_semantics
from app.modules.study_design import rebuild_and_save_study_design
from app.modules.delta_log import append_delta_log

router = APIRouter(prefix="/quality", tags=["quality"])

pipeline = PipelineManager(DATA_DIR)

def _sanitize_json(obj):
    if hasattr(obj, "item") and callable(getattr(obj, "item")):
        try:
            return _sanitize_json(obj.item())
        except Exception:
            return str(obj)

    if isinstance(obj, float):
        try:
            import math
            if math.isnan(obj) or math.isinf(obj):
                return None
        except Exception:
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [_sanitize_json(v) for v in obj]
    return obj

@router.get("/{dataset_id}/scan", response_model=QualityReport)
async def scan_dataset_quality(dataset_id: str):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
            
        # 1. Rule-based checks
        constant_cols = detect_constant_columns(df)
        near_constant = detect_near_constant_columns(df)
        outliers = detect_outliers_iqr(df)
        skewness = calculate_skewness(df)
        
        # 2. AI-based checks (Semantic)
        ai_issues = await scan_data_quality(df)
        
        # Combined issues list
        issues = []
        for col in constant_cols:
            issues.append({"column": col, "type": "constant", "severity": "high", "message": "Column has only one unique value."})
        for col, val in near_constant.items():
             issues.append({"column": col, "type": "near_constant", "severity": "medium", "message": f"Column is 95%+ constant (dominant: {val})"})
        for col, count in outliers.items():
            if count > 0:
                issues.append({"column": col, "type": "outliers", "severity": "low", "message": f"Detected {count} potential outliers (IQR method)."})
        
        for item in ai_issues:
            if not isinstance(item, dict):
                continue
            issues.append(
                {
                    "column": item.get("column"),
                    "type": item.get("issue_type") or "ai_issue",
                    "severity": item.get("severity", "low"),
                    "message": item.get("description") or "AI detected potential issue.",
                    "suggestion": item.get("suggestion"),
                }
            )
        
        return {
            "dataset_id": dataset_id,
            "issues": issues,
            "summary": "Scan complete."
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить проверку качества данных: {str(e)}")

@router.post("/{dataset_id}/clean")
async def auto_clean_dataset(dataset_id: str, strategy: str = "mean"):
    from fastapi.concurrency import run_in_threadpool

    try:
        df = await run_in_threadpool(get_dataframe, dataset_id, DATA_DIR)
        cleaned_df = await run_in_threadpool(perform_auto_cleaning, df, strategy)

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        cleaned_df = await run_in_threadpool(scanner.optimize_dtypes, cleaned_df)

        pipeline.create_processed_snapshot(
            dataset_id,
            cleaned_df,
            cleaning_log={"action": "quality_auto_clean", "strategy": strategy}
        )

        scan_result = await run_in_threadpool(scanner.scan_dataset, cleaned_df)
        scan_report = scan_result.get("scan_report") or {}
        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        pipeline.write_json_atomic(report_path, _sanitize_json(scan_report), allow_nan=False)

        rebuild_and_save_semantics(
            dataset_id=dataset_id,
            base_dir=DATA_DIR,
            scan_report=scan_report,
            source="auto",
        )
        rebuild_and_save_study_design(
            dataset_id=dataset_id,
            base_dir=DATA_DIR,
            scan_report=scan_report,
            source="auto",
        )

        append_delta_log(
            base_dir=DATA_DIR,
            dataset_id=dataset_id,
            action="quality_auto_clean",
            actor="auto",
            details={"strategy": strategy},
        )

        return {"status": "success", "message": f"Файл данных очищен (стратегия: {strategy}) и сохранён."}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить очистку: {str(e)}")
