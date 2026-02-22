"""
Standard plot templates for publication-quality figures.
Uses configuration from app.modules.plot_config.
"""

import os
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from app.modules.plot_config import apply_publication_config, save_publication_figure, get_group_colors

# Apply config on module import
apply_publication_config()

def plot_group_comparison(
    df: pd.DataFrame,
    x: str,
    y: str,
    output_dir: str,
    filename: str = "group_comparison",
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None
) -> str:
    """
    Generate Boxplot + Stripplot for group comparison.
    
    Args:
        df: DataFrame
        x: Grouping variable (categorical)
        y: Outcome variable (continuous)
        output_dir: Directory to save the plot
        filename: Filename (without extension)
        title: Plot title
        
    Returns:
        Absolute path to the saved PNG file.
    """
    fig, ax = plt.subplots()
    
    # Get colors
    n_groups = df[x].nunique()
    palette = get_group_colors(n_groups)

    # Boxplot
    sns.boxplot(
        data=df, x=x, y=y,
        hue=x, legend=False,
        showfliers=False,
        boxprops={'alpha': 0.4},
        palette=palette,
        ax=ax
    )
    
    # Stripplot
    sns.stripplot(
        data=df, x=x, y=y,
        color=".2",
        alpha=0.6,
        jitter=True,
        size=4,
        ax=ax
    )
    
    if title: ax.set_title(title)
    if xlabel: ax.set_xlabel(xlabel)
    if ylabel: ax.set_ylabel(ylabel)
    
    # Save
    os.makedirs(output_dir, exist_ok=True)
    paths = save_publication_figure(fig, os.path.join(output_dir, filename), formats=['png'])
    plt.close(fig)
    
    return os.path.abspath(paths[0]) # Return PNG path


def plot_correlation_matrix(
    corr_matrix: pd.DataFrame,
    output_dir: str,
    filename: str = "correlation_matrix",
    title: str = "Correlation Matrix"
) -> str:
    """
    Generate Heatmap for correlation matrix.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # Mask for upper triangle
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
    
    sns.heatmap(
        corr_matrix,
        mask=mask,
        cmap="RdBu_r",
        vmax=1, vmin=-1,
        center=0,
        square=True,
        linewidths=.5,
        cbar_kws={"shrink": .5},
        annot=True,
        fmt=".2f",
        annot_kws={"size": 8},
        ax=ax
    )
    
    if title: ax.set_title(title)
    
    os.makedirs(output_dir, exist_ok=True)
    paths = save_publication_figure(fig, os.path.join(output_dir, filename), formats=['png'])
    plt.close(fig)
    
    return os.path.abspath(paths[0])


def plot_distribution(
    df: pd.DataFrame,
    col: str,
    output_dir: str,
    filename: Optional[str] = None,
    title: Optional[str] = None
) -> str:
    """
    Generate Histogram + KDE for a single variable.
    """
    if filename is None:
        filename = f"dist_{col}"
        
    fig, ax = plt.subplots()
    
    sns.histplot(
        data=df, x=col,
        kde=True,
        color=sns.color_palette("colorblind")[0],
        line_kws={'linewidth': 2},
        alpha=0.3,
        ax=ax
    )
    
    if title: ax.set_title(title)
    
    os.makedirs(output_dir, exist_ok=True)
    paths = save_publication_figure(fig, os.path.join(output_dir, filename), formats=['png'])
    plt.close(fig)
    
    return os.path.abspath(paths[0])


def plot_regression(
    df: pd.DataFrame,
    x: str,
    y: str,
    output_dir: str,
    filename: str = "regression_plot",
    title: Optional[str] = None
) -> str:
    """
    Generate Scatter + Regression Line.
    """
    fig, ax = plt.subplots()
    
    sns.regplot(
        data=df, x=x, y=y,
        scatter_kws={'alpha': 0.5, 's': 30},
        line_kws={'color': 'black', 'linewidth': 1.5},
        color=sns.color_palette("colorblind")[0],
        ax=ax
    )
    
    if title: ax.set_title(title)
    
    os.makedirs(output_dir, exist_ok=True)
    paths = save_publication_figure(fig, os.path.join(output_dir, filename), formats=['png'])
    plt.close(fig)
    
    return os.path.abspath(paths[0])
