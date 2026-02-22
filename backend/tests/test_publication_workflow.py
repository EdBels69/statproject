import json
import os
import sys

import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api import datasets as ds
from app.api import v2 as v2_api
from app.core.pipeline import PipelineManager
from app.modules.cleaning_run import build_cleaning_run_artifact


client = TestClient(app)


def _write_parquet_dataset(base_dir: str, dataset_id: str, df: pd.DataFrame, *, with_cleaning_log: bool = True) -> None:
    ds_root = os.path.join(base_dir, dataset_id)
    os.makedirs(os.path.join(ds_root, "processed"), exist_ok=True)
    os.makedirs(os.path.join(ds_root, "source"), exist_ok=True)
    os.makedirs(os.path.join(ds_root, "analysis"), exist_ok=True)
    df.to_parquet(os.path.join(ds_root, "processed", f"{dataset_id}.parquet"))
    if with_cleaning_log:
        cleaning_log = {"action": "ingest", "auto": {"auto_clean": True, "auto_impute": "simple", "actions": []}}
        with open(os.path.join(ds_root, "processed", "cleaning_log.json"), "w", encoding="utf-8") as f:
            json.dump(cleaning_log, f)
        artifact = build_cleaning_run_artifact(
            dataset_id=dataset_id,
            cleaning_log=cleaning_log,
            df_before=None,
            df_after=df,
            actor="qa-user",
            source="test",
        )
        with open(os.path.join(ds_root, "processed", "cleaning_run.json"), "w", encoding="utf-8") as f:
            json.dump(artifact, f)
    with open(os.path.join(ds_root, "source", "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "publication_test.xlsx", "header_row": 0}, f)


def test_publication_plan_freeze_execute_roundtrip(tmp_path, monkeypatch):
    dataset_id = "publication_workflow_ds"
    df = pd.DataFrame(
        {
            "group": ["A", "A", "A", "B", "B", "B", "A", "B"],
            "outcome": [10.2, 11.1, 9.8, 14.0, 13.5, 12.9, 10.9, 13.8],
            "marker": [1.0, 1.1, 1.2, 2.0, 2.1, 1.9, 1.3, 2.2],
        }
    )
    _write_parquet_dataset(str(tmp_path), dataset_id, df)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))
    monkeypatch.setattr(v2_api, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(v2_api, "pipeline", PipelineManager(str(tmp_path)))
    monkeypatch.setattr(v2_api.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    async def _fake_analyze_research_design(**kwargs):
        return {
            "protocol_name": "Publication plan",
            "protocol": [
                {
                    "id": "pub_step_1",
                    "method": "t_test_ind",
                    "config": {"outcome": "outcome", "group": "group"},
                }
            ],
            "globals": {},
            "notes": [],
        }

    async def _fake_critique_protocol(**kwargs):
        return None

    monkeypatch.setattr(v2_api, "analyze_research_design", _fake_analyze_research_design)
    monkeypatch.setattr(v2_api, "critique_protocol", _fake_critique_protocol)

    plan_res = client.post(
        "/api/v1/v2/analysis/plan",
        json={
            "dataset_id": dataset_id,
            "text": "Сформируй publication protocol",
            "protocol": [],
            "preferences": {
                "analysis_mode": "publication",
                "design_confirmed": True,
                "use_critic": False,
            },
        },
    )
    assert plan_res.status_code == 200, plan_res.text
    plan_payload = plan_res.json()
    assert plan_payload.get("status") in {"completed", "partial"}
    assert plan_payload.get("analysis_mode") == "publication"
    assert isinstance(plan_payload.get("cleaning_plan"), dict)
    assert isinstance(plan_payload.get("cohort_plan"), dict)
    assert isinstance(plan_payload.get("report_spec"), dict)
    assert plan_payload.get("cohort_plan", {}).get("required") is True

    design_confirm_res = client.post(
        f"/api/v1/datasets/{dataset_id}/design_review/confirm",
        json={"actor": "qa-user", "source": "publication-test"},
    )
    assert design_confirm_res.status_code == 200, design_confirm_res.text
    assert design_confirm_res.json().get("confirmed") is True

    cohort_plan = plan_payload.get("cohort_plan") if isinstance(plan_payload.get("cohort_plan"), dict) else {}
    freeze_res = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "publication-test",
            "mode": cohort_plan.get("mode") or "complete_case",
            "enforce": cohort_plan.get("enforce") or "models",
            "required_non_missing": cohort_plan.get("required_non_missing") or ["outcome", "group"],
            "impute_columns": cohort_plan.get("impute_columns") or [],
        },
    )
    assert freeze_res.status_code == 200, freeze_res.text
    analysis_set_id = str(freeze_res.json().get("analysis_set_id") or "")
    assert analysis_set_id

    execute_res = client.post(
        "/api/v1/v2/analysis/execute",
        json={
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": plan_payload.get("protocol") or [],
            "globals": {
                "analysis_mode": "publication",
                "analysis_set_id": analysis_set_id,
                "analysis_set_strict": True,
            },
        },
    )
    assert execute_res.status_code == 200, execute_res.text
    execute_payload = execute_res.json()
    assert execute_payload.get("status") in {"completed", "partial"}
    assert execute_payload.get("publication_mode") is True
    assert execute_payload.get("analysis_mode") == "publication"
    assert execute_payload.get("design_review_confirmed") is True
    assert execute_payload.get("analysis_set", {}).get("analysis_set_id") == analysis_set_id
    assert execute_payload.get("cleaning_artifact", {}).get("valid") is True
    assert execute_payload.get("cleaning_artifact", {}).get("artifact_kind") == "cleaning_run"
    items = execute_payload.get("results") if isinstance(execute_payload.get("results"), list) else []
    assert items
    first_payload = items[0].get("results") if isinstance(items[0], dict) else None
    contract = first_payload.get("interpretation_contract") if isinstance(first_payload, dict) else None
    assert isinstance(contract, dict)
    for key in ["claim", "evidence", "clinical_meaning", "limitations", "actionable_next_step"]:
        assert isinstance(contract.get(key), str)
        assert contract.get(key).strip()


def test_publication_execute_requires_cleaning_artifact(tmp_path, monkeypatch):
    dataset_id = "publication_workflow_no_cleaning"
    df = pd.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "outcome": [1.0, 1.2, 2.1, 2.3],
            "marker": [0.4, 0.5, 0.7, 0.8],
        }
    )
    _write_parquet_dataset(str(tmp_path), dataset_id, df, with_cleaning_log=False)

    monkeypatch.setattr(ds, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ds, "pipeline", PipelineManager(str(tmp_path)))
    monkeypatch.setattr(v2_api, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(v2_api, "pipeline", PipelineManager(str(tmp_path)))
    monkeypatch.setattr(v2_api.settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)

    confirm_res = client.post(
        f"/api/v1/datasets/{dataset_id}/design_review/confirm",
        json={"actor": "qa-user", "source": "publication-test"},
    )
    assert confirm_res.status_code == 200, confirm_res.text

    freeze_res = client.post(
        f"/api/v1/datasets/{dataset_id}/analysis_set/freeze",
        json={
            "actor": "qa-user",
            "source": "publication-test",
            "mode": "complete_case",
            "enforce": "models",
            "required_non_missing": ["group", "outcome", "marker"],
            "impute_columns": [],
        },
    )
    assert freeze_res.status_code == 200, freeze_res.text
    analysis_set_id = str(freeze_res.json().get("analysis_set_id") or "")
    assert analysis_set_id

    execute_res = client.post(
        "/api/v1/v2/analysis/execute",
        json={
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": [
                {"id": "step_1", "method": "t_test_ind", "config": {"outcome": "outcome", "group": "group"}}
            ],
            "globals": {
                "analysis_mode": "publication",
                "analysis_set_id": analysis_set_id,
                "analysis_set_strict": True,
            },
        },
    )
    assert execute_res.status_code == 400, execute_res.text
    assert "cleaning_run artifact" in execute_res.text.lower()
