import os
import sys
import tempfile

from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api import analysis


def test_report_design_gate_blocks_when_study_design_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_id = "ds_missing_design"
        ds_dir = os.path.join(tmpdir, dataset_id)
        os.makedirs(os.path.join(ds_dir, "processed"), exist_ok=True)

        monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_DESIGN", True)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: ds_dir)

        try:
            analysis._enforce_report_design_gate(dataset_id)
            assert False, "Expected HTTPException when study_design.json is missing"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "study_design.json" in str(exc.detail)


def test_report_design_gate_passes_when_study_design_present(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_id = "ds_with_design"
        ds_dir = os.path.join(tmpdir, dataset_id)
        processed_dir = os.path.join(ds_dir, "processed")
        os.makedirs(processed_dir, exist_ok=True)
        with open(os.path.join(processed_dir, "study_design.json"), "w", encoding="utf-8") as f:
            f.write('{"design":{"design_type":"cohort","roles":{"group":"group"}}}')

        monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_DESIGN", True)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: ds_dir)

        analysis._enforce_report_design_gate(dataset_id)


def test_report_design_gate_disabled_allows_export(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        dataset_id = "ds_no_gate"
        ds_dir = os.path.join(tmpdir, dataset_id)
        os.makedirs(ds_dir, exist_ok=True)

        monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_DESIGN", False)
        monkeypatch.setattr(analysis.pipeline, "get_dataset_dir", lambda _dataset_id: ds_dir)

        analysis._enforce_report_design_gate(dataset_id)


def test_report_methods_gate_blocks_when_methods_missing(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_METHODS", True)
    monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: {"results": {}})

    try:
        analysis._enforce_report_methods_gate("ds_methods_missing", "run_1")
        assert False, "Expected HTTPException when Methods section is incomplete"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "Methods" in str(exc.detail)


def test_report_methods_gate_passes_when_method_metadata_present(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_METHODS", True)
    monkeypatch.setattr(
        analysis.pipeline,
        "get_run_results",
        lambda _dataset_id, _run_id: {
            "results": {
                "step_1": {
                    "type": "hypothesis_test",
                    "method_id": "t_test_ind",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.01,
                    "stat_value": 2.4,
                }
            }
        },
    )

    analysis._enforce_report_methods_gate("ds_methods_ok", "run_1")


def test_report_methods_gate_allows_descriptive_step_without_method(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_METHODS", True)
    monkeypatch.setattr(
        analysis.pipeline,
        "get_run_results",
        lambda _dataset_id, _run_id: {
            "results": {
                "desc_stats": {
                    "type": "table_1",
                    "data": {"A": {"count": 10, "mean": 1.2}},
                }
            }
        },
    )

    analysis._enforce_report_methods_gate("ds_methods_desc_ok", "run_1")


def test_report_methods_gate_disabled_allows_incomplete_methods(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_METHODS", False)
    monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: {"results": {}})

    analysis._enforce_report_methods_gate("ds_methods_off", "run_1")


def test_report_verification_gate_blocks_when_verification_failed(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_VERIFICATION", True)
    monkeypatch.setattr(
        analysis.pipeline,
        "get_run_results",
        lambda _dataset_id, _run_id: {
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method_id": "t_test_ind",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.01,
                }
            },
            "verification": {
                "status": "failed",
                "failures": [{"step_id": "s1", "check": "p_value_bounds", "message": "bad p"}],
            },
        },
    )

    try:
        analysis._enforce_report_verification_gate("ds_verif", "run_1")
        assert False, "Expected HTTPException when verification failed"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "верификация" in str(exc.detail).lower()


def test_report_verification_gate_disabled_allows_missing(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_VERIFICATION", False)
    monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: {"results": {}})

    analysis._enforce_report_verification_gate("ds_verif_off", "run_1")


def test_report_provenance_gate_blocks_when_reproducibility_incomplete(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_PROVENANCE", True)
    monkeypatch.setattr(
        analysis.pipeline,
        "get_run_results",
        lambda _dataset_id, _run_id: {
            "results": {
                "s1": {
                    "type": "hypothesis_test",
                    "method_id": "t_test_ind",
                    "method": {"id": "t_test_ind", "name": "Independent t-test"},
                    "p_value": 0.01,
                }
            },
            "reproducibility": {"ready": False},
        },
    )
    monkeypatch.setattr(
        analysis.pipeline,
        "get_run_state",
        lambda _dataset_id, _run_id: {
            "state": "compile",
            "missing_artifacts": ["verification", "report_html"],
            "artifacts": {"protocol": "protocol.json"},
        },
    )

    try:
        analysis._enforce_report_provenance_gate("ds_prov", "run_1")
        assert False, "Expected HTTPException when provenance is incomplete"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "provenance" in str(exc.detail).lower()


def test_report_provenance_gate_disabled_allows_incomplete(monkeypatch):
    monkeypatch.setattr(analysis.settings, "CLINIMETRIA_REPORT_HARD_GATE_PROVENANCE", False)
    monkeypatch.setattr(analysis.pipeline, "get_run_results", lambda _dataset_id, _run_id: {"results": {}})

    analysis._enforce_report_provenance_gate("ds_prov_off", "run_1")
