import shutil
import uuid
import os
import numpy as np
import pandas as pd
import aiofiles
import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Header
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from typing import List, Dict, Any, Optional, Literal

from app.schemas.dataset import (
    DatasetUpload,
    DatasetProfile,
    DatasetReparse,
    DatasetModification,
    ModificationAction,
    ColumnInfo,
    VariableMappingUpdate,
    VariableMappingDocument,
    DesignReviewAction,
    DesignReviewDocument,
    AnalysisSetAction,
    AnalysisSetDocument,
    InteractiveCleaningApplyRequest,
    InteractiveCleaningApplyResponse,
    StudyDesignUpdateAction,
)
from app.modules.parsers import parse_file, get_dataset_path, get_dataframe, get_dataset_columns, get_dataset_row_count, get_dataframe_window
from app.modules.semantics import rebuild_and_save_semantics, load_semantics
from app.modules.study_design import rebuild_and_save_study_design, load_study_design, save_study_design
from app.modules.design_review import load_design_review, confirm_design_review, revoke_design_review
from app.modules.analysis_set import load_analysis_set, freeze_analysis_set, clear_current_analysis_set
from app.modules.delta_log import append_delta_log
from app.core.pipeline import PipelineManager
from app.core.paths import get_workspace_dir, get_datasets_dir
from pydantic import BaseModel
import math

router = APIRouter()

WORKSPACE_DIR = get_workspace_dir()
DATA_DIR = get_datasets_dir()
pipeline = PipelineManager(DATA_DIR)
_STUDY_DESIGN_MIN_REVISION = 1


class PrepareHistoryResponse(BaseModel):
    count: int


def _load_dataset_meta(dataset_id: str) -> Dict[str, Any]:
    upload_dir = os.path.join(DATA_DIR, dataset_id)
    meta_path = os.path.join(upload_dir, "source", "meta.json")
    if not os.path.exists(meta_path):
        meta_path = os.path.join(upload_dir, "metadata.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _sanitize_json(obj: Any) -> Any:
    if hasattr(obj, "item") and callable(getattr(obj, "item")):
        try:
            return _sanitize_json(obj.item())
        except Exception:
            return str(obj)

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [_sanitize_json(v) for v in obj]
    return obj


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if model is None:
        return {}
    if isinstance(model, dict):
        return dict(model)
    if hasattr(model, "model_dump") and callable(getattr(model, "model_dump")):
        try:
            out = model.model_dump(exclude_none=True)
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    if hasattr(model, "dict") and callable(getattr(model, "dict")):
        try:
            out = model.dict(exclude_none=True)
            return out if isinstance(out, dict) else {}
        except Exception:
            return {}
    return {}


def _dedupe_str_list(value: Any) -> List[str]:
    out: List[str] = []
    for item in value if isinstance(value, list) else []:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _study_design_revision(payload: Dict[str, Any]) -> int:
    try:
        rev = int(payload.get("revision") or 0)
    except Exception:
        rev = 0
    if rev <= 0:
        rev = _STUDY_DESIGN_MIN_REVISION
    return rev


def _study_design_etag(revision: int) -> str:
    return f'W/"sd-{max(_STUDY_DESIGN_MIN_REVISION, int(revision))}"'


def _parse_study_design_etag(value: Any) -> Optional[int]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    marker = "sd-"
    idx = text.find(marker)
    if idx < 0:
        return None
    tail = text[idx + len(marker) :]
    digits = []
    for ch in tail:
        if ch.isdigit():
            digits.append(ch)
        else:
            break
    if not digits:
        return None
    try:
        return int("".join(digits))
    except Exception:
        return None


def _validate_alpha(value: Any) -> float:
    try:
        alpha = float(value)
    except Exception:
        raise ValueError("analysis_policy.alpha должен быть числом")
    if alpha <= 0 or alpha >= 1:
        raise ValueError("analysis_policy.alpha должен быть в диапазоне (0, 1)")
    return alpha


def _validate_positive_int(value: Any, key: str, min_v: int = 1, max_v: int = 1000) -> int:
    try:
        iv = int(value)
    except Exception:
        raise ValueError(f"analysis_policy.{key} должен быть целым числом")
    if iv < min_v or iv > max_v:
        raise ValueError(f"analysis_policy.{key} должен быть в диапазоне [{min_v}, {max_v}]")
    return iv


def _column_kind(columns_meta: Dict[str, Any], column: str) -> str:
    meta = columns_meta.get(column) if isinstance(columns_meta, dict) else None
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("type") or "").strip().lower()


def _is_numeric_column(columns_meta: Dict[str, Any], column: str) -> bool:
    return _column_kind(columns_meta, column) == "numeric"


def _is_categorical_column(columns_meta: Dict[str, Any], column: str) -> bool:
    kind = _column_kind(columns_meta, column)
    return kind in {"categorical", "text"}


def _validate_column_exists(column: Optional[str], *, key: str, available_cols: set) -> Optional[str]:
    if column is None:
        return None
    text = str(column or "").strip()
    if not text:
        return None
    if text not in available_cols:
        raise ValueError(f"{key}: колонка не найдена в датасете: {text}")
    return text


def _validate_column_list(
    values: Any,
    *,
    key: str,
    available_cols: set,
    kind_check: Optional[str] = None,
    columns_meta: Optional[Dict[str, Any]] = None,
) -> List[str]:
    out = _dedupe_str_list(values)
    missing = [c for c in out if c not in available_cols]
    if missing:
        raise ValueError(f"{key}: колонки не найдены в датасете: {', '.join(missing)}")

    if kind_check and isinstance(columns_meta, dict):
        bad: List[str] = []
        for col in out:
            if kind_check == "numeric" and not _is_numeric_column(columns_meta, col):
                bad.append(col)
            if kind_check == "categorical" and not _is_categorical_column(columns_meta, col):
                bad.append(col)
        if bad:
            msg = "числовыми" if kind_check == "numeric" else "категориальными"
            raise ValueError(f"{key}: ожидаются {msg} колонки: {', '.join(bad)}")
    return out


_MISSING_STRING_TOKENS = {"", "na", "n/a", "none", "null", "nan", "nat", "missing"}

_INTERACTIVE_CLEAN_ACTION_ALIASES = {
    "drop_column_high_missing": "drop_col",
    "drop_column": "drop_col",
    "remove_column": "drop_col",
    "impute_numeric_mean": "fill_mean",
    "impute_numeric_median": "fill_median",
    "impute_categorical_mode": "fill_mode",
    "fill_forward": "fill_locf",
    "fill_backward": "fill_nocb",
    "remove_missing_rows": "drop_na",
    "convert_to_numeric": "to_numeric",
    "normalize_category_values": "normalize_categories",
}

_INTERACTIVE_CLEAN_ALLOWED_ACTIONS = {
    "drop_col",
    "drop_na",
    "to_numeric",
    "normalize_categories",
    "fill_mean",
    "fill_median",
    "fill_mode",
    "fill_locf",
    "fill_nocb",
    "normalize_missing_tokens",
}


def _normalize_interactive_clean_action(action: Any) -> str:
    key = str(action or "").strip().lower().replace("-", "_")
    if not key:
        return ""
    key = _INTERACTIVE_CLEAN_ACTION_ALIASES.get(key, key)
    return key if key in _INTERACTIVE_CLEAN_ALLOWED_ACTIONS else ""


def _normalize_missing_tokens_series(series: pd.Series) -> pd.Series:
    try:
        if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
            text = series.astype(str).str.strip().str.lower()
            mask = text.isin(_MISSING_STRING_TOKENS)
            if bool(mask.any()):
                normalized = series.where(~mask, pd.NA)
                return normalized
    except Exception:
        return series
    return series


def _coerce_update_cell_value(df: pd.DataFrame, *, column: str, value: Any) -> Any:
    series = df[column]
    if value is None:
        if pd.api.types.is_integer_dtype(series.dtype):
            # Numpy int dtypes cannot store missing values safely.
            df[column] = pd.to_numeric(series, errors="coerce").astype("Int64")
            return pd.NA
        return None

    if isinstance(value, str):
        value = value.strip()
        if value.lower() in _MISSING_STRING_TOKENS:
            if pd.api.types.is_integer_dtype(series.dtype):
                df[column] = pd.to_numeric(series, errors="coerce").astype("Int64")
                return pd.NA
            return None

    if pd.api.types.is_datetime64_any_dtype(series.dtype):
        ts = pd.to_datetime(value, errors="coerce")
        return ts if pd.notna(ts) else None

    if pd.api.types.is_bool_dtype(series.dtype):
        if isinstance(value, bool):
            return value
        token = str(value).strip().lower()
        if token in {"1", "true", "yes", "y", "да"}:
            return True
        if token in {"0", "false", "no", "n", "нет"}:
            return False
        return None

    if pd.api.types.is_integer_dtype(series.dtype):
        num = pd.to_numeric(value, errors="coerce")
        if pd.isna(num):
            df[column] = pd.to_numeric(series, errors="coerce").astype("Int64")
            return pd.NA
        num_f = float(num)
        if num_f.is_integer():
            num_i = int(num_f)
            try:
                bounded_dtype = getattr(series.dtype, "numpy_dtype", series.dtype)
                bounds = np.iinfo(bounded_dtype)
                if num_i < int(bounds.min) or num_i > int(bounds.max):
                    df[column] = pd.to_numeric(series, errors="coerce").astype("Int64")
            except Exception:
                # If dtype bounds are unknown, keep value as-is and let pandas handle assignment.
                pass
            return num_i
        # Widen dtype once if user enters non-integer value into an integer column.
        df[column] = pd.to_numeric(series, errors="coerce").astype("float64")
        return num_f

    if pd.api.types.is_float_dtype(series.dtype):
        num = pd.to_numeric(value, errors="coerce")
        return float(num) if pd.notna(num) else None

    return value


def _apply_interactive_clean_action(df: pd.DataFrame, *, column: Optional[str], action: str) -> pd.DataFrame:
    op = _normalize_interactive_clean_action(action)
    if not op:
        raise ValueError(f"Неподдерживаемое действие очистки: {action}")

    col = str(column or "").strip()
    if op not in {"normalize_missing_tokens"} and not col:
        raise ValueError(f"{op}: column обязателен")
    if col and col not in df.columns:
        raise ValueError(f"Колонка не найдена: {col}")

    if op == "normalize_missing_tokens":
        if col:
            df[col] = _normalize_missing_tokens_series(df[col])
        else:
            for name in list(df.columns):
                df[name] = _normalize_missing_tokens_series(df[name])
        return df

    if op == "drop_col":
        return df.drop(columns=[col])

    if op == "to_numeric":
        df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    if op == "normalize_categories":
        from app.modules.data_normalizer import normalize_categorical_series

        df[col] = normalize_categorical_series(df[col])
        return df

    if op == "fill_mean":
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"{op}: поддерживается только для числовых столбцов ({col})")
        df[col] = df[col].fillna(df[col].mean())
        return df

    if op == "fill_median":
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"{op}: поддерживается только для числовых столбцов ({col})")
        df[col] = df[col].fillna(df[col].median())
        return df

    if op == "fill_mode":
        mode_series = df[col].mode(dropna=True)
        if mode_series.empty:
            raise ValueError(f"{op}: требуется хотя бы одно ненулевое значение ({col})")
        df[col] = df[col].fillna(mode_series.iloc[0])
        return df

    if op == "fill_locf":
        df[col] = df[col].ffill()
        return df

    if op == "fill_nocb":
        df[col] = df[col].bfill()
        return df

    if op == "drop_na":
        return df.dropna(subset=[col])

    raise ValueError(f"Неподдерживаемое действие очистки: {action}")


def _design_review_document(dataset_id: str, artifact: Optional[Dict[str, Any]]) -> DesignReviewDocument:
    if not isinstance(artifact, dict):
        return DesignReviewDocument(dataset_id=str(dataset_id), artifact_exists=False)

    details = artifact.get("details")
    if not isinstance(details, dict):
        details = {}

    return DesignReviewDocument(
        dataset_id=str(dataset_id),
        version=int(artifact.get("version") or 1),
        confirmed=bool(artifact.get("confirmed")),
        confirmed_at=artifact.get("confirmed_at") if isinstance(artifact.get("confirmed_at"), str) else None,
        confirmed_by=artifact.get("confirmed_by") if isinstance(artifact.get("confirmed_by"), str) else None,
        confirmed_source=artifact.get("confirmed_source") if isinstance(artifact.get("confirmed_source"), str) else None,
        revoked_at=artifact.get("revoked_at") if isinstance(artifact.get("revoked_at"), str) else None,
        revoked_by=artifact.get("revoked_by") if isinstance(artifact.get("revoked_by"), str) else None,
        revoke_reason=artifact.get("revoke_reason") if isinstance(artifact.get("revoke_reason"), str) else None,
        revoke_source=artifact.get("revoke_source") if isinstance(artifact.get("revoke_source"), str) else None,
        updated_at=artifact.get("updated_at") if isinstance(artifact.get("updated_at"), str) else None,
        details=details,
        artifact_exists=True,
    )


def _analysis_set_document(dataset_id: str, artifact: Optional[Dict[str, Any]]) -> AnalysisSetDocument:
    if not isinstance(artifact, dict):
        return AnalysisSetDocument(dataset_id=str(dataset_id), artifact_exists=False)

    analysis_set_id = artifact.get("analysis_set_id") if isinstance(artifact.get("analysis_set_id"), str) else None
    fingerprint = artifact.get("fingerprint")
    if not isinstance(fingerprint, dict):
        fingerprint = {}

    required_non_missing = artifact.get("required_non_missing")
    if not isinstance(required_non_missing, list):
        required_non_missing = []

    impute_columns = artifact.get("impute_columns")
    if not isinstance(impute_columns, list):
        impute_columns = []

    n_total = artifact.get("n_total")
    n_selected = artifact.get("n_selected")

    return AnalysisSetDocument(
        dataset_id=str(dataset_id),
        analysis_set_id=analysis_set_id,
        version=int(artifact.get("version") or 1),
        mode=str(artifact.get("mode") or "").strip() or None,
        enforce=str(artifact.get("enforce") or "").strip() or None,
        required_non_missing=[str(c) for c in required_non_missing if c is not None],
        impute_columns=[str(c) for c in impute_columns if c is not None],
        n_total=int(n_total) if isinstance(n_total, (int, float)) else None,
        n_selected=int(n_selected) if isinstance(n_selected, (int, float)) else None,
        created_at=artifact.get("created_at") if isinstance(artifact.get("created_at"), str) else None,
        created_by=artifact.get("created_by") if isinstance(artifact.get("created_by"), str) else None,
        created_source=artifact.get("created_source") if isinstance(artifact.get("created_source"), str) else None,
        updated_at=artifact.get("updated_at") if isinstance(artifact.get("updated_at"), str) else None,
        fingerprint=fingerprint,
        artifact_exists=True,
    )


async def _ingest_dataset_bytes(
    content: bytes,
    filename: str,
    *,
    auto_clean: bool = True,
    auto_impute: str = "simple",
) -> DatasetUpload:
    dataset_id = str(uuid.uuid4())
    try:
        raw_path = pipeline.save_source(dataset_id, content, filename)

        def parse_logic():
            return parse_file(raw_path, header_row=0, original_filename=filename)

        df, used_header = await run_in_threadpool(parse_logic)

        from app.modules.smart_scanner import SmartScanner
        from app.services.upload_service import _auto_clean_and_impute, _normalize_auto_impute
        scanner = SmartScanner()
        df = await run_in_threadpool(scanner.optimize_dtypes, df)

        scan_before = await run_in_threadpool(scanner.scan_dataset, df)
        scan_report_before = scan_before.get("scan_report") or {}

        auto_impute_norm = _normalize_auto_impute(auto_impute)
        df, auto_stats = await run_in_threadpool(
            lambda: _auto_clean_and_impute(
                df,
                scan_report_before,
                auto_clean=bool(auto_clean),
                auto_impute=auto_impute_norm,
            )
        )

        if auto_stats.get("actions"):
            df = await run_in_threadpool(scanner.optimize_dtypes, df)
            scan_result = await run_in_threadpool(scanner.scan_dataset, df)
        else:
            scan_result = scan_before

        pipeline.create_processed_snapshot(
            dataset_id,
            df,
            cleaning_log={"header_row": used_header, "auto": auto_stats},
        )

        profile_data = _sanitize_json(scan_result["profile"])
        scan_report = scan_result["scan_report"]

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
            action="ingest",
            actor="auto",
            details={
                "header_row": used_header,
                "auto": auto_stats,
            },
        )
    except Exception as e:
        shutil.rmtree(os.path.join(DATA_DIR, dataset_id), ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Обработка файла не удалась: {str(e)}")

    return DatasetUpload(id=dataset_id, filename=filename, profile=profile_data)


def get_variable_mapping_path(dataset_id: str) -> str:
    return os.path.join(DATA_DIR, dataset_id, "processed", "variable_mapping.json")


def load_variable_mapping(dataset_id: str) -> dict:
    path = get_variable_mapping_path(dataset_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_variable_mapping(dataset_id: str, mapping: Dict[str, Any]) -> None:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        return

    processed_dir = os.path.join(ds_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    path = get_variable_mapping_path(dataset_id)

    if os.path.exists(path):
        try:
            from datetime import datetime

            backups_dir = os.path.join(processed_dir, "backups")
            os.makedirs(backups_dir, exist_ok=True)

            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backups_dir, f"variable_mapping.{ts}.json")
            shutil.copy2(path, backup_path)
        except Exception:
            pass

    serializable_mapping: Dict[str, Any] = {}
    for k, v in (mapping or {}).items():
        if isinstance(v, BaseModel):
            serializable_mapping[k] = v.model_dump()
        else:
            serializable_mapping[k] = v

    pipeline.write_json_atomic(path, serializable_mapping, allow_nan=False)


def update_variable_mapping_for_actions(
    dataset_id: str,
    mapping: Dict[str, Any],
    actions: List[Any],
    existing_columns: List[str],
) -> Dict[str, Any]:
    next_mapping: Dict[str, Any] = dict(mapping or {})

    for action in actions:
        a_type = getattr(action, "type", None)
        if a_type == "rename_col":
            col = getattr(action, "column", None)
            new_name = getattr(action, "new_name", None)
            if isinstance(col, str) and isinstance(new_name, str) and col and new_name and col in next_mapping:
                next_mapping[new_name] = next_mapping.pop(col)
        elif a_type == "drop_col":
            col = getattr(action, "column", None)
            if isinstance(col, str) and col:
                next_mapping.pop(col, None)
        elif a_type == "change_type":
            col = getattr(action, "column", None)
            new_type = getattr(action, "new_type", None)
            if isinstance(col, str) and col and isinstance(new_type, str) and new_type:
                current = next_mapping.get(col)
                if not isinstance(current, dict):
                    current = {}
                next_mapping[col] = {**current, "data_type": new_type}

    allowed = {str(c) for c in (existing_columns or [])}
    next_mapping = {k: v for k, v in next_mapping.items() if k in allowed}
    save_variable_mapping(dataset_id, next_mapping)
    return next_mapping


def generate_profile(
    df: pd.DataFrame,
    page: int = 1,
    limit: int = 100,
    head_col_offset: int = 0,
    head_col_limit: Optional[int] = None,
) -> DatasetProfile:
    """
    Generate a DatasetProfile from a pandas DataFrame.
    """
    import numpy as np
    
    def to_python(val):
        """Convert numpy types to Python native types for JSON serialization."""
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        if isinstance(val, np.ndarray):
            return val.tolist()
        if pd.isna(val):
            return None
        return val
    
    total_rows = int(len(df))
    total_cols = int(len(df.columns))

    stats_sampled = False
    stats_sample_rows: Optional[int] = None
    df_stats = df
    if total_cols > 500 or total_rows > 20000:
        stats_sampled = True
        stats_sample_rows = min(2000, total_rows)
        if stats_sample_rows > 0:
            df_stats = df.sample(n=stats_sample_rows, random_state=42)

    sample_n = int(len(df_stats))
    sample_missing = df_stats.isna().sum() if sample_n else None
    sample_unique = df_stats.nunique(dropna=True) if sample_n else None

    dtypes = df.dtypes

    columns = []
    for col in df.columns:
        dtype = dtypes[col]
        dtype_str = str(dtype)

        unique_est = int(sample_unique[col]) if sample_unique is not None else 0
        name_l = str(col).strip().lower()

        if "int" in dtype_str or "float" in dtype_str:
            col_type = "numeric"
            if unique_est and sample_n:
                ratio = float(unique_est) / float(max(1, sample_n))
                looks_like_group = any(
                    k in name_l
                    for k in [
                        "группа",
                        "group",
                        "treatment",
                        "arm",
                        "cohort",
                        "класс",
                        "категор",
                        "category",
                        "групп",
                        "рандом",
                    ]
                )
                if (unique_est <= 12 and ratio <= 0.2) or (looks_like_group and unique_est <= 50):
                    col_type = "categorical"
        elif "datetime" in dtype_str:
            col_type = "datetime"
        elif dtype == "object" or getattr(dtype, "name", "") == "category":
            sample_uc = int(sample_unique[col]) if sample_unique is not None else 0
            col_type = "categorical" if sample_uc and sample_uc < 20 else "text"
        else:
            col_type = "text"

        example_val = None
        if sample_n:
            try:
                s = df_stats[col]
                non_na = s.dropna()
                if not non_na.empty:
                    example_val = to_python(non_na.iloc[0])
            except Exception:
                example_val = None

        if sample_missing is not None and sample_n:
            missing_est = int(round((float(sample_missing[col]) / float(sample_n)) * float(total_rows)))
        else:
            missing_est = 0

        columns.append(
            ColumnInfo(
                name=str(col),
                type=col_type,
                missing_count=missing_est,
                unique_count=unique_est,
                example=example_val,
            )
        )
    
    total_pages = max(1, math.ceil(total_rows / limit))
    start = (page - 1) * limit
    end = start + limit
    
    effective_head_limit: int
    if head_col_limit is None:
        effective_head_limit = 120 if total_cols > 300 else total_cols
    else:
        effective_head_limit = int(head_col_limit)
    effective_head_limit = max(1, min(400, effective_head_limit))

    safe_head_offset = max(0, int(head_col_offset))
    safe_head_offset = min(safe_head_offset, max(0, total_cols - 1)) if total_cols else 0
    head_cols = list(df.columns)[safe_head_offset : safe_head_offset + effective_head_limit]

    head_df = df.loc[df.index[start:end], head_cols].replace({pd.NA: None, float('nan'): None})
    head = []
    for _, row in head_df.iterrows():
        head.append({k: to_python(v) for k, v in row.items()})
    
    return DatasetProfile(
        row_count=total_rows,
        col_count=total_cols,
        columns=columns,
        head=head,
        head_col_offset=safe_head_offset,
        head_col_limit=effective_head_limit,
        stats_sampled=bool(stats_sampled),
        stats_sample_rows=stats_sample_rows,
        page=page,
        total_pages=total_pages
    )

@router.get("", response_model=List[dict])
async def list_datasets():
    datasets = []
    if not os.path.exists(DATA_DIR):
        return []
    
    # New Pipeline Structure Logic
    try:
        # Use run_in_threadpool if there are many files to avoid blocking the event loop
        def scan_datasets():
            results = []
            for dataset_id in os.listdir(DATA_DIR):
                try:
                    ds_dir = os.path.join(DATA_DIR, dataset_id)
                    if not os.path.isdir(ds_dir): continue
                    
                    row_count = None
                    col_count = None
                    file_size = None
                    created_at = None
                    filename = "unknown"
                    
                    # Try to get size from original.raw
                    raw_path = os.path.join(ds_dir, "source", "original.raw")
                    if os.path.exists(raw_path):
                         try:
                             file_size = os.path.getsize(raw_path)
                         except:
                             pass
                    
                    # Try to get rows/cols from scan_report
                    report_path = os.path.join(ds_dir, "processed", "scan_report.json")
                    if os.path.exists(report_path):
                        try:
                            with open(report_path, "r") as f:
                                report = json.load(f)
                                profile = report.get("profile", {})
                                row_count = profile.get("row_count")
                                col_count = profile.get("col_count")
                        except:
                            pass

                    # Check source metadata
                    meta_path = os.path.join(ds_dir, "source", "meta.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, "r") as f:
                                meta = json.load(f)
                                filename = meta.get("original_filename", "unknown")
                                created_at = meta.get("ingest_timestamp")
                                
                                results.append({
                                    "id": dataset_id, 
                                    "filename": filename,
                                    "created_at": created_at,
                                    "row_count": row_count,
                                    "col_count": col_count,
                                    "size": file_size,
                                    "is_ready": row_count is not None
                                })
                            continue
                        except:
                            pass
                            
                    # Fallback to old flat structure (Migration support)
                    files = [f for f in os.listdir(ds_dir) if not f.endswith('.json') and f != "processed.csv" and not os.path.isdir(os.path.join(ds_dir, f))]
                    if files:
                        results.append({
                            "id": dataset_id, 
                            "filename": files[0],
                            "row_count": None,
                            "col_count": None,
                            "size": None,
                            "is_ready": False
                        })
                except Exception:
                    continue # Skip bad dataset
            return results

        datasets = await run_in_threadpool(scan_datasets)

    except Exception as e:
        print(f"Error listing datasets: {e}")
        return []

    # Sort by created_at desc
    datasets.sort(key=lambda x: x.get("created_at") or "", reverse=True)
            
    return datasets


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str):
    data_root = os.path.realpath(DATA_DIR)
    ds_dir = os.path.realpath(os.path.join(DATA_DIR, str(dataset_id)))
    if not ds_dir.startswith(data_root + os.sep):
        raise HTTPException(status_code=400, detail="Некорректный идентификатор файла данных")

    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    try:
        shutil.rmtree(ds_dir)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось удалить файл данных: {str(e)}")

    return {"id": dataset_id, "deleted": True}

@router.post("", response_model=DatasetUpload)
async def upload_dataset(
    file: UploadFile = File(...),
    auto_clean: bool = Query(True),
    auto_impute: str = Query("simple"),
):
    # File size validation (50MB max)
    MAX_FILE_SIZE = 50 * 1024 * 1024
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Файл слишком большой. Максимум {MAX_FILE_SIZE/1024/1024:.0f} МБ, получено {file_size/1024/1024:.1f} МБ"
        )
    
    content = await file.read()
    return await _ingest_dataset_bytes(
        content,
        file.filename,
        auto_clean=auto_clean,
        auto_impute=auto_impute,
    )


@router.get("/{dataset_id}/report", response_model=Dict[str, Any])
def get_dataset_report(dataset_id: str):
    """
    Returns the full 'Technical Audit' report (scan_report.json).
    Contains: basic stats, data quality issues, normality checks, etc.
    """
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    report_path = os.path.join(ds_dir, "processed", "scan_report.json")
    if not os.path.exists(report_path):
        # Fallback: if not found, generate a fresh profile and return minimal info
        # But ideally we should re-scan. For now, 404 is appropriate or a basic mock.
        return {"error": "Report not found", "status": "pending"}

    try:
        with open(report_path, "r") as f:
            data = json.load(f)
        return _sanitize_json(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {str(e)}")


@router.get("/{dataset_id}/sheets", response_model=List[str])
def list_dataset_sheets(dataset_id: str):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    meta = _load_dataset_meta(dataset_id)
    original_filename = str(meta.get("original_filename") or "")
    ext = os.path.splitext(original_filename)[1].lower()
    if ext not in (".xlsx", ".xls"):
        return []

    file_path, _ = get_dataset_path(dataset_id, DATA_DIR)
    if not file_path:
        return []

    try:
        xls = pd.ExcelFile(file_path, engine="openpyxl" if ext == ".xlsx" else None)
        names = [str(s) for s in (xls.sheet_names or [])]
        return [n for n in names if n]
    except Exception:
        return []


@router.post("/{dataset_id}/prepare/clone", response_model=DatasetUpload)
async def clone_dataset_for_preparation(dataset_id: str):
    new_id: Optional[str] = None
    try:
        df = get_dataframe(dataset_id, DATA_DIR)

        base_meta = _load_dataset_meta(dataset_id)
        base_filename = str(base_meta.get("original_filename") or base_meta.get("filename") or dataset_id)
        prepared_filename = f"Подготовлено — {base_filename}"

        new_id = str(uuid.uuid4())
        paths = pipeline.initialize_dataset(new_id)

        meta = {
            "original_filename": prepared_filename,
            "ingest_timestamp": datetime.now().isoformat(),
            "derived_from": dataset_id,
            "locked": True,
        }
        with open(os.path.join(paths["source"], "meta.json"), "w") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = await run_in_threadpool(scanner.optimize_dtypes, df)
        pipeline.create_processed_snapshot(new_id, df, cleaning_log={"action": "prepare_clone", "from": dataset_id})

        scan_result = await run_in_threadpool(scanner.scan_dataset, df)
        profile_data = scan_result["profile"]
        scan_report = scan_result["scan_report"]

        report_path = os.path.join(pipeline.get_dataset_dir(new_id), "processed", "scan_report.json")
        pipeline.write_json_atomic(report_path, _sanitize_json(scan_report), allow_nan=False)

        mapping = load_variable_mapping(dataset_id)
        if mapping:
            save_variable_mapping(new_id, mapping)

        rebuild_and_save_semantics(
            dataset_id=new_id,
            base_dir=DATA_DIR,
            scan_report=scan_report,
            source="auto",
        )
        rebuild_and_save_study_design(
            dataset_id=new_id,
            base_dir=DATA_DIR,
            scan_report=scan_report,
            source="auto",
        )

        append_delta_log(
            base_dir=DATA_DIR,
            dataset_id=new_id,
            action="prepare_clone",
            actor="auto",
            details={"from": dataset_id},
        )

        return DatasetUpload(id=new_id, filename=prepared_filename, profile=profile_data)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден")
    except Exception as e:
        if isinstance(new_id, str) and new_id:
            shutil.rmtree(os.path.join(DATA_DIR, new_id), ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Не удалось создать подготовленную копию: {str(e)}")


@router.get("/{dataset_id}/prepare/history", response_model=PrepareHistoryResponse)
def get_prepare_history(dataset_id: str):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    meta = _load_dataset_meta(dataset_id)
    if meta.get("locked") is not True:
        raise HTTPException(status_code=400, detail="История доступна только для подготовленного датасета")

    return PrepareHistoryResponse(count=pipeline.get_processed_history_count(dataset_id))


@router.post("/{dataset_id}/prepare/undo", response_model=DatasetProfile)
async def undo_prepare_change(
    dataset_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000),
):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    meta = _load_dataset_meta(dataset_id)
    if meta.get("locked") is not True:
        raise HTTPException(status_code=400, detail="Откат доступен только для подготовленного датасета")

    ok = await run_in_threadpool(pipeline.restore_last_processed_snapshot, dataset_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Нет изменений для отката")

    df = await run_in_threadpool(get_dataframe, dataset_id, DATA_DIR)

    from app.modules.smart_scanner import SmartScanner

    scanner = SmartScanner()
    scan_result = await run_in_threadpool(scanner.scan_dataset, df)
    scan_report = scan_result["scan_report"]

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
        action="prepare_undo",
        actor="user",
        details={},
    )

    total_pages = max(1, math.ceil(len(df) / limit))
    safe_page = min(page, total_pages)
    return generate_profile(df, page=safe_page, limit=limit)


@router.post("/demo/primary", response_model=DatasetUpload)
async def upload_primary_demo_dataset():
    repo_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    path = os.path.join(repo_root, "docs", "Первичка для анализа работа.xlsx")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Файл данных не найден: {path}")

    try:
        with open(path, "rb") as f:
            content = f.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать файл данных: {str(e)}")

    return await _ingest_dataset_bytes(content, os.path.basename(path))


@router.get("/{dataset_id}/variable_mapping", response_model=VariableMappingDocument)
def get_variable_mapping(dataset_id: str):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    mapping = load_variable_mapping(dataset_id)
    return VariableMappingDocument(dataset_id=dataset_id, mapping=mapping)


@router.put("/{dataset_id}/variable_mapping", response_model=VariableMappingDocument)
def put_variable_mapping(dataset_id: str, payload: VariableMappingUpdate):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    save_variable_mapping(dataset_id, payload.mapping)

    rebuild_and_save_semantics(
        dataset_id=dataset_id,
        base_dir=DATA_DIR,
        source="user",
    )
    rebuild_and_save_study_design(
        dataset_id=dataset_id,
        base_dir=DATA_DIR,
        source="user",
    )

    append_delta_log(
        base_dir=DATA_DIR,
        dataset_id=dataset_id,
        action="variable_mapping_update",
        actor="user",
        details={"count": len(payload.mapping or {})},
    )

    return VariableMappingDocument(dataset_id=dataset_id, mapping=payload.mapping)


@router.get("/{dataset_id}/design_review", response_model=DesignReviewDocument)
def get_design_review(dataset_id: str):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    artifact = load_design_review(DATA_DIR, dataset_id)
    return _design_review_document(dataset_id, artifact)


@router.post("/{dataset_id}/design_review/confirm", response_model=DesignReviewDocument)
def confirm_dataset_design_review(dataset_id: str, payload: Optional[DesignReviewAction] = None):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    payload = payload or DesignReviewAction()
    details = payload.details if isinstance(payload.details, dict) else {}
    artifact = confirm_design_review(
        DATA_DIR,
        dataset_id,
        actor=payload.actor or "user",
        source=payload.source or "ui",
        details=details,
    )

    append_delta_log(
        base_dir=DATA_DIR,
        dataset_id=dataset_id,
        action="design_review_confirm",
        actor=payload.actor or "user",
        details={
            "source": payload.source or "ui",
            "confirmed_at": artifact.get("confirmed_at"),
            "details": details,
        },
    )

    return _design_review_document(dataset_id, artifact)


@router.post("/{dataset_id}/design_review/revoke", response_model=DesignReviewDocument)
def revoke_dataset_design_review(dataset_id: str, payload: Optional[DesignReviewAction] = None):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    payload = payload or DesignReviewAction()
    details = payload.details if isinstance(payload.details, dict) else {}
    artifact = revoke_design_review(
        DATA_DIR,
        dataset_id,
        actor=payload.actor or "user",
        source=payload.source or "ui",
        reason=payload.reason,
        details=details,
    )

    append_delta_log(
        base_dir=DATA_DIR,
        dataset_id=dataset_id,
        action="design_review_revoke",
        actor=payload.actor or "user",
        details={
            "source": payload.source or "ui",
            "reason": payload.reason,
            "revoked_at": artifact.get("revoked_at"),
            "details": details,
        },
    )

    return _design_review_document(dataset_id, artifact)


@router.get("/{dataset_id}/analysis_set", response_model=AnalysisSetDocument)
def get_analysis_set_status(dataset_id: str):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    artifact = load_analysis_set(DATA_DIR, dataset_id)
    return _analysis_set_document(dataset_id, artifact)


@router.post("/{dataset_id}/analysis_set/freeze", response_model=AnalysisSetDocument)
def freeze_dataset_analysis_set(dataset_id: str, payload: Optional[AnalysisSetAction] = None):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    payload = payload or AnalysisSetAction()
    df = get_dataframe(dataset_id, DATA_DIR)
    try:
        artifact = freeze_analysis_set(
            DATA_DIR,
            dataset_id,
            df=df,
            mode=payload.mode,
            enforce=payload.enforce,
            required_non_missing=payload.required_non_missing,
            impute_columns=payload.impute_columns,
            actor=payload.actor or "user",
            source=payload.source or "ui",
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    append_delta_log(
        base_dir=DATA_DIR,
        dataset_id=dataset_id,
        action="analysis_set_freeze",
        actor=payload.actor or "user",
        details={
            "source": payload.source or "ui",
            "analysis_set_id": artifact.get("analysis_set_id"),
            "mode": artifact.get("mode"),
            "enforce": artifact.get("enforce"),
            "n_selected": artifact.get("n_selected"),
        },
    )

    return _analysis_set_document(dataset_id, artifact)


@router.post("/{dataset_id}/analysis_set/clear", response_model=AnalysisSetDocument)
def clear_dataset_analysis_set(dataset_id: str, payload: Optional[AnalysisSetAction] = None):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    payload = payload or AnalysisSetAction()
    clear_current_analysis_set(DATA_DIR, dataset_id)

    append_delta_log(
        base_dir=DATA_DIR,
        dataset_id=dataset_id,
        action="analysis_set_clear",
        actor=payload.actor or "user",
        details={
            "source": payload.source or "ui",
        },
    )

    artifact = load_analysis_set(DATA_DIR, dataset_id)
    return _analysis_set_document(dataset_id, artifact)

@router.post("/{dataset_id}/reparse", response_model=DatasetProfile)
def reparse_dataset(
    dataset_id: str,
    request: DatasetReparse,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000),
):
    # Retrieve raw source path
    # With pipeline, raw is always in source/original.raw
    upload_dir = os.path.join(DATA_DIR, dataset_id)

    meta = _load_dataset_meta(dataset_id)
    if meta.get("locked") is True:
        raise HTTPException(status_code=400, detail="Перепарсинг запрещён для подготовленного датасета")

    raw_path = os.path.join(upload_dir, "source", "original.raw")
    
    if not os.path.exists(raw_path): 
        # Fallback for old datasets
        file_path, _ = get_dataset_path(dataset_id, DATA_DIR)
        if not file_path: raise HTTPException(status_code=404, detail="Файл данных не найден")
        raw_path = file_path
        
    try:
        df, used_header = parse_file(raw_path, header_row=request.header_row, sheet_name=request.sheet_name)

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)
        
        # Create new processed snapshot (Overwrite stage 1)
        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"header_row": used_header, "sheet": request.sheet_name})

        mapping = load_variable_mapping(dataset_id)
        if mapping:
            update_variable_mapping_for_actions(
                dataset_id=dataset_id,
                mapping=mapping,
                actions=[],
                existing_columns=[str(c) for c in df.columns],
            )

        scan_result = scanner.scan_dataset(df)
        scan_report = scan_result["scan_report"]
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
            action="reparse",
            actor="user",
            details={"header_row": used_header, "sheet": request.sheet_name},
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось перепарсить файл: {str(e)}")
        
    total_pages = max(1, math.ceil(len(df) / limit))
    safe_page = min(page, total_pages)
    return generate_profile(df, page=safe_page, limit=limit)

@router.post("/{dataset_id}/modify", response_model=DatasetProfile)
def modify_dataset(
    dataset_id: str,
    modification: DatasetModification,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000),
):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
        actions = list((modification.actions or []))

        for action in actions:
            if action.type == "drop_col":
                if action.column and action.column in df.columns:
                    df = df.drop(columns=[action.column])
            elif action.type == "rename_col":
                if action.column and action.new_name and action.column in df.columns:
                    if action.new_name in df.columns and action.new_name != action.column:
                        raise ValueError(f"Column already exists: {action.new_name}")
                    df = df.rename(columns={action.column: action.new_name})
            elif action.type == "change_type":
                if action.column and action.new_type and action.column in df.columns:
                    if action.new_type == "numeric":
                        df[action.column] = pd.to_numeric(df[action.column], errors="coerce")
                    elif action.new_type == "datetime":
                        df[action.column] = pd.to_datetime(df[action.column], errors="coerce")
                    elif action.new_type in ("text", "categorical"):
                        df[action.column] = df[action.column].astype(str)
                    else:
                        raise ValueError(f"Unsupported new_type: {action.new_type}")
            elif action.type == "drop_row":
                if action.row_index is not None and isinstance(action.row_index, int):
                    if 0 <= action.row_index < len(df.index):
                        df = df.drop(index=action.row_index)
            elif action.type == "update_cell":
                if action.row_index is None or not isinstance(action.row_index, int):
                    continue
                if not action.column or action.column not in df.columns:
                    continue

                if 0 <= action.row_index < len(df.index):
                    v = action.value
                    if v == "":
                        v = None
                    v = _coerce_update_cell_value(df, column=action.column, value=v)
                    df.at[action.row_index, action.column] = v
            else:
                raise ValueError(f"Unknown modification type: {action.type}")

        df = df.reset_index(drop=True)

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)

        pipeline.create_processed_snapshot(
            dataset_id,
            df,
            cleaning_log={"action": "modify", "count": len(actions)}
        )

        mapping = load_variable_mapping(dataset_id)
        if mapping:
            update_variable_mapping_for_actions(
                dataset_id=dataset_id,
                mapping=mapping,
                actions=actions,
                existing_columns=[str(c) for c in df.columns],
            )
        scan_report = scanner.scan_dataset(df)["scan_report"]

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
            action="modify",
            actor="user",
            details={"actions": actions},
        )

        total_pages = max(1, math.ceil(len(df) / limit))
        safe_page = min(page, total_pages)
        return generate_profile(df, page=safe_page, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось изменить файл данных: {str(e)}")

class CleanCommand(BaseModel):
    column: str
    action: str


class ComputeColumnCommand(BaseModel):
    name: str
    op: Literal["difference", "indicator"]
    a: Optional[str] = None
    b: Optional[str] = None
    source: Optional[str] = None
    threshold: Optional[float] = None


class MiceImputeCommand(BaseModel):
    columns: List[str]
    max_iter: int = 10
    n_imputations: int = 5
    random_state: int = 42


@router.post("/{dataset_id}/impute_mice")
def impute_mice_api(dataset_id: str, cmd: MiceImputeCommand):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)

        columns = [c for c in (cmd.columns or []) if isinstance(c, str) and c]
        if not columns:
            raise ValueError("Список columns не должен быть пустым")

        missing_cols = [c for c in columns if c not in df.columns]
        if missing_cols:
            raise ValueError(f"Столбцы не найдены: {missing_cols}")

        if len(columns) > 50:
            raise ValueError("MICE поддерживает до 50 столбцов за один запуск")

        numeric_df = df[columns].apply(pd.to_numeric, errors="coerce")

        has_missing = bool(numeric_df.isna().any().any())
        if not has_missing:
            return generate_profile(df)

        try:
            from sklearn.experimental import enable_iterative_imputer  # noqa: F401
            from sklearn.impute import IterativeImputer
        except Exception as e:
            raise ValueError(f"Зависимости для MICE недоступны: {str(e)}")

        max_iter = int(cmd.max_iter)
        n_imputations = int(cmd.n_imputations)
        random_state = int(cmd.random_state)

        if max_iter < 1 or max_iter > 50:
            raise ValueError("max_iter должен быть в диапазоне от 1 до 50")
        if n_imputations < 1 or n_imputations > 20:
            raise ValueError("n_imputations должен быть в диапазоне от 1 до 20")

        matrices = []
        for i in range(n_imputations):
            imputer = IterativeImputer(
                max_iter=max_iter,
                random_state=random_state + i,
                sample_posterior=True,
                skip_complete=True
            )
            imputed = imputer.fit_transform(numeric_df)
            matrices.append(imputed)

        imputed_mean = sum(matrices) / float(len(matrices))
        df.loc[:, columns] = imputed_mean

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)

        pipeline.create_processed_snapshot(
            dataset_id,
            df,
            cleaning_log={
                "action": "mice_imputation",
                "columns": columns,
                "max_iter": max_iter,
                "n_imputations": n_imputations
            }
        )

        scan_report = scanner.scan_dataset(df)["scan_report"]

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
            action="mice_imputation",
            actor="user",
            details={
                "columns": columns,
                "max_iter": max_iter,
                "n_imputations": n_imputations,
            },
        )

        return generate_profile(df)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось выполнить MICE-импутацию: {str(e)}")

@router.post("/{dataset_id}/clean_column")
def clean_column_api(dataset_id: str, cmd: CleanCommand):
    """
    Apply a cleaning action to a column.
    """
    try:
        # 1. Load Data
        df = get_dataframe(dataset_id, DATA_DIR)

        if cmd.column not in df.columns:
            raise ValueError(f"Столбец не найден: {cmd.column}")
        
        # 2. Apply Operation
        if cmd.action == "to_numeric":
            df[cmd.column] = pd.to_numeric(df[cmd.column], errors='coerce')
        elif cmd.action == "normalize_categories":
            from app.modules.data_normalizer import normalize_categorical_series
            df[cmd.column] = normalize_categorical_series(df[cmd.column])
        elif cmd.action == "fill_mean":
            if pd.api.types.is_numeric_dtype(df[cmd.column]):
                df[cmd.column] = df[cmd.column].fillna(df[cmd.column].mean())
            else:
                raise ValueError("Действие fill_mean поддерживается только для числовых столбцов")
        elif cmd.action == "fill_median":
            if pd.api.types.is_numeric_dtype(df[cmd.column]):
                df[cmd.column] = df[cmd.column].fillna(df[cmd.column].median())
            else:
                raise ValueError("Действие fill_median поддерживается только для числовых столбцов")
        elif cmd.action == "fill_mode":
            mode_series = df[cmd.column].mode(dropna=True)
            if mode_series.empty:
                raise ValueError("Для fill_mode требуется хотя бы одно ненулевое значение")
            df[cmd.column] = df[cmd.column].fillna(mode_series.iloc[0])
        elif cmd.action == "fill_locf":
            df[cmd.column] = df[cmd.column].ffill()
        elif cmd.action == "fill_nocb":
            df[cmd.column] = df[cmd.column].bfill()
        elif cmd.action == "drop_na":
            df = df.dropna(subset=[cmd.column])
        else:
            raise ValueError(f"Неизвестное действие: {cmd.action}")

        df = df.reset_index(drop=True)
             
        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)

        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"action": cmd.action, "column": cmd.column})
        
        # 4. Re-Scan (Update Report)
        scan_report = scanner.scan_dataset(df)["scan_report"]
        
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
            action="clean_column",
            actor="user",
            details={"column": cmd.column, "action": cmd.action},
        )
            
        return generate_profile(df)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось выполнить очистку: {str(e)}")


@router.post("/{dataset_id}/prepare/cleaning/interactive/apply", response_model=InteractiveCleaningApplyResponse)
@router.post("/{dataset_id}/cleaning/interactive/apply", response_model=InteractiveCleaningApplyResponse, include_in_schema=False)
def apply_interactive_cleaning_api(
    dataset_id: str,
    payload: InteractiveCleaningApplyRequest,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000),
):
    try:
        meta = _load_dataset_meta(dataset_id)
        if meta.get("locked") is not True:
            raise ValueError("Интерактивная очистка доступна только для подготовленного датасета (/prepare).")

        df = get_dataframe(dataset_id, DATA_DIR)
        operations_in = payload.operations if isinstance(payload.operations, list) else []
        if not operations_in:
            raise ValueError("operations не должен быть пустым")

        operations_log: List[Dict[str, Any]] = []
        mapping_actions: List[ModificationAction] = []
        applied_count = 0
        skipped_count = 0

        for idx, op in enumerate(operations_in):
            action_raw = str(op.action or "").strip()
            action = _normalize_interactive_clean_action(action_raw)
            column = str(op.column or "").strip() or None
            enabled = bool(op.enabled)
            op_id = str(op.operation_id or "").strip() or f"op_{idx + 1}"

            log_entry: Dict[str, Any] = {
                "operation_id": op_id,
                "column": column,
                "action": action or action_raw,
                "enabled": enabled,
            }

            if not enabled:
                skipped_count += 1
                log_entry["status"] = "skipped"
                log_entry["reason"] = "disabled"
                operations_log.append(log_entry)
                continue

            if not action:
                raise ValueError(f"operations[{idx}]: неподдерживаемое действие '{action_raw}'")

            before_rows = int(len(df))
            before_cols = int(len(df.columns))
            df = _apply_interactive_clean_action(df, column=column, action=action)
            after_rows = int(len(df))
            after_cols = int(len(df.columns))
            applied_count += 1

            if action == "drop_col" and column:
                mapping_actions.append(ModificationAction(type="drop_col", column=column))

            log_entry["status"] = "applied"
            log_entry["rows_delta"] = int(after_rows - before_rows)
            log_entry["cols_delta"] = int(after_cols - before_cols)
            operations_log.append(log_entry)

        if applied_count <= 0:
            raise ValueError("Нет выбранных операций для применения")

        df = df.reset_index(drop=True)

        from app.modules.smart_scanner import SmartScanner

        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)

        clean_notes = _dedupe_str_list(payload.notes)
        clean_actor = str(payload.actor or "user").strip() or "user"
        clean_source = str(payload.source or "interactive_prepare_ui").strip() or "interactive_prepare_ui"
        cleaning_log = {
            "action": "interactive_cleaning_apply",
            "actor": clean_actor,
            "source": clean_source,
            "notes": clean_notes,
            "count": int(applied_count),
            "operations": operations_log,
        }
        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log=cleaning_log)

        mapping = load_variable_mapping(dataset_id)
        if mapping and mapping_actions:
            update_variable_mapping_for_actions(
                dataset_id=dataset_id,
                mapping=mapping,
                actions=mapping_actions,
                existing_columns=[str(c) for c in df.columns],
            )

        scan_report = scanner.scan_dataset(df)["scan_report"]
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
            action="interactive_cleaning_apply",
            actor=clean_actor,
            details={
                "source": clean_source,
                "applied_count": int(applied_count),
                "skipped_count": int(skipped_count),
            },
        )

        total_pages = max(1, math.ceil(len(df) / limit))
        safe_page = min(page, total_pages)
        profile = generate_profile(df, page=safe_page, limit=limit)
        return InteractiveCleaningApplyResponse(
            dataset_id=str(dataset_id),
            applied_count=int(applied_count),
            skipped_count=int(skipped_count),
            operations=operations_log,
            profile=profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось применить интерактивную очистку: {str(e)}")


@router.post("/{dataset_id}/compute_column", response_model=DatasetProfile)
def compute_column_api(dataset_id: str, cmd: ComputeColumnCommand):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)

        name = str(cmd.name or "").strip()
        if not name:
            raise ValueError("name не должен быть пустым")
        if name in df.columns:
            raise ValueError(f"Колонка уже существует: {name}")

        if cmd.op == "difference":
            a = str(cmd.a or "").strip()
            b = str(cmd.b or "").strip()
            if not a or not b:
                raise ValueError("Для difference нужны поля a и b")
            if a not in df.columns or b not in df.columns:
                raise ValueError("Одна из колонок не найдена")
            df[name] = pd.to_numeric(df[a], errors="coerce") - pd.to_numeric(df[b], errors="coerce")

        elif cmd.op == "indicator":
            source = str(cmd.source or "").strip()
            if not source:
                raise ValueError("Для indicator нужен source")
            if source not in df.columns:
                raise ValueError("Колонка source не найдена")
            threshold = cmd.threshold
            if threshold is None:
                raise ValueError("Для indicator нужен threshold")
            s = pd.to_numeric(df[source], errors="coerce")
            df[name] = (s >= float(threshold)).astype("int64")
        else:
            raise ValueError(f"Неизвестная операция: {cmd.op}")

        df = df.reset_index(drop=True)

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)

        pipeline.create_processed_snapshot(
            dataset_id,
            df,
            cleaning_log={"action": "compute_column", "op": cmd.op, "name": name},
        )

        scan_report = scanner.scan_dataset(df)["scan_report"]
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
            action="compute_column",
            actor="user",
            details={"op": cmd.op, "name": name},
        )

        return generate_profile(df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось добавить колонку: {str(e)}")

@router.get("/{dataset_id}/scan_report")
def get_scan_report(dataset_id: str):
    try:
        path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        if not os.path.exists(path):
            return {"status": "no_report"}
            
        with open(path, "r") as f:
            data = json.load(f)
        return _sanitize_json(data)
    except Exception as e:
        raise HTTPException(status_code=404, detail="Отчёт не найден")


@router.get("/{dataset_id}/cleaning_log")
def get_cleaning_log(dataset_id: str):
    try:
        path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "cleaning_log.json")
        if not os.path.exists(path):
            return {"status": "no_log"}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _sanitize_json(data)
    except Exception:
        raise HTTPException(status_code=404, detail="Лог очистки не найден")


@router.get("/{dataset_id}/delta_log")
def get_delta_log(dataset_id: str):
    try:
        path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "delta_log.json")
        if not os.path.exists(path):
            return {"status": "no_log"}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _sanitize_json(data)
    except Exception:
        raise HTTPException(status_code=404, detail="Лог изменений не найден")


@router.get("/{dataset_id}/semantics")
def get_semantics(dataset_id: str):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    semantics = load_semantics(DATA_DIR, dataset_id)
    if semantics is None:
        scan_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        scan_report = None
        if os.path.exists(scan_path):
            try:
                with open(scan_path, "r", encoding="utf-8") as f:
                    scan_report = json.load(f)
            except Exception:
                scan_report = None

        semantics = rebuild_and_save_semantics(
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

    return _sanitize_json(semantics or {})


@router.get("/{dataset_id}/export/cleaned")
async def export_cleaned_dataset(
    dataset_id: str,
    format: str = Query("xlsx", description="Export format: xlsx or csv"),
):
    """
    Export the cleaned/processed dataset used for analysis.
    Returns an Excel (xlsx) or CSV file built from processed Parquet.
    """
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
        fmt = str(format or "xlsx").strip().lower()
        if fmt not in {"xlsx", "csv"}:
            raise HTTPException(status_code=400, detail="Поддерживаются только xlsx или csv")

        if fmt == "csv":
            content = df.to_csv(index=False).encode("utf-8")
            filename = f"{dataset_id}_cleaned.csv"
            return Response(
                content=content,
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
            )

        import io

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="cleaned")
        buffer.seek(0)
        filename = f"{dataset_id}_cleaned.xlsx"
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename=\"{filename}\"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось экспортировать датасет: {str(e)}")


@router.get("/{dataset_id}/study_design")
def get_study_design(dataset_id: str, response: Response = None):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    design = load_study_design(DATA_DIR, dataset_id)
    if design is None:
        scan_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        scan_report = None
        if os.path.exists(scan_path):
            try:
                with open(scan_path, "r", encoding="utf-8") as f:
                    scan_report = json.load(f)
            except Exception:
                scan_report = None

        design = rebuild_and_save_study_design(
            dataset_id=dataset_id,
            base_dir=DATA_DIR,
            scan_report=scan_report,
            source="auto",
        )

    design_out = _sanitize_json(design or {})
    revision = _study_design_revision(design_out if isinstance(design_out, dict) else {})
    if response is not None:
        response.headers["ETag"] = _study_design_etag(revision)
        response.headers["X-Study-Design-Revision"] = str(revision)
    return design_out


@router.put("/{dataset_id}/study_design")
def put_study_design(
    dataset_id: str,
    payload: StudyDesignUpdateAction,
    response: Response,
    if_match: Optional[str] = Header(None),
):
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if not os.path.isdir(ds_dir):
        raise HTTPException(status_code=404, detail="Файл данных не найден")

    current = load_study_design(DATA_DIR, dataset_id)
    if not isinstance(current, dict):
        current = rebuild_and_save_study_design(
            dataset_id=dataset_id,
            base_dir=DATA_DIR,
            source="auto",
        )
    if not isinstance(current, dict) or not current:
        raise HTTPException(status_code=500, detail="Не удалось загрузить study_design")

    expected_revision = payload.expected_revision
    if expected_revision is None:
        expected_revision = _parse_study_design_etag(if_match)
    current_revision = _study_design_revision(current)

    if expected_revision is not None and int(expected_revision) != current_revision:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Конфликт версии study_design: expected_revision={int(expected_revision)}, "
                f"current_revision={current_revision}. Обновите дизайн и повторите."
            ),
        )

    incoming_design = _model_to_dict(payload.design)
    incoming_policy = dict(payload.analysis_policy or {}) if isinstance(payload.analysis_policy, dict) else {}
    incoming_notes = _dedupe_str_list(payload.notes)
    if not incoming_design and not incoming_policy and not incoming_notes:
        raise HTTPException(status_code=400, detail="Передайте хотя бы одно изменение: design/analysis_policy/notes")

    current_design = current.get("design") if isinstance(current.get("design"), dict) else {}
    next_design: Dict[str, Any] = dict(current_design)
    columns_meta = current.get("columns") if isinstance(current.get("columns"), dict) else {}
    available_cols = set(columns_meta.keys()) if isinstance(columns_meta, dict) else set()
    if not available_cols:
        available_cols = set(get_dataset_columns(dataset_id, DATA_DIR))
        columns_meta = {}

    try:
        if "design_type" in incoming_design:
            next_design["design_type"] = str(incoming_design.get("design_type") or "").strip() or "cross_sectional"
        if "repeated_measures" in incoming_design:
            next_design["repeated_measures"] = bool(incoming_design.get("repeated_measures"))
        if "group_column" in incoming_design:
            next_design["group_column"] = _validate_column_exists(
                incoming_design.get("group_column"),
                key="design.group_column",
                available_cols=available_cols,
            )
        if "time_column" in incoming_design:
            next_design["time_column"] = _validate_column_exists(
                incoming_design.get("time_column"),
                key="design.time_column",
                available_cols=available_cols,
            )
        if "subject_column" in incoming_design:
            next_design["subject_column"] = _validate_column_exists(
                incoming_design.get("subject_column"),
                key="design.subject_column",
                available_cols=available_cols,
            )
        if "id_like_columns" in incoming_design:
            next_design["id_like_columns"] = _validate_column_list(
                incoming_design.get("id_like_columns"),
                key="design.id_like_columns",
                available_cols=available_cols,
            )
        if "outcomes" in incoming_design:
            next_design["outcomes"] = _validate_column_list(
                incoming_design.get("outcomes"),
                key="design.outcomes",
                available_cols=available_cols,
                kind_check="numeric",
                columns_meta=columns_meta,
            )
        if "categorical_outcomes" in incoming_design:
            next_design["categorical_outcomes"] = _validate_column_list(
                incoming_design.get("categorical_outcomes"),
                key="design.categorical_outcomes",
                available_cols=available_cols,
                kind_check="categorical",
                columns_meta=columns_meta,
            )
        if "predictors" in incoming_design:
            next_design["predictors"] = _validate_column_list(
                incoming_design.get("predictors"),
                key="design.predictors",
                available_cols=available_cols,
            )
        if "endpoint_groups" in incoming_design:
            endpoint_groups: List[Dict[str, Any]] = []
            raw_groups = incoming_design.get("endpoint_groups")
            if raw_groups is not None:
                for idx, item in enumerate(raw_groups if isinstance(raw_groups, list) else []):
                    item_dict = _model_to_dict(item)
                    endpoint = str(item_dict.get("endpoint") or "").strip()
                    if not endpoint:
                        raise ValueError(f"design.endpoint_groups[{idx}].endpoint не должен быть пустым")
                    cols = _validate_column_list(
                        item_dict.get("columns"),
                        key=f"design.endpoint_groups[{idx}].columns",
                        available_cols=available_cols,
                    )
                    tps = _dedupe_str_list(item_dict.get("timepoints"))
                    endpoint_groups.append({"endpoint": endpoint, "columns": cols, "timepoints": tps})
            next_design["endpoint_groups"] = endpoint_groups

        current_policy = current.get("analysis_policy") if isinstance(current.get("analysis_policy"), dict) else {}
        next_policy = dict(current_policy)
        for key, value in incoming_policy.items():
            if key == "alpha":
                next_policy["alpha"] = _validate_alpha(value)
            elif key in {"max_batch_targets", "max_descriptive_targets", "max_table1_categorical", "max_protocol_steps"}:
                next_policy[key] = _validate_positive_int(value, key)
            elif key in {"exploratory_mode", "allow_data_mining"}:
                next_policy[key] = bool(value)
            elif key in {"multiplicity_correction", "post_hoc", "post_hoc_correction"}:
                next_policy[key] = str(value or "").strip() or "none"
            else:
                next_policy[key] = value
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = datetime.utcnow().isoformat()
    next_revision = current_revision + 1
    next_notes = _dedupe_str_list([*(current.get("notes") if isinstance(current.get("notes"), list) else []), *incoming_notes])

    updated = dict(current)
    updated["dataset_id"] = str(dataset_id)
    updated["version"] = int(current.get("version") or 1)
    updated["revision"] = int(next_revision)
    updated["source"] = str(payload.source or "user").strip() or "user"
    updated["design"] = next_design
    updated["analysis_policy"] = next_policy
    updated["notes"] = next_notes
    updated["updated_at"] = now
    updated["updated_by"] = str(payload.actor or "user").strip() or "user"
    updated["update_reason"] = str(payload.reason or "").strip() or None
    if not isinstance(updated.get("generated_at"), str):
        updated["generated_at"] = now
    if not isinstance(updated.get("summary"), dict):
        updated["summary"] = {
            "n_rows": None,
            "n_cols": len(columns_meta) if isinstance(columns_meta, dict) else len(available_cols),
        }

    save_study_design(DATA_DIR, dataset_id, updated)

    design_review_artifact = load_design_review(DATA_DIR, dataset_id)
    design_review_revoked = False
    if isinstance(design_review_artifact, dict) and bool(design_review_artifact.get("confirmed")):
        revoke_design_review(
            DATA_DIR,
            dataset_id,
            actor=payload.actor or "user",
            source=payload.source or "study_design_update",
            reason=payload.reason or "study_design_updated",
            details={"auto_revoked": True, "study_design_revision": next_revision},
        )
        design_review_revoked = True

    append_delta_log(
        base_dir=DATA_DIR,
        dataset_id=dataset_id,
        action="study_design_update",
        actor=payload.actor or "user",
        details={
            "source": payload.source or "ui",
            "reason": payload.reason,
            "from_revision": current_revision,
            "to_revision": next_revision,
            "design_review_revoked": design_review_revoked,
        },
    )

    output = _sanitize_json(updated)
    if isinstance(output, dict):
        output["design_review_revoked"] = bool(design_review_revoked)
    response.headers["ETag"] = _study_design_etag(next_revision)
    response.headers["X-Study-Design-Revision"] = str(next_revision)
    return output

@router.get("/{dataset_id}", response_model=DatasetProfile)
def get_dataset(
    dataset_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000),
    head_col_offset: int = Query(0, ge=0),
    head_col_limit: Optional[int] = Query(None, ge=1, le=400),
):
    try:
        df = get_dataframe(dataset_id, DATA_DIR)
        df.columns = df.columns.astype(str)
        return generate_profile(
            df,
            page=page,
            limit=limit,
            head_col_offset=head_col_offset,
            head_col_limit=head_col_limit,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось загрузить файл данных: {str(e)}")

@router.get("/{dataset_id}/columns")
def list_dataset_columns(
    dataset_id: str,
    q: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=2000),
):
    cols = get_dataset_columns(dataset_id, DATA_DIR)
    if q:
        q_l = str(q).lower()
        cols = [c for c in cols if q_l in c.lower()]

    total = int(len(cols))
    start = int(offset)
    end = start + int(limit)
    return {
        "columns": cols[start:end],
        "total": total,
        "offset": start,
        "limit": int(limit),
    }

@router.get("/{dataset_id}/content")
def get_dataset_content(
    dataset_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=2000),
    col_offset: int = Query(0, ge=0),
    col_limit: int = Query(120, ge=1, le=400),
    sheet: str = None,
):
    """
    Returns the dataset content (rows) with pagination.
    Used by the Data View component.
    """
    # Pagination
    start = (page - 1) * limit
    end = start + limit

    all_cols = get_dataset_columns(dataset_id, DATA_DIR)
    total_cols = int(len(all_cols))
    safe_col_offset = max(0, int(col_offset))
    safe_col_offset = min(safe_col_offset, max(0, total_cols - 1)) if total_cols else 0
    safe_col_limit = max(1, min(400, int(col_limit)))
    cols = all_cols[safe_col_offset : safe_col_offset + safe_col_limit]

    df_slice = get_dataframe_window(dataset_id, DATA_DIR, columns=cols, start=start, end=end)
    data_slice = df_slice.replace({pd.NA: None, float('nan'): None}).to_dict(orient="records")
    
    return {
        "data": data_slice,
        "total_rows": int(get_dataset_row_count(dataset_id, DATA_DIR)),
        "page": page,
        "limit": limit,
        "columns": cols,
        "total_columns": total_cols,
        "col_offset": safe_col_offset,
        "col_limit": safe_col_limit,
    }
