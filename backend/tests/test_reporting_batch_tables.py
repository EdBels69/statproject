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
    assert "t_test_ind" in html

    # Previously these step types were rendered by unknown fallback with raw JSON dump.
    assert "batch_step (batch_analysis)" not in html
    assert "tp_step (timepoint_batch_analysis)" not in html
    assert "white-space:pre-wrap; word-break:break-word" not in html

