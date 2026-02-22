import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


CLEANING_RUN_VERSION = 1
MISSING_STRING_TOKENS = {
    "",
    "na",
    "n/a",
    "none",
    "null",
    "nan",
    "nat",
    "missing",
}


def _series_missing_mask(series: pd.Series) -> pd.Series:
    mask = series.isna()
    try:
        if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
            text = series.astype(str).str.strip().str.lower()
            mask = mask | text.isin(MISSING_STRING_TOKENS)
    except Exception:
        pass
    return mask


def dataframe_fingerprint(df: pd.DataFrame) -> str:
    columns = [str(c) for c in df.columns]
    dtypes = {str(c): str(df[c].dtype) for c in df.columns}
    missing_counts = {str(c): int(_series_missing_mask(df[c]).sum()) for c in df.columns}
    payload = {
        "n_rows": int(len(df)),
        "n_cols": int(len(columns)),
        "columns": columns,
        "dtypes": dtypes,
        "missing_counts": missing_counts,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_missingness_summary(df: pd.DataFrame, max_columns: int = 300) -> Dict[str, Any]:
    n_rows = int(len(df))
    n_cols = int(len(df.columns))
    total_cells = int(n_rows * n_cols)

    by_column: List[Dict[str, Any]] = []
    missing_total = 0
    for col in df.columns:
        col_name = str(col)
        mask = _series_missing_mask(df[col])
        missing_count = int(mask.sum())
        missing_total += missing_count
        pct = (missing_count / float(max(1, n_rows))) * 100.0 if n_rows else 0.0
        by_column.append(
            {
                "column": col_name,
                "missing_count": missing_count,
                "missing_percent": float(round(pct, 4)),
            }
        )

    by_column.sort(key=lambda x: (int(x.get("missing_count") or 0), str(x.get("column") or "")), reverse=True)
    if max_columns > 0:
        by_column = by_column[: max_columns]

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "total_cells": total_cells,
        "missing_cells": int(missing_total),
        "missing_rate": float(round((missing_total / float(max(1, total_cells))) * 100.0, 4)) if total_cells else 0.0,
        "by_column": by_column,
    }


def _extract_operations(cleaning_log: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    operations: List[Dict[str, Any]] = []
    parameters: Dict[str, Any] = {}

    if not isinstance(cleaning_log, dict):
        return operations, parameters

    if isinstance(cleaning_log.get("operations"), list):
        for idx, item in enumerate(cleaning_log.get("operations") or []):
            if not isinstance(item, dict):
                continue
            op_type = str(item.get("type") or item.get("action") or f"operation_{idx + 1}").strip()
            if not op_type:
                continue
            entry = dict(item)
            entry["type"] = op_type
            operations.append(entry)
    elif isinstance(cleaning_log.get("auto"), dict):
        auto = cleaning_log.get("auto") or {}
        actions = auto.get("actions")
        if isinstance(actions, list):
            for idx, item in enumerate(actions):
                if isinstance(item, dict):
                    op_type = str(item.get("type") or item.get("action") or f"auto_{idx + 1}").strip()
                    if not op_type:
                        continue
                    entry = dict(item)
                    entry["type"] = op_type
                    operations.append(entry)
        parameters["auto"] = {
            "auto_clean": bool(auto.get("auto_clean")),
            "auto_impute": auto.get("auto_impute"),
        }

    action = cleaning_log.get("action")
    if isinstance(action, str) and action.strip():
        if not operations:
            operations.append({"type": action.strip()})
        parameters["action"] = action.strip()

    for key in ("header_row", "sheet", "normalization", "n_imputations", "max_iter", "columns", "count"):
        if key in cleaning_log:
            parameters[key] = cleaning_log.get(key)

    return operations, parameters


def build_cleaning_run_artifact(
    *,
    dataset_id: str,
    cleaning_log: Optional[Dict[str, Any]],
    df_after: pd.DataFrame,
    df_before: Optional[pd.DataFrame] = None,
    actor: str = "system",
    source: str = "pipeline",
) -> Dict[str, Any]:
    cleaning_log_payload = cleaning_log if isinstance(cleaning_log, dict) else {}
    operations, parameters = _extract_operations(cleaning_log_payload)

    before_summary = build_missingness_summary(df_before) if isinstance(df_before, pd.DataFrame) else None
    after_summary = build_missingness_summary(df_after)
    before_fingerprint = dataframe_fingerprint(df_before) if isinstance(df_before, pd.DataFrame) else None
    after_fingerprint = dataframe_fingerprint(df_after)

    delta = None
    if isinstance(before_summary, dict):
        delta = {
            "missing_cells_delta": int(after_summary.get("missing_cells") or 0) - int(before_summary.get("missing_cells") or 0),
            "missing_rate_delta": float(round(float(after_summary.get("missing_rate") or 0.0) - float(before_summary.get("missing_rate") or 0.0), 4)),
        }

    now = datetime.utcnow().isoformat()
    return {
        "version": CLEANING_RUN_VERSION,
        "artifact_type": "cleaning_run",
        "cleaning_run_id": uuid.uuid4().hex,
        "dataset_id": str(dataset_id),
        "applied": True,
        "created_at": now,
        "updated_at": now,
        "actor": str(actor or "system"),
        "source": str(source or "pipeline"),
        "operations": operations,
        "operation_count": int(len(operations)),
        "parameters": parameters,
        "before": {
            "fingerprint": before_fingerprint,
            "missingness": before_summary,
        },
        "after": {
            "fingerprint": after_fingerprint,
            "missingness": after_summary,
        },
        "delta": delta,
        "cleaning_log": cleaning_log_payload,
    }


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    data = json.dumps(payload if isinstance(payload, dict) else {}, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_cleaning_run_", dir=parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def save_cleaning_run_artifact(base_dir: str, dataset_id: str, artifact: Dict[str, Any]) -> None:
    ds_dir = os.path.join(str(base_dir), str(dataset_id), "processed")
    run_id = str(artifact.get("cleaning_run_id") or "").strip()
    _write_json_atomic(os.path.join(ds_dir, "cleaning_run.json"), artifact)
    if run_id:
        _write_json_atomic(os.path.join(ds_dir, "cleaning_runs", f"{run_id}.json"), artifact)


def load_cleaning_run_artifact(base_dir: str, dataset_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(str(base_dir), str(dataset_id), "processed", "cleaning_run.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def validate_cleaning_run_artifact(
    artifact: Optional[Dict[str, Any]],
    *,
    current_df: Optional[pd.DataFrame] = None,
) -> Tuple[bool, str]:
    if not isinstance(artifact, dict):
        return False, "missing_cleaning_run"
    if str(artifact.get("artifact_type") or "").strip().lower() != "cleaning_run":
        return False, "invalid_artifact_type"
    if int(artifact.get("version") or 0) < 1:
        return False, "invalid_version"
    if artifact.get("applied") is not True:
        return False, "not_applied"

    after = artifact.get("after") if isinstance(artifact.get("after"), dict) else {}
    missingness = after.get("missingness") if isinstance(after.get("missingness"), dict) else {}
    fingerprint = str(after.get("fingerprint") or "").strip()
    if not fingerprint:
        return False, "missing_after_fingerprint"
    required_missingness_keys = {"n_rows", "n_cols", "missing_cells", "missing_rate"}
    if not required_missingness_keys.issubset(set(missingness.keys())):
        return False, "missing_after_missingness"

    if isinstance(current_df, pd.DataFrame):
        current_fp = dataframe_fingerprint(current_df)
        if current_fp != fingerprint:
            return False, "fingerprint_mismatch"

    return True, "ok"

