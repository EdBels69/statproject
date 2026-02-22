import json
import os
import subprocess
import tempfile
import base64
from typing import Any, Callable, Dict, Optional, List

import pandas as pd

from app.core.logging import logger


R_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "r_engine.R")


def _collect_columns(
    col_a: Optional[str],
    col_b: Optional[str],
    predictors: Optional[List[str]] = None,
    variables: Optional[List[str]] = None,
    group1: Optional[str] = None,
    group2: Optional[str] = None,
    group_col: Optional[str] = None,
    time_col: Optional[str] = None,
    subject_col: Optional[str] = None,
    outcome_cols: Optional[List[str]] = None,
) -> List[str]:
    cols: List[str] = []
    for c in [col_a, col_b, group1, group2, group_col, time_col, subject_col]:
        if c and c not in cols:
            cols.append(c)
    if isinstance(predictors, list):
        for c in predictors:
            if c and c not in cols:
                cols.append(c)
    if isinstance(variables, list):
        for c in variables:
            if c and c not in cols:
                cols.append(c)
    if isinstance(outcome_cols, list):
        for c in outcome_cols:
            if c and c not in cols:
                cols.append(c)
    return cols


def _prepare_payload(
    df: pd.DataFrame,
    method_id: str,
    col_a: str,
    col_b: str,
    *,
    alpha: float,
    is_paired: bool,
    predictors: Optional[List[str]] = None,
    variables: Optional[List[str]] = None,
    cluster_method: Optional[str] = None,
    linkage_method: Optional[str] = None,
    n_clusters: Optional[int] = None,
    distance_threshold: Optional[float] = None,
    show_p_values: Optional[bool] = None,
    group1: Optional[str] = None,
    group2: Optional[str] = None,
    group_col: Optional[str] = None,
    time_col: Optional[str] = None,
    subject_col: Optional[str] = None,
    outcome_cols: Optional[List[str]] = None,
    time_labels: Optional[List[str]] = None,
    alternative: Optional[str] = None,
    plot_engine: Optional[str] = None,
) -> Dict[str, Any]:
    cols = _collect_columns(
        col_a,
        col_b,
        predictors=predictors,
        variables=variables,
        group1=group1,
        group2=group2,
        group_col=group_col,
        time_col=time_col,
        subject_col=subject_col,
        outcome_cols=outcome_cols,
    )
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return {}

    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    force_factor = [c for c in [group_col, time_col, subject_col] if c]
    payload: Dict[str, Any] = {
        "method_id": str(method_id),
        "col_a": col_a,
        "col_b": col_b,
        "alpha": float(alpha),
        "is_paired": bool(is_paired),
        "predictors": predictors or [],
        "variables": variables or [],
        "cluster_method": cluster_method or "pearson",
        "linkage_method": linkage_method or "ward",
        "n_clusters": int(n_clusters) if isinstance(n_clusters, int) else None,
        "distance_threshold": float(distance_threshold) if isinstance(distance_threshold, (int, float)) else None,
        "show_p_values": bool(show_p_values) if isinstance(show_p_values, bool) else True,
        "group1": group1 or col_b,
        "group2": group2,
        "group_col": group_col,
        "time_col": time_col,
        "subject_col": subject_col,
        "outcome_cols": outcome_cols or [],
        "time_labels": time_labels or [],
        "alternative": alternative or "two-sided",
        "plot_engine": plot_engine or "python",
        "numeric_cols": numeric_cols,
        "force_factor_cols": force_factor,
    }
    payload["columns"] = cols
    return payload


def _run_r_stats(payload: Dict[str, Any], df: pd.DataFrame) -> Dict[str, Any]:
    if not payload:
        return {"status": "error", "error": "empty payload"}

    if not os.path.exists(R_SCRIPT_PATH):
        return {"status": "error", "error": "r_engine.R not found"}

    cols = payload.get("columns") or []
    df_sub = df[cols].copy() if cols else df.copy()

    with tempfile.TemporaryDirectory(prefix="r_engine_") as tmpdir:
        data_path = os.path.join(tmpdir, "data.csv")
        input_path = os.path.join(tmpdir, "input.json")
        output_path = os.path.join(tmpdir, "output.json")
        plot_path = os.path.join(tmpdir, "plot.png")

        df_sub.to_csv(data_path, index=False)
        payload = dict(payload)
        payload["data_path"] = data_path
        payload["plot_path"] = plot_path

        with open(input_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

        cmd = ["Rscript", R_SCRIPT_PATH, input_path, output_path]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=90,
            )
        except Exception as e:
            return {"status": "error", "error": f"Rscript failed: {e}"}

        if proc.returncode != 0:
            return {
                "status": "error",
                "error": proc.stderr.strip() or "Rscript exited with error",
            }

        if not os.path.exists(output_path):
            return {"status": "error", "error": "R output missing"}

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                if os.path.exists(plot_path):
                    try:
                        with open(plot_path, "rb") as pf:
                            data["plot_image_b64"] = base64.b64encode(pf.read()).decode("utf-8")
                    except Exception:
                        pass
                return data
            return {"status": "error", "error": "Invalid R output"}
        except Exception as e:
            return {"status": "error", "error": f"R output read failed: {e}"}


def run_analysis_r(
    df: pd.DataFrame,
    method_id: str,
    col_a: str,
    col_b: str,
    *,
    is_paired: bool = False,
    alpha: float = 0.05,
    python_fallback: Optional[Callable[..., Dict[str, Any]]] = None,
    **kwargs,
) -> Dict[str, Any]:
    base_result: Optional[Dict[str, Any]] = None
    fallback_error: Optional[str] = None

    if python_fallback is not None:
        try:
            base_result = python_fallback(
                df,
                method_id,
                col_a,
                col_b,
                is_paired=is_paired,
                alpha=alpha,
                **kwargs,
            )
        except Exception as e:
            fallback_error = str(e)

    predictors = kwargs.get("predictors")
    variables = kwargs.get("variables")
    cluster_method = kwargs.get("method") or kwargs.get("correlation_method")
    linkage_method = kwargs.get("linkage_method")
    n_clusters = kwargs.get("n_clusters")
    distance_threshold = kwargs.get("distance_threshold")
    show_p_values = kwargs.get("show_p_values")
    group1 = kwargs.get("group1") or kwargs.get("factor_a")
    group2 = kwargs.get("group2") or kwargs.get("factor_b")
    group_col = kwargs.get("group_col")
    time_col = kwargs.get("time_col")
    subject_col = kwargs.get("subject_col")
    outcome_cols = kwargs.get("outcome_cols")
    time_labels = kwargs.get("time_labels")
    alternative = kwargs.get("alternative")
    plot_engine = kwargs.get("plot_engine")

    payload = _prepare_payload(
        df,
        method_id,
        col_a,
        col_b,
        alpha=alpha,
        is_paired=is_paired,
        predictors=predictors if isinstance(predictors, list) else None,
        variables=variables if isinstance(variables, list) else None,
        cluster_method=cluster_method if isinstance(cluster_method, str) else None,
        linkage_method=linkage_method if isinstance(linkage_method, str) else None,
        n_clusters=n_clusters if isinstance(n_clusters, int) else None,
        distance_threshold=distance_threshold if isinstance(distance_threshold, (int, float)) else None,
        show_p_values=show_p_values if isinstance(show_p_values, bool) else None,
        group1=group1 if isinstance(group1, str) else None,
        group2=group2 if isinstance(group2, str) else None,
        group_col=group_col if isinstance(group_col, str) else None,
        time_col=time_col if isinstance(time_col, str) else None,
        subject_col=subject_col if isinstance(subject_col, str) else None,
        outcome_cols=outcome_cols if isinstance(outcome_cols, list) else None,
        time_labels=time_labels if isinstance(time_labels, list) else None,
        alternative=alternative if isinstance(alternative, str) else None,
        # plotting
        plot_engine=plot_engine if isinstance(plot_engine, str) else None,
    )

    r_result = _run_r_stats(payload, df)
    if not isinstance(r_result, dict) or r_result.get("status") == "error":
        if base_result is not None:
            warnings = base_result.get("warnings") if isinstance(base_result.get("warnings"), list) else []
            err_msg = r_result.get("error") if isinstance(r_result, dict) else None
            if err_msg:
                warnings.append(f"R engine failed: {err_msg}")
            if fallback_error:
                warnings.append(f"Python fallback error: {fallback_error}")
            base_result["warnings"] = warnings
            base_result["engine"] = "python"
            return base_result
        raise ValueError(r_result.get("error") if isinstance(r_result, dict) else "R engine failed")

    out: Dict[str, Any] = base_result if isinstance(base_result, dict) else {}
    if "warnings" not in out or not isinstance(out.get("warnings"), list):
        out["warnings"] = []
    if fallback_error:
        out["warnings"].append(f"Python fallback error: {fallback_error}")

    for key in [
        "p_value",
        "stat_value",
        "effect_size",
        "effect_size_name",
        "effect_size_ci_lower",
        "effect_size_ci_upper",
        "r_squared",
        "effects",
        "n_observations",
        "n_variables",
        "n_clusters",
        "linkage",
        "correlation_matrix",
        "original_order",
        "cluster_assignments",
        "clusters",
        "heatmap_data",
        "dendrogram",
    ]:
        if key in r_result and r_result.get(key) is not None:
            out[key] = r_result.get(key)

    if "roc_auc" in r_result and r_result.get("roc_auc") is not None:
        roc = out.get("roc") if isinstance(out.get("roc"), dict) else {}
        roc["auc"] = r_result.get("roc_auc")
        out["roc"] = roc

    if "plot_image_b64" in r_result:
        out["plot_image_b64"] = r_result.get("plot_image_b64")

    out["engine"] = "r"
    if "p_value" in out and out.get("p_value") is not None:
        try:
            out["significant"] = float(out["p_value"]) < float(alpha)
        except Exception:
            pass

    return out
