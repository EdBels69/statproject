import io
import os
import sys
import tempfile

from docx import Document

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting import generate_protocol_docx_report, render_protocol_report


def _simple_run_data() -> dict:
    return {
        "dataset_id": "report_sections_ds",
        "alpha": 0.05,
        "results": {
            "step_compare": {
                "type": "hypothesis_test",
                "method": {"id": "t_test_ind", "name": "Independent t-test"},
                "method_id": "t_test_ind",
                "p_value": 0.01,
                "stat_value": 2.45,
                "effect_size": 0.62,
                "plot_stats": {
                    "A": {"count": 20, "mean": 10.1, "sd": 1.1, "median": 10.0, "q1": 9.4, "q3": 10.8},
                    "B": {"count": 20, "mean": 11.2, "sd": 1.0, "median": 11.1, "q1": 10.5, "q3": 11.8},
                },
                "plot_data": [
                    {"group": "A", "value": 10.1},
                    {"group": "A", "value": 9.9},
                    {"group": "B", "value": 11.1},
                    {"group": "B", "value": 11.3},
                ],
                "interpretation_contract": {
                    "claim": "There is a between-group effect for the primary endpoint.",
                    "evidence": "Independent t-test, p=0.0100, effect=0.620.",
                    "clinical_meaning": "Difference is clinically plausible for baseline stratification.",
                    "limitations": "Single-center dataset; external validation required.",
                    "actionable_next_step": "Run adjusted model with confounders and sensitivity analysis.",
                },
                "conclusion": "Group means differ significantly.",
            }
        },
    }


def _p2_run_data() -> dict:
    return {
        "dataset_id": "report_sections_p2",
        "alpha": 0.05,
        "results": {
            "step_bootstrap": {
                "type": "bootstrap_pipeline",
                "method": {"id": "bootstrap_pipeline", "name": "Bootstrap pipeline"},
                "method_id": "bootstrap_pipeline",
                "p_value": 0.012,
                "stat_value": 1.24,
                "effect_size": 1.24,
                "effect_size_ci_lower": 0.45,
                "effect_size_ci_upper": 2.03,
                "mode": "group_difference",
                "statistic": "mean_difference",
                "groups": ["A", "B"],
                "n_left": 44,
                "n_right": 46,
                "bootstrap": {
                    "n_resamples": 400,
                    "ci_level": 0.95,
                    "distribution_mean": 1.20,
                    "distribution_std": 0.41,
                    "observed_effect": 1.24,
                },
            },
            "step_cluster": {
                "type": "cluster_profiles",
                "method": {"id": "cluster_profiles", "name": "Cluster profiles"},
                "method_id": "cluster_profiles",
                "n_observations": 120,
                "n_variables": 6,
                "n_clusters": 3,
                "silhouette_score": 0.37,
                "clusters": [
                    {"cluster": 0, "size": 44, "proportion": 0.366},
                    {"cluster": 1, "size": 39, "proportion": 0.325},
                    {"cluster": 2, "size": 37, "proportion": 0.308},
                ],
                "embedding": [
                    {"row_id": "0", "cluster": 0, "x": -1.2, "y": 0.6},
                    {"row_id": "1", "cluster": 1, "x": 0.9, "y": -0.4},
                    {"row_id": "2", "cluster": 2, "x": 1.4, "y": 0.8},
                    {"row_id": "3", "cluster": 0, "x": -0.8, "y": 0.2},
                ],
            },
            "step_external": {
                "type": "external_validation",
                "method": {"id": "external_validation", "name": "External validation"},
                "method_id": "external_validation",
                "task": "classification",
                "external_dataset_id": "external_ds_1",
                "n_train": 150,
                "n_internal_test": 50,
                "n_external": 80,
                "internal_metrics": {
                    "auc": 0.83,
                    "accuracy": 0.78,
                    "precision": 0.77,
                    "recall": 0.75,
                    "f1": 0.76,
                },
                "external_metrics": {
                    "auc": 0.79,
                    "accuracy": 0.74,
                    "precision": 0.72,
                    "recall": 0.70,
                    "f1": 0.71,
                },
                "generalization_gap": {"auc_gap_external_minus_internal": -0.04},
                "confusion_matrix": {
                    "labels": ["0", "1"],
                    "values": [[31, 9], [12, 28]],
                },
                "calibration": {
                    "brier_score": 0.19,
                    "curve": [
                        {"x": 0.15, "y": 0.11},
                        {"x": 0.35, "y": 0.28},
                        {"x": 0.65, "y": 0.62},
                    ],
                },
                "roc": {
                    "auc": 0.79,
                    "plot_data": [
                        {"x": 0.0, "y": 0.0},
                        {"x": 0.2, "y": 0.6},
                        {"x": 1.0, "y": 1.0},
                    ],
                    "plot_config": {"type": "line"},
                },
            },
        },
    }


def test_render_protocol_report_includes_methods_results_and_limitations(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        html = render_protocol_report(_simple_run_data(), dataset_name="Demo", style="apa7")

    assert 'id="methods"' in html
    assert 'id="results"' in html
    assert 'id="limitations"' in html
    assert "Methods" in html
    assert "Results" in html
    assert "Limitations" in html
    assert "Independent t-test" in html
    assert "Figure caption:" in html
    assert "Statistical claim" in html


def test_generate_protocol_docx_report_includes_methods_and_limitations(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        payload = generate_protocol_docx_report(_simple_run_data(), dataset_name="Demo", style="apa7")

    doc = Document(io.BytesIO(payload))
    text = "\n".join([p.text for p in doc.paragraphs if p.text])

    assert "Methods" in text
    assert "Limitations" in text
    assert "Statistical Analysis Results" in text
    assert "Figure caption:" in text
    assert "Statistical claim:" in text


def test_render_protocol_report_includes_p2_structured_sections(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        html = render_protocol_report(_p2_run_data(), dataset_name="Demo", style="apa7")

    assert "Bootstrap Effect Stability" in html
    assert "Cluster Profiles" in html
    assert "External Validation" in html
    assert "Generalization gap" in html
    assert "Brier score" in html


def test_generate_protocol_docx_report_includes_p2_structured_sections(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", tmpdir)
        payload = generate_protocol_docx_report(_p2_run_data(), dataset_name="Demo", style="apa7")

    doc = Document(io.BytesIO(payload))
    text = "\n".join([p.text for p in doc.paragraphs if p.text])

    assert "Bootstrap Effect Stability" in text
    assert "Cluster Profiles" in text
    assert "External Validation" in text
    assert "Brier score" in text
