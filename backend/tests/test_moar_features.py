"""Tests for MOAR-level features: forest plot, power, assumptions, DOCX data quality."""
import numpy as np
import pytest


class TestForestPlot:
    def test_forest_plot_renders(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        res = {
            "plot_hint": "forest_plot",
            "effects": [
                {"label": "HGB", "effect_size": 0.8, "ci_lower": 0.3, "ci_upper": 1.3, "significant": True},
                {"label": "PLT", "effect_size": 0.1, "ci_lower": -0.2, "ci_upper": 0.4, "significant": False},
                {"label": "WBC", "effect_size": -0.5, "ci_lower": -0.9, "ci_upper": -0.1, "significant": True},
            ],
        }
        png = _render_plot_png_bytes(res, is_ru=True)
        assert png is not None
        assert len(png) > 3000

    def test_forest_plot_empty_effects(self):
        from app.modules.reporting_plots import _render_plot_png_bytes

        res = {"plot_hint": "forest_plot", "effects": []}
        png = _render_plot_png_bytes(res, is_ru=True)
        # Should return None or minimal output without crash
        assert png is None or isinstance(png, bytes)


class TestPostHocPower:
    def test_power_two_sample(self):
        from app.stats.engine import compute_post_hoc_power

        power = compute_post_hoc_power(n1=30, n2=30, effect_size=0.8, alpha=0.05, test_type="two_sample")
        assert power is not None
        assert 0 < power <= 1.0
        # For d=0.8, n=30+30, power should be decent (>0.7)
        assert power > 0.7

    def test_power_paired(self):
        from app.stats.engine import compute_post_hoc_power

        power = compute_post_hoc_power(n1=20, effect_size=0.5, alpha=0.05, test_type="paired")
        assert power is not None
        assert 0 < power <= 1.0

    def test_power_zero_effect(self):
        from app.stats.engine import compute_post_hoc_power

        power = compute_post_hoc_power(n1=100, effect_size=0.0, alpha=0.05)
        assert power is None  # zero effect -> None

    def test_power_none_effect(self):
        from app.stats.engine import compute_post_hoc_power

        power = compute_post_hoc_power(n1=100, effect_size=None, alpha=0.05)
        assert power is None


class TestAssumptionsBadge:
    def test_badge_renders(self):
        from app.modules.reporting_html import ProtocolReport

        rpt = ProtocolReport({"results": {}, "step_meta": {}, "dataset_id": "x"}, dataset_name="test")
        rpt.is_ru = True
        html = rpt._render_assumptions_badge(
            {"normality": {"test": "shapiro", "stat": 0.95, "p": 0.32, "passed": True}},
            is_ru=True,
        )
        assert "shapiro" in html.lower() or "Shapiro" in html
        assert "✓" in html

    def test_badge_empty(self):
        from app.modules.reporting_html import ProtocolReport

        rpt = ProtocolReport({"results": {}, "step_meta": {}, "dataset_id": "x"}, dataset_name="test")
        html = rpt._render_assumptions_badge({}, is_ru=False)
        assert html == ""


class TestConvertNumpyUtils:
    def test_convert_from_utils(self):
        from app.utils import convert_numpy_to_native

        result = convert_numpy_to_native({"a": np.float64(3.14), "b": np.int64(42)})
        assert result["a"] == pytest.approx(3.14)
        assert result["b"] == 42
        assert isinstance(result["a"], float)
        assert isinstance(result["b"], int)

    def test_convert_nan(self):
        from app.utils import convert_numpy_to_native

        result = convert_numpy_to_native(np.float64(np.nan))
        assert result is None
