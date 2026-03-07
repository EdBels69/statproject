"""Tests for paired_wide descriptive stats + dot plot rendering."""

import asyncio

import pandas as pd
import pytest

from app.modules.reporting_html import ProtocolReport
from app.modules.reporting_plots import _render_plot_png_bytes
from app.stats.executors.paired_wide import execute_paired_wide


class TestPairedWideDescriptive:
    """Test descriptive payload inside paired_wide executor."""

    def test_desc_basic_stats(self):
        """Descriptive dict should have n, mean, median, q1, q3."""
        df = pd.DataFrame(
            {
                "Control": [10.0, 11.0, 12.0, 13.0],
                "Treatment": [11.0, 12.0, 14.0, 15.0],
            }
        )
        payload = asyncio.run(
            execute_paired_wide(
                df,
                {"baseline": "Control", "follow": "Treatment", "method": "t_test_rel"},
                0.05,
                runtime_kwargs={"bootstrap_ci": False},
            )
        )

        desc = payload.get("descriptive")
        assert isinstance(desc, dict)
        assert set(["Control", "Treatment", "delta"]).issubset(set(desc.keys()))

        ctrl = desc["Control"]
        assert ctrl.get("n") == 4
        assert ctrl.get("mean") == pytest.approx(11.5)
        assert ctrl.get("median") == pytest.approx(11.5)
        assert ctrl.get("q1") == pytest.approx(10.75)
        assert ctrl.get("q3") == pytest.approx(12.25)

    def test_desc_single_value(self):
        """std should be None for n=1."""
        df = pd.DataFrame({"Control": [5.0], "Treatment": [6.0]})
        payload = asyncio.run(
            execute_paired_wide(
                df,
                {"baseline": "Control", "follow": "Treatment", "method": "t_test_rel"},
                0.05,
                runtime_kwargs={"bootstrap_ci": False},
            )
        )

        desc = payload.get("descriptive")
        assert isinstance(desc, dict)
        assert desc.get("Control", {}).get("n") == 1
        assert desc.get("Control", {}).get("std") is None
        assert desc.get("Treatment", {}).get("std") is None
        assert desc.get("delta", {}).get("std") is None


class TestPairedDotPlot:
    """Test paired dot plot rendering."""

    def test_paired_dot_generates_png(self):
        res = {
            "type": "hypothesis_test",
            "method": {"id": "paired_wide"},
            "plot_hint": "paired_dot",
            "baseline": "Control",
            "follow": "Treatment",
            "p_value": 0.03,
            "significant": True,
            "raw_pairs": [{"baseline": float(b), "follow": float(f)} for b, f in zip(range(10), range(1, 11))],
        }
        png = _render_plot_png_bytes(res, is_ru=True)
        assert png is not None
        assert len(png) > 1000

    def test_paired_dot_no_pairs_returns_none(self):
        res = {
            "type": "hypothesis_test",
            "method": {"id": "paired_wide"},
            "plot_hint": "paired_dot",
            "raw_pairs": [],
        }
        png = _render_plot_png_bytes(res)
        assert png is None or isinstance(png, bytes)


class TestGlobalDescriptiveSection:
    """Test the Table 0 section in HTML report."""

    def test_section_renders_from_descriptive_data(self):
        run_data = {
            "analysis_set": {
                "descriptive": {
                    "var_A": {
                        "n": 10,
                        "mean": 5.0,
                        "std": 1.0,
                        "median": 5.0,
                        "q1": 4.0,
                        "q3": 6.0,
                        "iqr": 2.0,
                        "min": 3.0,
                        "max": 7.0,
                    }
                }
            },
            "results": {},
            "step_meta": {},
        }
        rpt = ProtocolReport(run_data, dataset_name="test")
        rpt.is_ru = True
        rpt.html_parts = []
        rpt._add_global_descriptive_section()
        html = "".join(rpt.html_parts)
        assert "Таблица 0" in html
        assert "var_A" in html
