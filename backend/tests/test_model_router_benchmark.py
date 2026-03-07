import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.model_router_benchmark import (
    collect_llm_benchmark_artifacts,
    build_router_benchmark_report,
    evaluate_benchmark_coverage,
    build_router_benchmark_markdown,
)


def _write_benchmark(
    workspace_dir: Path,
    *,
    dataset_id: str,
    run_id: str,
    payload: dict,
) -> None:
    path = workspace_dir / "datasets" / dataset_id / "analysis" / run_id / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    (path / "llm_benchmark.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_collect_and_aggregate_router_benchmark_from_workspace(tmp_path: Path):
    workspace_dir = tmp_path / "workspace"

    _write_benchmark(
        workspace_dir,
        dataset_id="ds_a",
        run_id="run_1",
        payload={
            "schema": "clinimetria.llm_benchmark",
            "benchmark_context": {
                "analysis_mode": "exploratory",
                "validation_profile": "exploratory",
                "expected_step_count": 9,
            },
            "recommended_id": "minimax_single",
            "variants": [
                {
                    "id": "minimax_single",
                    "label": "MiniMax",
                    "status": "ok",
                    "quality_score": 92,
                    "elapsed_ms": 910,
                    "token_total": 4300,
                    "step_count": 9,
                    "attempt_count": 2,
                    "fallback_used": True,
                },
                {
                    "id": "gemini_single",
                    "label": "Gemini",
                    "status": "ok",
                    "quality_score": 87,
                    "elapsed_ms": 1200,
                    "token_total": 4800,
                    "step_count": 9,
                    "attempt_count": 1,
                    "fallback_used": False,
                },
            ],
        },
    )
    _write_benchmark(
        workspace_dir,
        dataset_id="ds_b",
        run_id="run_2",
        payload={
            "schema": "clinimetria.llm_benchmark",
            "benchmark_context": {
                "analysis_mode": "publication",
                "validation_profile": "publication",
                "expected_step_count": 12,
            },
            "recommended_id": "gemini_single",
            "variants": [
                {
                    "id": "minimax_single",
                    "label": "MiniMax",
                    "status": "ok",
                    "quality_score": 91,
                    "elapsed_ms": 950,
                    "token_total": 4300,
                    "step_count": 11,
                    "attempt_count": 3,
                    "fallback_used": True,
                },
                {
                    "id": "gemini_single",
                    "label": "Gemini",
                    "status": "ok",
                    "quality_score": 89,
                    "elapsed_ms": 1250,
                    "token_total": 4900,
                    "step_count": 11,
                    "attempt_count": 1,
                    "fallback_used": False,
                },
            ],
        },
    )
    _write_benchmark(
        workspace_dir,
        dataset_id="ds_c",
        run_id="run_3",
        payload={
            "schema": "clinimetria.llm_benchmark",
            "benchmark_context": {
                "analysis_mode": "publication",
                "validation_profile": "publication",
                "expected_step_count": 13,
            },
            "recommended_id": "gemini_single",
            "variants": [
                {
                    "id": "qwen_single",
                    "label": "Qwen",
                    "status": "error",
                },
                {
                    "id": "gemini_single",
                    "label": "Gemini",
                    "status": "ok",
                    "quality_score": 90,
                    "elapsed_ms": 1190,
                    "token_total": 4700,
                    "step_count": 12,
                    "attempt_count": 1,
                    "fallback_used": False,
                },
            ],
        },
    )

    artifacts = collect_llm_benchmark_artifacts(workspace_dir)
    assert len(artifacts) == 3

    report = build_router_benchmark_report(artifacts, workspace_dir=workspace_dir)
    assert report.get("schema") == "clinimetria.model_router_benchmark_report"

    summary = report.get("summary")
    assert isinstance(summary, dict)
    assert int(summary.get("runs_total") or 0) == 3
    assert int(summary.get("variants_total") or 0) == 6

    winners = report.get("winners_by_profile")
    assert isinstance(winners, dict)
    assert winners.get("publication", {}).get("variant_id") == "gemini_single"
    assert winners.get("publication", {}).get("total_runs") == 2
    assert winners.get("exploratory", {}).get("variant_id") == "minimax_single"
    assert winners.get("exploratory", {}).get("total_runs") == 1

    variants = report.get("variants")
    assert isinstance(variants, list) and variants
    by_id = {str(item.get("id")): item for item in variants if isinstance(item, dict)}
    assert "gemini_single" in by_id
    assert "minimax_single" in by_id

    gemini = by_id["gemini_single"]
    minimax = by_id["minimax_single"]
    assert int(gemini.get("recommended_count") or 0) == 2
    assert int(minimax.get("recommended_count") or 0) == 1
    assert float(minimax.get("fallback_rate") or 0.0) > float(gemini.get("fallback_rate") or 0.0)


def test_router_benchmark_markdown_and_coverage_gate(tmp_path: Path):
    workspace_dir = tmp_path / "workspace"
    _write_benchmark(
        workspace_dir,
        dataset_id="ds_one",
        run_id="run_1",
        payload={
            "schema": "clinimetria.llm_benchmark",
            "benchmark_context": {
                "analysis_mode": "focused",
                "validation_profile": "focused",
                "expected_step_count": 8,
            },
            "recommended_id": "gemini_single",
            "variants": [
                {
                    "id": "gemini_single",
                    "label": "Gemini",
                    "status": "ok",
                    "quality_score": 88,
                    "elapsed_ms": 1100,
                    "token_total": 4500,
                    "step_count": 8,
                    "attempt_count": 1,
                    "fallback_used": False,
                }
            ],
        },
    )

    artifacts = collect_llm_benchmark_artifacts(workspace_dir)
    report = build_router_benchmark_report(artifacts, workspace_dir=workspace_dir)

    gate_warn = evaluate_benchmark_coverage(report, min_runs=3)
    assert gate_warn.get("meets_threshold") is False
    assert int(gate_warn.get("deficit") or 0) == 2

    gate_pass = evaluate_benchmark_coverage(report, min_runs=1)
    assert gate_pass.get("meets_threshold") is True
    assert int(gate_pass.get("deficit") or 0) == 0

    markdown = build_router_benchmark_markdown(report, min_runs=3, top_n=5)
    assert "Model Router Benchmark Report" in markdown
    assert "Coverage gate: WARN" in markdown
    assert "| focused | gemini_single" in markdown
    assert "| gemini_single |" in markdown


def test_benchmark_cli_generates_json_and_markdown(tmp_path: Path):
    workspace_dir = tmp_path / "workspace"
    _write_benchmark(
        workspace_dir,
        dataset_id="ds_cli",
        run_id="run_1",
        payload={
            "schema": "clinimetria.llm_benchmark",
            "benchmark_context": {
                "analysis_mode": "exploratory",
                "validation_profile": "exploratory",
                "expected_step_count": 7,
            },
            "recommended_id": "qwen_single",
            "variants": [
                {
                    "id": "qwen_single",
                    "label": "Qwen",
                    "status": "ok",
                    "quality_score": 86,
                    "elapsed_ms": 980,
                    "token_total": 4100,
                    "step_count": 7,
                    "attempt_count": 1,
                    "fallback_used": False,
                }
            ],
        },
    )

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "benchmark_model_router.py"
    output_json = tmp_path / "release" / "model_router_benchmark_report.json"
    output_md = tmp_path / "release" / "model_router_benchmark_report.md"

    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--workspace-dir",
            str(workspace_dir),
            "--output",
            str(output_json),
            "--markdown-out",
            str(output_md),
            "--min-runs",
            "1",
            "--pretty",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert output_json.exists()
    assert output_md.exists()

    report = json.loads(output_json.read_text(encoding="utf-8"))
    assert report.get("schema") == "clinimetria.model_router_benchmark_report"
    assert int((report.get("summary") or {}).get("runs_total") or 0) == 1

    markdown = output_md.read_text(encoding="utf-8")
    assert "Model Router Benchmark Report" in markdown
    assert "Coverage gate: PASS" in markdown


def test_benchmark_cli_strict_min_runs_fails_when_insufficient(tmp_path: Path):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "benchmark_model_router.py"
    output_json = tmp_path / "release" / "model_router_benchmark_report.json"
    output_md = tmp_path / "release" / "model_router_benchmark_report.md"

    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--workspace-dir",
            str(workspace_dir),
            "--output",
            str(output_json),
            "--markdown-out",
            str(output_md),
            "--min-runs",
            "1",
            "--strict-min-runs",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    assert proc.returncode != 0
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert "Coverage gate failed" in combined
