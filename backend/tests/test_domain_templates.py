"""Tests for domain_templates.py — 5 pre-built protocol templates."""
import pytest
from app.modules.domain_templates import (
    list_templates,
    get_template,
    build_protocol,
)


class TestTemplateRegistry:
    def test_list_templates_returns_five(self):
        templates = list_templates()
        assert len(templates) == 5
        ids = {t["id"] for t in templates}
        assert ids == {"rct_two_arm", "before_after", "cross_sectional", "longitudinal", "responder_analysis"}

    def test_list_templates_has_required_fields(self):
        for t in list_templates():
            assert "id" in t
            assert "title" in t
            assert "description" in t
            assert len(t["title"]) > 0
            assert len(t["description"]) > 0

    def test_get_template_unknown_returns_none(self):
        assert get_template("nonexistent") is None

    def test_get_template_has_builder(self):
        meta = get_template("rct_two_arm")
        assert meta is not None
        assert callable(meta["builder"])


class TestRCTTemplate:
    def test_basic_build(self):
        proto = build_protocol("rct_two_arm", variables={
            "outcome": "SBP",
            "group": "Treatment",
        })
        assert proto["name"] == "RCT Two-Arm Protocol"
        assert proto["alpha"] == 0.05
        assert len(proto["steps"]) >= 2
        step_ids = [s["id"] for s in proto["steps"]]
        assert "table_1" in step_ids
        assert "primary_endpoint" in step_ids

    def test_with_secondary_and_safety(self):
        proto = build_protocol("rct_two_arm", variables={
            "outcome": "SBP",
            "group": "Treatment",
            "secondary_outcomes": ["DBP", "HR"],
            "safety_variables": ["AE_count"],
        })
        step_ids = [s["id"] for s in proto["steps"]]
        assert "secondary_1" in step_ids
        assert "secondary_2" in step_ids
        assert "safety_1" in step_ids

    def test_why_selected_present(self):
        proto = build_protocol("rct_two_arm", variables={"outcome": "X", "group": "G"})
        for step in proto["steps"]:
            assert "why_selected" in step
            assert len(step["why_selected"]) > 10


class TestBeforeAfterTemplate:
    def test_basic_build(self):
        proto = build_protocol("before_after", variables={
            "before": "Score_V1",
            "after": "Score_V2",
        })
        assert len(proto["steps"]) >= 1
        assert proto["steps"][0]["is_paired"] is True

    def test_with_responder(self):
        proto = build_protocol("before_after", variables={
            "before": "Score_V1",
            "after": "Score_V2",
            "group": "Arm",
            "subject": "PatientID",
            "response_threshold": 5.0,
        })
        step_ids = [s["id"] for s in proto["steps"]]
        assert "responder" in step_ids


class TestCrossSectionalTemplate:
    def test_with_predictors(self):
        proto = build_protocol("cross_sectional", variables={
            "outcome": "BMI",
            "predictors": ["Age", "Sex", "Smoking"],
        })
        step_ids = [s["id"] for s in proto["steps"]]
        assert "correlation_1" in step_ids
        assert "regression" in step_ids

    def test_without_group(self):
        proto = build_protocol("cross_sectional", variables={
            "outcome": "BMI",
            "predictors": ["Age"],
        })
        assert not any(s["id"] == "descriptives" for s in proto["steps"])


class TestLongitudinalTemplate:
    def test_basic_build(self):
        proto = build_protocol("longitudinal", variables={
            "outcome": "Score",
            "outcome_columns": ["V1", "V2", "V3"],
            "group": "Treatment",
            "subject": "PatientID",
        })
        step_ids = [s["id"] for s in proto["steps"]]
        assert "mixed_effects" in step_ids
        assert "final_comparison" in step_ids


class TestResponderTemplate:
    def test_basic_build(self):
        proto = build_protocol("responder_analysis", variables={
            "outcome_columns": ["V1", "V2"],
            "group": "Arm",
            "subject": "PID",
            "response_threshold": 10,
        })
        step_ids = [s["id"] for s in proto["steps"]]
        assert "responder_rates" in step_ids

    def test_unknown_template_raises(self):
        with pytest.raises(KeyError, match="nonexistent"):
            build_protocol("nonexistent", variables={})
