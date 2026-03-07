from __future__ import annotations

from datetime import datetime
import math
from typing import Any, Dict, Iterable, List, Optional, Tuple


ALLOWED_MULTIPLICITY_METHODS = {
    "none",
    "fdr_bh",
    "fdr_by",
    "fdr_tsbky",
    "holm",
    "bonferroni",
    "sidak",
    "holm-sidak",
}


def _normalize_correction(value: Any) -> str:
    corr = str(value or "").strip().lower()
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
    if corr in {"holm-sidak", "holm_sidak", "holmsidak"}:
        return "holm-sidak"
    if corr in {"none", "off", "no", ""}:
        return "none"
    return corr


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        out = float(value)
        if not math.isfinite(out):
            return None
        return out
    except Exception:
        return None


def _iter_step_payloads(run_payload: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    results = run_payload.get("results")
    if isinstance(results, dict):
        for step_id, payload in results.items():
            if isinstance(payload, dict):
                yield str(step_id), payload
        return
    if isinstance(results, list):
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            step_id = item.get("step_id") or item.get("id") or f"step_{idx + 1}"
            payload = item.get("results") if isinstance(item.get("results"), dict) else item
            if isinstance(payload, dict):
                yield str(step_id), payload


def _append_issue(bucket: List[Dict[str, Any]], *, check: str, step_id: str, message: str) -> None:
    bucket.append({"check": check, "step_id": step_id, "message": message})


def verify_run_payload(run_payload: Dict[str, Any], *, alpha: float = 0.05) -> Dict[str, Any]:
    failures: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []
    p_value_steps: List[str] = []
    multiplicity_covered_steps: List[str] = []

    for step_id, payload in _iter_step_payloads(run_payload if isinstance(run_payload, dict) else {}):
        p_value = _to_float(payload.get("p_value"))
        p_raw = _to_float(payload.get("p_value_raw"))
        p_adj = _to_float(payload.get("p_value_adj"))
        p_candidates = [("p_value", p_value), ("p_value_raw", p_raw), ("p_value_adj", p_adj)]
        for label, p in p_candidates:
            if p is None:
                continue
            checks.append({"check": "p_value_bounds", "step_id": step_id, "field": label, "value": p})
            if p < 0.0 or p > 1.0:
                _append_issue(
                    failures,
                    check="p_value_bounds",
                    step_id=step_id,
                    message=f"{label} out of [0,1]: {p}",
                )
        if any(p is not None for _, p in p_candidates):
            p_value_steps.append(step_id)

        effect_size_raw = payload.get("effect_size")
        if effect_size_raw is not None and _to_float(effect_size_raw) is None:
            checks.append(
                {
                    "check": "effect_size_finite",
                    "step_id": step_id,
                    "value": effect_size_raw,
                }
            )
            _append_issue(
                failures,
                check="effect_size_finite",
                step_id=step_id,
                message=f"effect_size is non-finite: {effect_size_raw}",
            )

        ci_lower = _to_float(payload.get("effect_size_ci_lower"))
        ci_upper = _to_float(payload.get("effect_size_ci_upper"))
        effect_size = _to_float(payload.get("effect_size"))
        if ci_lower is not None and ci_upper is not None:
            checks.append(
                {
                    "check": "effect_ci_order",
                    "step_id": step_id,
                    "ci_lower": ci_lower,
                    "ci_upper": ci_upper,
                }
            )
            if ci_lower >= ci_upper:
                _append_issue(
                    failures,
                    check="effect_ci_order",
                    step_id=step_id,
                    message=f"effect_size_ci_lower >= effect_size_ci_upper ({ci_lower} >= {ci_upper})",
                )
            if effect_size is not None and not (ci_lower <= effect_size <= ci_upper):
                _append_issue(
                    warnings,
                    check="effect_outside_ci",
                    step_id=step_id,
                    message=(
                        "effect_size is outside its CI bounds; verify effect/CI extraction "
                        f"(effect={effect_size}, ci=[{ci_lower}, {ci_upper}])"
                    ),
                )

        trace = payload.get("multiplicity_trace")
        step_correction = _normalize_correction(payload.get("multiplicity_correction"))
        if step_correction != "none":
            multiplicity_covered_steps.append(step_id)
        if isinstance(trace, dict):
            method = str(trace.get("method") or "").strip().lower() or "none"
            checks.append({"check": "multiplicity_trace_method", "step_id": step_id, "method": method})
            if method not in ALLOWED_MULTIPLICITY_METHODS:
                _append_issue(
                    failures,
                    check="multiplicity_trace_method",
                    step_id=step_id,
                    message=f"Unsupported multiplicity method in trace: {method}",
                )
            if method != "none":
                multiplicity_covered_steps.append(step_id)
            n_total = trace.get("n_total")
            n_valid = trace.get("n_valid")
            try:
                n_total_i = int(n_total)
                n_valid_i = int(n_valid)
                checks.append(
                    {
                        "check": "multiplicity_trace_counts",
                        "step_id": step_id,
                        "n_total": n_total_i,
                        "n_valid": n_valid_i,
                    }
                )
                if n_total_i < 0 or n_valid_i < 0 or n_valid_i > n_total_i:
                    _append_issue(
                        failures,
                        check="multiplicity_trace_counts",
                        step_id=step_id,
                        message=f"Invalid multiplicity counts: n_total={n_total_i}, n_valid={n_valid_i}",
                    )
            except Exception:
                _append_issue(
                    warnings,
                    check="multiplicity_trace_counts",
                    step_id=step_id,
                    message="Multiplicity counts are not numeric.",
                )

        sig_adj = payload.get("significant_adj")
        if isinstance(sig_adj, bool) and p_adj is not None:
            expected = bool(p_adj < float(alpha))
            checks.append(
                {
                    "check": "significant_adj_consistency",
                    "step_id": step_id,
                    "significant_adj": sig_adj,
                    "p_value_adj": p_adj,
                    "alpha": float(alpha),
                }
            )
            if sig_adj != expected:
                _append_issue(
                    warnings,
                    check="significant_adj_consistency",
                    step_id=step_id,
                    message=f"significant_adj={sig_adj} is inconsistent with p_value_adj={p_adj} at alpha={alpha}",
                )

    if len(p_value_steps) >= 2:
        policy_obj = run_payload.get("multiplicity_policy") if isinstance(run_payload, dict) else None
        policy_obj = policy_obj if isinstance(policy_obj, dict) else {}
        global_correction = _normalize_correction(
            policy_obj.get("correction")
            or policy_obj.get("multiplicity_correction")
            or run_payload.get("multiplicity_correction")
        )
        if global_correction != "none":
            multiplicity_covered_steps.extend(p_value_steps)

        covered = {str(s) for s in multiplicity_covered_steps if str(s)}
        missing = [str(s) for s in p_value_steps if str(s) not in covered]
        checks.append(
            {
                "check": "multiplicity_correction_required",
                "n_pvalue_steps": int(len(p_value_steps)),
                "global_correction": global_correction,
                "covered_steps": sorted(list(covered)),
                "missing_steps": missing,
            }
        )
        if missing:
            _append_issue(
                failures,
                check="multiplicity_correction_required",
                step_id="__global__",
                message=(
                    "Multiple p-value steps require multiplicity correction; "
                    f"missing for steps: {', '.join(missing)}"
                ),
            )

    status = "passed" if not failures else "failed"
    return {
        "schema": "clinimetria.verification",
        "version": 1,
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "status": status,
        "summary": {
            "checks_total": len(checks),
            "failed": len(failures),
            "warnings": len(warnings),
        },
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
    }
