import json
import os
import shutil
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.api import v2 as v2_api


client = TestClient(app)

REQUIRED_V2_KEYS = {
    "method_id",
    "engine",
    "stat_value",
    "p_value",
    "effect_size",
    "diagnostics",
    "warnings",
    "plots",
}


def _assert_v2_contract(payload: dict) -> None:
    assert isinstance(payload, dict)
    for key in REQUIRED_V2_KEYS:
        assert key in payload
    assert isinstance(payload.get("method_id"), str) and payload.get("method_id")
    assert payload.get("engine") in {"python", "r"}
    assert isinstance(payload.get("diagnostics"), dict)
    assert isinstance(payload.get("warnings"), list)
    assert isinstance(payload.get("plots"), list)


def _prepare_dataset(dataset_id: str, df: pd.DataFrame, *, with_design_review: bool = True) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": f"{dataset_id}.csv"}, f)

    if with_design_review:
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-22T10:00:00",
                    "confirmed_by": "test",
                    "confirmed_source": "test",
                },
                f,
            )

    return ds_dir


def _write_scan_and_design(dataset_id: str, *, n_rows: int) -> None:
    processed = os.path.join(DATA_DIR, dataset_id, "processed")
    os.makedirs(processed, exist_ok=True)

    scan_report = {
        "columns": {
            "group": {"type": "category", "unique_count": 2, "categories": ["A", "B"]},
            "age": {"type": "float64"},
            "crp": {"type": "float64"},
            "wbc": {"type": "float64"},
            "ferritin": {"type": "float64"},
            "event": {"type": "category", "unique_count": 2, "categories": [0, 1]},
        },
        "missing_report": {"total_rows": int(n_rows), "by_column": []},
    }
    with open(os.path.join(processed, "scan_report.json"), "w", encoding="utf-8") as f:
        json.dump(scan_report, f, ensure_ascii=False)

    study_design = {
        "dataset_id": dataset_id,
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "design": {
            "design_type": "cross_sectional",
            "group_column": "group",
            "time_column": None,
            "subject_column": None,
            "outcomes": ["crp", "ferritin"],
            "categorical_outcomes": ["event"],
            "predictors": ["age", "crp", "wbc", "ferritin", "group"],
            "id_like_columns": [],
            "endpoint_groups": [],
        },
        "analysis_policy": {},
    }
    with open(os.path.join(processed, "study_design.json"), "w", encoding="utf-8") as f:
        json.dump(study_design, f, ensure_ascii=False)


def test_execute_protocol_supports_p2_bootstrap_and_cluster_profiles():
    dataset_id = "test_p2_bootstrap_cluster"
    rng = np.random.default_rng(42)
    n = 120

    age = rng.normal(60.0, 9.0, n)
    crp = rng.normal(40.0, 11.0, n)
    wbc = rng.normal(8.2, 2.1, n)
    ferritin = 0.6 * crp + 0.4 * age + rng.normal(0.0, 4.0, n)
    group = np.where(rng.random(n) > 0.5, "A", "B")

    # Add a stable between-group shift to make bootstrap signal detectable.
    crp = np.where(group == "B", crp + 4.5, crp)

    df = pd.DataFrame(
        {
            "group": group,
            "age": age,
            "crp": crp,
            "wbc": wbc,
            "ferritin": ferritin,
        }
    )

    ds_dir = _prepare_dataset(dataset_id, df, with_design_review=True)

    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {"analysis_mode": "exploratory"},
            "protocol": [
                {
                    "id": "p2_boot",
                    "method": "bootstrap_pipeline",
                    "config": {
                        "outcome": "crp",
                        "group": "group",
                        "n_resamples": 350,
                        "ci_level": 0.95,
                        "random_state": 42,
                    },
                },
                {
                    "id": "p2_cluster",
                    "method": "cluster_profiles",
                    "config": {
                        "variables": ["age", "crp", "wbc", "ferritin"],
                        "n_clusters": 3,
                        "random_state": 42,
                    },
                },
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("status") in {"completed", "partial"}

        rows = body.get("results")
        assert isinstance(rows, list) and rows
        by_method = {}
        for row in rows:
            payload_row = row.get("results") if isinstance(row, dict) else None
            if isinstance(payload_row, dict):
                by_method[str(payload_row.get("method_id") or "")] = payload_row

        boot = by_method.get("bootstrap_pipeline")
        assert isinstance(boot, dict), by_method
        _assert_v2_contract(boot)
        assert isinstance(boot.get("stat_value"), (int, float))
        assert isinstance(boot.get("p_value"), (int, float))
        assert isinstance(boot.get("effect_size_ci_lower"), (int, float))
        assert isinstance(boot.get("effect_size_ci_upper"), (int, float))

        cluster = by_method.get("cluster_profiles")
        assert isinstance(cluster, dict), by_method
        _assert_v2_contract(cluster)
        assert int(cluster.get("n_clusters") or 0) >= 2
        assert isinstance(cluster.get("clusters"), list) and cluster.get("clusters")
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_supports_p2_external_validation():
    train_id = "test_p2_external_train"
    external_id = "test_p2_external_holdout"
    rng_train = np.random.default_rng(123)
    rng_ext = np.random.default_rng(321)

    n_train = 180
    age_t = rng_train.normal(61.0, 10.0, n_train)
    crp_t = rng_train.normal(38.0, 12.0, n_train)
    wbc_t = rng_train.normal(8.0, 1.8, n_train)
    logit_t = -8.0 + 0.06 * age_t + 0.09 * crp_t + 0.03 * wbc_t
    prob_t = 1.0 / (1.0 + np.exp(-logit_t))
    event_t = (rng_train.random(n_train) < prob_t).astype(int)

    n_ext = 120
    age_e = rng_ext.normal(63.0, 10.0, n_ext)
    crp_e = rng_ext.normal(40.0, 11.0, n_ext)
    wbc_e = rng_ext.normal(8.3, 1.9, n_ext)
    logit_e = -8.2 + 0.06 * age_e + 0.09 * crp_e + 0.03 * wbc_e
    prob_e = 1.0 / (1.0 + np.exp(-logit_e))
    event_e = (rng_ext.random(n_ext) < prob_e).astype(int)

    df_train = pd.DataFrame(
        {
            "age": age_t,
            "crp": crp_t,
            "wbc": wbc_t,
            "event": event_t,
        }
    )
    df_external = pd.DataFrame(
        {
            "age": age_e,
            "crp": crp_e,
            "wbc": wbc_e,
            "event": event_e,
        }
    )

    train_dir = _prepare_dataset(train_id, df_train, with_design_review=True)
    external_dir = _prepare_dataset(external_id, df_external, with_design_review=False)

    try:
        payload = {
            "dataset_id": train_id,
            "alpha": 0.05,
            "globals": {"analysis_mode": "exploratory"},
            "protocol": [
                {
                    "id": "p2_external",
                    "method": "external_validation",
                    "config": {
                        "outcome": "event",
                        "predictors": ["age", "crp", "wbc"],
                        "task": "classification",
                        "model_method": "logistic_regression",
                        "external_dataset_id": external_id,
                        "test_size": 0.25,
                        "random_state": 42,
                    },
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("status") in {"completed", "partial"}

        rows = body.get("results")
        assert isinstance(rows, list) and rows
        first = rows[0].get("results") if isinstance(rows[0], dict) else None
        assert isinstance(first, dict)
        _assert_v2_contract(first)
        assert first.get("method_id") == "external_validation"
        assert first.get("task") == "classification"
        assert str(first.get("external_dataset_id") or "") == external_id

        ext_metrics = first.get("external_metrics")
        assert isinstance(ext_metrics, dict)
        assert isinstance(ext_metrics.get("accuracy"), (int, float))

        cm = first.get("confusion_matrix")
        assert isinstance(cm, dict)
        values = cm.get("values")
        assert isinstance(values, list) and len(values) == 2
        assert all(isinstance(row, list) and len(row) == 2 for row in values)
    finally:
        if os.path.exists(train_dir):
            shutil.rmtree(train_dir)
        if os.path.exists(external_dir):
            shutil.rmtree(external_dir)


def test_plan_to_execute_external_validation_flow_with_preferences(monkeypatch):
    train_id = "test_p2_plan_execute_train"
    external_id = "test_p2_plan_execute_external"
    rng = np.random.default_rng(777)

    n_train = 210
    age_t = rng.normal(61.0, 9.0, n_train)
    crp_t = rng.normal(39.0, 11.0, n_train)
    wbc_t = rng.normal(8.1, 1.7, n_train)
    ferritin_t = 0.45 * crp_t + 0.35 * age_t + rng.normal(0.0, 4.5, n_train)
    group_t = np.where(rng.random(n_train) > 0.5, "A", "B")
    logit_t = -8.2 + 0.055 * age_t + 0.085 * crp_t + 0.025 * wbc_t
    prob_t = 1.0 / (1.0 + np.exp(-logit_t))
    event_t = (rng.random(n_train) < prob_t).astype(int)

    n_ext = 130
    age_e = rng.normal(63.0, 10.0, n_ext)
    crp_e = rng.normal(40.5, 10.5, n_ext)
    wbc_e = rng.normal(8.3, 1.8, n_ext)
    ferritin_e = 0.44 * crp_e + 0.36 * age_e + rng.normal(0.0, 4.0, n_ext)
    group_e = np.where(rng.random(n_ext) > 0.5, "A", "B")
    logit_e = -8.0 + 0.055 * age_e + 0.085 * crp_e + 0.025 * wbc_e
    prob_e = 1.0 / (1.0 + np.exp(-logit_e))
    event_e = (rng.random(n_ext) < prob_e).astype(int)

    df_train = pd.DataFrame(
        {
            "group": group_t,
            "age": age_t,
            "crp": crp_t,
            "wbc": wbc_t,
            "ferritin": ferritin_t,
            "event": event_t,
        }
    )
    df_external = pd.DataFrame(
        {
            "group": group_e,
            "age": age_e,
            "crp": crp_e,
            "wbc": wbc_e,
            "ferritin": ferritin_e,
            "event": event_e,
        }
    )

    train_dir = _prepare_dataset(train_id, df_train, with_design_review=True)
    external_dir = _prepare_dataset(external_id, df_external, with_design_review=False)
    _write_scan_and_design(train_id, n_rows=len(df_train))

    async def _fake_analyze_research_design(**kwargs):
        return {}

    async def _fake_critique_protocol(**kwargs):
        return {"notes": [], "issues": [], "drop_step_ids": []}

    monkeypatch.setattr(v2_api, "analyze_research_design", _fake_analyze_research_design)
    monkeypatch.setattr(v2_api, "critique_protocol", _fake_critique_protocol)

    try:
        plan_payload = {
            "dataset_id": train_id,
            "text": "Expert protocol with deep mining and external validation",
            "preferences": {
                "analysis_mode": "expert_comprehensive",
                "allow_data_mining": True,
                "external_validation_dataset_id": external_id,
            },
        }
        resp_plan = client.post("/api/v1/v2/analysis/plan", json=plan_payload)
        assert resp_plan.status_code == 200, resp_plan.text
        body_plan = resp_plan.json()

        protocol = body_plan.get("protocol")
        assert isinstance(protocol, list) and protocol
        methods = [str((s or {}).get("method") or "") for s in protocol if isinstance(s, dict)]
        assert "bootstrap_pipeline" in methods
        assert "cluster_profiles" in methods
        assert "external_validation" in methods

        ext_step = next((s for s in protocol if isinstance(s, dict) and str(s.get("method")) == "external_validation"), None)
        assert isinstance(ext_step, dict)
        ext_cfg = ext_step.get("config") if isinstance(ext_step.get("config"), dict) else {}
        assert str(ext_cfg.get("external_dataset_id") or "") == external_id

        execute_payload = {
            "dataset_id": train_id,
            "alpha": 0.05,
            "globals": {
                "analysis_mode": "discovery",
                "mode": "discovery",
                "allow_unconfirmed_design": True,
            },
            "protocol": [ext_step],
        }
        resp_exec = client.post("/api/v1/v2/analysis/execute", json=execute_payload)
        assert resp_exec.status_code == 200, resp_exec.text
        body_exec = resp_exec.json()
        assert body_exec.get("status") in {"completed", "partial"}
        rows = body_exec.get("results")
        assert isinstance(rows, list) and rows
        first = rows[0].get("results") if isinstance(rows[0], dict) else None
        assert isinstance(first, dict)
        assert first.get("method_id") == "external_validation"
        assert str(first.get("external_dataset_id") or "") == external_id
    finally:
        if os.path.exists(train_dir):
            shutil.rmtree(train_dir)
        if os.path.exists(external_dir):
            shutil.rmtree(external_dir)
