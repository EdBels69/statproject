from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except Exception:
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        number = float(value)
        if not math.isfinite(number):
            return None
        return number
    except Exception:
        return None


def _clamp01(value: Any, fallback: float = 0.0) -> float:
    number = _safe_float(value)
    if not isinstance(number, float):
        return float(fallback)
    return float(max(0.0, min(1.0, number)))


def _normalize_analysis_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode == "publication":
        return "publication"
    if mode == "focused":
        return "focused"
    return "exploratory"


def _normalize_validation_profile(value: Any, *, analysis_mode: str) -> str:
    profile = str(value or "").strip().lower()
    if profile in {"publication", "focused", "exploratory"}:
        return profile
    if analysis_mode == "publication":
        return "publication"
    if analysis_mode == "focused":
        return "focused"
    return "exploratory"


def _resolve_score_profile(row: Dict[str, Any]) -> Dict[str, Any]:
    analysis_mode = _normalize_analysis_mode(row.get("analysis_mode"))
    validation_profile = _normalize_validation_profile(
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


def _score_latency(elapsed_ms: Any) -> float:
    elapsed = _safe_float(elapsed_ms)
    if not isinstance(elapsed, float) or elapsed < 0:
        return 0.5
    return _clamp01(1.0 / (1.0 + elapsed / 2000.0), fallback=0.5)


def _score_token_efficiency(token_total: Any) -> float:
    token_value = _safe_float(token_total)
    if not isinstance(token_value, float) or token_value < 0:
        return 0.5
    return _clamp01(1.0 / (1.0 + token_value / 6000.0), fallback=0.5)


def _score_step_coverage(step_count: Any, expected_step_count: Any = None) -> float:
    steps = _safe_float(step_count)
    expected_raw = _safe_float(expected_step_count)
    expected = expected_raw if isinstance(expected_raw, float) and expected_raw > 0 else 12.0
    if not isinstance(steps, float) or steps < 0:
        return 0.5
    return _clamp01(steps / expected, fallback=0.5)


def _score_retry_efficiency(attempt_count: Any) -> float:
    attempts = _safe_float(attempt_count)
    if not isinstance(attempts, float) or attempts < 1:
        return 1.0
    return _clamp01(1.0 / (1.0 + max(0.0, attempts - 1.0)), fallback=1.0)


def _auto_score_variant(row: Dict[str, Any]) -> float:
    profile = _resolve_score_profile(row)
    weights = profile.get("weights") if isinstance(profile.get("weights"), dict) else {}
    penalties = profile.get("penalties") if isinstance(profile.get("penalties"), dict) else {}

    benchmark = _safe_float(row.get("benchmark_score"))
    quality = _safe_float(row.get("quality_score"))
    quality_norm = _clamp01((quality or 0.0) / 100.0, fallback=0.0)
    if isinstance(benchmark, float):
        benchmark_norm = _clamp01(benchmark, fallback=quality_norm)
        quality_norm = _clamp01((benchmark_norm * 0.75) + (quality_norm * 0.25), fallback=benchmark_norm)

    latency = _score_latency(row.get("elapsed_ms"))
    token_efficiency = _score_token_efficiency(row.get("token_total"))
    step_coverage = _score_step_coverage(
        row.get("step_count"),
        expected_step_count=row.get("expected_step_count"),
    )
    retry_efficiency = _score_retry_efficiency(row.get("attempt_count"))
    fallback_used = bool(row.get("fallback_used"))

    fallback_reliability_factor = _clamp01(
        penalties.get("fallback_reliability_factor"),
        fallback=0.90,
    )
    reliability = _clamp01(
        (fallback_reliability_factor if fallback_used else 1.0) * 0.7 + retry_efficiency * 0.3,
        fallback=0.0,
    )

    attempt_count = _safe_int(row.get("attempt_count"))
    attempts = int(attempt_count) if isinstance(attempt_count, int) else 1
    fallback_penalty = float(max(0.0, penalties.get("fallback") or 0.0)) if fallback_used else 0.0
    retry_penalty_per_attempt = float(max(0.0, penalties.get("retry_per_attempt") or 0.0))
    retry_penalty = min(0.12, max(0.0, float(attempts - 1) * retry_penalty_per_attempt))

    score = (
        quality_norm * float(weights.get("quality") or 0.76)
        + latency * float(weights.get("latency") or 0.14)
        + token_efficiency * float(weights.get("token") or 0.07)
        + step_coverage * float(weights.get("step") or 0.02)
        + reliability * float(weights.get("reliability") or 0.01)
        - fallback_penalty
        - retry_penalty
    )
    return float(round(score, 6))


def _mean(values: Iterable[float]) -> Optional[float]:
    arr = [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]
    if not arr:
        return None
    return float(sum(arr) / len(arr))


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def collect_llm_benchmark_artifacts(workspace_dir: Path | str) -> List[Dict[str, Any]]:
    root = Path(workspace_dir).expanduser().resolve()
    datasets_root = root / "datasets"
    if not datasets_root.exists():
        return []

    artifacts: List[Dict[str, Any]] = []
    for dataset_dir in sorted(datasets_root.iterdir()):
        if not dataset_dir.is_dir():
            continue
        analysis_dir = dataset_dir / "analysis"
        if not analysis_dir.exists():
            continue
        for run_dir in sorted(analysis_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            bench_path = run_dir / "artifacts" / "llm_benchmark.json"
            if not bench_path.exists():
                continue
            payload = _load_json(bench_path)
            if not isinstance(payload, dict):
                continue
            variants = payload.get("variants")
            if not isinstance(variants, list) or not variants:
                continue
            artifacts.append(
                {
                    "dataset_id": dataset_dir.name,
                    "run_id": run_dir.name,
                    "artifact_path": str(bench_path),
                    "payload": payload,
                }
            )
    return artifacts


def _normalize_variant(
    raw: Dict[str, Any],
    *,
    analysis_mode: str,
    validation_profile: str,
    expected_step_count: Optional[int],
    recommended_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    variant_id = str(raw.get("id") or "").strip()
    if not variant_id:
        return None

    row_mode = _normalize_analysis_mode(raw.get("analysis_mode") or analysis_mode)
    row_profile = _normalize_validation_profile(
        raw.get("validation_profile"),
        analysis_mode=row_mode,
    )
    row_expected_steps = _safe_int(raw.get("expected_step_count"))
    if not isinstance(row_expected_steps, int):
        row_expected_steps = expected_step_count
    if isinstance(row_expected_steps, int):
        row_expected_steps = max(1, int(row_expected_steps))

    status = str(raw.get("status") or "unknown").strip().lower()
    row = {
        "id": variant_id,
        "label": str(raw.get("label") or variant_id).strip(),
        "status": status or "unknown",
        "recommended": bool(variant_id == str(recommended_id or "").strip()),
        "analysis_mode": row_mode,
        "validation_profile": row_profile,
        "expected_step_count": row_expected_steps,
        "quality_score": _safe_float(raw.get("quality_score")),
        "benchmark_score": _safe_float(raw.get("benchmark_score")),
        "elapsed_ms": _safe_int(raw.get("elapsed_ms")),
        "token_total": _safe_int(raw.get("token_total")),
        "step_count": _safe_int(raw.get("step_count")),
        "attempt_count": max(1, int(_safe_int(raw.get("attempt_count")) or 1)),
        "fallback_used": bool(raw.get("fallback_used")),
        "model_used": str(raw.get("model_used") or "").strip() or None,
        "planner_model": str(raw.get("planner_model") or "").strip() or None,
    }
    row["auto_score"] = _auto_score_variant(row)
    return row


def build_router_benchmark_report(artifacts: List[Dict[str, Any]], *, workspace_dir: Path | str) -> Dict[str, Any]:
    runs: List[Dict[str, Any]] = []
    variant_rows: List[Dict[str, Any]] = []
    recommended_by_profile: Dict[str, List[str]] = {"publication": [], "focused": [], "exploratory": []}

    for item in artifacts:
        payload = item.get("payload") if isinstance(item, dict) else None
        if not isinstance(payload, dict):
            continue
        context_raw = payload.get("benchmark_context") if isinstance(payload.get("benchmark_context"), dict) else {}
        analysis_mode = _normalize_analysis_mode(
            context_raw.get("analysis_mode")
            or payload.get("analysis_mode")
            or payload.get("mode")
        )
        validation_profile = _normalize_validation_profile(
            context_raw.get("validation_profile")
            or payload.get("validation_profile"),
            analysis_mode=analysis_mode,
        )
        expected_step_count = _safe_int(
            context_raw.get("expected_step_count")
            if "expected_step_count" in context_raw
            else payload.get("expected_step_count")
        )
        if isinstance(expected_step_count, int):
            expected_step_count = max(1, int(expected_step_count))

        recommended_id_raw = str(payload.get("recommended_id") or "").strip() or None
        variants_raw = payload.get("variants")
        if not isinstance(variants_raw, list) or not variants_raw:
            continue

        rows: List[Dict[str, Any]] = []
        for variant in variants_raw:
            if not isinstance(variant, dict):
                continue
            row = _normalize_variant(
                variant,
                analysis_mode=analysis_mode,
                validation_profile=validation_profile,
                expected_step_count=expected_step_count,
                recommended_id=recommended_id_raw,
            )
            if isinstance(row, dict):
                rows.append(row)
                variant_rows.append(row)

        if not rows:
            continue

        recommended_id = recommended_id_raw
        if not recommended_id or recommended_id not in {r.get("id") for r in rows}:
            candidates = [r for r in rows if str(r.get("status")) == "ok"]
            if not candidates:
                candidates = rows
            candidates = sorted(
                candidates,
                key=lambda row: (
                    float(row.get("auto_score") or -1.0),
                    float(row.get("quality_score") or -1.0),
                    -int(row.get("elapsed_ms") or 10**9),
                ),
                reverse=True,
            )
            recommended_id = str(candidates[0].get("id")) if candidates else None

        if recommended_id:
            recommended_by_profile.setdefault(validation_profile, []).append(str(recommended_id))

        runs.append(
            {
                "dataset_id": str(item.get("dataset_id") or ""),
                "run_id": str(item.get("run_id") or ""),
                "artifact_path": str(item.get("artifact_path") or ""),
                "validation_profile": validation_profile,
                "analysis_mode": analysis_mode,
                "expected_step_count": expected_step_count,
                "recommended_id": recommended_id,
                "variant_count": len(rows),
            }
        )

    variant_agg: Dict[str, Dict[str, Any]] = {}
    for row in variant_rows:
        variant_id = str(row.get("id"))
        bucket = variant_agg.setdefault(
            variant_id,
            {
                "id": variant_id,
                "label": str(row.get("label") or variant_id),
                "runs": 0,
                "ok_runs": 0,
                "recommended_count": 0,
                "fallback_count": 0,
                "profiles": set(),
                "analysis_modes": set(),
                "quality_scores": [],
                "auto_scores": [],
                "elapsed_ms": [],
                "token_total": [],
                "attempt_count": [],
            },
        )
        bucket["runs"] += 1
        if str(row.get("status")) == "ok":
            bucket["ok_runs"] += 1
        if bool(row.get("recommended")):
            bucket["recommended_count"] += 1
        if bool(row.get("fallback_used")):
            bucket["fallback_count"] += 1
        bucket["profiles"].add(str(row.get("validation_profile") or "exploratory"))
        bucket["analysis_modes"].add(str(row.get("analysis_mode") or "exploratory"))
        if isinstance(row.get("quality_score"), (int, float)):
            bucket["quality_scores"].append(float(row["quality_score"]))
        if isinstance(row.get("auto_score"), (int, float)):
            bucket["auto_scores"].append(float(row["auto_score"]))
        if isinstance(row.get("elapsed_ms"), int):
            bucket["elapsed_ms"].append(int(row["elapsed_ms"]))
        if isinstance(row.get("token_total"), int):
            bucket["token_total"].append(int(row["token_total"]))
        if isinstance(row.get("attempt_count"), int):
            bucket["attempt_count"].append(int(row["attempt_count"]))

    variant_summary: List[Dict[str, Any]] = []
    runs_total = len(runs)
    for bucket in variant_agg.values():
        rows_count = int(bucket.get("runs") or 0)
        ok_rows = int(bucket.get("ok_runs") or 0)
        rec_count = int(bucket.get("recommended_count") or 0)
        fallback_count = int(bucket.get("fallback_count") or 0)
        variant_summary.append(
            {
                "id": str(bucket.get("id") or ""),
                "label": str(bucket.get("label") or ""),
                "runs": rows_count,
                "ok_runs": ok_rows,
                "success_rate": round(ok_rows / rows_count, 4) if rows_count > 0 else 0.0,
                "recommended_count": rec_count,
                "recommendation_share": round(rec_count / runs_total, 4) if runs_total > 0 else 0.0,
                "fallback_rate": round(fallback_count / rows_count, 4) if rows_count > 0 else 0.0,
                "mean_quality_score": _mean(bucket.get("quality_scores") or []),
                "mean_auto_score": _mean(bucket.get("auto_scores") or []),
                "mean_elapsed_ms": _mean(bucket.get("elapsed_ms") or []),
                "mean_token_total": _mean(bucket.get("token_total") or []),
                "mean_attempt_count": _mean(bucket.get("attempt_count") or []),
                "profiles": sorted([str(v) for v in (bucket.get("profiles") or set())]),
                "analysis_modes": sorted([str(v) for v in (bucket.get("analysis_modes") or set())]),
            }
        )

    variant_summary = sorted(
        variant_summary,
        key=lambda item: (
            float(item.get("recommendation_share") or 0.0),
            float(item.get("mean_auto_score") or -1.0),
            float(item.get("success_rate") or 0.0),
        ),
        reverse=True,
    )

    winners_by_profile: Dict[str, Dict[str, Any]] = {}
    for profile in ["publication", "focused", "exploratory"]:
        votes = recommended_by_profile.get(profile) or []
        total = len(votes)
        counts: Dict[str, int] = {}
        for variant_id in votes:
            counts[variant_id] = int(counts.get(variant_id, 0) + 1)
        if total > 0 and counts:
            top_variant, top_count = sorted(
                counts.items(),
                key=lambda item: (int(item[1]), str(item[0])),
                reverse=True,
            )[0]
            winners_by_profile[profile] = {
                "variant_id": str(top_variant),
                "count": int(top_count),
                "share": round(float(top_count) / float(total), 4),
                "total_runs": int(total),
            }
        else:
            winners_by_profile[profile] = {
                "variant_id": None,
                "count": 0,
                "share": 0.0,
                "total_runs": 0,
            }

    status_counts: Dict[str, int] = {}
    for row in variant_rows:
        status = str(row.get("status") or "unknown").strip().lower() or "unknown"
        status_counts[status] = int(status_counts.get(status, 0) + 1)

    summary = {
        "runs_total": len(runs),
        "variants_total": len(variant_rows),
        "distinct_variants": len(variant_summary),
        "status_counts": status_counts,
        "profiles": {
            profile: int(len(recommended_by_profile.get(profile) or []))
            for profile in ["publication", "focused", "exploratory"]
        },
        "unique_recommended_variants": int(
            len(
                {
                    item.get("recommended_id")
                    for item in runs
                    if isinstance(item, dict) and isinstance(item.get("recommended_id"), str)
                }
            )
        ),
    }

    return {
        "schema": "clinimetria.model_router_benchmark_report",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "workspace_dir": str(Path(workspace_dir).expanduser().resolve()),
        "summary": summary,
        "winners_by_profile": winners_by_profile,
        "variants": variant_summary,
        "runs": runs,
    }


def evaluate_benchmark_coverage(report: Dict[str, Any], *, min_runs: int = 0) -> Dict[str, Any]:
    threshold = max(0, int(min_runs))
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    runs_total_raw = _safe_int(summary.get("runs_total"))
    runs_total = int(runs_total_raw) if isinstance(runs_total_raw, int) else 0
    meets_threshold = runs_total >= threshold
    deficit = max(0, threshold - runs_total)
    return {
        "runs_total": runs_total,
        "min_runs": threshold,
        "meets_threshold": bool(meets_threshold),
        "deficit": deficit,
    }


def build_router_benchmark_markdown(
    report: Dict[str, Any],
    *,
    min_runs: int = 0,
    top_n: int = 10,
) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    winners = report.get("winners_by_profile") if isinstance(report.get("winners_by_profile"), dict) else {}
    variants = report.get("variants") if isinstance(report.get("variants"), list) else []
    coverage = evaluate_benchmark_coverage(report, min_runs=min_runs)

    lines: List[str] = []
    lines.append("# Model Router Benchmark Report")
    lines.append("")
    lines.append(f"- Generated at: `{report.get('generated_at') or '-'}`")
    lines.append(f"- Workspace: `{report.get('workspace_dir') or '-'}`")
    lines.append(f"- Runs total: `{summary.get('runs_total', 0)}`")
    lines.append(f"- Variants total: `{summary.get('variants_total', 0)}`")
    lines.append(f"- Distinct variants: `{summary.get('distinct_variants', 0)}`")
    lines.append("")

    if int(coverage.get("min_runs") or 0) > 0:
        if bool(coverage.get("meets_threshold")):
            lines.append(
                f"Coverage gate: PASS (`runs_total={coverage.get('runs_total')}` >= `min_runs={coverage.get('min_runs')}`)."
            )
        else:
            lines.append(
                f"Coverage gate: WARN (`runs_total={coverage.get('runs_total')}` < `min_runs={coverage.get('min_runs')}`, "
                f"deficit={coverage.get('deficit')})."
            )
        lines.append("")

    lines.append("## Winners by profile")
    lines.append("")
    lines.append("| Profile | Winner | Share | N |")
    lines.append("|---|---|---:|---:|")
    for profile in ("publication", "focused", "exploratory"):
        item = winners.get(profile) if isinstance(winners.get(profile), dict) else {}
        share = _safe_float(item.get("share"))
        share_pct = f"{(share * 100.0):.1f}%" if isinstance(share, float) else "-"
        lines.append(
            f"| {profile} | {item.get('variant_id') or '-'} | {share_pct} | {int(item.get('total_runs') or 0)} |"
        )
    lines.append("")

    lines.append("## Top variants")
    lines.append("")
    lines.append("| Variant | Recommendation share | Success rate | Mean auto score | Fallback rate | Runs |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for item in variants[: max(1, int(top_n))]:
        if not isinstance(item, dict):
            continue
        rec_share = _safe_float(item.get("recommendation_share"))
        success_rate = _safe_float(item.get("success_rate"))
        auto_score = _safe_float(item.get("mean_auto_score"))
        fallback_rate = _safe_float(item.get("fallback_rate"))
        lines.append(
            "| {variant} | {rec_share} | {success_rate} | {auto_score} | {fallback_rate} | {runs} |".format(
                variant=str(item.get("id") or "-"),
                rec_share=(f"{rec_share * 100.0:.1f}%" if isinstance(rec_share, float) else "-"),
                success_rate=(f"{success_rate * 100.0:.1f}%" if isinstance(success_rate, float) else "-"),
                auto_score=(f"{auto_score:.3f}" if isinstance(auto_score, float) else "-"),
                fallback_rate=(f"{fallback_rate * 100.0:.1f}%" if isinstance(fallback_rate, float) else "-"),
                runs=int(item.get("runs") or 0),
            )
        )
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
