from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple


def _norm_status(value: Any, *, default: str = "missing") -> str:
    text = str(value or "").strip().lower()
    return text or default


def _collect_failed_step_ids(verification: Any) -> List[str]:
    if not isinstance(verification, dict):
        return []
    failures = verification.get("failures")
    if not isinstance(failures, list):
        return []

    out: List[str] = []
    for row in failures:
        if not isinstance(row, dict):
            continue
        step_id = row.get("step_id")
        if not isinstance(step_id, str):
            continue
        sid = step_id.strip()
        if sid:
            out.append(sid)
    return list(dict.fromkeys(out))


def build_report_integrity_context(
    run_data: Any,
    *,
    run_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = run_data if isinstance(run_data, dict) else {}

    verification = data.get("verification")
    verification_present = isinstance(verification, dict)
    verification_status = _norm_status(
        verification.get("status") if isinstance(verification, dict) else None
    )
    failed_steps = _collect_failed_step_ids(verification)
    block_all_steps = bool(
        verification_present and verification_status in {"failed", "error", "blocked"} and not failed_steps
    )
    verification_ok = bool(verification_present and verification_status in {"passed", "ok"})

    state_payload = run_state if isinstance(run_state, dict) else data.get("run_state")
    state_payload = state_payload if isinstance(state_payload, dict) else {}
    state_value = _norm_status(state_payload.get("state"), default="")
    state_artifacts = state_payload.get("artifacts")
    if not isinstance(state_artifacts, dict):
        state_artifacts = {}
    missing_state_artifacts = state_payload.get("missing_artifacts")
    if not isinstance(missing_state_artifacts, list):
        missing_state_artifacts = []

    reproducibility = data.get("reproducibility")
    reproducibility = reproducibility if isinstance(reproducibility, dict) else {}
    reproducibility_present = bool(reproducibility)
    reproducibility_ready = bool(reproducibility.get("ready"))
    missing_repro_fields: List[str] = []
    for key in ["manifest", "script", "payload", "protocol"]:
        value = reproducibility.get(key)
        if not isinstance(value, str) or not value.strip():
            missing_repro_fields.append(key)

    return {
        "verification": {
            "present": verification_present,
            "status": verification_status,
            "ok": verification_ok,
            "failed_steps": failed_steps,
            "block_all_steps": block_all_steps,
        },
        "provenance": {
            "run_state_present": bool(state_payload),
            "state": state_value,
            "state_artifacts": state_artifacts,
            "missing_state_artifacts": [str(x) for x in missing_state_artifacts if str(x).strip()],
            "reproducibility_present": reproducibility_present,
            "reproducibility_ready": reproducibility_ready,
            "missing_reproducibility_fields": missing_repro_fields,
        },
    }


def filter_step_pairs_for_report(
    step_pairs: Sequence[Tuple[Any, Any]],
    integrity: Optional[Dict[str, Any]],
) -> Tuple[List[Tuple[str, Dict[str, Any]]], Dict[str, Any]]:
    pairs: List[Tuple[str, Dict[str, Any]]] = []
    for item in step_pairs:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        step_id, payload = item
        if not isinstance(step_id, str) or not isinstance(payload, dict):
            continue
        sid = step_id.strip()
        if sid:
            pairs.append((sid, payload))

    verification = integrity.get("verification") if isinstance(integrity, dict) else {}
    verification = verification if isinstance(verification, dict) else {}
    status = _norm_status(verification.get("status"))
    present = bool(verification.get("present"))
    block_all_steps = bool(verification.get("block_all_steps"))
    failed_steps_raw = verification.get("failed_steps")
    failed_steps = (
        set([str(x).strip() for x in failed_steps_raw if isinstance(x, str) and str(x).strip()])
        if isinstance(failed_steps_raw, list)
        else set()
    )

    if not present or status in {"passed", "ok"}:
        return pairs, {
            "verification_status": status,
            "verification_present": present,
            "excluded_step_ids": [],
            "source_total_steps": len(pairs),
        }

    if block_all_steps:
        excluded = [sid for sid, _ in pairs]
        return [], {
            "verification_status": status,
            "verification_present": present,
            "excluded_step_ids": excluded,
            "source_total_steps": len(pairs),
        }

    if not failed_steps:
        return pairs, {
            "verification_status": status,
            "verification_present": present,
            "excluded_step_ids": [],
            "source_total_steps": len(pairs),
        }

    filtered: List[Tuple[str, Dict[str, Any]]] = []
    excluded: List[str] = []
    for sid, payload in pairs:
        if sid in failed_steps:
            excluded.append(sid)
            continue
        filtered.append((sid, payload))

    return filtered, {
        "verification_status": status,
        "verification_present": present,
        "excluded_step_ids": excluded,
        "source_total_steps": len(pairs),
    }
