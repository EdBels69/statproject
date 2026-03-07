import math
from typing import Any, Dict, List, Optional


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        v = float(value)
        if not math.isfinite(v):
            return None
        return v
    except Exception:
        return None


def _to_method_id(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    normalized = "_".join(text.replace("-", "_").split())
    aliases = {
        "mixed_model": "mixed_effects",
        "linear_mixed_model": "mixed_effects",
        "fisher": "fisher_exact",
        "welch_t_test": "t_test_welch",
        "kruskal_wallis": "kruskal",
        "two_way_anova": "anova_twoway",
        "bayesian_t_test_one": "bayes_t_test_one",
        "bayesian_t_test_ind": "bayes_t_test_ind",
        "bayesian_t_test_rel": "bayes_t_test_rel",
        "bayesian_correlation": "bayes_correlation",
        "bayesian_anova": "bayes_anova",
        "bayesian_linear_regression": "bayes_linear_regression",
        "bayesian_chi_square": "bayes_chi_square",
        "bayes_regression": "bayes_linear_regression",
        "time_series": "time_series_analysis",
        "timeseries": "time_series_analysis",
    }
    return aliases.get(normalized, normalized)


def _normalize_engine(value: Any) -> Optional[str]:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"py", "python", "python3"}:
        return "python"
    if text in {"r", "r_engine", "rstats"}:
        return "r"
    return None


def _normalize_warnings(payload: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    raw = payload.get("warnings")
    if isinstance(raw, list):
        for item in raw:
            text = str(item or "").strip()
            if text:
                out.append(text)
    warning_one = payload.get("warning")
    if warning_one is not None:
        text = str(warning_one).strip()
        if text:
            out.append(text)
    return out


def _normalize_plots(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = payload.get("plots")
    if isinstance(raw, list):
        out: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw):
            if isinstance(item, dict):
                plot_id = str(item.get("id") or f"plot_{idx + 1}").strip()
                kind = str(item.get("kind") or item.get("type") or "plot").strip()
                out.append({"id": plot_id or f"plot_{idx + 1}", "kind": kind or "plot"})
            else:
                text = str(item or "").strip()
                if text:
                    out.append({"id": f"plot_{idx + 1}", "kind": text})
        return out

    inferred: List[Dict[str, Any]] = []

    def _add_plot(plot_id: str, kind: str) -> None:
        for existing in inferred:
            if str(existing.get("id")) == plot_id:
                return
        inferred.append({"id": plot_id, "kind": kind})

    if isinstance(payload.get("plot_data"), list) and payload.get("plot_data"):
        _add_plot("main", "plot_data")
    if isinstance(payload.get("plot_stats"), dict) and payload.get("plot_stats"):
        _add_plot("summary", "plot_stats")
    plot_image_b64 = payload.get("plot_image_b64")
    if isinstance(plot_image_b64, str) and plot_image_b64.strip():
        _add_plot("main_image", "plot_image")
    if isinstance(payload.get("heatmap_data"), list) and payload.get("heatmap_data"):
        _add_plot("heatmap", "heatmap")
    if isinstance(payload.get("correlation_matrix"), dict) and payload.get("correlation_matrix"):
        _add_plot("correlation_matrix", "matrix")
    roc = payload.get("roc")
    if isinstance(roc, dict) and isinstance(roc.get("plot_data"), list) and roc.get("plot_data"):
        _add_plot("roc", "roc_curve")
    if isinstance(payload.get("dendrogram"), dict) and payload.get("dendrogram"):
        _add_plot("dendrogram", "dendrogram")
    return inferred


def _normalize_diagnostics(payload: Dict[str, Any]) -> Dict[str, Any]:
    diagnostics = payload.get("diagnostics")
    out = diagnostics.copy() if isinstance(diagnostics, dict) else {}

    assumptions = payload.get("assumptions")
    if isinstance(assumptions, dict) and assumptions and "assumptions" not in out:
        out["assumptions"] = assumptions

    for key in ["n", "n_observations", "n_subjects", "n_variables", "n_clusters", "total_pairs"]:
        if key in payload and payload.get(key) is not None:
            out[key] = payload.get(key)

    if isinstance(payload.get("delta_summary"), dict):
        out["delta_summary"] = payload.get("delta_summary")

    if payload.get("error") is not None:
        out["error"] = payload.get("error")

    result_type = payload.get("type")
    if isinstance(result_type, str) and result_type.strip():
        out.setdefault("result_type", result_type.strip())

    if payload.get("mode") is not None:
        out.setdefault("mode", payload.get("mode"))

    return out


def normalize_analysis_result_v2(
    payload: Any,
    *,
    method_id: Any = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = payload.copy() if isinstance(payload, dict) else {"value": payload}
    cfg = config if isinstance(config, dict) else {}

    method_obj = base.get("method")
    method_id_from_method = None
    if isinstance(method_obj, dict):
        method_id_from_method = _to_method_id(method_obj.get("id") or method_obj.get("method_id"))
    elif isinstance(method_obj, str):
        method_id_from_method = _to_method_id(method_obj)

    method_id_from_payload = _to_method_id(base.get("method_id"))
    method_id_from_arg = _to_method_id(method_id)
    resolved_method_id = method_id_from_payload or method_id_from_arg or method_id_from_method or "unknown"

    if isinstance(method_obj, str):
        base["method"] = {"id": resolved_method_id, "name": method_obj}
    elif not isinstance(method_obj, dict):
        base["method"] = {"id": resolved_method_id, "name": resolved_method_id}
    elif not method_obj.get("id") or not method_obj.get("name"):
        next_method = dict(method_obj)
        if not next_method.get("id"):
            next_method["id"] = resolved_method_id
        if not next_method.get("name"):
            next_method["name"] = str(next_method.get("id") or resolved_method_id)
        base["method"] = next_method

    engine = (
        _normalize_engine(base.get("engine"))
        or _normalize_engine(base.get("stats_engine"))
        or _normalize_engine(base.get("analysis_engine"))
        or _normalize_engine(cfg.get("engine"))
        or _normalize_engine(cfg.get("stats_engine"))
        or _normalize_engine(cfg.get("analysis_engine"))
        or "python"
    )

    stat_value = _to_float(base.get("stat_value"))
    if stat_value is None:
        stat_value = _to_float(base.get("stats"))

    p_value = _to_float(base.get("p_value"))
    effect_size = _to_float(base.get("effect_size"))

    if base.get("effect_size_ci_lower") is None and base.get("effect_ci_lower") is not None:
        base["effect_size_ci_lower"] = base.get("effect_ci_lower")
    if base.get("effect_size_ci_upper") is None and base.get("effect_ci_upper") is not None:
        base["effect_size_ci_upper"] = base.get("effect_ci_upper")

    base["method_id"] = resolved_method_id
    base["engine"] = engine
    base["stat_value"] = stat_value
    base["p_value"] = p_value
    base["effect_size"] = effect_size
    base["diagnostics"] = _normalize_diagnostics(base)
    base["warnings"] = _normalize_warnings(base)
    base["plots"] = _normalize_plots(base)
    return base


def normalize_results_map(
    results: Any,
    step_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(results, dict):
        return {}
    step_meta = step_meta if isinstance(step_meta, dict) else {}
    out: Dict[str, Any] = {}
    for step_id, payload in results.items():
        meta = step_meta.get(step_id) if isinstance(step_meta.get(step_id), dict) else {}
        out[str(step_id)] = normalize_analysis_result_v2(
            payload,
            method_id=meta.get("method"),
            config=meta.get("config") if isinstance(meta.get("config"), dict) else {},
        )
    return out


def normalize_results_list(
    items: Any,
    step_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []
    step_meta = step_meta if isinstance(step_meta, dict) else {}
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            out.append({"step_id": f"step_{idx + 1}", "status": "completed", "results": normalize_analysis_result_v2(item)})
            continue

        step_id = str(item.get("step_id") or item.get("id") or f"step_{idx + 1}")
        method_hint = item.get("method")
        meta = step_meta.get(step_id) if isinstance(step_meta.get(step_id), dict) else {}

        payload = item.get("results")
        if "results" not in item:
            payload = item.get("payload")

        normalized_payload = normalize_analysis_result_v2(
            payload,
            method_id=method_hint or meta.get("method"),
            config=meta.get("config") if isinstance(meta.get("config"), dict) else {},
        )

        next_item = dict(item)
        next_item["step_id"] = step_id
        next_item["method"] = normalized_payload.get("method_id")
        next_item["results"] = normalized_payload
        out.append(next_item)
    return out


def normalize_run_data_results(run_data: Any) -> Dict[str, Any]:
    if not isinstance(run_data, dict):
        return {}
    step_meta = run_data.get("step_meta") if isinstance(run_data.get("step_meta"), dict) else {}
    out = dict(run_data)
    results = out.get("results")
    if isinstance(results, dict):
        out["results"] = normalize_results_map(results, step_meta=step_meta)
    elif isinstance(results, list):
        out["results"] = normalize_results_list(results, step_meta=step_meta)
    return out
