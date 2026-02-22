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


def test_build_study_design_treats_object_as_categorical_outcomes():
    scan_report = {
        "columns": {
            "patient_id": {"type": "object", "unique_count": 4, "missing_count": 0},
            "comorbidity": {"type": "object", "unique_count": 3, "missing_count": 0},
            "therapy_arm": {"type": "object", "unique_count": 2, "missing_count": 0},
            "crp": {"type": "float64", "unique_count": 4, "missing_count": 0},
        },
        "missing_report": {"total_rows": 4},
    }

    design = build_study_design(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        variable_mapping={},
        source="test",
    )

    core = design.get("design", {})
    assert "comorbidity" in core.get("categorical_outcomes", [])
    assert "patient_id" not in core.get("categorical_outcomes", [])


def test_build_study_design_respects_manual_outcome_mapping():
    scan_report = {
        "columns": {
            "group": {"type": "object", "unique_count": 2, "missing_count": 0},
            "age": {"type": "float64", "unique_count": 90, "missing_count": 0},
            "glucose": {"type": "float64", "unique_count": 88, "missing_count": 0},
            "death": {"type": "object", "unique_count": 2, "missing_count": 0},
            "icu": {"type": "object", "unique_count": 2, "missing_count": 0},
        },
        "missing_report": {"total_rows": 100},
    }

    mapping = {
        "group": {"role": "group"},
        "glucose": {"role": "outcome"},
        "death": {"role": "categorical_outcome"},
        "icu": {"role": "ignore"},
    }

    design = build_study_design(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        variable_mapping=mapping,
        source="test",
    )

    core = design.get("design", {})
    assert core.get("group_column") == "group"
    assert core.get("outcomes") == ["glucose"]
    assert core.get("categorical_outcomes") == ["death"]
