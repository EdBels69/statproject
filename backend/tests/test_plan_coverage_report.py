import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api import v2


def test_build_protocol_coverage_report_from_study_design_targets():
    protocol = [
        {"id": "step_1", "method": "descriptive_compare", "config": {"target": "glucose", "group": "group"}},
        {"id": "step_2", "method": "batch_analysis", "config": {"targets": ["hba1c"], "group": "group"}},
    ]
    study_design = {
        "design": {
            "outcomes": ["glucose", "hba1c", "crp"],
            "categorical_outcomes": ["death"],
        }
    }

    report = v2._build_protocol_coverage_report(protocol=protocol, study_design=study_design)
    assert isinstance(report, dict)
    assert report.get("target_total") == 4
    assert report.get("covered_total") == 2
    assert report.get("status") == "partial"
    assert "crp" in (report.get("missing_outcomes") or [])
    assert "death" in (report.get("missing_outcomes") or [])

