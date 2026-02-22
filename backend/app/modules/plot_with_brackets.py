from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import matplotlib.axes


def format_significance_label(p_value: float) -> str:
    try:
        p = float(p_value)
    except Exception:
        return ""

    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def add_significance_bracket(
    ax: matplotlib.axes.Axes,
    x1: float,
    x2: float,
    y: float,
    p_value: float,
    h: float = 0.02,
    lw: float = 1.2,
    color: str = "#111111",
    font_size: int = 12,
    font_weight: int = 700,
) -> None:
    try:
        y0, y1_lim = ax.get_ylim()
        y_range = (y1_lim - y0) or 1.0
    except Exception:
        y_range = 1.0

    height = float(h) * float(y_range)
    y_top = y + height

    ax.plot([x1, x1, x2, x2], [y, y_top, y_top, y], lw=lw, c=color, solid_capstyle="butt")

    label = format_significance_label(p_value)
    if not label:
        return

    ax.text(
        (x1 + x2) / 2,
        y_top + (0.01 * y_range),
        label,
        ha="center",
        va="bottom",
        fontsize=font_size,
        fontweight=font_weight,
        color=color,
    )


@dataclass(frozen=True)
class Comparison:
    a: str
    b: str
    p_value: float


def normalize_comparisons(raw: Optional[Iterable[object]]) -> list[Comparison]:
    if not raw:
        return []

    out: list[Comparison] = []
    for c in raw:
        if isinstance(c, dict):
            a = c.get("a") or c.get("group1") or c.get("left")
            b = c.get("b") or c.get("group2") or c.get("right")
            p = c.get("p_value")
        else:
            a = getattr(c, "a", None)
            b = getattr(c, "b", None)
            p = getattr(c, "p_value", None)

        if a is None or b is None:
            continue

        try:
            p_f = float(p)
        except Exception:
            continue

        out.append(Comparison(a=str(a), b=str(b), p_value=p_f))

    return out

