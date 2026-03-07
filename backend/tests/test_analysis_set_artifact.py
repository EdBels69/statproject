import json
import os
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import datasets as ds
from app.api import v2 as v2_api
from app.core.pipeline import PipelineManager


client = TestClient(app)


def _write_parquet_dataset(base_dir: str, dataset_id: str, df: pd.DataFrame) -> None:
    ds_root = os.path.join(base_dir, dataset_id)
    os.makedirs(os.path.join(ds_root, "processed"), exist_ok=True)
    os.makedirs(os.path.join(ds_root, "source"), exist_ok=True)
    os.makedirs(os.path.join(ds_root, "analysis"), exist_ok=True)
    df.to_parquet(os.path.join(ds_root, "processed", f"{dataset_id}.parquet"))
    with open(os.path.join(ds_root, "source", "original.raw"), "wb") as f:
        f.write(b"dummy")
    with open(os.path.join(ds_root, "source", "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "test.xlsx", "header_row": 0}, f)


def _confirm_design_review(base_dir: str, dataset_id: str) -> None:
    ds_root = os.path.join(base_dir, dataset_id)
    os.makedirs(os.path.join(ds_root, "processed"), exist_ok=True)
    with open(os.path.join(ds_root, "processed", "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-08T00:00:00",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )


def test_analysis_set_endpoints_freeze_and_clear(tmp_path, monkeypatch):
    dataset_id = "analysis_set_endpoint_ds"
    df = pd.DataFrame(
        {
            "y": [1, 0, 1, 0, 1],
            "x": [1.0, 2.0, None, 4.0, 5.0],
        }
    )
    _write_parquet_dataset(str(tmp_path), dataset_id, df)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))

    response = client.get(f"/api/v1/datasets/{dataset_id}/analysis_set")
    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_exists"] is False

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "mode": "complete_case",
            "enforce": "models",
            "required_non_missing": ["y", "x"],
            "impute_columns": [],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_exists"] is True
    assert isinstance(payload.get("analysis_set_id"), str) and payload["analysis_set_id"]
    assert payload.get("mode") == "complete_case"
    assert payload.get("enforce") == "models"
    assert payload.get("n_total") == 5
    assert payload.get("n_selected") == 4  # one x is missing

    set_id = payload["analysis_set_id"]
    artifact_path = os.path.join(str(tmp_path), dataset_id, "processed", "analysis_sets", f"{set_id}.json")
    artifact_parquet_path = os.path.join(str(tmp_path), dataset_id, "processed", "analysis_sets", f"{set_id}.parquet")
    pointer_path = os.path.join(str(tmp_path), dataset_id, "processed", "analysis_set_current.json")
    hash_path = os.path.join(str(tmp_path), dataset_id, "processed", "analysis_set_hash.json")
    assert os.path.exists(artifact_path)
    assert os.path.exists(artifact_parquet_path)
    assert os.path.exists(pointer_path)
    assert os.path.exists(hash_path)
    with open(hash_path, "r", encoding="utf-8") as f:
        hash_payload = json.load(f)
    assert hash_payload.get("analysis_set_id") == set_id
    assert isinstance(hash_payload.get("analysis_set_sha256"), str) and hash_payload.get("analysis_set_sha256")

    state_response = client.get(f"/api/v1/datasets/{dataset_id}/pipeline_state")
    assert state_response.status_code == 200
    state_payload = state_response.json()
    assert state_payload.get("state") == "profile"
    assert isinstance(state_payload.get("artifacts"), dict)
    assert "analysis_set" in state_payload["artifacts"]

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/clear",
        json={"actor": "qa-user", "source": "frontend-test"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_exists"] is False
    assert not os.path.exists(pointer_path)
    assert not os.path.exists(hash_path)

    state_response_after_clear = client.get(f"/api/v1/datasets/{dataset_id}/pipeline_state")
    assert state_response_after_clear.status_code == 200
    state_payload_after_clear = state_response_after_clear.json()
    assert state_payload_after_clear.get("state") == "profile"
    assert "analysis_set" not in (state_payload_after_clear.get("artifacts") or {})


def test_analysis_set_freeze_invalid_payload_returns_400(tmp_path, monkeypatch):
    dataset_id = "analysis_set_invalid_payload_ds"
    df = pd.DataFrame({"y": [1, 0, 1], "x": [1.0, 2.0, 3.0]})
    _write_parquet_dataset(str(tmp_path), dataset_id, df)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "mode": "complete_case",
            "enforce": "models",
            "required_non_missing": [],
            "impute_columns": [],
        },
    )
    assert response.status_code == 400
    assert "required_non_missing" in response.text


def test_analysis_set_strict_enforcement_in_v2_execute(tmp_path, monkeypatch):
    dataset_id = "analysis_set_execute_ds"
    df = pd.DataFrame(
        {
            "y": [1, 0, 1, 0, 1, 0, 1, 0],
            "x1": [1.0, 2.0, 3.0, 4.0, None, 6.0, 7.0, 8.0],
        }
    )
    _write_parquet_dataset(str(tmp_path), dataset_id, df)
    _confirm_design_review(str(tmp_path), dataset_id)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))
    monkeypatch.setattr(v2_api, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(v2_api, "pipeline", PipelineManager(str(tmp_path)))

    # Freeze complete-case covering both outcome and predictor: should work.
    resp_freeze = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "mode": "complete_case",
            "enforce": "models",
            "required_non_missing": ["y", "x1"],
            "impute_columns": [],
        },
    )
    assert resp_freeze.status_code == 200
    analysis_set_id = resp_freeze.json()["analysis_set_id"]

    exec_payload = {
        "dataset_id": dataset_id,
        "alpha": 0.05,
        "globals": {"analysis_set_id": analysis_set_id, "analysis_set_strict": True},
        "protocol": [
            {
                "id": "m1",
                "method": "logistic_regression",
                "config": {"outcome": "y", "predictors": ["x1"]},
            }
        ],
    }
    resp_exec = client.post("/api/v1/v2/analysis/execute", json=exec_payload)
    assert resp_exec.status_code == 200, resp_exec.text
    out = resp_exec.json()
    assert out.get("analysis_set", {}).get("analysis_set_id") == analysis_set_id
    step = (out.get("results") or [])[0]
    step_results = step.get("results") if isinstance(step, dict) else {}
    # n_selected should be 7 because one x1 is missing.
    assert int(step_results.get("n_obs") or 0) == 7

    # Freeze with insufficient coverage: should hard-fail before running.
    resp_freeze2 = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "mode": "complete_case",
            "enforce": "models",
            "required_non_missing": ["y"],
            "impute_columns": [],
        },
    )
    assert resp_freeze2.status_code == 200
    analysis_set_id2 = resp_freeze2.json()["analysis_set_id"]
    exec_payload["globals"]["analysis_set_id"] = analysis_set_id2
    resp_exec2 = client.post("/api/v1/v2/analysis/execute", json=exec_payload)
    assert resp_exec2.status_code == 400
    assert "не покрывает" in resp_exec2.text.lower()

    # Simple impute: outcome required, predictor imputed; should work with N=8.
    resp_freeze3 = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "mode": "simple_impute",
            "enforce": "models",
            "required_non_missing": ["y"],
            "impute_columns": ["x1"],
        },
    )
    assert resp_freeze3.status_code == 200
    analysis_set_id3 = resp_freeze3.json()["analysis_set_id"]
    exec_payload["globals"]["analysis_set_id"] = analysis_set_id3
    resp_exec3 = client.post("/api/v1/v2/analysis/execute", json=exec_payload)
    assert resp_exec3.status_code == 200, resp_exec3.text
    out3 = resp_exec3.json()
    step3 = (out3.get("results") or [])[0]
    step3_results = step3.get("results") if isinstance(step3, dict) else {}
    assert int(step3_results.get("n_obs") or 0) == 8
