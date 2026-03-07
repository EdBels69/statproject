from app.modules.ai_context import generate_prompt_brief


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
            "analysis_policy": {
                "alpha": 0.05,
                "multiplicity_correction": "fdr_bh",
                "post_hoc": "tukey",
                "bootstrap_ci": True,
                "bootstrap_samples": 1200,
            },
        },
    }

    prompt = generate_prompt_brief(dataset_meta, {"analysis_mode": "exploratory"})
    assert "group" in prompt
    assert "repeated_measures_wide" in prompt
    assert "bp_v1" in prompt
    assert "Поправка множественности: fdr_bh." in prompt
    assert "Bootstrap для CI: включен (samples=1200)." in prompt
