import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.core.pipeline import PipelineManager
from app.modules.semantics import load_semantics, rebuild_and_save_semantics


STUDY_DESIGN_VERSION = 1


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


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


def _kind_from_type(type_str: str) -> str:
    t = (type_str or "").lower()
    if "datetime" in t or "date" in t or "time" in t:
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


def _matches_any(name_l: str, patterns: List[str]) -> bool:
    return any(p in name_l for p in patterns)


def _extract_timepoint(name: str) -> Tuple[str, Optional[str]]:
    text = str(name)
    pattern = re.compile(
        r"(?i)(?:^|[\s_\-])(?:(v|visit|визит|time|t|week|wk|month|mo|day|d|год|year|yr|неделя|месяц))\s*[_\-]?(\d+)(?:$|[\s_\-])"
    )
    m = pattern.search(text)
    if not m:
        return text.strip(), None
    prefix = m.group(1)
    num = m.group(2)
    label = f"{prefix.upper()}{num}"
    base = (text[: m.start()] + " " + text[m.end() :]).strip()
    base = re.sub(r"[\s_\-]+", " ", base).strip()
    if not base:
        base = text.strip()
    return base, label


def _sort_timepoints(labels: List[str]) -> List[str]:
    def key_fn(x: str) -> Tuple[int, str]:
        m = re.search(r"(\d+)$", x)
        if not m:
            return (10**9, x)
        return (int(m.group(1)), x)

    unique = list(dict.fromkeys(labels))
    unique.sort(key=key_fn)
    return unique


def _sort_endpoint_columns(columns: List[str], labels: List[str]) -> List[str]:
    def score(col: str) -> Tuple[int, str]:
        for idx, label in enumerate(labels):
            if label.lower() in str(col).lower():
                return (idx, col)
        return (len(labels) + 1, col)

    return sorted(list(dict.fromkeys(columns)), key=score)


def _score_group_candidate(name: str, unique: Optional[int], ratio: Optional[float]) -> int:
    if not unique or unique < 2:
        return 0
    score = 0
    name_l = str(name).strip().lower()
    keywords = [
        "группа",
        "групп",
        "group",
        "treatment",
        "arm",
        "cohort",
        "категор",
        "category",
        "класс",
        "тип",
        "рандом",
        "random",
        "intervention",
    ]
    if any(k in name_l for k in keywords):
        score += 3
    if unique <= 6:
        score += 2
    elif unique <= 15:
        score += 1
    if ratio is not None and ratio <= 0.2:
        score += 1
    return score


def _has_id_token(name_l: str) -> bool:
    if re.search(r"(^|[^a-z0-9])id($|[^a-z0-9])", name_l):
        return True
    return False


def _score_subject_candidate(name: str, ratio: Optional[float]) -> int:
    name_l = str(name).strip().lower()
    if not (
        _has_id_token(name_l)
        or any(
            k in name_l
            for k in ["uuid", "subject", "patient", "participant", "испытуемый", "пациент", "участник", "код", "номер"]
        )
    ):
        return 0
    if ratio is None:
        return 1
    return 3 if ratio >= 0.8 else 1


def _score_time_candidate(name: str, kind: str) -> int:
    name_l = str(name).strip().lower()
    strong_keywords = ["time", "visit", "day", "week", "month", "date", "день", "недел", "месяц", "дата", "визит"]
    if kind == "datetime":
        return 3
    if any(k in name_l for k in strong_keywords):
        return 2
    if "время" in name_l or "time" in name_l:
        return 0
    return 0


def _is_id_like(name_l: str, kind: str, unique_ratio: Optional[float], unique_count: Optional[int]) -> bool:
    if _has_id_token(name_l):
        return True
    if any(k in name_l for k in ["№", "номер", "no.", "n.", "код", "истор", "history", "patient"]):
        return True
    if name_l.replace(" ", "") in {"п/п", "пп", "row", "index"}:
        return True
    if kind == "numeric" and unique_ratio is not None and unique_ratio >= 0.9 and (unique_count or 0) > 20:
        return True
    return False


def get_study_design_path(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", "study_design.json")


def load_study_design(base_dir: str, dataset_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(get_study_design_path(base_dir, dataset_id))


def save_study_design(base_dir: str, dataset_id: str, design: Dict[str, Any]) -> None:
    pipeline = PipelineManager(str(base_dir))
    path = get_study_design_path(base_dir, dataset_id)
    pipeline.write_json_atomic(path, design, allow_nan=False)


def build_study_design(
    *,
    dataset_id: str,
    base_dir: str,
    scan_report: Optional[Dict[str, Any]] = None,
    semantics: Optional[Dict[str, Any]] = None,
    variable_mapping: Optional[Dict[str, Any]] = None,
    source: str = "auto",
) -> Dict[str, Any]:
    dataset_id = str(dataset_id)
    base_dir = str(base_dir)

    if scan_report is None:
        scan_path = os.path.join(base_dir, dataset_id, "processed", "scan_report.json")
        scan_report = _load_json(scan_path) or {}

    if semantics is None:
        semantics = load_semantics(base_dir, dataset_id)
        if semantics is None:
            semantics = rebuild_and_save_semantics(
                dataset_id=dataset_id,
                base_dir=base_dir,
                scan_report=scan_report,
                source="auto",
            )

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

    sem_cols = semantics.get("columns") if isinstance(semantics, dict) else {}
    if not isinstance(sem_cols, dict):
        sem_cols = {}

    columns_out: Dict[str, Dict[str, Any]] = {}
    group_candidates: List[Tuple[int, str]] = []
    subject_candidates: List[Tuple[int, str]] = []
    time_candidates: List[Tuple[int, str]] = []
    numeric_cols: List[str] = []
    categorical_cols: List[str] = []
    datetime_cols: List[str] = []
    id_like_cols: List[str] = []

    endpoint_groups: Dict[str, Dict[str, Any]] = {}

    for name, meta in columns_meta.items():
        col_name = _safe_str(name)
        if not col_name:
            continue
        meta = meta if isinstance(meta, dict) else {}
        type_str = _safe_str(meta.get("type"))
        kind = _kind_from_type(type_str)
        missing_count = meta.get("missing_count")
        unique_count = meta.get("unique_count")
        name_l = col_name.lower()
        unique_ratio: Optional[float] = None
        if isinstance(unique_count, int) and total_rows:
            try:
                unique_ratio = float(unique_count) / float(max(1, total_rows))
            except Exception:
                unique_ratio = None

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
            sem = sem_cols.get(col_name) if isinstance(sem_cols, dict) else None
            sem_role = sem.get("role") if isinstance(sem, dict) else None
            if isinstance(sem_role, str) and sem_role.strip():
                role = sem_role.strip()

        if role == "unknown":
            if _matches_any(name_l, ["id", "uuid", "guid", "patient", "subject", "participant", "animal", "пациент", "субъект", "номер", "код"]):
                role = "subject"
            elif _matches_any(name_l, ["group", "arm", "treat", "treatment", "cohort", "групп", "рандом", "grouping"]):
                role = "group"
            elif _matches_any(name_l, ["time", "visit", "day", "week", "month", "date", "день", "недел", "месяц", "дата", "время", "визит"]) or kind == "datetime":
                role = "time"
            elif kind == "numeric":
                role = "outcome"

        # Validate inferred semantic roles to avoid false positives (e.g. "covid" contains "id")
        if role == "subject" and _score_subject_candidate(col_name, unique_ratio) == 0:
            role = "unknown"
        if role == "time" and _score_time_candidate(col_name, kind) == 0:
            role = "unknown"

        columns_out[col_name] = {
            "type": kind,
            "source_type": type_str,
            "role": role,
            "missing_count": missing_count,
            "unique_count": unique_count,
        }

        if kind == "numeric":
            numeric_cols.append(col_name)
        elif kind == "categorical":
            categorical_cols.append(col_name)
        elif kind == "datetime":
            datetime_cols.append(col_name)

        if _is_id_like(name_l, kind, unique_ratio, unique_count if isinstance(unique_count, int) else None):
            id_like_cols.append(col_name)

        group_score = _score_group_candidate(col_name, unique_count if isinstance(unique_count, int) else None, unique_ratio)
        if group_score > 0 or role == "group":
            group_candidates.append((group_score + (2 if role == "group" else 0), col_name))

        subject_score = _score_subject_candidate(col_name, unique_ratio)
        if subject_score > 0 or role == "subject":
            subject_candidates.append((subject_score + (2 if role == "subject" else 0), col_name))

        time_score = _score_time_candidate(col_name, kind)
        if time_score > 0 or role == "time":
            time_candidates.append((time_score + (2 if role == "time" else 0), col_name))

        base, label = _extract_timepoint(col_name)
        if label:
            endpoint_groups.setdefault(base, {"endpoint": base, "columns": [], "timepoints": []})
            endpoint_groups[base]["columns"].append(col_name)
            endpoint_groups[base]["timepoints"].append(label)

    group_candidates.sort(key=lambda x: (-x[0], x[1]))
    subject_candidates.sort(key=lambda x: (-x[0], x[1]))
    time_candidates.sort(key=lambda x: (-x[0], x[1]))

    group_column = group_candidates[0][1] if group_candidates else None
    subject_column = subject_candidates[0][1] if subject_candidates else None
    time_column = time_candidates[0][1] if time_candidates else None

    if isinstance(semantics, dict):
        design = semantics.get("design") if isinstance(semantics.get("design"), dict) else {}
        group_column = design.get("group_column") or group_column
        subject_column = design.get("subject_column") or subject_column
        time_column = design.get("time_column") or time_column

    if time_column and isinstance(time_column, str):
        meta = columns_out.get(time_column, {})
        kind = meta.get("type") or ""
        if _score_time_candidate(time_column, str(kind)) == 0:
            time_column = None

    if subject_column and isinstance(subject_column, str):
        if _score_subject_candidate(subject_column, None) == 0:
            subject_column = None

    endpoint_groups_list: List[Dict[str, Any]] = []
    for item in endpoint_groups.values():
        timepoints = _sort_timepoints(item.get("timepoints") or [])
        columns_sorted = _sort_endpoint_columns(item.get("columns") or [], timepoints)
        endpoint_groups_list.append(
            {
                "endpoint": item.get("endpoint"),
                "columns": columns_sorted,
                "timepoints": timepoints,
            }
        )

    # Sort endpoints for stability
    endpoint_groups_list.sort(key=lambda x: str(x.get("endpoint") or ""))

    repeated_measures = bool(subject_column and time_column) or any(
        len(g.get("timepoints") or []) >= 2 for g in endpoint_groups_list
    )

    design_type = "cross_sectional"
    if subject_column and time_column:
        design_type = "repeated_measures_long"
    elif any(len(g.get("timepoints") or []) >= 2 for g in endpoint_groups_list):
        design_type = "repeated_measures_wide"

    id_like_set = set(id_like_cols)
    outcomes = [c for c in numeric_cols if c not in {group_column, subject_column, time_column} and c not in id_like_set]
    categorical_outcomes = [c for c in categorical_cols if c not in {group_column, subject_column, time_column} and c not in id_like_set]

    predictors = list(dict.fromkeys([*numeric_cols, *categorical_cols]))
    predictors = [c for c in predictors if c not in {group_column, subject_column, time_column} and c not in id_like_set]

    analysis_policy = {
        "alpha": 0.05,
        "multiplicity_correction": "fdr_bh",
        "post_hoc": "tukey",
        "post_hoc_correction": "fdr_bh",
        "bootstrap_ci": False,
        "bootstrap_samples": 1000,
        "exploratory_mode": True,
        "allow_data_mining": True,
        "max_batch_targets": 60,
        "max_descriptive_targets": 60,
        "max_table1_categorical": 40,
        "max_protocol_steps": 60,
    }

    return {
        "version": STUDY_DESIGN_VERSION,
        "dataset_id": dataset_id,
        "generated_at": _utc_iso(),
        "source": source,
        "summary": {
            "n_rows": total_rows or None,
            "n_cols": len(columns_out),
        },
        "columns": columns_out,
        "design": {
            "design_type": design_type,
            "repeated_measures": repeated_measures,
            "group_column": group_column,
            "time_column": time_column,
            "subject_column": subject_column,
            "endpoint_groups": endpoint_groups_list,
            "id_like_columns": sorted(list(set(id_like_cols))),
            "outcomes": outcomes[:200],
            "categorical_outcomes": categorical_outcomes[:200],
            "predictors": predictors[:200],
        },
        "analysis_policy": analysis_policy,
        "notes": [],
    }


def rebuild_and_save_study_design(
    *,
    dataset_id: str,
    base_dir: str,
    scan_report: Optional[Dict[str, Any]] = None,
    semantics: Optional[Dict[str, Any]] = None,
    variable_mapping: Optional[Dict[str, Any]] = None,
    source: str = "auto",
) -> Dict[str, Any]:
    try:
        design = build_study_design(
            dataset_id=dataset_id,
            base_dir=base_dir,
            scan_report=scan_report,
            semantics=semantics,
            variable_mapping=variable_mapping,
            source=source,
        )
        save_study_design(base_dir, dataset_id, design)
        return design
    except Exception as e:
        logger.error(f"Failed to build study design for {dataset_id}: {e}", exc_info=True)
        return {}
