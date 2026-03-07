import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api import datasets as ds


class _DummyPipeline:
    def __init__(self, root: str):
        self.root = root

    def _dataset_dir(self, dataset_id: str) -> str:
        return os.path.join(self.root, dataset_id)

    def save_source(self, dataset_id: str, file_content: bytes, filename: str):
        src_dir = os.path.join(self._dataset_dir(dataset_id), "source")
        os.makedirs(src_dir, exist_ok=True)
        path = os.path.join(src_dir, "original.raw")
        with open(path, "wb") as f:
            f.write(file_content)
        return path

    def create_processed_snapshot(self, dataset_id: str, df, cleaning_log=None):
        processed = os.path.join(self._dataset_dir(dataset_id), "processed")
        os.makedirs(processed, exist_ok=True)
        out = os.path.join(processed, f"{dataset_id}.parquet")
        df.to_parquet(out, engine="pyarrow", index=False)
        if cleaning_log is not None:
            self.write_json_atomic(os.path.join(processed, "cleaning_log.json"), cleaning_log, allow_nan=False)

    def get_dataset_dir(self, dataset_id: str) -> str:
        ds_dir = self._dataset_dir(dataset_id)
        os.makedirs(os.path.join(ds_dir, "processed"), exist_ok=True)
        return ds_dir

    def write_json_atomic(self, path: str, payload, allow_nan: bool = False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)


@pytest.mark.anyio
async def test_ingest_rebuilds_study_design_once(tmp_path, monkeypatch):
    dummy_pipeline = _DummyPipeline(str(tmp_path))
    calls = {"semantics": 0, "design": 0, "delta": 0}

    async def _fake_threadpool(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    def _fake_parse_file(raw_path, header_row=0, original_filename=None):
        import pandas as pd

        df = pd.DataFrame(
            {
                "patient_id": [1, 2, 3],
                "group": ["A", "A", "B"],
                "value": [10.0, 11.5, 8.8],
            }
        )
        return df, 0

    class _FakeScanner:
        def optimize_dtypes(self, df):
            return df

        def scan_dataset(self, df):
            return {
                "profile": {
                    "row_count": int(len(df.index)),
                    "col_count": int(len(df.columns)),
                    "columns": [
                        {"name": "patient_id", "type": "numeric", "missing_count": 0, "unique_count": 3},
                        {"name": "group", "type": "categorical", "missing_count": 0, "unique_count": 2},
                        {"name": "value", "type": "numeric", "missing_count": 0, "unique_count": 3},
                    ],
                    "head": [
                        {"patient_id": 1, "group": "A", "value": 10.0},
                        {"patient_id": 2, "group": "A", "value": 11.5},
                    ],
                    "page": 1,
                    "total_pages": 1,
                },
                "scan_report": {
                    "columns": {
                        "patient_id": {"type": "int64", "unique_count": 3, "missing_count": 0},
                        "group": {"type": "object", "unique_count": 2, "missing_count": 0},
                        "value": {"type": "float64", "unique_count": 3, "missing_count": 0},
                    },
                    "missing_report": {"total_rows": int(len(df.index))},
                },
            }

    def _fake_normalize_auto_impute(value):
        return "simple"

    def _fake_auto_clean_and_impute(df, scan_report, *, auto_clean, auto_impute):
        return df, {"auto_clean": bool(auto_clean), "auto_impute": auto_impute, "actions": []}

    def _fake_rebuild_semantics(**kwargs):
        calls["semantics"] += 1
        return {}

    def _fake_rebuild_study_design(**kwargs):
        calls["design"] += 1
        return {}

    def _fake_delta_log(**kwargs):
        calls["delta"] += 1

    monkeypatch.setattr(ds, "pipeline", dummy_pipeline)
    monkeypatch.setattr(ds, "run_in_threadpool", _fake_threadpool)
    monkeypatch.setattr(ds, "parse_file", _fake_parse_file)
    monkeypatch.setattr(ds, "rebuild_and_save_semantics", _fake_rebuild_semantics)
    monkeypatch.setattr(ds, "rebuild_and_save_study_design", _fake_rebuild_study_design)
    monkeypatch.setattr(ds, "append_delta_log", _fake_delta_log)

    monkeypatch.setitem(sys.modules, "app.modules.smart_scanner", types.SimpleNamespace(SmartScanner=_FakeScanner))
    monkeypatch.setitem(
        sys.modules,
        "app.services.upload_service",
        types.SimpleNamespace(
            _normalize_auto_impute=_fake_normalize_auto_impute,
            _auto_clean_and_impute=_fake_auto_clean_and_impute,
        ),
    )

    out = await ds._ingest_dataset_bytes(b"a,b\n1,2\n", "unit.csv")
    assert out.id
    assert calls["semantics"] == 1
    assert calls["design"] == 1
    assert calls["delta"] == 1
