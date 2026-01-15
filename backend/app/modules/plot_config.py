from __future__ import annotations

from typing import Any, Dict

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns


PUBLICATION_CONFIG: Dict[str, Any] = {
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 1.0,
    "xtick.major.width": 1.0,
    "ytick.major.width": 1.0,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
}


_APPLIED = False


def apply_publication_config() -> None:
    global _APPLIED
    if _APPLIED:
        return

    plt.rcParams.update(PUBLICATION_CONFIG)
    sns.set_theme(style="whitegrid", palette="colorblind")
    matplotlib.rcParams["axes.unicode_minus"] = False

    _APPLIED = True

