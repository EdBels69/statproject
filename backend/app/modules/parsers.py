import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Tuple, Optional, Any

import pandas as pd

DEFAULT_PROCESSED_TTL_HOURS = 72


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class DatasetMetadata:
    header_row: int = 0
    sheet_name: Optional[str] = None
    version: int = 1
    profile_version: int = 0
    modification_version: int = 0
    last_profile_at: Optional[str] = None
    last_modified_at: str = field(default_factory=_now_iso)
    original_filename: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DatasetMetadata":
        defaults = cls()
        base = asdict(defaults)
        base.update(payload or {})
        return cls(**base)

    def bump_profile(self) -> None:
        self.profile_version += 1
        self.last_profile_at = _now_iso()

    def bump_modification(self) -> None:
        self.modification_version += 1
        self.version += 1
        self.last_modified_at = _now_iso()


DATAFRAME_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_LOCK = Lock()


def get_dataset_path(dataset_id: str, base_dir: str) -> Tuple[Optional[str], str]:
    """Return (path_to_file, upload_directory) for a dataset."""
    upload_dir = os.path.join(base_dir, dataset_id)
    if not os.path.exists(upload_dir):
        return None, upload_dir

    # Prioritize original uploaded file (not metadata, not processed)
    files = [f for f in os.listdir(upload_dir) if not f.endswith('.json') and f != "processed.csv"]
    if not files:
        return None, upload_dir

    return os.path.join(upload_dir, files[0]), upload_dir

def parse_file(file_path: str, header_row: int = 0, sheet_name: str = None) -> Tuple[pd.DataFrame, int]:
    """
    Parses various file types into a DataFrame.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.csv':
        df = pd.read_csv(file_path, header=header_row)
    elif ext == '.xlsx':
        df = pd.read_excel(file_path, header=header_row, sheet_name=sheet_name or 0, engine='openpyxl')
    elif ext == '.xls':
        # Fallback for old Excel
        df = pd.read_excel(file_path, header=header_row, sheet_name=sheet_name or 0)
    elif ext == '.json':
        df = pd.read_json(file_path)
    elif ext == '.parquet':
        df = pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")
        
    return df, header_row

def _metadata_path(dataset_id: str, data_dir: str) -> str:
    return os.path.join(data_dir, dataset_id, "metadata.json")


def load_metadata(dataset_id: str, data_dir: str, original_filename: Optional[str] = None) -> DatasetMetadata:
    upload_dir = os.path.join(data_dir, dataset_id)
    os.makedirs(upload_dir, exist_ok=True)
    meta_path = _metadata_path(dataset_id, data_dir)
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            stored = json.load(f)
            return DatasetMetadata.from_dict(stored)

    meta = DatasetMetadata(original_filename=original_filename)
    persist_metadata(dataset_id, data_dir, meta)
    return meta


def persist_metadata(dataset_id: str, data_dir: str, metadata: DatasetMetadata) -> None:
    meta_path = _metadata_path(dataset_id, data_dir)
    with open(meta_path, "w") as f:
        json.dump(asdict(metadata), f, indent=2)


def _dataset_cache_key(metadata: DatasetMetadata, processed_path: Optional[str]) -> Tuple[Any, ...]:
    processed_mtime = os.path.getmtime(processed_path) if processed_path and os.path.exists(processed_path) else None
    return (metadata.version, metadata.modification_version, processed_mtime)


def invalidate_dataset_cache(dataset_id: str) -> None:
    with CACHE_LOCK:
        DATAFRAME_CACHE.pop(dataset_id, None)


def clear_profile_cache(dataset_id: str, data_dir: str) -> None:
    cache_path = os.path.join(data_dir, dataset_id, "profile_cache.json")
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
        except OSError:
            pass


def get_dataframe(dataset_id: str, data_dir: str, *, force_refresh: bool = False, prefer_processed: bool = True) -> pd.DataFrame:
    """
    Centralized function to load DataFrame for any dataset with caching and metadata awareness.
    Checks for processed.csv first (faster), falls back to original file. Uses in-memory cache keyed by
    modification/version and processed mtime to avoid stale reads.
    """
    upload_dir = os.path.join(data_dir, dataset_id)
    if not os.path.exists(upload_dir):
        raise FileNotFoundError(f"Dataset {dataset_id} not found")

    metadata = load_metadata(dataset_id, data_dir)
    processed_path = os.path.join(upload_dir, "processed.csv") if prefer_processed else None
    cache_key = _dataset_cache_key(metadata, processed_path)

    with CACHE_LOCK:
        cached = DATAFRAME_CACHE.get(dataset_id)
        if cached and cached["cache_key"] == cache_key and not force_refresh:
            return cached["df"].copy()

    df: Optional[pd.DataFrame] = None
    source = "raw"
    if prefer_processed and processed_path and os.path.exists(processed_path):
        df = pd.read_csv(processed_path)
        source = "processed"
    else:
        file_path, _ = get_dataset_path(dataset_id, data_dir)
        if not file_path:
            raise FileNotFoundError(f"Dataset {dataset_id} not found")
        df, _ = parse_file(file_path, header_row=metadata.header_row, sheet_name=metadata.sheet_name)

    with CACHE_LOCK:
        DATAFRAME_CACHE[dataset_id] = {"cache_key": cache_key, "df": df, "source": source}

    return df.copy()


def cache_profile(dataset_id: str, data_dir: str, profile: Dict[str, Any], metadata: DatasetMetadata, *, page: int, limit: int) -> None:
    metadata.bump_profile()
    profile_path = os.path.join(data_dir, dataset_id, "profile_cache.json")
    payload = {
        "page": page,
        "limit": limit,
        "profile_version": metadata.profile_version,
        "data_version": metadata.version,
        "modification_version": metadata.modification_version,
        "profile": profile,
    }
    with open(profile_path, "w") as f:
        json.dump(payload, f, indent=2)
    persist_metadata(dataset_id, data_dir, metadata)


def read_cached_profile(dataset_id: str, data_dir: str, metadata: DatasetMetadata, *, page: int, limit: int) -> Optional[Dict[str, Any]]:
    profile_path = os.path.join(data_dir, dataset_id, "profile_cache.json")
    if not os.path.exists(profile_path):
        return None
    try:
        with open(profile_path, "r") as f:
            payload = json.load(f)
        if (
            payload.get("profile_version") == metadata.profile_version
            and payload.get("data_version") == metadata.version
            and payload.get("modification_version") == metadata.modification_version
            and payload.get("page") == page
            and payload.get("limit") == limit
        ):
            return payload.get("profile")
    except Exception:
        return None
    return None


def cleanup_processed_files(data_dir: str, *, ttl_hours: int = DEFAULT_PROCESSED_TTL_HOURS) -> int:
    """Delete stale processed.csv artifacts to control disk usage. Returns number removed."""
    removed = 0
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
    for dataset_id in os.listdir(data_dir):
        processed_path = os.path.join(data_dir, dataset_id, "processed.csv")
        if not os.path.exists(processed_path):
            continue
        mtime = datetime.utcfromtimestamp(os.path.getmtime(processed_path))
        if mtime < cutoff:
            try:
                os.remove(processed_path)
                invalidate_dataset_cache(dataset_id)
                removed += 1
            except Exception:
                continue
    return removed


def snapshot_dataset(dataset_id: str, data_dir: str) -> Optional[str]:
    """Create a point-in-time snapshot of the processed dataset for auditability."""
    upload_dir = os.path.join(data_dir, dataset_id)
    processed_path = os.path.join(upload_dir, "processed.csv")
    if not os.path.exists(processed_path):
        return None
    snapshots_dir = os.path.join(upload_dir, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    target = os.path.join(snapshots_dir, f"processed_{stamp}.csv")
    shutil.copyfile(processed_path, target)
    return target
