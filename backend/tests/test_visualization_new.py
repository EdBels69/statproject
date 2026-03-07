"""Tests for new visualization features: brackets, spaghetti v2, waterfall, responder."""


class TestSignificanceBrackets:
    """Auto-bracket for 2-group hypothesis_test."""

    def test_bracket_renders_on_two_group_hypothesis_test(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        res = {
            "type": "hypothesis_test",
            "method": {"id": "mann_whitney"},
            "p_value": 0.023,
            "significant": True,
            "plot_data": [
                {"group": "A", "value": 10.0},
                {"group": "A", "value": 12.0},
                {"group": "A", "value": 9.0},
                {"group": "B", "value": 20.0},
                {"group": "B", "value": 22.0},
                {"group": "B", "value": 18.0},
            ],
        }
        png = _render_plot_png_bytes(res, is_ru=True)
        assert png is not None
        assert len(png) > 2000

    def test_no_bracket_without_p_value(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        res = {
            "type": "hypothesis_test",
            "method": {"id": "mann_whitney"},
            "plot_data": [
                {"group": "A", "value": 10.0},
                {"group": "B", "value": 20.0},
            ],
        }
        png = _render_plot_png_bytes(res, is_ru=False)
        # Should not crash, returns PNG or None
        assert png is None or isinstance(png, bytes)

    def test_bracket_label_ns_for_p_above_005(self):
        from app.modules.plot_with_brackets import format_significance_label

        assert format_significance_label(0.06) == "ns"
        assert format_significance_label(0.049) == "*"
        assert format_significance_label(0.009) == "**"
        assert format_significance_label(0.0009) == "***"


class TestSpaghettiV2:
    """Improved spaghetti plot with direction colors and annotation."""

    def test_spaghetti_renders_direction_stats(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        raw = [{"baseline": float(b), "follow": float(b) - 3.0} for b in range(20, 35)]
        raw += [{"baseline": float(b), "follow": float(b) + 2.0} for b in range(30, 36)]
        res = {
            "type": "hypothesis_test",
            "method": {"id": "paired_wide"},
            "plot_hint": "paired_dot",
            "baseline": "До",
            "follow": "После",
            "p_value": 0.008,
            "significant": True,
            "raw_pairs": raw,
        }
        png = _render_plot_png_bytes(res, is_ru=True)
        assert png is not None
        assert len(png) > 3000


class TestWaterfallPlot:
    """Waterfall plot rendering."""

    def test_waterfall_renders_from_waterfall_data(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        deltas = [float(d) for d in range(-15, 15)]
        res = {
            "type": "hypothesis_test",
            "method": {"id": "paired_wide"},
            "plot_hint": "waterfall",
            "baseline": "До",
            "follow": "После",
            "waterfall_data": [{"delta": d} for d in deltas],
        }
        png = _render_plot_png_bytes(res, is_ru=True)
        assert png is not None
        assert len(png) > 3000

    def test_waterfall_renders_from_raw_pairs(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        raw = [{"baseline": 10.0 + i, "follow": 10.0 + i - 4.0} for i in range(20)]
        res = {
            "type": "hypothesis_test",
            "method": {"id": "paired_wide"},
            "plot_hint": "waterfall",
            "baseline": "V1",
            "follow": "V2",
            "raw_pairs": raw,
        }
        png = _render_plot_png_bytes(res, is_ru=False)
        assert png is not None
        assert len(png) > 3000


class TestNestedPlotRendering:
    """Nested per-step plots should be rendered in HTML."""

    def test_protocol_report_renders_nested_waterfall_plot(self):
        from app.modules.reporting_html import ProtocolReport

        run_data = {
            "results": {
                "step_1": {
                    "type": "hypothesis_test",
                    "method": {"id": "paired_wide", "name": "Paired Wide"},
                    "plot_hint": "paired_dot",
                    "baseline": "V1",
                    "follow": "V2",
                    "p_value": 0.02,
                    "significant": True,
                    "raw_pairs": [{"baseline": 10.0 + i, "follow": 8.0 + i} for i in range(12)],
                    "waterfall_result": {
                        "type": "hypothesis_test",
                        "method": {"id": "paired_wide"},
                        "plot_hint": "waterfall",
                        "baseline": "V1",
                        "follow": "V2",
                        "waterfall_data": [{"delta": -2.0} for _ in range(12)],
                    },
                }
            },
            "step_meta": {"step_1": {"method": "paired_wide", "config": {"baseline": "V1", "follow": "V2"}}},
        }

        report = ProtocolReport(run_data, dataset_name="test")
        report.is_ru = True
        html = report.generate_html()
        assert html.count("data:image/png;base64,") >= 2


class TestResponderAnalysis:
    """Responder analysis executor."""

    def _make_df(self):
        import pandas as pd

        return pd.DataFrame(
            {
                "V1": [50.0, 60, 40, 55, 70, 80, 45, 90, 35, 65],
                "V2": [30.0, 55, 38, 20, 40, 75, 44, 45, 33, 60],
                "Group": ["A", "B", "A", "A", "B", "B", "A", "A", "B", "B"],
            }
        )

    def test_basic_responder_analysis(self):
        from app.stats.executors.responder_analysis import execute_responder_analysis

        df = self._make_df()
        result = execute_responder_analysis(
            df,
            config={"baseline": "V1", "follow": "V2", "group": "Group", "threshold": 5.0, "direction": "decrease"},
            alpha=0.05,
        )
        assert result["type"] == "responder_analysis"
        assert "groups" in result
        assert len(result["groups"]) == 2
        assert "p_value" in result
        assert isinstance(result["n_total"], int)
        assert result["n_total"] == 10

    def test_table_has_header_row(self):
        from app.stats.executors.responder_analysis import execute_responder_analysis

        df = self._make_df()
        result = execute_responder_analysis(
            df,
            config={"baseline": "V1", "follow": "V2", "group": "Group"},
            alpha=0.05,
        )
        table = result.get("table", [])
        assert len(table) >= 2
        assert table[0][0] in {"Группа", "Group"}

    def test_pct_threshold_responder(self):
        from app.stats.executors.responder_analysis import execute_responder_analysis

        df = self._make_df()
        result = execute_responder_analysis(
            df,
            config={"baseline": "V1", "follow": "V2", "group": "Group", "threshold_pct": 0.20, "direction": "decrease"},
            alpha=0.05,
        )
        assert result["type"] == "responder_analysis"
        assert "threshold_description" in result
        assert "20" in result["threshold_description"]

    def test_missing_column_returns_error(self):
        from app.stats.executors.responder_analysis import execute_responder_analysis
        import pandas as pd

        df = pd.DataFrame({"A": [1.0, 2.0]})
        result = execute_responder_analysis(
            df,
            config={"baseline": "nonexistent", "follow": "also_missing"},
            alpha=0.05,
        )
        assert "error" in result

    def test_responder_bar_plot_renders(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        res = {
            "type": "responder_analysis",
            "method": {"id": "responder_analysis"},
            "plot_hint": "responder_bar",
            "threshold_description": "снижение ≥20%",
            "p_value": 0.032,
            "test_name": "Fisher's exact test",
            "groups": [
                {"group": "Active", "n": 10, "n_responders": 7, "n_nonresponders": 3, "pct_responders": 70.0},
                {"group": "Placebo", "n": 10, "n_responders": 3, "n_nonresponders": 7, "pct_responders": 30.0},
            ],
        }
        png = _render_plot_png_bytes(res, is_ru=True)
        assert png is not None
        assert len(png) > 3000
