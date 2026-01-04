#!/usr/bin/env python3
"""
Agent Server: Autonomous Builder (Roo Code Simulation)
Features:
- "Set and Forget" automation
- Self-Healing Loop: Generate -> Verify -> Fix -> Repeat
- Direct file manipulation
"""

import os
import json
import re
import asyncio
import subprocess
import httpx
from pathlib import Path
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

# Load env
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
# We assume the server is running from backend/automation or similar, need to find repo root
# Actually, the user runs it from project root, so:
PROJECT_ROOT = Path(os.getcwd())

MAX_RETRIES = 3

app = FastAPI(title="Autonomous Builder Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class TaskRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None
    verification_command: Optional[str] = None # e.g., "npm run test" or "python -m pytest"

class GLMClient:
    def __init__(self):
        self.api_key = os.getenv("GLM_API_KEY") 
        # User can use their Roo Code key here if it's compatible (e.g. OpenRouter)
        self.api_url = os.getenv("GLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.model = os.getenv("GLM_MODEL", "xiaomi/mimo-v2-flash:free") # Use free/cheap model for loop

    async def chat(self, messages: List[Dict]) -> str:
        if not self.api_key:
            raise Exception("API Key missing. Please set GLM_API_KEY in .env")
            
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(self.api_url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

client = GLMClient()

def apply_files(content: str):
    """Parse FILE: blocks and write to disk"""
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
    """The Core 'Until it works' Loop"""
    log_file = PROJECT_ROOT / "workspace" / "tasks" / "completed" / f"{task_id}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(msg):
        print(block := f"[{task_id}] {msg}")
        with open(log_file, "a") as f: f.write(block + "\n")

    history = [
        {"role": "system", "content": "You are an autonomous code builder. You write files directly. When specificed, you fix errors based on feedback."},
        {"role": "user", "content": f"Task: {request.task}\nContext: {request.context or {}}\n\nOutput files in format:\nFILE: path/to/file\n```\ncontent\n```"}
    ]

    for attempt in range(MAX_RETRIES):
        log(f"Attempt {attempt + 1}/{MAX_RETRIES}...")
        
        # 1. Generate
        try:
            response = await client.chat(history)
        except Exception as e:
            log(f"LLM Error: {e}")
            break
            
        history.append({"role": "assistant", "content": response})
        
        # 2. Apply
        files = apply_files(response)
        log(f"Created/Modified: {files}")
        
        # 3. Verify
        if not request.verification_command:
            log("No verification command provided. Assuming success.")
            break
            
        log(f"Running verification: {request.verification_command}")
        proc = subprocess.run(request.verification_command, shell=True, capture_output=True, text=True, cwd=PROJECT_ROOT)
        
        if proc.returncode == 0:
            log("Verification Passed! ✅")
            break
        else:
            log(f"Verification Failed ❌\nOutput: {proc.stderr[:500]}")
            history.append({"role": "user", "content": f"The verification command failed:\n{proc.stderr}\n{proc.stdout}\n\nPlease fix the code."})
    
    log("Task Loop Ended.")

@app.post("/api/task")
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    task_id = f"task_{int(time.time())}"
    background_tasks.add_task(run_loop, task_id, request)
    return {"status": "accepted", "task_id": task_id, "message": "Started autonomous loop in background."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
