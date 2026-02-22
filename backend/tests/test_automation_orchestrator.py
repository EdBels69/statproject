from fastapi.testclient import TestClient


def test_stats_endpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from automation.orchestrator import app

    with TestClient(app) as client:
        stats = client.get("/api/stats")
        assert stats.status_code == 200
        body = stats.json()
        assert "counts" in body
        assert "kpi" in body


def test_create_task_includes_operations_and_retries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from automation.orchestrator import app

    with TestClient(app) as client:
        resp = client.post(
            "/api/task",
            json={
                "description": "run checks",
                "requirements": ["pytest", "lint"],
                "priority": "medium",
                "type": "code",
                "operations": [
                    {"type": "run", "cwd": "backend", "command": "python3 -m pytest -q"},
                    {"type": "run", "cwd": "frontend", "command": "npm run lint"},
                ],
                "max_retries": 3,
            },
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "queued"


def test_retry_task_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from automation.orchestrator import app

    with TestClient(app) as client:
        resp = client.post("/api/task/task_missing/retry")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_found"
