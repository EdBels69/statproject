import json
import os
from datetime import datetime
from typing import Any, Dict, List

from app.core.pipeline import PipelineManager
from app.core.logging import logger


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _log_path(base_dir: str, dataset_id: str) -> str:
    return os.path.join(str(base_dir), str(dataset_id), "processed", "delta_log.json")


def append_delta_log(
    *,
    base_dir: str,
    dataset_id: str,
    action: str,
    details: Dict[str, Any],
    actor: str = "auto",
    max_entries: int = 500,
) -> Dict[str, Any]:
    path = _log_path(base_dir, dataset_id)
    entries: List[Dict[str, Any]] = []

    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict) and isinstance(existing.get("entries"), list):
                entries = existing.get("entries", [])
            elif isinstance(existing, list):
                entries = existing
    except Exception:
        entries = []

    entry = {
        "ts": _utc_iso(),
        "actor": str(actor or "auto"),
        "action": str(action or "unknown"),
        "details": details or {},
    }

    entries.append(entry)
    if max_entries and len(entries) > max_entries:
        entries = entries[-max_entries:]

    payload = {
        "dataset_id": str(dataset_id),
        "entries": entries,
    }

    try:
        pipeline = PipelineManager(str(base_dir))
        pipeline.write_json_atomic(path, payload, allow_nan=False)
    except Exception as e:
        logger.error(f"Failed to write delta log for {dataset_id}: {e}", exc_info=True)

    return payload
