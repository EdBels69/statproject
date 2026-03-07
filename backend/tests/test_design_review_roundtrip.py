import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api import datasets as ds
from app.core.pipeline import PipelineManager
from app.schemas.dataset import VariableMappingUpdate


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def test_design_override_round_trip_rebuilds_study_design(tmp_path, monkeypatch):
    dataset_id = "design_roundtrip_ds"
    base_dir = str(tmp_path)
    ds_dir = os.path.join(base_dir, dataset_id, "processed")
    os.makedirs(ds_dir, exist_ok=True)

    scan_report = {
        "columns": {
            "patient_id": {"type": "object", "unique_count": 6, "missing_count": 0},
            "arm": {"type": "object", "unique_count": 2, "missing_count": 0},
            "visit": {"type": "object", "unique_count": 3, "missing_count": 0},
            "outcome_score": {"type": "float64", "unique_count": 6, "missing_count": 0},
            "sex": {"type": "object", "unique_count": 2, "missing_count": 0},
        },
        "missing_report": {"total_rows": 6},
    }
    _write_json(os.path.join(ds_dir, "scan_report.json"), scan_report)

    monkeypatch.setattr(ds, "DATA_DIR", base_dir)
    monkeypatch.setattr(ds, "pipeline", PipelineManager(base_dir))

    initial_design = ds.get_study_design(dataset_id)
    assert isinstance(initial_design, dict)

    payload = VariableMappingUpdate(
        mapping={
            "arm": {"role": "group"},
            "visit": {"role": "time"},
            "patient_id": {"role": "subject"},
            "outcome_score": {"role": "outcome"},
            "sex": {"subgroup": "user"},
        }
    )
    ds.put_variable_mapping(dataset_id, payload)

    updated_design = ds.get_study_design(dataset_id)
    assert isinstance(updated_design, dict)
    design = updated_design.get("design") if isinstance(updated_design.get("design"), dict) else {}
    assert design.get("group_column") == "arm"
    assert design.get("time_column") == "visit"
    assert design.get("subject_column") == "patient_id"
    assert "outcome_score" in (design.get("outcomes") or [])

    semantics_path = os.path.join(base_dir, dataset_id, "processed", "dataset_semantics.json")
    assert os.path.exists(semantics_path)
