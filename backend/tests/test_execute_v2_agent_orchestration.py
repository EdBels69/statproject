import json
import os
import shutil
import sys

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.datasets import DATA_DIR
import app.api.v2 as v2_api
from app.main import app


client = TestClient(app)


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed_dir = os.path.join(ds_dir, "processed")
    source_dir = os.path.join(ds_dir, "source")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)

    rng = np.random.default_rng(13)
    rows = []
    for i in range(64):
        group = "A" if i < 32 else "B"
        rows.append(
            {
                "group": group,
                "cov1": float(rng.normal(45.0, 7.0)),
                "outcome": float(8.0 + (0.8 if group == "B" else 0.0) + rng.normal(0.0, 0.7)),
            }
        )
    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(processed_dir, f"{dataset_id}.parquet"), index=False)

    with open(os.path.join(source_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "execute_v2_orchestrator.csv"}, f)
    with open(os.path.join(source_dir, "original.raw"), "wb") as f:
        f.write(b"group,cov1,outcome\nA,1,2\n")

    with open(os.path.join(processed_dir, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-23T12:00:00Z",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )

    return ds_dir


def test_execute_v2_agent_orchestration_happy_path():
    dataset_id = "test_exec_v2_orchestrator_ok"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "agent_orchestrator_enabled": True,
                "agent_orchestrator_max_rounds": 12,
            },
            "protocol": [
                {
                    "id": "s1",
                    "method": "ancova",
                    "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1"]},
                }
            ],
        }

        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert not data.get("errors"), data

        orchestration = data.get("agent_orchestration")
        assert isinstance(orchestration, dict), data
        assert orchestration.get("enabled") is True
        assert orchestration.get("status") == "completed"
        assert orchestration.get("state") == "release"

        events = orchestration.get("events")
        assert isinstance(events, list) and events, orchestration
        roles = {str(item.get("role")) for item in events if isinstance(item, dict)}
        assert {"planner", "executor", "verifier", "reporter"}.issubset(roles)

        transitions = orchestration.get("transitions")
        assert isinstance(transitions, list) and transitions, orchestration
        transition_pairs = {(str(item.get("from")), str(item.get("to"))) for item in transitions if isinstance(item, dict)}
        assert ("compile", "execute") in transition_pairs
        assert ("execute", "verify") in transition_pairs
        assert ("verify", "report") in transition_pairs
        assert ("report", "release") in transition_pairs
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_v2_agent_orchestration_verifier_gate_retry(monkeypatch):
    dataset_id = "test_exec_v2_orchestrator_verify_fail"
    ds_dir = _prepare_dataset(dataset_id)

    def _forced_verify_fail(_payload, alpha=0.05):
        return {
            "schema": "clinimetria.verification",
            "status": "failed",
            "alpha": float(alpha),
            "checks": [{"id": "forced_fail", "status": "failed"}],
            "summary": {"failed": 1},
        }

    monkeypatch.setattr(v2_api, "verify_run_payload", _forced_verify_fail)

    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "agent_orchestrator_enabled": True,
            },
            "protocol": [
                {
                    "id": "s1",
                    "method": "ancova",
                    "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1"]},
                }
            ],
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") == "partial"

        run_state = data.get("run_state")
        assert isinstance(run_state, dict), data
        assert run_state.get("state") == "verify"
        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        assert reproducibility.get("ready") is False
        assert any(
            "Verifier gate failed" in str(err)
            for err in (reproducibility.get("errors") if isinstance(reproducibility.get("errors"), list) else [])
        )

        orchestration = data.get("agent_orchestration")
        assert isinstance(orchestration, dict), data
        assert orchestration.get("state") == "verify"
        assert orchestration.get("status") == "incomplete"

        events = orchestration.get("events")
        assert isinstance(events, list) and events, orchestration
        last_event = events[-1] if events else {}
        assert last_event.get("role") == "verifier"
        assert last_event.get("action") == "retry"
        assert "verification_failed" in str(last_event.get("reason") or "")
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_v2_agent_orchestration_reflection_reject_loop_to_release(monkeypatch):
    dataset_id = "test_exec_v2_orchestrator_reflection_ok"
    ds_dir = _prepare_dataset(dataset_id)
    calls = {"n": 0}

    def _verify_fail_then_pass(_payload, alpha=0.05):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "schema": "clinimetria.verification",
                "status": "failed",
                "alpha": float(alpha),
                "checks": [{"check": "multiplicity_trace_method", "step_id": "s1", "method": "legacy"}],
                "failures": [
                    {
                        "check": "multiplicity_trace_method",
                        "step_id": "s1",
                        "message": "Unsupported multiplicity method in trace: legacy",
                    }
                ],
                "warnings": [],
                "summary": {"checks_total": 1, "failed": 1, "warnings": 0},
            }
        return {
            "schema": "clinimetria.verification",
            "status": "passed",
            "alpha": float(alpha),
            "checks": [{"check": "multiplicity_trace_method", "step_id": "s1", "method": "fdr_bh"}],
            "failures": [],
            "warnings": [],
            "summary": {"checks_total": 1, "failed": 0, "warnings": 0},
        }

    monkeypatch.setattr(v2_api, "verify_run_payload", _verify_fail_then_pass)

    try:
        payload = {
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "globals": {
                "design_confirmed": True,
                "agent_orchestrator_enabled": True,
                "agent_reflection_enabled": True,
                "agent_reflection_max_rounds": 2,
                "multiplicity_correction": "fdr_bh",
            },
            "protocol": [
                {
                    "id": "s1",
                    "method": "ancova",
                    "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1"]},
                }
            ],
        }
        response = client.post("/api/v1/v2/analysis/execute", json=payload)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data.get("status") == "completed", data
        assert calls["n"] >= 2

        orchestration = data.get("agent_orchestration")
        assert isinstance(orchestration, dict), data
        assert orchestration.get("state") == "release"
        assert orchestration.get("status") == "completed"

        events = orchestration.get("events")
        assert isinstance(events, list) and events, orchestration
        assert any(
            isinstance(ev, dict)
            and ev.get("action") == "reject"
            and ev.get("target_state") == "compile"
            for ev in events
        ), events

        transitions = orchestration.get("transitions")
        transition_pairs = {(str(item.get("from")), str(item.get("to"))) for item in transitions if isinstance(item, dict)}
        assert ("verify", "compile") in transition_pairs
        assert ("compile", "execute") in transition_pairs
        assert ("execute", "verify") in transition_pairs
        assert ("verify", "report") in transition_pairs

        reflection_rounds = orchestration.get("reflection_rounds")
        assert isinstance(reflection_rounds, list) and len(reflection_rounds) >= 2
        assert any(
            isinstance(item, dict)
            and item.get("stage") == "reflection_retry"
            and item.get("action") == "repair_applied"
            for item in reflection_rounds
        ), reflection_rounds

        run_id = str(data.get("run_id") or "")
        assert run_id
        reflection_path = os.path.join(ds_dir, "analysis", run_id, "artifacts", "reflection_log.json")
        assert os.path.exists(reflection_path)
        with open(reflection_path, "r", encoding="utf-8") as f:
            reflection_doc = json.load(f)
        assert reflection_doc.get("final_verification_status") == "passed"
        assert isinstance(reflection_doc.get("rounds"), list) and len(reflection_doc["rounds"]) >= 2
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
