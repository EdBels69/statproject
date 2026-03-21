from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from app.modules.plot_config import apply_publication_config, style_axis_minimal, GROUP_PALETTE


def _require_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a pandas DataFrame")
    if df.empty:
        raise ValueError("df is empty")
    return df


def _require_series(data: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(data), dtype=float)
    if arr.size == 0:
        raise ValueError("data is empty")
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        raise ValueError("data has no finite values")
    return arr


def plot_group_comparison(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
    order: Optional[Sequence[str]] = None,
) -> Tuple[plt.Figure, plt.Axes]:
    _require_dataframe(df)
    if x not in df.columns or y not in df.columns:
        raise ValueError("x or y column not found")

    data = df[[x, y]].dropna()
    if data.empty:
        raise ValueError("no data after dropping missing values")

    apply_publication_config()
    fig, ax = plt.subplots()

    order_list = list(order) if order else None
    sns.boxplot(
        x=x,
        y=y,
        data=data,
        order=order_list,
        palette=GROUP_PALETTE,
        showfliers=False,
        ax=ax,
    )
    sns.stripplot(
        x=x,
        y=y,
        data=data,
        order=order_list,
        color="#0f172a",
        size=4,
        alpha=0.6,
        dodge=True,
        ax=ax,
    )

    ax.set_title(title or "Сравнение групп")
    ax.set_xlabel(xlabel or str(x))
    ax.set_ylabel(ylabel or str(y))
    style_axis_minimal(ax)
    fig.tight_layout()
    return fig, ax


def plot_correlation_matrix(
    corr_matrix: pd.DataFrame | np.ndarray,
    labels: Optional[Sequence[str]] = None,
    title: Optional[str] = None,
) -> Tuple[plt.Figure, plt.Axes]:
    if isinstance(corr_matrix, pd.DataFrame):
        values = corr_matrix.to_numpy(dtype=float)
        x_labels = [str(x) for x in corr_matrix.columns.tolist()]
        y_labels = [str(x) for x in corr_matrix.index.tolist()]
    else:
        values = np.asarray(corr_matrix, dtype=float)
        x_labels = [str(x) for x in labels] if labels else None
        y_labels = x_labels

    if values.size == 0:
        raise ValueError("corr_matrix is empty")

    apply_publication_config()
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    sns.heatmap(
        values,
        vmin=-1,
        vmax=1,
        cmap="vlag",
        center=0,
        square=True,
        cbar=True,
        xticklabels=x_labels if x_labels else True,
        yticklabels=y_labels if y_labels else True,
        ax=ax,
    )
    ax.set_title(title or "Корреляционная матрица")
    ax.tick_params(axis="x", labelrotation=60, labelsize=8)
    ax.tick_params(axis="y", labelrotation=0, labelsize=8)
    fig.tight_layout()
    return fig, ax


def plot_distribution(
    data: Iterable[float],
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    bins: int = 30,
) -> Tuple[plt.Figure, plt.Axes]:
    arr = _require_series(data)

    apply_publication_config()
    fig, ax = plt.subplots()
    sns.histplot(arr, bins=int(bins), kde=True, ax=ax, color="#4269d0")
    ax.set_title(title or "Распределение")
    ax.set_xlabel(xlabel or "Значение")
    ax.set_ylabel("Частота")
    style_axis_minimal(ax)
    fig.tight_layout()
    return fig, ax


def plot_regression(
    x: Iterable[float],
    y: Iterable[float],
    model: Optional[object] = None,
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: Optional[str] = None,
) -> Tuple[plt.Figure, plt.Axes]:
    x_arr = _require_series(x)
    y_arr = _require_series(y)

    if x_arr.shape[0] != y_arr.shape[0]:
        raise ValueError("x and y must have the same length")

    apply_publication_config()
    fig, ax = plt.subplots()

    ax.scatter(x_arr, y_arr, s=24, alpha=0.7, color="#0f172a")
    if model is None:
        sns.regplot(x=x_arr, y=y_arr, scatter=False, ax=ax, color="#ef4444")
    elif hasattr(model, "predict"):
        xs = np.sort(x_arr)
        try:
            ys = model.predict(xs.reshape(-1, 1))
        except Exception:
            ys = model.predict(xs)
        ax.plot(xs, ys, color="#ef4444", linewidth=1.8)

    ax.set_title(title or "Регрессия")
    ax.set_xlabel(xlabel or "X")
    ax.set_ylabel(ylabel or "Y")
    style_axis_minimal(ax)
    fig.tight_layout()
    return fig, ax
