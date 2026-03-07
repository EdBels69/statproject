"""Builders and policy utilities extracted from API v2."""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
from datetime import datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.api.datasets import DATA_DIR
from app.api.helpers import (
    _as_bool,
    _as_str_list,
    _canonical_method_id,
    _finite_float,
    _normalize_correction,
    _normalize_validation_profile,
    _resolve_llm_benchmark_score_profile as _helpers_resolve_llm_benchmark_score_profile,
)
from app.copilot.verification_policy import (
    attempt_verifier_reflection_repair as _vp_attempt_verifier_reflection_repair,
    extract_step_p_value as _vp_extract_step_p_value,
    iter_result_payload_entries as _vp_iter_result_payload_entries,
    repair_run_payload_multiplicity as _vp_repair_run_payload_multiplicity,
    repair_run_payload_p_bounds as _vp_repair_run_payload_p_bounds,
)
from app.core.artifact_contracts import assert_artifact_contract
from app.core.logging import logger
from app.core.pipeline import PipelineManager
from app.modules.hypothesis_discovery import build_hypothesis_discovery
from app.stats.engine import _safe_bootstrap_samples

pipeline = PipelineManager(DATA_DIR)

DEFAULT_BOOTSTRAP_SAMPLES = 1000

BOOTSTRAP_COMPATIBLE_METHODS = {
    "auto",
    "batch_analysis",
    "timepoint_batch_analysis",
    "delta_batch_analysis",
    "paired_wide",
    "t_test_one",
    "t_test_ind",
    "t_test_welch",
    "mann_whitney",
    "t_test_rel",
    "wilcoxon",
    "anova",
    "anova_welch",
    "kruskal",
    "pearson",
    "spearman",
    "kendall",
    "linear_regression",
    "logistic_regression",
    "ancova",
    "bayes_t_test_one",
    "bayes_t_test_ind",
    "bayes_t_test_rel",
    "bayes_correlation",
    "bayes_anova",
    "bayes_linear_regression",
}

MULTIPLICITY_BATCH_METHODS = {
    "batch_analysis",
    "timepoint_batch_analysis",
    "delta_batch_analysis",
}

MULTIPLICITY_POSTHOC_METHODS = {
    "auto",
    "anova",
    "anova_welch",
    "kruskal",
}

MULTIPLICITY_COMPATIBLE_METHODS = MULTIPLICITY_BATCH_METHODS.union(
    MULTIPLICITY_POSTHOC_METHODS
)


def _resolve_llm_benchmark_score_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    return _helpers_resolve_llm_benchmark_score_profile(row)


def _normalize_bootstrap_samples(value: Any, default: int = DEFAULT_BOOTSTRAP_SAMPLES) -> int:
    return int(_safe_bootstrap_samples(value, default=default))

def _safe_build_hypothesis_discovery(
    *,
    dataset_meta: Any,
    preferences: Optional[Dict[str, Any]] = None,
    protocol: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    fallback = {
        "schema": "clinimetria.hypothesis_discovery",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "analysis_mode": str((preferences or {}).get("analysis_mode") or (preferences or {}).get("mode") or "exploratory").strip().lower(),
        "count": 0,
        "items": [],
    }
    try:
        doc = build_hypothesis_discovery(
            dataset_meta=dataset_meta if isinstance(dataset_meta, dict) else {},
            preferences=preferences if isinstance(preferences, dict) else {},
            protocol=protocol if isinstance(protocol, list) else None,
        )
        if isinstance(doc, dict):
            return doc
    except Exception as e:
        logger.warning(f"hypothesis_discovery failed: {e}")
    return fallback





def _resolve_multiplicity_policy(
    policy_source: Dict[str, Any],
    *,
    analysis_mode: str,
) -> Dict[str, Any]:
    source = policy_source if isinstance(policy_source, dict) else {}
    multiplicity_block = source.get("multiplicity") if isinstance(source.get("multiplicity"), dict) else {}

    correction_raw = None
    for key in (
        "multiplicity_correction",
        "multiple_testing_correction",
        "correction",
    ):
        if key in source:
            correction_raw = source.get(key)
            break
    if correction_raw is None:
        correction_raw = multiplicity_block.get("correction")

    correction = _normalize_correction(correction_raw) or "fdr_bh"

    post_hoc_correction_raw = None
    for key in ("post_hoc_correction", "posthoc_correction"):
        if key in source:
            post_hoc_correction_raw = source.get(key)
            break
    if post_hoc_correction_raw is None:
        post_hoc_correction_raw = multiplicity_block.get("post_hoc_correction")
    if post_hoc_correction_raw is None:
        post_hoc_correction_raw = correction
    post_hoc_correction = _normalize_correction(post_hoc_correction_raw) or (
        "none" if correction == "none" else correction
    )

    alpha = 0.05
    alpha_raw = source.get("alpha")
    if alpha_raw is None:
        alpha_raw = multiplicity_block.get("alpha")
    try:
        alpha_candidate = float(alpha_raw)
        if math.isfinite(alpha_candidate):
            alpha = max(0.001, min(0.2, alpha_candidate))
    except Exception:
        alpha = 0.05

    methods_raw = source.get("multiplicity_methods")
    if methods_raw is None:
        methods_raw = multiplicity_block.get("methods")
    methods_list: List[str] = []
    if isinstance(methods_raw, list):
        methods_list = [str(v).strip() for v in methods_raw if isinstance(v, (str, int, float)) and str(v).strip()]
    elif isinstance(methods_raw, str):
        methods_list = [item.strip() for item in methods_raw.split(",") if item.strip()]

    normalized_methods = sorted(
        list(
            {
                _canonical_method_id(item)
                for item in methods_list
                if _canonical_method_id(item) in MULTIPLICITY_COMPATIBLE_METHODS
            }
        )
    )
    if not normalized_methods:
        normalized_methods = sorted(list(MULTIPLICITY_COMPATIBLE_METHODS))

    return {
        "enabled": bool(correction != "none"),
        "correction": correction,
        "multiplicity_correction": correction,
        "post_hoc_correction": post_hoc_correction,
        "alpha": float(alpha),
        "methods": normalized_methods,
        "analysis_mode": analysis_mode,
        "scope": "global_defaults",
    }


def _attach_multiplicity_policy_to_plan_globals(
    globals_in: Dict[str, Any],
    *,
    preferences: Dict[str, Any],
    analysis_mode: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    globals_out = dict(globals_in) if isinstance(globals_in, dict) else {}
    policy_source: Dict[str, Any] = {}
    if isinstance(preferences, dict):
        policy_source.update(preferences)
    policy_source.update(globals_out)

    multiplicity_policy = _resolve_multiplicity_policy(policy_source, analysis_mode=analysis_mode)

    if "multiplicity_correction" not in globals_out:
        globals_out["multiplicity_correction"] = multiplicity_policy.get("correction")
    if "post_hoc_correction" not in globals_out:
        globals_out["post_hoc_correction"] = multiplicity_policy.get("post_hoc_correction")

    return globals_out, multiplicity_policy


def _resolve_bootstrap_policy(
    policy_source: Dict[str, Any],
    *,
    analysis_mode: str,
) -> Dict[str, Any]:
    source = policy_source if isinstance(policy_source, dict) else {}
    bootstrap_block = source.get("bootstrap") if isinstance(source.get("bootstrap"), dict) else {}

    enabled_raw = None
    for key in ("bootstrap_ci", "use_bootstrap_ci", "bootstrap_enabled"):
        if key in source:
            enabled_raw = source.get(key)
            break
    if enabled_raw is None and "enabled" in bootstrap_block:
        enabled_raw = bootstrap_block.get("enabled")
    if enabled_raw is None and "ci" in bootstrap_block:
        enabled_raw = bootstrap_block.get("ci")
    enabled = _as_bool(enabled_raw, default=False) if enabled_raw is not None else False

    samples_raw = None
    for key in ("bootstrap_samples", "bootstrap_iterations", "n_boot"):
        if key in source:
            samples_raw = source.get(key)
            break
    if samples_raw is None:
        for key in ("samples", "iterations", "n_boot"):
            if key in bootstrap_block:
                samples_raw = bootstrap_block.get(key)
                break
    samples = _normalize_bootstrap_samples(samples_raw, default=DEFAULT_BOOTSTRAP_SAMPLES)

    ci_level = 0.95
    ci_level_raw = source.get("bootstrap_ci_level")
    if ci_level_raw is None:
        ci_level_raw = bootstrap_block.get("ci_level")
    try:
        ci_candidate = float(ci_level_raw)
        if math.isfinite(ci_candidate):
            ci_level = max(0.5, min(0.99, ci_candidate))
    except Exception:
        ci_level = 0.95

    methods_raw = source.get("bootstrap_methods")
    if methods_raw is None:
        methods_raw = bootstrap_block.get("methods")
    methods_list: List[str] = []
    if isinstance(methods_raw, list):
        methods_list = [str(v).strip() for v in methods_raw if isinstance(v, (str, int, float)) and str(v).strip()]
    elif isinstance(methods_raw, str):
        methods_list = [item.strip() for item in methods_raw.split(",") if item.strip()]
    normalized_methods = sorted(
        list(
            {
                _canonical_method_id(item)
                for item in methods_list
                if _canonical_method_id(item) in BOOTSTRAP_COMPATIBLE_METHODS
            }
        )
    )
    if not normalized_methods:
        normalized_methods = sorted(list(BOOTSTRAP_COMPATIBLE_METHODS))

    return {
        "enabled": bool(enabled),
        "samples": int(samples),
        "ci_level": float(ci_level),
        "methods": normalized_methods,
        "analysis_mode": analysis_mode,
        "scope": "global_defaults",
    }


def _attach_bootstrap_policy_to_plan_globals(
    globals_in: Dict[str, Any],
    *,
    preferences: Dict[str, Any],
    analysis_mode: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    globals_out = dict(globals_in) if isinstance(globals_in, dict) else {}
    policy_source: Dict[str, Any] = {}
    if isinstance(preferences, dict):
        policy_source.update(preferences)
    policy_source.update(globals_out)

    bootstrap_policy = _resolve_bootstrap_policy(policy_source, analysis_mode=analysis_mode)

    if "bootstrap_ci" not in globals_out:
        globals_out["bootstrap_ci"] = bool(bootstrap_policy.get("enabled"))
    if "bootstrap_samples" not in globals_out:
        globals_out["bootstrap_samples"] = int(bootstrap_policy.get("samples") or DEFAULT_BOOTSTRAP_SAMPLES)
    if "bootstrap_ci_level" not in globals_out:
        globals_out["bootstrap_ci_level"] = float(bootstrap_policy.get("ci_level") or 0.95)

    return globals_out, bootstrap_policy


def _analysis_runtime_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(config, dict):
        return {}

    out: Dict[str, Any] = {}

    normality_test = config.get("normality_test")
    if isinstance(normality_test, str) and normality_test.strip():
        out["normality_test"] = normality_test.strip().lower()

    normality_decision = config.get("normality_decision")
    if isinstance(normality_decision, str) and normality_decision.strip():
        out["normality_decision"] = normality_decision.strip().lower()

    homogeneity_test = config.get("homogeneity_test")
    if isinstance(homogeneity_test, str) and homogeneity_test.strip():
        out["homogeneity_test"] = homogeneity_test.strip().lower()

    homogeneity_center = config.get("homogeneity_center")
    if isinstance(homogeneity_center, str) and homogeneity_center.strip():
        out["homogeneity_center"] = homogeneity_center.strip().lower()

    corr_method = config.get("correlation_method")
    if isinstance(corr_method, str):
        corr_method_norm = corr_method.strip().lower()
        if corr_method_norm in {"pearson", "spearman", "kendall"}:
            out["correlation_method"] = corr_method_norm

    bootstrap_ci = config.get("bootstrap_ci")
    if bootstrap_ci is not None:
        out["bootstrap_ci"] = _as_bool(bootstrap_ci, default=False)

    bootstrap_samples = config.get("bootstrap_samples")
    try:
        bs = _normalize_bootstrap_samples(bootstrap_samples, default=DEFAULT_BOOTSTRAP_SAMPLES)
    except Exception:
        bs = None
    if bs is not None:
        out["bootstrap_samples"] = int(bs)

    return out

def _build_batch_multiplicity_trace(
    items: Any,
    *,
    alpha: float,
    correction: Optional[str],
    scope: Optional[str] = None,
) -> Dict[str, Any]:
    local_items = items if isinstance(items, list) else []

    rows: List[Dict[str, Any]] = []
    p_raw_vec: List[Optional[float]] = []
    p_adj_vec: List[Optional[float]] = []
    valid_indices: List[int] = []
    method_hint = _normalize_correction(correction) or "none"

    for idx, item in enumerate(local_items):
        if not isinstance(item, dict):
            continue

        trace_item = item.get("multiplicity_trace")
        if isinstance(trace_item, dict):
            trace_method = _normalize_correction(trace_item.get("method"))
            if trace_method:
                method_hint = trace_method

        target = item.get("target") or item.get("label") or item.get("outcome")
        p_raw = _finite_float(item.get("p_value_raw"))
        if p_raw is None:
            p_raw = _finite_float(item.get("p_value"))
        p_adj = _finite_float(item.get("p_value_adj"))
        if p_adj is None:
            p_adj = _finite_float(item.get("adjusted_p_value"))

        sig_adj = item.get("significant_adj")
        if not isinstance(sig_adj, bool):
            sig_adj = bool(p_adj < alpha) if p_adj is not None else None

        if p_raw is not None:
            valid_indices.append(idx)

        p_raw_vec.append(p_raw)
        p_adj_vec.append(p_adj)
        rows.append(
            {
                "index": idx,
                "target": str(target) if target is not None else None,
                "p_value_raw": p_raw,
                "p_value_adj": p_adj,
                "significant_adj": sig_adj,
            }
        )

    return {
        "scope": scope or "batch",
        "method": method_hint,
        "alpha": float(alpha),
        "n_total": int(len(local_items)),
        "n_valid": int(len(valid_indices)),
        "valid_indices": valid_indices,
        "p_values_raw": p_raw_vec,
        "p_values_adj": p_adj_vec,
        "items": rows,
    }


def _bootstrap_metric_preview(name: str, value: Any, *, limit: int = 8) -> Any:
    metric = str(name or "").strip()
    if not metric:
        return None

    if isinstance(value, dict):
        out: Dict[str, Any] = {"metric": metric}
        for key in ["estimate", "ci_lower", "ci_upper", "n_valid", "samples", "ci_level", "name"]:
            if key in value:
                out[key] = value.get(key)
        if len(out) == 1:
            out["present"] = True
        return out

    if isinstance(value, list):
        if metric == "coefficients":
            rows: List[Dict[str, Any]] = []
            for row in value[:limit]:
                if not isinstance(row, dict):
                    continue
                rows.append(
                    {
                        "variable": row.get("variable"),
                        "estimate": row.get("estimate"),
                        "ci_lower": row.get("ci_lower"),
                        "ci_upper": row.get("ci_upper"),
                        "n_valid": row.get("n_valid"),
                        "or_ci_lower": row.get("or_ci_lower"),
                        "or_ci_upper": row.get("or_ci_upper"),
                    }
                )
            return {
                "metric": metric,
                "n_total": len(value),
                "rows": rows,
            }
        return {"metric": metric, "n_items": len(value)}

    if isinstance(value, (str, int, float, bool)) or value is None:
        return {"metric": metric, "value": value}
    return {"metric": metric, "present": True}


def _build_bootstrap_trace_document(
    *,
    dataset_id: str,
    run_id: str,
    results_map: Any,
    step_meta_map: Any,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    steps_total = 0
    steps_with_bootstrap = 0
    steps_with_bootstrap_errors = 0

    results = results_map if isinstance(results_map, dict) else {}
    meta_map = step_meta_map if isinstance(step_meta_map, dict) else {}

    for step_id, payload in results.items():
        if not isinstance(step_id, str) or not isinstance(payload, dict):
            continue
        steps_total += 1
        bootstrap = payload.get("bootstrap")
        if not isinstance(bootstrap, dict):
            continue
        if bootstrap.get("enabled") is False:
            continue
        steps_with_bootstrap += 1

        method_meta = payload.get("method")
        method_id = None
        if isinstance(method_meta, dict):
            method_id = method_meta.get("id") or method_meta.get("name")
        if not method_id:
            method_id = payload.get("method_id")
        if not method_id:
            meta = meta_map.get(step_id) if isinstance(meta_map.get(step_id), dict) else {}
            method_id = meta.get("method") or (
                meta.get("config", {}).get("method_id")
                if isinstance(meta.get("config"), dict)
                else None
            )

        metrics_raw = bootstrap.get("metrics") if isinstance(bootstrap.get("metrics"), dict) else {}
        metrics_preview: List[Any] = []
        for metric_name, metric_value in metrics_raw.items():
            preview = _bootstrap_metric_preview(str(metric_name), metric_value)
            if preview is not None:
                metrics_preview.append(preview)

        error_text = bootstrap.get("error")
        if isinstance(error_text, str) and error_text.strip():
            steps_with_bootstrap_errors += 1

        rows.append(
            {
                "step_id": step_id,
                "method": method_id,
                "type": payload.get("type"),
                "bootstrap": {
                    "enabled": True,
                    "method": bootstrap.get("method"),
                    "samples": bootstrap.get("samples"),
                    "ci_level": bootstrap.get("ci_level"),
                    "n_valid_models": bootstrap.get("n_valid_models"),
                    "error": error_text,
                    "metrics": metrics_preview,
                },
            }
        )

    return {
        "schema": "clinimetria.bootstrap_trace",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_id": str(dataset_id or ""),
        "run_id": str(run_id or ""),
        "summary": {
            "steps_total": int(steps_total),
            "steps_with_bootstrap": int(steps_with_bootstrap),
            "steps_with_errors": int(steps_with_bootstrap_errors),
        },
        "steps": rows,
    }


def _count_adjusted_p_values(items: Any) -> int:
    if not isinstance(items, list):
        return 0
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        p_adj = _finite_float(item.get("p_value_adj"))
        if p_adj is None:
            p_adj = _finite_float(item.get("adjusted_p_value"))
        if p_adj is not None:
            count += 1
    return count


def _build_multiplicity_trace_document(
    *,
    dataset_id: str,
    run_id: str,
    results_map: Any,
    step_meta_map: Any,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    steps_total = 0
    steps_with_multiplicity = 0

    results = results_map if isinstance(results_map, dict) else {}
    meta_map = step_meta_map if isinstance(step_meta_map, dict) else {}

    for step_id, payload in results.items():
        if not isinstance(step_id, str) or not isinstance(payload, dict):
            continue
        steps_total += 1

        method_meta = payload.get("method")
        method_id = None
        if isinstance(method_meta, dict):
            method_id = method_meta.get("id") or method_meta.get("name")
        if not method_id:
            method_id = payload.get("method_id")
        if not method_id:
            meta = meta_map.get(step_id) if isinstance(meta_map.get(step_id), dict) else {}
            method_id = meta.get("method") or (
                meta.get("config", {}).get("method_id")
                if isinstance(meta.get("config"), dict)
                else None
            )

        step_had_multiplicity = False

        trace = payload.get("multiplicity_trace") if isinstance(payload.get("multiplicity_trace"), dict) else None
        if isinstance(trace, dict):
            correction = _normalize_correction(trace.get("method")) or _normalize_correction(
                payload.get("multiplicity_correction")
            ) or "none"
            p_values_adj = trace.get("p_values_adj") if isinstance(trace.get("p_values_adj"), list) else []
            n_adjusted = len([v for v in p_values_adj if _finite_float(v) is not None])
            rows.append(
                {
                    "step_id": step_id,
                    "method": method_id,
                    "scope": str(trace.get("scope") or payload.get("type") or "step"),
                    "source": "result_trace",
                    "correction": correction,
                    "alpha": _finite_float(trace.get("alpha")),
                    "n_total": int(trace.get("n_total") or 0),
                    "n_valid": int(trace.get("n_valid") or 0),
                    "n_adjusted": int(n_adjusted),
                }
            )
            step_had_multiplicity = True

        trace_by_slice = (
            payload.get("multiplicity_trace_by_slice")
            if isinstance(payload.get("multiplicity_trace_by_slice"), dict)
            else {}
        )
        for slice_key, slice_trace in trace_by_slice.items():
            if not isinstance(slice_trace, dict):
                continue
            correction = _normalize_correction(slice_trace.get("method")) or _normalize_correction(
                payload.get("multiplicity_correction")
            ) or "none"
            p_values_adj = slice_trace.get("p_values_adj") if isinstance(slice_trace.get("p_values_adj"), list) else []
            n_adjusted = len([v for v in p_values_adj if _finite_float(v) is not None])
            rows.append(
                {
                    "step_id": step_id,
                    "method": method_id,
                    "scope": str(slice_trace.get("scope") or f"slice:{slice_key}"),
                    "slice": str(slice_key),
                    "source": "result_trace_by_slice",
                    "correction": correction,
                    "alpha": _finite_float(slice_trace.get("alpha")),
                    "n_total": int(slice_trace.get("n_total") or 0),
                    "n_valid": int(slice_trace.get("n_valid") or 0),
                    "n_adjusted": int(n_adjusted),
                }
            )
            step_had_multiplicity = True

        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        if items and not step_had_multiplicity:
            correction = _normalize_correction(payload.get("multiplicity_correction")) or _normalize_correction(
                payload.get("post_hoc_correction")
            )
            n_adjusted = _count_adjusted_p_values(items)
            if correction and n_adjusted > 0:
                n_valid = 0
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    p_raw = _finite_float(item.get("p_value_raw"))
                    if p_raw is None:
                        p_raw = _finite_float(item.get("p_value"))
                    if p_raw is not None:
                        n_valid += 1
                rows.append(
                    {
                        "step_id": step_id,
                        "method": method_id,
                        "scope": str(payload.get("type") or "batch"),
                        "source": "derived_items",
                        "correction": correction,
                        "alpha": None,
                        "n_total": int(len(items)),
                        "n_valid": int(n_valid),
                        "n_adjusted": int(n_adjusted),
                    }
                )
                step_had_multiplicity = True

        post_hoc = payload.get("post_hoc") if isinstance(payload.get("post_hoc"), list) else []
        if post_hoc:
            correction = _normalize_correction(payload.get("post_hoc_correction")) or _normalize_correction(
                payload.get("multiplicity_correction")
            )
            n_adjusted = _count_adjusted_p_values(post_hoc)
            if correction and n_adjusted > 0:
                n_valid = 0
                for item in post_hoc:
                    if not isinstance(item, dict):
                        continue
                    p_raw = _finite_float(item.get("p_value"))
                    if p_raw is not None:
                        n_valid += 1
                rows.append(
                    {
                        "step_id": step_id,
                        "method": method_id,
                        "scope": "post_hoc",
                        "source": "derived_post_hoc",
                        "correction": correction,
                        "alpha": None,
                        "n_total": int(len(post_hoc)),
                        "n_valid": int(n_valid),
                        "n_adjusted": int(n_adjusted),
                    }
                )
                step_had_multiplicity = True

        if step_had_multiplicity:
            steps_with_multiplicity += 1

    return {
        "schema": "clinimetria.multiplicity_trace",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_id": str(dataset_id or ""),
        "run_id": str(run_id or ""),
        "summary": {
            "steps_total": int(steps_total),
            "steps_with_multiplicity": int(steps_with_multiplicity),
            "traces_total": int(len(rows)),
        },
        "steps": rows,
    }


def _iter_result_payload_entries(results: Any) -> List[tuple[str, Dict[str, Any]]]:
    return _vp_iter_result_payload_entries(results)


def _extract_step_p_value(payload: Dict[str, Any]) -> Optional[float]:
    return _vp_extract_step_p_value(payload)


def _repair_run_payload_multiplicity(
    run_payload: Dict[str, Any],
    *,
    alpha: float,
    correction: str = "fdr_bh",
) -> Dict[str, Any]:
    return _vp_repair_run_payload_multiplicity(
        run_payload,
        alpha=float(alpha),
        correction=correction,
    )


def _repair_run_payload_p_bounds(
    run_payload: Dict[str, Any],
    *,
    epsilon: float = 1e-12,
) -> Dict[str, Any]:
    return _vp_repair_run_payload_p_bounds(
        run_payload,
        epsilon=float(epsilon),
    )


def _attempt_verifier_reflection_repair(
    run_payload: Dict[str, Any],
    *,
    verification: Dict[str, Any],
    alpha: float,
    correction: str = "fdr_bh",
) -> Dict[str, Any]:
    return _vp_attempt_verifier_reflection_repair(
        run_payload,
        verification=verification,
        alpha=float(alpha),
        correction=correction,
    )


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _build_environment_snapshot() -> Dict[str, Any]:
    packages: Dict[str, str] = {}
    for name in (
        "numpy",
        "pandas",
        "scipy",
        "statsmodels",
        "pingouin",
        "fastapi",
        "uvicorn",
        "scikit-learn",
    ):
        try:
            version = importlib_metadata.version(name)
            if isinstance(version, str) and version.strip():
                packages[name] = version.strip()
        except Exception:
            continue

    return {
        "schema": "clinimetria.reproducibility_environment",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "packages": packages,
    }


def _reproduce_script_template() -> str:
    return """#!/usr/bin/env python3
\"\"\"Reproduce StatProject analysis run via API.

Usage:
  python reproduce_run.py --base-url http://127.0.0.1:8000/api/v1/v2
\"\"\"

import argparse
import json
import pathlib
import urllib.request


def main():
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument(\"--base-url\", default=\"http://127.0.0.1:8000/api/v1/v2\", help=\"StatProject v2 API base URL\")
    parser.add_argument(\"--payload\", default=str(here / \"reproduce_payload.json\"), help=\"Path to reproduce payload JSON\")
    parser.add_argument(\"--output\", default=str(here / \"reproduce_response.json\"), help=\"Where to store API response JSON\")
    args = parser.parse_args()

    with open(args.payload, \"r\", encoding=\"utf-8\") as f:
        payload = json.load(f)

    url = args.base_url.rstrip(\"/\") + \"/analysis/execute\"
    data = json.dumps(payload, ensure_ascii=False).encode(\"utf-8\")
    req = urllib.request.Request(url, data=data, method=\"POST\", headers={\"Content-Type\": \"application/json\"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = json.loads(resp.read().decode(\"utf-8\"))

    with open(args.output, \"w\", encoding=\"utf-8\") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    print(f\"Saved reproduced response to: {args.output}\")
    print(f\"run_id={body.get('run_id')}\")


if __name__ == \"__main__\":
    main()
"""


def _build_fallback_report_html(dataset_id: str, run_id: str, protocol_name: str) -> str:
    safe_dataset = str(dataset_id or "")
    safe_run = str(run_id or "")
    safe_protocol = str(protocol_name or "")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Protocol Report</title></head>"
        "<body>"
        f"<h1>Protocol report (fallback)</h1><p>dataset_id={safe_dataset}</p>"
        f"<p>run_id={safe_run}</p><p>protocol={safe_protocol}</p>"
        "</body></html>"
    )


def _create_run_reproducibility_artifacts(
    *,
    run_dir: str,
    run_id: str,
    dataset_id: str,
    protocol_name: str,
    alpha: float,
    globals_in: Dict[str, Any],
    normalized_steps: List[Dict[str, Any]],
    run_payload: Dict[str, Any],
    result_ir: Dict[str, Any],
    analysis_dataset_artifacts: Optional[Dict[str, Any]],
    llm_benchmark: Optional[Dict[str, Any]],
    runtime_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    artifact_rows: List[Dict[str, Any]] = []
    errors: List[str] = []
    notes: List[str] = []
    dataset_artifacts: List[str] = []

    def _save_bytes(filename: str, content: bytes) -> None:
        pipeline.save_run_artifact(run_dir, filename, content)
        artifact_rows.append(
            {
                "name": filename,
                "size_bytes": int(len(content)),
                "sha256": _sha256_hex(content),
            }
        )

    def _copy_dataset_processed_json(src_name: str, dst_name: str) -> None:
        src_path = os.path.join(DATA_DIR, dataset_id, "processed", src_name)
        if not os.path.exists(src_path):
            return
        try:
            with open(src_path, "rb") as f:
                content = f.read()
            _save_bytes(dst_name, content)
            dataset_artifacts.append(dst_name)
        except Exception as e:
            errors.append(f"{dst_name}: {e}")

    # Payload to re-run execute-v2 with the same settings.
    reproduce_payload = {
        "dataset_id": dataset_id,
        "protocol_name": protocol_name,
        "alpha": float(alpha),
        "globals": globals_in if isinstance(globals_in, dict) else {},
        "protocol": normalized_steps if isinstance(normalized_steps, list) else [],
    }

    protocol_resolved = {
        "name": protocol_name,
        "dataset_id": dataset_id,
        "alpha": float(alpha),
        "globals": globals_in if isinstance(globals_in, dict) else {},
        "steps": normalized_steps if isinstance(normalized_steps, list) else [],
        "run_id": run_id,
    }

    try:
        _save_bytes(
            "reproduce_payload.json",
            json.dumps(reproduce_payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    except Exception as e:
        errors.append(f"reproduce_payload.json: {e}")

    try:
        _save_bytes(
            "protocol_resolved.json",
            json.dumps(protocol_resolved, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    except Exception as e:
        errors.append(f"protocol_resolved.json: {e}")

    try:
        _save_bytes("reproduce_run.py", _reproduce_script_template().encode("utf-8"))
    except Exception as e:
        errors.append(f"reproduce_run.py: {e}")

    environment_artifact: Optional[str] = None
    try:
        environment_artifact = "reproducibility_environment.json"
        _save_bytes(
            environment_artifact,
            json.dumps(_build_environment_snapshot(), ensure_ascii=False, indent=2).encode("utf-8"),
        )
    except Exception as e:
        environment_artifact = None
        errors.append(f"reproducibility_environment.json: {e}")

    llm_benchmark_artifact: Optional[str] = None
    if isinstance(llm_benchmark, dict):
        try:
            llm_benchmark_artifact = "llm_benchmark.json"
            _save_bytes(
                llm_benchmark_artifact,
                json.dumps(llm_benchmark, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except Exception as e:
            llm_benchmark_artifact = None
            errors.append(f"llm_benchmark.json: {e}")

    runtime_profile_artifact: Optional[str] = None
    if isinstance(runtime_profile, dict):
        try:
            runtime_profile_artifact = "runtime_profile.json"
            _save_bytes(
                runtime_profile_artifact,
                json.dumps(runtime_profile, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except Exception as e:
            runtime_profile_artifact = None
            errors.append(f"runtime_profile.json: {e}")

    hypothesis_discovery_artifact: Optional[str] = None
    hypothesis_discovery = (
        run_payload.get("hypotheses")
        if isinstance(run_payload.get("hypotheses"), dict)
        else None
    )
    if (
        isinstance(hypothesis_discovery, dict)
        and isinstance(hypothesis_discovery.get("items"), list)
        and len(hypothesis_discovery.get("items") or []) > 0
    ):
        try:
            hypothesis_discovery_artifact = "hypothesis_discovery.json"
            _save_bytes(
                hypothesis_discovery_artifact,
                json.dumps(hypothesis_discovery, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except Exception as e:
            hypothesis_discovery_artifact = None
            errors.append(f"hypothesis_discovery.json: {e}")

    bootstrap_trace_artifact: Optional[str] = None
    bootstrap_trace = run_payload.get("bootstrap_trace") if isinstance(run_payload.get("bootstrap_trace"), dict) else None
    bootstrap_steps = (
        int((bootstrap_trace.get("summary") or {}).get("steps_with_bootstrap") or 0)
        if isinstance(bootstrap_trace, dict)
        else 0
    )
    if isinstance(bootstrap_trace, dict) and bootstrap_steps > 0:
        try:
            bootstrap_trace_artifact = "bootstrap_trace.json"
            _save_bytes(
                bootstrap_trace_artifact,
                json.dumps(bootstrap_trace, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except Exception as e:
            bootstrap_trace_artifact = None
            errors.append(f"bootstrap_trace.json: {e}")

    multiplicity_trace_artifact: Optional[str] = None
    multiplicity_trace = (
        run_payload.get("multiplicity_trace")
        if isinstance(run_payload.get("multiplicity_trace"), dict)
        else None
    )
    multiplicity_steps = (
        int((multiplicity_trace.get("summary") or {}).get("steps_with_multiplicity") or 0)
        if isinstance(multiplicity_trace, dict)
        else 0
    )
    if isinstance(multiplicity_trace, dict) and multiplicity_steps > 0:
        try:
            multiplicity_trace_artifact = "multiplicity_trace.json"
            _save_bytes(
                multiplicity_trace_artifact,
                json.dumps(multiplicity_trace, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        except Exception as e:
            multiplicity_trace_artifact = None
            errors.append(f"multiplicity_trace.json: {e}")

    report_html = None
    try:
        from app.modules.reporting import render_protocol_report

        report_html = render_protocol_report(
            run_payload,
            dataset_name=f"Dataset {dataset_id}",
            style="gost",
        )
    except Exception as e:
        notes.append(f"protocol_report_auto.html(render fallback): {e}")
        report_html = _build_fallback_report_html(dataset_id, run_id, protocol_name)

    try:
        _save_bytes("protocol_report_auto.html", str(report_html or "").encode("utf-8"))
    except Exception as e:
        errors.append(f"protocol_report_auto.html(save): {e}")

    for src_name, dst_name in [
        ("profile.json", "dataset_profile.json"),
        ("data_contract.json", "dataset_data_contract.json"),
        ("cleaning_plan.json", "dataset_cleaning_plan.json"),
        ("cleaning_log.json", "dataset_cleaning_log.json"),
        ("data_lineage.json", "dataset_data_lineage.json"),
        ("scan_report.json", "dataset_scan_report.json"),
        ("study_design.json", "dataset_study_design.json"),
        ("analysis_set_hash.json", "dataset_analysis_set_hash.json"),
    ]:
        _copy_dataset_processed_json(src_name, dst_name)

    analysis_set_info = run_payload.get("analysis_set") if isinstance(run_payload.get("analysis_set"), dict) else {}
    analysis_set_id = analysis_set_info.get("analysis_set_id") if isinstance(analysis_set_info.get("analysis_set_id"), str) else None
    if analysis_set_id:
        src = os.path.join(DATA_DIR, dataset_id, "processed", "analysis_sets", f"{analysis_set_id}.json")
        if os.path.exists(src):
            try:
                with open(src, "rb") as f:
                    _save_bytes("dataset_analysis_set.json", f.read())
                dataset_artifacts.append("dataset_analysis_set.json")
            except Exception as e:
                errors.append(f"dataset_analysis_set.json: {e}")
        src_parquet = os.path.join(DATA_DIR, dataset_id, "processed", "analysis_sets", f"{analysis_set_id}.parquet")
        if os.path.exists(src_parquet):
            try:
                with open(src_parquet, "rb") as f:
                    _save_bytes("dataset_analysis_set.parquet", f.read())
                dataset_artifacts.append("dataset_analysis_set.parquet")
            except Exception as e:
                errors.append(f"dataset_analysis_set.parquet: {e}")

    manifest = {
        "schema": "clinimetria.reproducibility_manifest",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "run_id": run_id,
        "dataset_id": dataset_id,
        "protocol_name": protocol_name,
        "alpha": float(alpha),
        "analysis_dataset": analysis_dataset_artifacts if isinstance(analysis_dataset_artifacts, dict) else None,
        "environment": {"artifact": environment_artifact} if isinstance(environment_artifact, str) else None,
        "llm_benchmark": (
            {
                "artifact": llm_benchmark_artifact,
                "recommended_id": llm_benchmark.get("recommended_id"),
                "variant_count": len(llm_benchmark.get("variants") or []),
            }
            if isinstance(llm_benchmark, dict)
            else None
        ),
        "runtime_profile": (
            {
                "artifact": runtime_profile_artifact,
                "total_elapsed_ms": int(
                    ((runtime_profile.get("summary") if isinstance(runtime_profile.get("summary"), dict) else {}) or {}).get("total_elapsed_ms")
                    or 0
                ),
                "profiled_steps": int(
                    ((runtime_profile.get("summary") if isinstance(runtime_profile.get("summary"), dict) else {}) or {}).get("profiled_steps")
                    or 0
                ),
            }
            if isinstance(runtime_profile, dict)
            else None
        ),
        "hypothesis_discovery": (
            {
                "artifact": hypothesis_discovery_artifact,
                "count": int(hypothesis_discovery.get("count") or len(hypothesis_discovery.get("items") or [])),
            }
            if isinstance(hypothesis_discovery, dict) and isinstance(hypothesis_discovery_artifact, str)
            else None
        ),
        "bootstrap_trace": (
            {
                "artifact": bootstrap_trace_artifact,
                "steps_with_bootstrap": bootstrap_steps,
            }
            if isinstance(bootstrap_trace, dict) and bootstrap_steps > 0
            else None
        ),
        "multiplicity_trace": (
            {
                "artifact": multiplicity_trace_artifact,
                "steps_with_multiplicity": multiplicity_steps,
            }
            if isinstance(multiplicity_trace, dict) and multiplicity_steps > 0
            else None
        ),
        "result_ir": result_ir if isinstance(result_ir, dict) else {},
        "dataset_artifacts": dataset_artifacts,
        "artifacts": artifact_rows,
        "errors": errors,
        "notes": notes,
    }
    try:
        assert_artifact_contract("reproducibility_manifest.json", manifest)
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        _save_bytes("reproducibility_manifest.json", manifest_bytes)
    except Exception as e:
        errors.append(f"reproducibility_manifest.json: {e}")

    return {
        "ready": len(errors) == 0,
        "manifest": "reproducibility_manifest.json",
        "script": "reproduce_run.py",
        "payload": "reproduce_payload.json",
        "protocol": "protocol_resolved.json",
        "report_html": "protocol_report_auto.html",
        "analysis_dataset": analysis_dataset_artifacts if isinstance(analysis_dataset_artifacts, dict) else None,
        "environment": environment_artifact,
        "llm_benchmark": llm_benchmark_artifact,
        "runtime_profile": runtime_profile_artifact,
        "hypothesis_discovery": hypothesis_discovery_artifact,
        "bootstrap_trace": bootstrap_trace_artifact,
        "multiplicity_trace": multiplicity_trace_artifact,
        "dataset_artifacts": dataset_artifacts,
        "artifacts": [row.get("name") for row in artifact_rows if isinstance(row, dict)],
        "errors": errors,
        "notes": notes,
    }


def _collect_dataset_columns(dataset_meta: Dict[str, Any]) -> set:
    cols = dataset_meta.get("columns") if isinstance(dataset_meta, dict) else None
    names: set = set()
    if isinstance(cols, list):
        for item in cols:
            if isinstance(item, dict):
                name = item.get("name")
            else:
                name = item
            if name:
                names.add(str(name))
    return names


def _filter_protocol_steps(protocol: List[Dict[str, Any]], dataset_meta: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str]]:
    available = _collect_dataset_columns(dataset_meta)
    if not available:
        return protocol, []

    def _keep_col(val):
        if isinstance(val, str) and val in available:
            return val
        return None

    def _keep_list(lst):
        if not isinstance(lst, list):
            return []
        return [str(v) for v in lst if isinstance(v, str) and v in available]

    notes: List[str] = []
    filtered: List[Dict[str, Any]] = []

    for step in protocol:
        if not isinstance(step, dict):
            continue
        method = str(step.get("method") or "").strip()
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        cfg = dict(cfg)

        if "outcome" not in cfg and "target" in cfg:
            cfg["outcome"] = cfg.get("target")
        if "group" not in cfg and "predictor" in cfg:
            cfg["group"] = cfg.get("predictor")
        if "split_by" not in cfg:
            if "timepoint" in cfg:
                cfg["split_by"] = cfg.get("timepoint")
            elif "time" in cfg:
                cfg["split_by"] = cfg.get("time")

        for key in [
            "outcome",
            "group",
            "group1",
            "group2",
            "subject",
            "subject_col",
            "time",
            "time_col",
            "baseline",
            "follow",
            "split_by",
            "predictor",
            "method_1",
            "method_2",
            "rater_col",
            "rater_a",
            "rater_b",
            "before",
            "after",
        ]:
            if key in cfg:
                cfg[key] = _keep_col(cfg.get(key))

        for key in ["predictors", "covariates", "variables", "outcome_cols", "targets", "outcome_columns"]:
            if key in cfg:
                cfg[key] = _keep_list(cfg.get(key))

        if "pairs" in cfg and isinstance(cfg.get("pairs"), list):
            pairs = []
            for pair in cfg.get("pairs"):
                if not isinstance(pair, dict):
                    continue
                baseline = _keep_col(pair.get("baseline"))
                follow = _keep_col(pair.get("follow"))
                if baseline and follow:
                    pairs.append({**pair, "baseline": baseline, "follow": follow})
            cfg["pairs"] = pairs

        required = []
        if method in {"descriptive_compare", "auto", "t_test_ind", "t_test_welch", "mann_whitney", "anova", "anova_welch", "kruskal", "chi_square", "pearson", "spearman", "kendall", "t_test_rel", "wilcoxon"}:
            required = ["outcome", "group"]
        elif method == "t_test_one":
            required = ["outcome"]
        elif method == "bayes_t_test_one":
            required = ["outcome"]
        elif method in {"bayes_anova", "bayes_chi_square"}:
            required = ["outcome", "group"]
        elif method in {"bayes_t_test_ind", "bayes_t_test_rel", "bayes_correlation"}:
            required = ["outcome", "group"]
        elif method == "bayes_linear_regression":
            required = ["outcome", "predictors"]
        elif method in {"linear_regression", "logistic_regression"}:
            required = ["outcome", "predictors"]
        elif method == "roc_analysis":
            required = ["outcome", "group"]
        elif method == "mixed_effects":
            required = ["outcome", "time", "group", "subject"]
        elif method == "clustered_correlation":
            required = ["variables"]
        elif method == "responders":
            required = ["outcome_columns", "group"]
        elif method == "anova_twoway":
            required = ["outcome", "group1", "group2"]
        elif method == "ancova":
            required = ["outcome", "group", "covariates"]
        elif method in {"pca", "efa", "cronbach_alpha", "kmeans", "hierarchical_clustering"}:
            required = ["variables"]
        elif method == "shapiro_wilk":
            required = ["outcome"]
        elif method == "bland_altman":
            required = ["method_1", "method_2"]
        elif method == "icc":
            required = ["outcome", "subject_col", "rater_col"]
        elif method in {"cohens_kappa", "mcnemar", "point_biserial"}:
            required = ["outcome", "group"]
        elif method == "cochran_q":
            required = ["outcome_cols"]
        elif method == "partial_correlation":
            required = ["outcome", "group", "covariates"]
        elif method == "time_series_analysis":
            required = ["outcome"]
        elif method == "rm_anova":
            required = ["outcome_cols", "subject_col"]
        elif method == "friedman":
            required = ["outcome_cols"]
        elif method == "paired_wide":
            required = ["baseline", "follow"]
        elif method == "batch_analysis":
            required = ["group"]
        elif method == "timepoint_batch_analysis":
            required = ["group", "split_by"]
        elif method == "delta_batch_analysis":
            required = ["group", "pairs"]

        def _missing(key: str) -> bool:
            if key not in cfg or cfg.get(key) in (None, ""):
                return True
            if key in {"predictors", "covariates", "variables", "outcome_cols", "targets", "pairs", "outcome_columns"}:
                return not isinstance(cfg.get(key), list) or len(cfg.get(key)) == 0
            return False

        if required and any(_missing(k) for k in required):
            notes.append(f"Шаг {step.get('id') or method}: удалён (нет обязательных колонок).")
            continue

        if method == "clustered_correlation" and len(cfg.get("variables", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 переменных).")
            continue
        if method == "responders" and len(cfg.get("outcome_columns", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 outcome_columns).")
            continue
        if method == "rm_anova" and len(cfg.get("outcome_cols", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 outcome_cols).")
            continue
        if method == "friedman" and len(cfg.get("outcome_cols", [])) < 3:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥3 outcome_cols).")
            continue

        step = dict(step)
        step["config"] = cfg
        filtered.append(step)

    return filtered, notes

def _resolve_runtime_validation_policy(globals_in: Dict[str, Any], *, analysis_mode: str) -> Dict[str, Any]:
    profile = _normalize_validation_profile(
        globals_in.get("validation_profile") or globals_in.get("runtime_validation_profile"),
        analysis_mode=analysis_mode,
    )

    defaults = {
        "publication": {
            "validator_enabled": True,
            "validator_strict": True,
            "reflection_enabled": True,
            "reflection_max_rounds": 3,
            "repair_correction": "fdr_by",
        },
        "focused": {
            "validator_enabled": True,
            "validator_strict": False,
            "reflection_enabled": True,
            "reflection_max_rounds": 2,
            "repair_correction": "fdr_bh",
        },
        "exploratory": {
            "validator_enabled": True,
            "validator_strict": False,
            "reflection_enabled": False,
            "reflection_max_rounds": 1,
            "repair_correction": "none",
        },
    }.get(profile, {})

    validator_enabled = _as_bool(
        globals_in.get("validator_enabled"),
        default=bool(defaults.get("validator_enabled", True)),
    )
    validator_strict = _as_bool(
        globals_in.get("validator_strict"),
        default=bool(defaults.get("validator_strict", False)),
    )
    reflection_enabled = _as_bool(
        globals_in.get("agent_reflection_enabled", globals_in.get("verifier_reflection_enabled")),
        default=bool(defaults.get("reflection_enabled", False)),
    )
    rounds_raw = globals_in.get(
        "agent_reflection_max_rounds",
        globals_in.get("verifier_reflection_rounds", defaults.get("reflection_max_rounds", 1)),
    )
    try:
        reflection_max_rounds = int(rounds_raw)
    except Exception:
        reflection_max_rounds = int(defaults.get("reflection_max_rounds", 1))
    reflection_max_rounds = max(1, min(10, reflection_max_rounds))

    repair_correction = _normalize_correction(
        globals_in.get("verifier_repair_correction")
        or globals_in.get("multiplicity_correction")
        or globals_in.get("post_hoc_correction")
        or defaults.get("repair_correction", "fdr_bh")
    ) or "fdr_bh"

    return {
        "profile": profile,
        "analysis_mode": analysis_mode,
        "validator_enabled": bool(validator_enabled),
        "validator_strict": bool(validator_strict),
        "reflection_enabled": bool(reflection_enabled),
        "reflection_max_rounds": int(reflection_max_rounds),
        "repair_correction": repair_correction,
    }


def _attach_validation_policy_to_plan_globals(
    globals_in: Dict[str, Any],
    *,
    preferences: Dict[str, Any],
    analysis_mode: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    globals_out = dict(globals_in) if isinstance(globals_in, dict) else {}
    policy_source: Dict[str, Any] = {}
    if isinstance(preferences, dict):
        policy_source.update(preferences)
    policy_source.update(globals_out)

    validation_policy = _resolve_runtime_validation_policy(policy_source, analysis_mode=analysis_mode)

    if "validation_profile" not in globals_out:
        globals_out["validation_profile"] = validation_policy.get("profile")

    for key in (
        "validator_enabled",
        "validator_strict",
        "agent_reflection_enabled",
        "agent_reflection_max_rounds",
        "verifier_repair_correction",
    ):
        if key in policy_source and key not in globals_out:
            globals_out[key] = policy_source.get(key)

    return globals_out, validation_policy

def _infer_protocol_column_sets(protocol: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    required_all: set = set()
    predictor_like: set = set()
    outcomes: set = set()
    methods: set = set()

    for step in protocol:
        if not isinstance(step, dict):
            continue
        method = _canonical_method_id(step.get("method"))
        if method:
            methods.add(method)
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}

        for key in ["outcome", "target", "group", "group1", "group2", "subject", "subject_col", "time", "baseline", "follow", "split_by"]:
            val = cfg.get(key)
            if isinstance(val, str) and val.strip():
                required_all.add(val.strip())
                if key in {"outcome", "target"}:
                    outcomes.add(val.strip())

        for key in ["predictors", "covariates"]:
            for val in _as_str_list(cfg.get(key)):
                required_all.add(val)
                predictor_like.add(val)

        for key in ["variables", "outcome_cols", "outcome_columns", "targets"]:
            for val in _as_str_list(cfg.get(key)):
                required_all.add(val)
                if key in {"outcome_cols", "outcome_columns", "targets"}:
                    outcomes.add(val)

    return {
        "required_all": sorted(required_all),
        "predictor_like": sorted(predictor_like),
        "outcomes": sorted(outcomes),
        "methods": sorted(methods),
    }


def _build_cleaning_plan(
    *,
    scan_report: Dict[str, Any],
    protocol: List[Dict[str, Any]],
    analysis_mode: str,
) -> Dict[str, Any]:
    inferred = _infer_protocol_column_sets(protocol)
    critical_cols = set(inferred.get("required_all") or [])
    columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else None
    columns_meta = columns_meta if isinstance(columns_meta, dict) else {}
    missing_report = scan_report.get("missing_report") if isinstance(scan_report, dict) else None
    missing_by_col = missing_report.get("by_column") if isinstance(missing_report, dict) else None
    missing_by_col = missing_by_col if isinstance(missing_by_col, list) else []

    operations: List[Dict[str, Any]] = [
        {
            "type": "normalize_missing_tokens",
            "columns": "__all__",
            "tokens": ["", "na", "n/a", "none", "null", "nan"],
        }
    ]

    for col, rep in list(columns_meta.items())[:500]:
        if not isinstance(rep, dict):
            continue
        if rep.get("mixed_type_suspected") is not True:
            continue
        try:
            pct = float(rep.get("numeric_convertible_percent") or 0.0)
        except Exception:
            pct = 0.0
        if pct >= 90.0:
            operations.append(
                {
                    "type": "to_numeric",
                    "columns": [str(col)],
                    "when": {"numeric_convertible_percent_gte": 90.0},
                }
            )

    for row in missing_by_col[:80]:
        if not isinstance(row, dict):
            continue
        col = row.get("column")
        if not isinstance(col, str) or not col.strip():
            continue
        col = col.strip()
        try:
            missing_percent = float(row.get("missing_percent") or 0.0)
        except Exception:
            missing_percent = 0.0
        if missing_percent <= 0:
            continue

        rep = columns_meta.get(col) if isinstance(columns_meta, dict) else None
        dtype = str(rep.get("type") if isinstance(rep, dict) else "").strip().lower()
        is_numeric = any(token in dtype for token in ["int", "float", "double", "number", "numeric", "decimal"])
        is_critical = col in critical_cols

        if missing_percent >= 60.0 and not is_critical:
            operations.append(
                {
                    "type": "exclude_from_models",
                    "columns": [col],
                    "when": {"missing_percent_gte": 60.0},
                }
            )
            continue

        if is_numeric:
            if missing_percent <= 20.0:
                operations.append(
                    {
                        "type": "fill_median",
                        "columns": [col],
                        "when": {"missing_percent_lte": 20.0},
                    }
                )
            elif is_critical:
                operations.append(
                    {
                        "type": "mice",
                        "columns": [col],
                        "when": {"missing_percent_gt": 20.0},
                    }
                )
            continue

        if missing_percent <= 10.0:
            operations.append(
                {
                    "type": "fill_mode",
                    "columns": [col],
                    "when": {"missing_percent_lte": 10.0},
                }
            )
        elif is_critical:
            operations.append(
                {
                    "type": "fill_mode",
                    "columns": [col],
                    "when": {"missing_percent_gt": 10.0},
                    "note": "critical_column",
                }
            )

    notes: List[str] = []
    if analysis_mode == "publication":
        notes.append("Publication mode: cleaning plan должен быть применён и зафиксирован в cleaning_log перед execute.")
    if len(operations) <= 1:
        notes.append("Критичных авто-операций по scan_report не найдено; проверьте plan вручную.")

    return {
        "version": 1,
        "required": analysis_mode == "publication",
        "operations": operations,
        "notes": notes,
    }


def _build_cohort_plan(
    *,
    protocol: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    analysis_mode: str,
) -> Dict[str, Any]:
    inferred = _infer_protocol_column_sets(protocol)
    required_all = inferred.get("required_all") or []
    predictor_like = inferred.get("predictor_like") or []
    outcomes = inferred.get("outcomes") or []

    mode_raw = (
        preferences.get("analysis_set_mode")
        or preferences.get("fixed_cohort_mode")
        or preferences.get("cohort_mode")
        or "complete_case"
    )
    mode = str(mode_raw or "").strip().lower() or "complete_case"
    if mode not in {"complete_case", "simple_impute"}:
        mode = "complete_case"

    enforce_raw = preferences.get("analysis_set_enforce") or preferences.get("fixed_cohort_enforce") or "models"
    enforce = str(enforce_raw or "").strip().lower() or "models"
    if enforce not in {"models", "all"}:
        enforce = "models"

    strict = _as_bool(preferences.get("analysis_set_strict"), default=True)
    if analysis_mode == "publication":
        strict = True

    impute_columns: List[str] = []
    required_non_missing: List[str] = list(required_all)
    if mode == "simple_impute":
        impute_columns = sorted([c for c in predictor_like if c in set(required_all)])
        required_non_missing = sorted([c for c in required_all if c not in set(impute_columns)])
        if not required_non_missing:
            required_non_missing = sorted(outcomes[:1] or required_all[:1])

    analysis_set_id = str(preferences.get("analysis_set_id") or preferences.get("analysis_set") or "").strip() or None
    required = bool(required_all) or analysis_mode == "publication"

    notes: List[str] = []
    if analysis_mode == "publication":
        notes.append("Freeze cohort обязателен: execute будет отклонён без валидного analysis_set.")
    if not required_all:
        notes.append("В текущем протоколе не найдено регрессионных шагов; зафиксируйте cohort вручную при необходимости.")

    return {
        "version": 1,
        "required": required,
        "mode": mode,
        "enforce": enforce,
        "strict": strict,
        "analysis_set_id": analysis_set_id,
        "required_non_missing": required_non_missing,
        "impute_columns": impute_columns,
        "notes": notes,
    }


def _build_report_spec(*, protocol: List[Dict[str, Any]], analysis_mode: str) -> Dict[str, Any]:
    inferred = _infer_protocol_column_sets(protocol)
    methods = set(inferred.get("methods") or [])

    sections = [
        {"id": "design", "title": "Design", "required": True},
        {"id": "methods", "title": "Methods", "required": True},
        {"id": "results", "title": "Results", "required": True},
        {"id": "discussion", "title": "Discussion", "required": True},
        {"id": "limitations", "title": "Limitations", "required": True},
    ]

    table_requirements: List[Dict[str, Any]] = [
        {"id": "baseline", "required": True, "description": "Baseline descriptives by group/time."},
        {"id": "inferential_summary", "required": True, "description": "Inferential summary with p and p(adj)."},
    ]

    if methods & {"linear_regression", "logistic_regression"}:
        table_requirements.append(
            {"id": "model_coefficients", "required": True, "description": "Regression coefficients/OR with CI."}
        )
    if methods & {"batch_analysis", "timepoint_batch_analysis", "delta_batch_analysis"}:
        table_requirements.append(
            {"id": "multiplicity", "required": True, "description": "Multiplicity correction and adjusted p-values."}
        )

    figure_requirements: List[Dict[str, Any]] = []
    if methods & {"linear_regression", "logistic_regression", "roc_analysis"}:
        figure_requirements.append({"id": "roc_curve", "required": False})
    if methods & {"clustered_correlation", "pearson", "spearman", "kendall"}:
        figure_requirements.append({"id": "correlation_heatmap", "required": False})
    if methods & {"t_test_ind", "t_test_welch", "mann_whitney", "anova", "anova_welch", "kruskal"}:
        figure_requirements.append({"id": "group_distribution", "required": False})
    if methods & {"time_series_analysis"}:
        figure_requirements.append({"id": "time_series_plot", "required": True})

    return {
        "version": 1,
        "style": "publication" if analysis_mode == "publication" else "standard",
        "sections": sections,
        "table_requirements": table_requirements,
        "figure_requirements": figure_requirements,
        "interpretation_rules": {
            "per_table": True,
            "per_figure": True,
            "link_to_research_question": True,
        },
        "strict_interpretations": analysis_mode == "publication",
        "export_formats": ["html", "docx", "pdf"],
    }



def _load_model_router_benchmark_capture_last(workspace_dir: Path) -> Dict[str, Any]:
    capture_summary: Dict[str, Any] = {
        "available": False,
        "status": "missing",
        "generated_at": None,
        "dataset_id": None,
        "analysis_mode": None,
        "validation_profile": None,
        "skip_reason": None,
        "run_id": None,
        "recommended_id": None,
        "recommendation_source": None,
        "snapshot": {"summary": {}, "coverage_gate": {}},
    }
    capture_path = workspace_dir.parent / "release" / "model_router_benchmark_capture_last.json"
    if not capture_path.exists():
        return capture_summary

    try:
        raw = json.loads(capture_path.read_text(encoding="utf-8"))
    except Exception:
        capture_summary["status"] = "invalid"
        return capture_summary

    if not isinstance(raw, dict):
        capture_summary["status"] = "invalid"
        return capture_summary

    snapshot_raw = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else {}
    summary = snapshot_raw.get("summary") if isinstance(snapshot_raw.get("summary"), dict) else {}
    coverage_gate = snapshot_raw.get("coverage_gate") if isinstance(snapshot_raw.get("coverage_gate"), dict) else {}
    capture_summary.update(
        {
            "available": True,
            "status": str(raw.get("status") or "").strip().lower() or "unknown",
            "generated_at": raw.get("generated_at") if isinstance(raw.get("generated_at"), str) else None,
            "dataset_id": raw.get("dataset_id") if isinstance(raw.get("dataset_id"), str) else None,
            "analysis_mode": raw.get("analysis_mode") if isinstance(raw.get("analysis_mode"), str) else None,
            "validation_profile": (
                raw.get("validation_profile") if isinstance(raw.get("validation_profile"), str) else None
            ),
            "skip_reason": raw.get("skip_reason") if isinstance(raw.get("skip_reason"), str) else None,
            "run_id": raw.get("run_id") if isinstance(raw.get("run_id"), str) else None,
            "recommended_id": raw.get("recommended_id") if isinstance(raw.get("recommended_id"), str) else None,
            "recommendation_source": (
                raw.get("recommendation_source") if isinstance(raw.get("recommendation_source"), str) else None
            ),
            "snapshot": {
                "summary": summary,
                "coverage_gate": coverage_gate,
            },
        }
    )
    return capture_summary

