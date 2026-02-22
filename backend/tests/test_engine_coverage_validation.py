import json
import os
import shutil
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.stats.method_coverage import is_engine_supported, normalize_engine_name, supported_engines


client = TestClient(app)


def test_method_coverage_helpers():
    assert normalize_engine_name("r_engine") == "r"
    assert normalize_engine_name("python3") == "python"
    assert is_engine_supported("mixed_effects", "python") is True
    assert is_engine_supported("mixed_effects", "r") is True
    assert "python" in supported_engines("mixed_effects")
    assert "r" in supported_engines("mixed_effects")
    assert is_engine_supported("clustered_correlation", "r") is True
    assert is_engine_supported("responders", "python") is True
    assert is_engine_supported("responders", "r") is True
    assert is_engine_supported("bootstrap_pipeline", "python") is True
    assert is_engine_supported("cluster_profiles", "python") is True
    assert is_engine_supported("external_validation", "python") is True
    assert is_engine_supported("bootstrap_pipeline", "r") is False
    assert is_engine_supported("cluster_profiles", "r") is False
    assert is_engine_supported("external_validation", "r") is False


def test_execute_protocol_allows_mixed_effects_with_r_engine():
    dataset_id = "test_engine_coverage_mixed_effects_r"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        rows = []
        for sid in range(1, 13):
            grp = "A" if sid <= 6 else "B"
            for t in [1, 2, 3]:
                baseline = 10.0 if grp == "A" else 11.0
                trend = 0.7 * t
                interaction = 0.8 * t if grp == "B" else 0.0
                rows.append(
                    {
                        "outcome": baseline + trend + interaction + (0.1 * sid),
                        "time": t,
                        "group": grp,
                        "subject": f"s{sid:02d}",
                    }
                )
        df = pd.DataFrame(
            rows
        )
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "mixed_effects.csv"}, f)
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
                    "id": "m1",
                    "method": "mixed_effects",
                    "config": {
                        "outcome": "outcome",
                        "time": "time",
                        "group": "group",
                        "subject": "subject",
                        "engine": "r",
                    },
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") in {"completed", "partial"}
        assert isinstance(data.get("results"), list) and data["results"]
        step = data["results"][0]
        payload_out = step.get("results") if isinstance(step, dict) else None
        assert isinstance(payload_out, dict), data
        assert payload_out.get("method_id") == "mixed_effects"
        assert str(payload_out.get("engine") or "").strip().lower() == "r"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_allows_clustered_correlation_with_r_engine():
    dataset_id = "test_engine_coverage_clustered_correlation_r"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        df = pd.DataFrame(
            {
                "outcome": [1.0, 2.0, 3.0, 2.5, 4.0, 3.7],
                "time": [1, 2, 1, 2, 3, 3],
                "group": ["A", "A", "B", "B", "A", "B"],
                "time_group": ["T1", "T2", "T1", "T2", "T3", "T3"],
            }
        )
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "clustered_correlation.csv"}, f)
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-08T12:00:00",
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
                    "id": "m1",
                    "method": "clustered_correlation",
                    "config": {
                        "variables": ["outcome", "time", "time_group"],
                        "method": "pearson",
                        "linkage_method": "average",
                        "n_clusters": 2,
                        "show_p_values": True,
                        "engine": "r",
                    },
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") in {"completed", "partial"}
        assert isinstance(data.get("results"), list) and data["results"]

        step = data["results"][0]
        payload_out = step.get("results") if isinstance(step, dict) else None
        assert isinstance(payload_out, dict), data
        assert payload_out.get("method_id") == "clustered_correlation"
        assert str(payload_out.get("engine") or "").strip().lower() == "r"
        assert payload_out.get("significant") in {True, False, None}
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_allows_anova_twoway_with_r_engine():
    dataset_id = "test_engine_coverage_anova_twoway_r"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        df = pd.DataFrame(
            {
                "outcome": [8.0, 9.1, 10.3, 11.2, 10.7, 12.1, 13.2, 14.0],
                "group": ["A", "A", "A", "A", "B", "B", "B", "B"],
                "time_group": ["T1", "T1", "T2", "T2", "T1", "T1", "T2", "T2"],
            }
        )
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "anova_twoway.csv"}, f)
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-08T12:30:00",
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
                    "id": "m1",
                    "method": "anova_twoway",
                    "config": {"outcome": "outcome", "group1": "group", "group2": "time_group", "engine": "r"},
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") in {"completed", "partial"}
        assert isinstance(data.get("results"), list) and data["results"]

        step = data["results"][0]
        payload_out = step.get("results") if isinstance(step, dict) else None
        assert isinstance(payload_out, dict), data
        assert payload_out.get("method_id") == "anova_twoway"
        assert str(payload_out.get("engine") or "").strip().lower() == "r"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_allows_responders_with_python_engine():
    dataset_id = "test_engine_coverage_responders_python"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        rows = []
        for sid in range(1, 13):
            grp = "A" if sid <= 6 else "B"
            base = 10.0 + (0.2 * sid)
            v2 = base - (1.6 if grp == "B" else 0.4)
            v3 = base - (2.2 if grp == "B" else 0.7)
            rows.append({"subject": f"s{sid:02d}", "group": grp, "v1": base, "v2": v2, "v3": v3})
        df = pd.DataFrame(rows)
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "responders.csv"}, f)
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-08T17:00:00",
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
                    "id": "r1",
                    "method": "responders",
                    "config": {
                        "outcome_columns": ["v1", "v2", "v3"],
                        "time_labels": ["baseline", "week2", "week4"],
                        "group": "group",
                        "subject": "subject",
                        "threshold": 1.0,
                        "direction": "decrease",
                        "engine": "python",
                    },
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") in {"completed", "partial"}
        assert isinstance(data.get("results"), list) and data["results"]
        step = data["results"][0]
        payload_out = step.get("results") if isinstance(step, dict) else None
        assert isinstance(payload_out, dict), data
        assert payload_out.get("method_id") == "responders"
        assert str(payload_out.get("engine") or "").strip().lower() == "python"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_allows_responders_with_r_engine():
    dataset_id = "test_engine_coverage_responders_r"
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    try:
        df = pd.DataFrame(
            {
                "subject": ["s1", "s2", "s3", "s4"],
                "group": ["A", "A", "B", "B"],
                "v1": [10.0, 11.0, 10.5, 11.2],
                "v2": [9.5, 10.4, 8.7, 9.4],
            }
        )
        df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
        with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
            json.dump({"original_filename": "responders_r.csv"}, f)
        with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "confirmed": True,
                    "confirmed_at": "2026-02-08T17:15:00",
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
                    "id": "r1",
                    "method": "responders",
                    "config": {
                        "outcome_columns": ["v1", "v2"],
                        "group": "group",
                        "subject": "subject",
                        "threshold": 0.5,
                        "direction": "decrease",
                        "engine": "r",
                    },
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") in {"completed", "partial"}
        assert isinstance(data.get("results"), list) and data["results"]
        step = data["results"][0]
        payload_out = step.get("results") if isinstance(step, dict) else None
        assert isinstance(payload_out, dict), data
        assert payload_out.get("method_id") == "responders"
        assert str(payload_out.get("engine") or "").strip().lower() == "r"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
