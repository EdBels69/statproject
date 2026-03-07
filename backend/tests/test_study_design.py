import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.study_design import build_study_design


def test_build_study_design_handles_subject_role_without_unique_ratio():
    scan_report = {
        "columns": {
            "patient_id": {"type": "object", "unique_count": 100, "missing_count": 0},
            "group": {"type": "object", "unique_count": 2, "missing_count": 0},
            "outcome": {"type": "float64", "unique_count": 95, "missing_count": 2},
        },
        "missing_report": {"total_rows": 0},
    }

    design = build_study_design(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        variable_mapping={},
        source="test",
    )

    assert isinstance(design, dict)
    assert design.get("design", {}).get("subject_column") == "patient_id"

