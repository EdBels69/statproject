import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.api.datasets import get_dataset_path, parse_file
from app.schemas.dataset import QualityReport, QualityIssue
from app.llm import scan_data_quality

router = APIRouter()

import os

@router.post("/datasets/{dataset_id}/scan", response_model=QualityReport)
async def scan_dataset_quality(dataset_id: str):
    file_path, _ = get_dataset_path(dataset_id)
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset not found")
        
    try:
        # Load data using shared parser
        df, _ = parse_file(file_path, header_row=0)
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Failed to load dataset: {str(e)}")
    
    issues = []
    
    # 1. Rule-Based Checks (Pandas)
    
    # A. Missing Values
    for col in df.columns:
        missing_count = df[col].isna().sum()
        if missing_count > 0:
            pct = (missing_count / len(df)) * 100
            severity = "high" if pct > 20 else "medium"
            issues.append(QualityIssue(
                column=col,
                issue_type="missing",
                severity=severity,
                description=f"{int(missing_count)} missing values ({pct:.1f}%)",
                suggestion="Fill missing values or drop rows/column"
            ))
            
    # B. Duplicates
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        issues.append(QualityIssue(
            column=None,
            issue_type="duplicate",
            severity="medium",
            description=f"Found {int(dup_count)} exact duplicate rows",
            suggestion="Remove duplicate rows"
        ))
        
    # C. Outliers (Z-Score > 3) for numeric
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) > 10: # Only check if enough data
            z_scores = np.abs((col_data - col_data.mean()) / col_data.std())
            outliers = (z_scores > 3).sum()
            if outliers > 0:
                 issues.append(QualityIssue(
                    column=col,
                    issue_type="outlier",
                    severity="low",
                    description=f"Found {int(outliers)} outliers (Z > 3)",
                    suggestion="Check for data entry errors or apply winsorization"
                ))

    # 2. AI Semantic Check (LLM)
    # Prepare snippet for LLM
    head_csv = df.head(10).to_csv(index=False)
    # Prepare types info
    col_info = "\n".join([f"{col}: {df[col].dtype}" for col in df.columns])
    
    ai_issues_data = await scan_data_quality(head_csv, col_info)
    
    # Convert LLM dicts to Pydantic models
    for issue in ai_issues_data:
        try:
            # Map LLM output to our schema safely
            issues.append(QualityIssue(
                column=issue.get("column"),
                issue_type=issue.get("issue_type", "ai_finding"),
                severity=issue.get("severity", "medium"),
                description=issue.get("description", "Detected by AI"),
                suggestion=issue.get("suggestion", "Review manually")
            ))
        except:
            continue

    return QualityReport(
        row_count=len(df),
        issues=issues
    )
