import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.protocol_rules import build_exploratory_plan


def test_exploratory_plan_adds_paired_and_delta():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "bp_v1": {"type": "float64", "unique_count": 20, "normality": {"p_value": 0.2}},
            "bp_v2": {"type": "float64", "unique_count": 20, "normality": {"p_value": 0.2}},
        },
        "missing_report": {"total_rows": 20},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "time_column": None,
            "subject_column": None,
            "endpoint_groups": [
                {"endpoint": "bp", "columns": ["bp_v1", "bp_v2"], "timepoints": ["V1", "V2"]}
            ],
            "outcomes": ["bp_v1", "bp_v2"],
            "categorical_outcomes": [],
            "predictors": ["bp_v1", "bp_v2"],
            "id_like_columns": [],
        },
        "analysis_policy": {"max_protocol_steps": 40},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "exploratory"},
    )

    methods = [step.get("method") for step in plan.get("protocol", [])]
    assert "paired_wide" in methods
    assert "delta_batch_analysis" in methods


def test_exploratory_plan_one_vs_rest_logistic():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "age": {"type": "float64", "unique_count": 30, "normality": {"p_value": 0.3}},
            "outcome_status": {
                "type": "category",
                "unique_count": 3,
                "categories": ["recovered", "ongoing", "death"],
                "top_values": [
                    {"value": "recovered", "count": 10},
                    {"value": "ongoing", "count": 10},
                    {"value": "death", "count": 10},
                ],
            },
        },
        "missing_report": {"total_rows": 30},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["age"],
            "categorical_outcomes": ["outcome_status"],
            "predictors": ["age", "outcome_status"],
            "id_like_columns": [],
        },
        "analysis_policy": {"max_protocol_steps": 40},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "exploratory"},
    )

    logistic_steps = [
        step for step in plan.get("protocol", []) if step.get("method") == "logistic_regression"
    ]
    assert logistic_steps, "Expected logistic_regression step"
    cfg = logistic_steps[0].get("config", {})
    assert cfg.get("one_vs_rest") is True
    assert cfg.get("positive_label") == "death"


def test_plan_respects_primary_outcome_and_group_preferences():
    scan_report = {
        "columns": {
            "arm": {"type": "category", "unique_count": 2},
            "group": {"type": "category", "unique_count": 3},
            "primary_outcome": {"type": "float64", "unique_count": 50, "normality": {"p_value": 0.2}},
            "secondary": {"type": "float64", "unique_count": 50, "normality": {"p_value": 0.2}},
        },
        "missing_report": {"total_rows": 50},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["primary_outcome", "secondary"],
            "categorical_outcomes": ["arm", "group"],
            "predictors": ["primary_outcome", "secondary", "arm", "group"],
            "id_like_columns": [],
        },
        "analysis_policy": {"max_protocol_steps": 40},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "focused", "primary_outcome": "primary_outcome", "group_column": "arm"},
    )

    steps = plan.get("protocol") or []
    desc_steps = [s for s in steps if s.get("method") == "descriptive_compare"]
    assert desc_steps
    assert desc_steps[0].get("config", {}).get("target") == "primary_outcome"

    batch_steps = [s for s in steps if s.get("method") == "batch_analysis"]
    assert any(s.get("config", {}).get("group") == "arm" for s in batch_steps)


def test_subgroup_interaction_anova_twoway():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "sex": {"type": "category", "unique_count": 2},
            "outcome1": {"type": "float64", "unique_count": 40, "normality": {"p_value": 0.2}},
        },
        "missing_report": {"total_rows": 40},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["outcome1"],
            "categorical_outcomes": ["sex"],
            "predictors": ["outcome1", "sex", "group"],
            "id_like_columns": [],
        },
        "analysis_policy": {"max_protocol_steps": 40},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "exploratory", "subgroup_columns": ["sex"]},
    )

    twoway = [s for s in plan.get("protocol") or [] if s.get("method") == "anova_twoway"]
    assert twoway
    cfg = twoway[0].get("config", {})
    assert cfg.get("group1") == "group"
    assert cfg.get("group2") == "sex"


def test_exploratory_plan_multiple_descriptive_steps():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "age": {"type": "float64", "unique_count": 30, "normality": {"p_value": 0.2}},
            "crp": {"type": "float64", "unique_count": 30, "normality": {"p_value": 0.01}},
            "wbc": {"type": "float64", "unique_count": 30, "normality": {"p_value": 0.2}},
        },
        "missing_report": {"total_rows": 30},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["age", "crp", "wbc"],
            "categorical_outcomes": [],
            "predictors": ["age", "crp", "wbc"],
            "id_like_columns": [],
        },
        "analysis_policy": {"max_protocol_steps": 40, "max_descriptive_targets": 3},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "exploratory"},
    )

    desc_steps = [s for s in plan.get("protocol", []) if s.get("method") == "descriptive_compare"]
    assert len(desc_steps) >= 2


def test_exploratory_plan_returns_coverage_report():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "outcome_1": {"type": "float64", "unique_count": 40},
            "outcome_2": {"type": "float64", "unique_count": 40},
            "outcome_3": {"type": "float64", "unique_count": 40},
            "outcome_4": {"type": "float64", "unique_count": 40},
            "event": {"type": "category", "unique_count": 2},
        },
        "missing_report": {"total_rows": 40},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["outcome_1", "outcome_2", "outcome_3", "outcome_4"],
            "categorical_outcomes": ["event"],
            "predictors": ["outcome_1", "outcome_2", "outcome_3", "outcome_4", "event"],
            "id_like_columns": [],
        },
        "analysis_policy": {"max_protocol_steps": 40, "max_batch_targets": 2},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "focused"},
        constraints={"max_steps": 6, "max_variables_per_step": 4, "max_predictors": 3},
    )

    coverage = plan.get("coverage_report")
    assert isinstance(coverage, dict)
    assert int(coverage.get("target_total") or 0) >= 5
    assert int(coverage.get("covered_total") or 0) >= 1
    assert 0.0 <= float(coverage.get("coverage_ratio") or 0.0) <= 1.0
    assert coverage.get("status") in {"ok", "partial"}


def test_publication_mode_expands_budget_and_coverage():
    columns = {
        "group": {"type": "category", "unique_count": 2},
        "event": {"type": "category", "unique_count": 2},
    }
    outcomes = []
    for idx in range(1, 97):
        name = f"outcome_{idx:03d}"
        columns[name] = {"type": "float64", "unique_count": 120}
        outcomes.append(name)

    scan_report = {"columns": columns, "missing_report": {"total_rows": 120}}
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": outcomes,
            "categorical_outcomes": ["event"],
            "predictors": outcomes[:20] + ["event", "group"],
            "id_like_columns": [],
        },
        "analysis_policy": {},
    }

    focused = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "focused"},
    )
    publication = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "publication"},
    )

    focused_cov = focused.get("coverage_report") or {}
    publication_cov = publication.get("coverage_report") or {}
    assert int(publication_cov.get("max_steps") or 0) > int(focused_cov.get("max_steps") or 0)
    assert float(publication_cov.get("coverage_ratio") or 0.0) >= float(focused_cov.get("coverage_ratio") or 0.0)


def test_publication_mode_adds_comorbidity_and_treatment_branches():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "comorbidity_diabetes": {"type": "category", "unique_count": 2},
            "treatment_steroids": {"type": "category", "unique_count": 2},
            "outcome1": {"type": "float64", "unique_count": 80},
            "outcome2": {"type": "float64", "unique_count": 80},
        },
        "missing_report": {"total_rows": 80},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["outcome1", "outcome2"],
            "categorical_outcomes": [],
            "predictors": ["outcome1", "outcome2", "comorbidity_diabetes", "treatment_steroids"],
            "id_like_columns": [],
        },
        "analysis_policy": {},
    }

    plan = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "publication"},
    )

    subgroup_steps = [
        s for s in (plan.get("protocol") or []) if s.get("method") == "batch_analysis" and str(s.get("name") or "").startswith("Подгруппы:")
    ]
    subgroup_groups = {str(s.get("config", {}).get("group")) for s in subgroup_steps}
    assert "comorbidity_diabetes" in subgroup_groups
    assert "treatment_steroids" in subgroup_groups

    branches = ((plan.get("coverage_report") or {}).get("clinical_branches") or {})
    assert branches.get("comorbidity") is True
    assert branches.get("treatment") is True


def test_expert_mode_adds_ml_benchmark_and_expands_budget():
    columns = {
        "group": {"type": "category", "unique_count": 2},
        "event": {"type": "category", "unique_count": 2},
        "age": {"type": "float64", "unique_count": 120},
        "crp": {"type": "float64", "unique_count": 120},
        "wbc": {"type": "float64", "unique_count": 120},
    }
    outcomes = ["age", "crp", "wbc"]
    scan_report = {"columns": columns, "missing_report": {"total_rows": 120}}
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": outcomes,
            "categorical_outcomes": ["event"],
            "predictors": ["age", "crp", "wbc", "event", "group"],
            "id_like_columns": [],
        },
        "analysis_policy": {},
    }

    publication = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "publication"},
    )
    expert = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={"analysis_mode": "expert_comprehensive"},
    )

    pub_cov = publication.get("coverage_report") or {}
    exp_cov = expert.get("coverage_report") or {}
    assert int(exp_cov.get("max_steps") or 0) >= int(pub_cov.get("max_steps") or 0)

    methods = [str(step.get("method") or "") for step in (expert.get("protocol") or [])]
    assert "random_forest" in methods
    assert "gradient_boosting" in methods


def test_expert_mode_adds_p2_bootstrap_cluster_and_external_validation():
    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2},
            "event": {"type": "category", "unique_count": 2},
            "age": {"type": "float64", "unique_count": 120},
            "crp": {"type": "float64", "unique_count": 120},
            "wbc": {"type": "float64", "unique_count": 120},
            "ferritin": {"type": "float64", "unique_count": 120},
        },
        "missing_report": {"total_rows": 120},
    }
    study_design = {
        "design": {
            "group_column": "group",
            "endpoint_groups": [],
            "outcomes": ["age", "crp", "wbc", "ferritin"],
            "categorical_outcomes": ["event"],
            "predictors": ["age", "crp", "wbc", "ferritin", "event", "group"],
            "id_like_columns": [],
        },
        "analysis_policy": {},
    }

    expert = build_exploratory_plan(
        dataset_id="demo",
        base_dir=".",
        scan_report=scan_report,
        semantics={},
        study_design=study_design,
        preferences={
            "analysis_mode": "expert_comprehensive",
            "external_validation_dataset_id": "external_demo_ds",
        },
    )

    methods = [str(step.get("method") or "") for step in (expert.get("protocol") or [])]
    assert "bootstrap_pipeline" in methods
    assert "cluster_profiles" in methods
    assert "external_validation" in methods
