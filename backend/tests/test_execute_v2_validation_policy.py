import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.datasets import DATA_DIR
from app.main import app


client = TestClient(app)


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed_dir = os.path.join(ds_dir, "processed")
    source_dir = os.path.join(ds_dir, "source")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)

    rng = np.random.default_rng(19)
    rows = []
    for i in range(80):
        group = "A" if i < 40 else "B"
        rows.append(
            {
                "group": group,
                "cov1": float(rng.normal(10.0, 2.0)),
                "outcome": float(3.0 + (0.6 if group == "B" else 0.0) + rng.normal(0.0, 0.5)),
            }
        )
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed_dir, f"{dataset_id}.parquet"), index=False)

    with open(os.path.join(source_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "policy.csv"}, f)
    with open(os.path.join(source_dir, "original.raw"), "wb") as f:
        f.write(b"group,cov1,outcome\nA,1,2\n")

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


def _valid_protocol():
    return [
        {
            "id": "s1",
            "method": "ancova",
            "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1"]},
        }
    ]


def test_execute_v2_validation_profile_publication_defaults_apply():
    dataset_id = "test_exec_v2_policy_publication"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "analysis_mode": "focused",
                "validation_profile": "publication",
            },
            "protocol": _valid_protocol(),
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") == "completed", data

        policy = data.get("validation_policy")
        assert isinstance(policy, dict), data
        assert policy.get("profile") == "publication"
        assert policy.get("validator_enabled") is True
        assert policy.get("validator_strict") is True
        assert policy.get("reflection_enabled") is True
        assert int(policy.get("reflection_max_rounds") or 0) == 3
        assert policy.get("repair_correction") == "fdr_by"

        validation = data.get("protocol_validation")
        assert isinstance(validation, dict)
        assert validation.get("policy_profile") == "publication"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_v2_validation_profile_overrides_apply():
    dataset_id = "test_exec_v2_policy_overrides"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "analysis_mode": "focused",
                "validation_profile": "publication",
                "validator_strict": False,
                "agent_reflection_enabled": False,
                "agent_reflection_max_rounds": 7,
                "verifier_repair_correction": "holm",
            },
            "protocol": _valid_protocol(),
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") == "completed", data

        policy = data.get("validation_policy")
        assert isinstance(policy, dict), data
        assert policy.get("profile") == "publication"
        assert policy.get("validator_strict") is False
        assert policy.get("reflection_enabled") is False
        assert int(policy.get("reflection_max_rounds") or 0) == 7
        assert policy.get("repair_correction") == "holm"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_v2_validation_profile_auto_tracks_analysis_mode():
    dataset_id = "test_exec_v2_policy_auto"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "analysis_mode": "exploratory",
            },
            "protocol": _valid_protocol(),
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") == "completed", data

        policy = data.get("validation_policy")
        assert isinstance(policy, dict), data
        assert policy.get("profile") == "exploratory"
        assert policy.get("validator_strict") is False
        assert policy.get("reflection_enabled") is False
        assert int(policy.get("reflection_max_rounds") or 0) == 1
        assert policy.get("repair_correction") == "none"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)

