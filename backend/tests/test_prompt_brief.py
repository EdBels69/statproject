from app.modules.ai_context import generate_prompt_brief, safe_plan_constraints


def test_generate_prompt_brief_includes_design():
    dataset_meta = {
        "summary": {"n_rows": 100, "n_cols": 10},
        "study_design": {
            "design": {
                "design_type": "repeated_measures_wide",
                "group_column": "group",
                "time_column": None,
                "subject_column": None,
                "outcomes": ["bp_v1", "bp_v2"],
                "categorical_outcomes": ["sex"],
                "endpoint_groups": [
                    {"endpoint": "bp", "timepoints": ["V1", "V2"]}
                ],
            },
            "analysis_policy": {"alpha": 0.05, "multiplicity_correction": "fdr_bh", "post_hoc": "tukey"},
        },
    }

    prompt = generate_prompt_brief(dataset_meta, {"analysis_mode": "exploratory"})
    assert "group" in prompt
    assert "repeated_measures_wide" in prompt
    assert "bp_v1" in prompt


def test_safe_plan_constraints_increase_limits_for_publication_mode():
    focused = safe_plan_constraints({"analysis_mode": "focused"})
    discovery = safe_plan_constraints({"analysis_mode": "discovery"})
    publication = safe_plan_constraints({"analysis_mode": "publication"})
    expert = safe_plan_constraints({"analysis_mode": "expert_comprehensive"})

    assert int(discovery.get("max_steps") or 0) >= int(focused.get("max_steps") or 0)
    assert int(discovery.get("max_variables_per_step") or 0) >= int(focused.get("max_variables_per_step") or 0)
    assert int(discovery.get("max_predictors") or 0) >= int(focused.get("max_predictors") or 0)
    assert int(publication.get("max_steps") or 0) >= int(focused.get("max_steps") or 0)
    assert int(publication.get("max_variables_per_step") or 0) >= int(focused.get("max_variables_per_step") or 0)
    assert int(publication.get("max_predictors") or 0) >= int(focused.get("max_predictors") or 0)
    assert int(expert.get("max_steps") or 0) >= int(publication.get("max_steps") or 0)
    assert int(expert.get("max_variables_per_step") or 0) >= int(publication.get("max_variables_per_step") or 0)
    assert int(expert.get("max_predictors") or 0) >= int(publication.get("max_predictors") or 0)
