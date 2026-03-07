"""
Script Executor: Safely executes generated analysis scripts and captures output.
Provides isolation and error handling.
"""
import subprocess
import json
import tempfile
import os
from typing import Dict, Any
from pathlib import Path


class ScriptExecutor:
    """
    Executes generated Python scripts in a controlled environment.
    Captures stdout, stderr, and return code.
    """
    
    def __init__(self, timeout_seconds: int = 300):
        """
        Args:
            timeout_seconds: Maximum execution time for scripts
        """
        self.timeout = timeout_seconds
    
    def execute(self, script_code: str) -> Dict[str, Any]:
        """
        Execute a Python script and return parsed results.
        
        Args:
            script_code: Python code to execute
            
        Returns:
            Dict with:
                - success: bool
                - results: parsed JSON from script stdout
                - error: error message if failed
                - audit_log: transparency log from script
        """
        # Create temporary file for script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script_code)
            script_path = f.name
        
        try:
            # Execute script
            result = subprocess.run(
                ['python3', script_path],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # Parse output
            if result.returncode == 0:
                try:
                    output = json.loads(result.stdout)
                    return {
                        "success": True,
                        "results": output.get("results", {}),
                        "audit_log": output.get("audit_log", []),
                        "summary": output.get("summary", {}),
                        "script_path": script_path  # For debugging
                    }
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed to parse script output: {str(e)}",
                        "stdout": result.stdout,
                        "stderr": result.stderr
                    }
            else:
                return {
                    "success": False,
                    "error": f"Script failed with return code {result.returncode}",
                    "stderr": result.stderr,
                    "stdout": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Script execution timeout after {self.timeout} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution error: {str(e)}"
            }
        finally:
            # Cleanup (optionally keep for debugging)
            # os.unlink(script_path)
            pass
    
    def execute_and_save(self, script_code: str, output_dir: str) -> Dict[str, Any]:
        """
        Execute script and save both the script and results to disk.
        Useful for reproducibility and debugging.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save script
        script_file = output_path / "analysis_script.py"
        script_file.write_text(script_code)
        
        # Execute
        exec_result = self.execute(script_code)
        
        # Save results
        results_file = output_path / "results.json"
        results_file.write_text(json.dumps(exec_result, ensure_ascii=False, indent=2))
        
        exec_result["saved_to"] = str(output_path)
        return exec_result
