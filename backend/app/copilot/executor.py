"""
Safe Code Executor - Runs LLM-generated Python code in isolation.

Security measures:
1. Timeout limit
2. Memory limit (via resource limits)
3. No network access in generated code
4. Restricted imports (only safe scientific libs)
"""

import subprocess
import tempfile
import json
import os
import ast
from typing import Dict, Any, Tuple
from pathlib import Path


class CodeExecutor:
    """Safely execute Python code with timeout and capture output."""
    
    ALLOWED_IMPORTS = {
        'pandas', 'numpy', 'scipy', 'pingouin', 'statsmodels', 
        'sklearn', 'lifelines', 'json', 'warnings', 'math', 'statistics',
        'matplotlib', 'seaborn', 'app', 'os', 'sys'
    }
    
    def __init__(self, timeout_seconds: int = 120, max_memory_mb: int = 1024):
        self.timeout = timeout_seconds
        self.max_memory = max_memory_mb
    
    def execute(self, code: str, dataset_path: str = None) -> Dict[str, Any]:
        """
        Execute Python code and return results.
        
        Args:
            code: Python code to execute
            dataset_path: Optional path to inject into code
            
        Returns:
            {
                "success": bool,
                "output": str,  # stdout
                "error": str,   # stderr if failed
                "results": dict # parsed JSON results if available
            }
        """
        ok, err = self.validate_code(code)
        if not ok:
            return {
                "success": False,
                "output": None,
                "error": err,
                "results": None,
                "code": code
            }

        # Replace dataset_path placeholder if provided
        if dataset_path:
            code = code.replace('{dataset_path}', dataset_path)
            code = code.replace('{{dataset_path}}', dataset_path)
            
        # Replace project_root placeholder (assume running from project root or backend)
        project_root = os.getcwd()
        code = code.replace('{project_root}', project_root)
        code = code.replace('{{project_root}}', project_root)
        
        code = self._sandbox_header() + "\n" + code

        # Create temp file for execution
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            script_path = f.name
        
        try:
            # Execute with timeout
            result = subprocess.run(
                ['python3', script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=os.path.dirname(script_path),
                env={
                    **os.environ,
                    'PYTHONIOENCODING': 'utf-8'
                }
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                parsed_results = None
                
                # Marker-based extraction (Primary)
                if "<JSON_START>" in output and "<JSON_END>" in output:
                    try:
                        json_str = output.split("<JSON_START>")[1].split("<JSON_END>")[0]
                        parsed_results = json.loads(json_str)
                    except Exception as e:
                        return {
                            "success": False, 
                            "output": output,
                            "error": f"Failed to parse marked JSON: {e}",
                            "code": code
                        }
                else:
                    # Fallback: Robust JSON extraction
                    candidates = [i for i, c in enumerate(output) if c == '{']
                    last_end = -1
                    
                    for start_idx in candidates:
                        if start_idx < last_end:
                            continue # Skip nested objects
                            
                        try:
                            # Attempt to parse from this position
                            brace_count = 0
                            end_idx = -1
                            for i in range(start_idx, len(output)):
                                if output[i] == '{':
                                    brace_count += 1
                                elif output[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_idx = i + 1
                                        break
                            
                            if end_idx != -1:
                                candidate_json = output[start_idx:end_idx]
                                obj = json.loads(candidate_json)
                                # If it's a dict, it's a candidate for results
                                if isinstance(obj, dict):
                                    parsed_results = obj
                                    last_end = end_idx # Update end pointer to skip nested
                        except json.JSONDecodeError:
                            continue
                
                return {
                    "success": True,
                    "output": output,
                    "error": None,
                    "results": parsed_results,
                    "code": code
                }
            else:
                return {
                    "success": False,
                    "output": result.stdout,
                    "error": result.stderr,
                    "results": None,
                    "code": code
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": None,
                "error": f"Execution timed out after {self.timeout} seconds",
                "results": None,
                "code": code
            }
        except Exception as e:
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "results": None,
                "code": code
            }
        finally:
            # Cleanup temp file
            try:
                os.unlink(script_path)
            except:
                pass
    
    def validate_code(self, code: str) -> Tuple[bool, str]:
        """
        Basic validation of generated code.
        Returns (is_valid, error_message).
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        banned_calls = {"eval", "exec", "compile", "__import__", "open", "input", "globals", "locals"}
        banned_modules = {"subprocess", "socket", "requests", "urllib", "pathlib", "shutil"}
        restricted_modules = {"os", "sys"}
        banned_attrs = {"system", "popen", "Popen", "run", "call", "check_call", "check_output", "spawn", "fork", "exec", "execv", "execve"}
        allowed_os_calls = {"path", "makedirs", "getcwd"}
        allowed_sys_calls = {"path"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod in banned_modules or mod not in self.ALLOWED_IMPORTS:
                        return False, f"Import not allowed: {mod}"
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in banned_modules or mod not in self.ALLOWED_IMPORTS:
                    return False, f"Import not allowed: {mod}"
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in banned_calls:
                    return False, f"Call not allowed: {func.id}"
                if isinstance(func, ast.Attribute):
                    if isinstance(func.value, ast.Name) and func.value.id in banned_modules:
                        if func.attr in banned_attrs:
                            return False, f"Call not allowed: {func.value.id}.{func.attr}"
                    if isinstance(func.value, ast.Name) and func.value.id in restricted_modules:
                        base = func.value.id
                        if base == "os" and func.attr not in allowed_os_calls:
                            return False, f"Call not allowed: os.{func.attr}"
                        if base == "sys" and func.attr not in allowed_sys_calls:
                            return False, f"Call not allowed: sys.{func.attr}"
                    if isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name):
                        base = func.value.value.id
                        if base == "os" and func.value.attr == "path":
                            pass
                        elif base == "sys" and func.value.attr == "path":
                            pass
                        elif base in restricted_modules:
                            return False, f"Call not allowed: {base}.{func.value.attr}.{func.attr}"

        return True, ""

    def _sandbox_header(self) -> str:
        mem_bytes = int(self.max_memory) * 1024 * 1024
        cpu_limit = int(self.timeout)
        return (
            "import os\n"
            "try:\n"
            "    import resource\n"
            f"    resource.setrlimit(resource.RLIMIT_AS, ({mem_bytes}, {mem_bytes}))\n"
            f"    resource.setrlimit(resource.RLIMIT_CPU, ({cpu_limit}, {cpu_limit}))\n"
            "except Exception:\n"
            "    pass\n"
        )
    
    def execute_stream(self, code: str, dataset_path: str = None, emit_done: bool = True):
        """
        Execute Python code and stream output line-by-line.
        
        Yields:
            dict: {"type": "log", "data": str} for stdout lines
            dict: {"type": "error", "data": str} for errors
            dict: {"type": "result", "data": dict} for final parsed JSON
            dict: {"type": "done"} at the end
        """
        ok, err = self.validate_code(code)
        if not ok:
            yield {"type": "error", "data": err}
            if emit_done:
                yield {"type": "done"}
            return

        # Replace dataset_path placeholder if provided
        if dataset_path:
            code = code.replace('{dataset_path}', dataset_path)
            code = code.replace('{{dataset_path}}', dataset_path)
        
        code = self._sandbox_header() + "\n" + code

        # Create temp file for execution
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            script_path = f.name
        
        try:
            # Start process with Popen for streaming
            process = subprocess.Popen(
                ['python3', '-u', script_path],  # -u for unbuffered output
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(script_path),
                env={
                    **os.environ,
                    'PYTHONUNBUFFERED': '1',
                    'PYTHONIOENCODING': 'utf-8'
                }
            )
            
            full_output = []
            
            # Stream stdout line by line
            for line in iter(process.stdout.readline, ''):
                full_output.append(line)
                yield {"type": "log", "data": line.rstrip('\n')}
            
            # Wait for process to complete
            process.wait(timeout=self.timeout)
            
            # Read any stderr
            stderr = process.stderr.read()
            if stderr:
                yield {"type": "error", "data": stderr}
            
            # Parse results from full output
            output = ''.join(full_output).strip()
            parsed_results = None
            
            if process.returncode == 0:
                # Marker-based extraction (Primary)
                if "<JSON_START>" in output and "<JSON_END>" in output:
                    try:
                        json_str = output.split("<JSON_START>")[1].split("<JSON_END>")[0]
                        parsed_results = json.loads(json_str)
                    except:
                        pass # Fallback to candidates
                
                if parsed_results is None:
                    # Fallback: Robust JSON extraction
                    candidates = [i for i, c in enumerate(output) if c == '{']
                    last_end = -1
                    
                    for start_idx in candidates:
                        if start_idx < last_end:
                            continue
                        try:
                            brace_count = 0
                            end_idx = -1
                            for i in range(start_idx, len(output)):
                                if output[i] == '{':
                                    brace_count += 1
                                elif output[i] == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end_idx = i + 1
                                        break
                            
                            if end_idx != -1:
                                candidate_json = output[start_idx:end_idx]
                                obj = json.loads(candidate_json)
                                if isinstance(obj, dict):
                                    parsed_results = obj
                                    last_end = end_idx
                        except json.JSONDecodeError:
                            continue
                
                yield {"type": "result", "data": parsed_results, "code": code}
            else:
                yield {"type": "error", "data": f"Process exited with code {process.returncode}"}
            
            if emit_done:
                yield {"type": "done"}
            
        except subprocess.TimeoutExpired:
            process.kill()
            yield {"type": "error", "data": f"Execution timed out after {self.timeout} seconds"}
            if emit_done:
                yield {"type": "done"}
        except Exception as e:
            yield {"type": "error", "data": str(e)}
            if emit_done:
                yield {"type": "done"}
        finally:
            try:
                os.unlink(script_path)
            except:
                pass
