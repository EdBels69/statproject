import json
import os
import shutil
import sys
import warnings

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.stats.engine import run_analysis


client = TestClient(app)


def _build_advanced_df(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    subjects = [f"s{i:02d}" for i in range(1, 31)]
    for subject in subjects:
        sid = int(subject[1:])
        group = "A" if sid <= 15 else "B"
        base = 10.0 + (0.0 if group == "A" else 1.0) + rng.normal(0.0, 0.5)
        item_latent = base + rng.normal(0.0, 0.4)
        before = int(base + rng.normal(0.0, 0.4) > 10.7)
        after = int(base + rng.normal(0.0, 0.4) > 10.5)
        cq1 = int(base + rng.normal(0.0, 0.4) > 10.2)
        cq2 = int(base + rng.normal(0.0, 0.4) > 10.5)
        cq3 = int(base + rng.normal(0.0, 0.4) > 10.8)
        rater_a = "pos" if base + rng.normal(0.0, 0.4) > 10.7 else "neg"
        rater_b = "pos" if base + rng.normal(0.0, 0.4) > 10.9 else "neg"
        method_1 = base + rng.normal(0.0, 0.2)
        method_2 = base + rng.normal(0.0, 0.2)

        for rater_col in ("R1", "R2"):
            rating = base + (0.2 if rater_col == "R2" else 0.0) + rng.normal(0.0, 0.25)
            baseline_a = base + rng.normal(0.0, 0.3)
            follow_a = baseline_a + (0.3 if group == "A" else 0.9) + rng.normal(0.0, 0.2)
            baseline_b = base * 0.7 + rng.normal(0.0, 0.3)
            follow_b = baseline_b + (0.2 if group == "A" else 0.8) + rng.normal(0.0, 0.2)

            rows.append(
                {
                    "subject": subject,
                    "rater_col": rater_col,
                    "visit": "v1" if rater_col == "R1" else "v2",
                    "group": group,
                    "outcome": base + rng.normal(0.0, 0.4),
                    "cov1": rng.normal(50.0, 8.0),
                    "cov2": rng.normal(100.0, 12.0),
                    "item1": item_latent + rng.normal(0.0, 0.2),
                    "item2": item_latent + rng.normal(0.0, 0.2),
                    "item3": item_latent + rng.normal(0.0, 0.2),
                    "method_1": method_1 + rng.normal(0.0, 0.1),
                    "method_2": method_2 + rng.normal(0.0, 0.1),
                    "rating": rating,
                    "rater_a": rater_a,
                    "rater_b": rater_b,
                    "before": before,
                    "after": after,
                    "cq1": cq1,
                    "cq2": cq2,
                    "cq3": cq3,
                    "group_bin": "yes" if group == "B" else "no",
                    "num_x": base + rng.normal(0.0, 0.5),
                    "num_y": base * 0.8 + rng.normal(0.0, 0.5),
                    "baseline_a": baseline_a,
                    "follow_a": follow_a,
                    "baseline_b": baseline_b,
                    "follow_b": follow_b,
                }
            )
    return pd.DataFrame(rows)


def _prepare_dataset(dataset_id: str) -> str:
    ds_dir = os.path.join(DATA_DIR, dataset_id)
    processed = os.path.join(ds_dir, "processed")
    source = os.path.join(ds_dir, "source")
    os.makedirs(processed, exist_ok=True)
    os.makedirs(source, exist_ok=True)

    df = _build_advanced_df()
    df.to_parquet(os.path.join(processed, f"{dataset_id}.parquet"))
    with open(os.path.join(source, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"original_filename": "advanced_v2.csv"}, f)
    with open(os.path.join(processed, "design_review.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "confirmed": True,
                "confirmed_at": "2026-02-23T12:00:00",
                "confirmed_by": "test",
                "confirmed_source": "test",
            },
            f,
        )
    return ds_dir


def _execute(dataset_id: str, protocol, globals_extra=None):
    globals_payload = {"design_confirmed": True}
    if isinstance(globals_extra, dict) and globals_extra:
        globals_payload.update(globals_extra)
    payload = {
        "dataset_id": dataset_id,
        "alpha": 0.05,
        "globals": globals_payload,
        "protocol": protocol,
    }
    response = client.post("/api/v1/v2/analysis/execute", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data.get("status") in {"completed", "partial"}
    return data


@pytest.mark.parametrize(
    "method,config",
    [
        ("ancova", {"outcome": "outcome", "group": "group", "covariates": ["cov1", "cov2"]}),
        ("pca", {"variables": ["item1", "item2", "item3"], "n_components": 2}),
        ("efa", {"variables": ["item1", "item2", "item3"], "n_factors": 2}),
        ("kmeans", {"variables": ["item1", "item2", "item3"], "n_clusters": 3}),
        ("hierarchical_clustering", {"variables": ["item1", "item2", "item3"], "n_clusters": 3}),
        ("shapiro_wilk", {"outcome": "outcome"}),
        ("bland_altman", {"method_1": "method_1", "method_2": "method_2"}),
        ("icc", {"outcome": "rating", "subject_col": "subject", "rater_col": "rater_col"}),
        ("cohens_kappa", {"outcome": "rater_a", "group": "rater_b"}),
        ("mcnemar", {"outcome": "before", "group": "after"}),
        ("cochran_q", {"outcome_cols": ["cq1", "cq2", "cq3"]}),
        ("point_biserial", {"outcome": "outcome", "group": "group_bin"}),
        ("partial_correlation", {"outcome": "num_x", "group": "num_y", "covariates": ["cov1", "cov2"]}),
        ("cronbach_alpha", {"variables": ["item1", "item2", "item3"]}),
        ("bayes_t_test_one", {"outcome": "outcome", "test_value": 0}),
        ("bayes_t_test_ind", {"outcome": "outcome", "group": "group"}),
        ("bayes_t_test_rel", {"outcome": "outcome", "group": "visit"}),
        ("bayes_correlation", {"outcome": "num_x", "group": "num_y", "correlation_method": "pearson"}),
        ("bayes_anova", {"outcome": "outcome", "group": "group"}),
        ("bayes_linear_regression", {"outcome": "outcome", "predictors": ["cov1", "cov2"]}),
        ("bayes_chi_square", {"outcome": "rater_a", "group": "rater_b"}),
        ("time_series_analysis", {"outcome": "outcome", "time": "cov1", "forecast_horizon": 6, "ljung_lags": 4}),
    ],
)
def test_execute_protocol_advanced_methods_are_wired(method, config):
    dataset_id = f"test_exec_v2_adv_{method}"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        data = _execute(dataset_id, [{"id": "s1", "method": method, "config": config}])
        assert not data.get("errors"), data
        assert isinstance(data.get("results"), list) and data["results"], data
        step = data["results"][0]
        assert step.get("status") == "completed", data
        assert step.get("method") == method
        payload = step.get("results")
        assert isinstance(payload, dict), data
        assert payload.get("error") is None, payload
        method_meta = payload.get("method")
        if isinstance(method_meta, dict):
            assert method_meta.get("id") == method
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_batch_modes_include_multiplicity_trace():
    dataset_id = "test_exec_v2_multiplicity_trace"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "b1",
                "method": "batch_analysis",
                "config": {
                    "group": "group",
                    "targets": ["item1", "item2", "item3"],
                    "method_id": "t_test_ind",
                    "multiplicity_correction": "holm",
                },
            },
            {
                "id": "b2",
                "method": "timepoint_batch_analysis",
                "config": {
                    "split_by": "visit",
                    "group": "group",
                    "targets": ["item1", "item2"],
                    "method_id": "t_test_ind",
                    "multiplicity_correction": "holm",
                },
            },
            {
                "id": "b3",
                "method": "delta_batch_analysis",
                "config": {
                    "group": "group",
                    "pairs": [
                        {"baseline": "baseline_a", "follow": "follow_a"},
                        {"baseline": "baseline_b", "follow": "follow_b"},
                    ],
                    "method_id": "t_test_ind",
                    "multiplicity_correction": "holm",
                },
            },
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data

        by_step = {str(step.get("step_id")): step.get("results") for step in data.get("results", []) if isinstance(step, dict)}
        batch_payload = by_step.get("b1")
        assert isinstance(batch_payload, dict), data
        trace = batch_payload.get("multiplicity_trace")
        assert isinstance(trace, dict), batch_payload
        assert trace.get("method") == "holm"
        assert int(trace.get("n_total")) == 3
        assert int(trace.get("n_valid")) >= 1

        tp_payload = by_step.get("b2")
        assert isinstance(tp_payload, dict), data
        trace_by_slice = tp_payload.get("multiplicity_trace_by_slice")
        assert isinstance(trace_by_slice, dict) and trace_by_slice, tp_payload
        for trace in trace_by_slice.values():
            assert isinstance(trace, dict)
            assert trace.get("method") == "holm"
            assert int(trace.get("n_total")) >= 1
            assert int(trace.get("n_valid")) >= 1

        delta_payload = by_step.get("b3")
        assert isinstance(delta_payload, dict), data
        delta_trace = delta_payload.get("multiplicity_trace")
        assert isinstance(delta_trace, dict), delta_payload
        assert delta_trace.get("method") == "holm"
        assert int(delta_trace.get("n_total")) == 2
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_applies_global_multiplicity_policy_defaults():
    dataset_id = "test_exec_v2_multiplicity_policy_globals"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "b1",
                "method": "batch_analysis",
                "config": {
                    "group": "group",
                    "targets": ["item1", "item2", "item3"],
                    "method_id": "t_test_ind",
                },
            },
            {
                "id": "a1",
                "method": "ancova",
                "config": {
                    "outcome": "outcome",
                    "group": "group",
                    "covariates": ["cov1", "cov2"],
                },
            },
            {
                "id": "s1",
                "method": "shapiro_wilk",
                "config": {"outcome": "outcome"},
            },
        ]
        data = _execute(
            dataset_id,
            protocol,
            globals_extra={"multiplicity_correction": "holm", "post_hoc_correction": "holm"},
        )
        assert not data.get("errors"), data

        by_step = {str(step.get("step_id")): step.get("results") for step in data.get("results", []) if isinstance(step, dict)}
        batch_payload = by_step.get("b1")
        assert isinstance(batch_payload, dict), data
        assert batch_payload.get("multiplicity_correction") == "holm"
        trace = batch_payload.get("multiplicity_trace")
        assert isinstance(trace, dict), batch_payload
        assert trace.get("method") == "holm"

        policy = data.get("multiplicity_policy")
        assert isinstance(policy, dict), data
        assert policy.get("correction") == "holm"
        assert policy.get("post_hoc_correction") == "holm"
        assert int(policy.get("n_applied_steps") or 0) >= 1
        assert int(policy.get("n_ignored_steps") or 0) >= 1
        assert "b1" in set(policy.get("applied_steps") or [])

        run_id = data.get("run_id")
        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        run_policy = run_payload.get("multiplicity_policy")
        assert isinstance(run_policy, dict), run_payload
        assert run_policy.get("correction") == "holm"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_persists_multiplicity_trace_artifact():
    dataset_id = "test_exec_v2_multiplicity_trace_artifact"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "b1",
                "method": "batch_analysis",
                "config": {
                    "group": "group",
                    "targets": ["item1", "item2", "item3"],
                    "method_id": "t_test_ind",
                    "multiplicity_correction": "fdr_by",
                },
            }
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        run_id = data.get("run_id")
        assert isinstance(run_id, str) and run_id

        multiplicity_trace = data.get("multiplicity_trace")
        assert isinstance(multiplicity_trace, dict), data
        assert multiplicity_trace.get("schema") == "clinimetria.multiplicity_trace"
        summary = multiplicity_trace.get("summary")
        assert isinstance(summary, dict)
        assert int(summary.get("steps_with_multiplicity") or 0) >= 1

        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        assert reproducibility.get("multiplicity_trace") == "multiplicity_trace.json"

        artifacts_dir = os.path.join(ds_dir, "analysis", run_id, "artifacts")
        artifact_path = os.path.join(artifacts_dir, "multiplicity_trace.json")
        assert os.path.exists(artifact_path)
        with open(artifact_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert payload.get("schema") == "clinimetria.multiplicity_trace"
        assert int(payload.get("summary", {}).get("steps_with_multiplicity") or 0) >= 1

        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        assert isinstance(run_payload.get("multiplicity_trace"), dict)

        list_res = client.get(f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={dataset_id}")
        assert list_res.status_code == 200, list_res.text
        names = {item.get("name") for item in list_res.json().get("files", [])}
        assert "multiplicity_trace.json" in names
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_creates_reproducibility_artifacts():
    dataset_id = "test_exec_v2_repro_artifacts"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "r1",
                "method": "ancova",
                "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1", "cov2"]},
            }
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        run_id = data.get("run_id")
        assert isinstance(run_id, str) and run_id

        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        assert reproducibility.get("script") == "reproduce_run.py"
        assert reproducibility.get("payload") == "reproduce_payload.json"
        assert reproducibility.get("protocol") == "protocol_resolved.json"
        assert reproducibility.get("manifest") == "reproducibility_manifest.json"
        assert reproducibility.get("report_html") == "protocol_report_auto.html"
        assert reproducibility.get("environment") == "reproducibility_environment.json"
        assert reproducibility.get("hypothesis_discovery") == "hypothesis_discovery.json"
        assert reproducibility.get("runtime_profile") == "runtime_profile.json"

        runtime_profile = data.get("runtime_profile")
        assert isinstance(runtime_profile, dict), data
        assert runtime_profile.get("schema") == "clinimetria.runtime_profile"
        runtime_summary = runtime_profile.get("summary")
        assert isinstance(runtime_summary, dict), runtime_profile
        assert int(runtime_summary.get("profiled_steps") or 0) >= 1
        assert int(runtime_summary.get("total_elapsed_ms") or 0) >= int(runtime_summary.get("steps_elapsed_ms") or 0)

        artifacts_dir = os.path.join(ds_dir, "analysis", run_id, "artifacts")
        for name in [
            "reproduce_run.py",
            "reproduce_payload.json",
            "protocol_resolved.json",
            "reproducibility_manifest.json",
            "reproducibility_environment.json",
            "hypothesis_discovery.json",
            "runtime_profile.json",
            "protocol_report_auto.html",
        ]:
            assert os.path.exists(os.path.join(artifacts_dir, name))

        list_res = client.get(f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={dataset_id}")
        assert list_res.status_code == 200, list_res.text
        names = {item.get("name") for item in list_res.json().get("files", [])}
        assert "reproduce_run.py" in names
        assert "reproducibility_manifest.json" in names
        assert "reproducibility_environment.json" in names
        assert "hypothesis_discovery.json" in names
        assert "runtime_profile.json" in names
        assert "protocol_report_auto.html" in names

        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        assert isinstance(run_payload.get("runtime_profile"), dict)
        assert run_payload["runtime_profile"].get("schema") == "clinimetria.runtime_profile"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_persists_hypothesis_discovery_artifact():
    dataset_id = "test_exec_v2_hypothesis_discovery_artifact"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "h1",
                "method": "t_test_ind",
                "config": {"outcome": "outcome", "group": "group"},
            }
        ]
        data = _execute(dataset_id, protocol, globals_extra={"analysis_mode": "focused"})
        assert not data.get("errors"), data
        run_id = data.get("run_id")
        assert isinstance(run_id, str) and run_id

        hypotheses = data.get("hypotheses")
        assert isinstance(hypotheses, dict), data
        assert hypotheses.get("schema") == "clinimetria.hypothesis_discovery"
        assert int(hypotheses.get("count") or 0) >= 1

        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        assert reproducibility.get("hypothesis_discovery") == "hypothesis_discovery.json"

        artifacts_dir = os.path.join(ds_dir, "analysis", run_id, "artifacts")
        artifact_path = os.path.join(artifacts_dir, "hypothesis_discovery.json")
        assert os.path.exists(artifact_path)
        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact_doc = json.load(f)
        assert artifact_doc.get("schema") == "clinimetria.hypothesis_discovery"
        assert int(artifact_doc.get("count") or 0) >= 1

        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        assert isinstance(run_payload.get("hypotheses"), dict)
        assert run_payload["hypotheses"].get("schema") == "clinimetria.hypothesis_discovery"

        list_res = client.get(f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={dataset_id}")
        assert list_res.status_code == 200, list_res.text
        names = {item.get("name") for item in list_res.json().get("files", [])}
        assert "hypothesis_discovery.json" in names
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_reproducibility_embeds_dataset_artifacts():
    dataset_id = "test_exec_v2_repro_dataset_artifacts"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        processed_dir = os.path.join(ds_dir, "processed")
        with open(os.path.join(processed_dir, "profile.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "clinimetria.profile", "version": 1, "dataset_id": dataset_id}, f)
        with open(os.path.join(processed_dir, "data_contract.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "clinimetria.data_contract", "version": 1, "dataset_id": dataset_id}, f)
        with open(os.path.join(processed_dir, "cleaning_plan.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "clinimetria.cleaning_plan", "version": 1, "dataset_id": dataset_id, "actions": []}, f)
        with open(os.path.join(processed_dir, "data_lineage.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": "clinimetria.data_lineage", "version": 1, "dataset_id": dataset_id, "entries": []}, f)

        protocol = [
            {
                "id": "r1",
                "method": "ancova",
                "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1", "cov2"]},
            }
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        run_id = data.get("run_id")
        assert isinstance(run_id, str) and run_id

        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        ds_artifacts = reproducibility.get("dataset_artifacts")
        assert isinstance(ds_artifacts, list)
        for expected in [
            "dataset_profile.json",
            "dataset_data_contract.json",
            "dataset_cleaning_plan.json",
            "dataset_data_lineage.json",
        ]:
            assert expected in ds_artifacts

        artifacts_dir = os.path.join(ds_dir, "analysis", run_id, "artifacts")
        for expected in [
            "dataset_profile.json",
            "dataset_data_contract.json",
            "dataset_cleaning_plan.json",
            "dataset_data_lineage.json",
        ]:
            assert os.path.exists(os.path.join(artifacts_dir, expected))

        manifest_path = os.path.join(artifacts_dir, "reproducibility_manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        assert isinstance(manifest.get("dataset_artifacts"), list)
        assert "dataset_profile.json" in manifest.get("dataset_artifacts")
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_persists_llm_benchmark_artifact():
    dataset_id = "test_exec_v2_llm_benchmark_artifact"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "r1",
                "method": "ancova",
                "config": {"outcome": "outcome", "group": "group", "covariates": ["cov1"]},
            }
        ]
        llm_benchmark = {
            "recorded_at": "2026-02-23T18:00:00Z",
            "recommended_id": "gemini_single",
            "variants": [
                {
                    "id": "gemini_single",
                    "label": "Gemini",
                    "status": "ok",
                    "elapsed_ms": 1200,
                    "quality_score": 78.4,
                    "benchmark_score": 0.912,
                    "step_count": 12,
                    "token_total": 2400,
                    "validation_profile": "focused",
                    "validator_strict": False,
                    "reflection_enabled": True,
                    "repair_correction": "fdr_bh",
                    "recommended": True,
                },
                {
                    "id": "qwen_single",
                    "label": "Qwen",
                    "status": "error",
                    "elapsed_ms": 120000,
                    "error": "timeout",
                    "recommended": False,
                },
            ],
        }

        data = _execute(dataset_id, protocol, globals_extra={"llm_benchmark": llm_benchmark})
        assert not data.get("errors"), data
        run_id = data.get("run_id")
        assert isinstance(run_id, str) and run_id

        benchmark_resp = data.get("llm_benchmark")
        assert isinstance(benchmark_resp, dict), data
        assert benchmark_resp.get("recommended_id") == "gemini_single"
        assert len(benchmark_resp.get("variants") or []) == 2

        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        assert reproducibility.get("llm_benchmark") == "llm_benchmark.json"

        artifacts_dir = os.path.join(ds_dir, "analysis", run_id, "artifacts")
        benchmark_path = os.path.join(artifacts_dir, "llm_benchmark.json")
        assert os.path.exists(benchmark_path)
        with open(benchmark_path, "r", encoding="utf-8") as f:
            bench_saved = json.load(f)
        assert bench_saved.get("schema") == "clinimetria.llm_benchmark"
        assert bench_saved.get("recommended_id") == "gemini_single"
        assert len(bench_saved.get("variants") or []) == 2
        first_variant = (bench_saved.get("variants") or [])[0]
        assert first_variant.get("validation_profile") == "focused"
        assert first_variant.get("validator_strict") is False
        assert first_variant.get("reflection_enabled") is True
        assert first_variant.get("repair_correction") == "fdr_bh"
        assert isinstance(first_variant.get("benchmark_score"), float)
        assert first_variant.get("benchmark_score") == 0.912

        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        assert isinstance(run_payload.get("llm_benchmark"), dict)
        assert run_payload["llm_benchmark"].get("recommended_id") == "gemini_single"

        list_res = client.get(f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={dataset_id}")
        assert list_res.status_code == 200, list_res.text
        names = {item.get("name") for item in list_res.json().get("files", [])}
        assert "llm_benchmark.json" in names
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_persists_bootstrap_trace_artifact():
    dataset_id = "test_exec_v2_bootstrap_trace"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "a1",
                "method": "ancova",
                "config": {
                    "outcome": "outcome",
                    "group": "group",
                    "covariates": ["cov1", "cov2"],
                    "bootstrap_ci": True,
                    "bootstrap_samples": 250,
                },
            },
            {
                "id": "p1",
                "method": "paired_wide",
                "config": {
                    "baseline": "baseline_a",
                    "follow": "follow_a",
                    "bootstrap_ci": True,
                    "bootstrap_samples": 250,
                },
            },
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        run_id = data.get("run_id")
        assert isinstance(run_id, str) and run_id

        bootstrap_trace = data.get("bootstrap_trace")
        assert isinstance(bootstrap_trace, dict), data
        assert bootstrap_trace.get("schema") == "clinimetria.bootstrap_trace"
        summary = bootstrap_trace.get("summary")
        assert isinstance(summary, dict)
        assert int(summary.get("steps_with_bootstrap") or 0) >= 2

        reproducibility = data.get("reproducibility")
        assert isinstance(reproducibility, dict), data
        assert reproducibility.get("bootstrap_trace") == "bootstrap_trace.json"

        artifacts_dir = os.path.join(ds_dir, "analysis", run_id, "artifacts")
        artifact_path = os.path.join(artifacts_dir, "bootstrap_trace.json")
        assert os.path.exists(artifact_path)
        with open(artifact_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert payload.get("schema") == "clinimetria.bootstrap_trace"
        assert int(payload.get("summary", {}).get("steps_with_bootstrap") or 0) >= 2

        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        assert isinstance(run_payload.get("bootstrap_trace"), dict)

        list_res = client.get(f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={dataset_id}")
        assert list_res.status_code == 200, list_res.text
        names = {item.get("name") for item in list_res.json().get("files", [])}
        assert "bootstrap_trace.json" in names
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_applies_global_bootstrap_policy_defaults():
    dataset_id = "test_exec_v2_bootstrap_policy_globals"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "a1",
                "method": "ancova",
                "config": {
                    "outcome": "outcome",
                    "group": "group",
                    "covariates": ["cov1", "cov2"],
                },
            },
            {
                "id": "s1",
                "method": "shapiro_wilk",
                "config": {"outcome": "outcome"},
            },
            {
                "id": "p1",
                "method": "paired_wide",
                "config": {
                    "baseline": "baseline_a",
                    "follow": "follow_a",
                },
            },
        ]
        data = _execute(
            dataset_id,
            protocol,
            globals_extra={"bootstrap_ci": True, "bootstrap_samples": 275},
        )
        assert not data.get("errors"), data

        by_step = {
            str(step.get("step_id")): step.get("results")
            for step in data.get("results", [])
            if isinstance(step, dict)
        }
        ancova_payload = by_step.get("a1")
        assert isinstance(ancova_payload, dict), data
        ancova_bootstrap = ancova_payload.get("bootstrap")
        assert isinstance(ancova_bootstrap, dict), ancova_payload
        assert ancova_bootstrap.get("enabled") is True
        assert int(ancova_bootstrap.get("samples")) == 275

        paired_payload = by_step.get("p1")
        assert isinstance(paired_payload, dict), data
        paired_bootstrap = paired_payload.get("bootstrap")
        assert isinstance(paired_bootstrap, dict), paired_payload
        assert paired_bootstrap.get("enabled") is True
        assert int(paired_bootstrap.get("samples")) == 275

        shapiro_payload = by_step.get("s1")
        assert isinstance(shapiro_payload, dict), data
        assert not isinstance(shapiro_payload.get("bootstrap"), dict), shapiro_payload

        policy = data.get("bootstrap_policy")
        assert isinstance(policy, dict), data
        assert policy.get("enabled") is True
        assert int(policy.get("samples")) == 275
        assert int(policy.get("n_applied_steps") or 0) >= 2
        assert int(policy.get("n_ignored_steps") or 0) >= 1

        run_id = data.get("run_id")
        with open(os.path.join(ds_dir, "analysis", run_id, "results.json"), "r", encoding="utf-8") as f:
            run_payload = json.load(f)
        run_policy = run_payload.get("bootstrap_policy")
        assert isinstance(run_policy, dict), run_payload
        assert run_policy.get("enabled") is True
        assert int(run_policy.get("samples")) == 275
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_engine_one_sample_bootstrap_payload():
    rng = np.random.default_rng(123)
    df = pd.DataFrame({"x": rng.normal(loc=0.5, scale=1.0, size=120)})
    res = run_analysis(
        df,
        "t_test_one",
        "x",
        "",
        alpha=0.05,
        bootstrap_ci=True,
        bootstrap_samples=400,
    )
    bootstrap = res.get("bootstrap")
    assert isinstance(bootstrap, dict), res
    assert bootstrap.get("enabled") is True
    assert int(bootstrap.get("samples")) == 400
    metrics = bootstrap.get("metrics")
    assert isinstance(metrics, dict)
    assert isinstance(metrics.get("mean_diff"), dict)
    assert isinstance(metrics.get("effect_size"), dict)


def test_engine_linear_regression_bootstrap_payload():
    rng = np.random.default_rng(321)
    n = 220
    x1 = rng.normal(0.0, 1.0, size=n)
    x2 = 0.5 * x1 + rng.normal(0.0, 1.0, size=n)
    y = 1.2 + 0.8 * x1 - 0.4 * x2 + rng.normal(0.0, 0.7, size=n)
    df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})

    res = run_analysis(
        df,
        "linear_regression",
        "y",
        "x1",
        alpha=0.05,
        predictors=["x1", "x2"],
        bootstrap_ci=True,
        bootstrap_samples=300,
    )
    bootstrap = res.get("bootstrap")
    assert isinstance(bootstrap, dict), res
    assert bootstrap.get("enabled") is True
    assert int(bootstrap.get("samples")) == 300
    metrics = bootstrap.get("metrics")
    assert isinstance(metrics, dict), bootstrap
    coef_rows = metrics.get("coefficients")
    assert isinstance(coef_rows, list) and coef_rows, metrics
    x1_row = next((row for row in coef_rows if isinstance(row, dict) and row.get("variable") == "x1"), None)
    assert isinstance(x1_row, dict), coef_rows
    assert x1_row.get("ci_lower") is not None
    assert x1_row.get("ci_upper") is not None
    assert isinstance(metrics.get("r_squared"), dict)

    coef_map = {
        str(row.get("variable")): row
        for row in (res.get("coefficients") if isinstance(res.get("coefficients"), list) else [])
        if isinstance(row, dict)
    }
    assert isinstance(coef_map.get("x1"), dict)
    assert coef_map["x1"].get("bootstrap_ci_lower") is not None
    assert coef_map["x1"].get("bootstrap_ci_upper") is not None


def test_engine_logistic_regression_bootstrap_payload():
    rng = np.random.default_rng(654)
    n = 260
    x1 = rng.normal(0.0, 1.0, size=n)
    x2 = rng.normal(0.0, 1.0, size=n)
    logits = 0.7 * x1 - 0.5 * x2 + rng.normal(0.0, 0.4, size=n)
    probs = 1.0 / (1.0 + np.exp(-logits))
    y = (rng.random(n) < probs).astype(int)
    df = pd.DataFrame({"y": y, "x1": x1, "x2": x2})

    res = run_analysis(
        df,
        "logistic_regression",
        "y",
        "x1",
        alpha=0.05,
        predictors=["x1", "x2"],
        bootstrap_ci=True,
        bootstrap_samples=300,
        show_roc=False,
    )
    bootstrap = res.get("bootstrap")
    assert isinstance(bootstrap, dict), res
    assert bootstrap.get("enabled") is True
    assert int(bootstrap.get("samples")) == 300
    metrics = bootstrap.get("metrics")
    assert isinstance(metrics, dict), bootstrap
    coef_rows = metrics.get("coefficients")
    assert isinstance(coef_rows, list) and coef_rows, metrics
    x1_row = next((row for row in coef_rows if isinstance(row, dict) and row.get("variable") == "x1"), None)
    assert isinstance(x1_row, dict), coef_rows
    assert x1_row.get("or_ci_lower") is not None
    assert x1_row.get("or_ci_upper") is not None
    assert isinstance(metrics.get("pseudo_r2"), dict)

    coef_map = {
        str(row.get("variable")): row
        for row in (res.get("coefficients") if isinstance(res.get("coefficients"), list) else [])
        if isinstance(row, dict)
    }
    assert isinstance(coef_map.get("x1"), dict)
    assert coef_map["x1"].get("bootstrap_or_ci_lower") is not None
    assert coef_map["x1"].get("bootstrap_or_ci_upper") is not None


def test_engine_ancova_bootstrap_payload():
    rng = np.random.default_rng(777)
    n = 200
    group = np.where(np.arange(n) < (n // 2), "A", "B")
    cov1 = rng.normal(50.0, 8.0, size=n)
    outcome = 10.0 + (group == "B").astype(float) * 1.2 + 0.35 * cov1 + rng.normal(0.0, 1.0, size=n)
    df = pd.DataFrame({"outcome": outcome, "group": group, "cov1": cov1})

    res = run_analysis(
        df,
        "ancova",
        "outcome",
        "group",
        alpha=0.05,
        covariates=["cov1"],
        bootstrap_ci=True,
        bootstrap_samples=300,
    )
    bootstrap = res.get("bootstrap")
    assert isinstance(bootstrap, dict), res
    assert bootstrap.get("enabled") is True
    assert int(bootstrap.get("samples")) == 300
    metrics = bootstrap.get("metrics")
    assert isinstance(metrics, dict), bootstrap
    assert isinstance(metrics.get("effect_size"), dict)
    assert res.get("effect_size_ci_lower") is not None
    assert res.get("effect_size_ci_upper") is not None


def test_execute_protocol_paired_wide_bootstrap_payload():
    dataset_id = "test_exec_v2_paired_wide_bootstrap"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "pw1",
                "method": "paired_wide",
                "config": {
                    "baseline": "baseline_a",
                    "follow": "follow_a",
                    "method": "t_test_rel",
                    "bootstrap_ci": True,
                    "bootstrap_samples": 400,
                },
            }
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        step = data.get("results", [])[0]
        payload = step.get("results")
        assert isinstance(payload, dict), data
        bootstrap = payload.get("bootstrap")
        assert isinstance(bootstrap, dict), payload
        assert bootstrap.get("enabled") is True
        assert int(bootstrap.get("samples")) == 400
        metrics = bootstrap.get("metrics")
        assert isinstance(metrics, dict)
        assert isinstance(metrics.get("mean_diff"), dict)
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_ancova_bootstrap_payload():
    dataset_id = "test_exec_v2_ancova_bootstrap"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "a1",
                "method": "ancova",
                "config": {
                    "outcome": "outcome",
                    "group": "group",
                    "covariates": ["cov1", "cov2"],
                    "bootstrap_ci": True,
                    "bootstrap_samples": 300,
                },
            }
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        step = data.get("results", [])[0]
        payload = step.get("results")
        assert isinstance(payload, dict), data
        bootstrap = payload.get("bootstrap")
        assert isinstance(bootstrap, dict), payload
        assert bootstrap.get("enabled") is True
        assert int(bootstrap.get("samples")) == 300
        metrics = bootstrap.get("metrics")
        assert isinstance(metrics, dict)
        assert isinstance(metrics.get("effect_size"), dict)
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_logistic_bootstrap_payload():
    dataset_id = "test_exec_v2_logistic_bootstrap"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        protocol = [
            {
                "id": "l1",
                "method": "logistic_regression",
                "config": {
                    "outcome": "before",
                    "group": "cov1",
                    "predictors": ["cov1", "cov2"],
                    "bootstrap_ci": True,
                    "bootstrap_samples": 300,
                    "show_roc": False,
                },
            }
        ]
        data = _execute(dataset_id, protocol)
        assert not data.get("errors"), data
        step = data.get("results", [])[0]
        payload = step.get("results")
        assert isinstance(payload, dict), data
        bootstrap = payload.get("bootstrap")
        assert isinstance(bootstrap, dict), payload
        assert bootstrap.get("enabled") is True
        assert int(bootstrap.get("samples")) == 300
        metrics = bootstrap.get("metrics")
        assert isinstance(metrics, dict)
        coef_rows = metrics.get("coefficients")
        assert isinstance(coef_rows, list) and coef_rows
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)


def test_execute_protocol_paired_wide_constant_no_runtime_warning():
    dataset_id = "test_exec_v2_paired_wide_constant"
    ds_dir = _prepare_dataset(dataset_id)
    try:
        parquet_path = os.path.join(ds_dir, "processed", f"{dataset_id}.parquet")
        df = pd.read_parquet(parquet_path)
        df["baseline_a"] = 10.0
        df["follow_a"] = 10.0
        df.to_parquet(parquet_path)

        protocol = [
            {
                "id": "pw_const",
                "method": "paired_wide",
                "config": {
                    "baseline": "baseline_a",
                    "follow": "follow_a",
                    "method": "t_test_rel",
                },
            }
        ]

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            data = _execute(dataset_id, protocol)

        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert not runtime_warnings
        assert not data.get("errors"), data
        step = data.get("results", [])[0]
        payload = step.get("results")
        assert isinstance(payload, dict), data
        assert payload.get("method", {}).get("id") == "paired_wide"
    finally:
        if os.path.exists(ds_dir):
            shutil.rmtree(ds_dir)
