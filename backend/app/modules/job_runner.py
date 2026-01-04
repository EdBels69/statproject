import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, Optional

DEFAULT_MAX_WORKERS = 4


def _utcnow() -> str:
    return datetime.utcnow().isoformat()


class JobManager:
    def __init__(self, base_dir: str, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._key_index: Dict[str, str] = {}
        self._lock = Lock()

    def _job_dir(self, dataset_id: str) -> str:
        path = os.path.join(self.base_dir, dataset_id, "jobs")
        os.makedirs(path, exist_ok=True)
        return path

    def _status_path(self, dataset_id: str, job_id: str) -> str:
        return os.path.join(self._job_dir(dataset_id), f"{job_id}.status.json")

    def _result_path(self, dataset_id: str, job_id: str, suffix: str = "json") -> str:
        return os.path.join(self._job_dir(dataset_id), f"{job_id}.result.{suffix}")

    def _write_status(self, dataset_id: str, job_id: str, payload: Dict[str, Any]) -> None:
        status_path = self._status_path(dataset_id, job_id)
        with open(status_path, "w") as f:
            json.dump(payload, f, indent=2)

    def _load_status(self, dataset_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        status_path = self._status_path(dataset_id, job_id)
        if os.path.exists(status_path):
            with open(status_path, "r") as f:
                return json.load(f)
        return None

    def submit(self, *, dataset_id: str, task_type: str, job_key: Optional[str], runner: Callable[[], Dict[str, Any]], payload: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if job_key and job_key in self._key_index:
                existing_id = self._key_index[job_key]
                existing = self._jobs.get(existing_id) or self._load_status(dataset_id, existing_id)
                if existing:
                    return existing

            job_id = job_key or str(uuid.uuid4())
            status = {
                "id": job_id,
                "dataset_id": dataset_id,
                "task_type": task_type,
                "status": "queued",
                "created_at": _utcnow(),
                "updated_at": _utcnow(),
                "result_path": None,
                "log_path": None,
                "error": None,
                "payload": payload,
            }
            self._jobs[job_id] = status
            if job_key:
                self._key_index[job_key] = job_id

        log_path = os.path.join(self._job_dir(dataset_id), f"{job_id}.log")
        status["log_path"] = log_path
        self._write_status(dataset_id, job_id, status)

        def _wrapped():
            try:
                with open(log_path, "a") as log:
                    log.write(f"[{_utcnow()}] Job started\n")
                self._update_status(dataset_id, job_id, "running")
                result = runner()
                result_path = self._result_path(dataset_id, job_id)
                with open(result_path, "w") as f:
                    json.dump(result, f, indent=2)
                self._update_status(dataset_id, job_id, "succeeded", result_path=result_path)
                with open(log_path, "a") as log:
                    log.write(f"[{_utcnow()}] Job completed\n")
            except Exception as exc:  # pylint: disable=broad-except
                with open(log_path, "a") as log:
                    log.write(f"[{_utcnow()}] Job failed: {exc}\n")
                self._update_status(dataset_id, job_id, "failed", error=str(exc))

        self._executor.submit(_wrapped)
        return status

    def _update_status(self, dataset_id: str, job_id: str, state: str, *, result_path: Optional[str] = None, error: Optional[str] = None) -> None:
        with self._lock:
            status = self._jobs.get(job_id) or {"id": job_id}
            status["status"] = state
            status["updated_at"] = _utcnow()
            if result_path:
                status["result_path"] = result_path
            if error:
                status["error"] = error
            self._jobs[job_id] = status
        self._write_status(dataset_id, job_id, status)

    def get(self, dataset_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            status = self._jobs.get(job_id)
        if status:
            return status
        return self._load_status(dataset_id, job_id)

