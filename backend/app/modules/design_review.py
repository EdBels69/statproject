import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.pipeline import PipelineManager


DESIGN_REVIEW_VERSION = 1


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def get_design_review_path(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", "design_review.json")


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


def load_design_review(base_dir: str, dataset_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(get_design_review_path(base_dir, dataset_id))


def save_design_review(base_dir: str, dataset_id: str, artifact: Dict[str, Any]) -> None:
    pipeline = PipelineManager(str(base_dir))
    path = get_design_review_path(base_dir, dataset_id)
    pipeline.write_json_atomic(path, artifact, allow_nan=False)


def _clean_actor(value: Any, default: str = "user") -> str:
    text = str(value or "").strip()
    return text or default


def _clean_source(value: Any, default: str = "ui") -> str:
    text = str(value or "").strip()
    return text or default


def _clean_reason(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _clean_details(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def confirm_design_review(
    base_dir: str,
    dataset_id: str,
    *,
    actor: Any = "user",
    source: Any = "ui",
    details: Any = None,
) -> Dict[str, Any]:
    now = _utc_iso()
    artifact = {
        "version": DESIGN_REVIEW_VERSION,
        "dataset_id": str(dataset_id),
        "confirmed": True,
        "confirmed_at": now,
        "confirmed_by": _clean_actor(actor),
        "confirmed_source": _clean_source(source),
        "revoked_at": None,
        "revoked_by": None,
        "revoke_reason": None,
        "updated_at": now,
        "details": _clean_details(details),
    }
    save_design_review(base_dir, dataset_id, artifact)
    return artifact


def revoke_design_review(
    base_dir: str,
    dataset_id: str,
    *,
    actor: Any = "user",
    source: Any = "ui",
    reason: Any = None,
    details: Any = None,
) -> Dict[str, Any]:
    previous = load_design_review(base_dir, dataset_id) or {}
    now = _utc_iso()

    confirmed_at = previous.get("confirmed_at") if isinstance(previous.get("confirmed_at"), str) else None
    confirmed_by = previous.get("confirmed_by") if isinstance(previous.get("confirmed_by"), str) else None
    confirmed_source = previous.get("confirmed_source") if isinstance(previous.get("confirmed_source"), str) else None

    merged_details = _clean_details(previous.get("details"))
    incoming_details = _clean_details(details)
    if incoming_details:
        merged_details = {**merged_details, **incoming_details}

    artifact = {
        "version": DESIGN_REVIEW_VERSION,
        "dataset_id": str(dataset_id),
        "confirmed": False,
        "confirmed_at": confirmed_at,
        "confirmed_by": confirmed_by,
        "confirmed_source": confirmed_source,
        "revoked_at": now,
        "revoked_by": _clean_actor(actor),
        "revoke_reason": _clean_reason(reason),
        "updated_at": now,
        "revoke_source": _clean_source(source),
        "details": merged_details,
    }
    save_design_review(base_dir, dataset_id, artifact)
    return artifact
