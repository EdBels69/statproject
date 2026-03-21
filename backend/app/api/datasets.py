import shutil
import uuid
import os
import pandas as pd
import aiofiles
import json
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.concurrency import run_in_threadpool
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

from app.schemas.dataset import (
    DatasetUpload,
    DatasetProfile,
    DatasetReparse,
    DatasetModification,
    ColumnInfo,
    VariableMappingUpdate,
    VariableMappingDocument,
)
from app.modules.parsers import parse_file, get_dataset_path, get_dataframe, get_dataset_columns, get_dataset_row_count, get_dataframe_window
from app.core.pipeline import PipelineManager
from app.api.deps import require_roles
from pydantic import BaseModel
import math

router = APIRouter()

WORKSPACE_DIR = os.getenv("STATWIZARD_WORKSPACE_DIR", "workspace")
DATA_DIR = os.path.join(WORKSPACE_DIR, "datasets")
pipeline = PipelineManager(DATA_DIR)


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


def _normalize_dataset_timestamp(meta: Dict[str, Any]) -> Optional[str]:
    if not isinstance(meta, dict):
        return None
    for key in ("ingest_timestamp", "uploaded_at", "created_at", "upload_date"):
        value = meta.get(key)
        if value:
            return str(value)
    return None


async def _ingest_dataset_bytes(content: bytes, filename: str) -> DatasetUpload:
    dataset_id = str(uuid.uuid4())
    try:
        raw_path = pipeline.save_source(dataset_id, content, filename)

        def parse_logic():
            return parse_file(raw_path, header_row=0, original_filename=filename)

        df, used_header = await run_in_threadpool(parse_logic)

        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = await run_in_threadpool(scanner.optimize_dtypes, df)

        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"header_row": used_header})

        scan_result = await run_in_threadpool(scanner.scan_dataset, df)
        profile_data = scan_result["profile"]
        scan_report = scan_result["scan_report"]

        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        pipeline.write_json_atomic(report_path, _sanitize_json(scan_report), allow_nan=False)
    except Exception as e:
        shutil.rmtree(os.path.join(DATA_DIR, dataset_id), ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"Обработка файла не удалась: {str(e)}")

    return DatasetUpload(id=dataset_id, filename=filename, profile=profile_data)


def get_variable_mapping_path(dataset_id: str) -> str:
    return os.path.join(DATA_DIR, dataset_id, "processed", "variable_mapping.json")


# ── Data Wrangling Helpers ────────────────────────────────────────────────────

_WRANGLING_ACTIONS = frozenset(
    {"split_column", "recode_values", "derive_column", "bin_variable", "string_clean"}
)


def _append_transform_log(
    *,
    dataset_id: str,
    actions: List[Any],
    rows_before: int,
    cols_before: int,
    rows_after: int,
    cols_after: int,
) -> None:
    """Append wrangling-action records to processed/transform_log.json."""
    wrangling = [a for a in actions if getattr(a, "type", None) in _WRANGLING_ACTIONS]
    if not wrangling:
        return

    log_path = os.path.join(DATA_DIR, dataset_id, "processed", "transform_log.json")
    entries: List[Dict[str, Any]] = []
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, list):
                entries = existing
    except Exception:
        entries = []

    for a in wrangling:
        entries.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "action": a.type,
                "column": a.column,
                "config": getattr(a, "config", None) or {},
                "rows_before": rows_before,
                "rows_after": rows_after,
                "cols_before": cols_before,
                "cols_after": cols_after,
            }
        )

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass  # transform_log is best-effort


def _action_split_column(df: "pd.DataFrame", action: Any) -> "pd.DataFrame":
    """
    split_column: разбить значения колонки по разделителю.

    config:
        separator : str  — разделитель (default ",")
        mode      : "rows" | "columns"
        trim      : bool — убрать пробелы (default True)
        prefix    : str  — префикс новых колонок (только mode=columns)
    """
    col = action.column
    if not col or col not in df.columns:
        raise ValueError(f"Колонка не найдена: {col}")

    cfg = getattr(action, "config", None) or {}
    sep = str(cfg.get("separator", ","))
    mode = str(cfg.get("mode", "rows"))
    trim = bool(cfg.get("trim", True))
    prefix = str(cfg.get("prefix", f"{col}_"))

    # Сохраняем NaN, не превращая в строку "nan"
    series = df[col].astype(str).where(df[col].notna(), other=None)
    split_series = series.str.split(sep)
    if trim:
        split_series = split_series.apply(
            lambda parts: [p.strip() for p in parts] if isinstance(parts, list) else parts
        )

    if mode == "rows":
        df = df.assign(**{col: split_series}).explode(col).reset_index(drop=True)
    elif mode == "columns":
        expanded = split_series.apply(pd.Series)
        expanded.columns = [f"{prefix}{i + 1}" for i in range(len(expanded.columns))]
        df = pd.concat([df, expanded], axis=1)
    else:
        raise ValueError(f"Неизвестный mode для split_column: {mode}")

    return df


def _action_recode_values(df: "pd.DataFrame", action: Any) -> "pd.DataFrame":
    """
    recode_values: перекодировать значения колонки по словарю.

    config:
        mapping  : dict  — {"старое": "новое", ...}
        unmapped : "keep" | "null"  (default "keep")
    """
    col = action.column
    if not col or col not in df.columns:
        raise ValueError(f"Колонка не найдена: {col}")

    cfg = getattr(action, "config", None) or {}
    mapping: Dict[str, Any] = cfg.get("mapping") or {}
    unmapped = str(cfg.get("unmapped", "keep"))

    if not mapping:
        raise ValueError("Для recode_values нужен непустой mapping")

    # Сохраняем NaN, не превращая в строку "nan"
    str_series = df[col].astype(str).where(df[col].notna(), other=None)

    if unmapped == "keep":
        # .replace() оставляет нематченные значения на месте
        df[col] = str_series.replace(mapping)
    else:
        # unmapped="null" — нематченные станут NaN
        mapped = str_series.map(mapping)
        df[col] = mapped

    return df


def _action_derive_column(df: "pd.DataFrame", action: Any) -> "pd.DataFrame":
    """
    derive_column: создать новую колонку по формуле через pd.DataFrame.eval().

    config:
        formula        : str
        source_columns : list[str]
    """
    new_col = action.column
    if not new_col:
        raise ValueError("Нужно указать column — имя новой колонки")

    cfg = getattr(action, "config", None) or {}
    formula = str(cfg.get("formula", "")).strip()
    if not formula:
        raise ValueError("Для derive_column нужна формула в config.formula")

    source_columns = cfg.get("source_columns") or []
    for src in source_columns:
        if src not in df.columns:
            raise ValueError(f"Исходная колонка не найдена: {src}")

    try:
        result = df.eval(formula)
    except Exception as e:
        raise ValueError(f"Ошибка в формуле: {e}")

    df[new_col] = result
    return df


def _action_bin_variable(df: "pd.DataFrame", action: Any) -> "pd.DataFrame":
    """
    bin_variable: разбить числовую переменную на категориальные группы.

    config:
        new_column : str
        method     : "custom" | "equal_width" | "quantile"
        bins       : list[float]  (для custom)
        labels     : list[str]
        n_bins     : int  (default 4)
    """
    col = action.column
    if not col or col not in df.columns:
        raise ValueError(f"Колонка не найдена: {col}")

    cfg = getattr(action, "config", None) or {}
    new_col = str(cfg.get("new_column", f"{col}_bin"))
    method = str(cfg.get("method", "equal_width"))
    n_bins = int(cfg.get("n_bins", 4))
    bins = cfg.get("bins")
    labels = cfg.get("labels") or None

    numeric_col = pd.to_numeric(df[col], errors="coerce")

    if method == "custom":
        if not bins or len(bins) < 2:
            raise ValueError("Для method=custom нужен список bins с минимум 2 значениями")
        df[new_col] = pd.cut(numeric_col, bins=bins, labels=labels, include_lowest=True)
    elif method == "equal_width":
        df[new_col] = pd.cut(numeric_col, bins=n_bins, labels=labels)
    elif method == "quantile":
        df[new_col] = pd.qcut(numeric_col, q=n_bins, labels=labels, duplicates="drop")
    else:
        raise ValueError(f"Неизвестный method для bin_variable: {method}")

    df[new_col] = df[new_col].astype(str).replace("nan", None)
    return df


def _action_string_clean(df: "pd.DataFrame", action: Any) -> "pd.DataFrame":
    """
    string_clean: строковые операции над колонкой.

    config:
        operations   : list[str]  — ["trim", "lowercase", "uppercase", "replace"]
        replace_from : str
        replace_to   : str  (default "")
    """
    col = action.column
    if not col or col not in df.columns:
        raise ValueError(f"Колонка не найдена: {col}")

    cfg = getattr(action, "config", None) or {}
    operations = list(cfg.get("operations") or [])
    replace_from = str(cfg.get("replace_from", ""))
    replace_to = str(cfg.get("replace_to", ""))

    # Сохраняем NaN как NaN, не превращая в строку "nan"
    mask = df[col].notna()
    series = df[col].copy()
    series.loc[mask] = series.loc[mask].astype(str)

    for op in operations:
        if op == "trim":
            series.loc[mask] = series.loc[mask].str.strip()
        elif op == "lowercase":
            series.loc[mask] = series.loc[mask].str.lower()
        elif op == "uppercase":
            series.loc[mask] = series.loc[mask].str.upper()
        elif op == "replace":
            if replace_from:
                series.loc[mask] = series.loc[mask].str.replace(replace_from, replace_to, regex=False)
        else:
            raise ValueError(f"Неизвестная операция string_clean: {op}")

    df[col] = series
    return df


# ─────────────────────────────────────────────────────────────────────────────


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
    for dataset_id in os.listdir(DATA_DIR):
        ds_dir = os.path.join(DATA_DIR, dataset_id)
        if not os.path.isdir(ds_dir): continue
        
        # Check source metadata first
        meta_path = os.path.join(ds_dir, "source", "meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    uploaded_at = _normalize_dataset_timestamp(meta)
                    datasets.append({
                        "id": dataset_id, 
                        "filename": meta.get("original_filename", "unknown"),
                        "uploaded_at": uploaded_at,
                        "created_at": uploaded_at,
                    })
                continue
            except:
                pass
                
        # Fallback to old flat structure (Migration support)
        files = [f for f in os.listdir(ds_dir) if not f.endswith('.json') and f != "processed.csv" and not os.path.isdir(os.path.join(ds_dir, f))]
        if files:
            datasets.append({"id": dataset_id, "filename": files[0], "uploaded_at": None, "created_at": None})
            
    return datasets


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: str, _user: dict = Depends(require_roles(["admin"]))):
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
async def upload_dataset(file: UploadFile = File(...)):
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
    return await _ingest_dataset_bytes(content, file.filename)


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

    return VariableMappingDocument(dataset_id=dataset_id, mapping=payload.mapping)

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

        rows_before = len(df)
        cols_before = len(df.columns)

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
                    df.at[action.row_index, action.column] = v

            # ── Data Wrangling Actions ─────────────────────────────────────────
            elif action.type == "split_column":
                df = _action_split_column(df, action)
            elif action.type == "recode_values":
                df = _action_recode_values(df, action)
            elif action.type == "derive_column":
                df = _action_derive_column(df, action)
            elif action.type == "bin_variable":
                df = _action_bin_variable(df, action)
            elif action.type == "string_clean":
                df = _action_string_clean(df, action)
            # ──────────────────────────────────────────────────────────────────
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

        _append_transform_log(
            dataset_id=dataset_id,
            actions=actions,
            rows_before=rows_before,
            cols_before=cols_before,
            rows_after=len(df),
            cols_after=len(df.columns),
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
        
        # 2. Apply Operation
        if cmd.action == "to_numeric":
            df[cmd.column] = pd.to_numeric(df[cmd.column], errors='coerce')
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
             
        from app.modules.smart_scanner import SmartScanner
        scanner = SmartScanner()
        df = scanner.optimize_dtypes(df)

        pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"action": cmd.action, "column": cmd.column})
        
        # 4. Re-Scan (Update Report)
        scan_report = scanner.scan_dataset(df)["scan_report"]
        
        report_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "scan_report.json")
        pipeline.write_json_atomic(report_path, _sanitize_json(scan_report), allow_nan=False)
            
        return generate_profile(df)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось выполнить очистку: {str(e)}")


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


@router.get("/{dataset_id}/methods_text")
def get_methods_text(dataset_id: str, dataset_name: Optional[str] = None):
    """
    Returns an auto-generated Methods paragraph based on the wrangling
    transform_log.json recorded during dataset preprocessing.
    """
    from app.modules.reporting import generate_methods_section

    log_path = os.path.join(pipeline.get_dataset_dir(dataset_id), "processed", "transform_log.json")
    transform_log: List[Dict[str, Any]] = []
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                transform_log = json.load(f)
    except Exception:
        pass

    name = dataset_name or f"dataset {dataset_id[:8]}"
    text = generate_methods_section(transform_log, dataset_name=name)
    return {"methods_text": text, "steps": len(transform_log)}
