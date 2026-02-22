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


def _minimal_publication_run_payload() -> dict:
    result = {
        "type": "hypothesis_test",
        "p_value": 0.01,
        "stat_value": 2.5,
        "effect_size": 0.7,
        "conclusion": "Significant between-group difference.",
        "method": {"id": "t_test_ind", "name": "Independent t-test"},
        "method_id": "t_test_ind",
    }
    return {
        "dataset_id": "ds_quality",
        "publication_mode": True,
        "analysis_mode": "publication",
        "results": {"step_1": result},
        "step_meta": {"step_1": {"method": "t_test_ind", "config": {"outcome": "outcome", "group": "group"}}},
        "design_review": {"confirmed": False},
        "analysis_set": {"artifact_exists": False, "strict": False},
        "cleaning_artifact": {"valid": False},
    }


def _full_contract(tag: str = "ok") -> dict:
    return {
        "claim": f"Claim {tag}",
        "evidence": f"Evidence {tag}",
        "clinical_meaning": f"Clinical meaning {tag}",
        "limitations": f"Limitations {tag}",
        "actionable_next_step": f"Action {tag}",
    }


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


def test_report_quality_endpoint_publication_requires_reproducibility(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_pub")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(
            os.path.join(dataset_dir, "processed", "study_design.json"),
            json.dumps(
                {
                    "design": {
                        "design_type": "cohort",
                        "group_column": "group",
                        "outcomes": ["outcome"],
                        "categorical_outcomes": [],
                    }
                },
                ensure_ascii=False,
            ),
        )
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: _minimal_publication_run_payload())

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_pub/quality",
            params={"dataset_id": "ds_quality", "require_exports": "false", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload.get("status") == "fail"
        assert payload.get("publication_mode") is True
        missing = payload.get("missing") or []
        assert "reproducibility" in missing
        checks = payload.get("checks") or {}
        assert (checks.get("reproducibility") or {}).get("required") is True
        assert (checks.get("reproducibility") or {}).get("ok") is False


def test_report_quality_endpoint_expert_mode_requires_reproducibility(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_expert")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(
            os.path.join(dataset_dir, "processed", "study_design.json"),
            json.dumps(
                {
                    "design": {
                        "design_type": "cohort",
                        "group_column": "group",
                        "outcomes": ["outcome"],
                        "categorical_outcomes": [],
                    }
                },
                ensure_ascii=False,
            ),
        )
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        run_payload = _minimal_publication_run_payload()
        run_payload["analysis_mode"] = "expert_comprehensive"
        run_payload["publication_mode"] = False

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_payload)

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_expert/quality",
            params={"dataset_id": "ds_quality", "require_exports": "false", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        checks = payload.get("checks") or {}
        assert payload.get("status") == "fail"
        assert "reproducibility" in (payload.get("missing") or [])
        assert (checks.get("reproducibility") or {}).get("required") is True
        assert (checks.get("reproducibility") or {}).get("ok") is False


def test_report_quality_endpoint_publication_passes_with_all_gates(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_pub_ok")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(
            os.path.join(dataset_dir, "processed", "study_design.json"),
            json.dumps(
                {
                    "design": {
                        "design_type": "cohort",
                        "group_column": "group",
                        "outcomes": ["outcome"],
                        "categorical_outcomes": ["event"],
                    }
                },
                ensure_ascii=False,
            ),
        )
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
            "group_distribution.png",
            "correlation_heatmap.png",
            "roc_curve.png",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        run_payload = {
            "dataset_id": "ds_quality",
            "publication_mode": True,
            "analysis_mode": "publication",
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method_id": "t_test_ind",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.01,
                    "conclusion": "Difference between groups is significant.",
                    "interpretation_contract": _full_contract("s1"),
                },
                "s2": {
                    "type": "regression",
                    "method_id": "logistic_regression",
                    "method": {"id": "logistic_regression", "name": "Logistic Regression"},
                    "p_value": 0.03,
                    "conclusion": "Outcome is associated with predictors.",
                    "interpretation_contract": _full_contract("s2"),
                },
                "s3": {
                    "type": "correlation",
                    "method_id": "clustered_correlation",
                    "method": {"id": "clustered_correlation", "name": "Clustered Correlation"},
                    "p_value": 0.02,
                    "conclusion": "Correlation structure is stable.",
                    "interpretation_contract": _full_contract("s3"),
                },
            },
            "step_meta": {
                "s1": {"method": "t_test_ind", "config": {"outcome": "outcome", "group": "group"}},
                "s2": {
                    "method": "logistic_regression",
                    "config": {"outcome": "event", "predictors": ["outcome"], "group": "group"},
                },
                "s3": {
                    "method": "clustered_correlation",
                    "config": {"variables": ["outcome"], "group": "group"},
                },
            },
            "design_review": {"confirmed": True},
            "analysis_set": {"artifact_exists": True, "strict": True},
            "cleaning_artifact": {"valid": True},
        }

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_payload)

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_pub_ok/quality",
            params={"dataset_id": "ds_quality", "require_exports": "false", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()

        assert payload.get("status") == "pass"
        assert payload.get("publication_mode") is True
        checks = payload.get("checks") or {}
        assert (checks.get("reproducibility") or {}).get("ok") is True
        assert (checks.get("coverage") or {}).get("ok") is True
        assert (checks.get("interpretation_completeness") or {}).get("ok") is True
        assert (checks.get("figure_completeness") or {}).get("ok") is True


def test_report_quality_endpoint_publication_requires_interpretation_contract(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_pub_no_contract")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(
            os.path.join(dataset_dir, "processed", "study_design.json"),
            json.dumps(
                {
                    "design": {
                        "design_type": "cohort",
                        "group_column": "group",
                        "outcomes": ["outcome"],
                        "categorical_outcomes": [],
                    }
                },
                ensure_ascii=False,
            ),
        )
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
            "group_distribution.png",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        run_payload = {
            "dataset_id": "ds_quality",
            "publication_mode": True,
            "analysis_mode": "publication",
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method_id": "t_test_ind",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.01,
                    "conclusion": "Difference between groups is significant.",
                }
            },
            "step_meta": {"s1": {"method": "t_test_ind", "config": {"outcome": "outcome", "group": "group"}}},
            "design_review": {"confirmed": True},
            "analysis_set": {"artifact_exists": True, "strict": True},
            "cleaning_artifact": {"valid": True},
        }

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_payload)

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_pub_no_contract/quality",
            params={"dataset_id": "ds_quality", "require_exports": "false", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        checks = payload.get("checks") or {}
        assert payload.get("status") == "fail"
        assert "interpretation_completeness" in (payload.get("missing") or [])
        assert (checks.get("interpretation_completeness") or {}).get("ok") is False


def test_report_quality_endpoint_publication_figures_detected_from_payload(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_dir = os.path.join(tmpdir, "dataset")
        run_dir = os.path.join(dataset_dir, "analysis", "run_pub_payload_fig")
        artifacts_dir = os.path.join(run_dir, "artifacts")

        _write(
            os.path.join(dataset_dir, "processed", "study_design.json"),
            json.dumps(
                {
                    "design": {
                        "design_type": "cohort",
                        "group_column": "group",
                        "outcomes": ["outcome"],
                        "categorical_outcomes": ["event"],
                    }
                },
                ensure_ascii=False,
            ),
        )
        os.makedirs(artifacts_dir, exist_ok=True)
        for name in [
            "analysis_dataset.parquet",
            "analysis_dataset.xlsx",
            "analysis_dataset.meta.json",
        ]:
            with open(os.path.join(artifacts_dir, name), "wb") as f:
                f.write(b"ok")

        run_payload = {
            "dataset_id": "ds_quality",
            "publication_mode": True,
            "analysis_mode": "publication",
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method_id": "t_test_ind",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.01,
                    "conclusion": "Difference between groups is significant.",
                    "interpretation_contract": _full_contract("s1"),
                    "plot_stats": {
                        "A": {"count": 20, "mean": 10.0, "sd": 1.0},
                        "B": {"count": 20, "mean": 11.0, "sd": 1.1},
                    },
                    "plot_data": [{"group": "A", "value": 10.0}, {"group": "B", "value": 11.0}],
                },
                "s2": {
                    "type": "regression",
                    "method_id": "logistic_regression",
                    "method": {"id": "logistic_regression", "name": "Logistic Regression"},
                    "p_value": 0.03,
                    "conclusion": "Outcome is associated with predictors.",
                    "interpretation_contract": _full_contract("s2"),
                    "roc": {"auc": 0.81, "plot_data": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}]},
                },
                "s3": {
                    "type": "correlation",
                    "method_id": "clustered_correlation",
                    "method": {"id": "clustered_correlation", "name": "Clustered Correlation"},
                    "p_value": 0.02,
                    "conclusion": "Correlation structure is stable.",
                    "interpretation_contract": _full_contract("s3"),
                    "correlation_matrix": {"outcome": {"outcome": 1.0}},
                },
            },
            "step_meta": {
                "s1": {"method": "t_test_ind", "config": {"outcome": "outcome", "group": "group"}},
                "s2": {"method": "logistic_regression", "config": {"outcome": "event", "predictors": ["outcome"]}},
                "s3": {"method": "clustered_correlation", "config": {"variables": ["outcome"]}},
            },
            "design_review": {"confirmed": True},
            "analysis_set": {"artifact_exists": True, "strict": True},
            "cleaning_artifact": {"valid": True},
        }

        monkeypatch.setattr(analysis.settings, "GLM_ENABLED", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: dataset_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_dir", lambda _dataset_id, _run_id: run_dir)
        monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: run_payload)

        resp = client.get(
            "/api/v1/analysis/protocol/report/run_pub_payload_fig/quality",
            params={"dataset_id": "ds_quality", "require_exports": "false", "style": "apa7"},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        checks = payload.get("checks") or {}
        assert (checks.get("figure_completeness") or {}).get("ok") is True
        assert payload.get("status") == "pass"
