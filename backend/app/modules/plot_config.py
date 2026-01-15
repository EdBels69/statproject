"""
Publication-ready plot configuration.

Based on:
- Nathan Yau "Visualize This" (FlowingData)
- Edward Tufte data-ink principles
- SCIENTIFIC_STANDARDS.md guidelines

Usage:
    from app.modules.plot_config import apply_publication_config
    apply_publication_config()
    fig, ax = plt.subplots()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import io

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns


# =============================================================================
# COLOR PALETTES (FlowingData style)
# =============================================================================

COLORS = {
    'primary': '#0f172a',     # Dark slate (main data)
    'secondary': '#64748b',   # Gray (secondary data)
    'accent': '#8b5cf6',      # Purple (highlights)
    'positive': '#10b981',    # Green (significant)
    'negative': '#ef4444',    # Red (errors)
    'neutral': '#f1f5f9',     # Light background
    'white': '#ffffff',
    'black': '#000000',
}

# Colorblind-safe palette for groups (max 8)
GROUP_PALETTE: List[str] = [
    '#4269d0',  # Blue
    '#ef9154',  # Orange
    '#4ca858',  # Green
    '#db4949',  # Red
    '#8b5cf6',  # Purple
    '#14b8a6',  # Teal
    '#f59e0b',  # Amber
    '#6366f1',  # Indigo
]


# =============================================================================
# PUBLICATION CONFIG (Nathan Yau + Tufte principles)
# =============================================================================

PUBLICATION_CONFIG: Dict[str, Any] = {
    # Figure
    "figure.figsize": (7, 5),
    "figure.dpi": 300,
    "figure.facecolor": "white",
    "figure.edgecolor": "none",
    
    # Saving
    "savefig.dpi": 300,
    "savefig.facecolor": "white",
    "savefig.edgecolor": "none",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.1,
    
    # Font (Helvetica Neue style)
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "figure.titlesize": 14,
    
    # Axes (minimal style)
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.5,
    "axes.edgecolor": "#64748b",
    "axes.labelcolor": "#0f172a",
    "axes.titleweight": "normal",
    "axes.titlepad": 15,
    
    # Ticks
    "xtick.major.width": 0.5,
    "ytick.major.width": 0.5,
    "xtick.color": "#64748b",
    "ytick.color": "#64748b",
    "xtick.direction": "out",
    "ytick.direction": "out",
    
    # Grid (subtle)
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.linewidth": 0.3,
    "grid.alpha": 0.2,
    "grid.color": "#94a3b8",
    "axes.axisbelow": True,
    
    # Legend
    "legend.frameon": False,
    "legend.loc": "upper right",
    
    # Lines
    "lines.linewidth": 1.5,
    "lines.markersize": 6,
}


# =============================================================================
# SCREEN CONFIG (for web display)
# =============================================================================

SCREEN_CONFIG: Dict[str, Any] = {
    **PUBLICATION_CONFIG,
    "figure.figsize": (8, 5),
    "figure.dpi": 100,
    "savefig.dpi": 150,
}


_APPLIED = False


def apply_publication_config() -> None:
    """Apply publication-ready configuration to all matplotlib plots."""
    global _APPLIED
    if _APPLIED:
        return

    plt.rcParams.update(PUBLICATION_CONFIG)
    sns.set_theme(style="whitegrid", palette="colorblind")
    matplotlib.rcParams["axes.unicode_minus"] = False

    _APPLIED = True


def apply_screen_config() -> None:
    """Apply screen-optimized configuration (lower DPI, larger size)."""
    plt.rcParams.update(SCREEN_CONFIG)
    sns.set_theme(style="whitegrid", palette="colorblind")
    matplotlib.rcParams["axes.unicode_minus"] = False


def reset_config() -> None:
    """Reset to matplotlib defaults."""
    global _APPLIED
    matplotlib.rcdefaults()
    _APPLIED = False


def get_group_colors(n: int) -> List[str]:
    """Get n colorblind-safe colors for groups."""
    if n <= len(GROUP_PALETTE):
        return GROUP_PALETTE[:n]
    # Fallback: extend with seaborn colorblind palette
    extended = sns.color_palette("colorblind", n)
    return [matplotlib.colors.to_hex(c) for c in extended]


def save_publication_figure(
    fig: plt.Figure,
    filename: str,
    formats: Optional[List[str]] = None
) -> List[str]:
    """
    Save figure in multiple formats for publication.
    
    Args:
        fig: matplotlib Figure object
        filename: base filename (without extension)
        formats: list of formats ['pdf', 'png', 'svg']. Default: ['pdf', 'png']
    
    Returns:
        List of saved file paths
    """
    if formats is None:
        formats = ['pdf', 'png']
    
    saved_files = []
    for fmt in formats:
        filepath = f"{filename}.{fmt}"
        fig.savefig(
            filepath,
            format=fmt,
            dpi=300,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none'
        )
        saved_files.append(filepath)
    
    return saved_files


def fig_to_png_bytes(fig: plt.Figure, dpi: int = 150) -> bytes:
    """Convert matplotlib figure to PNG bytes for embedding."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    return buf.getvalue()


def style_axis_minimal(ax: plt.Axes) -> plt.Axes:
    """Apply minimal FlowingData style to a single axis."""
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_linewidth(0.5)
    ax.spines['left'].set_color('#64748b')
    ax.spines['bottom'].set_color('#64748b')
    ax.tick_params(colors='#64748b', width=0.5)
    ax.yaxis.grid(True, alpha=0.2, linewidth=0.3)
    ax.set_axisbelow(True)
    return ax

