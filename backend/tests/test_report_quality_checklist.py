import json
import os
import sys
import tempfile

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import analysis


client = TestClient(app)


def _write(path: str, payload: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)


def _minimal_design_payload() -> str:
    return json.dumps(
        {"design": {"design_type": "cohort", "group_column": "group"}, "analysis_policy": {"alpha": 0.05}},
        ensure_ascii=False,
    )


def _minimal_run_payload(method_ok: bool = True) -> dict:
    result = {
        "type": "hypothesis_test",
        "p_value": 0.01,
        "stat_value": 2.5,
        "effect_size": 0.7,
        "conclusion": "Significant between-group difference.",
    }
    if method_ok:
        result["method"] = {"id": "t_test_ind", "name": "Independent t-test"}
        result["method_id"] = "t_test_ind"
    return {"dataset_id": "ds_quality", "results": {"step_1": result}}


def test_report_quality_endpoint_passes_with_full_artifacts(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_1")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(os.path.join(dataset_dir, "processed", "study_design.json"), _minimal_design_payload())
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
            "protocol_report_run_1.html",
            "protocol_report_run_1.pdf",
            "protocol_report_run_1.docx",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: _minimal_run_payload(method_ok=True))

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_1/quality",
            params={"dataset_id": "ds_quality", "require_exports": "true", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()

        assert payload.get("status") == "pass"
        assert payload.get("ready") is True
        checks = payload.get("checks") or {}
        assert (checks.get("design_artifact") or {}).get("ok") is True
        assert (checks.get("methods_metadata") or {}).get("ok") is True
        assert "verification_gate" in checks
        assert "provenance_trace" in checks
        assert (checks.get("sections") or {}).get("ok") is True
        assert (checks.get("analysis_dataset_artifacts") or {}).get("ok") is True
        assert (checks.get("report_exports") or {}).get("ok") is True


def test_report_quality_endpoint_fails_when_methods_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_2")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(os.path.join(dataset_dir, "processed", "study_design.json"), _minimal_design_payload())
        os.makedirs(artifacts_dir, exist_ok=True)

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: _minimal_run_payload(method_ok=False))

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_2/quality",
            params={"dataset_id": "ds_quality", "require_exports": "false", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()

        assert payload.get("status") == "fail"
        assert payload.get("ready") is False
        missing = payload.get("missing") or []
        assert "methods_metadata" in missing
        checks = payload.get("checks") or {}
        assert (checks.get("methods_metadata") or {}).get("ok") is False


def test_enrich_run_data_for_report_adds_run_id_and_step_meta(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = os.path.join(tmpdir, "analysis", "run_html")
        os.makedirs(run_dir, exist_ok=True)
        protocol_payload = {
            "name": "proto",
            "steps": [
                {"id": "s1", "method": "t_test_ind", "config": {"target": "x", "group": "g"}},
                {"id": "s2", "method": "time_series_analysis", "config": {"outcome": "crp", "time": "ID"}},
            ],
        }
        _write(os.path.join(run_dir, "protocol.json"), json.dumps(protocol_payload, ensure_ascii=False))

        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        base = {"dataset_id": "ds_x", "results": {"s1": {"type": "hypothesis_test"}}}
        enriched = analysis._enrich_run_data_for_report(base, "ds_x", "run_html")

        assert isinstance(enriched, dict)
        assert enriched.get("run_id") == "run_html"
        step_meta = enriched.get("step_meta")
        assert isinstance(step_meta, dict)
        assert "s1" in step_meta
        assert "s2" in step_meta


def test_report_quality_endpoint_fails_when_verification_required_and_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_3")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(os.path.join(dataset_dir, "processed", "study_design.json"), _minimal_design_payload())
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
            "protocol_report_run_3.html",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(
            analysis.pipeline,
            "get_run_results",
            lambda _dataset_id, _run_id: _minimal_run_payload(method_ok=True),
        )
        monkeypatch.setattr(
            analysis.pipeline,
            "get_run_state",
            lambda _dataset_id, _run_id: {"state": "release", "missing_artifacts": [], "artifacts": {}},
        )

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_3/quality",
            params={
                "dataset_id": "ds_quality",
                "require_exports": "false",
                "require_verification": "true",
                "style": "apa7",
            },
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload.get("status") == "fail"
        assert "verification_gate" in (payload.get("missing") or [])
