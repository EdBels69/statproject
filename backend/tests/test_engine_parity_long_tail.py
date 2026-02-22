import json
import math
import os
import shutil
import sys
from typing import Dict

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.stats.engine import run_analysis


client = TestClient(app)


def _as_float(value):
    try:
        if value is None:
            return None
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        return None
    return None


def _build_paired_df(seed: int = 314, n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pre = rng.normal(12.0, 1.4, n)
    post = pre + rng.normal(0.9, 0.6, n)
    return pd.DataFrame(
        {
            "phase": ["pre"] * n + ["post"] * n,
            "value": np.concatenate([pre, post]),
        }
    )


def _run(method_id: str, df: pd.DataFrame, engine: str) -> Dict:
    return run_analysis(
        df,
        method_id,
        "value",
        "phase",
        alpha=0.05,
        engine=engine,
    )


def test_python_r_parity_for_paired_methods():
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available in PATH")

    df = _build_paired_df()
    probe = _run("t_test_rel", df, engine="r")
    if str(probe.get("engine", "")).strip().lower() != "r":
        pytest.skip("R engine is unavailable or fell back to Python")

    for method_id in ("t_test_rel", "wilcoxon"):
        py = _run(method_id, df, engine="python")
        r = _run(method_id, df, engine="r")

        assert "error" not in py, f"{method_id}: python error: {py.get('error')}"
        assert "error" not in r, f"{method_id}: r error: {r.get('error')}"
        assert str(r.get("engine", "")).strip().lower() == "r", f"{method_id}: expected R engine output"

        assert bool(py.get("significant")) == bool(r.get("significant")), (
            f"{method_id}: significance mismatch python={py.get('significant')} r={r.get('significant')}"
        )
        py_p = _as_float(py.get("p_value"))
        r_p = _as_float(r.get("p_value"))
        if py_p is not None and r_p is not None:
            assert abs(py_p - r_p) <= 0.2, (
                f"{method_id}: p-value drift too large python={py_p}, r={r_p}"
            )


def _prepare_responders_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    rng = np.random.default_rng(99)
    rows = []
    for i in range(1, 81):
        grp = "A" if i <= 40 else "B"
        baseline = 20.0 + rng.normal(0, 1.0)
        delta_1 = rng.normal(0.8, 0.35) if grp == "A" else rng.normal(2.4, 0.4)
        delta_2 = rng.normal(1.0, 0.4) if grp == "A" else rng.normal(3.0, 0.45)
        rows.append(
            {
                "subject": f"s{i:03d}",
                "group": grp,
                "v0": baseline,
                "v1": baseline - delta_1,
                "v2": baseline - delta_2,
            }
        )

    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))

    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "responders_long_tail.csv"}, f)
    with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-08T18:00:00",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def _execute_responders(dataset_id: str, engine: str) -> Dict:
    payload = {
        "dataset_id": dataset_id,
        "alpha": 0.05,
        "globals": {"design_confirmed": True},
        "protocol": [
            {
                "id": "responders_step",
                "method": "responders",
                "config": {
                    "outcome_columns": ["v0", "v1", "v2"],
                    "time_labels": ["baseline", "week2", "week4"],
                    "group": "group",
                    "subject": "subject",
                    "threshold": 1.5,
                    "direction": "decrease",
                    "engine": engine,
                },
            }
        ],
    }
    response = client.post("/api/v1/v2/analysis/execute", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") in {"completed", "partial"}
    assert isinstance(body.get("results"), list) and body["results"]
    step = body["results"][0]
    result = step.get("results") if isinstance(step, dict) else None
    assert isinstance(result, dict), body
    return result


def test_execute_responders_python_r_parity():
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available in PATH")

    dataset_id = "test_engine_parity_responders_long_tail"
    ds_dir = _prepare_responders_dataset(dataset_id)
    try:
        probe = _execute_responders(dataset_id, engine="r")
        if str(probe.get("engine", "")).strip().lower() != "r":
            pytest.skip("R engine is unavailable or fell back to Python")

        py = _execute_responders(dataset_id, engine="python")
        r = _execute_responders(dataset_id, engine="r")

        assert py.get("method_id") == "responders"
        assert r.get("method_id") == "responders"
        assert str(r.get("engine", "")).strip().lower() == "r"
        assert bool(py.get("significant")) == bool(r.get("significant"))

        py_p = _as_float(py.get("p_value"))
        r_p = _as_float(r.get("p_value"))
        if py_p is not None and r_p is not None:
            assert abs(py_p - r_p) <= 0.2, f"responders: p-value drift too large python={py_p}, r={r_p}"

        py_visits = py.get("by_visit") if isinstance(py.get("by_visit"), dict) else {}
        r_visits = r.get("by_visit") if isinstance(r.get("by_visit"), dict) else {}
        assert py_visits and r_visits

        common = sorted(set(py_visits.keys()).intersection(r_visits.keys()))
        assert common
        for visit in common:
            py_test = py_visits[visit].get("test") if isinstance(py_visits.get(visit), dict) else None
            r_test = r_visits[visit].get("test") if isinstance(r_visits.get(visit), dict) else None
            if isinstance(py_test, dict) and isinstance(r_test, dict):
                assert bool(py_test.get("significant")) == bool(r_test.get("significant"))
                py_test_p = _as_float(py_test.get("p_value"))
                r_test_p = _as_float(r_test.get("p_value"))
                if py_test_p is not None and r_test_p is not None:
                    assert abs(py_test_p - r_test_p) <= 0.25
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)

