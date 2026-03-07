from app.modules.hypothesis_discovery import build_hypothesis_discovery


def test_hypothesis_discovery_from_design_context():
    dataset_meta = {
        "summary": {"n_rows": 120, "n_cols": 8},
        "numeric_cols": ["crp", "wbc", "glucose"],
        "categorical_cols": ["group", "sex", "responder"],
        "study_design": {
            "design": {
                "design_type": "parallel_groups",
                "group_column": "group",
                "time_column": "visit",
                "subject_column": "patient_id",
                "outcomes": ["crp", "wbc"],
                "categorical_outcomes": ["responder"],
            }
        },
    }

    doc = build_hypothesis_discovery(
        dataset_meta=dataset_meta,
        preferences={"analysis_mode": "exploratory", "subgroup_columns": "sex"},
    )

    assert doc.get("schema") == "clinimetria.hypothesis_discovery"
    assert doc.get("analysis_mode") == "exploratory"
    assert int(doc.get("count") or 0) >= 4
    items = doc.get("items") if isinstance(doc.get("items"), list) else []
    assert any(isinstance(item, dict) and item.get("suggested_method") == "mixed_effects" for item in items)
    assert any(
        isinstance(item, dict)
        and "kmeans" in str(item.get("suggested_method") or "")
        for item in items
    )


def test_hypothesis_discovery_adds_protocol_anchors():
    dataset_meta = {
        "summary": {"n_rows": 64, "n_cols": 4},
        "numeric_cols": ["outcome"],
        "categorical_cols": ["group"],
        "study_design": {
            "design": {
                "design_type": "parallel_groups",
                "group_column": "group",
                "outcomes": ["outcome"],
            }
        },
    }

    protocol = [
        {
            "id": "s1",
            "method": "t_test_ind",
            "config": {"outcome": "outcome", "group": "group"},
        }
    ]

    doc = build_hypothesis_discovery(
        dataset_meta=dataset_meta,
        preferences={"analysis_mode": "focused", "hypotheses_max": 10},
        protocol=protocol,
    )

    items = doc.get("items") if isinstance(doc.get("items"), list) else []
    assert any(
        isinstance(item, dict)
        and str(item.get("id") or "").startswith("h_protocol_")
        and item.get("suggested_method") == "t_test_ind"
        for item in items
    )
