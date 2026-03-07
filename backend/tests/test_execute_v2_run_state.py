import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR


client = TestClient(app)


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed_dir = os.path.join(ds_dir, "processed")
    source_dir = os.path.join(ds_dir, "source")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)

    rng = np.random.default_rng(7)
    rows = []
    for i in range(60):
        group = "A" if i < 30 else "B"
        rows.append(
            {
                "group": group,
                "cov1": float(rng.normal(50.0, 8.0)),
                "outcome": float(10.0 + (1.0 if group == "B" else 0.0) + rng.normal(0.0, 0.8)),
            }
        )
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed_dir, f"{dataset_id}.parquet"), index=False)

    with open(os.path.join(source_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "execute_v2_state.csv"}, f)

    with open(os.path.join(processed_dir, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-23T12:00:00Z",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def test_execute_v2_tracks_run_state_and_verification_artifacts():
    dataset_id = "test_exec_v2_run_state"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {"design_confirmed": True},
            "protocol": [
                {
                    "id": "s1",
                    "method": "ancova",
                    "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1"]},
                }
            ],
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert not data.get("errors"), data

        run_state = data.get("run_state")
        assert isinstance(run_state, dict), data
        assert run_state.get("state") == "release"

        run_id = str(data.get("run_id") or "")
        assert run_id
        run_dir = os.path.join(ds_dir, "analysis", run_id)
        artifacts_dir = os.path.join(run_dir, "artifacts")
        assert os.path.exists(os.path.join(artifacts_dir, "verification.json"))
        assert os.path.exists(os.path.join(artifacts_dir, "reproducibility_manifest.json"))

        run_state_path = os.path.join(run_dir, "run_state.json")
        assert os.path.exists(run_state_path)
        with open(run_state_path, "r", encoding="utf-8") as f:
            state_doc = json.load(f)

        assert state_doc.get("state") == "release"
        artifacts = state_doc.get("artifacts")
        assert isinstance(artifacts, dict)
        for key in [
            "protocol",
            "results",
            "verification",
            "report_html",
            "reproducibility_manifest",
            "reproduce_script",
            "reproduce_payload",
            "protocol_resolved",
            "hypothesis_discovery",
        ]:
            assert key in artifacts, state_doc
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
