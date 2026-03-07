#!/usr/bin/env python3
"""
Capture a real model-router benchmark run and persist llm_benchmark artifact.

Flow:
1. Run /api/v1/v2/analysis/plan across preset model variants.
2. Build normalized llm_benchmark payload (same server-side scoring logic).
3. Execute a short protocol and persist llm_benchmark.json in run artifacts.
4. Rebuild aggregate benchmark snapshot report (JSON + Markdown).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
DEFAULT_WORKSPACE_DIR = PROJECT_ROOT / "workspace"
DEFAULT_SNAPSHOT_JSON = PROJECT_ROOT / "release" / "model_router_benchmark_report.json"
DEFAULT_SNAPSHOT_MD = PROJECT_ROOT / "release" / "model_router_benchmark_report.md"
DEFAULT_CAPTURE_JSON = PROJECT_ROOT / "release" / "model_router_benchmark_capture_last.json"

# Settings loader in app.core.config reads .env from current cwd on import.
os.chdir(str(BACKEND_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.model_router_benchmark import (
    build_router_benchmark_markdown,
    build_router_benchmark_report,
    collect_llm_benchmark_artifacts,
    evaluate_benchmark_coverage,
)


MODEL_BENCHMARK_VARIANTS: List[Dict[str, Any]] = [
    {
        "id": "gemini_single",
        "label": "Gemini Flash 2.5 (single)",
        "models": {
            "planner": "google/gemini-2.5-flash",
            "quality": "google/gemini-2.5-flash",
            "interpret": "google/gemini-2.5-flash",
            "report": "google/gemini-2.5-flash",
            "codegen": "google/gemini-2.5-flash",
        },
    },
    {
        "id": "minimax_single",
        "label": "MiniMax M2.5 (single)",
        "models": {
            "planner": "minimax/minimax-m2.5",
            "quality": "minimax/minimax-m2.5",
            "interpret": "minimax/minimax-m2.5",
            "report": "minimax/minimax-m2.5",
            "codegen": "minimax/minimax-m2.5",
        },
    },
    {
        "id": "glm5_single",
        "label": "GLM-5 (single)",
        "models": {
            "planner": "z-ai/glm-5",
            "quality": "z-ai/glm-5",
            "interpret": "z-ai/glm-5",
            "report": "z-ai/glm-5",
            "codegen": "z-ai/glm-5",
        },
    },
    {
        "id": "qwen_single",
        "label": "Qwen 3.5 397B-A17B (single)",
        "models": {
            "planner": "qwen/qwen3.5-397b-a17b",
            "quality": "qwen/qwen3.5-397b-a17b",
            "interpret": "qwen/qwen3.5-397b-a17b",
            "report": "qwen/qwen3.5-397b-a17b",
            "codegen": "qwen/qwen3.5-397b-a17b",
        },
    },
    {
        "id": "routerai_combo",
        "label": "Combo: M2.5 + GLM-5 + Qwen 3.5",
        "models": {
            "planner": "minimax/minimax-m2.5",
            "quality": "z-ai/glm-5",
            "interpret": "qwen/qwen3.5-397b-a17b",
            "report": "qwen/qwen3.5-397b-a17b",
            "codegen": "deepseek/deepseek-chat-v3-0324:floor",
        },
    },
]


@dataclass
class DatasetCandidate:
    dataset_id: str
    mtime: float


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def _dataset_candidates(workspace_dir: Path) -> List[DatasetCandidate]:
    datasets_root = workspace_dir / "datasets"
    if not datasets_root.exists():
        return []

    out: List[DatasetCandidate] = []
    for ds_dir in datasets_root.iterdir():
        if not ds_dir.is_dir():
            continue
        processed = ds_dir / "processed"
        if not processed.exists():
            continue
        design_review = _load_json(processed / "design_review.json")
        if not isinstance(design_review, dict) or bool(design_review.get("confirmed")) is not True:
            continue
        has_parquet = any(p.suffix.lower() == ".parquet" for p in processed.glob("*.parquet"))
        if not has_parquet:
            continue
        out.append(DatasetCandidate(dataset_id=ds_dir.name, mtime=ds_dir.stat().st_mtime))

    out.sort(key=lambda item: item.mtime, reverse=True)
    return out


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
        return float(value)
    except Exception:
        return None


def _token_total_from_usage(usage: Any) -> Optional[int]:
    if not isinstance(usage, dict):
        return None
    planner = usage.get("planner") if isinstance(usage.get("planner"), dict) else {}
    planner_tokens = _safe_int(planner.get("total_tokens"))
    if isinstance(planner_tokens, int) and planner_tokens >= 0:
        return planner_tokens

    total = 0
    found = False
    for item in usage.values():
        if not isinstance(item, dict):
            continue
        tokens = _safe_int(item.get("total_tokens"))
        if isinstance(tokens, int) and tokens >= 0:
            total += tokens
            found = True
    return total if found else None


def _normalize_profile(value: str, *, analysis_mode: str) -> str:
    profile = str(value or "").strip().lower()
    if profile in {"publication", "focused", "exploratory"}:
        return profile
    if analysis_mode == "publication":
        return "publication"
    if analysis_mode == "focused":
        return "focused"
    return "exploratory"


def _build_test_client():
    from fastapi.testclient import TestClient  # local import to avoid unnecessary import cost in skip paths
    from app.main import app

    return TestClient(app)


def _normalize_llm_benchmark_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    import app.api.v2 as v2_api

    normalized = v2_api._normalize_llm_benchmark_payload(payload)
    return normalized if isinstance(normalized, dict) else None


def _build_snapshot(workspace_dir: Path, *, min_runs: int) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
    artifacts = collect_llm_benchmark_artifacts(workspace_dir)
    report = build_router_benchmark_report(artifacts, workspace_dir=workspace_dir)
    markdown = build_router_benchmark_markdown(report, min_runs=max(0, int(min_runs)))
    coverage = evaluate_benchmark_coverage(report, min_runs=max(0, int(min_runs)))
    return report, markdown, coverage


def _plan_variant(
    client: Any,
    *,
    dataset_id: str,
    text: str,
    analysis_mode: str,
    validation_profile: str,
    variant: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    variant_id = str(variant.get("id") or "").strip()
    variant_label = str(variant.get("label") or variant_id).strip()
    variant_models = variant.get("models") if isinstance(variant.get("models"), dict) else {}

    started = time.perf_counter()
    protocol_out: List[Dict[str, Any]] = []
    try:
        payload = {
            "dataset_id": dataset_id,
            "text": text,
            "protocol": [],
            "preferences": {
                "analysis_mode": analysis_mode,
                "validation_profile": validation_profile,
                "design_confirmed": True,
                "use_critic": False,
                "use_knowledge_base": False,
                "return_usage": True,
                "llm_models": variant_models,
            },
        }
        response = client.post("/api/v1/v2/analysis/plan", json=payload)
        elapsed_ms = max(0, int(round((time.perf_counter() - started) * 1000)))

        if response.status_code != 200:
            return (
                {
                    "id": variant_id,
                    "label": variant_label,
                    "status": "error",
                    "elapsed_ms": elapsed_ms,
                    "quality_score": None,
                    "step_count": 0,
                    "token_total": None,
                    "attempt_count": None,
                    "fallback_used": False,
                    "planner_model": variant_models.get("planner"),
                    "model_used": None,
                    "models": variant_models,
                    "analysis_mode": analysis_mode,
                    "validation_profile": validation_profile,
                    "error": f"HTTP {response.status_code}: {response.text[:220]}",
                },
                protocol_out,
            )

        plan_payload = response.json() if isinstance(response.json(), dict) else {}
        usage = plan_payload.get("usage") if isinstance(plan_payload.get("usage"), dict) else {}
        planner_usage = usage.get("planner") if isinstance(usage.get("planner"), dict) else {}
        quality = plan_payload.get("quality") if isinstance(plan_payload.get("quality"), dict) else {}

        protocol = plan_payload.get("protocol") if isinstance(plan_payload.get("protocol"), list) else []
        protocol_out = [step for step in protocol if isinstance(step, dict)]
        policy = plan_payload.get("validation_policy") if isinstance(plan_payload.get("validation_policy"), dict) else {}

        row = {
            "id": variant_id,
            "label": variant_label,
            "status": "ok",
            "elapsed_ms": elapsed_ms,
            "quality_score": _safe_float(quality.get("score")),
            "step_count": len(protocol_out),
            "token_total": _token_total_from_usage(usage),
            "attempt_count": _safe_int(planner_usage.get("attempt_count")) or 1,
            "fallback_used": bool(planner_usage.get("fallback_used")),
            "planner_model": variant_models.get("planner"),
            "model_used": str(planner_usage.get("model_used") or "").strip() or None,
            "models": variant_models,
            "analysis_mode": analysis_mode,
            "validation_profile": _normalize_profile(
                str(policy.get("profile") or validation_profile),
                analysis_mode=analysis_mode,
            ),
            "error": None,
        }
        return row, protocol_out
    except Exception as exc:  # pragma: no cover - external provider failures
        elapsed_ms = max(0, int(round((time.perf_counter() - started) * 1000)))
        return (
            {
                "id": variant_id,
                "label": variant_label,
                "status": "error",
                "elapsed_ms": elapsed_ms,
                "quality_score": None,
                "step_count": 0,
                "token_total": None,
                "attempt_count": None,
                "fallback_used": False,
                "planner_model": variant_models.get("planner"),
                "model_used": None,
                "models": variant_models,
                "analysis_mode": analysis_mode,
                "validation_profile": validation_profile,
                "error": str(exc),
            },
            protocol_out,
        )


def _execute_with_benchmark(
    client: Any,
    *,
    dataset_id: str,
    protocol_steps: List[Dict[str, Any]],
    llm_benchmark: Dict[str, Any],
    analysis_mode: str,
    max_protocol_steps: int,
) -> Dict[str, Any]:
    if not protocol_steps:
        raise RuntimeError("No protocol steps available for execute")

    steps = protocol_steps[: max(1, int(max_protocol_steps))]
    payload = {
        "dataset_id": dataset_id,
        "protocol": steps,
        "alpha": 0.05,
        "protocol_name": "model_router_benchmark_capture",
        "globals": {
            "analysis_mode": analysis_mode,
            "mode": analysis_mode,
            "design_confirmed": True,
            "llm_benchmark": llm_benchmark,
        },
    }
    response = client.post("/api/v1/v2/analysis/execute", json=payload)
    if response.status_code != 200:
        raise RuntimeError(f"execute failed: HTTP {response.status_code}: {response.text[:240]}")
    payload_out = response.json() if isinstance(response.json(), dict) else {}
    run_id = str(payload_out.get("run_id") or "").strip()
    if not run_id:
        raise RuntimeError("execute completed without run_id")
    return payload_out


def _artifact_path(workspace_dir: Path, dataset_id: str, run_id: str) -> Path:
    return workspace_dir / "datasets" / dataset_id / "analysis" / run_id / "artifacts" / "llm_benchmark.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture model-router benchmark from real planning runs")
    parser.add_argument("--workspace-dir", type=Path, default=DEFAULT_WORKSPACE_DIR)
    parser.add_argument("--dataset-id", type=str, default="")
    parser.add_argument(
        "--analysis-mode",
        type=str,
        default="focused",
        choices=["exploratory", "focused"],
        help="Execution mode for benchmark capture. Publication mode is intentionally excluded in this helper.",
    )
    parser.add_argument("--validation-profile", type=str, default="")
    parser.add_argument(
        "--text",
        type=str,
        default="Compare key outcomes between groups and build an execution-ready protocol.",
    )
    parser.add_argument("--max-protocol-steps", type=int, default=1)
    parser.add_argument("--skip-execute", action="store_true")
    parser.add_argument("--snapshot-output", type=Path, default=DEFAULT_SNAPSHOT_JSON)
    parser.add_argument("--snapshot-markdown", type=Path, default=DEFAULT_SNAPSHOT_MD)
    parser.add_argument("--capture-output", type=Path, default=DEFAULT_CAPTURE_JSON)
    parser.add_argument("--min-runs", type=int, default=0)
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Exit successfully and write skipped capture summary when no eligible dataset is found.",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    workspace_dir = args.workspace_dir if args.workspace_dir.is_absolute() else (PROJECT_ROOT / args.workspace_dir)
    workspace_dir = workspace_dir.expanduser().resolve()
    snapshot_output = args.snapshot_output if args.snapshot_output.is_absolute() else (PROJECT_ROOT / args.snapshot_output)
    snapshot_markdown = (
        args.snapshot_markdown if args.snapshot_markdown.is_absolute() else (PROJECT_ROOT / args.snapshot_markdown)
    )
    capture_output = args.capture_output if args.capture_output.is_absolute() else (PROJECT_ROOT / args.capture_output)

    def _write_outputs(report: Dict[str, Any], markdown: str, capture_summary: Dict[str, Any]) -> None:
        snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        snapshot_markdown.parent.mkdir(parents=True, exist_ok=True)
        capture_output.parent.mkdir(parents=True, exist_ok=True)
        snapshot_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        snapshot_markdown.write_text(markdown, encoding="utf-8")
        capture_output.write_text(json.dumps(capture_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    requested_dataset_id = str(args.dataset_id or "").strip()
    dataset_id: Optional[str] = None
    if requested_dataset_id:
        dataset_id = requested_dataset_id
    else:
        candidates = _dataset_candidates(workspace_dir)
        if not candidates:
            if not args.allow_empty:
                raise SystemExit(
                    "No dataset candidates with confirmed design_review and processed parquet were found. "
                    "Pass --dataset-id explicitly."
                )
            report, markdown, coverage = _build_snapshot(workspace_dir, min_runs=args.min_runs)
            capture_summary = {
                "schema": "clinimetria.model_router_benchmark_capture",
                "version": 1,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "status": "skipped",
                "skip_reason": "no_dataset_candidates",
                "dataset_id": None,
                "analysis_mode": args.analysis_mode,
                "validation_profile": _normalize_profile(
                    args.validation_profile,
                    analysis_mode=str(args.analysis_mode).strip().lower(),
                ),
                "skip_execute": bool(args.skip_execute),
                "run_id": None,
                "llm_benchmark_artifact": None,
                "recommended_id": None,
                "recommendation_source": None,
                "variants": [],
                "snapshot": {
                    "json": str(snapshot_output),
                    "markdown": str(snapshot_markdown),
                    "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {},
                    "coverage_gate": coverage,
                },
            }
            _write_outputs(report, markdown, capture_summary)
            if args.pretty:
                summary = capture_summary.get("snapshot", {}).get("summary", {})
                print("dataset_id=-")
                print("recommended_id=-")
                print("run_id=-")
                print(
                    "snapshot: runs_total={runs} variants_total={vars} coverage={coverage}".format(
                        runs=int(summary.get("runs_total") or 0),
                        vars=int(summary.get("variants_total") or 0),
                        coverage="PASS" if bool(coverage.get("meets_threshold")) else "WARN",
                    )
                )
                print("status=skipped skip_reason=no_dataset_candidates")
                print(f"capture_summary={capture_output}")
            return
        dataset_id = candidates[0].dataset_id

    validation_profile = _normalize_profile(
        args.validation_profile,
        analysis_mode=str(args.analysis_mode).strip().lower(),
    )

    client = _build_test_client()

    rows: List[Dict[str, Any]] = []
    selected_protocol: List[Dict[str, Any]] = []
    for variant in MODEL_BENCHMARK_VARIANTS:
        row, protocol = _plan_variant(
            client,
            dataset_id=dataset_id,
            text=args.text,
            analysis_mode=args.analysis_mode,
            validation_profile=validation_profile,
            variant=variant,
        )
        rows.append(row)
        if not selected_protocol and protocol:
            selected_protocol = protocol

        if args.pretty:
            print(
                f"{row.get('id')}: status={row.get('status')} quality={row.get('quality_score')} "
                f"steps={row.get('step_count')} elapsed_ms={row.get('elapsed_ms')} "
                f"model_used={row.get('model_used')} fallback={row.get('fallback_used')}"
            )

    ok_rows = [row for row in rows if str(row.get("status")) == "ok"]
    expected_step_count = 1
    if ok_rows:
        expected_step_count = max(
            1,
            int(round(sum(int(row.get("step_count") or 0) for row in ok_rows) / len(ok_rows))),
        )

    raw_benchmark_payload = {
        "schema": "clinimetria.llm_benchmark",
        "version": 1,
        "recorded_at": datetime.utcnow().isoformat() + "Z",
        "benchmark_context": {
            "analysis_mode": args.analysis_mode,
            "validation_profile": validation_profile,
            "expected_step_count": expected_step_count,
            "variant_count": len(rows),
        },
        "variants": rows,
    }

    normalized_benchmark = _normalize_llm_benchmark_payload(raw_benchmark_payload)
    if not isinstance(normalized_benchmark, dict):
        raise SystemExit("Failed to normalize llm_benchmark payload")

    run_id: Optional[str] = None
    llm_benchmark_artifact: Optional[Path] = None

    if not args.skip_execute:
        execute_payload = _execute_with_benchmark(
            client,
            dataset_id=str(dataset_id),
            protocol_steps=selected_protocol,
            llm_benchmark=normalized_benchmark,
            analysis_mode=args.analysis_mode,
            max_protocol_steps=max(1, int(args.max_protocol_steps)),
        )
        run_id = str(execute_payload.get("run_id") or "").strip() or None
        if not run_id:
            raise SystemExit("Execute completed without run_id")

        llm_benchmark_artifact = _artifact_path(workspace_dir, dataset_id, run_id)
        if not llm_benchmark_artifact.exists():
            raise SystemExit(f"Expected artifact was not created: {llm_benchmark_artifact}")

    report, markdown, coverage = _build_snapshot(workspace_dir, min_runs=args.min_runs)

    capture_summary = {
        "schema": "clinimetria.model_router_benchmark_capture",
        "version": 1,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "status": "completed",
        "skip_reason": None,
        "dataset_id": str(dataset_id),
        "analysis_mode": args.analysis_mode,
        "validation_profile": validation_profile,
        "skip_execute": bool(args.skip_execute),
        "run_id": run_id,
        "llm_benchmark_artifact": str(llm_benchmark_artifact) if isinstance(llm_benchmark_artifact, Path) else None,
        "recommended_id": normalized_benchmark.get("recommended_id"),
        "recommendation_source": normalized_benchmark.get("recommendation_source"),
        "variants": rows,
        "snapshot": {
            "json": str(snapshot_output),
            "markdown": str(snapshot_markdown),
            "summary": report.get("summary") if isinstance(report.get("summary"), dict) else {},
            "coverage_gate": coverage,
        },
    }
    _write_outputs(report, markdown, capture_summary)

    if args.pretty:
        summary = capture_summary.get("snapshot", {}).get("summary", {})
        print(f"dataset_id={dataset_id}")
        print(f"recommended_id={capture_summary.get('recommended_id')}")
        print(f"run_id={run_id or '-'}")
        print(
            "snapshot: runs_total={runs} variants_total={vars} coverage={coverage}".format(
                runs=int(summary.get("runs_total") or 0),
                vars=int(summary.get("variants_total") or 0),
                coverage="PASS" if bool(coverage.get("meets_threshold")) else "WARN",
            )
        )
        print(f"capture_summary={capture_output}")


if __name__ == "__main__":
    main()
