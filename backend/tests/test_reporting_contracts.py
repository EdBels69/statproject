import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting_contracts import (
    build_report_integrity_context,
    filter_step_pairs_for_report,
)


def test_filter_step_pairs_excludes_failed_verification_steps():
    run_data = {
        "verification": {
            "status": "failed",
            "failures": [
                {"check": "p_value_bounds", "step_id": "bad_step", "message": "p_value out of bounds"},
            ],
        }
    }
    context = build_report_integrity_context(run_data)
    steps = [
        ("ok_step", {"type": "hypothesis_test", "p_value": 0.02}),
        ("bad_step", {"type": "hypothesis_test", "p_value": 1.2}),
    ]

    filtered, meta = filter_step_pairs_for_report(steps, context)

    assert [sid for sid, _ in filtered] == ["ok_step"]
    assert meta.get("verification_status") == "failed"
    assert meta.get("verification_present") is True
    assert meta.get("excluded_step_ids") == ["bad_step"]


def test_filter_step_pairs_blocks_all_when_failed_without_step_ids():
    run_data = {
        "verification": {
            "status": "failed",
            "failures": [
                {"check": "internal_error", "message": "verification failed"},
            ],
        }
    }
    context = build_report_integrity_context(run_data)
    steps = [
        ("step_1", {"type": "hypothesis_test", "p_value": 0.02}),
        ("step_2", {"type": "hypothesis_test", "p_value": 0.04}),
    ]

    filtered, meta = filter_step_pairs_for_report(steps, context)

    assert filtered == []
    assert sorted(meta.get("excluded_step_ids") or []) == ["step_1", "step_2"]

