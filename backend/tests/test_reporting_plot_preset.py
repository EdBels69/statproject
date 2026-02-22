import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules import reporting


def test_render_plot_uses_theme_colors_for_roc_lines(monkeypatch):
    colors_seen = []
    original_plot = reporting.plt.plot

    def _capture_plot(*args, **kwargs):
        color = kwargs.get("color")
        if isinstance(color, str):
            colors_seen.append(color)
        return original_plot(*args, **kwargs)

    monkeypatch.setattr(reporting.plt, "plot", _capture_plot)
    monkeypatch.setattr(
        reporting,
        "_report_plot_theme",
        lambda: {
            "primary": "#111111",
            "secondary": "#999999",
            "accent": "#123456",
            "neutral": "#f1f5f9",
            "palette": ["#123456", "#abcdef"],
            "bar_fill": "#123456",
            "box_fill": "#f1f5f9",
            "diag_line": "#654321",
            "hexbin_cmap": "viridis",
            "contingency_cmap": "Blues",
            "correlation_heatmap_cmap": "vlag",
        },
    )

    payload = {
        "plot_data": [
            {"x": 0.0, "y": 0.0},
            {"x": 0.4, "y": 0.8},
            {"x": 1.0, "y": 1.0},
        ],
        "plot_config": {"type": "line"},
    }
    png = reporting._render_plot_png_bytes(payload, is_ru=False)

    assert png.startswith(b"\x89PNG")
    assert "#123456" in colors_seen
    assert "#654321" in colors_seen


def test_render_plot_uses_theme_colors_for_group_comparison(monkeypatch):
    box_colors = []
    strip_colors = []
    original_boxplot = reporting.sns.boxplot
    original_stripplot = reporting.sns.stripplot

    def _capture_boxplot(*args, **kwargs):
        color = kwargs.get("color")
        if isinstance(color, str):
            box_colors.append(color)
        return original_boxplot(*args, **kwargs)

    def _capture_stripplot(*args, **kwargs):
        color = kwargs.get("color")
        if isinstance(color, str):
            strip_colors.append(color)
        return original_stripplot(*args, **kwargs)

    monkeypatch.setattr(reporting.sns, "boxplot", _capture_boxplot)
    monkeypatch.setattr(reporting.sns, "stripplot", _capture_stripplot)
    monkeypatch.setattr(
        reporting,
        "_report_plot_theme",
        lambda: {
            "primary": "#222222",
            "secondary": "#777777",
            "accent": "#4444aa",
            "neutral": "#eceff3",
            "palette": ["#556677", "#778899"],
            "bar_fill": "#556677",
            "box_fill": "#eceff3",
            "diag_line": "#777777",
            "hexbin_cmap": "viridis",
            "contingency_cmap": "Blues",
            "correlation_heatmap_cmap": "vlag",
        },
    )

    payload = {
        "plot_data": [
            {"group": "A", "value": 1.2},
            {"group": "A", "value": 1.4},
            {"group": "B", "value": 2.1},
            {"group": "B", "value": 2.4},
        ]
    }
    png = reporting._render_plot_png_bytes(payload, is_ru=False)

    assert png.startswith(b"\x89PNG")
    assert "#eceff3" in box_colors
    assert "#222222" in strip_colors
