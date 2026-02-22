#!/usr/bin/env python3
"""
Agent Server: Autonomous Builder (Async Patch)
"""
import os
import json
import re
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

PROJECT_ROOT = Path(os.getcwd())
MAX_RETRIES = 3

app = FastAPI(title="Autonomous Builder Agent (Multithreaded)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Only allow frontend
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"]
)

# Mount the API routes
from app.api.routes import api_router
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Run cleanup tasks on server start"""
    from app.modules.reporting import cleanup_old_reports
    cleanup_old_reports(max_age_hours=24)
    print("✓ Startup complete - old reports cleaned")

executor = ThreadPoolExecutor(max_workers=5)

class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None
    verification_command: Optional[str] = None

from zhipuai import ZhipuAI

class GLMClient:
    def __init__(self):
        self.api_key = os.getenv("GLM_API_KEY")
        base_url = os.getenv("GLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/")
        if "/chat/completions" in base_url:
            base_url = base_url.replace("/chat/completions", "")
        if not base_url.endswith("/"):
            base_url += "/"
        self.client = ZhipuAI(api_key=self.api_key, base_url=base_url)
        self.model = os.getenv("GLM_MODEL", "glm-4")

    async def chat(self, messages: List[Dict]) -> str:
        if not self.api_key: raise Exception("API Key missing.")
        
        # OFF-LOAD TO THREAD to prevent loop freeze
        loop = asyncio.get_event_loop()
        def sync_call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2
            )
        
        response = await loop.run_in_executor(executor, sync_call)
        return response.choices[0].message.content

client = GLMClient()

def apply_files(content: str):
    pattern = r'FILE:\s*(.+?)\n```(?:\w+)?\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL)
    created = []
    for path, code in matches:
        full_path = PROJECT_ROOT / path.strip()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(code.strip())
        created.append(path.strip())
    return created

async def run_loop(task_id: str, request: TaskRequest):
    log_file = PROJECT_ROOT / "workspace" / "tasks" / "completed" / f"{task_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    def log(msg):
        print(block := f"[{task_id}] {msg}")
        with open(log_file, "a") as f: f.write(block + "\n")

    history = [
        {"role": "system", "content": "You are an autonomous code builder. You write files directly. Output format:\nFILE: path/to/file\n```\ncontent\n```"},
        {"role": "user", "content": f"Task: {request.task}\nContext: {request.context or {}}"}
    ]

    for attempt in range(MAX_RETRIES):
        log(f"Attempt {attempt + 1}/{MAX_RETRIES}...")
        try:
            response = await client.chat(history)
            history.append({"role": "assistant", "content": response})
            files = apply_files(response)
            log(f"Created/Modified: {files}")
            
            if not request.verification_command: break
            
            proc = subprocess.run(request.verification_command, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
            if proc.returncode == 0:
                log("Verification Passed! ✅")
                break
            else:
                log(f"Verification Failed ❌\nOutput: {proc.stderr}")
                history.append({"role": "user", "content": f"Fix error:\n{proc.stderr}\n{proc.stdout}"})
        except Exception as e:
            log(f"Error: {e}")
            break
    log("Task Ended.")

@app.post("/api/task")
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    task_id = f"task_{int(time.time())}"
    background_tasks.add_task(run_loop, task_id, request)
    return {"status": "accepted", "task_id": task_id}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
