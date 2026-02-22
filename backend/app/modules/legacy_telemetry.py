import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List

from app.core.config import settings
from app.core.logging import logger


_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {
    "total_hits": 0,
    "last_hit_at": None,
    "endpoints": {},
}


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat()


def _snapshot_unlocked() -> Dict[str, Any]:
    endpoints_raw = _STATE.get("endpoints")
    endpoints_raw = endpoints_raw if isinstance(endpoints_raw, dict) else {}

    endpoints: List[Dict[str, Any]] = []
    for endpoint, payload in endpoints_raw.items():
        if not isinstance(payload, dict):
            continue
        endpoints.append(
            {
                "endpoint": str(endpoint),
                "count": int(payload.get("count") or 0),
                "last_hit_at": payload.get("last_hit_at"),
            }
        )
    endpoints.sort(key=lambda x: x["endpoint"])
    return {
        "total_hits": int(_STATE.get("total_hits") or 0),
        "last_hit_at": _STATE.get("last_hit_at"),
        "endpoints": endpoints,
    }


def _persist_snapshot(snapshot: Dict[str, Any]) -> None:
    path = settings.CLINIMETRIA_LEGACY_TELEMETRY_PATH
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.warning(f"Legacy telemetry persist failed: {e}")


def record_legacy_hit(endpoint: str) -> None:
    endpoint_name = str(endpoint or "unknown").strip() or "unknown"
    now = _utc_now_iso()
    with _LOCK:
        endpoints = _STATE.setdefault("endpoints", {})
        current = endpoints.get(endpoint_name)
        if not isinstance(current, dict):
            current = {"count": 0, "last_hit_at": None}
        current["count"] = int(current.get("count") or 0) + 1
        current["last_hit_at"] = now
        endpoints[endpoint_name] = current

        _STATE["total_hits"] = int(_STATE.get("total_hits") or 0) + 1
        _STATE["last_hit_at"] = now
        snapshot = _snapshot_unlocked()

    _persist_snapshot(snapshot)


def get_legacy_snapshot() -> Dict[str, Any]:
    with _LOCK:
        return _snapshot_unlocked()


def reset_legacy_telemetry() -> None:
    with _LOCK:
        _STATE["total_hits"] = 0
        _STATE["last_hit_at"] = None
        _STATE["endpoints"] = {}
        snapshot = _snapshot_unlocked()
    _persist_snapshot(snapshot)
