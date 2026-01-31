import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logging import logger


def _utc_iso() -> str:
    return datetime.utcnow().isoformat()


def _safe_realpath(path: str) -> str:
    try:
        return os.path.realpath(path)
    except Exception:
        return path


@dataclass(frozen=True)
class JobRef:
    id: str
    kind: str
    dataset_id: Optional[str] = None


class JobStore:
    def __init__(self, base_dir: str):
        self.base_dir = str(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def _job_path(self, job_id: str) -> str:
        return os.path.join(self.base_dir, f"{job_id}.json")

    def create(self, kind: str, *, dataset_id: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> JobRef:
        job_id = str(uuid.uuid4())
        now = _utc_iso()
        data = {
            "id": job_id,
            "kind": str(kind),
            "dataset_id": dataset_id,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "created_at": now,
            "updated_at": now,
            "error": None,
            "payload": payload or {},
            "artifacts": {},
            "events": [
                {"ts": now, "type": "queued", "stage": "queued", "message": None, "progress": 0}
            ],
        }
        self._write_atomic(self._job_path(job_id), data)
        return JobRef(id=job_id, kind=str(kind), dataset_id=dataset_id)

    def get(self, job_id: str) -> Dict[str, Any]:
        path = self._job_path(job_id)
        if not os.path.exists(path):
            raise FileNotFoundError(job_id)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Invalid job payload")
        return data

    def list(self, *, dataset_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        try:
            for name in os.listdir(self.base_dir):
                if not name.endswith(".json"):
                    continue
                path = os.path.join(self.base_dir, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if not isinstance(data, dict):
                        continue
                    if dataset_id and str(data.get("dataset_id") or "") != str(dataset_id):
                        continue
                    items.append(data)
                except Exception:
                    continue
        except Exception:
            return []
        items.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
        return items[: max(1, int(limit))]

    def update(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        current = self.get(job_id)
        now = _utc_iso()

        next_data = dict(current)
        next_data["updated_at"] = now
        if status is not None:
            next_data["status"] = str(status)
        if stage is not None:
            next_data["stage"] = str(stage)
        if progress is not None:
            next_data["progress"] = max(0, min(100, int(progress)))
        if error is not None:
            next_data["error"] = str(error) if error else None

        if artifacts:
            cur_artifacts = next_data.get("artifacts")
            if not isinstance(cur_artifacts, dict):
                cur_artifacts = {}
            next_data["artifacts"] = {**cur_artifacts, **artifacts}

        if extra:
            payload = next_data.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            next_data["payload"] = {**payload, **extra}

        events = next_data.get("events")
        if not isinstance(events, list):
            events = []
        events.append(
            {
                "ts": now,
                "type": str(status or next_data.get("status") or "update"),
                "stage": str(stage or next_data.get("stage") or ""),
                "message": str(message) if message else None,
                "progress": int(next_data.get("progress") or 0),
            }
        )
        next_data["events"] = events[-200:]

        self._write_atomic(self._job_path(job_id), next_data)
        return next_data

    def fail(self, job_id: str, *, stage: str, error: str) -> Dict[str, Any]:
        logger.exception("job failed: %s stage=%s error=%s", job_id, stage, error)
        return self.update(job_id, status="failed", stage=stage, progress=100, error=error, message=error)

    def complete(self, job_id: str, *, stage: str = "completed", artifacts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.update(job_id, status="completed", stage=stage, progress=100, artifacts=artifacts, message="completed")

    def _write_atomic(self, path: str, payload: Dict[str, Any]) -> None:
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        tmp = f"{path}.tmp.{int(time.time() * 1000)}"
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


def build_job_store(workspace_dir: str) -> JobStore:
    base = os.path.join(str(workspace_dir), "jobs")
    logger.info("job store dir: %s", _safe_realpath(base))
    return JobStore(base)

