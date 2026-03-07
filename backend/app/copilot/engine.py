"""
Copilot Engine - The Brain.

Orchestrates:
1. User request → LLM understands → Analysis plan (JSON)
2. Analysis plan → LLM generates → Python code
3. Python code → Executor → Results
4. Results → LLM interprets → Clinical summary
5. User refinement → Loop back to step 2
"""

import json
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import os
import logging

from app.api.datasets import DATA_DIR
from app.modules.ai_context import build_ai_context

from app.llm import _chat_completion
from app.core.config import settings
from .prompts import UNDERSTAND_PROMPT, GENERATE_CODE_PROMPT, REFINE_PROMPT, INTERPRET_PROMPT
from .executor import CodeExecutor
from .r_engine import RExecutor
from .orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

class CopilotEngine:
    """
    Chat-first statistical analysis engine.
    """
    
    def __init__(self):
        self.executor = CodeExecutor(timeout_seconds=120)
        self.r_executor = RExecutor()
        self.agent_orchestrator = AgentOrchestrator(max_rounds=10)
        self.model = (
            os.getenv("LLM_MODEL_ID")
            or os.getenv("COPILOT_MODEL_PLANNER")
            or settings.COPILOT_MODEL_PLANNER
            or settings.GLM_MODEL
        )
        self.fallback_model = (
            os.getenv("LLM_MODEL_FALLBACK")
            or os.getenv("COPILOT_MODEL_FALLBACK")
            or os.getenv("COPILOT_MODEL_INTERPRETER")
            or settings.COPILOT_MODEL_FALLBACK
            or settings.GLM_MODEL
        )
        self.sessions_file = Path("copilot_sessions.json")
        self.sessions: Dict[str, Dict] = self._load_sessions()

    def _parse_llm_json(self, response: str) -> Dict:
        """Parse JSON from LLM response, stripping markdown fences."""
        text = response.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    def _load_sessions(self) -> Dict[str, Dict]:
        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Failed to load sessions: {e}")
        return {}

    def _save_sessions(self):
        try:
            # Create a serializable copy
            serializable_sessions = json.loads(json.dumps(self.sessions, default=str))
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(serializable_sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save sessions: {e}")
    
    async def _llm_call(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4000
    ) -> Tuple[Optional[str], Dict[str, int]]:
        """Call LLM and return (response, usage). Includes Fallback logic."""
        model = model or self.model
        try:
            response, usage = await _chat_completion(
                model=model,
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_s=120.0
            )
            if response:
                return response, usage
        except Exception:
            pass
            
        fallback_model = str(self.fallback_model or "").strip()
        if fallback_model and model != fallback_model:
            print(f"⚠️ Primary model {model} failed. Switching to fallback: {fallback_model}")
            try:
                response, usage = await _chat_completion(
                    model=fallback_model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_s=120.0
                )
                return response, usage
            except Exception:
                pass
                
        return None, {}

    def _compress_metadata(self, meta: Dict) -> str:
        """Compress metadata to fit context window."""
        meta_str = json.dumps(meta, ensure_ascii=False, default=str)
        if len(meta_str) < 15000:
            return meta_str
        
        # Simple compression: keep only column names and types, truncate categories
        compact = {}
        if "columns" in meta:
            compact["columns"] = [c.get("name") for c in meta["columns"]][:300] # Limit col count
        if "summary" in meta:
            compact["summary"] = meta["summary"]
        
        return json.dumps(compact, ensure_ascii=False, default=str)

    async def create_plan(
        self, 
        session_id: str, 
        user_request: str,
        dataset_path: str,
        dataset_info: Dict,
        model_id: Optional[str] = None,
        advanced: bool = False
    ) -> Dict[str, Any]:
        """
        Stage 1: Understand user request & create analysis plan
        """
        # Initialize usage tracking
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        def _add_usage(u: Dict[str, int]):
            total_usage["prompt_tokens"] += u.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += u.get("completion_tokens", 0)
            total_usage["total_tokens"] += u.get("total_tokens", 0)


        
        # Stage 1: Understand request → Analysis plan
        understand_prompt = UNDERSTAND_PROMPT.format(
            filename=dataset_info["filename"],
            n_rows=dataset_info["n_rows"],
            n_cols=dataset_info["n_cols"],
            columns=json.dumps(dataset_info["columns"], ensure_ascii=False),
            dataset_meta=json.dumps(dataset_info["dataset_meta"], ensure_ascii=False, default=str),
            user_request=user_request,
        )
        
        
        plan_response, usage = await self._llm_call(
            understand_prompt, 
            model=model_id or settings.COPILOT_MODEL_PLANNER
        )
        _add_usage(usage)
        
        if not plan_response:
            return {
                "session_id": session_id,
                "success": False,
                "error": "LLM failed to understand request"
            }
        
        # Parse plan JSON
        try:
            plan = self._parse_llm_json(plan_response)
        except json.JSONDecodeError as e:
            return {
                "session_id": session_id,
                "success": False,
                "error": f"Failed to parse analysis plan: {e}",
                "raw_response": plan_response
            }
            
        # Store interim state
        self.sessions[session_id] = {
            "dataset_path": dataset_path,
            "dataset_info": dataset_info,
            "plan": plan,
            "user_request": user_request,
            "model_id": model_id or self.model,
            "usage": total_usage,
            "status": "planned",
            "advanced": bool(advanced),
        }
        self._save_sessions()
        
        return {
            "session_id": session_id,
            "plan": plan,
            "success": True,
            "usage": total_usage
        }

    async def execute_plan(
        self,
        session_id: str,
        plan_override: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Stage 2 & 3: Generate code from plan and execute it.
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        if not bool(session.get("advanced")):
            return {"success": False, "error": "Advanced mode is required for code execution"}
            
        plan = plan_override or session["plan"]
        model_id = session["model_id"]
        dataset_path = session["dataset_path"]
        total_usage = session["usage"]
        
        def _add_usage(u: Dict[str, int]):
            total_usage["prompt_tokens"] += u.get("prompt_tokens", 0)
            total_usage["completion_tokens"] += u.get("completion_tokens", 0)
            total_usage["total_tokens"] += u.get("total_tokens", 0)
            
        max_attempts = 3
        exec_result = None
        code = None
        last_error = None
        last_output = None
        for attempt in range(1, max_attempts + 1):
            if attempt == 1:
                prompt = GENERATE_CODE_PROMPT.format(
                    analysis_plan=json.dumps(plan, indent=2, ensure_ascii=False),
                    dataset_path=dataset_path,
                    project_root=os.getcwd()
                )
            else:
                prompt = (
                    "The code failed with this error: {error}. Fix it.\n\n"
                    "Analysis plan:\n{plan}\n\n"
                    "Previous code:\n{code}"
                ).format(
                    error=last_error,
                    plan=json.dumps(plan, indent=2, ensure_ascii=False),
                    code=code
                )

            code_response, usage = await self._llm_call(
                prompt,
                model=settings.COPILOT_MODEL_CODER,
                temperature=0.1,
                max_tokens=8000
            )
            _add_usage(usage)

            if not code_response:
                return {
                    "session_id": session_id,
                    "plan": plan,
                    "success": False,
                    "error": "LLM failed to generate code"
                }

            # 2. Extract code
            if "<R_CODE_START>" in code_response:
                code_to_run = code_response.split("<R_CODE_START>")[1].split("<R_CODE_END>")[0].strip()
                is_r = True
            elif "```python" in code_response:
                code_to_run = code_response.split("```python")[1].split("```")[0].strip()
                is_r = False
            elif "```" in code_response:
                code_to_run = code_response.split("```")[1].split("```")[0].strip()
                is_r = False
            else:
                code_to_run = code_response.strip()
                is_r = False

            # 3. Execute
            stdout, stderr, success = "", "", False
            
            if is_r:
                stdout, stderr = await self.r_executor.execute_code(code_to_run, dataset_path) # Changed context to dataset_path
                # Rscript returns empty stdout on success if no print, check stderr for errors?
                # Our RExecutor returns stderr if exit code != 0.
                if "Execution Error" in stderr or "System Error" in stderr:
                    success = False
                else:
                    success = True
                    # If R printed JSON to stdout, we might need to parse it.
                    # For now, let's assume R usage is for plots/reports and not returning JSON results to Python.
                    # If JSON results required, we need to instruct R to write to a specific file.
            else:
                # Python Execution
                # The original execute_plan uses self.executor.execute which returns a dict.
                # The provided snippet assumes _execute_python_safe which returns stdout, stderr, success.
                # To integrate, we'll adapt to the existing self.executor.execute structure.
                exec_result = self.executor.execute(code_to_run, dataset_path)
                stdout = exec_result.get("output", "")
                stderr = exec_result.get("error", "")
                success = exec_result.get("success", False)
            
            if success:
                # Prioritize: parsed JSON > fallback JSON parse > raw stdout
                parsed = exec_result.get("results") if exec_result else None
                
                if not parsed and not is_r and stdout and "<JSON_START>" in stdout:
                    try:
                        json_str = stdout.split("<JSON_START>")[1].split("<JSON_END>")[0]
                        parsed = json.loads(json_str)
                    except Exception:
                        pass
                
                session["results"] = parsed or {"_raw_stdout": stdout, "_raw_stderr": stderr}
                session["output"] = stdout

                code = code_to_run
                break
            
            # If fail, loop again (feedback)
            last_error = f"{stderr}\n{stdout}"
            last_output = stdout # Keep track of output for the next prompt
            print(f"Attempt {attempt+1} failed: {last_error[:200]}...")
        
        # After the loop, check if execution was successful
        if not success: # Use the 'success' variable from the loop
            return {
                "session_id": session_id,
                "plan": plan,
                "code": code, # This will be the last attempted code
                "success": False,
                "error": last_error,
                "output": last_output,
                "usage": total_usage
            }
        
        # If we reached here, 'success' is True and 'code' and 'session["results"]' are updated.
        results = session.get("results", {}) # Get results from the updated session
        
        # Stage 4: Generate interpretation (optional, can be slow)
        interpretation = None
        if results:
            try:
                interpret_prompt = INTERPRET_PROMPT.format(
                    results=json.dumps(results, indent=2, ensure_ascii=False, default=str)[:8000],
                    domain_context=plan.get("domain", "General"),
                    language=plan.get("language", "ru")
                )
                interp_resp, usage = await self._llm_call(
                    interpret_prompt, 
                    model=settings.COPILOT_MODEL_INTERPRETER,
                    temperature=0.3
                )
                interpretation = interp_resp
                _add_usage(usage)
            except:
                pass  # Interpretation is optional
        
        # Update session
        session.update({
            "plan": plan, # Update if overridden
            "code": code,
            "results": results,
            "usage": total_usage,
            "interpretation": interpretation,
            "status": "completed"
        })
        self.sessions[session_id] = session
        self._save_sessions()
        
        return {
            "session_id": session_id,
            "plan": plan,
            "code": code,
            "results": results,
            "interpretation": interpretation,
            "output": exec_result.get("output"),
            "success": True,
            "error": None,
            "usage": total_usage
        }

    async def execute_plan_stream(
        self,
        session_id: str,
        plan_override: Optional[Dict] = None
    ):
        """
        Stage 2 & 3: Generate code and execute with streaming output.
        Yields SSE-formatted events.
        """
        session = self.sessions.get(session_id)
        if not session:
            yield {"type": "error", "data": "Session not found"}
            yield {"type": "done"}
            return
        if not bool(session.get("advanced")):
            yield {"type": "error", "data": "Advanced mode is required for code execution"}
            yield {"type": "done"}
            return
            
        plan = plan_override or session["plan"]
        model_id = session["model_id"]
        dataset_path = session["dataset_path"]
        
        max_attempts = 3
        final_results = None
        code = None
        last_error = None
        result_received = False

        for attempt in range(1, max_attempts + 1):
            yield {"type": "log", "data": "🧠 Generating analysis code..."}

            if attempt == 1:
                prompt = GENERATE_CODE_PROMPT.format(
                    analysis_plan=json.dumps(plan, indent=2, ensure_ascii=False),
                    dataset_path=dataset_path,
                    project_root=os.getcwd()
                )
            else:
                prompt = (
                    "The code failed with this error: {error}. Fix it.\n\n"
                    "Analysis plan:\n{plan}\n\n"
                    "Previous code:\n{code}"
                ).format(
                    error=last_error,
                    plan=json.dumps(plan, indent=2, ensure_ascii=False),
                    code=code
                )

            code_response, usage = await self._llm_call(
                prompt,
                model=settings.COPILOT_MODEL_CODER,
                temperature=0.1,
                max_tokens=8000
            )

            if not code_response:
                yield {"type": "error", "data": "LLM failed to generate code"}
                yield {"type": "done"}
                return

            code = code_response.strip()
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            yield {"type": "log", "data": "⚙️ Executing analysis..."}
            yield {"type": "code", "data": code[:500] + "..." if len(code) > 500 else code}

            result_received = False
            final_results = None
            error_messages = []
            for event in self.executor.execute_stream(code, dataset_path, emit_done=False):
                if event["type"] == "result":
                    final_results = event.get("data")
                    result_received = True
                if event["type"] == "error":
                    error_messages.append(event.get("data"))
                yield event

            if result_received:
                break

            last_error = "\n".join([m for m in error_messages if m]).strip() or "Execution failed"
            if attempt < max_attempts:
                yield {"type": "log", "data": f"⚠️ Execution failed. Retrying ({attempt + 1}/{max_attempts})..."}
            else:
                yield {"type": "error", "data": last_error}
                yield {"type": "done"}
                return
        
        # Stage 4: Generate interpretation if we have results
        interp_resp = None
        if result_received:
            yield {"type": "log", "data": "📊 Generating interpretation..."}
            try:
                interpret_prompt = INTERPRET_PROMPT.format(
                    results=json.dumps(final_results, indent=2, ensure_ascii=False, default=str)[:8000],
                    domain_context=plan.get("domain", "General"),
                    language=plan.get("language", "ru")
                )
                interp_resp, _ = await self._llm_call(
                    interpret_prompt, 
                    model=settings.COPILOT_MODEL_INTERPRETER,
                    temperature=0.3
                )
                if interp_resp:
                    yield {"type": "interpretation", "data": interp_resp}
            except Exception as e:
                yield {"type": "log", "data": f"⚠️ Interpretation skipped: {str(e)}"}
        
        # Update session
        session.update({
            "plan": plan,
            "code": code,
            "results": final_results,
            "interpretation": interp_resp,
            "status": "completed"
        })
        self.sessions[session_id] = session
        self._save_sessions()

        yield {"type": "done"}

    async def analyze(
        self,
        dataset_path: str,
        user_request: str,
        dataset_info: Dict,
        model_id: Optional[str] = None, 
        advanced: bool = False
    ) -> Dict[str, Any]:
        """
        Full pipeline: Understand -> Code -> Execute -> Interpret
        """
        import uuid
        session_id = str(uuid.uuid4())
        
        # 1. Create Plan
        plan_result = await self.create_plan(
            session_id=session_id,
            user_request=user_request,
            dataset_path=dataset_path,
            dataset_info=dataset_info,
            model_id=model_id,
            advanced=advanced
        )
        
        if not plan_result["success"]:
            return plan_result
            
        # 2. Execute
        exec_result = await self.execute_plan(
            session_id=session_id
        )
        
        return exec_result
    
    async def refine(
        self,
        session_id: str,
        refinement_request: str
    ) -> Dict[str, Any]:
        """
        Refine existing analysis based on user feedback.
        """
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found. Start new analysis."
            }
        
        session = self.sessions[session_id]
        model_id = session.get("model_id")
        
        # Ask LLM to update the plan
        refine_prompt = REFINE_PROMPT.format(
            current_results=json.dumps(session["results"], indent=2, default=str)[:4000],
            refinement_request=refinement_request
        )
        
        updated_plan_response, usage = await self._llm_call(refine_prompt, model=model_id)
        # Note: We don't easily track usage cumulatively across sessions unless we explicitly update session state
        # For this turn's result, we'll return this turn's usage in the analyze call, but we should pass accumulated context.
        # However, engine.analyze initializes fresh usage tracking. 
        # Ideally, we'd pass usage dict to analyze, but simple for now.
        
        if not updated_plan_response:
            return {
                "session_id": session_id,
                "success": False,
                "error": "LLM failed to process refinement"
            }
        
        # Parse and re-run
        try:
            updated_plan = self._parse_llm_json(updated_plan_response)
        except Exception:
            # If can't parse, try to append to existing analyses
            updated_plan = session["plan"].copy()
            updated_plan["analyses"].append({
                "name": refinement_request,
                "type": "custom",
                "description": refinement_request
            })
        
        # Re-generate code with updated plan
        return await self.analyze(
            dataset_path=session["dataset_path"],
            user_request=session["user_request"] + f"\n\nADDITIONAL: {refinement_request}",
            dataset_info=session.get("dataset_info", {}),
            model_id=model_id,
            advanced=bool(session.get("advanced")),
        )
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session state for debugging/inspection."""
        return self.sessions.get(session_id)
