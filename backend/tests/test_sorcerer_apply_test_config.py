import os
import shutil
from io import BytesIO

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.api.datasets import DATA_DIR
from app.main import app


client = TestClient(app)


def _upload_dataset(df: pd.DataFrame) -> str:
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    resp = client.post(
        "/api/v1/datasets",
        files={"file": ("sorcerer_test.csv", buf, "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    dataset_id = resp.json()["id"]
    assert dataset_id
    return dataset_id


def _cleanup_dataset(dataset_id: str) -> None:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    if os.path.exists(ds_dir):
        shutil.rmtree(ds_dir)


def test_sorcerer_apply_uses_test_config_for_posthoc():
    rng = np.random.default_rng(42)
    n = 30
    df = pd.DataFrame(
        {
            "Group": ["A"] * n + ["B"] * n + ["C"] * n,
            "Value": np.concatenate(
                [
                    rng.normal(0, 1, n),
                    rng.normal(6, 1, n),
                    rng.normal(12, 1, n),
                ]
            ),
        }
    )

    dataset_id = _upload_dataset(df)
    try:
        resp = client.post(
            "/api/v1/sorcerer/apply",
            json={
                "dataset_id": dataset_id,
                "recommendation": {
                    "method_id": "anova",
                    "name": "ANOVA",
                    "description": "",
                    "assumptions": [],
                },
                "variables": {
                    "target": "Value",
                    "group": "Group",
                    "all_numeric": False,
                    "post_hoc": "none",
                    "post_hoc_correction": "none",
                },
                "test_config": {
                    "post_hoc": "tukey",
                    "post_hoc_correction": "bonferroni",
                },
                "alpha": 0.05,
            },
        )
        assert resp.status_code == 200, resp.text
        results = resp.json().get("results")
        assert isinstance(results, dict)

        post_hoc = results.get("post_hoc")
        assert isinstance(post_hoc, list) and len(post_hoc) > 0
        assert any(isinstance(r, dict) and "p_value_adj" in r for r in post_hoc)
        assert any(isinstance(r, dict) and r.get("correction") == "bonferroni" for r in post_hoc)
    finally:
        _cleanup_dataset(dataset_id)


def test_sorcerer_apply_uses_test_config_for_multiplicity():
    rng = np.random.default_rng(7)
    n = 40
    df = pd.DataFrame(
        {
            "Group": ["A"] * n + ["B"] * n,
            "Value1": np.concatenate([rng.normal(0, 1, n), rng.normal(1.5, 1, n)]),
            "Value2": np.concatenate([rng.normal(0, 1, n), rng.normal(2.0, 1, n)]),
        }
    )

    dataset_id = _upload_dataset(df)
    try:
        resp = client.post(
            "/api/v1/sorcerer/apply",
            json={
                "dataset_id": dataset_id,
                "recommendation": {
                    "method_id": "t_test_ind",
                    "name": "t-test",
                    "description": "",
                    "assumptions": [],
                },
                "variables": {
                    "target": "",
                    "group": "Group",
                    "all_numeric": True,
                    "multiplicity_correction": "fdr_bh",
                    "post_hoc": "none",
                    "post_hoc_correction": "none",
                },
                "test_config": {
                    "multiplicity_correction": "bonferroni",
                },
                "alpha": 0.05,
            },
        )

        assert resp.status_code == 200, resp.text
        results = resp.json().get("results")
        assert isinstance(results, dict)
        assert results.get("type") == "batch_analysis"
        assert results.get("multiplicity_correction") == "bonferroni"

        items = results.get("items")
        assert isinstance(items, list) and len(items) >= 2
        for it in items:
            assert it.get("multiplicity_correction") == "bonferroni"
            assert "p_value_adj" in it
    finally:
        _cleanup_dataset(dataset_id)

