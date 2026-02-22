import json
import os
import shutil
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR


client = TestClient(app)


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    rows = []
    for i in range(1, 33):
        grp = "A" if i <= 16 else "B"
        timepoint = "T1" if i % 2 == 0 else "T2"
        base_shift = 0.0 if grp == "A" else 1.6
        tp_shift = 0.0 if timepoint == "T1" else 0.7

        baseline_a = 10.0 + base_shift + tp_shift + (0.03 * i)
        follow_a = baseline_a + (0.35 if grp == "A" else 1.05)
        baseline_b = 7.5 + 0.75 * base_shift + 0.4 * tp_shift + (0.02 * i)
        follow_b = baseline_b + (0.25 if grp == "A" else 0.85)

        rows.append(
            {
                "group": grp,
                "timepoint": timepoint,
                "baseline_a": baseline_a,
                "follow_a": follow_a,
                "baseline_b": baseline_b,
                "follow_b": follow_b,
                "metric_x": baseline_a * 0.8 + follow_b * 0.2,
                "metric_y": baseline_b * 0.7 + follow_a * 0.3,
            }
        )

    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))

    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "advanced_batch_modes.csv"}, f)
    with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-08T16:00:00",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def _run_execute(dataset_id: str, method: str, config: dict) -> dict:
    payload = {
        "dataset_id": dataset_id,
        "alpha": 0.05,
        "globals": {"design_confirmed": True},
        "protocol": [
            {
                "id": "s1",
                "method": method,
                "config": config,
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


def _assert_items_engine_r(items):
    assert isinstance(items, list) and items
    engines = [
        str(item.get("engine") or "").strip().lower()
        for item in items
        if isinstance(item, dict) and "error" not in item
    ]
    assert engines, items
    assert all(engine == "r" for engine in engines), items


def test_execute_batch_analysis_with_r_engine():
    dataset_id = "test_engine_parity_batch_analysis_r"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        result = _run_execute(
            dataset_id,
            "batch_analysis",
            {
                "group": "group",
                "targets": ["baseline_a", "follow_a", "metric_x"],
                "method_id": "t_test_ind",
                "engine": "r",
            },
        )
        assert str(result.get("engine") or "").strip().lower() == "r"
        _assert_items_engine_r(result.get("items"))
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_timepoint_batch_analysis_with_r_engine():
    dataset_id = "test_engine_parity_timepoint_batch_r"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        result = _run_execute(
            dataset_id,
            "timepoint_batch_analysis",
            {
                "split_by": "timepoint",
                "group": "group",
                "targets": ["baseline_a", "follow_a"],
                "method_id": "t_test_ind",
                "engine": "r",
            },
        )
        assert str(result.get("engine") or "").strip().lower() == "r"
        slices = result.get("slices")
        assert isinstance(slices, dict) and slices
        for payload in slices.values():
            assert isinstance(payload, dict)
            _assert_items_engine_r(payload.get("items"))
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_delta_batch_analysis_with_r_engine():
    dataset_id = "test_engine_parity_delta_batch_r"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        result = _run_execute(
            dataset_id,
            "delta_batch_analysis",
            {
                "group": "group",
                "pairs": [
                    {"baseline": "baseline_a", "follow": "follow_a"},
                    {"baseline": "baseline_b", "follow": "follow_b"},
                ],
                "method_id": "t_test_ind",
                "engine": "r",
            },
        )
        assert str(result.get("engine") or "").strip().lower() == "r"
        _assert_items_engine_r(result.get("items"))
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_paired_wide_with_r_engine():
    dataset_id = "test_engine_parity_paired_wide_r"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        result = _run_execute(
            dataset_id,
            "paired_wide",
            {
                "baseline": "baseline_a",
                "follow": "follow_a",
                "method": "t_test_rel",
                "engine": "r",
            },
        )
        assert str(result.get("engine") or "").strip().lower() == "r"
        assert isinstance(result.get("p_value"), (float, int))
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
