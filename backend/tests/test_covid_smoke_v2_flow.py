import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import json
from typing import Any, Dict, List, Optional, Tuple
import zipfile
from io import BytesIO
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app
from app.api.datasets import DATA_DIR
from app.core.config import settings


client = TestClient(app)


def _docx_text(payload: bytes) -> str:
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        xml = archive.read("word/document.xml")
    return xml.decode("utf-8", errors="ignore")


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _covid_file_path() -> str:
    return os.path.join(_repo_root(), "docs", "Общая таблица Ковид19.xlsx")


def _read_profile_columns(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    cols = profile.get("columns") if isinstance(profile, dict) else None
    if not isinstance(cols, list):
        return out

    for item in cols:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "type": str(item.get("type") or "").strip().lower(),
                "missing_count": item.get("missing_count"),
                "unique_count": item.get("unique_count"),
            }
        )
    return out


def _is_numeric_col(col: Dict[str, Any]) -> bool:
    ctype = str(col.get("type") or "").strip().lower()
    uniq = col.get("unique_count")
    if not isinstance(uniq, int) or uniq < 8:
        return False
    return (
        ctype == "numeric"
        or "float" in ctype
        or "int" in ctype
        or "double" in ctype
        or "number" in ctype
        or "decimal" in ctype
    )


def _is_group_col(col: Dict[str, Any]) -> bool:
    ctype = str(col.get("type") or "").strip().lower()
    uniq = col.get("unique_count")
    if not isinstance(uniq, int) or uniq < 2 or uniq > 20:
        return False
    return (
        ctype in {"categorical", "category", "text", "object", "string"}
        or "categor" in ctype
        or "object" in ctype
        or "text" in ctype
        or "string" in ctype
    )


def _pick_smoke_columns(profile: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    cols = _read_profile_columns(profile)
    if not cols:
        return None, None, None

    by_name: Dict[str, Dict[str, Any]] = {str(c["name"]): c for c in cols}

    group_pref = ["пол", "Исход", "Исход.2", "group", "sex"]
    target_pref = ["возраст", "NEWS2", "qSOFA", "SpO2 %", "Длительность госпитализации", "age"]

    group_name: Optional[str] = None
    for name in group_pref:
        candidate = by_name.get(name)
        if candidate and _is_group_col(candidate):
            group_name = name
            break
    if group_name is None:
        groups = [c for c in cols if _is_group_col(c)]
        groups.sort(
            key=lambda c: (
                abs(int(c.get("unique_count") or 99) - 2),
                int(c.get("missing_count") or 0),
                str(c.get("name")),
            )
        )
        if groups:
            group_name = str(groups[0]["name"])

    target_name: Optional[str] = None
    for name in target_pref:
        candidate = by_name.get(name)
        if candidate and _is_numeric_col(candidate):
            target_name = name
            break
    if target_name is None:
        nums = [
            c
            for c in cols
            if _is_numeric_col(c) and str(c.get("name")) != str(group_name or "")
        ]
        nums.sort(
            key=lambda c: (
                int(c.get("missing_count") or 0),
                -int(c.get("unique_count") or 0),
                str(c.get("name")),
            )
        )
        if nums:
            target_name = str(nums[0]["name"])

    if group_name is None or target_name is None:
        return group_name, target_name, None

    group_unique = by_name.get(group_name, {}).get("unique_count")
    method_id = "t_test_welch" if int(group_unique or 0) == 2 else "kruskal"
    return group_name, target_name, method_id


def _confirm_design_review(dataset_id: str) -> Dict[str, Any]:
    response = client.post(
        f"/api/v1/datasets/{dataset_id}/design_review/confirm",
        json={"actor": "smoke-test", "source": "covid-smoke-v2"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("confirmed") is True
    return payload


def _allowed_method_ids(requested: str) -> set[str]:
    normalized = str(requested or "").strip().lower()
    if normalized == "t_test_welch":
        # Runtime assumption checks may switch to a safer alternative.
        return {"t_test_welch", "t_test_ind", "mann_whitney"}
    if normalized == "kruskal":
        return {"kruskal", "anova", "anova_welch"}
    return {normalized} if normalized else set()


@pytest.fixture(scope="module")
def covid_smoke_context():
    file_path = _covid_file_path()
    if not os.path.exists(file_path):
        pytest.skip(f"COVID smoke dataset not found: {file_path}")

    with open(file_path, "rb") as f:
        upload_res = client.post(
            "/api/v1/datasets",
            files={
                "file": (
                    "covid_smoke.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert upload_res.status_code == 200, upload_res.text
    dataset_id = str(upload_res.json().get("id"))
    assert dataset_id

    dataset_dir = os.path.join(DATA_DIR, dataset_id)
    try:
        profile_res = client.get(f"/api/v1/datasets/{dataset_id}")
        assert profile_res.status_code == 200, profile_res.text
        profile = profile_res.json()
        group_col, outcome_col, method_id = _pick_smoke_columns(profile)

        if not group_col or not outcome_col or not method_id:
            pytest.skip("Unable to pick robust group/outcome columns for COVID smoke flow")

        yield {
            "dataset_id": dataset_id,
            "group_col": group_col,
            "outcome_col": outcome_col,
            "method_id": method_id,
        }
    finally:
        shutil.rmtree(dataset_dir, ignore_errors=True)


def test_covid_smoke_v2_python_plan_execute_report(covid_smoke_context, monkeypatch):
    monkeypatch.setattr(settings, "GLM_ENABLED", False)

    dataset_id = str(covid_smoke_context["dataset_id"])
    group_col = str(covid_smoke_context["group_col"])
    outcome_col = str(covid_smoke_context["outcome_col"])
    method_id = str(covid_smoke_context["method_id"])

    study_design_res = client.get(f"/api/v1/datasets/{dataset_id}/study_design")
    assert study_design_res.status_code == 200, study_design_res.text
    study_design_payload = study_design_res.json()
    assert isinstance(study_design_payload, dict)
    assert study_design_payload

    _confirm_design_review(dataset_id)
    design_status_res = client.get(f"/api/v1/datasets/{dataset_id}/design_review")
    assert design_status_res.status_code == 200, design_status_res.text
    assert design_status_res.json().get("confirmed") is True

    plan_text = (
        f"COVID cohort smoke: compare '{outcome_col}' between groups '{group_col}', "
        "then prepare an execution-ready protocol and report."
    )
    plan_res = client.post(
        "/api/v1/v2/analysis/plan",
        json={
            "dataset_id": dataset_id,
            "text": plan_text,
            "protocol": [],
            "preferences": {
                "design_confirmed": True,
                "use_critic": False,
                "use_knowledge_base": False,
            },
        },
    )
    assert plan_res.status_code == 200, plan_res.text
    plan_payload = plan_res.json()
    assert plan_payload.get("status") in {"completed", "partial"}
    assert isinstance(plan_payload.get("protocol"), list)
    assert len(plan_payload.get("protocol")) > 0

    execute_protocol = [
        {
            "id": "smoke_compare_python",
            "method": method_id,
            "config": {"outcome": outcome_col, "group": group_col, "engine": "python"},
        }
    ]
    execute_res = client.post(
        "/api/v1/v2/analysis/execute",
        json={
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": execute_protocol,
            "globals": {
                "design_confirmed": True,
                "source": "covid_smoke_v2_py",
                "engine": "python",
            },
        },
    )
    assert execute_res.status_code == 200, execute_res.text
    execute_payload = execute_res.json()
    run_id = str(execute_payload.get("run_id") or "")
    assert run_id
    assert execute_payload.get("design_review_confirmed") is True
    assert execute_payload.get("design_review_artifact_confirmed") is True
    assert execute_payload.get("status") in {"completed", "partial"}

    run_res = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={dataset_id}")
    assert run_res.status_code == 200, run_res.text
    run_payload = run_res.json()
    step_payload = (run_payload.get("results") or {}).get("smoke_compare_python")
    assert isinstance(step_payload, dict), run_payload
    actual_method_id = str(step_payload.get("method_id") or "").strip().lower()
    assert actual_method_id in _allowed_method_ids(method_id), step_payload
    assert str(step_payload.get("engine") or "").strip().lower() == "python"
    assert "p_value" in step_payload

    report_res = client.get(f"/api/v1/analysis/protocol/report/{run_id}/html?dataset_id={dataset_id}")
    assert report_res.status_code == 200, report_res.text
    html = report_res.text
    assert "<html" in html.lower()
    assert ("design" in html.lower()) or ("дизайн" in html.lower())
    assert 'id="methods"' in html
    assert 'id="results"' in html
    assert 'id="limitations"' in html

    pdf_res = client.get(f"/api/v1/analysis/protocol/report/{run_id}/pdf?dataset_id={dataset_id}")
    assert pdf_res.status_code == 200, pdf_res.text
    assert pdf_res.content[:4] == b"%PDF"

    docx_res = client.get(f"/api/v1/analysis/protocol/report/{run_id}/docx?dataset_id={dataset_id}")
    assert docx_res.status_code == 200, docx_res.text
    assert docx_res.content[:2] == b"PK"
    docx_text = _docx_text(docx_res.content)
    assert "Methods" in docx_text or "Методы" in docx_text
    assert "Limitations" in docx_text or "Ограничения" in docx_text

    artifacts_res = client.get(f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={dataset_id}")
    assert artifacts_res.status_code == 200, artifacts_res.text
    files = artifacts_res.json().get("files") or []
    names = {str(item.get("name")) for item in files if isinstance(item, dict)}
    assert "analysis_dataset.parquet" in names
    assert "analysis_dataset.xlsx" in names
    assert "analysis_dataset.meta.json" in names
    assert any(name.endswith(".html") and "protocol_report" in name for name in names)
    assert any(name.endswith(".pdf") and "protocol_report" in name for name in names)
    assert any(name.endswith(".docx") and "protocol_report" in name for name in names)

    quality_res = client.get(
        f"/api/v1/analysis/protocol/report/{run_id}/quality?dataset_id={dataset_id}&require_exports=true&style=gost"
    )
    assert quality_res.status_code == 200, quality_res.text
    quality_payload = quality_res.json()
    assert quality_payload.get("status") == "pass"
    assert quality_payload.get("ready") is True
    checks = quality_payload.get("checks") or {}
    assert (checks.get("design_artifact") or {}).get("ok") is True
    assert (checks.get("methods_metadata") or {}).get("ok") is True
    assert (checks.get("sections") or {}).get("ok") is True
    assert (checks.get("analysis_dataset_artifacts") or {}).get("ok") is True
    assert (checks.get("report_exports") or {}).get("ok") is True


def test_covid_smoke_v2_r_execute(covid_smoke_context, monkeypatch):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available in PATH")

    monkeypatch.setattr(settings, "GLM_ENABLED", False)

    dataset_id = str(covid_smoke_context["dataset_id"])
    group_col = str(covid_smoke_context["group_col"])
    outcome_col = str(covid_smoke_context["outcome_col"])
    method_id = str(covid_smoke_context["method_id"])

    _confirm_design_review(dataset_id)

    execute_protocol = [
        {
            "id": "smoke_compare_r",
            "method": method_id,
            "config": {"outcome": outcome_col, "group": group_col, "engine": "r"},
        }
    ]
    execute_res = client.post(
        "/api/v1/v2/analysis/execute",
        json={
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": execute_protocol,
            "globals": {
                "design_confirmed": True,
                "source": "covid_smoke_v2_r",
                "engine": "r",
            },
        },
    )
    assert execute_res.status_code == 200, execute_res.text
    execute_payload = execute_res.json()
    run_id = str(execute_payload.get("run_id") or "")
    assert run_id
    assert execute_payload.get("design_review_confirmed") is True
    assert execute_payload.get("design_review_artifact_confirmed") is True
    assert execute_payload.get("status") in {"completed", "partial"}

    run_res = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={dataset_id}")
    assert run_res.status_code == 200, run_res.text
    run_payload = run_res.json()
    step_payload = (run_payload.get("results") or {}).get("smoke_compare_r")
    assert isinstance(step_payload, dict), run_payload
    actual_method_id = str(step_payload.get("method_id") or "").strip().lower()
    assert actual_method_id in _allowed_method_ids(method_id), step_payload
    engine_used = str(step_payload.get("engine") or "").strip().lower()
    if engine_used != "r":
        pytest.skip("R engine fell back to Python in current environment")
    assert "p_value" in step_payload


def _execute_smoke_compare_step(
    dataset_id: str,
    method_id: str,
    outcome_col: str,
    group_col: str,
    *,
    engine: str,
    source: str,
) -> Dict[str, Any]:
    step_id = f"smoke_compare_{engine}"
    execute_protocol = [
        {
            "id": step_id,
            "method": method_id,
            "config": {"outcome": outcome_col, "group": group_col, "engine": engine},
        }
    ]
    execute_res = client.post(
        "/api/v1/v2/analysis/execute",
        json={
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": execute_protocol,
            "globals": {
                "design_confirmed": True,
                "source": source,
                "engine": engine,
            },
        },
    )
    assert execute_res.status_code == 200, execute_res.text
    execute_payload = execute_res.json()
    run_id = str(execute_payload.get("run_id") or "")
    assert run_id
    assert execute_payload.get("design_review_confirmed") is True
    assert execute_payload.get("design_review_artifact_confirmed") is True
    assert execute_payload.get("status") in {"completed", "partial"}

    run_res = client.get(f"/api/v1/analysis/run/{run_id}?dataset_id={dataset_id}")
    assert run_res.status_code == 200, run_res.text
    run_payload = run_res.json()
    step_payload = (run_payload.get("results") or {}).get(step_id)
    assert isinstance(step_payload, dict), run_payload
    return step_payload


def _start_replay_server(response_payload: Dict[str, Any]) -> Tuple[HTTPServer, str]:
    payload_bytes = json.dumps(response_payload, ensure_ascii=False).encode("utf-8")

    class _ReplayHandler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            path = str(self.path or "").strip()
            if path != "/api/v1/v2/analysis/execute":
                self.send_response(404)
                self.end_headers()
                return
            try:
                content_length = int(self.headers.get("Content-Length", "0") or 0)
            except Exception:
                content_length = 0
            if content_length > 0:
                _ = self.rfile.read(content_length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload_bytes)))
            self.end_headers()
            self.wfile.write(payload_bytes)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
    server = HTTPServer((host, port), _ReplayHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/api/v1/v2"


def test_covid_smoke_v2_python_r_metric_drift(covid_smoke_context, monkeypatch):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available in PATH")

    monkeypatch.setattr(settings, "GLM_ENABLED", False)

    dataset_id = str(covid_smoke_context["dataset_id"])
    group_col = str(covid_smoke_context["group_col"])
    outcome_col = str(covid_smoke_context["outcome_col"])
    method_id = str(covid_smoke_context["method_id"])

    _confirm_design_review(dataset_id)

    py_step = _execute_smoke_compare_step(
        dataset_id,
        method_id,
        outcome_col,
        group_col,
        engine="python",
        source="covid_smoke_v2_drift_py",
    )
    r_step = _execute_smoke_compare_step(
        dataset_id,
        method_id,
        outcome_col,
        group_col,
        engine="r",
        source="covid_smoke_v2_drift_r",
    )

    engine_used = str(r_step.get("engine") or "").strip().lower()
    if engine_used != "r":
        pytest.skip("R engine fell back to Python in current environment")

    assert str(py_step.get("method_id") or "").strip().lower() in _allowed_method_ids(method_id), py_step
    assert str(r_step.get("method_id") or "").strip().lower() in _allowed_method_ids(method_id), r_step

    assert bool(py_step.get("significant")) == bool(r_step.get("significant")), (
        f"COVID smoke significance mismatch python={py_step.get('significant')} r={r_step.get('significant')}"
    )

    py_p = py_step.get("p_value")
    r_p = r_step.get("p_value")
    try:
        py_p = float(py_p) if py_p is not None else None
        r_p = float(r_p) if r_p is not None else None
    except Exception:
        py_p = None
        r_p = None
    if py_p is not None and r_p is not None:
        assert abs(py_p - r_p) <= 0.25, (
            f"COVID smoke p-value drift too large python={py_p}, r={r_p}"
        )


def test_covid_smoke_v2_release_bundle_strict_compare(covid_smoke_context, monkeypatch):
    monkeypatch.setattr(settings, "GLM_ENABLED", False)

    dataset_id = str(covid_smoke_context["dataset_id"])
    group_col = str(covid_smoke_context["group_col"])
    outcome_col = str(covid_smoke_context["outcome_col"])
    method_id = str(covid_smoke_context["method_id"])

    _confirm_design_review(dataset_id)

    execute_protocol = [
        {
            "id": "smoke_compare_release",
            "method": method_id,
            "config": {"outcome": outcome_col, "group": group_col, "engine": "python"},
        }
    ]
    execute_res = client.post(
        "/api/v1/v2/analysis/execute",
        json={
            "dataset_id": dataset_id,
            "alpha": 0.05,
            "protocol": execute_protocol,
            "globals": {
                "design_confirmed": True,
                "source": "covid_smoke_v2_release_bundle",
                "engine": "python",
            },
        },
    )
    assert execute_res.status_code == 200, execute_res.text
    execute_payload = execute_res.json()
    run_id = str(execute_payload.get("run_id") or "")
    assert run_id

    release_res = client.get(
        f"/api/v1/analysis/protocol/release/{run_id}/zip",
        params={"dataset_id": dataset_id, "refresh": "true"},
    )
    assert release_res.status_code == 200, release_res.text
    assert str(release_res.headers.get("content-type") or "").startswith("application/zip")

    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = os.path.join(tmpdir, "bundle")
        os.makedirs(bundle_dir, exist_ok=True)

        with zipfile.ZipFile(BytesIO(release_res.content)) as archive:
            archive.extractall(bundle_dir)

        script_path = os.path.join(bundle_dir, "release", "reproduce_run.py")
        assert os.path.exists(script_path)

        with open(os.path.join(bundle_dir, "run", "results.json"), "r", encoding="utf-8") as f:
            bundled_results_payload = json.load(f)

        replay_server, base_url = _start_replay_server(bundled_results_payload)
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    script_path,
                    "--bundle-dir",
                    bundle_dir,
                    "--reexecute",
                    "--base-url",
                    base_url,
                    "--strict-compare",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            replay_server.shutdown()
            replay_server.server_close()

        assert completed.returncode == 0, (completed.stdout or "") + "\n" + (completed.stderr or "")
        assert "Manifest verification OK" in (completed.stdout or "")
        assert "Comparison summary" in (completed.stdout or "")
        assert '"mismatch_count": 0' in (completed.stdout or "")
