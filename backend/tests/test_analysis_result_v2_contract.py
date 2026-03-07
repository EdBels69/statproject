import json
import os
import shutil
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.modules.reporting import render_protocol_report


client = TestClient(app)


REQUIRED_KEYS = {
    "method_id",
    "engine",
    "stat_value",
    "p_value",
    "effect_size",
    "diagnostics",
    "warnings",
    "plots",
}


def _assert_v2_contract(payload):
    assert isinstance(payload, dict)
    for key in REQUIRED_KEYS:
        assert key in payload
    assert isinstance(payload.get("method_id"), str) and payload.get("method_id")
    assert payload.get("engine") in {"python", "r"}
    assert isinstance(payload.get("diagnostics"), dict)
    assert isinstance(payload.get("warnings"), list)
    assert isinstance(payload.get("plots"), list)


def _create_longitudinal_contract_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    rows = []
    for sid in range(1, 13):
        grp = "A" if sid <= 6 else "B"
        for t in [1, 2, 3]:
            baseline = 10.0 if grp == "A" else 11.0
            trend = 0.7 * t
            interaction = 0.8 * t if grp == "B" else 0.0
            marker = baseline + 0.25 * t + (0.2 if grp == "B" else 0.0) + 0.05 * sid
            outcome = baseline + trend + interaction + (0.08 * sid)
            rows.append(
                {
                    "group": grp,
                    "outcome": outcome,
                    "marker": marker,
                    "time": t,
                    "subject": f"s{sid:02d}",
                    "var1": outcome + 0.1 * t,
                    "var2": 0.9 * outcome + 0.1 * marker,
                    "var3": 0.8 * outcome + 0.2 * marker,
                    "var4": marker + 0.2 * t,
                    "var5": 0.9 * marker + 0.1 * outcome,
                    "var6": 0.85 * marker + 0.15 * outcome,
                }
            )

    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))

    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "contract_longitudinal.csv"}, f)
    with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-08T14:00:00",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def _create_group_compare_contract_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    df = pd.DataFrame(
        {
            "group": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "outcome": [10.2, 10.5, 9.9, 10.1, 11.8, 12.0, 11.6, 12.3],
            "marker": [101.0, 100.2, 102.4, 99.8, 110.5, 111.1, 109.7, 112.2],
        }
    )
    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "group_compare_contract.csv"}, f)
    return ds_dir


def test_execute_protocol_enforces_analysis_result_v2_contract():
    dataset_id = "test_analysis_result_v2_contract"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        df = pd.DataFrame(
            {
                "group": ["A", "A", "A", "B", "B", "B"],
                "outcome": [1.2, 1.4, 1.1, 2.0, 2.1, 1.9],
                "marker": [10.0, 10.5, 9.8, 12.2, 11.9, 12.4],
            }
        )
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))

        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "contract.csv"}, f)

        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-08T03:00:00",
                    "confirmed_by": "test",
                    "confirmed_source": "test",
                },
                f,
            )

        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": [
                {
                    "id": "s_hyp",
                    "method": "t_test_ind",
                    "config": {"outcome": "outcome", "group": "group"},
                },
                {
                    "id": "s_table",
                    "method": "descriptive_compare",
                    "config": {"target": "outcome", "group": "group"},
                },
                {
                    "id": "s_batch",
                    "method": "batch_analysis",
                    "config": {"group": "group", "targets": ["outcome", "marker"], "method_id": "t_test_ind"},
                },
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("status") in {"completed", "partial"}

        results = body.get("results")
        assert isinstance(results, list) and results
        for item in results:
            _assert_v2_contract(item.get("results"))

        run_id = body.get("run_id")
        assert isinstance(run_id, str) and run_id
        run_results_path = os.path.join(DATA_DIR, dataset_id, "analysis", run_id, "results.json")
        with open(run_results_path, "r", encoding="utf-8") as f:
            run_payload = json.load(f)

        by_step = run_payload.get("results")
        assert isinstance(by_step, dict) and by_step
        for payload_by_step in by_step.values():
            _assert_v2_contract(payload_by_step)
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_legacy_run_payload_is_normalized_for_run_and_reporting():
    dataset_id = "test_analysis_result_v2_legacy_run"
    run_id = "run_legacy_contract"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    run_dir = os.path.join(ds_dir, "analysis", run_id)
    os.makedirs(run_dir, exist_ok=True)

    try:
        legacy_payload = {
            "dataset_id": dataset_id,
            "protocol_name": "Legacy protocol",
            "results": {
                "legacy_step": {
                    "type": "hypothesis_test",
                    "method": "t_test_ind",
                    "p_value": 0.04,
                    "stat_value": 2.01,
                    "significant": True,
                }
            },
        }
        with open(os.path.join(run_dir, "results.json"), "w", encoding="utf-8") as f:
            json.dump(legacy_payload, f, ensure_ascii=False)

        response = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={dataset_id}")
        assert response.status_code == 200, response.text
        body = response.json()

        by_step = body.get("results")
        assert isinstance(by_step, dict) and by_step
        for payload_by_step in by_step.values():
            _assert_v2_contract(payload_by_step)

        assert isinstance(body.get("result_ir"), dict)
        html = render_protocol_report(body, dataset_name="Legacy Dataset", style="gost")
        assert "<html" in html.lower()
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_v2_mixed_effects_endpoint_returns_analysis_result_v2_contract():
    dataset_id = "test_analysis_result_v2_mixed_endpoint"
    ds_dir = _create_longitudinal_contract_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "outcome": "outcome",
            "time_col": "time",
            "group_col": "group",
            "subject_col": "subject",
            "covariates": ["marker"],
            "random_slope": False,
            "alpha": 0.05,
        }
        response = client.post("/api/v1/v2/mixed-effects", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        _assert_v2_contract(body)
        assert body.get("method_id") == "mixed_effects"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_v2_clustered_correlation_endpoint_returns_analysis_result_v2_contract():
    dataset_id = "test_analysis_result_v2_cluster_endpoint"
    ds_dir = _create_longitudinal_contract_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "variables": ["var1", "var2", "var3", "var4", "var5", "var6"],
            "method": "pearson",
            "linkage_method": "average",
            "n_clusters": 2,
            "show_p_values": True,
            "alpha": 0.05,
        }
        response = client.post("/api/v1/v2/clustered-correlation", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        _assert_v2_contract(body)
        assert body.get("method_id") == "clustered_correlation"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_v2_protocol_endpoint_returns_analysis_result_v2_contract():
    dataset_id = "test_analysis_result_v2_protocol_endpoint"
    ds_dir = _create_longitudinal_contract_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": {
                "method": "t_test_ind",
                "target_column": "outcome",
                "group_column": "group",
            },
        }
        response = client.post("/api/v1/v2/protocol", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        results = body.get("results")
        _assert_v2_contract(results)
        assert results.get("method_id") == "t_test_ind"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_v2_protocol_endpoint_supports_responders_contract():
    dataset_id = "test_analysis_result_v2_protocol_responders"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        rows = []
        for sid in range(1, 11):
            grp = "A" if sid <= 5 else "B"
            base = 10.0 + 0.1 * sid
            rows.append(
                {
                    "subject": f"s{sid:02d}",
                    "group": grp,
                    "v1": base,
                    "v2": base - (0.4 if grp == "A" else 1.2),
                    "v3": base - (0.7 if grp == "A" else 1.8),
                }
            )
        df = pd.DataFrame(rows)
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "responders_contract.csv"}, f)
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-08T17:30:00",
                    "confirmed_by": "test",
                    "confirmed_source": "test",
                },
                f,
            )

        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": {
                "method": "responders",
                "outcome_columns": ["v1", "v2", "v3"],
                "time_labels": ["baseline", "week2", "week4"],
                "group_column": "group",
                "subject_column": "subject",
                "threshold": 1.0,
                "direction": "decrease",
            },
        }
        response = client.post("/api/v1/v2/protocol", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        results = body.get("results")
        _assert_v2_contract(results)
        assert results.get("method_id") == "responders"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_legacy_analysis_run_endpoint_returns_v2_contract_fields():
    dataset_id = "test_analysis_result_v2_legacy_run_endpoint"
    ds_dir = _create_group_compare_contract_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "target_column": "outcome",
            "features": ["group"],
            "method_override": "t_test_ind",
            "is_paired": False,
            "engine": "python",
        }
        response = client.post("/api/v1/analysis/run", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        _assert_v2_contract(body)
        assert body.get("method_id") == "t_test_ind"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_legacy_analysis_batch_endpoint_returns_v2_contract_fields():
    dataset_id = "test_analysis_result_v2_legacy_batch_endpoint"
    ds_dir = _create_group_compare_contract_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "target_columns": ["outcome", "marker"],
            "group_column": "group",
            "alpha": 0.05,
        }
        response = client.post("/api/v1/analysis/batch", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        results = body.get("results")
        assert isinstance(results, dict) and results
        for item in results.values():
            _assert_v2_contract(item)
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
