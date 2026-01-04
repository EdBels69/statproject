import os
from fastapi import APIRouter, HTTPException
from typing import List

from app.modules.quality import (
    detect_constant_columns, 
    detect_near_constant_columns,
    calculate_skewness,
    detect_outliers_iqr,
    perform_auto_cleaning
)
from app.modules.parsers import get_dataset_path, get_dataframe, load_metadata, persist_metadata, invalidate_dataset_cache
from app.api.datasets import DATA_DIR
from app.llm import scan_data_quality
from app.schemas.dataset import QualityReport

router = APIRouter(prefix="/quality", tags=["quality"])

@router.get("/{dataset_id}/scan", response_model=QualityReport)
async def scan_dataset_quality(dataset_id: str):
    file_path, upload_dir = get_dataset_path(dataset_id, DATA_DIR)
    if not file_path:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
            
        # 1. Rule-based checks
        constant_cols = detect_constant_columns(df)
        near_constant = detect_near_constant_columns(df)
        outliers = detect_outliers_iqr(df)
        skewness = calculate_skewness(df)
        
        # 2. AI-based checks (Semantic)
        ai_report = await scan_data_quality(df)
        
        # Combined issues list
        issues = []
        for col in constant_cols:
            issues.append({"column": col, "type": "constant", "severity": "high", "message": "Column has only one unique value."})
        for col, val in near_constant.items():
             issues.append({"column": col, "type": "near_constant", "severity": "medium", "message": f"Column is 95%+ constant (dominant: {val})"})
        for col, count in outliers.items():
            if count > 0:
                issues.append({"column": col, "type": "outliers", "severity": "low", "message": f"Detected {count} potential outliers (IQR method)."})
        
        # Add AI issues
        issues.extend(ai_report.get("issues", []))
        
        return {
            "dataset_id": dataset_id,
            "issues": issues,
            "summary": ai_report.get("summary", "Scan complete.")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quality scan failed: {str(e)}")

@router.post("/{dataset_id}/clean")
async def auto_clean_dataset(dataset_id: str, strategy: str = "mean"):
    file_path, upload_dir = get_dataset_path(dataset_id, DATA_DIR)
    if not file_path:
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    try:
        df = get_dataframe(dataset_id, DATA_DIR, prefer_processed=False)
        cleaned_df = perform_auto_cleaning(df, method=strategy)
        
        # Save as processed
        processed_path = os.path.join(upload_dir, "processed.csv")
        cleaned_df.to_csv(processed_path, index=False)
        metadata = load_metadata(dataset_id, DATA_DIR)
        metadata.bump_modification()
        persist_metadata(dataset_id, DATA_DIR, metadata)
        invalidate_dataset_cache(dataset_id)

        return {"status": "success", "message": f"Dataset cleaned using {strategy} and saved as processed."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleaning failed: {str(e)}")
