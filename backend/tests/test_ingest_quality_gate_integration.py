import json
import os
import sys
import types

import pandas as pd
import pytest

from app.api import datasets as ds
from app.core.pipeline import PipelineManager
from app.services import upload_service as us


class _FakeScanner:
    def optimize_dtypes(self, df):
        return df

    def scan_dataset(self, df):
        columns_profile = []
        for c in df.columns:
            s = df[c]
            columns_profile.append(
                {
                    "name": str(c),
                    "type": str(s.dtype),
                    "missing_count": int(s.isna().sum()),
                    "unique_count": int(s.nunique(dropna=True)),
                }
            )
        return {
            "profile": {
                "row_count": int(len(df)),
                "col_count": int(len(df.columns)),
                "columns": columns_profile,
                "head": df.head(2).to_dict(orient="records"),
                "page": 1,
                "total_pages": 1,
            },
            "scan_report": {
                "columns": {
                    str(c): {
                        "type": str(df[c].dtype),
                        "unique_count": int(df[c].nunique(dropna=True)),
                        "missing_count": int(df[c].isna().sum()),
                    }
                    for c in df.columns
                },
                "missing_report": {"total_rows": int(len(df)), "total_missing": int(df.isna().sum().sum())},
            },
        }


def _quality_gate_result_df() -> dict:
    df = pd.DataFrame(
        {
            "patient_id": [1, 2, 3],
            "group": ["A", "A", "B"],
            "value": [10.0, 11.0, 9.5],
        }
    )
    return {
        "dataframe": df,
        "header_row": 0,
        "quality_gate_applied": True,
        "quality_report": {
            "is_ready": True,
            "overall_score": 0.96,
            "issues": [],
            "warnings": [],
        },
        "cleaning_log": {
            "schema": "clinimetria.cleaning_log",
            "version": 1,
            "action": "quality_gate",
            "steps": [{"action": "remove_duplicates"}],
            "issues": [],
            "warnings": [],
        },
        "cleaning_plan": {
            "schema": "clinimetria.cleaning_plan",
            "version": 1,
            "steps": [{"step": 1, "action": "profile"}],
        },
        "data_contract": {
            "schema": "clinimetria.data_contract",
            "version": 1,
            "columns": {
                "patient_id": {"dtype": "numeric"},
                "group": {"dtype": "categorical"},
                "value": {"dtype": "numeric"},
            },
        },
        "lineage": {
            "schema": "clinimetria.data_lineage",
            "version": 1,
            "entries": [{"action": "quality_gate"}],
            "steps": [{"action": "quality_gate"}],
        },
        "structure_log": {"issues": [], "log": [{"event": "header_detected"}]},
    }


@pytest.mark.anyio
async def test_sync_ingest_uses_quality_gate_and_persists_artifacts(tmp_path, monkeypatch):
    pipeline = PipelineManager(str(tmp_path))

    async def _fake_threadpool(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(ds, "pipeline", pipeline)
    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "run_in_threadpool", _fake_threadpool)
    monkeypatch.setattr(ds, "rebuild_and_save_semantics", lambda **kwargs: {})
    monkeypatch.setattr(ds, "rebuild_and_save_study_design", lambda **kwargs: {})
    monkeypatch.setattr(ds, "append_delta_log", lambda **kwargs: None)

    monkeypatch.setitem(sys.modules, "app.modules.smart_scanner", types.SimpleNamespace(SmartScanner=_FakeScanner))
    monkeypatch.setattr(us, "_run_quality_gate_ingest", lambda *args, **kwargs: _quality_gate_result_df())
    monkeypatch.setattr(us, "_normalize_auto_impute", lambda v: "simple")
    monkeypatch.setattr(
        us,
        "_auto_clean_and_impute",
        lambda df, scan_report, *, auto_clean, auto_impute: (
            df,
            {"auto_clean": bool(auto_clean), "auto_impute": auto_impute, "actions": []},
        ),
    )

    out = await ds._ingest_dataset_bytes(b"id,val\n1,2\n", "unit.csv")
    dataset_id = out.id
    processed_dir = os.path.join(str(tmp_path), dataset_id, "processed")

    for name in ["cleaning_plan.json", "data_contract.json", "data_lineage.json", "cleaning_log.json"]:
        assert os.path.exists(os.path.join(processed_dir, name))

    with open(os.path.join(processed_dir, "cleaning_log.json"), "r", encoding="utf-8") as f:
        cleaning_log = json.load(f)
    quality_gate = cleaning_log.get("quality_gate") if isinstance(cleaning_log, dict) else {}
    assert isinstance(quality_gate, dict)
    assert bool(quality_gate.get("applied")) is True


class _FakeDataNormalizer:
    def normalize(self, df):
        return df, {"normalized": False}


class _FakeJobStore:
    def __init__(self, payload=None):
        self._jobs = {"job-1": {"id": "job-1", "payload": payload or {}, "stage": "queued", "status": "queued"}}

    def get(self, job_id):
        return dict(self._jobs[job_id])

    def update(self, job_id, **kwargs):
        self._jobs[job_id].update(kwargs)

    def complete(self, job_id, artifacts=None):
        self._jobs[job_id].update({"status": "completed", "artifacts": artifacts or {}})

    def fail(self, job_id, stage=None, error=None):
        self._jobs[job_id].update({"status": "failed", "stage": stage, "error": error})


@pytest.mark.anyio
async def test_async_ingest_saved_raw_applies_quality_gate_artifacts(tmp_path, monkeypatch):
    data_dir = str(tmp_path)
    pipeline = PipelineManager(data_dir)
    dataset_id = "ds_qg_async"
    pipeline.initialize_dataset(dataset_id)
    raw_path = os.path.join(data_dir, dataset_id, "source", "original.raw")
    with open(raw_path, "wb") as f:
        f.write(b"id,val\n1,10\n2,11\n")

    async def _fake_threadpool(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(us, "run_in_threadpool", _fake_threadpool)
    monkeypatch.setattr(us, "DataNormalizer", _FakeDataNormalizer)
    monkeypatch.setattr(us, "SmartScanner", _FakeScanner)
    monkeypatch.setattr(us, "rebuild_and_save_semantics", lambda **kwargs: {})
    monkeypatch.setattr(us, "rebuild_and_save_study_design", lambda **kwargs: {})
    monkeypatch.setattr(us, "append_delta_log", lambda **kwargs: None)
    monkeypatch.setattr(us, "_run_quality_gate_ingest", lambda *args, **kwargs: _quality_gate_result_df())

    job_store = _FakeJobStore(payload={"auto_clean": True, "auto_impute": "simple"})
    out = await us.ingest_saved_raw_to_parquet_job(
        dataset_id=dataset_id,
        raw_path=raw_path,
        original_filename="unit.csv",
        data_dir=data_dir,
        job_store=job_store,
        job_id="job-1",
    )

    assert out["status"] == "completed"
    processed_dir = os.path.join(data_dir, dataset_id, "processed")
    for name in ["cleaning_plan.json", "data_contract.json", "data_lineage.json", "cleaning_log.json"]:
        assert os.path.exists(os.path.join(processed_dir, name))

    with open(os.path.join(processed_dir, "cleaning_log.json"), "r", encoding="utf-8") as f:
        cleaning_log = json.load(f)
    quality_gate = cleaning_log.get("quality_gate") if isinstance(cleaning_log, dict) else {}
    assert isinstance(quality_gate, dict)
    assert bool(quality_gate.get("applied")) is True


def test_reparse_path_uses_quality_gate_and_persists_artifacts(tmp_path, monkeypatch):
    pipeline = PipelineManager(str(tmp_path))
    dataset_id = "ds_qg_reparse"
    pipeline.save_source(dataset_id, b"id,val\n1,10\n2,11\n", "unit.csv")

    monkeypatch.setattr(ds, "pipeline", pipeline)
    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "rebuild_and_save_semantics", lambda **kwargs: {})
    monkeypatch.setattr(ds, "rebuild_and_save_study_design", lambda **kwargs: {})
    monkeypatch.setattr(ds, "append_delta_log", lambda **kwargs: None)
    monkeypatch.setitem(sys.modules, "app.modules.smart_scanner", types.SimpleNamespace(SmartScanner=_FakeScanner))
    monkeypatch.setattr(us, "_run_quality_gate_ingest", lambda *args, **kwargs: _quality_gate_result_df())

    req = ds.DatasetReparse(header_row=0, sheet_name=None)
    profile = ds.reparse_dataset(dataset_id, req, page=1, limit=100)
    assert int(profile.row_count) == 3

    processed_dir = os.path.join(str(tmp_path), dataset_id, "processed")
    for name in ["cleaning_plan.json", "data_contract.json", "data_lineage.json", "cleaning_log.json"]:
        assert os.path.exists(os.path.join(processed_dir, name))

    with open(os.path.join(processed_dir, "cleaning_log.json"), "r", encoding="utf-8") as f:
        cleaning_log = json.load(f)
    quality_gate = cleaning_log.get("quality_gate") if isinstance(cleaning_log, dict) else {}
    assert isinstance(quality_gate, dict)
    assert bool(quality_gate.get("applied")) is True
