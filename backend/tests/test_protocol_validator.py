import json
import os
import shutil
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.datasets import DATA_DIR
from app.copilot.validator import validate_protocol_step, build_protocol_validation_report
from app.main import app


client = TestClient(app)


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed_dir = os.path.join(ds_dir, "processed")
    source_dir = os.path.join(ds_dir, "source")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)

    df = pd.DataFrame(
        [
            {"group": "A", "cov1": 10.0, "outcome": 7.0},
            {"group": "A", "cov1": 11.0, "outcome": 8.0},
            {"group": "B", "cov1": 12.0, "outcome": 9.0},
            {"group": "B", "cov1": 13.0, "outcome": 10.0},
        ]
    )
    df.to_parquet(os.path.join(processed_dir, f"{dataset_id}.parquet"), index=False)

    with open(os.path.join(source_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "validator.csv"}, f)
    with open(os.path.join(source_dir, "original.raw"), "wb") as f:
        f.write(b"group,cov1,outcome\nA,10,7\n")

    with open(os.path.join(processed_dir, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-24T00:00:00Z",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def test_validate_protocol_step_detects_missing_required_keys():
    df = pd.DataFrame({"group": ["A", "B"], "outcome": [1.0, 2.0]})
    step = {"id": "s1", "method": "ancova", "config": {"outcome": "outcome", "group": "group"}}

    report = validate_protocol_step(step, df, alpha=0.05)

    assert report["status"] == "failed"
    assert any("Missing required config keys" in msg for msg in report["errors"])


def test_build_protocol_validation_report_summary_counts():
    rows = [
        {"step_id": "s1", "status": "passed", "errors": [], "warnings": [], "checks": []},
        {"step_id": "s2", "status": "failed", "errors": ["x"], "warnings": [], "checks": []},
    ]
    report = build_protocol_validation_report(
        steps=[{"id": "s1"}, {"id": "s2"}],
        step_reports=rows,
        validator_enabled=True,
        validator_strict=True,
        alpha=0.05,
        global_errors=[{"code": "dup"}],
    )

    assert report["status"] == "failed"
    summary = report["summary"]
    assert int(summary["steps_total"]) == 2
    assert int(summary["steps_failed"]) == 1
    assert int(summary["global_errors"]) == 1


def test_validate_protocol_step_timeseries_warns_on_epoch_like_years():
    df = pd.DataFrame(
        {
            "visit_date": ["1970-01-01", "1970-01-08", "1970-01-15", "1970-01-22"],
            "outcome": [1.0, 1.2, 0.9, 1.1],
        }
    )
    step = {
        "id": "ts1",
        "method": "time_series_analysis",
        "config": {"time": "visit_date", "outcome": "outcome"},
    }

    report = validate_protocol_step(step, df, alpha=0.05)

    assert report["status"] == "passed"
    assert any("1970-1985" in msg or "epoch" in msg.lower() for msg in report["warnings"])
    assert any((row.get("check") == "time_series_time_quality") for row in report["checks"])


def test_validate_protocol_step_bland_altman_requires_distinct_columns():
    df = pd.DataFrame({"m1": [1.0, 2.0, 3.0, 4.0]})
    step = {
        "id": "ba1",
        "method": "bland_altman",
        "config": {"method_1": "m1", "method_2": "m1"},
    }

    report = validate_protocol_step(step, df, alpha=0.05)

    assert report["status"] == "failed"
    assert any("distinct measurement columns" in msg for msg in report["errors"])


def test_validate_protocol_step_efa_requires_at_least_three_variables():
    df = pd.DataFrame({"v1": [1.0, 2.0, 3.0, 4.0], "v2": [2.0, 3.0, 4.0, 5.0]})
    step = {"id": "efa1", "method": "efa", "config": {"variables": ["v1", "v2"]}}

    report = validate_protocol_step(step, df, alpha=0.05)

    assert report["status"] == "failed"
    assert any("requires at least 3 variables" in msg for msg in report["errors"])


def test_execute_v2_strict_validator_blocks_invalid_step_and_writes_artifact():
    dataset_id = "test_exec_v2_validator_strict"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "validator_enabled": True,
                "validator_strict": True,
            },
            "protocol": [
                {
                    "id": "s1",
                    "method": "ancova",
                    "config": {"outcome": "outcome", "group": "group"},
                }
            ],
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()

        assert data.get("status") == "partial"
        errs = data.get("errors") if isinstance(data.get("errors"), list) else []
        assert any(str(item.get("method")) == "validator" for item in errs if isinstance(item, dict))

        validation = data.get("protocol_validation")
        assert isinstance(validation, dict), data
        assert validation.get("status") == "failed"
        assert int(validation.get("summary", {}).get("steps_failed") or 0) >= 1

        run_id = str(data.get("run_id") or "")
        assert run_id
        artifact_path = os.path.join(ds_dir, "analysis", run_id, "artifacts", "protocol_validation.json")
        assert os.path.exists(artifact_path)

        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)
        assert artifact.get("schema") == "clinimetria.protocol_validation"
        assert artifact.get("status") == "failed"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
