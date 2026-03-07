from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.stats.engine import _apply_multiplicity_with_trace


def _finite_float(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    if out != out:
        return None
    if out in {float("inf"), float("-inf")}:
        return None
    return float(out)


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
    if corr in {"holm-sidak", "holmsidak", "holm_sidak"}:
        return "holm-sidak"
    if corr in {"none", "off", "no"}:
        return "none"
    return corr or "none"


def iter_result_payload_entries(results: Any) -> List[Tuple[str, Dict[str, Any]]]:
    entries: List[Tuple[str, Dict[str, Any]]] = []
    if isinstance(results, dict):
        for step_id, payload in results.items():
            if isinstance(payload, dict):
                entries.append((str(step_id), payload))
        return entries
    if isinstance(results, list):
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            payload = item.get("results") if isinstance(item.get("results"), dict) else item
            if not isinstance(payload, dict):
                continue
            step_id = item.get("step_id") or item.get("id") or f"step_{idx + 1}"
            entries.append((str(step_id), payload))
    return entries


def extract_step_p_value(payload: Dict[str, Any]) -> Optional[float]:
    for field in ["p_value_raw", "p_value", "p_value_adj"]:
        val = _finite_float(payload.get(field))
        if val is not None:
            return float(val)
    return None


def repair_run_payload_multiplicity(
    run_payload: Dict[str, Any],
    *,
    alpha: float,
    correction: str = "fdr_bh",
) -> Dict[str, Any]:
    results = run_payload.get("results")
    if not isinstance(results, dict):
        return {"changed": False, "reason": "results_not_mapping"}

    step_rows: List[Tuple[str, Dict[str, Any], float]] = []
    p_values: List[float] = []
    for step_id, payload in iter_result_payload_entries(results):
        p_val = extract_step_p_value(payload)
        if p_val is None:
            continue
        step_rows.append((step_id, payload, float(p_val)))
        p_values.append(float(p_val))

    if not step_rows:
        return {"changed": False, "reason": "no_p_values"}

    corr_result = _apply_multiplicity_with_trace(
        p_values,
        alpha=float(alpha),
        correction=correction,
    )
    if not isinstance(corr_result, dict):
        return {"changed": False, "reason": "multiplicity_failed"}

    method = _normalize_correction(corr_result.get("method")) or "none"
    adjusted = corr_result.get("adjusted") if isinstance(corr_result.get("adjusted"), list) else []
    rejected = corr_result.get("rejected") if isinstance(corr_result.get("rejected"), list) else []
    trace_obj = corr_result.get("trace") if isinstance(corr_result.get("trace"), dict) else {}

    changed_steps: List[str] = []
    for idx, (step_id, payload, p_raw) in enumerate(step_rows):
        p_adj_raw = adjusted[idx] if idx < len(adjusted) else None
        p_adj = _finite_float(p_adj_raw)
        if p_adj is None:
            p_adj = float(p_raw)
        sig_adj_raw = rejected[idx] if idx < len(rejected) else None
        sig_adj = bool(sig_adj_raw) if isinstance(sig_adj_raw, bool) else bool(p_adj < float(alpha))

        trace_step = {
            "scope": "verification_repair",
            "method": method,
            "alpha": float(alpha),
            "n_total": int(trace_obj.get("n_total") or len(step_rows)),
            "n_valid": int(trace_obj.get("n_valid") or len(step_rows)),
            "valid_indices": trace_obj.get("valid_indices")
            if isinstance(trace_obj.get("valid_indices"), list)
            else list(range(len(step_rows))),
            "p_values_raw": trace_obj.get("p_values_raw")
            if isinstance(trace_obj.get("p_values_raw"), list)
            else [row[2] for row in step_rows],
            "p_values_adj": trace_obj.get("p_values_adj")
            if isinstance(trace_obj.get("p_values_adj"), list)
            else adjusted,
            "row_index": idx,
        }

        next_payload = dict(payload)
        if _finite_float(next_payload.get("p_value_raw")) is None:
            next_payload["p_value_raw"] = float(p_raw)
        next_payload["multiplicity_correction"] = method
        next_payload["p_value_adj"] = float(p_adj)
        next_payload["significant_adj"] = bool(sig_adj)
        next_payload["multiplicity_trace"] = trace_step

        if next_payload != payload:
            results[step_id] = next_payload
            changed_steps.append(step_id)

    return {
        "changed": bool(changed_steps),
        "kind": "multiplicity_repair",
        "method": method,
        "steps": changed_steps,
        "n_steps": int(len(changed_steps)),
    }


def repair_run_payload_p_bounds(
    run_payload: Dict[str, Any],
    *,
    epsilon: float = 1e-12,
) -> Dict[str, Any]:
    results = run_payload.get("results")
    if not isinstance(results, dict):
        return {"changed": False, "reason": "results_not_mapping"}

    changed_rows: List[Dict[str, Any]] = []
    for step_id, payload in iter_result_payload_entries(results):
        updated = dict(payload)
        row_changed = False
        for field in ["p_value", "p_value_raw", "p_value_adj"]:
            val = _finite_float(updated.get(field))
            if val is None:
                continue
            if val < 0.0 and val >= (0.0 - float(epsilon)):
                updated[field] = 0.0
                row_changed = True
            elif val > 1.0 and val <= (1.0 + float(epsilon)):
                updated[field] = 1.0
                row_changed = True
        if row_changed:
            results[step_id] = updated
            changed_rows.append({"step_id": step_id})

    return {
        "changed": bool(changed_rows),
        "kind": "p_value_bounds_repair",
        "steps": [row["step_id"] for row in changed_rows],
        "n_steps": int(len(changed_rows)),
    }


def attempt_verifier_reflection_repair(
    run_payload: Dict[str, Any],
    *,
    verification: Dict[str, Any],
    alpha: float,
    correction: str = "fdr_bh",
) -> Dict[str, Any]:
    failures = verification.get("failures") if isinstance(verification, dict) else None
    if not isinstance(failures, list) or not failures:
        return {"applied": False, "reason": "no_failures"}

    failure_checks: List[str] = []
    for item in failures:
        if isinstance(item, dict):
            failure_checks.append(str(item.get("check") or "").strip().lower())
    checks = {check for check in failure_checks if check}

    if checks.intersection({"multiplicity_trace_method", "multiplicity_trace_counts"}):
        repaired = repair_run_payload_multiplicity(
            run_payload,
            alpha=float(alpha),
            correction=correction,
        )
        if repaired.get("changed"):
            return {
                "applied": True,
                "reason": "multiplicity_trace_repaired",
                "details": repaired,
            }

    if "p_value_bounds" in checks:
        repaired = repair_run_payload_p_bounds(run_payload)
        if repaired.get("changed"):
            return {
                "applied": True,
                "reason": "p_value_bounds_repaired",
                "details": repaired,
            }

    return {
        "applied": False,
        "reason": "no_deterministic_repair_available",
        "checks": sorted(list(checks)),
    }

