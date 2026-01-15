from fastapi import FastAPI
from contextlib import asynccontextmanager
from pydantic import BaseModel
import os
import json
import uuid
import time
from typing import Any, Dict, List, Optional

@asynccontextmanager
async def lifespan(_: FastAPI):
    _ensure_dirs()
    yield


app = FastAPI(title="Antigravity Orchestrator", lifespan=lifespan)

TASKS_DIR = os.getenv("TASKS_DIR", "workspace/tasks")
INCOMING_DIR = f"{TASKS_DIR}/incoming"
PROCESSING_DIR = f"{TASKS_DIR}/processing"
COMPLETED_DIR = f"{TASKS_DIR}/completed"
FAILED_DIR = f"{TASKS_DIR}/failed"


def _ensure_dirs() -> None:
    for d in [INCOMING_DIR, PROCESSING_DIR, COMPLETED_DIR, FAILED_DIR]:
        os.makedirs(d, exist_ok=True)

class Task(BaseModel):
    description: str
    requirements: List[str] = []
    priority: str = "medium"
    type: str = "code"
    operations: Optional[List[Dict[str, Any]]] = None
    quality_gates: List[Dict[str, Any]] = []
    tags: List[str] = []
    max_retries: int = 2

class TaskResponse(BaseModel):
    task_id: str
    status: str
    path: str

@app.post("/api/task", response_model=TaskResponse)
async def create_task(task: Task):
    _ensure_dirs()
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    
    task_data = task.model_dump()
    task_data["task_id"] = task_id
    task_data["created_at"] = time.time()
    task_data["status"] = "pending"
    task_data["attempt"] = 0
    task_data["log"] = []
    task_data["metrics"] = {}
    
    file_path = f"{INCOMING_DIR}/{task_id}.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
        
    return {
        "task_id": task_id,
        "status": "queued",
        "path": file_path
    }


@app.post("/api/task/{task_id}/retry", response_model=TaskResponse)
async def retry_task(task_id: str):
    _ensure_dirs()
    filename = f"{task_id}.json"
    candidates = [
        os.path.join(FAILED_DIR, filename),
        os.path.join(COMPLETED_DIR, filename),
        os.path.join(PROCESSING_DIR, filename),
    ]

    src = None
    for path in candidates:
        if os.path.exists(path):
            src = path
            break

    if not src:
        return {"task_id": task_id, "status": "not_found", "path": ""}

    with open(src, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    task_data["status"] = "pending"
    task_data["next_run_at"] = None

    dest = os.path.join(INCOMING_DIR, filename)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)

    try:
        os.remove(src)
    except Exception:
        pass

    return {"task_id": task_id, "status": "queued", "path": dest}

@app.get("/api/tasks")
async def list_tasks():
    tasks = []
    # Scan all folders
    for status, path in [("incoming", INCOMING_DIR), ("processing", PROCESSING_DIR), 
                        ("completed", COMPLETED_DIR), ("failed", FAILED_DIR)]:
        if not os.path.exists(path): continue
        for filename in os.listdir(path):
            if filename.endswith(".json"):
                with open(f"{path}/{filename}", "r") as f:
                    try:
                        data = json.load(f)
                        data["queue_status"] = status
                        tasks.append(data)
                    except:
                        pass
    return tasks


@app.get("/api/stats")
async def get_stats():
    _ensure_dirs()

    def scan_dir(path: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        if not os.path.exists(path):
            return out
        for filename in os.listdir(path):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(path, filename), "r", encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                continue
        return out

    incoming = scan_dir(INCOMING_DIR)
    processing = scan_dir(PROCESSING_DIR)
    completed = scan_dir(COMPLETED_DIR)
    failed = scan_dir(FAILED_DIR)

    def avg(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return sum(values) / len(values)

    completed_durations = [
        float(t.get("metrics", {}).get("total_duration_s"))
        for t in completed
        if t.get("metrics", {}).get("total_duration_s") is not None
    ]

    queue_waits = [
        float(t.get("metrics", {}).get("queue_wait_s"))
        for t in completed
        if t.get("metrics", {}).get("queue_wait_s") is not None
    ]

    attempts = [
        int(t.get("attempt", 0))
        for t in completed + failed
        if t.get("attempt") is not None
    ]

    succeeded = len(completed)
    errored = len(failed)
    total_done = succeeded + errored
    success_rate = (succeeded / total_done) if total_done else None

    return {
        "counts": {
            "incoming": len(incoming),
            "processing": len(processing),
            "completed": len(completed),
            "failed": len(failed),
        },
        "kpi": {
            "success_rate": success_rate,
            "avg_total_duration_s": avg(completed_durations),
            "avg_queue_wait_s": avg(queue_waits),
            "avg_attempt": avg([float(x) for x in attempts]) if attempts else None,
        },
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
