#!/usr/bin/env python3
"""
Aggregate model-router benchmark quality from run artifacts.

Scans: workspace/datasets/*/analysis/*/artifacts/llm_benchmark.json
Outputs a consolidated report with winners per profile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.model_router_benchmark import (
    collect_llm_benchmark_artifacts,
    build_router_benchmark_report,
    build_router_benchmark_markdown,
    evaluate_benchmark_coverage,
)


def _default_output_path() -> Path:
    return PROJECT_ROOT / "release" / "model_router_benchmark_report.json"


def _default_markdown_output_path() -> Path:
    return PROJECT_ROOT / "release" / "model_router_benchmark_report.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model-router benchmark report from run artifacts.")
    parser.add_argument(
        "--workspace-dir",
        type=Path,
        default=PROJECT_ROOT / "workspace",
        help="Workspace directory containing datasets/*/analysis/*/artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_default_output_path(),
        help="Output JSON path.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=_default_markdown_output_path(),
        help="Output Markdown summary path.",
    )
    parser.add_argument(
        "--min-runs",
        type=int,
        default=0,
        help="Minimum number of benchmark runs required for coverage gate.",
    )
    parser.add_argument(
        "--strict-min-runs",
        action="store_true",
        help="Exit with non-zero code when runs_total < min_runs.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print report summary to stdout.",
    )
    args = parser.parse_args()

    workspace_dir = args.workspace_dir if args.workspace_dir.is_absolute() else (PROJECT_ROOT / args.workspace_dir)
    output_path = args.output if args.output.is_absolute() else (PROJECT_ROOT / args.output)
    markdown_path = args.markdown_out if args.markdown_out.is_absolute() else (PROJECT_ROOT / args.markdown_out)
    min_runs = max(0, int(args.min_runs or 0))

    artifacts = collect_llm_benchmark_artifacts(workspace_dir)
    report = build_router_benchmark_report(artifacts, workspace_dir=workspace_dir)
    markdown = build_router_benchmark_markdown(report, min_runs=min_runs)
    coverage = evaluate_benchmark_coverage(report, min_runs=min_runs)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(markdown, encoding="utf-8")

    if args.pretty:
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        winners = report.get("winners_by_profile") if isinstance(report.get("winners_by_profile"), dict) else {}
        print(f"Saved: {output_path}")
        print(f"Saved: {markdown_path}")
        print(f"runs_total={summary.get('runs_total', 0)} variants_total={summary.get('variants_total', 0)}")
        print(
            f"coverage_gate={'PASS' if coverage.get('meets_threshold') else 'WARN'} "
            f"(runs_total={coverage.get('runs_total')} min_runs={coverage.get('min_runs')})"
        )
        for profile in ("publication", "focused", "exploratory"):
            item = winners.get(profile) if isinstance(winners.get(profile), dict) else {}
            print(
                f"{profile}: winner={item.get('variant_id') or '-'} "
                f"share={item.get('share', 0)} n={item.get('total_runs', 0)}"
            )

    if args.strict_min_runs and not bool(coverage.get("meets_threshold")):
        deficit = int(coverage.get("deficit") or 0)
        raise SystemExit(
            f"Coverage gate failed: runs_total={coverage.get('runs_total')} "
            f"< min_runs={coverage.get('min_runs')} (deficit={deficit})."
        )


if __name__ == "__main__":
    main()
