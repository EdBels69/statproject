import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.reporting import render_protocol_report


def _group_stats(a_mean, b_mean):
    return {
        "A": {"count": 20, "mean": a_mean, "sd": 1.2, "median": a_mean - 0.1, "q1": a_mean - 0.8, "q3": a_mean + 0.7},
        "B": {"count": 20, "mean": b_mean, "sd": 1.1, "median": b_mean - 0.1, "q1": b_mean - 0.7, "q3": b_mean + 0.6},
    }


def test_render_protocol_report_renders_batch_and_timepoint_tables_without_unknown_fallback():
    run_data = {
        "dataset_id": "report_batch_tables",
        "alpha": 0.05,
        "results": {
            "batch_step": {
                "type": "batch_analysis",
                "group": "group",
                "multiplicity_correction": "fdr_bh",
                "items": [
                    {
                        "target": "marker_1",
                        "p_value": 0.004,
                        "p_value_adj": 0.008,
                        "method": "t_test_ind",
                        "plot_stats": _group_stats(10.4, 12.1),
                    },
                    {
                        "target": "marker_2",
                        "p_value": 0.07,
                        "p_value_adj": 0.09,
                        "method": "t_test_ind",
                        "plot_stats": _group_stats(7.9, 8.3),
                    },
                ],
            },
            "tp_step": {
                "type": "timepoint_batch_analysis",
                "split_by": "visit",
                "group": "group",
                "slices": {
                    "T1": {
                        "items": [
                            {
                                "target": "marker_1",
                                "p_value": 0.01,
                                "p_value_adj": 0.02,
                                "method": "t_test_ind",
                                "plot_stats": _group_stats(10.0, 11.5),
                            }
                        ]
                    },
                    "T2": {
                        "items": [
                            {
                                "target": "marker_1",
                                "p_value": 0.2,
                                "p_value_adj": 0.3,
                                "method": "t_test_ind",
                                "plot_stats": _group_stats(10.5, 10.8),
                            }
                        ]
                    },
                },
            },
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert 'id="step-batch_step"' in html
    assert 'id="step-tp_step"' in html
    assert "Пакетный анализ" in html
    assert "Точка: T1" in html
    assert "p(adj)" in html
    assert "t-тест (независимые выборки)" in html
    assert "FDR (Benjamini-Hochberg)" in html
    assert "Таблица 1*. Описательная статистика для инференциальных тестов" in html

    # Previously these step types were rendered by unknown fallback with raw JSON dump.
    assert "batch_step (batch_analysis)" not in html
    assert "tp_step (timepoint_batch_analysis)" not in html
    assert "white-space:pre-wrap; word-break:break-word" not in html


def test_render_protocol_report_renders_time_series_as_analysis_section():
    run_data = {
        "dataset_id": "report_time_series",
        "alpha": 0.05,
        "results": {
            "ts_step": {
                "type": "time_series",
                "method": {"id": "time_series_analysis", "name": "Time Series"},
                "p_value": 0.012,
                "trend": {"slope": 0.24},
                "diagnostics": {"ljung_box": {"p_value": 0.031, "white_noise_like": False}},
                "time_quality": {
                    "quality": "warning",
                    "datetime_parse_ratio": 1.0,
                    "min_year": 1970,
                    "max_year": 1970,
                    "flags": ["epoch_artifact_risk"],
                    "inferred_frequency": "D",
                },
                "forecast": {"points": [{"x": "2026-01-04", "y": 12.4}, {"x": "2026-01-05", "y": 12.8}]},
                "plot_data": [
                    {"x": "2026-01-01", "y": 10.0, "trend": 9.9},
                    {"x": "2026-01-02", "y": 10.7, "trend": 10.3},
                    {"x": "2026-01-03", "y": 11.4, "trend": 10.8},
                ],
                "plot_config": {"type": "line", "x_label": "date", "y_label": "value"},
                "warnings": [
                    "Calendar years are concentrated in 1970-1985; verify date parsing to avoid Unix-epoch artifacts."
                ],
                "conclusion": "Тренд восходящий; ряд не белый шум.",
            }
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert 'id="step-ts_step"' in html
    assert "Диагностика ряда" in html
    assert "Прогноз (точек)" in html
    assert "Качество временной оси" in html
    assert "Предупреждения по хронологии" in html
    assert "epoch_artifact_risk" in html
    assert "ts_step (time_series)" not in html
    assert "white-space:pre-wrap; word-break:break-word" not in html


def test_render_protocol_report_replaces_placeholder_interpretation_and_adds_hypotheses():
    run_data = {
        "dataset_id": "report_interpretation_fallback",
        "alpha": 0.05,
        "step_meta": {
            "ancova_step": {
                "id": "ancova_step",
                "method": "ancova",
                "title": "ANCOVA контроль baseline",
                "config": {
                    "outcome": "Глюкоза",
                    "group": "Исход",
                    "covariates": ["Возраст", "SpO2"],
                },
            }
        },
        "results": {
            "ancova_step": {
                "type": "hypothesis_test",
                "method": {"id": "ancova", "name": "ancova"},
                "p_value": 0.012,
                "stat_value": 5.1,
                "significant": True,
                "covariates": ["Возраст", "SpO2"],
                "conclusion": "Analysis completed.",
            }
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert "Analysis completed." not in html
    assert "ANCOVA-анализ" in html
    assert "Гипотезы" in html
    assert "H0: эффекта/различий нет." in html


def test_render_protocol_report_includes_hypothesis_discovery_trace_section():
    run_data = {
        "dataset_id": "report_hypothesis_trace",
        "hypotheses": {
            "schema": "clinimetria.hypothesis_discovery",
            "analysis_mode": "publication",
            "design_type": "parallel_groups",
            "count": 2,
            "items": [
                {
                    "id": "h_group_numeric",
                    "title": "Сравнить outcome между group",
                    "h0": "H0: различий нет",
                    "h1": "H1: различия есть",
                    "suggested_method": "t_test_ind / mann_whitney / anova",
                    "priority": "high",
                },
                {
                    "id": "h_assoc",
                    "title": "Проверить связь num_x и num_y",
                    "h0": "H0: связи нет",
                    "h1": "H1: связь есть",
                    "suggested_method": "pearson / spearman",
                    "priority": "medium",
                },
            ],
        },
        "step_meta": {
            "s1": {"id": "s1", "method": "t_test_ind", "config": {"outcome": "outcome", "group": "group"}},
            "s2": {"id": "s2", "method": "pearson", "config": {"outcome": "num_x", "group": "num_y"}},
        },
        "results": {
            "s1": {
                "type": "hypothesis_test",
                "method": {"id": "t_test_ind", "name": "t_test_ind"},
                "p_value": 0.01,
            },
            "s2": {
                "type": "correlation",
                "method": {"id": "pearson", "name": "pearson"},
                "p_value": 0.03,
            },
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert 'id="hypothesis-discovery"' in html
    assert "Гипотезы и их трассировка" in html
    assert "Сравнить outcome между group" in html
    assert "Проверить связь num_x и num_y" in html
    assert "s1" in html
    assert "s2" in html
    assert "Вердикт" in html
    assert "подтверждена" in html


def test_render_protocol_report_renders_bootstrap_trace_for_regression():
    run_data = {
        "dataset_id": "report_bootstrap_trace",
        "alpha": 0.05,
        "results": {
            "reg_step": {
                "type": "regression",
                "method": {"id": "linear_regression", "name": "linear_regression"},
                "p_value": 0.004,
                "r_squared": 0.62,
                "coefficients": [
                    {"variable": "const", "coefficient": 1.2, "p_value": 0.03, "std_err": 0.2, "ci_lower": 0.8, "ci_upper": 1.6},
                    {"variable": "x1", "coefficient": 0.5, "p_value": 0.001, "std_err": 0.1, "ci_lower": 0.3, "ci_upper": 0.7},
                ],
                "bootstrap": {
                    "enabled": True,
                    "method": "bootstrap_percentile",
                    "samples": 300,
                    "ci_level": 0.95,
                    "n_valid_models": 276,
                    "metrics": {
                        "r_squared": {
                            "estimate": 0.61,
                            "ci_lower": 0.54,
                            "ci_upper": 0.67,
                            "n_valid": 276,
                        },
                        "coefficients": [
                            {
                                "variable": "x1",
                                "estimate": 0.50,
                                "ci_lower": 0.38,
                                "ci_upper": 0.63,
                                "n_valid": 276,
                            }
                        ],
                    },
                },
            }
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert "Bootstrap-трассировка" in html
    assert "samples=300" in html
    assert "x1: est=0.500" in html


def test_render_protocol_report_includes_provenance_and_step_scope(tmp_path, monkeypatch):
    dataset_id = "ds_provenance_case"
    run_id = "run_20260223_case"
    source_dir = tmp_path / "datasets" / dataset_id / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "meta.json").write_text(
        json.dumps(
            {
                "original_filename": "Общая таблица Ковид19.xlsx",
                "sheet_name": "Sheet1",
                "header_row": 0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (source_dir / "dataset.raw").write_bytes(b"raw")
    monkeypatch.setenv("CLINIMETRIA_WORKSPACE_DIR", str(tmp_path))

    run_data = {
        "dataset_id": dataset_id,
        "run_id": run_id,
        "analysis_set": {
            "analysis_set_id": "aset_01",
            "n_selected": 424,
            "mode": "simple_impute",
            "enforce": "all",
        },
        "analysis_dataset": {
            "rows": 424,
            "columns": 159,
            "xlsx": "analysis_dataset.xlsx",
            "parquet": "analysis_dataset.parquet",
        },
        "reproducibility": {
            "ready": True,
            "script": "reproduce_run.py",
            "payload": "reproduce_payload.json",
            "manifest": "reproducibility_manifest.json",
            "protocol": "protocol_resolved.json",
            "multiplicity_trace": "multiplicity_trace.json",
            "bootstrap_trace": "bootstrap_trace.json",
            "artifacts": [
                "reproduce_run.py",
                "reproduce_payload.json",
                "reproducibility_manifest.json",
                "multiplicity_trace.json",
                "bootstrap_trace.json",
            ],
        },
        "protocol_validation": {
            "schema": "clinimetria.protocol_validation",
            "status": "failed",
            "enabled": True,
            "strict": False,
            "policy_profile": "focused",
            "policy": {
                "profile": "focused",
                "multiplicity_correction": "fdr_bh",
                "repair_correction": "holm",
                "reflection_enabled": True,
            },
            "summary": {
                "steps_total": 1,
                "steps_checked": 1,
                "steps_failed": 1,
                "global_errors": 0,
            },
            "steps": [
                {
                    "step_id": "batch_step",
                    "status": "failed",
                    "warnings": [
                        "Time column year range looks unusual (1970-1985); verify chronology and source dates."
                    ],
                    "errors": ["Dummy validation failure"],
                }
            ],
        },
        "bootstrap_policy": {
            "enabled": True,
            "samples": 2000,
            "n_applied_steps": 1,
            "n_ignored_steps": 0,
        },
        "multiplicity_policy": {
            "enabled": True,
            "correction": "fdr_bh",
            "post_hoc_correction": "holm",
            "n_applied_steps": 1,
            "n_ignored_steps": 0,
        },
        "step_meta": {
            "batch_step": {
                "id": "batch_step",
                "name": "Batch CRP by outcome",
                "config": {
                    "method_id": "auto",
                    "group": "Исход.2",
                    "targets": ["СРБ1", "Глюкоза при поступлении"],
                    "normality_test": "anderson",
                    "homogeneity_test": "fligner",
                    "bootstrap_ci": True,
                    "bootstrap_samples": 2000,
                    "multiplicity_correction": "fdr_bh",
                },
            }
        },
        "results": {
            "batch_step": {
                "type": "batch_analysis",
                "group": "Исход.2",
                "multiplicity_correction": "fdr_bh",
                "items": [
                    {
                        "target": "СРБ1",
                        "p_value": 0.01,
                        "p_value_adj": 0.02,
                        "method": "t_test_ind",
                        "plot_stats": _group_stats(15.2, 20.3),
                    }
                ],
            }
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert 'id="provenance"' in html
    assert 'id="protocol-validation"' in html
    assert "Общая таблица Ковид19.xlsx" in html
    assert run_id in html
    assert "reproduce_run.py" in html
    assert "bootstrap_trace.json" in html
    assert "multiplicity_trace.json" in html
    assert "analysis_dataset.xlsx" in html
    assert "Замороженная выборка (analysis_set)" in html
    assert "batch_step" in html
    assert "фактор=Исход.2" in html
    assert "Нормальность: anderson" in html
    assert "Валидация протокола" in html
    assert "status=ошибка" in html
    assert "FDR (Benjamini-Hochberg)" in html
    assert "[fdr_bh]" not in html
    assert "[holm]" not in html
    assert "Multiplicity-политика" in html
    assert "Bootstrap-политика" in html
    assert "samples=2000" in html
    assert "Проблемные шаги валидации" in html


def test_render_protocol_report_hides_failed_verification_steps():
    run_data = {
        "dataset_id": "report_verify_filter",
        "alpha": 0.05,
        "verification": {
            "status": "failed",
            "failures": [
                {"check": "p_value_bounds", "step_id": "bad_step", "message": "p_value out of [0,1]"},
            ],
        },
        "results": {
            "ok_step": {
                "type": "hypothesis_test",
                "method": {"id": "t_test_ind", "name": "Independent t-test"},
                "p_value": 0.03,
                "effect_size": 0.42,
                "conclusion": "Difference observed.",
                "plot_stats": _group_stats(10.2, 11.1),
            },
            "bad_step": {
                "type": "hypothesis_test",
                "method": {"id": "t_test_ind", "name": "Independent t-test"},
                "p_value": 1.4,
                "effect_size": 0.10,
                "conclusion": "Invalid p-value.",
                "plot_stats": _group_stats(8.0, 8.1),
            },
        },
    }

    html = render_protocol_report(run_data, dataset_name="Demo", style="gost")

    assert 'id="step-ok_step"' in html
    assert 'id="step-bad_step"' not in html
    assert "Исключено верификатором" in html
