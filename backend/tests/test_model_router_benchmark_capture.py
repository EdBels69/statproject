import json
import os
import subprocess
import sys
from pathlib import Path


def test_benchmark_capture_cli_allows_empty_workspace(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "backend" / "scripts" / "run_model_router_benchmark_capture.py"

    workspace_dir = tmp_path / "workspace"
    snapshot_json = tmp_path / "release" / "model_router_benchmark_report.json"
    snapshot_md = tmp_path / "release" / "model_router_benchmark_report.md"
    capture_json = tmp_path / "release" / "model_router_benchmark_capture_last.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--workspace-dir",
            str(workspace_dir),
            "--allow-empty",
            "--snapshot-output",
            str(snapshot_json),
            "--snapshot-markdown",
            str(snapshot_md),
            "--capture-output",
            str(capture_json),
            "--min-runs",
            "3",
            "--pretty",
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert snapshot_json.exists()
    assert snapshot_md.exists()
    assert capture_json.exists()

    report = json.loads(snapshot_json.read_text(encoding="utf-8"))
    summary = report.get("summary") if isinstance(report, dict) else {}
    assert isinstance(summary, dict)
    assert int(summary.get("runs_total") or 0) == 0

    capture = json.loads(capture_json.read_text(encoding="utf-8"))
    assert capture.get("status") == "skipped"
    assert capture.get("skip_reason") == "no_dataset_candidates"
    snapshot = capture.get("snapshot") if isinstance(capture.get("snapshot"), dict) else {}
    coverage = snapshot.get("coverage_gate") if isinstance(snapshot.get("coverage_gate"), dict) else {}
    assert bool(coverage.get("meets_threshold")) is False
    assert int(coverage.get("deficit") or 0) == 3
