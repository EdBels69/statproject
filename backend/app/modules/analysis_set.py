import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from app.core.pipeline import PipelineManager


ANALYSIS_SET_VERSION = 1

_MISSING_STRINGS = {"", "nan", "none", "null", "na", "n/a"}


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _analysis_sets_dir(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", "analysis_sets")


def _current_pointer_path(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", "analysis_set_current.json")


def _analysis_set_path(base_dir: str, dataset_id: str, analysis_set_id: str) -> str:
    safe_id = str(analysis_set_id or "").strip()
    return os.path.join(_analysis_sets_dir(base_dir, dataset_id), f"{safe_id}.json")


def _processed_parquet_path(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", f"{dataset_id}.parquet")


def _sha256_file(path: str) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        return None
    return None


def _write_json_atomic(base_dir: str, path: str, payload: Dict[str, Any]) -> None:
    pipeline = PipelineManager(str(base_dir))
    pipeline.write_json_atomic(path, payload, allow_nan=False)


def _normalize_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def _clean_actor(value: Any, default: str = "user") -> str:
    text = str(value or "").strip()
    return text or default


def _clean_source(value: Any, default: str = "ui") -> str:
    text = str(value or "").strip()
    return text or default


def _series_nonmissing_mask(series: pd.Series) -> pd.Series:
    mask = series.notna()
    try:
        if (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or isinstance(getattr(series, "dtype", None), pd.CategoricalDtype)
        ):
            as_text = series.astype(str).str.strip().str.lower()
            bad = as_text.isin(_MISSING_STRINGS)
            mask = mask & ~bad
    except Exception:
        pass
    return mask


def _normalize_string_missing_values(series: pd.Series) -> Tuple[pd.Series, int]:
    try:
        if not (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or isinstance(getattr(series, "dtype", None), pd.CategoricalDtype)
        ):
            return series, 0
        as_text = series.astype(str).str.strip().str.lower()
        missing_mask = as_text.isin(_MISSING_STRINGS)
        normalized_count = int(missing_mask.sum())
        if normalized_count <= 0:
            return series, 0
        out = series.copy()
        out.loc[missing_mask] = pd.NA
        return out, normalized_count
    except Exception:
        return series, 0


def _compute_imputation_values(df: pd.DataFrame, indices: List[int], columns: List[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    if not indices or not columns:
        return values
    subset = df.loc[indices, columns].copy()
    for col in columns:
        if col not in subset.columns:
            continue
        s = subset[col]
        try:
            if pd.api.types.is_numeric_dtype(s):
                val = pd.to_numeric(s, errors="coerce").dropna().median()
                values[col] = float(val) if pd.notna(val) else 0.0
                continue
        except Exception:
            pass
        try:
            mask = _series_nonmissing_mask(s)
            nonmissing = s[mask]
            if nonmissing.empty:
                values[col] = "Missing"
            else:
                mode = nonmissing.astype(str).value_counts().index[0]
                values[col] = str(mode)
        except Exception:
            values[col] = "Missing"
    return values


def _fingerprint_for_dataset(base_dir: str, dataset_id: str, df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    fp: Dict[str, Any] = {}
    parquet_path = _processed_parquet_path(base_dir, dataset_id)
    if os.path.exists(parquet_path):
        fp["processed_path"] = parquet_path
        fp["processed_sha256"] = _sha256_file(parquet_path)
        try:
            stat = os.stat(parquet_path)
            fp["processed_bytes"] = int(stat.st_size)
            fp["processed_mtime"] = float(stat.st_mtime)
        except Exception:
            pass
    if isinstance(df, pd.DataFrame):
        try:
            fp["row_count"] = int(len(df))
            fp["col_count"] = int(len(df.columns))
            cols = [str(c) for c in df.columns]
            fp["columns_sha256"] = hashlib.sha256("\n".join(cols).encode("utf-8")).hexdigest()
        except Exception:
            pass
    return fp


def load_analysis_set(base_dir: str, dataset_id: str, analysis_set_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if analysis_set_id:
        return _load_json(_analysis_set_path(base_dir, dataset_id, analysis_set_id))
    pointer = _load_json(_current_pointer_path(base_dir, dataset_id))
    if not isinstance(pointer, dict):
        return None
    cur_id = pointer.get("analysis_set_id")
    if not isinstance(cur_id, str) or not cur_id.strip():
        return None
    return _load_json(_analysis_set_path(base_dir, dataset_id, cur_id))


def validate_analysis_set_fingerprint(
    base_dir: str,
    dataset_id: str,
    artifact: Dict[str, Any],
    *,
    df: Optional[pd.DataFrame] = None,
) -> Tuple[bool, Dict[str, Any]]:
    expected = artifact.get("fingerprint") if isinstance(artifact, dict) else None
    if not isinstance(expected, dict) or not expected:
        return True, {"reason": "fingerprint_missing"}

    actual = _fingerprint_for_dataset(base_dir, dataset_id, df=df)
    mismatches: List[str] = []

    exp_sha = expected.get("processed_sha256")
    act_sha = actual.get("processed_sha256")
    if isinstance(exp_sha, str) and exp_sha and isinstance(act_sha, str) and act_sha and exp_sha != act_sha:
        mismatches.append("processed_sha256")

    exp_row = expected.get("row_count")
    act_row = actual.get("row_count")
    if isinstance(exp_row, (int, float)) and isinstance(act_row, (int, float)) and int(exp_row) != int(act_row):
        mismatches.append("row_count")

    exp_col = expected.get("col_count")
    act_col = actual.get("col_count")
    if isinstance(exp_col, (int, float)) and isinstance(act_col, (int, float)) and int(exp_col) != int(act_col):
        mismatches.append("col_count")

    exp_cols_sha = expected.get("columns_sha256")
    act_cols_sha = actual.get("columns_sha256")
    if (
        isinstance(exp_cols_sha, str)
        and exp_cols_sha
        and isinstance(act_cols_sha, str)
        and act_cols_sha
        and exp_cols_sha != act_cols_sha
    ):
        mismatches.append("columns_sha256")

    return len(mismatches) == 0, {"mismatches": mismatches, "expected": expected, "actual": actual}


def set_current_analysis_set(base_dir: str, dataset_id: str, analysis_set_id: str) -> None:
    pointer_path = _current_pointer_path(base_dir, dataset_id)
    payload = {
        "dataset_id": str(dataset_id),
        "analysis_set_id": str(analysis_set_id),
        "updated_at": _utc_iso(),
        "version": ANALYSIS_SET_VERSION,
    }
    _write_json_atomic(base_dir, pointer_path, payload)


def clear_current_analysis_set(base_dir: str, dataset_id: str) -> bool:
    pointer_path = _current_pointer_path(base_dir, dataset_id)
    try:
        if os.path.exists(pointer_path):
            os.remove(pointer_path)
        return True
    except Exception:
        return False


def freeze_analysis_set(
    base_dir: str,
    dataset_id: str,
    *,
    df: pd.DataFrame,
    mode: Any = "complete_case",
    enforce: Any = "models",
    required_non_missing: Any = None,
    impute_columns: Any = None,
    actor: Any = "user",
    source: Any = "ui",
    notes: Any = None,
) -> Dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df is required for freeze_analysis_set")

    mode_norm = str(mode or "").strip().lower() or "complete_case"
    if mode_norm not in {"complete_case", "simple_impute"}:
        raise ValueError("mode must be complete_case or simple_impute")

    enforce_norm = str(enforce or "").strip().lower() or "models"
    if enforce_norm not in {"models", "all"}:
        raise ValueError("enforce must be models or all")

    required_cols = _normalize_str_list(required_non_missing)
    impute_cols = _normalize_str_list(impute_columns)

    if not required_cols and mode_norm == "complete_case":
        raise ValueError("required_non_missing must be non-empty for complete_case mode")

    missing_cols = [c for c in [*required_cols, *impute_cols] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Колонки не найдены в датасете: {', '.join(missing_cols)}")

    mask = pd.Series([True] * len(df), index=df.index)
    coverage: Dict[str, Dict[str, int]] = {}
    for col in required_cols:
        col_mask = _series_nonmissing_mask(df[col])
        coverage[col] = {"available": int(col_mask.sum()), "missing": int((~col_mask).sum())}
        mask = mask & col_mask

    indices = [int(i) for i in df.index[mask].tolist()]
    indices.sort()

    imputation = None
    if mode_norm == "simple_impute" and impute_cols:
        impute_values = _compute_imputation_values(df, indices, impute_cols)
        imputation = {"strategy": "median_mode", "values": impute_values}

    now = _utc_iso()
    analysis_set_id = uuid.uuid4().hex
    artifact = {
        "version": ANALYSIS_SET_VERSION,
        "dataset_id": str(dataset_id),
        "analysis_set_id": analysis_set_id,
        "mode": mode_norm,
        "enforce": enforce_norm,
        "required_non_missing": required_cols,
        "impute_columns": impute_cols,
        "imputation": imputation,
        "coverage": coverage,
        "n_total": int(len(df)),
        "n_selected": int(len(indices)),
        "row_indices": indices,
        "fingerprint": _fingerprint_for_dataset(base_dir, dataset_id, df=df),
        "created_at": now,
        "created_by": _clean_actor(actor),
        "created_source": _clean_source(source),
        "notes": _normalize_str_list(notes),
        "updated_at": now,
    }

    sets_dir = _analysis_sets_dir(base_dir, dataset_id)
    os.makedirs(sets_dir, exist_ok=True)
    artifact_path = _analysis_set_path(base_dir, dataset_id, analysis_set_id)
    _write_json_atomic(base_dir, artifact_path, artifact)
    set_current_analysis_set(base_dir, dataset_id, analysis_set_id)
    return artifact


def apply_analysis_set_to_df(df: pd.DataFrame, artifact: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a DataFrame")
    if not isinstance(artifact, dict):
        raise ValueError("artifact must be a dict")
    indices = artifact.get("row_indices")
    if not isinstance(indices, list) or not indices:
        raise ValueError("analysis_set row_indices is empty")
    try:
        normalized_indices = [int(i) for i in indices]
    except Exception as e:
        raise ValueError(f"analysis_set row_indices is invalid: {e}")
    if min(normalized_indices) < 0 or max(normalized_indices) >= len(df):
        raise ValueError("analysis_set row_indices out of range for current dataset; re-freeze cohort")

    subset = df.iloc[normalized_indices].copy()
    info: Dict[str, Any] = {"selected_rows": int(len(subset))}

    mode = str(artifact.get("mode") or "").strip().lower()
    imputation = artifact.get("imputation") if isinstance(artifact.get("imputation"), dict) else None
    if mode == "simple_impute" and imputation:
        values = imputation.get("values") if isinstance(imputation.get("values"), dict) else {}
        filled = 0
        normalized_strings = 0
        for col, val in values.items():
            if col not in subset.columns:
                continue
            subset[col], normalized_count = _normalize_string_missing_values(subset[col])
            normalized_strings += int(normalized_count)
            before = int((~_series_nonmissing_mask(subset[col])).sum())
            if before <= 0:
                continue
            try:
                subset[col] = subset[col].fillna(val)
                after = int((~_series_nonmissing_mask(subset[col])).sum())
                filled += max(0, before - after)
            except Exception:
                pass
        info["imputed_cells"] = int(filled)
        info["normalized_string_missing"] = int(normalized_strings)
    return subset, info
