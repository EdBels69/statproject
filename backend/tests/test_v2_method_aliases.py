import json
import os
import shutil
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.api.v2 import _canonical_method_id


client = TestClient(app)


def test_canonical_method_aliases():
    assert _canonical_method_id("mixed_model") == "mixed_effects"
    assert _canonical_method_id("fisher") == "fisher_exact"
    assert _canonical_method_id("welch_t_test") == "t_test_welch"
    assert _canonical_method_id("kruskal_wallis") == "kruskal"


def test_execute_protocol_survival_km_path():
    dataset_id = "test_v2_survival_alias"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        df = pd.DataFrame(
            {
                "duration": [5, 7, 4, 12, 9, 11, 3, 6],
                "event": [1, 0, 1, 1, 0, 1, 1, 0],
                "group": ["A", "A", "A", "A", "B", "B", "B", "B"],
            }
        )
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "survival.csv"}, f)
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-07T12:00:00",
                    "confirmed_by": "test",
                    "confirmed_source": "test",
                },
                f,
            )

        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {"design_confirmed": True},
            "protocol": [
                {
                    "id": "s1",
                    "method": "survival_km",
                    "config": {"target": "duration", "event": "event", "group": "group"},
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") in {"completed", "partial"}
        assert data.get("run_id")
        if data.get("errors"):
            all_errors = " | ".join(str(e.get("error", "")) for e in data.get("errors", []))
            assert "не реализован" not in all_errors.lower()
            assert "not implemented" not in all_errors.lower()
        else:
            assert isinstance(data.get("results"), list) and data["results"]
            step = data["results"][0]
            assert step.get("status") == "completed"
            method_meta = step.get("results", {}).get("method")
            if isinstance(method_meta, dict):
                assert method_meta.get("id") == "survival_km"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
