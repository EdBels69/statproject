import json
import math
import os
import shutil
import sys
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR


client = TestClient(app)


def _as_float(value: Any):
    try:
        if value is None:
            return None
        out = float(value)
        if math.isfinite(out):
            return out
    except Exception:
        return None
    return None


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    rng = np.random.default_rng(2026)
    rows: List[Dict[str, Any]] = []
    for i in range(1, 81):
        grp = "A" if i <= 40 else "B"

        baseline_a = 15.0 + (0.02 * i) + (0.0 if grp == "A" else 1.2) + rng.normal(0, 0.35)
        follow_a = baseline_a - (rng.normal(0.7, 0.25) if grp == "A" else rng.normal(1.8, 0.3))

        baseline_b = 9.0 + (0.015 * i) + (0.0 if grp == "A" else 0.8) + rng.normal(0, 0.3)
        follow_b = baseline_b - (rng.normal(0.5, 0.2) if grp == "A" else rng.normal(1.3, 0.25))

        rows.append(
            {
                "subject": f"s{i:03d}",
                "group": grp,
                "baseline_a": baseline_a,
                "follow_a": follow_a,
                "baseline_b": baseline_b,
                "follow_b": follow_b,
            }
        )

    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))

    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "complex_protocol_parity.csv"}, f)
    with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-08T19:00:00",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def _build_protocol(engine: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": "s_compare",
            "method": "t_test_ind",
            "config": {
                "outcome": "baseline_a",
                "group": "group",
                "engine": engine,
            },
        },
        {
            "id": "s_responders",
            "method": "responders",
            "config": {
                "outcome_columns": ["baseline_a", "follow_a", "follow_b"],
                "time_labels": ["baseline", "week2", "week4"],
                "group": "group",
                "subject": "subject",
                "threshold": 1.0,
                "direction": "decrease",
                "engine": engine,
            },
        },
        {
            "id": "s_delta",
            "method": "delta_batch_analysis",
            "config": {
                "group": "group",
                "pairs": [
                    {"baseline": "baseline_a", "follow": "follow_a"},
                    {"baseline": "baseline_b", "follow": "follow_b"},
                ],
                "method_id": "t_test_ind",
                "engine": engine,
            },
        },
    ]


def _execute(dataset_id: str, engine: str) -> Dict[str, Dict[str, Any]]:
    payload = {
        "dataset_id": dataset_id,
        "alpha": 0.05,
        "globals": {"design_confirmed": True, "engine": engine},
        "protocol": _build_protocol(engine),
    }
    response = client.post("/api/v1/v2/analysis/execute", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") in {"completed", "partial"}
    results = body.get("results")
    assert isinstance(results, list) and results, body

    out: Dict[str, Dict[str, Any]] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        step_id = str(item.get("step_id") or item.get("id") or "").strip()
        payload = item.get("results")
        if step_id and isinstance(payload, dict):
            out[step_id] = payload
    return out


def _assert_step_parity(py: Dict[str, Any], r: Dict[str, Any], step_id: str, tol: float = 0.2) -> None:
    assert bool(py.get("significant")) == bool(r.get("significant")), (
        f"{step_id}: significance mismatch python={py.get('significant')} r={r.get('significant')}"
    )
    py_p = _as_float(py.get("p_value"))
    r_p = _as_float(r.get("p_value"))
    if py_p is not None and r_p is not None:
        assert abs(py_p - r_p) <= tol, f"{step_id}: p-value drift too large python={py_p}, r={r_p}"


def test_execute_complex_protocol_python_r_parity():
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available in PATH")

    dataset_id = "test_engine_parity_complex_protocol_e2e"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        probe = _execute(dataset_id, engine="r")
        probe_compare = probe.get("s_compare") if isinstance(probe, dict) else None
        if not isinstance(probe_compare, dict) or str(probe_compare.get("engine", "")).strip().lower() != "r":
            pytest.skip("R engine is unavailable or fell back to Python")

        py = _execute(dataset_id, engine="python")
        r = _execute(dataset_id, engine="r")

        for step in ("s_compare", "s_responders", "s_delta"):
            assert step in py and step in r, f"missing step in execute results: {step}"
            assert str(r[step].get("engine", "")).strip().lower() == "r", f"{step}: expected R engine output"

        _assert_step_parity(py["s_compare"], r["s_compare"], "s_compare", tol=0.2)
        _assert_step_parity(py["s_responders"], r["s_responders"], "s_responders", tol=0.2)

        py_items = py["s_delta"].get("items") if isinstance(py["s_delta"].get("items"), list) else []
        r_items = r["s_delta"].get("items") if isinstance(r["s_delta"].get("items"), list) else []
        assert py_items and r_items

        def _key(item: Dict[str, Any]) -> str:
            base = str(item.get("baseline") or "").strip()
            follow = str(item.get("follow") or "").strip()
            target = str(item.get("target") or "").strip()
            return f"{base}->{follow}" if base and follow else target

        py_by_key = {_key(i): i for i in py_items if isinstance(i, dict) and _key(i)}
        r_by_key = {_key(i): i for i in r_items if isinstance(i, dict) and _key(i)}
        common = sorted(set(py_by_key.keys()).intersection(r_by_key.keys()))
        assert common

        for key in common:
            py_item = py_by_key[key]
            r_item = r_by_key[key]
            assert str(r_item.get("engine", "")).strip().lower() == "r", f"{key}: expected R engine output"
            assert bool(py_item.get("significant")) == bool(r_item.get("significant")), (
                f"{key}: significance mismatch python={py_item.get('significant')} r={r_item.get('significant')}"
            )
            py_p = _as_float(py_item.get("p_value"))
            r_p = _as_float(r_item.get("p_value"))
            if py_p is not None and r_p is not None:
                assert abs(py_p - r_p) <= 0.25, f"{key}: p-value drift too large python={py_p}, r={r_p}"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)

