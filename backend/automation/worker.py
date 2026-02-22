import json
import os
import shutil
import subprocess
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


TASKS_DIR = os.getenv("TASKS_DIR", "workspace/tasks")
INCOMING = os.path.join(TASKS_DIR, "incoming")
PROCESSING = os.path.join(TASKS_DIR, "processing")
COMPLETED = os.path.join(TASKS_DIR, "completed")
FAILED = os.path.join(TASKS_DIR, "failed")


@dataclass
class ExecResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float


def _now() -> float:
    return time.time()


def _truthy_env(name: str) -> bool:
    val = os.getenv(name)
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _ensure_dirs() -> None:
    for d in [INCOMING, PROCESSING, COMPLETED, FAILED]:
        os.makedirs(d, exist_ok=True)


def _append_log(task: Dict[str, Any], level: str, message: str) -> None:
    task.setdefault("log", []).append({"ts": _now(), "level": level, "message": message})


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    head = text[:2000]
    tail = text[-2000:]
    return head + "\n...\n" + tail


def _load_task(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_task(path: str, task: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task, f, indent=2, ensure_ascii=False)


def _move(src: str, dest_dir: str) -> str:
    dest_path = os.path.join(dest_dir, os.path.basename(src))
    shutil.move(src, dest_path)
    return dest_path


def _due(task: Dict[str, Any]) -> bool:
    next_run_at = task.get("next_run_at")
    if next_run_at is None:
        return True
    try:
        return float(next_run_at) <= _now()
    except Exception:
        return True


def _op_key(op: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        str(op.get("type", "")),
        str(op.get("cwd", ".")),
        str(op.get("command", op.get("message", ""))),
    )


def _merge_operations(primary: List[Dict[str, Any]], gates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    merged: List[Dict[str, Any]] = []

    for op in primary:
        key = _op_key(op)
        if key in seen:
            continue
        seen.add(key)
        merged.append(op)

    for op in gates:
        key = _op_key(op)
        if key in seen:
            continue
        seen.add(key)
        merged.append(op)

    return merged


def _default_quality_gates(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    task_type = str(task.get("type", "")).strip().lower()
    if task_type != "code":
        return []

    return [
        {
            "type": "run",
            "cwd": "backend",
            "command": "python3 -m pytest -q",
            "timeout_s": 1200,
        },
        {
            "type": "run",
            "cwd": "frontend",
            "command": "npm run lint",
            "timeout_s": 900,
        },
        {
            "type": "run",
            "cwd": "frontend",
            "command": "npm run build",
            "timeout_s": 1200,
        },
    ]


def _order_operations(ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    non_commit: List[Dict[str, Any]] = []
    commits: List[Dict[str, Any]] = []

    for op in ops:
        if op.get("type") == "git_commit":
            commits.append(op)
        else:
            non_commit.append(op)

    return non_commit + commits


def _infer_operations(task: Dict[str, Any]) -> List[Dict[str, Any]]:
    ops = task.get("operations")
    gates = task.get("quality_gates")
    provided_gates = gates if isinstance(gates, list) else []
    quality_gates = _merge_operations(_default_quality_gates(task), provided_gates)

    if isinstance(ops, list) and ops:
        return _order_operations(_merge_operations(ops, quality_gates))

    text = " ".join(
        [
            str(task.get("description", "")),
            " ".join([str(x) for x in task.get("requirements", [])]),
            str(task.get("type", "")),
        ]
    ).lower()

    inferred: List[Dict[str, Any]] = []

    if any(k in text for k in ["pytest", "test", "tests", "backend"]):
        inferred.append(
            {
                "type": "run",
                "cwd": "backend",
                "command": "python3 -m pytest -q",
                "timeout_s": 1200,
            }
        )

    if any(k in text for k in ["eslint", "lint", "frontend"]):
        inferred.append(
            {
                "type": "run",
                "cwd": "frontend",
                "command": "npm run lint",
                "timeout_s": 900,
            }
        )

    if "build" in text:
        inferred.append(
            {
                "type": "run",
                "cwd": "frontend",
                "command": "npm run build",
                "timeout_s": 1200,
            }
        )

    if not inferred:
        inferred.append({"type": "noop"})

    merged = _merge_operations(inferred, quality_gates)
    if merged and merged[0].get("type") == "noop" and any(op.get("type") != "noop" for op in merged[1:]):
        merged = [op for op in merged if op.get("type") != "noop"]

    return _order_operations(merged)


def _run_command(command: str, cwd: str, timeout_s: float) -> ExecResult:
    start = _now()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            env={**os.environ, "PAGER": "cat"},
        )
        ok = proc.returncode == 0
        return ExecResult(
            ok=ok,
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_s=_now() - start,
        )
    except subprocess.TimeoutExpired as e:
        return ExecResult(
            ok=False,
            exit_code=124,
            stdout=getattr(e, "stdout", "") or "",
            stderr=getattr(e, "stderr", "") or "timeout",
            duration_s=_now() - start,
        )


def _git_head(repo_root: str) -> Optional[str]:
    res = _run_command("git rev-parse HEAD", cwd=os.path.abspath(repo_root), timeout_s=15)
    if not res.ok:
        return None
    head = (res.stdout or "").strip()
    return head or None


def _git_is_work_tree(repo_root: str) -> bool:
    res = _run_command(
        "git rev-parse --is-inside-work-tree",
        cwd=os.path.abspath(repo_root),
        timeout_s=15,
    )
    return res.ok and (res.stdout or "").strip() == "true"


def _git_rollback_to(repo_root: str, rev: str) -> Dict[str, Any]:
    cwd = os.path.abspath(repo_root)
    if not _git_is_work_tree(cwd):
        return {"attempted": False, "ok": False, "error": "not a git work tree"}

    reset = _run_command(f"git reset --hard {json.dumps(rev)}", cwd=cwd, timeout_s=120)
    clean = _run_command("git clean -fd", cwd=cwd, timeout_s=120)
    head_after = _git_head(cwd)

    ok = reset.ok and clean.ok
    return {
        "attempted": True,
        "ok": ok,
        "rev": rev,
        "head_after": head_after,
        "reset": {
            "ok": reset.ok,
            "exit_code": reset.exit_code,
            "stdout": _truncate(reset.stdout),
            "stderr": _truncate(reset.stderr),
            "duration_s": reset.duration_s,
        },
        "clean": {
            "ok": clean.ok,
            "exit_code": clean.exit_code,
            "stdout": _truncate(clean.stdout),
            "stderr": _truncate(clean.stderr),
            "duration_s": clean.duration_s,
        },
    }


def _execute_operation(op: Dict[str, Any], repo_root: str) -> Tuple[bool, Dict[str, Any]]:
    op_type = op.get("type")
    if op_type == "noop":
        return True, {"type": "noop"}

    if op_type == "run":
        rel_cwd = str(op.get("cwd", "."))
        cwd = os.path.abspath(os.path.join(repo_root, rel_cwd))
        command = str(op.get("command", "")).strip()
        timeout_s = float(op.get("timeout_s", 600))

        if not command:
            return False, {"type": "run", "error": "empty command", "cwd": rel_cwd}

        res = _run_command(command, cwd=cwd, timeout_s=timeout_s)
        payload = {
            "type": "run",
            "cwd": rel_cwd,
            "command": command,
            "ok": res.ok,
            "exit_code": res.exit_code,
            "duration_s": res.duration_s,
            "stdout": _truncate(res.stdout),
            "stderr": _truncate(res.stderr),
        }
        return res.ok, payload

    if op_type == "git_commit":
        message = str(op.get("message", "automation: update")).strip()
        allow_empty = bool(op.get("allow_empty", False))
        timeout_s = float(op.get("timeout_s", 120))
        cwd = os.path.abspath(repo_root)

        status = _run_command("git status --porcelain", cwd=cwd, timeout_s=timeout_s)
        has_changes = bool((status.stdout or "").strip())

        if not has_changes and not allow_empty:
            return True, {
                "type": "git_commit",
                "ok": True,
                "skipped": True,
                "reason": "no changes",
                "duration_s": status.duration_s,
            }

        add_res = _run_command("git add -A", cwd=cwd, timeout_s=timeout_s)
        if not add_res.ok:
            return False, {
                "type": "git_commit",
                "ok": False,
                "stage": "add",
                "exit_code": add_res.exit_code,
                "stdout": _truncate(add_res.stdout),
                "stderr": _truncate(add_res.stderr),
                "duration_s": add_res.duration_s,
            }

        commit_cmd = f"git commit -m {json.dumps(message)}"
        if allow_empty:
            commit_cmd += " --allow-empty"

        commit_res = _run_command(commit_cmd, cwd=cwd, timeout_s=timeout_s)
        payload = {
            "type": "git_commit",
            "ok": commit_res.ok,
            "message": message,
            "allow_empty": allow_empty,
            "exit_code": commit_res.exit_code,
            "stdout": _truncate(commit_res.stdout),
            "stderr": _truncate(commit_res.stderr),
            "duration_s": commit_res.duration_s,
        }
        return commit_res.ok, payload

    return False, {"type": str(op_type), "error": "unsupported operation"}


def _process_task_file(filename: str, repo_root: str) -> None:
    src = os.path.join(INCOMING, filename)
    processing_path = os.path.join(PROCESSING, filename)

    safe_mode = _truthy_env("SAFE_MODE") or _truthy_env("WORKER_SAFE_MODE")
    rollback_rev: Optional[str] = None
    rollback_enabled = False

    try:
        shutil.move(src, processing_path)
    except FileNotFoundError:
        return

    try:
        task = _load_task(processing_path)
        if not _due(task):
            _move(processing_path, INCOMING)
            return

        task_id = str(task.get("task_id") or filename.replace(".json", ""))
        task["task_id"] = task_id
        task["status"] = "processing"
        task["started_at"] = task.get("started_at") or _now()
        task["worker"] = {"pid": os.getpid()}

        created_at = task.get("created_at")
        if created_at is not None:
            try:
                task.setdefault("metrics", {})["queue_wait_s"] = max(0.0, _now() - float(created_at))
            except Exception:
                pass

        _append_log(task, "info", f"picked: {task_id}")
        _append_log(task, "info", f"description: {task.get('description', '')}")

        task_type = str(task.get("type", "")).strip().lower()
        rollback_enabled = safe_mode and task_type == "code"
        if rollback_enabled:
            rollback_rev = _git_head(repo_root)
            task["rollback"] = {"enabled": True, "rev": rollback_rev}

        operations = _infer_operations(task)
        task["operations"] = operations
        task.setdefault("attempt", 0)
        task.setdefault("max_retries", 2)
        task["attempt"] = int(task["attempt"]) + 1

        op_results: List[Dict[str, Any]] = []
        all_ok = True
        for idx, op in enumerate(operations):
            _append_log(task, "info", f"op_start: {idx}:{op.get('type')}")
            op_started_at = _now()
            ok, payload = _execute_operation(op, repo_root=repo_root)
            payload["started_at"] = op_started_at
            payload["ended_at"] = _now()
            op_results.append(payload)
            _append_log(task, "info", f"op_end: {idx}:{'ok' if ok else 'fail'}")
            if not ok:
                all_ok = False
                break

        task["op_results"] = op_results

        if all_ok:
            task["status"] = "completed"
            task["completed_at"] = _now()
            try:
                task.setdefault("metrics", {})["total_duration_s"] = max(
                    0.0, float(task["completed_at"]) - float(task["started_at"])
                )
            except Exception:
                pass
            _append_log(task, "info", "completed")
            _save_task(processing_path, task)
            _move(processing_path, COMPLETED)
            return

        if rollback_enabled and rollback_rev:
            rb = _git_rollback_to(repo_root, rollback_rev)
            task["rollback"] = {**task.get("rollback", {}), **{"result": rb}}
            _append_log(task, "info" if rb.get("ok") else "error", "rollback_attempted")

        err_summary = "operation failed"
        task["status"] = "failed"
        task["failed_at"] = _now()
        try:
            task.setdefault("metrics", {})["total_duration_s"] = max(
                0.0, float(task["failed_at"]) - float(task["started_at"])
            )
        except Exception:
            pass
        task["error"] = {"message": err_summary}
        _append_log(task, "error", err_summary)

        max_retries = int(task.get("max_retries", 0))
        if int(task.get("attempt", 1)) <= max_retries:
            backoff_s = min(300, 2 ** int(task.get("attempt", 1)))
            task["status"] = "pending"
            task["next_run_at"] = _now() + backoff_s
            _append_log(task, "info", f"retry_scheduled: {backoff_s}")
            _save_task(processing_path, task)
            _move(processing_path, INCOMING)
            return

        _save_task(processing_path, task)
        _move(processing_path, FAILED)

    except Exception as e:
        try:
            task = _load_task(processing_path)
        except Exception:
            task = {"task_id": filename.replace(".json", ""), "status": "failed"}

        task_type = str(task.get("type", "")).strip().lower()
        if safe_mode and task_type == "code" and rollback_rev:
            rb = _git_rollback_to(repo_root, rollback_rev)
            task["rollback"] = {"enabled": True, "rev": rollback_rev, "result": rb}

        task["status"] = "failed"
        task["failed_at"] = _now()
        task["error"] = {"message": str(e), "trace": traceback.format_exc()}
        _append_log(task, "error", str(e))
        _save_task(processing_path, task)
        _move(processing_path, FAILED)


def main() -> None:
    _ensure_dirs()
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    print(f"worker_started tasks_dir={os.path.abspath(TASKS_DIR)}")

    idle_sleep_s = float(os.getenv("WORKER_IDLE_SLEEP_S", "1.5"))
    max_batch = int(os.getenv("WORKER_MAX_BATCH", "10"))

    while True:
        try:
            files = [f for f in os.listdir(INCOMING) if f.endswith(".json")]
            files.sort()
            if not files:
                time.sleep(idle_sleep_s)
                continue

            for f in files[:max_batch]:
                _process_task_file(f, repo_root=repo_root)

        except Exception:
            time.sleep(2.0)


if __name__ == "__main__":
    main()
