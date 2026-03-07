"""
DataQualityGate — multi-step data cleaning pipeline with changelog.

Each step is atomic, logged, and produces a verifiable artifact.
The gate blocks analysis if quality score is below threshold.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CleaningStep:
    """One atomic cleaning operation."""
    action: str
    details: Dict[str, Any] = field(default_factory=dict)
    rows_before: int = 0
    rows_after: int = 0
    cols_affected: List[str] = field(default_factory=list)
    reversible: bool = True


@dataclass
class ColumnQuality:
    """Quality assessment for a single column."""
    name: str
    dtype_detected: str
    dtype_confidence: float  # 0.0-1.0
    missing_ratio: float
    unique_ratio: float
    quality_score: float  # 0.0-1.0
    issues: List[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """Full result of the quality gate pipeline."""
    df_clean: pd.DataFrame
    is_ready: bool
    overall_score: float
    column_quality: List[ColumnQuality]
    issues: List[str]
    warnings: List[str]
    cleaning_log: List[Dict[str, Any]]
    cleaning_plan: List[Dict[str, Any]]
    data_contract: Dict[str, Any]
    rows_original: int
    rows_final: int
    cols_original: int
    cols_final: int


# ---------------------------------------------------------------------------
# Quality scoring
# ---------------------------------------------------------------------------

def _score_column(s: pd.Series, name: str) -> ColumnQuality:
    """Compute quality score for a single column."""
    n = len(s)
    missing = int(s.isna().sum())
    missing_ratio = missing / max(1, n)
    unique = int(s.nunique(dropna=True))
    unique_ratio = unique / max(1, n - missing) if (n - missing) > 0 else 0.0

    issues: List[str] = []
    dtype_confidence = 1.0

    # Detect dtype
    if pd.api.types.is_numeric_dtype(s.dtype):
        dtype_detected = "numeric"
    elif pd.api.types.is_bool_dtype(s.dtype):
        dtype_detected = "boolean"
    elif pd.api.types.is_datetime64_any_dtype(s.dtype):
        dtype_detected = "datetime"
    else:
        dtype_detected = "categorical"
        # Check for mixed types
        non_null = s.dropna()
        if not non_null.empty:
            numeric_count = sum(1 for v in non_null.head(200).astype(str)
                              if _looks_numeric(str(v)))
            text_count = len(non_null.head(200)) - numeric_count
            if 0 < numeric_count < text_count and numeric_count > 3:
                issues.append("mixed_types: column contains both numeric and text values")
                dtype_confidence = 0.5

    # Missing data assessment
    if missing_ratio > 0.5:
        issues.append(f"high_missing: {missing_ratio:.0%} values are missing")
    elif missing_ratio > 0.2:
        issues.append(f"moderate_missing: {missing_ratio:.0%} values are missing")

    # Constant column
    if unique <= 1 and (n - missing) > 0:
        issues.append("constant: column has only one unique value")

    # Near-constant
    if unique == 2 and (n - missing) > 10:
        counts = s.value_counts(dropna=True)
        if not counts.empty and counts.iloc[0] / max(1, counts.sum()) > 0.98:
            issues.append("near_constant: >98% values are the same")

    # Quality score: penalize missing, mixed types, constants
    score = 1.0
    score -= missing_ratio * 0.4
    score -= (1.0 - dtype_confidence) * 0.3
    if unique <= 1 and (n - missing) > 0:
        score -= 0.3
    score = max(0.0, min(1.0, score))

    return ColumnQuality(
        name=name,
        dtype_detected=dtype_detected,
        dtype_confidence=dtype_confidence,
        missing_ratio=missing_ratio,
        unique_ratio=unique_ratio,
        quality_score=score,
        issues=issues,
    )


def _looks_numeric(s: str) -> bool:
    s = s.strip().replace(",", ".").replace(" ", "").replace("\u00a0", "")
    if s in ("", "-", "+", ".", ","):
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Cleaning operations
# ---------------------------------------------------------------------------

def _remove_duplicate_rows(df: pd.DataFrame, log: List[Dict]) -> pd.DataFrame:
    """Remove exact duplicate rows."""
    n_before = len(df)
    df = df.drop_duplicates()
    n_removed = n_before - len(df)
    if n_removed > 0:
        log.append(CleaningStep(
            action="remove_duplicates",
            details={"rows_removed": n_removed},
            rows_before=n_before,
            rows_after=len(df),
        ).__dict__)
    return df


def _handle_missing_numeric(df: pd.DataFrame, log: List[Dict], strategy: str = "median") -> pd.DataFrame:
    """Fill missing numeric values with median/mean."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    filled_cols: Dict[str, int] = {}

    for col in numeric_cols:
        n_missing = int(df[col].isna().sum())
        if n_missing == 0:
            continue

        total = len(df)
        ratio = n_missing / max(1, total)

        # Don't impute if too many missing (>60%)
        if ratio > 0.6:
            continue

        if strategy == "median":
            fill_val = df[col].median()
        elif strategy == "mean":
            fill_val = df[col].mean()
        else:
            fill_val = df[col].median()

        if pd.notna(fill_val):
            df[col] = df[col].fillna(fill_val)
            filled_cols[col] = n_missing

    if filled_cols:
        log.append(CleaningStep(
            action="impute_missing_numeric",
            details={
                "strategy": strategy,
                "columns": filled_cols,
                "total_filled": sum(filled_cols.values()),
            },
            rows_before=len(df),
            rows_after=len(df),
            cols_affected=list(filled_cols.keys()),
        ).__dict__)

    return df


def _handle_missing_categorical(df: pd.DataFrame, log: List[Dict]) -> pd.DataFrame:
    """Fill missing categorical values or leave as-is based on ratio."""
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    filled_cols: Dict[str, int] = {}

    for col in cat_cols:
        n_missing = int(df[col].isna().sum())
        ratio = n_missing / max(1, len(df))

        # Only fill if < 20% missing  
        if n_missing == 0 or ratio > 0.2:
            continue

        mode = df[col].mode()
        if not mode.empty:
            df[col] = df[col].fillna(mode.iloc[0])
            filled_cols[col] = n_missing

    if filled_cols:
        log.append(CleaningStep(
            action="impute_missing_categorical",
            details={
                "strategy": "mode",
                "columns": filled_cols,
            },
            rows_before=len(df),
            rows_after=len(df),
            cols_affected=list(filled_cols.keys()),
        ).__dict__)

    return df


def _detect_and_handle_outliers(
    df: pd.DataFrame,
    log: List[Dict],
    *,
    policy: str = "flag",
    iqr_multiplier: float = 1.5,
) -> pd.DataFrame:
    """Detect outliers using IQR. Policy: 'flag' (add metadata), 'winsorize', 'remove'."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    outlier_summary: Dict[str, Dict[str, Any]] = {}

    for col in numeric_cols:
        s = df[col].dropna()
        if len(s) < 10:
            continue

        q1 = s.quantile(0.25)
        q3 = s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue

        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr
        mask = (df[col] < lower) | (df[col] > upper)
        n_outliers = int(mask.sum())

        if n_outliers == 0:
            continue

        outlier_summary[col] = {
            "count": n_outliers,
            "lower_bound": round(float(lower), 4),
            "upper_bound": round(float(upper), 4),
            "policy_applied": policy,
        }

        if policy == "winsorize":
            df.loc[df[col] < lower, col] = lower
            df.loc[df[col] > upper, col] = upper
        elif policy == "remove":
            df = df[~mask]

    if outlier_summary:
        log.append(CleaningStep(
            action="outlier_detection",
            details={
                "method": "IQR",
                "iqr_multiplier": iqr_multiplier,
                "policy": policy,
                "columns": outlier_summary,
                "total_outliers": sum(v["count"] for v in outlier_summary.values()),
            },
            rows_before=len(df) + (sum(v["count"] for v in outlier_summary.values()) if policy == "remove" else 0),
            rows_after=len(df),
            cols_affected=list(outlier_summary.keys()),
        ).__dict__)

    return df


def _build_data_contract(df: pd.DataFrame, column_quality: List[ColumnQuality]) -> Dict[str, Any]:
    """Build a data_contract.json — canonical schema per column."""
    columns: Dict[str, Any] = {}

    for cq in column_quality:
        col = cq.name
        if col not in df.columns:
            continue
        s = df[col]

        contract: Dict[str, Any] = {
            "canonical_name": col,
            "dtype": cq.dtype_detected,
            "dtype_confidence": round(cq.dtype_confidence, 2),
            "quality_score": round(cq.quality_score, 2),
            "missing_policy": "impute_median" if cq.dtype_detected == "numeric" and cq.missing_ratio < 0.3 else (
                "impute_mode" if cq.dtype_detected == "categorical" and cq.missing_ratio < 0.2 else "keep_as_is"
            ),
            "n_unique": int(s.nunique(dropna=True)),
            "n_missing": int(s.isna().sum()),
            "missing_ratio": round(cq.missing_ratio, 4),
        }

        if cq.dtype_detected == "numeric":
            non_null = s.dropna()
            if not non_null.empty:
                contract["min"] = round(float(non_null.min()), 4)
                contract["max"] = round(float(non_null.max()), 4)
                contract["mean"] = round(float(non_null.mean()), 4)
                contract["median"] = round(float(non_null.median()), 4)
        elif cq.dtype_detected == "categorical":
            top_values = s.value_counts(dropna=True).head(10)
            contract["top_values"] = {str(k): int(v) for k, v in top_values.items()}

        if cq.issues:
            contract["issues"] = cq.issues

        columns[col] = contract

    return {
        "schema": "clinimetria.data_contract",
        "version": 1,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "n_rows": len(df),
        "n_columns": len(df.columns),
        "columns": columns,
    }


# ---------------------------------------------------------------------------
# Main gate
# ---------------------------------------------------------------------------

class DataQualityGate:
    """
    Multi-step data cleaning pipeline with quality scoring and changelog.
    Each step is atomic, logged, and produces a verifiable artifact.
    """

    def __init__(
        self,
        *,
        min_quality_score: float = 0.3,
        max_missing_threshold: float = 0.7,
        imputation_strategy: str = "median",
        outlier_policy: str = "flag",
        outlier_iqr_multiplier: float = 1.5,
    ):
        self.min_quality_score = min_quality_score
        self.max_missing_threshold = max_missing_threshold
        self.imputation_strategy = imputation_strategy
        self.outlier_policy = outlier_policy
        self.outlier_iqr_multiplier = outlier_iqr_multiplier

    def run(self, df: pd.DataFrame) -> QualityReport:
        """Execute the full quality gate pipeline."""
        cleaning_log: List[Dict[str, Any]] = []
        cleaning_plan: List[Dict[str, Any]] = []
        issues: List[str] = []
        warnings: List[str] = []

        rows_original = len(df)
        cols_original = len(df.columns)
        out = df.copy()

        # Step 1: Profile — assess raw quality
        raw_quality = [_score_column(out[col], str(col)) for col in out.columns]
        cleaning_plan.append({
            "step": 1,
            "action": "profile",
            "description": "Assess raw data quality per column",
        })

        # Step 2: Remove duplicates
        cleaning_plan.append({
            "step": 2,
            "action": "remove_duplicates",
            "description": "Remove exact duplicate rows",
        })
        out = _remove_duplicate_rows(out, cleaning_log)

        # Step 3: Drop columns with too many missing values
        cols_to_drop = []
        for cq in raw_quality:
            if cq.missing_ratio > self.max_missing_threshold:
                cols_to_drop.append(cq.name)
        if cols_to_drop:
            existing = [c for c in cols_to_drop if c in out.columns]
            if existing:
                out = out.drop(columns=existing)
                cleaning_log.append(CleaningStep(
                    action="drop_high_missing_columns",
                    details={
                        "threshold": self.max_missing_threshold,
                        "dropped": existing,
                    },
                    rows_before=len(out),
                    rows_after=len(out),
                    cols_affected=existing,
                ).__dict__)

        cleaning_plan.append({
            "step": 3,
            "action": "drop_high_missing_columns",
            "description": f"Drop columns with >{self.max_missing_threshold:.0%} missing",
            "affected": cols_to_drop,
        })

        # Step 4: Handle missing numeric values
        cleaning_plan.append({
            "step": 4,
            "action": "impute_numeric",
            "description": f"Impute missing numeric values (strategy: {self.imputation_strategy})",
        })
        out = _handle_missing_numeric(out, cleaning_log, strategy=self.imputation_strategy)

        # Step 5: Handle missing categorical values
        cleaning_plan.append({
            "step": 5,
            "action": "impute_categorical",
            "description": "Impute missing categorical values (mode)",
        })
        out = _handle_missing_categorical(out, cleaning_log)

        # Step 6: Outlier detection
        cleaning_plan.append({
            "step": 6,
            "action": "outlier_detection",
            "description": f"Detect outliers (IQR × {self.outlier_iqr_multiplier}, policy: {self.outlier_policy})",
        })
        out = _detect_and_handle_outliers(
            out, cleaning_log,
            policy=self.outlier_policy,
            iqr_multiplier=self.outlier_iqr_multiplier,
        )

        # Step 7: Final quality assessment
        final_quality = [_score_column(out[col], str(col)) for col in out.columns]
        overall_score = (
            sum(cq.quality_score for cq in final_quality) / max(1, len(final_quality))
        )

        # Collect issues
        for cq in final_quality:
            if cq.quality_score < self.min_quality_score:
                issues.append(f"Column '{cq.name}' quality score {cq.quality_score:.2f} < threshold {self.min_quality_score}")
            for issue in cq.issues:
                warnings.append(f"[{cq.name}] {issue}")

        is_ready = len(issues) == 0 and overall_score >= self.min_quality_score

        # Build data contract
        data_contract = _build_data_contract(out, final_quality)

        return QualityReport(
            df_clean=out,
            is_ready=is_ready,
            overall_score=overall_score,
            column_quality=final_quality,
            issues=issues,
            warnings=warnings,
            cleaning_log=cleaning_log,
            cleaning_plan=cleaning_plan,
            data_contract=data_contract,
            rows_original=rows_original,
            rows_final=len(out),
            cols_original=cols_original,
            cols_final=len(out.columns),
        )

    def to_cleaning_log_json(self, report: QualityReport) -> Dict[str, Any]:
        """Serialize the cleaning log as a JSON-compatible dict."""
        return {
            "schema": "clinimetria.cleaning_log",
            "version": 1,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "rows_original": report.rows_original,
            "rows_final": report.rows_final,
            "cols_original": report.cols_original,
            "cols_final": report.cols_final,
            "overall_quality_score": round(report.overall_score, 3),
            "is_ready": report.is_ready,
            "steps": report.cleaning_log,
            "issues": report.issues,
            "warnings": report.warnings[:20],
        }

    def to_cleaning_plan_json(self, report: QualityReport) -> Dict[str, Any]:
        """Serialize the cleaning plan as a JSON-compatible dict."""
        return {
            "schema": "clinimetria.cleaning_plan",
            "version": 1,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "config": {
                "min_quality_score": self.min_quality_score,
                "max_missing_threshold": self.max_missing_threshold,
                "imputation_strategy": self.imputation_strategy,
                "outlier_policy": self.outlier_policy,
                "outlier_iqr_multiplier": self.outlier_iqr_multiplier,
            },
            "steps": report.cleaning_plan,
        }


def compute_analysis_set_hash(df: pd.DataFrame) -> str:
    """Compute a deterministic SHA256 hash of a DataFrame for cohort freeze."""
    buf = df.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(buf).hexdigest()
