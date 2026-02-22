import json
import os
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import datasets as ds
from app.core.pipeline import PipelineManager


client = TestClient(app)


def _write_parquet_dataset(base_dir: str, dataset_id: str, df: pd.DataFrame) -> None:
    ds_root = os.path.join(base_dir, dataset_id)
    os.makedirs(os.path.join(ds_root, "processed"), exist_ok=True)
    os.makedirs(os.path.join(ds_root, "source"), exist_ok=True)
    os.makedirs(os.path.join(ds_root, "analysis"), exist_ok=True)
    df.to_parquet(os.path.join(ds_root, "processed", f"{dataset_id}.parquet"))
    with open(os.path.join(ds_root, "source", "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "test.xlsx", "header_row": 0, "locked": True}, f)


def test_interactive_cleaning_apply_saves_single_artifact_and_updates_profile(tmp_path, monkeypatch):
    dataset_id = "interactive_cleaning_apply_ds"
    df = pd.DataFrame(
        {
            "num": [1.0, None, 3.0, 5.0],
            "cat": ["A", "na", None, "A"],
            "mostly_empty": [None, None, None, "x"],
        }
    )
    _write_parquet_dataset(str(tmp_path), dataset_id, df)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/prepare/cleaning/interactive/apply?page=1&limit=100",
        json={
            "actor": "qa-user",
            "source": "frontend-test",
            "operations": [
                {"operation_id": "op_1", "column": "cat", "action": "normalize_missing_tokens", "enabled": True},
                {"operation_id": "op_2", "column": "num", "action": "fill_median", "enabled": True},
                {"operation_id": "op_3", "column": "cat", "action": "fill_mode", "enabled": True},
                {"operation_id": "op_4", "column": "mostly_empty", "action": "drop_col", "enabled": True},
            ],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("dataset_id") == dataset_id
    assert int(payload.get("applied_count") or 0) == 4
    assert int(payload.get("skipped_count") or 0) == 0

    profile = payload.get("profile") if isinstance(payload, dict) else {}
    column_names = [str(c.get("name")) for c in (profile.get("columns") or []) if isinstance(c, dict)]
    assert "mostly_empty" not in column_names
    assert "num" in column_names and "cat" in column_names

    cleaned_path = os.path.join(str(tmp_path), dataset_id, "processed", f"{dataset_id}.parquet")
    cleaned_df = pd.read_parquet(cleaned_path)
    assert "mostly_empty" not in cleaned_df.columns
    assert int(cleaned_df["num"].isna().sum()) == 0
    assert int(cleaned_df["cat"].isna().sum()) == 0
    assert "na" not in {str(v).strip().lower() for v in cleaned_df["cat"].tolist()}

    artifact_path = os.path.join(str(tmp_path), dataset_id, "processed", "cleaning_run.json")
    assert os.path.exists(artifact_path)
    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    assert artifact.get("artifact_type") == "cleaning_run"
    assert int(artifact.get("operation_count") or 0) == 4
    operation_types = [str(op.get("type")) for op in (artifact.get("operations") or []) if isinstance(op, dict)]
    assert operation_types == ["normalize_missing_tokens", "fill_median", "fill_mode", "drop_col"]


def test_interactive_cleaning_apply_rejects_unknown_action(tmp_path, monkeypatch):
    dataset_id = "interactive_cleaning_invalid_ds"
    df = pd.DataFrame({"num": [1.0, None, 3.0]})
    _write_parquet_dataset(str(tmp_path), dataset_id, df)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/prepare/cleaning/interactive/apply",
        json={
            "operations": [
                {"operation_id": "op_bad", "column": "num", "action": "unknown_action", "enabled": True},
            ]
        },
    )
    assert response.status_code == 400
    assert "неподдерживаемое действие" in response.text.lower()


def test_interactive_cleaning_apply_requires_prepare_dataset(tmp_path, monkeypatch):
    dataset_id = "interactive_cleaning_not_prepare_ds"
    df = pd.DataFrame({"num": [1.0, None, 3.0]})
    _write_parquet_dataset(str(tmp_path), dataset_id, df)

    meta_path = os.path.join(str(tmp_path), dataset_id, "source", "meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"original_filename": "test.xlsx", "header_row": 0, "locked": False}, f)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))

    response = client.post(
        f"/api/v1/datasets/{dataset_id}/prepare/cleaning/interactive/apply",
        json={
            "operations": [
                {"operation_id": "op_1", "column": "num", "action": "fill_median", "enabled": True},
            ]
        },
    )
    assert response.status_code == 400
    assert "только для подготовленного датасета" in response.text.lower()
