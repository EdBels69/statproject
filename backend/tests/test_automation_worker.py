import os
import json
import subprocess


def test_infer_operations_defaults_to_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    from automation import worker

    task = {"description": "do something", "requirements": [], "type": "data"}
    ops = worker._infer_operations(task)
    assert isinstance(ops, list)
    assert ops and ops[0]["type"] == "noop"


def test_infer_operations_detects_backend_tests(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    from automation import worker

    task = {"description": "run backend tests", "requirements": ["pytest"], "type": "code"}
    ops = worker._infer_operations(task)
    assert any(op.get("type") == "run" and op.get("cwd") == "backend" for op in ops)


def test_execute_operation_run_uses_repo_root(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    from automation import worker

    called = {}

    def fake_run_command(command, cwd, timeout_s):
        called["command"] = command
        called["cwd"] = cwd
        called["timeout_s"] = timeout_s
        return worker.ExecResult(ok=True, exit_code=0, stdout="ok", stderr="", duration_s=0.01)

    monkeypatch.setattr(worker, "_run_command", fake_run_command)
    repo_root = str(tmp_path / "repo")
    os.makedirs(os.path.join(repo_root, "backend"), exist_ok=True)

    ok, payload = worker._execute_operation(
        {"type": "run", "cwd": "backend", "command": "python3 -m pytest -q", "timeout_s": 1},
        repo_root=repo_root,
    )

    assert ok is True
    assert payload["ok"] is True
    assert called["cwd"].endswith("repo/backend")


def test_infer_operations_appends_quality_gates(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    from automation import worker

    task = {
        "description": "run backend tests",
        "requirements": ["pytest"],
        "type": "code",
        "quality_gates": [{"type": "run", "cwd": "frontend", "command": "npm run lint"}],
    }

    ops = worker._infer_operations(task)
    assert any(op.get("cwd") == "backend" for op in ops)
    assert any(op.get("cwd") == "frontend" and "lint" in op.get("command", "") for op in ops)


def test_infer_operations_includes_default_quality_gates_for_code(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    from automation import worker

    task = {"description": "do something", "requirements": [], "type": "code"}
    ops = worker._infer_operations(task)

    assert all(op.get("type") != "noop" for op in ops)
    assert any(op.get("type") == "run" and op.get("cwd") == "backend" and "pytest" in op.get("command", "") for op in ops)
    assert any(op.get("type") == "run" and op.get("cwd") == "frontend" and "lint" in op.get("command", "") for op in ops)
    assert any(op.get("type") == "run" and op.get("cwd") == "frontend" and "build" in op.get("command", "") for op in ops)


def test_infer_operations_orders_git_commit_last(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    from automation import worker

    task = {
        "description": "do something",
        "requirements": [],
        "type": "code",
        "operations": [
            {"type": "git_commit", "message": "x"},
            {"type": "run", "cwd": "backend", "command": "python3 -m pytest -q"},
        ],
    }

    ops = worker._infer_operations(task)
    assert ops[-1].get("type") == "git_commit"


def test_safe_mode_rolls_back_repo_on_failed_code_task(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.setenv("SAFE_MODE", "1")
    from automation import worker

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    def run(cmd: str) -> str:
        res = subprocess.run(cmd, shell=True, cwd=str(repo_root), check=True, text=True, capture_output=True)
        return (res.stdout or "") + (res.stderr or "")

    run("git init")
    run("git config user.email test@example.com")
    run("git config user.name test")
    (repo_root / "foo.txt").write_text("base\n", encoding="utf-8")
    run("git add -A")
    run("git commit -m base")

    worker._ensure_dirs()

    task = {
        "task_id": "t1",
        "type": "code",
        "description": "mutate repo then fail",
        "max_retries": 0,
        "operations": [
            {
                "type": "run",
                "cwd": ".",
                "command": "python3 -c \"open('foo.txt','w',encoding='utf-8').write('changed\\n')\"",
            },
            {"type": "run", "cwd": ".", "command": "python3 -c \"import sys; sys.exit(1)\""},
        ],
    }

    incoming_path = os.path.join(worker.INCOMING, "t1.json")
    os.makedirs(os.path.dirname(incoming_path), exist_ok=True)
    with open(incoming_path, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False)

    worker._process_task_file("t1.json", repo_root=str(repo_root))

    assert (repo_root / "foo.txt").read_text(encoding="utf-8") == "base\n"
    assert run("git status --porcelain").strip() == ""

    failed_path = os.path.join(worker.FAILED, "t1.json")
    assert os.path.exists(failed_path)
    with open(failed_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved.get("rollback", {}).get("enabled") is True
    assert saved.get("rollback", {}).get("result", {}).get("attempted") is True
    assert saved.get("rollback", {}).get("result", {}).get("ok") is True


def test_without_safe_mode_does_not_rollback_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_DIR", str(tmp_path / "tasks"))
    monkeypatch.delenv("SAFE_MODE", raising=False)
    from automation import worker

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    def run(cmd: str) -> str:
        res = subprocess.run(cmd, shell=True, cwd=str(repo_root), check=True, text=True, capture_output=True)
        return (res.stdout or "") + (res.stderr or "")

    run("git init")
    run("git config user.email test@example.com")
    run("git config user.name test")
    (repo_root / "foo.txt").write_text("base\n", encoding="utf-8")
    run("git add -A")
    run("git commit -m base")

    worker._ensure_dirs()

    task = {
        "task_id": "t2",
        "type": "code",
        "description": "mutate repo then fail",
        "max_retries": 0,
        "operations": [
            {
                "type": "run",
                "cwd": ".",
                "command": "python3 -c \"open('foo.txt','w',encoding='utf-8').write('changed\\n')\"",
            },
            {"type": "run", "cwd": ".", "command": "python3 -c \"import sys; sys.exit(1)\""},
        ],
    }

    incoming_path = os.path.join(worker.INCOMING, "t2.json")
    os.makedirs(os.path.dirname(incoming_path), exist_ok=True)
    with open(incoming_path, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False)

    worker._process_task_file("t2.json", repo_root=str(repo_root))

    assert (repo_root / "foo.txt").read_text(encoding="utf-8") == "changed\n"
    assert run("git status --porcelain").strip() != ""
