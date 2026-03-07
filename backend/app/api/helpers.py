"""Pure helper utilities for API v2."""
from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


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


def _ensure_method(payload: Dict[str, Any], method_id: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    if payload.get("method"):
        return payload
    payload["method"] = {"id": method_id, "name": method_id}
    return payload


def _canonical_method_id(raw_method: Any) -> str:
    method = str(raw_method or "").strip().lower()
    if not method:
        return ""
    aliases = {
        "mixed_model": "mixed_effects",
        "fisher": "fisher_exact",
        "welch_t_test": "t_test_welch",
        "kruskal_wallis": "kruskal",
        "two_way_anova": "anova_twoway",
        "hierarchical": "hierarchical_clustering",
        "hierarchical_cluster": "hierarchical_clustering",
        "hclust": "hierarchical_clustering",
        "k_means": "kmeans",
        "factor_analysis": "efa",
        "exploratory_factor_analysis": "efa",
        "principal_component_analysis": "pca",
        "cohen_kappa": "cohens_kappa",
        "cronbach": "cronbach_alpha",
        "shapiro": "shapiro_wilk",
        "bland_altman_analysis": "bland_altman",
        "point-biserial": "point_biserial",
        "partial_corr": "partial_correlation",
        "cochranq": "cochran_q",
        "bayesian_t_test_one": "bayes_t_test_one",
        "bayesian_t_test_ind": "bayes_t_test_ind",
        "bayesian_t_test_rel": "bayes_t_test_rel",
        "bayesian_correlation": "bayes_correlation",
        "bayesian_anova": "bayes_anova",
        "bayesian_linear_regression": "bayes_linear_regression",
        "bayesian_chi_square": "bayes_chi_square",
        "bayes_regression": "bayes_linear_regression",
        "bayes_chisq": "bayes_chi_square",
        "bayes_corr": "bayes_correlation",
        "time_series": "time_series_analysis",
        "timeseries": "time_series_analysis",
    }
    return aliases.get(method, method)


def _normalize_plan_step(item: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    raw_method = item.get("method") or item.get("test") or item.get("type")
    method = _canonical_method_id(raw_method)
    if not method:
        return None

    raw_config = item.get("config")
    config = raw_config if isinstance(raw_config, dict) else {}
    name = str(item.get("name") or "").strip() or None
    step_id = str(item.get("id") or f"ai_{idx + 1}").strip()
    if not name:
        name = method.replace("_", " ").title()

    if "outcome" not in config and "target" in config:
        config = {**config, "outcome": config.get("target")}
    if "target" not in config and "outcome" in config and method == "descriptive_compare":
        config = {**config, "target": config.get("outcome")}
    if "group" not in config and "predictor" in config:
        config = {**config, "group": config.get("predictor")}

    return {"id": step_id, "name": name, "method": method, "config": config}


def _to_int_or_none(value: Any) -> Optional[int]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except Exception:
        return None


def _to_float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    except Exception:
        return None


def _runtime_elapsed_ms(start_perf: float, end_perf: Optional[float] = None) -> int:
    try:
        end_value = float(end_perf) if isinstance(end_perf, (int, float)) else float(time.perf_counter())
        delta = max(0.0, end_value - float(start_perf))
        return int(round(delta * 1000.0))
    except Exception:
        return 0


def _runtime_percentile_ms(values: List[int], quantile: float) -> int:
    if not values:
        return 0
    q = max(0.0, min(1.0, float(quantile)))
    sorted_values = sorted([max(0, int(v)) for v in values])
    idx = int(math.ceil(q * len(sorted_values)) - 1)
    idx = max(0, min(len(sorted_values) - 1, idx))
    return int(sorted_values[idx])


def _normalize_role_models_payload(raw: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    allowed = {"planner", "quality", "interpret", "report", "codegen"}
    out: Dict[str, str] = {}
    for key, value in raw.items():
        key_norm = str(key or "").strip().lower()
        if key_norm not in allowed:
            continue
        model = str(value or "").strip()
        if model:
            out[key_norm] = model
    return out or None


def _benchmark_clamp01(value: Any, fallback: float = 0.0) -> float:
    try:
        number = float(value)
        if not math.isfinite(number):
            return float(fallback)
        return float(max(0.0, min(1.0, number)))
    except Exception:
        return float(fallback)


def _normalize_benchmark_analysis_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode == "publication":
        return "publication"
    if mode == "focused":
        return "focused"
    return "exploratory"


def _normalize_benchmark_validation_profile(value: Any, *, analysis_mode: str) -> str:
    profile = str(value or "").strip().lower()
    if profile in {"publication", "focused", "exploratory"}:
        return profile
    if analysis_mode == "publication":
        return "publication"
    if analysis_mode == "focused":
        return "focused"
    return "exploratory"


def _resolve_llm_benchmark_score_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    analysis_mode = _normalize_benchmark_analysis_mode(row.get("analysis_mode"))
    validation_profile = _normalize_benchmark_validation_profile(
        row.get("validation_profile"),
        analysis_mode=analysis_mode,
    )
    if validation_profile == "publication":
        return {
            "analysis_mode": analysis_mode,
            "validation_profile": validation_profile,
            "weights": {
                "quality": 0.74,
                "latency": 0.08,
                "token": 0.03,
                "step": 0.03,
                "reliability": 0.12,
            },
            "penalties": {
                "fallback": 0.15,
                "retry_per_attempt": 0.03,
                "fallback_reliability_factor": 0.55,
            },
        }
    if validation_profile == "focused":
        return {
            "analysis_mode": analysis_mode,
            "validation_profile": validation_profile,
            "weights": {
                "quality": 0.70,
                "latency": 0.10,
                "token": 0.05,
                "step": 0.03,
                "reliability": 0.12,
            },
            "penalties": {
                "fallback": 0.13,
                "retry_per_attempt": 0.025,
                "fallback_reliability_factor": 0.60,
            },
        }
    return {
        "analysis_mode": analysis_mode,
        "validation_profile": validation_profile,
        "weights": {
            "quality": 0.76,
            "latency": 0.14,
            "token": 0.07,
            "step": 0.02,
            "reliability": 0.01,
        },
        "penalties": {
            "fallback": 0.01,
            "retry_per_attempt": 0.004,
            "fallback_reliability_factor": 0.90,
        },
    }


def _score_benchmark_latency(elapsed_ms: Any) -> float:
    elapsed = _to_float_or_none(elapsed_ms)
    if not isinstance(elapsed, float) or elapsed < 0:
        return 0.5
    return _benchmark_clamp01(1.0 / (1.0 + elapsed / 2000.0), fallback=0.5)


def _score_benchmark_token_efficiency(token_total: Any) -> float:
    token_value = _to_float_or_none(token_total)
    if not isinstance(token_value, float) or token_value < 0:
        return 0.5
    return _benchmark_clamp01(1.0 / (1.0 + token_value / 6000.0), fallback=0.5)


def _score_benchmark_step_coverage(step_count: Any, expected_step_count: Any = None) -> float:
    steps = _to_float_or_none(step_count)
    expected_raw = _to_float_or_none(expected_step_count)
    expected = expected_raw if isinstance(expected_raw, float) and expected_raw > 0 else 12.0
    if not isinstance(steps, float) or steps < 0:
        return 0.5
    return _benchmark_clamp01(steps / expected, fallback=0.5)


def _score_benchmark_retry_efficiency(attempt_count: Any) -> float:
    attempts = _to_float_or_none(attempt_count)
    if not isinstance(attempts, float) or attempts < 1:
        return 1.0
    return _benchmark_clamp01(1.0 / (1.0 + max(0.0, attempts - 1.0)), fallback=1.0)


def _llm_benchmark_auto_score(row: Dict[str, Any]) -> float:
    profile = _resolve_llm_benchmark_score_profile(row)
    weights = profile.get("weights") if isinstance(profile.get("weights"), dict) else {}
    penalties = profile.get("penalties") if isinstance(profile.get("penalties"), dict) else {}

    benchmark = _to_float_or_none(row.get("benchmark_score"))
    quality = _to_float_or_none(row.get("quality_score"))
    quality_norm = _benchmark_clamp01((quality or 0.0) / 100.0, fallback=0.0)
    if isinstance(benchmark, float):
        benchmark_norm = _benchmark_clamp01(benchmark, fallback=quality_norm)
        quality_norm = _benchmark_clamp01((benchmark_norm * 0.75) + (quality_norm * 0.25), fallback=benchmark_norm)

    latency = _score_benchmark_latency(row.get("elapsed_ms"))
    token_efficiency = _score_benchmark_token_efficiency(row.get("token_total"))
    step_coverage = _score_benchmark_step_coverage(
        row.get("step_count"),
        expected_step_count=row.get("expected_step_count"),
    )
    retry_efficiency = _score_benchmark_retry_efficiency(row.get("attempt_count"))

    fallback_used = bool(row.get("fallback_used"))
    attempt_count_raw = _to_int_or_none(row.get("attempt_count"))
    attempt_count = int(attempt_count_raw) if isinstance(attempt_count_raw, int) else 1

    fallback_reliability_factor = _benchmark_clamp01(
        penalties.get("fallback_reliability_factor"),
        fallback=0.72,
    )
    reliability = _benchmark_clamp01(
        (fallback_reliability_factor if fallback_used else 1.0) * 0.7 + retry_efficiency * 0.3,
        fallback=0.0,
    )

    fallback_penalty = float(max(0.0, penalties.get("fallback") or 0.0)) if fallback_used else 0.0
    retry_penalty_per_attempt = float(max(0.0, penalties.get("retry_per_attempt") or 0.0))
    retry_penalty = min(0.12, max(0.0, float(attempt_count - 1) * retry_penalty_per_attempt))

    weighted_score = (
        quality_norm * float(weights.get("quality") or 0.63)
        + latency * float(weights.get("latency") or 0.17)
        + token_efficiency * float(weights.get("token") or 0.10)
        + step_coverage * float(weights.get("step") or 0.05)
        + reliability * float(weights.get("reliability") or 0.05)
        - fallback_penalty
        - retry_penalty
    )
    return float(round(weighted_score * 100.0, 4))


def _normalize_llm_benchmark_payload(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    rows_raw = raw.get("variants")
    if not isinstance(rows_raw, list):
        rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list):
        return None

    benchmark_context_raw = raw.get("benchmark_context") if isinstance(raw.get("benchmark_context"), dict) else {}
    context_analysis_mode = _normalize_benchmark_analysis_mode(
        benchmark_context_raw.get("analysis_mode")
        or raw.get("analysis_mode")
        or raw.get("mode")
    )
    context_validation_profile = _normalize_benchmark_validation_profile(
        benchmark_context_raw.get("validation_profile")
        or raw.get("validation_profile")
        or raw.get("policy_profile"),
        analysis_mode=context_analysis_mode,
    )
    context_expected_step_count = _to_int_or_none(
        benchmark_context_raw.get("expected_step_count")
        if "expected_step_count" in benchmark_context_raw
        else raw.get("expected_step_count")
    )
    if isinstance(context_expected_step_count, int):
        context_expected_step_count = max(1, context_expected_step_count)

    rows_out: List[Dict[str, Any]] = []
    for item in rows_raw[:20]:
        if not isinstance(item, dict):
            continue
        row: Dict[str, Any] = {
            "id": str(item.get("id") or "").strip() or None,
            "label": str(item.get("label") or "").strip() or None,
            "status": str(item.get("status") or "").strip().lower() or "unknown",
            "recommended": bool(item.get("recommended")),
        }

        elapsed_ms = _to_int_or_none(item.get("elapsed_ms") if "elapsed_ms" in item else item.get("elapsedMs"))
        if isinstance(elapsed_ms, int):
            row["elapsed_ms"] = max(0, elapsed_ms)

        quality_score = _to_float_or_none(
            item.get("quality_score") if "quality_score" in item else item.get("qualityScore")
        )
        if isinstance(quality_score, float):
            row["quality_score"] = quality_score

        benchmark_score = _to_float_or_none(
            item.get("benchmark_score") if "benchmark_score" in item else item.get("benchmarkScore")
        )
        if isinstance(benchmark_score, float):
            row["benchmark_score"] = max(0.0, min(1.0, benchmark_score))

        step_count = _to_int_or_none(item.get("step_count") if "step_count" in item else item.get("stepCount"))
        if isinstance(step_count, int):
            row["step_count"] = max(0, step_count)

        token_total = _to_int_or_none(item.get("token_total") if "token_total" in item else item.get("tokenTotal"))
        if isinstance(token_total, int):
            row["token_total"] = max(0, token_total)

        attempt_count = _to_int_or_none(
            item.get("attempt_count") if "attempt_count" in item else item.get("attemptCount")
        )
        if isinstance(attempt_count, int):
            row["attempt_count"] = max(1, attempt_count)

        fallback_used = item.get("fallback_used")
        if not isinstance(fallback_used, bool):
            fallback_used = item.get("fallbackUsed")
        if isinstance(fallback_used, bool):
            row["fallback_used"] = fallback_used

        model_used = str(item.get("model_used") if "model_used" in item else item.get("modelUsed") or "").strip()
        if model_used:
            row["model_used"] = model_used

        error_text = str(item.get("error") or "").strip()
        if error_text:
            row["error"] = error_text[:500]

        planner_model = str(item.get("planner_model") or item.get("plannerModel") or "").strip()
        models_payload = _normalize_role_models_payload(
            item.get("models") if isinstance(item.get("models"), dict)
            else (
                item.get("llm_models")
                if isinstance(item.get("llm_models"), dict)
                else item.get("role_models")
            )
        )
        if isinstance(models_payload, dict):
            row["models"] = models_payload
            if not planner_model:
                planner_model = str(models_payload.get("planner") or "").strip()
        if planner_model:
            row["planner_model"] = planner_model

        policy_profile = str(
            item.get("validation_profile")
            or item.get("policy_profile")
            or item.get("policyProfile")
            or context_validation_profile
        ).strip().lower()
        if not policy_profile:
            policy_profile = context_validation_profile

        analysis_mode = _normalize_benchmark_analysis_mode(
            item.get("analysis_mode")
            or item.get("mode")
            or context_analysis_mode
        )
        row["analysis_mode"] = analysis_mode

        row["validation_profile"] = _normalize_benchmark_validation_profile(
            policy_profile,
            analysis_mode=analysis_mode,
        )[:64]

        expected_step_count = _to_int_or_none(
            item.get("expected_step_count")
            if "expected_step_count" in item
            else item.get("expectedStepCount")
        )
        if not isinstance(expected_step_count, int):
            expected_step_count = context_expected_step_count
        if isinstance(expected_step_count, int):
            row["expected_step_count"] = max(1, expected_step_count)

        validator_strict = item.get("validator_strict")
        if isinstance(validator_strict, bool):
            row["validator_strict"] = validator_strict

        reflection_enabled = item.get("reflection_enabled")
        if isinstance(reflection_enabled, bool):
            row["reflection_enabled"] = reflection_enabled

        repair_correction = _normalize_correction(
            item.get("repair_correction")
            or item.get("repairCorrection")
        )
        if isinstance(repair_correction, str) and repair_correction:
            row["repair_correction"] = repair_correction

        if row.get("id") or row.get("label"):
            rows_out.append(row)

    if not rows_out:
        return None

    rows_by_id = {
        str(row.get("id")).strip(): row
        for row in rows_out
        if isinstance(row.get("id"), str) and str(row.get("id")).strip()
    }

    recommendation_source = "input"
    recommended_id = str(raw.get("recommended_id") or "").strip() or None
    if recommended_id and recommended_id not in rows_by_id:
        recommended_id = None
    if not recommended_id:
        for row in rows_out:
            if (
                row.get("recommended")
                and row.get("id")
                and str(row.get("status") or "").lower() == "ok"
            ):
                recommended_id = str(row.get("id"))
                recommendation_source = "explicit_flag"
                break

    if not recommended_id:
        candidates = [
            row for row in rows_out
            if row.get("id") and str(row.get("status") or "").lower() == "ok"
        ]
        if not candidates:
            candidates = [row for row in rows_out if row.get("id")]
            recommendation_source = "fallback_first"
        else:
            recommendation_source = "auto_metrics"

        if candidates:
            def _rank_key(item: Dict[str, Any]) -> Tuple[float, float, int, int, int]:
                score = _llm_benchmark_auto_score(item)
                quality = _to_float_or_none(item.get("quality_score")) or 0.0
                fallback_flag = 1 if bool(item.get("fallback_used")) else 0
                elapsed = _to_int_or_none(item.get("elapsed_ms"))
                token = _to_int_or_none(item.get("token_total"))
                elapsed_norm = int(elapsed) if isinstance(elapsed, int) else 10**9
                token_norm = int(token) if isinstance(token, int) else 10**9
                return (float(score), float(quality), -fallback_flag, -elapsed_norm, -token_norm)

            candidates_sorted = sorted(candidates, key=_rank_key, reverse=True)
            top = candidates_sorted[0] if candidates_sorted else None
            if isinstance(top, dict) and top.get("id"):
                recommended_id = str(top.get("id"))

    recommended_models: Optional[Dict[str, str]] = None
    for row in rows_out:
        row["recommended"] = bool(recommended_id and row.get("id") == recommended_id)
        if row["recommended"] and isinstance(row.get("models"), dict):
            recommended_models = dict(row.get("models"))

    recorded_at = raw.get("recorded_at")
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        recorded_at = raw.get("run_at")
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        recorded_at = raw.get("benchmark_run_at")
    if not isinstance(recorded_at, str) or not recorded_at.strip():
        recorded_at = datetime.utcnow().isoformat() + "Z"

    return {
        "schema": "clinimetria.llm_benchmark",
        "version": 1,
        "recorded_at": str(recorded_at).strip(),
        "benchmark_context": {
            "analysis_mode": context_analysis_mode,
            "validation_profile": context_validation_profile,
            "expected_step_count": context_expected_step_count,
            "variant_count": len(rows_out),
        },
        "recommended_id": recommended_id,
        "recommendation_source": recommendation_source,
        "recommended_models": recommended_models,
        "variants": rows_out,
    }


def _normalize_correction(value: Any) -> Optional[str]:
    if value is None:
        return None
    corr = str(value).strip().lower()
    if not corr:
        return None
    if corr in {"bh", "fdr_bh"}:
        return "fdr_bh"
    if corr in {"by", "fdr_by"}:
        return "fdr_by"
    if corr in {"bky", "fdr_bky", "fdr_tsbky"}:
        return "fdr_tsbky"
    if corr in {"bonferroni", "bonf"}:
        return "bonferroni"
    if corr in {"holm"}:
        return "holm"
    if corr in {"sidak"}:
        return "sidak"
    if corr in {"holm-sidak", "holmsidak", "holm_sidak"}:
        return "holm-sidak"
    if corr in {"none", "off", "no"}:
        return "none"
    return corr


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _method_supports_bootstrap(raw_method: Any) -> bool:
    method = _canonical_method_id(raw_method)
    return method in BOOTSTRAP_COMPATIBLE_METHODS


def _method_supports_multiplicity(raw_method: Any) -> bool:
    method = _canonical_method_id(raw_method)
    return method in MULTIPLICITY_COMPATIBLE_METHODS


def _finite_float(value: Any) -> Optional[float]:
    try:
        v = float(value)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v


def _normalize_analysis_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"publication", "publish", "manuscript", "article", "confirmatory"}:
        return "publication"
    if mode in {"focused", "standard", "targeted"}:
        return "focused"
    if mode in {"exploratory", "maximal", "broad", "deep", "mining"}:
        return "exploratory"
    return "exploratory"


def _normalize_validation_profile(value: Any, *, analysis_mode: str) -> str:
    profile = str(value or "").strip().lower()
    if profile in {"", "auto", "default"}:
        profile = analysis_mode
    if profile in {"publication", "publish", "manuscript", "confirmatory"}:
        return "publication"
    if profile in {"focused", "standard", "targeted"}:
        return "focused"
    if profile in {"exploratory", "maximal", "deep", "mining"}:
        return "exploratory"
    return _normalize_analysis_mode(analysis_mode)


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _merge_plan_section(default_section: Dict[str, Any], incoming: Any) -> Dict[str, Any]:
    if not isinstance(default_section, dict):
        return default_section
    if not isinstance(incoming, dict):
        return default_section
    out = dict(default_section)
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        out[key] = value
    return out
