import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.protocol_quality import evaluate_protocol_quality


def _sample_scan_report():
    return {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "outcome1": {"type": "float64", "unique_count": 80, "normality": {"p_value": 0.2}},
            "outcome2": {"type": "float64", "unique_count": 75, "normality": {"p_value": 0.01}},
            "sex": {"type": "category", "unique_count": 2},
            "time": {"type": "int64", "unique_count": 4},
        },
        "missing_report": {"total_rows": 100},
    }


def _sample_study_design(repeated: bool = False):
    return {
        "design": {
            "outcomes": ["outcome1", "outcome2"],
            "categorical_outcomes": ["sex"],
            "repeated_measures": repeated,
        }
    }


def test_quality_high_for_valid_protocol():
    scan_report = _sample_scan_report()
    study_design = _sample_study_design(repeated=False)
    protocol = [
        {
            "id": "step_1",
            "method": "descriptive_compare",
            "config": {"target": "outcome1", "group": "group"},
        },
        {
            "id": "step_2",
            "method": "batch_analysis",
            "config": {"group": "group", "targets": ["outcome1", "outcome2"], "method_id": "t_test_ind"},
        },
    ]
    quality = evaluate_protocol_quality(protocol, study_design=study_design, scan_report=scan_report)
    assert quality["score"] > 60
    assert not quality["invalid_steps"]


def test_quality_flags_missing_columns():
    scan_report = _sample_scan_report()
    study_design = _sample_study_design(repeated=False)
    protocol = [
        {
            "id": "step_1",
            "method": "descriptive_compare",
            "config": {"target": "missing_col", "group": "group"},
        }
    ]
    quality = evaluate_protocol_quality(protocol, study_design=study_design, scan_report=scan_report)
    assert quality["score"] < 60
    assert quality["invalid_steps"]
    assert "invalid_steps" in quality["issues"]


def test_quality_repeated_measures_mismatch():
    scan_report = _sample_scan_report()
    study_design = _sample_study_design(repeated=True)
    protocol = [
        {
            "id": "step_1",
            "method": "descriptive_compare",
            "config": {"target": "outcome1", "group": "group"},
        }
    ]
    quality = evaluate_protocol_quality(protocol, study_design=study_design, scan_report=scan_report)
    assert quality["design_fit"] < 0.8
