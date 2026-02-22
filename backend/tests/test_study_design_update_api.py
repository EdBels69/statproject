import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import datasets as ds
from app.core.pipeline import PipelineManager


client = TestClient(app)


def _write_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _prepare_dataset(tmp_path, dataset_id: str) -> str:
    base_dir = str(tmp_path)
    processed_dir = os.path.join(base_dir, dataset_id, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    scan_report = {
        "columns": {
            "patient_id": {"type": "object", "unique_count": 8, "missing_count": 0},
            "group": {"type": "object", "unique_count": 2, "missing_count": 0},
            "visit": {"type": "object", "unique_count": 3, "missing_count": 0},
            "glucose": {"type": "float64", "unique_count": 7, "missing_count": 1},
            "hba1c": {"type": "float64", "unique_count": 8, "missing_count": 0},
            "death": {"type": "object", "unique_count": 2, "missing_count": 0},
        },
        "missing_report": {"total_rows": 8},
    }
    _write_json(os.path.join(processed_dir, "scan_report.json"), scan_report)
    return base_dir


def test_put_study_design_updates_revision_and_revokes_design_review(tmp_path, monkeypatch):
    dataset_id = "study_design_update_ds"
    base_dir = _prepare_dataset(tmp_path, dataset_id)

    monkeypatch.setattr(ds, "DATA_DIR", base_dir)
    monkeypatch.setattr(ds, "pipeline", PipelineManager(base_dir))

    initial_res = client.get(f"/api/v1/datasets/{dataset_id}/study_design")
    assert initial_res.status_code == 200, initial_res.text
    initial_payload = initial_res.json()
    initial_revision = int(initial_payload.get("revision") or 1)

    confirm_res = client.post(
        f"/api/v1/datasets/{dataset_id}/design_review/confirm",
        json={"actor": "qa", "source": "test"},
    )
    assert confirm_res.status_code == 200, confirm_res.text
    assert confirm_res.json().get("confirmed") is True

    update_res = client.put(
        f"/api/v1/datasets/{dataset_id}/study_design",
        json={
            "actor": "qa",
            "source": "test",
            "reason": "manual_refine",
            "expected_revision": initial_revision,
            "design": {
                "design_type": "repeated_measures_long",
                "group_column": "group",
                "time_column": "visit",
                "subject_column": "patient_id",
                "outcomes": ["glucose", "hba1c"],
                "categorical_outcomes": ["death"],
                "predictors": ["group", "glucose", "hba1c"],
            },
            "analysis_policy": {"alpha": 0.01, "max_protocol_steps": 80},
            "notes": ["manual update"],
        },
    )
    assert update_res.status_code == 200, update_res.text
    payload = update_res.json()
    assert int(payload.get("revision") or 0) == initial_revision + 1
    assert payload.get("design_review_revoked") is True
    design = payload.get("design") or {}
    assert design.get("group_column") == "group"
    assert design.get("time_column") == "visit"
    assert design.get("subject_column") == "patient_id"
    assert "glucose" in (design.get("outcomes") or [])
    assert "death" in (design.get("categorical_outcomes") or [])
    assert float((payload.get("analysis_policy") or {}).get("alpha")) == 0.01

    review_res = client.get(f"/api/v1/datasets/{dataset_id}/design_review")
    assert review_res.status_code == 200, review_res.text
    review_payload = review_res.json()
    assert review_payload.get("confirmed") is False
    assert review_payload.get("artifact_exists") is True


def test_put_study_design_returns_409_on_revision_conflict(tmp_path, monkeypatch):
    dataset_id = "study_design_conflict_ds"
    base_dir = _prepare_dataset(tmp_path, dataset_id)

    monkeypatch.setattr(ds, "DATA_DIR", base_dir)
    monkeypatch.setattr(ds, "pipeline", PipelineManager(base_dir))

    get_res = client.get(f"/api/v1/datasets/{dataset_id}/study_design")
    assert get_res.status_code == 200, get_res.text

    conflict_res = client.put(
        f"/api/v1/datasets/{dataset_id}/study_design",
        json={
            "expected_revision": 999,
            "design": {"group_column": "group"},
        },
    )
    assert conflict_res.status_code == 409, conflict_res.text
    assert "Конфликт версии study_design" in conflict_res.text


def test_put_study_design_returns_400_for_unknown_column(tmp_path, monkeypatch):
    dataset_id = "study_design_bad_col_ds"
    base_dir = _prepare_dataset(tmp_path, dataset_id)

    monkeypatch.setattr(ds, "DATA_DIR", base_dir)
    monkeypatch.setattr(ds, "pipeline", PipelineManager(base_dir))

    get_res = client.get(f"/api/v1/datasets/{dataset_id}/study_design")
    assert get_res.status_code == 200, get_res.text
    revision = int(get_res.json().get("revision") or 1)

    bad_res = client.put(
        f"/api/v1/datasets/{dataset_id}/study_design",
        json={
            "expected_revision": revision,
            "design": {"group_column": "missing_col"},
        },
    )
    assert bad_res.status_code == 400, bad_res.text
    assert "group_column" in bad_res.text

