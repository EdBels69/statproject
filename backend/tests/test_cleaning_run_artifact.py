import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.cleaning_run import (
    build_cleaning_run_artifact,
    validate_cleaning_run_artifact,
    dataframe_fingerprint,
)


def test_build_cleaning_run_artifact_contains_before_after_and_delta():
    df_before = pd.DataFrame(
        {
            "a": [1.0, None, 3.0, None],
            "b": ["x", "na", "y", ""],
        }
    )
    df_after = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0],
            "b": ["x", "x", "y", "z"],
        }
    )
    artifact = build_cleaning_run_artifact(
        dataset_id="ds1",
        cleaning_log={"action": "modify", "count": 2},
        df_before=df_before,
        df_after=df_after,
        actor="qa",
        source="test",
    )

    assert artifact.get("artifact_type") == "cleaning_run"
    assert artifact.get("dataset_id") == "ds1"
    assert isinstance(artifact.get("operations"), list)
    assert int(artifact.get("operation_count") or 0) >= 1
    assert artifact.get("before", {}).get("missingness", {}).get("missing_cells") is not None
    assert artifact.get("after", {}).get("missingness", {}).get("missing_cells") is not None
    assert artifact.get("delta", {}).get("missing_cells_delta") is not None


def test_validate_cleaning_run_artifact_detects_fingerprint_mismatch():
    df = pd.DataFrame({"x": [1, 2, 3], "y": [None, 5, 6]})
    artifact = build_cleaning_run_artifact(
        dataset_id="ds2",
        cleaning_log={"action": "ingest"},
        df_before=None,
        df_after=df,
        actor="qa",
        source="test",
    )

    ok, reason = validate_cleaning_run_artifact(artifact, current_df=df)
    assert ok is True
    assert reason == "ok"

    mutated = dict(artifact)
    mutated_after = dict(mutated.get("after") or {})
    mutated_after["fingerprint"] = dataframe_fingerprint(pd.DataFrame({"x": [0], "y": [0]}))
    mutated["after"] = mutated_after

    ok2, reason2 = validate_cleaning_run_artifact(mutated, current_df=df)
    assert ok2 is False
    assert reason2 == "fingerprint_mismatch"

