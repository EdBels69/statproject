import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.logging import logger
from app.core.pipeline import PipelineManager


SEMANTICS_VERSION = 1


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _kind_from_type(type_str: str) -> str:
    t = (type_str or "").lower()
    if "datetime" in t or "date" in t:
        return "datetime"
    if "int" in t or "float" in t or "double" in t or "number" in t:
        return "numeric"
    if "bool" in t:
        return "categorical"
    if "category" in t:
        return "categorical"
    if "object" in t or "string" in t:
        return "text"
    return "text"


def _matches_any(name_l: str, patterns: list[str]) -> bool:
    for p in patterns:
        if p == "id":
            if re.search(r"(^|[^a-z0-9])id($|[^a-z0-9])", name_l):
                return True
        elif p in name_l:
            return True
    return False


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


def get_semantics_path(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", "dataset_semantics.json")


def load_semantics(base_dir: str, dataset_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(get_semantics_path(base_dir, dataset_id))


def save_semantics(base_dir: str, dataset_id: str, semantics: Dict[str, Any]) -> None:
    pipeline = PipelineManager(str(base_dir))
    path = get_semantics_path(base_dir, dataset_id)
    pipeline.write_json_atomic(path, semantics, allow_nan=False)


def build_dataset_semantics(
    *,
    dataset_id: str,
    base_dir: str,
    scan_report: Optional[Dict[str, Any]] = None,
    dtypes: Optional[Dict[str, Any]] = None,
    variable_mapping: Optional[Dict[str, Any]] = None,
    source: str = "auto",
) -> Dict[str, Any]:
    dataset_id = str(dataset_id)
    base_dir = str(base_dir)

    if scan_report is None:
        scan_path = os.path.join(base_dir, dataset_id, "processed", "scan_report.json")
        scan_report = _load_json(scan_path) or {}

    if dtypes is None:
        dtypes_path = os.path.join(base_dir, dataset_id, "processed", "dtypes.json")
        dtypes = _load_json(dtypes_path) or {}

    if variable_mapping is None:
        mapping_path = os.path.join(base_dir, dataset_id, "processed", "variable_mapping.json")
        variable_mapping = _load_json(mapping_path) or {}

    columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else {}
    if not isinstance(columns_meta, dict):
        columns_meta = {}

    total_rows = 0
    missing_report = scan_report.get("missing_report") if isinstance(scan_report, dict) else None
    if isinstance(missing_report, dict):
        try:
            total_rows = int(missing_report.get("total_rows") or 0)
        except Exception:
            total_rows = 0

    columns_out: Dict[str, Dict[str, Any]] = {}
    group_candidates: list[str] = []
    time_candidates: list[str] = []
    subject_candidates: list[str] = []
    id_candidates: list[str] = []
    outcome_candidates: list[str] = []
    predictor_candidates: list[str] = []

    for name, meta in columns_meta.items():
        col_name = _safe_str(name)
        if not col_name:
            continue
        meta = meta if isinstance(meta, dict) else {}
        type_str = _safe_str(meta.get("type") or dtypes.get(col_name))
        kind = _kind_from_type(type_str)
        missing_count = meta.get("missing_count")
        unique_count = meta.get("unique_count")
        name_l = col_name.lower()

        role = "unknown"
        mapping_entry = variable_mapping.get(col_name) if isinstance(variable_mapping, dict) else None
        if isinstance(mapping_entry, dict):
            mapped_role = mapping_entry.get("role")
            if isinstance(mapped_role, str) and mapped_role.strip():
                role = mapped_role.strip()
            elif mapping_entry.get("group_var"):
                role = "group"
            elif mapping_entry.get("timepoint"):
                role = "time"

        if role == "unknown":
            if _matches_any(name_l, ["id", "uuid", "guid", "patient", "subject", "participant", "animal", "пациент", "субъект", "номер", "код"]):
                if isinstance(unique_count, int) and total_rows and unique_count >= max(2, int(total_rows * 0.6)):
                    role = "subject"
            if role == "unknown" and _matches_any(name_l, ["group", "arm", "treat", "treatment", "cohort", "групп", "рандом", "grouping"]):
                role = "group"
            if role == "unknown" and (_matches_any(name_l, ["time", "visit", "day", "week", "month", "date", "день", "недел", "месяц", "дата", "время", "визит"]) or kind == "datetime"):
                role = "time"

        if role == "unknown" and kind == "numeric":
            role = "outcome"

        columns_out[col_name] = {
            "type": kind,
            "source_type": type_str,
            "role": role,
            "missing_count": missing_count,
            "unique_count": unique_count,
        }

        if role == "group":
            group_candidates.append(col_name)
        if role == "time":
            time_candidates.append(col_name)
        if role == "subject":
            subject_candidates.append(col_name)
        if role == "id":
            id_candidates.append(col_name)
        if role == "outcome":
            outcome_candidates.append(col_name)
        if role == "predictor":
            predictor_candidates.append(col_name)

        if role == "unknown":
            if kind == "numeric":
                predictor_candidates.append(col_name)
            elif kind == "categorical":
                group_candidates.append(col_name)

    repeated_measures = bool(subject_candidates and time_candidates)

    semantics = {
        "version": SEMANTICS_VERSION,
        "dataset_id": dataset_id,
        "generated_at": _utc_iso(),
        "source": source,
        "columns": columns_out,
        "design": {
            "repeated_measures": repeated_measures,
            "time_column": time_candidates[0] if time_candidates else None,
            "subject_column": subject_candidates[0] if subject_candidates else None,
            "group_column": group_candidates[0] if group_candidates else None,
            "outcome_candidates": outcome_candidates[:20],
            "predictor_candidates": predictor_candidates[:20],
        },
    }

    return semantics


def rebuild_and_save_semantics(
    *,
    dataset_id: str,
    base_dir: str,
    scan_report: Optional[Dict[str, Any]] = None,
    dtypes: Optional[Dict[str, Any]] = None,
    variable_mapping: Optional[Dict[str, Any]] = None,
    source: str = "auto",
) -> Dict[str, Any]:
    try:
        semantics = build_dataset_semantics(
            dataset_id=dataset_id,
            base_dir=base_dir,
            scan_report=scan_report,
            dtypes=dtypes,
            variable_mapping=variable_mapping,
            source=source,
        )
        save_semantics(base_dir, dataset_id, semantics)
        return semantics
    except Exception as e:
        logger.error(f"Failed to build semantics for {dataset_id}: {e}", exc_info=True)
        return {}
