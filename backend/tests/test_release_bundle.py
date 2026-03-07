import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import analysis


client = TestClient(app)


def _write(path: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(payload)


def test_release_bundle_endpoint_builds_zip_with_manifest(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_id = "ds_release_bundle"
        run_id = "run_1"
        dataset_dir = os.path.join(tmpdir, dataset_id)
        run_dir = os.path.join(dataset_dir, "analysis", run_id)
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(os.path.join(run_dir, "protocol.json"), b'{"name":"protocol","steps":[]}')
        _write(
            os.path.join(run_dir, "results.json"),
            b'{"dataset_id":"ds_release_bundle","status":"completed","results":{"s1":{"type":"hypothesis_test","p_value":0.03}},"errors":[],"warnings":[]}',
        )
        _write(os.path.join(run_dir, "run_state.json"), b'{"state":"release","artifacts":{},"missing_artifacts":[]}')

        _write(os.path.join(dataset_dir, "source", "meta.json"), b'{"original_filename":"source.xlsx"}')
        _write(os.path.join(dataset_dir, "source", "original.raw"), b"raw")
        _write(os.path.join(dataset_dir, "processed", "profile.json"), b'{"schema":"clinimetria.profile"}')
        _write(os.path.join(dataset_dir, "processed", "data_lineage.json"), b'{"schema":"clinimetria.data_lineage"}')
        _write(os.path.join(dataset_dir, "processed", f"{dataset_id}.parquet"), b"PAR1")
        _write(
            os.path.join(dataset_dir, "processed", "analysis_set_current.json"),
            b'{"analysis_set_id":"set_1","updated_at":"2026-03-01T00:00:00","version":1}',
        )
        _write(
            os.path.join(dataset_dir, "processed", "analysis_sets", "set_1.json"),
            b'{"analysis_set_id":"set_1","n_selected":3}',
        )
        _write(
            os.path.join(dataset_dir, "processed", "analysis_sets", "set_1.parquet"),
            b"PAR1",
        )

        for name, content in [
            ("reproduce_run.py", b"print('ok')\n"),
            ("reproduce_payload.json", b"{}"),
            ("protocol_resolved.json", b"{}"),
            ("reproducibility_manifest.json", b"{}"),
            ("protocol_report_auto.html", b"<html></html>"),
            ("protocol_report.docx", b"PK\x03\x04DOCX"),
            ("analysis_dataset.parquet", b"PAR1"),
        ]:
            _write(os.path.join(artifacts_dir, name), content)

        run_data = {
            "dataset_id": dataset_id,
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.03,
                }
            },
            "verification": {"status": "passed", "summary": {}},
            "reproducibility": {
                "ready": True,
                "script": "reproduce_run.py",
                "payload": "reproduce_payload.json",
                "protocol": "protocol_resolved.json",
                "manifest": "reproducibility_manifest.json",
            },
        }

        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_data)
        monkeypatch.setattr(
            analysis.pipeline,
            "get_run_state",
            lambda _dataset_id, _run_id: {"state": "release", "missing_artifacts": [], "artifacts": {}},
        )
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(
            analysis.pipeline,
            "read_run_artifact",
            lambda _dataset_id, _run_id, name: open(os.path.join(artifacts_dir, name), "rb").read(),
        )
        monkeypatch.setattr(
            analysis.pipeline,
            "save_run_artifact",
            lambda _run_dir, name, content: _write(os.path.join(artifacts_dir, name), content) or os.path.join(artifacts_dir, name),
        )

        response = client.get(
            f"/api/v1/analysis/protocol/release/{run_id}/zip",
            params={"dataset_id": dataset_id, "refresh": "true"},
        )
        assert response.status_code == 200, response.text
        assert response.headers.get("content-type") == "application/zip"

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            assert "run/protocol.json" in names
            assert "run/results.json" in names
            assert "run/artifacts/reproduce_run.py" in names
            assert "dataset/source/meta.json" in names
            assert "dataset/processed/profile.json" in names
            assert "dataset/processed/data_lineage.json" in names
            assert "dataset/processed/analysis_sets/set_1.parquet" in names
            assert "run/artifacts/protocol_report.docx" in names
            assert "release/README.md" in names
            assert "release/reproduce_run.py" in names
            assert "release/reproduce_run.sh" in names
            assert "release/reproduce_payload.json" in names
            assert "release/release_manifest.json" in names

            manifest = json.loads(archive.read("release/release_manifest.json").decode("utf-8"))
            assert manifest.get("entrypoint") == "release/reproduce_run.sh"
            assert manifest.get("reproduce_payload") == "release/reproduce_payload.json"
            manifest_files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
            assert any(isinstance(row, dict) and row.get("path") == "release/reproduce_run.py" for row in manifest_files)

        assert os.path.exists(os.path.join(artifacts_dir, f"release_bundle_{run_id}.zip"))
        assert os.path.exists(os.path.join(artifacts_dir, "release_manifest.json"))


def test_release_bundle_endpoint_blocks_without_passed_verification(monkeypatch):
    run_data = {
        "dataset_id": "ds_release_fail",
        "results": {"s1": {"type": "hypothesis_test", "p_value": 1.2}},
        "verification": {"status": "failed", "failures": [{"step_id": "s1", "check": "p_value_bounds"}]},
    }
    monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_data)

    response = client.get(
        "/api/v1/analysis/protocol/release/run_fail/zip",
        params={"dataset_id": "ds_release_fail"},
    )
    assert response.status_code == 409, response.text
    assert "верификац" in str(response.text).lower()


def test_release_bundle_generated_script_verifies_manifest(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_id = "ds_release_script"
        run_id = "run_script"
        dataset_dir = os.path.join(tmpdir, dataset_id)
        run_dir = os.path.join(dataset_dir, "analysis", run_id)
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(os.path.join(run_dir, "protocol.json"), b'{"name":"protocol","steps":[]}')
        _write(
            os.path.join(run_dir, "results.json"),
            b'{"dataset_id":"ds_release_script","status":"completed","results":{"s1":{"type":"hypothesis_test","p_value":0.03}},"errors":[],"warnings":[]}',
        )
        _write(os.path.join(run_dir, "run_state.json"), b'{"state":"release","artifacts":{},"missing_artifacts":[]}')

        _write(os.path.join(dataset_dir, "source", "meta.json"), b'{"original_filename":"source.xlsx"}')
        _write(os.path.join(dataset_dir, "source", "original.raw"), b"raw")
        _write(os.path.join(dataset_dir, "processed", "profile.json"), b'{"schema":"clinimetria.profile"}')
        _write(os.path.join(dataset_dir, "processed", f"{dataset_id}.parquet"), b"PAR1")
        _write(os.path.join(artifacts_dir, "reproducibility_manifest.json"), b"{}")

        run_data = {
            "dataset_id": dataset_id,
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.03,
                }
            },
            "verification": {"status": "passed", "summary": {}},
            "reproducibility": {
                "ready": True,
                "script": "reproduce_run.py",
                "payload": "reproduce_payload.json",
                "protocol": "protocol_resolved.json",
                "manifest": "reproducibility_manifest.json",
            },
        }

        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_data)
        monkeypatch.setattr(
            analysis.pipeline,
            "get_run_state",
            lambda _dataset_id, _run_id: {"state": "release", "missing_artifacts": [], "artifacts": {}},
        )
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(
            analysis.pipeline,
            "read_run_artifact",
            lambda _dataset_id, _run_id, name: open(os.path.join(artifacts_dir, name), "rb").read(),
        )
        monkeypatch.setattr(
            analysis.pipeline,
            "save_run_artifact",
            lambda _run_dir, name, content: _write(os.path.join(artifacts_dir, name), content) or os.path.join(artifacts_dir, name),
        )

        response = client.get(
            f"/api/v1/analysis/protocol/release/{run_id}/zip",
            params={"dataset_id": dataset_id, "refresh": "true"},
        )
        assert response.status_code == 200, response.text

        extract_dir = os.path.join(tmpdir, "bundle_extract")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            archive.extractall(extract_dir)

        script_path = os.path.join(extract_dir, "release", "reproduce_run.py")
        completed = subprocess.run(
            [sys.executable, script_path, "--bundle-dir", extract_dir],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert "Manifest verification OK" in (completed.stdout or "")
