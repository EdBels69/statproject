from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import uuid
import time
from typing import List, Optional

app = FastAPI(title="Antigravity Orchestrator")

TASKS_DIR = "workspace/tasks"
INCOMING_DIR = f"{TASKS_DIR}/incoming"
PROCESSING_DIR = f"{TASKS_DIR}/processing"
COMPLETED_DIR = f"{TASKS_DIR}/completed"
FAILED_DIR = f"{TASKS_DIR}/failed"

class Task(BaseModel):
    description: str
    requirements: List[str] = []
    priority: str = "medium"
    type: str = "code"

class TaskResponse(BaseModel):
    task_id: str
    status: str
    path: str

@app.on_event("startup")
def startup_event():
    for d in [INCOMING_DIR, PROCESSING_DIR, COMPLETED_DIR, FAILED_DIR]:
        os.makedirs(d, exist_ok=True)

@app.post("/api/task", response_model=TaskResponse)
async def create_task(task: Task):
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    
    task_data = task.dict()
    task_data["task_id"] = task_id
    task_data["created_at"] = time.time()
    task_data["status"] = "pending"
    
    file_path = f"{INCOMING_DIR}/{task_id}.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
        
    return {
        "task_id": task_id,
        "status": "queued",
        "path": file_path
    }

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
