"""
reporting_plots.py — extracted plot rendering from reporting.py.

Contains _report_plot_theme() and _render_plot_png_bytes() which handle all
matplotlib/seaborn chart generation for reports.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from app.modules.plot_config import apply_publication_config, get_group_colors, COLORS

try:
    from app.modules.reporting_utils import normalize_comparisons, add_significance_bracket
except ImportError:
    # Fallback if reporting_utils not available
    def normalize_comparisons(*args, **kwargs):
        return []
    def add_significance_bracket(*args, **kwargs):
        pass

logger = logging.getLogger(__name__)


# Import helper functions that _render_plot_png_bytes depends on
def _format_axis_label(res: Dict[str, Any], is_ru: bool) -> str:
    """Format Y-axis label from result metadata."""
    target = res.get("target_variable") or res.get("variable") or res.get("y_label")
    if target:
        return str(target)
    return "Значение" if is_ru else "Value"


def _format_group_axis_label(res: Dict[str, Any], is_ru: bool) -> str:
    """Format X-axis label (group variable)."""
    group = res.get("group_variable") or res.get("x_label")
    if group:
        return str(group)
    return "Группа" if is_ru else "Group"


def _report_plot_theme() -> Dict[str, Any]:
    palette = get_group_colors(8)
    primary = COLORS.get("primary", "#0f172a")
    secondary = COLORS.get("secondary", "#64748b")
    accent = COLORS.get("accent", "#8b5cf6")
    neutral = COLORS.get("neutral", "#f1f5f9")
    if not palette:
        palette = [primary, accent]

    return {
        "primary": primary,
        "secondary": secondary,
        "accent": accent,
        "neutral": neutral,
        "palette": palette,
        "bar_fill": palette[0],
        "box_fill": neutral,
        "diag_line": secondary,
        "hexbin_cmap": "viridis",
        "contingency_cmap": "Blues",
        "correlation_heatmap_cmap": "vlag",
    }


def _render_plot_png_bytes(res: Dict[str, Any], is_ru: bool = False) -> bytes:
    try:
        plot_b64 = res.get("plot_image_b64") if isinstance(res, dict) else None
        if isinstance(plot_b64, str) and plot_b64.strip():
            try:
                return base64.b64decode(plot_b64)
            except Exception:
                pass
        apply_publication_config()
        theme = _report_plot_theme()
        palette = list(theme.get("palette") or [])
        if not palette:
            palette = [str(theme.get("primary") or "#0f172a"), str(theme.get("accent") or "#8b5cf6")]

        base_type = res.get("type") if isinstance(res, dict) else None

        if base_type == "table_1":
            stats = res.get("data") if isinstance(res, dict) else None
            if isinstance(stats, dict) and stats:
                groups = [k for k in stats.keys() if k != "overall"]
                xs = []
                ys = []
                yerr_low = []
                yerr_high = []
                for g in groups:
                    s = stats.get(g)
                    if not isinstance(s, dict):
                        continue
                    mean = s.get("mean")
                    try:
                        mean_f = float(mean)
                        if not np.isfinite(mean_f):
                            continue
                    except Exception:
                        continue

                    lo = s.get("ci_95_low")
                    hi = s.get("ci_95_high")
                    n = s.get("count")
                    std = s.get("std")

                    lo_f = None
                    hi_f = None
                    try:
                        lo_f = float(lo) if lo is not None else None
                        if lo_f is not None and not np.isfinite(lo_f):
                            lo_f = None
                    except Exception:
                        lo_f = None
                    try:
                        hi_f = float(hi) if hi is not None else None
                        if hi_f is not None and not np.isfinite(hi_f):
                            hi_f = None
                    except Exception:
                        hi_f = None

                    if lo_f is None or hi_f is None:
                        try:
                            n_f = float(n) if n is not None else None
                            std_f = float(std) if std is not None else None
                            if n_f is not None and std_f is not None and np.isfinite(n_f) and np.isfinite(std_f) and n_f > 1:
                                sem = std_f / float(np.sqrt(n_f))
                                lo_f = mean_f - 1.96 * sem
                                hi_f = mean_f + 1.96 * sem
                        except Exception:
                            lo_f = None
                            hi_f = None

                    xs.append(str(g) + (f"\n(n={int(n)})" if isinstance(n, (int, float)) else ""))
                    ys.append(mean_f)
                    if lo_f is not None and hi_f is not None:
                        yerr_low.append(max(0.0, mean_f - lo_f))
                        yerr_high.append(max(0.0, hi_f - mean_f))
                    else:
                        yerr_low.append(0.0)
                        yerr_high.append(0.0)

                if xs and ys:
                    plt.figure(figsize=(7.6, 4.4))
                    x_pos = np.arange(len(xs))
                    yerr = np.array([yerr_low, yerr_high])
                    bar_color = str(theme.get("bar_fill") or palette[0])
                    edge_color = str(theme.get("primary") or "#0f172a")
                    plt.bar(x_pos, ys, color=bar_color, edgecolor=edge_color, linewidth=1.0, alpha=0.85)
                    if yerr.size and np.any(yerr > 0):
                        plt.errorbar(x_pos, ys, yerr=yerr, fmt="none", ecolor=edge_color, elinewidth=1.2, capsize=4)
                    plot_data = res.get("plot_data") if isinstance(res, dict) else None
                    if isinstance(plot_data, list) and plot_data:
                        group_order = []
                        for label in xs:
                            name = str(label).split("\n", 1)[0]
                            group_order.append(name)
                        group_index = {g: i for i, g in enumerate(group_order)}
                        rng = np.random.default_rng(42)
                        xs_scatter = []
                        ys_scatter = []
                        for row in plot_data:
                            if not isinstance(row, dict):
                                continue
                            g = row.get("group")
                            v = row.get("value")
                            if g is None or v is None:
                                continue
                            try:
                                yv = float(v)
                            except Exception:
                                continue
                            gi = group_index.get(str(g))
                            if gi is None:
                                continue
                            xs_scatter.append(float(gi) + float(rng.uniform(-0.12, 0.12)))
                            ys_scatter.append(yv)
                        if xs_scatter:
                            plt.scatter(xs_scatter, ys_scatter, s=14, alpha=0.45, color=edge_color, zorder=3)
                    plt.xticks(x_pos, xs)
                    plt.title("Описательная статистика (среднее ± 95% ДИ)" if is_ru else "Descriptives (mean ± 95% CI)")
                    plt.xlabel("Группа" if is_ru else "Group")
                    plt.ylabel(_format_axis_label(res, is_ru))
                    plt.grid(True, axis="y", alpha=0.25)
                    buf = io.BytesIO()
                    plt.tight_layout()
                    plt.savefig(buf, format="png")
                    plt.close()
                    return bytes(buf.getvalue())

        cont = res.get("contingency") if isinstance(res, dict) else None
        if isinstance(cont, dict) and isinstance(cont.get("counts"), list) and cont.get("counts"):
            try:
                counts = np.array(cont.get("counts"))
                if counts.size:
                    plt.figure(figsize=(7.6, 4.6))
                    rows = cont.get("rows") if isinstance(cont.get("rows"), list) else None
                    cols = cont.get("cols") if isinstance(cont.get("cols"), list) else None
                    rlab = [str(x) for x in rows] if rows else None
                    clab = [str(x) for x in cols] if cols else None
                    sns.heatmap(
                        counts,
                        annot=True,
                        fmt="g",
                        cmap=str(theme.get("contingency_cmap") or "Blues"),
                        cbar=False,
                        xticklabels=clab if clab else True,
                        yticklabels=rlab if rlab else True,
                    )
                    plt.title("Таблица сопряжённости")
                    plt.xlabel("Группа")
                    plt.ylabel("Категория")
                    buf = io.BytesIO()
                    plt.tight_layout()
                    plt.savefig(buf, format="png")
                    plt.close()
                    return bytes(buf.getvalue())
            except Exception:
                try:
                    plt.close()
                except Exception:
                    pass


        plot_hint = res.get("plot_hint") if isinstance(res, dict) else None

        # ------------------------------------------------------------------
        # Responder bar chart
        # ------------------------------------------------------------------
        if plot_hint == "responder_bar":
            groups_resp = res.get("groups") if isinstance(res, dict) else None
            if isinstance(groups_resp, list) and groups_resp:
                try:
                    import io as _io
                    theme_r = _report_plot_theme()
                    pal_r = list(theme_r.get("palette") or [])
                    labels = [str(g.get("group", "?")) for g in groups_resp]
                    pcts = [float(g.get("pct_responders", 0)) for g in groups_resp]
                    ns = [int(g.get("n", 0)) for g in groups_resp]

                    fig, ax = plt.subplots(figsize=(max(5, len(labels) * 1.5 + 2), 4.5))
                    fig.patch.set_facecolor(theme_r.get("bg") or "#ffffff")
                    ax.set_facecolor(theme_r.get("grid_bg") or "#f8fafc")
                    bar_colors = [pal_r[i % len(pal_r)] for i in range(len(labels))] if pal_r else None
                    bars = ax.bar(
                        labels,
                        pcts,
                        color=bar_colors,
                        width=0.55,
                        edgecolor="white",
                    )

                    for bar, n_val in zip(bars, ns):
                        h = bar.get_height()
                        ax.text(
                            bar.get_x() + bar.get_width() / 2,
                            h + 1.5,
                            f"{h:.1f}%\n(n={n_val})",
                            ha="center",
                            va="bottom",
                            fontsize=8.5,
                            fontweight="bold",
                        )

                    ax.set_ylim(0, min(115, max(pcts) + 20))
                    ax.set_ylabel("Доля ответивших, %" if is_ru else "Responder rate, %", fontsize=9)

                    # p-value annotation
                    p_val_r = res.get("p_value")
                    test_n = res.get("test_name", "")
                    thr_desc = res.get("threshold_description", "")
                    p_label = ""
                    if p_val_r is not None:
                        try:
                            pf = float(p_val_r)
                            p_label = f"p = {pf:.4f}" if pf >= 0.0001 else "p < 0.0001"
                            if test_n:
                                p_label = f"{test_n}: {p_label}"
                        except Exception:
                            pass

                    title_r = "Доля ответивших по группам" if is_ru else "Responder rate by group"
                    subtitle = str(thr_desc or "")
                    if p_label:
                        subtitle = (subtitle + "\n" + p_label).strip()
                    if subtitle:
                        title_r += "\n" + subtitle
                    ax.set_title(title_r, fontsize=9.5, fontweight="bold")
                    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
                    plt.tight_layout()
                    buf_r = _io.BytesIO()
                    plt.savefig(buf_r, format="png", dpi=150)
                    plt.close()
                    return bytes(buf_r.getvalue())
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        # ------------------------------------------------------------------
        # Waterfall plot — ranked individual deltas for paired_wide / delta
        # ------------------------------------------------------------------
        if plot_hint == "waterfall" or plot_hint == "responder_bar" or (
            isinstance(res, dict) and res.get("waterfall_data") and plot_hint != "paired_dot"
        ):
            waterfall_data = res.get("waterfall_data") if isinstance(res, dict) else None
            if not isinstance(waterfall_data, list) or len(waterfall_data) < 2:
                # Try to build from raw_pairs
                raw_pairs_w = res.get("raw_pairs") if isinstance(res, dict) else None
                if isinstance(raw_pairs_w, list):
                    waterfall_data = []
                    for p in raw_pairs_w:
                        bv = p.get("baseline")
                        fv = p.get("follow")
                        if bv is not None and fv is not None:
                            try:
                                waterfall_data.append({"delta": float(fv) - float(bv)})
                            except Exception:
                                pass

            if isinstance(waterfall_data, list) and len(waterfall_data) >= 2:
                try:
                    import io as _io
                    deltas = []
                    for item in waterfall_data:
                        if isinstance(item, dict):
                            d = item.get("delta")
                        else:
                            try:
                                d = float(item)
                            except Exception:
                                continue
                        if d is not None:
                            try:
                                deltas.append(float(d))
                            except Exception:
                                pass

                    if len(deltas) < 2:
                        raise ValueError("too few deltas")

                    deltas.sort()  # ascending: worst on left, best on right
                    xs = list(range(len(deltas)))
                    colors_wf = ["#dc2626" if d > 0 else "#16a34a" for d in deltas]

                    theme_wf = _report_plot_theme()
                    fig, ax = plt.subplots(figsize=(max(6.0, len(deltas) * 0.18 + 2), 4.5))
                    fig.patch.set_facecolor(theme_wf.get("bg") or "#ffffff")
                    ax.set_facecolor(theme_wf.get("grid_bg") or "#f8fafc")
                    ax.bar(xs, deltas, color=colors_wf, width=0.85, edgecolor="white", linewidth=0.3)
                    ax.axhline(0, color="#0f172a", linewidth=1.0, linestyle="-")

                    n_pos = sum(1 for d in deltas if d > 0)
                    n_neg = sum(1 for d in deltas if d <= 0)
                    pct_improved = 100 * n_neg / max(1, len(deltas))

                    baseline_l = str(res.get("baseline") or "Baseline")
                    follow_l = str(res.get("follow") or "Follow-up")
                    ylabel_str = f"Δ ({follow_l} − {baseline_l})"

                    ax.set_ylabel(ylabel_str, fontsize=8.5)
                    ax.set_xlabel("Пациенты (ранжировано)" if is_ru else "Patients (ranked)", fontsize=8.5)
                    title_wf = "Waterfall: индивидуальные изменения" if is_ru else "Waterfall: individual changes"
                    ax.set_title(
                        f"{title_wf}\n"
                        f"{'Улучшение' if is_ru else 'Improved'}: {n_neg} ({pct_improved:.0f}%)  |  "
                        f"{'Ухудшение' if is_ru else 'Worsened'}: {n_pos} ({100 - pct_improved:.0f}%)",
                        fontsize=9,
                        fontweight="bold",
                    )
                    ax.set_xticks([])
                    ax.grid(True, axis="y", alpha=0.25, linestyle="--")

                    # Legend patches
                    from matplotlib.patches import Patch
                    ax.legend(
                        handles=[
                            Patch(color="#16a34a", label="↓ улучшение" if is_ru else "↓ improved"),
                            Patch(color="#dc2626", label="↑ ухудшение" if is_ru else "↑ worsened"),
                        ],
                        fontsize=7.5,
                        loc="best",
                        framealpha=0.7,
                    )

                    plt.tight_layout()
                    buf_wf = _io.BytesIO()
                    plt.savefig(buf_wf, format="png", dpi=150)
                    plt.close()
                    return bytes(buf_wf.getvalue())
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass


        # ------------------------------------------------------------------
        # Paired dot plot (connected spaghetti) for paired_wide
        # ------------------------------------------------------------------
        plot_hint = res.get("plot_hint") if isinstance(res, dict) else None
        method_id_res = None
        method_field = res.get("method") if isinstance(res, dict) else None
        if isinstance(method_field, dict):
            method_id_res = method_field.get("id")
        elif isinstance(method_field, str):
            method_id_res = method_field

        if plot_hint == "paired_dot" or method_id_res == "paired_wide":
            raw_pairs = res.get("raw_pairs") if isinstance(res, dict) else None
            baseline_label = str(res.get("baseline") or "Baseline")
            follow_label = str(res.get("follow") or "Follow-up")
            p_val = res.get("p_value")
            significant = bool(res.get("significant"))

            if isinstance(raw_pairs, list) and len(raw_pairs) >= 2:
                try:
                    import io as _io
                    pairs_valid = [
                        p for p in raw_pairs
                        if "baseline" in p and "follow" in p
                        and p["baseline"] is not None and p["follow"] is not None
                    ]
                    xs_b = [float(p["baseline"]) for p in pairs_valid]
                    xs_f = [float(p["follow"]) for p in pairs_valid]
                    n_pairs = len(xs_b)
                    if n_pairs < 2:
                        raise ValueError("too few pairs")

                    theme2 = _report_plot_theme()
                    pal2 = list(theme2.get("palette") or [])
                    col_b = pal2[0] if pal2 else "#0f172a"
                    col_f = pal2[1] if len(pal2) > 1 else "#8b5cf6"

                    # Direction-colored lines
                    improved_color = "#16a34a"
                    worsened_color = "#dc2626"
                    neutral_color = "#94a3b8"

                    fig, ax = plt.subplots(figsize=(5.5, 5))
                    fig.patch.set_facecolor(theme2.get("bg") or "#ffffff")
                    ax.set_facecolor(theme2.get("grid_bg") or "#f8fafc")

                    n_improved = 0
                    n_worsened = 0
                    n_unchanged = 0
                    for bv, fv in zip(xs_b, xs_f):
                        delta = fv - bv
                        if delta < 0:
                            lc = improved_color
                            n_improved += 1
                        elif delta > 0:
                            lc = worsened_color
                            n_worsened += 1
                        else:
                            lc = neutral_color
                            n_unchanged += 1
                        ax.plot([0, 1], [bv, fv], color=lc, alpha=0.40, linewidth=1.2, zorder=1)

                    # Jittered dots
                    jitter = 0.04
                    rng2 = np.random.default_rng(42)
                    bx = rng2.uniform(-jitter, jitter, n_pairs)
                    fx = rng2.uniform(-jitter, jitter, n_pairs)
                    ax.scatter(
                        bx,
                        xs_b,
                        color=col_b,
                        s=50,
                        zorder=3,
                        label=baseline_label,
                        edgecolors="white",
                        linewidths=0.5,
                    )
                    ax.scatter(
                        1 + fx,
                        xs_f,
                        color=col_f,
                        s=50,
                        zorder=3,
                        label=follow_label,
                        edgecolors="white",
                        linewidths=0.5,
                    )

                    # Median segments
                    med_b = float(np.median(xs_b))
                    med_f = float(np.median(xs_f))
                    ax.plot([-0.22, 0.22], [med_b, med_b], color=col_b, linewidth=3.0, zorder=4)
                    ax.plot([0.78, 1.22], [med_f, med_f], color=col_f, linewidth=3.0, zorder=4)

                    ax.set_xticks([0, 1])
                    ax.set_xticklabels(
                        [baseline_label[:28], follow_label[:28]],
                        fontsize=8.5,
                    )
                    ax.set_xlim(-0.45, 1.45)
                    ax.set_ylabel("Значение" if is_ru else "Value", fontsize=9)

                    # p-value text
                    p_txt = ""
                    if p_val is not None:
                        try:
                            pf = float(p_val)
                            if pf >= 0.001:
                                p_txt = f"p = {pf:.3f}"
                            else:
                                p_txt = "p < 0.001"
                        except Exception:
                            pass

                    title = "Парные измерения" if is_ru else "Paired measurements"
                    if p_txt:
                        title += f"\n{p_txt}"
                    ax.set_title(title, fontsize=9.5, fontweight="bold")

                    # Direction stats annotation
                    dir_up = "↓ улучшение" if is_ru else "↓ improved"
                    dir_dn = "↑ ухудшение" if is_ru else "↑ worsened"
                    ann_lines = [
                        f"n = {n_pairs}",
                        f"{dir_up}: {n_improved} ({100 * n_improved // max(1, n_pairs)}%)",
                        f"{dir_dn}: {n_worsened} ({100 * n_worsened // max(1, n_pairs)}%)",
                    ]
                    ax.annotate(
                        "\n".join(ann_lines),
                        xy=(1.03, 0.96),
                        xycoords="axes fraction",
                        ha="left",
                        va="top",
                        fontsize=7.5,
                        color="#475569",
                        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.7, lw=0),
                    )

                    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.6)
                    ax.grid(True, axis="y", alpha=0.25, linestyle="--")
                    plt.tight_layout()
                    buf2 = _io.BytesIO()
                    plt.savefig(buf2, format="png", dpi=150)
                    plt.close()
                    return bytes(buf2.getvalue())
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        if base_type == "mixed_effects":
            estimated_means = res.get("estimated_means") if isinstance(res, dict) else None
            if isinstance(estimated_means, dict) and estimated_means:
                groups = list(estimated_means.keys())
                time_labels = []
                for g in groups:
                    tps = estimated_means.get(g)
                    if isinstance(tps, dict):
                        time_labels.extend(list(tps.keys()))
                time_labels = [str(x) for x in dict.fromkeys(time_labels).keys()]
                try:
                    time_labels_sorted = sorted(time_labels, key=lambda x: float(x))
                except Exception:
                    time_labels_sorted = time_labels

                w = 7.5
                h = 4.8
                plt.figure(figsize=(w, h))
                xs = list(range(len(time_labels_sorted)))
                for idx, g in enumerate(groups):
                    points = estimated_means.get(g)
                    if not isinstance(points, dict):
                        continue
                    ys = []
                    yerr = []
                    for t in time_labels_sorted:
                        cell = points.get(t)
                        if not isinstance(cell, dict):
                            ys.append(np.nan)
                            yerr.append((0.0, 0.0))
                            continue
                        est = cell.get("estimate")
                        lo = cell.get("ci_lower")
                        hi = cell.get("ci_upper")
                        y = float(est) if isinstance(est, (int, float)) else np.nan
                        ys.append(y)
                        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and np.isfinite(y):
                            yerr.append((max(0.0, y - float(lo)), max(0.0, float(hi) - y)))
                        else:
                            yerr.append((0.0, 0.0))

                    yerr_arr = np.array(yerr).T if yerr else None
                    color = palette[idx % len(palette)]
                    plt.errorbar(
                        xs,
                        ys,
                        yerr=yerr_arr,
                        marker="o",
                        linewidth=2,
                        capsize=3,
                        color=color,
                        markerfacecolor=color,
                        markeredgecolor=str(theme.get("primary") or "#0f172a"),
                        label=str(g),
                    )

                plt.xticks(xs, time_labels_sorted, rotation=0)
                plt.title("Время × Группа" if is_ru else "Time × Group")
                plt.xlabel("Время" if is_ru else "Time")
                plt.ylabel(_format_axis_label(res, is_ru))
                plt.legend(frameon=False)
                plt.grid(True, axis="y", alpha=0.25)
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format="png")
                plt.close()
                return bytes(buf.getvalue())

        if base_type == "clustered_correlation":
            corr = res.get("correlation_matrix") if isinstance(res, dict) else None
            if isinstance(corr, dict) and isinstance(corr.get("values"), list) and isinstance(corr.get("variables"), list):
                vars_ = [str(v) for v in corr.get("variables")]
                vals = np.array(corr.get("values"), dtype=float)
                n = max(2, len(vars_))
                size = min(11.5, max(6.0, 0.35 * n))
                plt.figure(figsize=(size, size))
                ax = sns.heatmap(
                    vals,
                    vmin=-1,
                    vmax=1,
                    cmap=str(theme.get("correlation_heatmap_cmap") or "vlag"),
                    center=0,
                    square=True,
                    cbar=True,
                    xticklabels=vars_,
                    yticklabels=vars_,
                )
                ax.tick_params(axis="x", labelrotation=60, labelsize=8)
                ax.tick_params(axis="y", labelrotation=0, labelsize=8)
                plt.title("Кластерная корреляция" if is_ru else "Clustered Correlation")
                buf = io.BytesIO()
                plt.tight_layout()
                plt.savefig(buf, format="png")
                plt.close()
                return bytes(buf.getvalue())

        # ------------------------------------------------------------------
        # Forest plot — all effect sizes from protocol
        # ------------------------------------------------------------------
        if plot_hint == "forest_plot":
            effects = res.get("effects") if isinstance(res, dict) else None
            if isinstance(effects, list) and len(effects) >= 2:
                try:
                    import io as _io

                    labels = []
                    es_vals = []
                    ci_lows = []
                    ci_highs = []
                    colors_f = []
                    for e in effects:
                        if not isinstance(e, dict):
                            continue
                        lbl = str(e.get("label", ""))[:50]
                        es = e.get("effect_size")
                        ci_l = e.get("ci_lower")
                        ci_h = e.get("ci_upper")
                        sig = e.get("significant", False)
                        if es is None:
                            continue
                        try:
                            es_f = float(es)
                            ci_l_f = float(ci_l) if ci_l is not None else es_f
                            ci_h_f = float(ci_h) if ci_h is not None else es_f
                        except Exception:
                            continue
                        if not np.isfinite(es_f):
                            continue
                        labels.append(lbl)
                        es_vals.append(es_f)
                        ci_lows.append(ci_l_f)
                        ci_highs.append(ci_h_f)
                        colors_f.append("#dc2626" if sig else "#94a3b8")

                    if len(labels) >= 2:
                        n_items = len(labels)
                        height = max(3.5, n_items * 0.35 + 1.5)
                        fig, ax = plt.subplots(figsize=(8, height))
                        ys = list(range(n_items))

                        for y, es, lo, hi, c in zip(ys, es_vals, ci_lows, ci_highs, colors_f):
                            ax.plot([lo, hi], [y, y], color=c, linewidth=2.0, solid_capstyle="round")
                            ax.plot(es, y, "o", color=c, markersize=7, markeredgecolor="white", markeredgewidth=0.5)

                        ax.axvline(0, color="#0f172a", linewidth=1.0, linestyle="--", alpha=0.6)
                        ax.set_yticks(ys)
                        ax.set_yticklabels(labels, fontsize=7.5)
                        ax.invert_yaxis()
                        ax.set_xlabel("Размер эффекта" if is_ru else "Effect size", fontsize=9)
                        ax.set_title(
                            "Forest Plot: все эффекты" if is_ru else "Forest Plot: all effects",
                            fontsize=10,
                            fontweight="bold",
                        )
                        ax.grid(True, axis="x", alpha=0.25, linestyle="--")
                        plt.tight_layout()
                        buf_f = _io.BytesIO()
                        plt.savefig(buf_f, format="png", dpi=150)
                        plt.close()
                        return bytes(buf_f.getvalue())
                except Exception:
                    try:
                        plt.close()
                    except Exception:
                        pass

        plt.figure(figsize=(8, 5))

        plot_data = []
        plot_config = {}
        is_roc_plot = False

        if isinstance(res, dict):
            roc = res.get("roc")
            if isinstance(roc, dict) and isinstance(roc.get("plot_data"), list) and roc.get("plot_data"):
                plot_data = roc.get("plot_data")
                plot_config = roc.get("plot_config") if isinstance(roc.get("plot_config"), dict) else {}
                is_roc_plot = True
            else:
                plot_data = res.get("plot_data", [])
                plot_config = res.get("plot_config") if isinstance(res.get("plot_config"), dict) else {}

        if plot_data:
            df_plot = pd.DataFrame(plot_data)

            if "group" in df_plot.columns and "value" in df_plot.columns:
                sns.boxplot(
                    x="group",
                    y="value",
                    data=df_plot,
                    showfliers=False,
                    color=str(theme.get("box_fill") or "#f1f5f9"),
                    width=0.5,
                )
                sns.stripplot(
                    x="group",
                    y="value",
                    data=df_plot,
                    size=4,
                    alpha=0.6,
                    color=str(theme.get("primary") or "#0f172a"),
                )
                plt.title("Сравнение групп" if is_ru else "Group Comparison")
                plt.xlabel(_format_group_axis_label(res, is_ru))
                plt.ylabel(_format_axis_label(res, is_ru))

                comparisons_raw = None
                if isinstance(res, dict):
                    comparisons_raw = (
                        res.get("comparisons")
                        or res.get("plot_comparisons")
                        or res.get("post_hoc")
                    )

                comparisons = normalize_comparisons(comparisons_raw)

                # --- AUTO BRACKET: generate from p_value for 2-group hypothesis_test ---
                if not comparisons and isinstance(res, dict):
                    p_val = res.get("p_value") or res.get("p_value_adj")
                    group_order = [str(g) for g in df_plot["group"].dropna().unique().tolist()]
                    if p_val is not None and len(group_order) == 2:
                        try:
                            p_f = float(p_val)
                            if np.isfinite(p_f):
                                from app.modules.plot_with_brackets import Comparison

                                comparisons = [Comparison(
                                    a=group_order[0],
                                    b=group_order[1],
                                    p_value=p_f,
                                )]
                        except Exception:
                            pass

                if comparisons:
                    group_order = [str(g) for g in (df_plot["group"].dropna().unique().tolist() or [])]
                    group_index = {g: i for i, g in enumerate(group_order)}

                    values = df_plot["value"].dropna().astype(float)
                    if len(values) > 0:
                        min_val = float(values.min())
                        max_val = float(values.max())
                        y_range = (max_val - min_val) or 1.0
                        base_pad = y_range * 0.08
                        step_pad = y_range * 0.08
                        y_base = max_val + base_pad

                        ranges = []
                        placed = []
                        for c in comparisons:
                            ia = group_index.get(c.a)
                            ib = group_index.get(c.b)
                            if ia is None or ib is None:
                                continue
                            start = min(ia, ib)
                            end = max(ia, ib)

                            level = 0
                            while True:
                                taken = ranges[level] if level < len(ranges) else []
                                overlaps = any(not (end < r[0] or start > r[1]) for r in taken)
                                if not overlaps:
                                    break
                                level += 1
                            while level >= len(ranges):
                                ranges.append([])
                            ranges[level].append((start, end))
                            placed.append((start, end, level, c.p_value))

                        ax = plt.gca()
                        max_level = max((lvl for _, _, lvl, _ in placed), default=-1)
                        try:
                            y0, y1_lim = ax.get_ylim()
                            extra = (max_level + 2) * step_pad
                            ax.set_ylim(y0, max(y1_lim, max_val + base_pad + extra))
                        except Exception:
                            pass
                        for start, end, level, p_value in placed:
                            add_significance_bracket(
                                ax,
                                float(start),
                                float(end),
                                y_base + level * step_pad,
                                p_value,
                                h=0.02,
                                lw=1.2,
                                color=str(theme.get("primary") or "#0f172a"),
                            )

            elif "x" in df_plot.columns and "y" in df_plot.columns:
                plot_type = str(plot_config.get("type") or "").strip().lower()
                if is_roc_plot or plot_type == "roc":
                    df_sorted = df_plot.sort_values("x")
                    plt.plot(df_sorted["x"], df_sorted["y"], color=str(theme.get("accent") or "#8b5cf6"), linewidth=2)
                    plt.plot([0, 1], [0, 1], linestyle="--", color=str(theme.get("diag_line") or "#64748b"), linewidth=1)
                    plt.xlim(0, 1)
                    plt.ylim(0, 1)
                    plt.title("ROC-кривая" if is_ru else "ROC Curve")
                    plt.xlabel("1 − специфичность" if is_ru else "1 − Specificity")
                    plt.ylabel("Чувствительность" if is_ru else "Sensitivity")
                elif plot_type == "line":
                    y_num = pd.to_numeric(df_plot["y"], errors="coerce")
                    keep = np.isfinite(y_num)
                    if keep.any():
                        line_df = df_plot.loc[keep].copy()
                        y_vals = y_num[keep].to_numpy(dtype=float)
                        x_labels = [str(v) for v in line_df["x"].tolist()]
                        x_vals = np.arange(len(y_vals), dtype=float)
                        plt.plot(
                            x_vals,
                            y_vals,
                            color=str(theme.get("accent") or "#8b5cf6"),
                            linewidth=2.2,
                            label=("Ряд" if is_ru else "Series"),
                        )

                        if "trend" in line_df.columns:
                            trend_num = pd.to_numeric(line_df["trend"], errors="coerce")
                            trend_mask = np.isfinite(trend_num)
                            if trend_mask.any():
                                plt.plot(
                                    x_vals[trend_mask.to_numpy()],
                                    trend_num[trend_mask].to_numpy(dtype=float),
                                    color=str(theme.get("secondary") or "#64748b"),
                                    linestyle="--",
                                    linewidth=1.8,
                                    label=("Тренд" if is_ru else "Trend"),
                                )

                        forecast = res.get("forecast") if isinstance(res, dict) else None
                        forecast_points = forecast.get("points") if isinstance(forecast, dict) else None
                        if isinstance(forecast_points, list) and forecast_points:
                            f_x = []
                            f_y = []
                            f_labels = []
                            for i, point in enumerate(forecast_points):
                                if not isinstance(point, dict):
                                    continue
                                yv = point.get("y")
                                try:
                                    y_f = float(yv)
                                except Exception:
                                    continue
                                if not np.isfinite(y_f):
                                    continue
                                f_x.append(float(len(x_vals) + i))
                                f_y.append(y_f)
                                f_labels.append(str(point.get("x") if point.get("x") is not None else f"f{i+1}"))
                            if f_x and f_y:
                                plt.plot(
                                    f_x,
                                    f_y,
                                    color=str(theme.get("accent") or "#8b5cf6"),
                                    linestyle=":",
                                    linewidth=2.0,
                                    label=("Прогноз" if is_ru else "Forecast"),
                                )
                                x_labels.extend(f_labels)

                        n_labels = len(x_labels)
                        if n_labels > 0:
                            step = max(1, int(np.ceil(n_labels / 12)))
                            tick_idx = list(range(0, n_labels, step))
                            if (n_labels - 1) not in tick_idx:
                                tick_idx.append(n_labels - 1)
                            tick_labels = [x_labels[i] if 0 <= i < n_labels else "" for i in tick_idx]
                            plt.xticks(tick_idx, tick_labels, rotation=30, ha="right")

                        plt.title("Временной ряд" if is_ru else "Time Series")
                        plt.xlabel(str(plot_config.get("x_label") or ("Время" if is_ru else "Time")))
                        plt.ylabel(str(plot_config.get("y_label") or ("Значение" if is_ru else "Value")))
                        plt.grid(True, axis="y", alpha=0.25)
                        plt.legend(frameon=False)
                elif plot_type == "bland_altman":
                    x_num = pd.to_numeric(df_plot["x"], errors="coerce")
                    y_num = pd.to_numeric(df_plot["y"], errors="coerce")
                    mask = np.isfinite(x_num) & np.isfinite(y_num)
                    x_vals = x_num[mask]
                    y_vals = y_num[mask]
                    if len(x_vals) > 0:
                        plt.scatter(
                            x_vals,
                            y_vals,
                            s=20,
                            alpha=0.65,
                            color=str(theme.get("accent") or "#8b5cf6"),
                            edgecolors="none",
                        )
                        refs = res.get("plot_reference_lines") if isinstance(res, dict) else None
                        line_defs = []
                        if isinstance(refs, dict):
                            for key in ("mean_difference", "loa_lower", "loa_upper", "zero"):
                                item = refs.get(key)
                                if isinstance(item, dict):
                                    line_defs.append((key, item.get("y")))
                        if not line_defs:
                            line_defs = [
                                ("mean_difference", res.get("mean_difference") if isinstance(res, dict) else None),
                                ("loa_lower", res.get("loa_lower") if isinstance(res, dict) else None),
                                ("loa_upper", res.get("loa_upper") if isinstance(res, dict) else None),
                                ("zero", 0.0),
                            ]
                        for key, value in line_defs:
                            try:
                                y_ref = float(value)
                            except Exception:
                                continue
                            if not np.isfinite(y_ref):
                                continue
                            if key == "mean_difference":
                                color = str(theme.get("accent") or "#8b5cf6")
                                style = "-"
                                width = 1.8
                            elif key in {"loa_lower", "loa_upper"}:
                                color = str(theme.get("secondary") or "#64748b")
                                style = "--"
                                width = 1.4
                            else:
                                color = str(theme.get("diag_line") or "#64748b")
                                style = ":"
                                width = 1.2
                            plt.axhline(y_ref, color=color, linestyle=style, linewidth=width)

                        plt.title("Диаграмма Бланда—Алтмана" if is_ru else "Bland-Altman Plot")
                        plt.xlabel(str(plot_config.get("x_label") or ("Среднее двух методов" if is_ru else "Mean of methods")))
                        plt.ylabel(str(plot_config.get("y_label") or ("Разность методов" if is_ru else "Difference of methods")))
                        plt.grid(True, axis="both", alpha=0.25)
                else:
                    x_num = pd.to_numeric(df_plot["x"], errors="coerce")
                    y_num = pd.to_numeric(df_plot["y"], errors="coerce")
                    mask = np.isfinite(x_num) & np.isfinite(y_num)
                    x_vals = x_num[mask]
                    y_vals = y_num[mask]
                    if len(x_vals) > 800:
                        hb = plt.hexbin(
                            x_vals,
                            y_vals,
                            gridsize=45,
                            cmap=str(theme.get("hexbin_cmap") or "viridis"),
                            mincnt=1,
                        )
                        try:
                            plt.colorbar(hb)
                        except Exception:
                            pass
                    else:
                        scatter_color = palette[0]
                        sns.scatterplot(x=x_vals, y=y_vals, s=18, alpha=0.7, color=scatter_color)

                    try:
                        reg_color = palette[1] if len(palette) > 1 else palette[0]
                        sns.regplot(x=x_vals, y=y_vals, scatter=False, color=reg_color, line_kws={"linewidth": 2})
                    except Exception:
                        pass
                    plt.title("Корреляция" if is_ru else "Correlation Analysis")
                    plt.xlabel(str(res.get("x_label") or "X"))
                    plt.ylabel(str(res.get("y_label") or "Y"))

            elif "probability" in df_plot.columns and "time" in df_plot.columns and "group" in df_plot.columns:
                groups = df_plot["group"].unique()
                for idx, g in enumerate(groups):
                    sub = df_plot[df_plot["group"] == g]
                    plt.step(
                        sub["time"],
                        sub["probability"],
                        where="post",
                        color=palette[idx % len(palette)],
                        label=f"{('Группа' if is_ru else 'Group')} {g}",
                    )
                plt.ylim(0, 1.05)
                plt.legend()
                plt.title("Кривая Каплана — Мейера" if is_ru else "Kaplan-Meier Survival Curve")
                plt.xlabel("Время" if is_ru else "Time")
                plt.ylabel("Вероятность выживания" if is_ru else "Survival probability")

        else:
            plot_stats = res.get("plot_stats", {}) if isinstance(res, dict) else {}
            if plot_stats:
                groups = []
                means = []
                sems = []
                for g, s in plot_stats.items():
                    if not isinstance(s, dict):
                        continue
                    m = s.get("mean")
                    try:
                        m_f = float(m)
                        if not np.isfinite(m_f):
                            continue
                    except Exception:
                        continue
                    sem = s.get("sem")
                    if sem is None:
                        sd = s.get("sd")
                        n = s.get("count")
                        try:
                            if sd is not None and n is not None and float(n) > 1:
                                sem = float(sd) / float(np.sqrt(float(n)))
                        except Exception:
                            sem = None
                    try:
                        sem_f = float(sem) if sem is not None else 0.0
                        if not np.isfinite(sem_f):
                            sem_f = 0.0
                    except Exception:
                        sem_f = 0.0
                    groups.append(str(g))
                    means.append(m_f)
                    sems.append(sem_f)

                if groups:
                    bar_color = str(theme.get("bar_fill") or palette[0])
                    edge_color = str(theme.get("primary") or "#0f172a")
                    plt.bar(groups, means, yerr=sems, capsize=5, color=bar_color, edgecolor=edge_color, alpha=0.8)
                    plot_data = res.get("plot_data") if isinstance(res, dict) else None
                    if isinstance(plot_data, list) and plot_data:
                        group_index = {str(g): i for i, g in enumerate(groups)}
                        rng = np.random.default_rng(42)
                        xs_scatter = []
                        ys_scatter = []
                        for row in plot_data:
                            if not isinstance(row, dict):
                                continue
                            g = row.get("group")
                            v = row.get("value")
                            if g is None or v is None:
                                continue
                            try:
                                yv = float(v)
                            except Exception:
                                continue
                            gi = group_index.get(str(g))
                            if gi is None:
                                continue
                            xs_scatter.append(float(gi) + float(rng.uniform(-0.12, 0.12)))
                            ys_scatter.append(yv)
                        if xs_scatter:
                            plt.scatter(xs_scatter, ys_scatter, s=14, alpha=0.45, color=edge_color, zorder=3)
                plt.title("Сравнение средних (±SEM)" if is_ru else "Mean comparison (±SEM)")
            else:
                plt.text(
                    0.5,
                    0.5,
                    "Нет визуализации" if is_ru else "No Visualization Available",
                    ha="center",
                    va="center",
                    transform=plt.gca().transAxes,
                )

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format="png")
        plt.close()
        return bytes(buf.getvalue())
    except Exception as e:
        logger.error(f"Plotting failed: {e}", exc_info=True)
        try:
            plt.close()
        except Exception:
            pass
        return b""
