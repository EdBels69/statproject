import json
import os

import pandas as pd

from app.core.pipeline import PipelineManager
from app.modules.analysis_set import freeze_analysis_set


def test_create_processed_snapshot_builds_dataset_artifacts(tmp_path):
    pipeline = PipelineManager(str(tmp_path))
    dataset_id = "pipeline_artifacts_ds"
    df = pd.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "value": [1.0, 2.0, 3.0, None],
        }
    )

    pipeline.create_processed_snapshot(
        dataset_id,
        df,
        cleaning_log={"action": "auto_clean", "strategy": "simple"},
    )

    processed_dir = os.path.join(str(tmp_path), dataset_id, "processed")
    for name in [
        "profile.json",
        "data_contract.json",
        "cleaning_plan.json",
        "data_lineage.json",
        "cleaning_log.json",
    ]:
        assert os.path.exists(os.path.join(processed_dir, name))


def test_create_analysis_run_bootstraps_state_from_dataset_artifacts(tmp_path):
    pipeline = PipelineManager(str(tmp_path))
    dataset_id = "pipeline_state_bootstrap_ds"
    df = pd.DataFrame(
        {
            "group": ["A", "A", "B", "B", "B"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cov": [10.0, 11.0, 12.0, 13.0, 14.0],
        }
    )

    pipeline.save_source(dataset_id, b"group,value\nA,1\n", "dataset.csv")
    pipeline.create_processed_snapshot(
        dataset_id,
        df,
        cleaning_log={"action": "snapshot", "notes": "unit-test"},
    )

    processed_dir = os.path.join(str(tmp_path), dataset_id, "processed")
    with open(os.path.join(processed_dir, "study_design.json"), "w", encoding="utf-8") as f:
        json.dump({"design": {"group_column": "group", "outcomes": ["value"]}}, f, ensure_ascii=False)

    freeze_analysis_set(
        str(tmp_path),
        dataset_id,
        df=df,
        mode="complete_case",
        enforce="models",
        required_non_missing=["group", "value"],
        impute_columns=[],
        actor="test",
        source="test",
    )

    run_dir = pipeline.create_analysis_run(
        dataset_id,
        {
            "name": "Unit Protocol",
            "alpha": 0.05,
            "steps": [{"id": "s1", "method": "ancova", "config": {"outcome": "value", "group": "group"}}],
        },
    )
    run_state_path = os.path.join(run_dir, "run_state.json")
    assert os.path.exists(run_state_path)
    with open(run_state_path, "r", encoding="utf-8") as f:
        state_doc = json.load(f)

    assert state_doc.get("state") == "compile"
    transitions = state_doc.get("transitions") if isinstance(state_doc.get("transitions"), list) else []
    assert [item.get("to") for item in transitions] == ["profile", "clean", "design", "freeze", "compile"]
    artifacts = state_doc.get("artifacts") if isinstance(state_doc.get("artifacts"), dict) else {}
    for key in ["source_raw", "source_meta", "profile", "cleaning_plan", "cleaning_log", "processed_dataset", "design", "analysis_set", "protocol"]:
        assert key in artifacts


def test_build_dataset_state_document_reaches_freeze(tmp_path):
    pipeline = PipelineManager(str(tmp_path))
    dataset_id = "pipeline_dataset_state_ds"
    df = pd.DataFrame(
        {
            "group": ["A", "B", "B", "A"],
            "value": [1.1, 2.2, 3.3, 4.4],
        }
    )

    pipeline.save_source(dataset_id, b"group,value\nA,1\n", "dataset.csv")
    pipeline.create_processed_snapshot(dataset_id, df, cleaning_log={"action": "snapshot"})
    processed_dir = os.path.join(str(tmp_path), dataset_id, "processed")
    with open(os.path.join(processed_dir, "study_design.json"), "w", encoding="utf-8") as f:
        json.dump({"design": {"group_column": "group", "outcomes": ["value"]}}, f, ensure_ascii=False)

    freeze_analysis_set(
        str(tmp_path),
        dataset_id,
        df=df,
        mode="complete_case",
        enforce="models",
        required_non_missing=["group", "value"],
        impute_columns=[],
        actor="test",
        source="test",
    )

    state_doc = pipeline.build_dataset_state_document(dataset_id)
    assert state_doc.get("state") == "freeze"
    assert state_doc.get("missing_artifacts") == []
    transitions = state_doc.get("transitions") if isinstance(state_doc.get("transitions"), list) else []
    assert [item.get("to") for item in transitions] == ["profile", "clean", "design", "freeze"]
