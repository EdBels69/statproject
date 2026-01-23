
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any, Optional
import asyncio
import os
import mimetypes
import hashlib
from datetime import datetime
import pandas as pd
from pydantic import BaseModel
import json
import uuid

from app.schemas.analysis import (
    AnalysisRequest, AnalysisResult, StatMethod, 
    ProtocolRequest, DesignRequest, BatchAnalysisRequest
)
from app.stats.registry import get_method, METHODS
from app.stats.engine import select_test, run_analysis
from app.modules.text_generator import TextGenerator
from app.core.pipeline import PipelineManager
from app.core.protocol_engine import ProtocolEngine
from app.modules.parsers import get_dataframe, get_dataset_path
from app.core.study_designer import StudyDesignEngine
from app.modules.reporting import generate_pdf_report, generate_protocol_pdf_report, generate_protocol_docx_report
from app.modules.docx_generator import create_results_document
from app.core.logging import logger

from app.api.datasets import DATA_DIR, parse_file

from app.stats.assumptions import check_normality as check_normality_profile
from app.stats.assumptions import check_homogeneity as check_homogeneity_profile
from app.stats.assumptions import recommend_test as recommend_test_from_profile

router = APIRouter()
pipeline = PipelineManager(DATA_DIR)
protocol_engine = ProtocolEngine(pipeline)


async def _run_in_threadpool_with_timeout(fn, timeout_s: float, timeout_detail: str):
    from fastapi.concurrency import run_in_threadpool

    try:
        return await asyncio.wait_for(run_in_threadpool(fn), timeout=timeout_s)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail=timeout_detail)


def _infer_kind(df: pd.DataFrame, col: str) -> str:
    if col not in df.columns:
        return "categorical"

    s = df[col]
    name_l = str(col).strip().lower()
    if pd.api.types.is_numeric_dtype(s):
        try:
            non_na = s.dropna()
            n = int(len(non_na))
            unique = int(non_na.nunique(dropna=True)) if n else 0
        except Exception:
            n = int(len(s))
            try:
                unique = int(s.nunique(dropna=True))
            except Exception:
                unique = 0

        ratio = float(unique) / float(max(1, n))
        looks_like_group = any(
            k in name_l
            for k in [
                "группа",
                "group",
                "treatment",
                "arm",
                "cohort",
                "класс",
                "категор",
                "category",
                "групп",
                "рандом",
            ]
        )
        if (unique and unique <= 12 and ratio <= 0.2) or (looks_like_group and unique and unique <= 50):
            return "categorical"

        return "numeric"

    return "categorical"


class ExportDocxRequest(BaseModel):
    results: Dict[str, Any]
    dataset_name: Optional[str] = None
    filename: Optional[str] = None
    style: Optional[str] = None
    format_options: Optional[Dict[str, Any]] = None


class AssumptionsCheckRequest(BaseModel):
    dataset_id: str
    method_id: str
    config: Dict[str, Any] = {}
    alpha: float = 0.05


@router.post("/assumptions")
async def check_assumptions(req: AssumptionsCheckRequest):
    try:
        df = get_dataframe(req.dataset_id, DATA_DIR)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось загрузить файл данных: {str(e)}")

    method_id = (req.method_id or "").strip()
    config = req.config or {}
    alpha = float(req.alpha) if req.alpha is not None else 0.05

    def pick(name: str):
        v = config.get(name)
        if v is None:
            return ""
        return str(v).strip()

    def pick_targets():
        v = config.get("targets")
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

    is_paired = bool(config.get("is_paired")) or method_id in {"t_test_rel", "wilcoxon", "rm_anova", "friedman"}

    target = pick("target") or pick("outcome")
    group = pick("group")
    targets = pick_targets()

    if not target and targets:
        target = targets[0]

    if method_id in {"pearson", "spearman", "clustered_correlation"}:
        if len(targets) < 2:
            return {"alpha": alpha, "method_id": method_id, "shapiro_p": None, "levene_p": None}

        col_a, col_b = targets[0], targets[1]
        if col_a not in df.columns or col_b not in df.columns:
            raise HTTPException(status_code=400, detail="Выбранные столбцы не найдены")

        a = pd.to_numeric(df[col_a], errors="coerce").tolist()
        b = pd.to_numeric(df[col_b], errors="coerce").tolist()
        norm_a = check_normality_profile(a, alpha=alpha)
        norm_b = check_normality_profile(b, alpha=alpha)
        p_vals = [p for p in [norm_a.get("p"), norm_b.get("p")] if p is not None]
        shapiro_p = min(p_vals) if p_vals else None
        return {
            "alpha": alpha,
            "method_id": method_id,
            "n_groups": None,
            "shapiro_p": shapiro_p,
            "levene_p": None,
            "normality": {"a": norm_a, "b": norm_b},
            "homogeneity": None,
            "recommended_test": None,
        }

    if not target or not group:
        return {"alpha": alpha, "method_id": method_id, "shapiro_p": None, "levene_p": None}

    if target not in df.columns or group not in df.columns:
        raise HTTPException(status_code=400, detail="Выбранные столбцы не найдены")

    df_local = df[[target, group]].copy()
    df_local[target] = pd.to_numeric(df_local[target], errors="coerce")
    df_local = df_local.dropna(subset=[group])

    groups = df_local[group].dropna().unique().tolist()
    n_groups = len(groups)
    if n_groups < 2:
        return {"alpha": alpha, "method_id": method_id, "n_groups": n_groups, "shapiro_p": None, "levene_p": None}

    normality = {}
    per_group_p = []
    data_groups = []
    for g in groups:
        values = df_local.loc[df_local[group] == g, target].dropna().tolist()
        data_groups.append(values)
        res = check_normality_profile(values, alpha=alpha)
        normality[str(g)] = res
        if res.get("p") is not None:
            per_group_p.append(res.get("p"))

    shapiro_p = min(per_group_p) if per_group_p else None
    homogeneity = check_homogeneity_profile(data_groups, alpha=alpha)
    levene_p = homogeneity.get("p")

    norm_ok_values = [r.get("passed") for r in normality.values() if r.get("passed") is not None]
    norm_ok = (all(norm_ok_values) if norm_ok_values else None)
    homo_ok = homogeneity.get("passed")
    recommended = None
    if norm_ok is not None and homo_ok is not None:
        recommended = recommend_test_from_profile(n_groups, is_paired, bool(norm_ok), bool(homo_ok))

    return {
        "alpha": alpha,
        "method_id": method_id,
        "n_groups": n_groups,
        "shapiro_p": shapiro_p,
        "levene_p": levene_p,
        "normality": normality,
        "homogeneity": homogeneity,
        "recommended_test": recommended,
        "independence": True,
    }

# --- Endpoints ---

@router.get("/templates", response_model=Dict[str, Any])
def list_design_templates(goal: Optional[str] = None):
    try:
        designer = StudyDesignEngine()
        return {"templates": designer.list_templates(goal=goal)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список шаблонов: {str(e)}")

@router.post("/design", response_model=Dict[str, Any])
def suggest_design(req: DesignRequest):
    """
    Uses StudyDesignEngine to generate an Analysis Protocol based on user inputs.
    """
    try:
        metadata: Dict[str, Any] = {}
        # 1. Load Dataset Metadata for Context (types, normality)
        # We assume the profile/scan_report exists or we quickly detect basic types
        # For MVP, we pass minimal metadata or load the scan report
        scan_path = os.path.join(pipeline.get_dataset_dir(req.dataset_id), "processed", "scan_report.json")
        
        if os.path.exists(scan_path):
            with open(scan_path) as f:
                full_report = json.load(f)
                metadata = full_report.get("columns", {})

        # 2. Generate Protocol
        designer = StudyDesignEngine()
        protocol = designer.suggest_protocol(req.goal, req.variables, metadata, template_id=req.template_id)
        return protocol
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось сформировать дизайн исследования: {str(e)}")

@router.get("/run/{run_id}")
def get_run_results(run_id: str, dataset_id: str):
    """
    Retrieves the results of a specific analysis run.
    """
    try:
        # We need dataset_id to find the run folder in the current hierarchy
        # Pipeline structure: datasets/{id}/analysis/{run_id}/results.json
        res = pipeline.get_run_results(dataset_id, run_id)
        if not res:
             raise HTTPException(status_code=404, detail="Результаты не найдены")
        return res
    except Exception as e:
         raise HTTPException(status_code=404, detail=f"Запуск не найден: {str(e)}")


def _apply_report_customization(run_data: Dict[str, Any], sections: Optional[str], order: Optional[str]) -> Dict[str, Any]:
    if not isinstance(run_data, dict):
        return run_data
    results = run_data.get("results")
    if not isinstance(results, dict):
        return run_data

    selected = None
    if isinstance(sections, str) and sections.strip():
        selected = [s.strip() for s in sections.split(",") if s.strip()]

    order_ids = None
    if isinstance(order, str) and order.strip():
        order_ids = [s.strip() for s in order.split(",") if s.strip()]

    working_ids = list(results.keys())
    if selected is not None:
        selected_set = set(selected)
        working_ids = [k for k in working_ids if k in selected_set]

    out_items: List[tuple[str, Any]] = []
    used = set()

    if order_ids:
        for k in order_ids:
            if k in results and k in working_ids and k not in used:
                out_items.append((k, results[k]))
                used.add(k)

    for k in working_ids:
        if k in results and k not in used:
            out_items.append((k, results[k]))
            used.add(k)

    next_run = dict(run_data)
    next_run["results"] = dict(out_items)
    return next_run


def _artifact_basename(
    kind: str,
    run_id: str,
    style: Optional[str],
    density: Optional[str],
    accent: Optional[str],
    sections: Optional[str],
    order: Optional[str],
) -> str:
    payload = {
        "kind": str(kind),
        "run_id": str(run_id),
        "style": style,
        "density": density,
        "accent": accent,
        "sections": sections,
        "order": order,
    }
    digest = hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"{kind}_{run_id}_{digest}"


def _read_run_file(dataset_id: str, run_id: str, filename: str) -> bytes:
    safe_name = os.path.basename(str(filename or "").strip())
    if not safe_name or safe_name in {".", ".."}:
        raise FileNotFoundError("File not found")
    if safe_name != str(filename).strip():
        raise FileNotFoundError("File not found")

    run_dir = pipeline.get_run_dir(dataset_id, run_id)
    path = os.path.join(run_dir, safe_name)
    if not os.path.exists(path) or not os.path.isfile(path):
        raise FileNotFoundError("File not found")
    with open(path, "rb") as f:
        return f.read()

@router.get("/protocol/report/{run_id}/html")
async def get_protocol_report_html(
    run_id: str,
    dataset_id: str,
    sections: Optional[str] = None,
    order: Optional[str] = None,
    style: Optional[str] = None,
    density: Optional[str] = None,
    accent: Optional[str] = None,
):
    """
    Generates a printable HTML report for the analysis run.
    """
    from fastapi.responses import HTMLResponse
    from app.modules.reporting import render_protocol_report
    
    try:
        artifact_name = _artifact_basename(
            "protocol_report",
            run_id,
            style,
            density,
            accent,
            sections,
            order,
        ) + ".html"
        try:
            cached = await _run_in_threadpool_with_timeout(
                lambda: pipeline.read_run_artifact(dataset_id, run_id, artifact_name),
                10.0,
                "",
            )
            return HTMLResponse(content=cached.decode("utf-8", errors="replace"))
        except Exception:
            pass

        res = await _run_in_threadpool_with_timeout(
            lambda: pipeline.get_run_results(dataset_id, run_id),
            60.0,
            "Получение результатов протокола занимает слишком много времени",
        )
        if not res:
            raise HTTPException(status_code=404, detail="Результаты не найдены")

        res = _apply_report_customization(res, sections, order)

        html = await _run_in_threadpool_with_timeout(
            lambda: render_protocol_report(
                res,
                dataset_name=f"Файл данных {dataset_id[:5]}...",
                style=style,
                options={"density": density, "accent": accent},
            ),
            60.0,
            "Формирование HTML-отчёта занимает слишком много времени",
        )
        try:
            await _run_in_threadpool_with_timeout(
                lambda: pipeline.save_run_artifact(
                    pipeline.get_run_dir(dataset_id, run_id),
                    artifact_name,
                    html.encode("utf-8"),
                ),
                10.0,
                "",
            )
        except Exception:
            pass
        return HTMLResponse(content=html)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать отчёт: {str(e)}")


@router.get("/protocol/report/{run_id}/pdf")
async def get_protocol_report_pdf(
    run_id: str,
    dataset_id: str,
    sections: Optional[str] = None,
    order: Optional[str] = None,
    style: Optional[str] = None,
    density: Optional[str] = None,
    accent: Optional[str] = None,
):
    from fastapi.responses import Response

    def _enrich_run_data_for_report(run_data: Any) -> Any:
        if not isinstance(run_data, dict):
            return run_data
        enriched = dict(run_data)
        enriched["run_id"] = run_id
        try:
            run_dir = pipeline.get_run_dir(dataset_id, run_id)
            proto_path = os.path.join(run_dir, "protocol.json")
            if os.path.exists(proto_path):
                with open(proto_path, "r") as f:
                    protocol = json.load(f)
                if isinstance(protocol, dict):
                    enriched["protocol"] = protocol
                    if isinstance(protocol.get("goal"), str) and protocol.get("goal"):
                        enriched["protocol_goal"] = protocol.get("goal")
                    steps = protocol.get("steps")
                    if isinstance(steps, list) and steps:
                        step_meta: Dict[str, Any] = {}
                        for s in steps:
                            if not isinstance(s, dict):
                                continue
                            sid = s.get("id")
                            if sid is None:
                                continue
                            step_meta[str(sid)] = s
                        if step_meta:
                            enriched["step_meta"] = step_meta
        except Exception:
            pass
        return enriched

    try:
        artifact_name = _artifact_basename(
            "protocol_report",
            run_id,
            style,
            density,
            accent,
            sections,
            order,
        ) + ".pdf"
        try:
            cached = await _run_in_threadpool_with_timeout(
                lambda: pipeline.read_run_artifact(dataset_id, run_id, artifact_name),
                10.0,
                "",
            )
            filename = f"protocol_report_{run_id}.pdf"
            return Response(
                content=cached,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception:
            pass

        res = await _run_in_threadpool_with_timeout(
            lambda: pipeline.get_run_results(dataset_id, run_id),
            60.0,
            "Получение результатов протокола занимает слишком много времени",
        )
        if not res:
            raise HTTPException(status_code=404, detail="Результаты не найдены")

        res = _apply_report_customization(res, sections, order)
        res = _enrich_run_data_for_report(res)

        pdf_bytes = await _run_in_threadpool_with_timeout(
            lambda: generate_protocol_pdf_report(
                res,
                dataset_name=f"Файл данных {dataset_id[:5]}...",
                style=style,
                options={"density": density, "accent": accent},
            ),
            240.0,
            "Формирование PDF-отчёта занимает слишком много времени",
        )
        try:
            await _run_in_threadpool_with_timeout(
                lambda: pipeline.save_run_artifact(
                    pipeline.get_run_dir(dataset_id, run_id),
                    artifact_name,
                    pdf_bytes,
                ),
                10.0,
                "",
            )
        except Exception:
            pass
        filename = f"protocol_report_{run_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать PDF-отчёт: {str(e)}")

@router.get("/protocol/report/{run_id}/docx")
async def get_protocol_report_docx(
    run_id: str,
    dataset_id: str,
    sections: Optional[str] = None,
    order: Optional[str] = None,
    style: Optional[str] = None,
    density: Optional[str] = None,
    accent: Optional[str] = None,
):
    from fastapi.responses import Response

    def _enrich_run_data_for_report(run_data: Any) -> Any:
        if not isinstance(run_data, dict):
            return run_data
        enriched = dict(run_data)
        enriched["run_id"] = run_id
        try:
            run_dir = pipeline.get_run_dir(dataset_id, run_id)
            proto_path = os.path.join(run_dir, "protocol.json")
            if os.path.exists(proto_path):
                with open(proto_path, "r") as f:
                    protocol = json.load(f)
                if isinstance(protocol, dict):
                    enriched["protocol"] = protocol
                    if isinstance(protocol.get("goal"), str) and protocol.get("goal"):
                        enriched["protocol_goal"] = protocol.get("goal")
                    steps = protocol.get("steps")
                    if isinstance(steps, list) and steps:
                        step_meta: Dict[str, Any] = {}
                        for s in steps:
                            if not isinstance(s, dict):
                                continue
                            sid = s.get("id")
                            if sid is None:
                                continue
                            step_meta[str(sid)] = s
                        if step_meta:
                            enriched["step_meta"] = step_meta
        except Exception:
            pass
        return enriched

    try:
        artifact_name = _artifact_basename(
            "protocol_report",
            run_id,
            style,
            density,
            accent,
            sections,
            order,
        ) + ".docx"
        try:
            cached = await _run_in_threadpool_with_timeout(
                lambda: pipeline.read_run_artifact(dataset_id, run_id, artifact_name),
                10.0,
                "",
            )
            filename = f"protocol_report_{run_id}.docx"
            return Response(
                content=cached,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception:
            pass

        res = await _run_in_threadpool_with_timeout(
            lambda: pipeline.get_run_results(dataset_id, run_id),
            60.0,
            "Получение результатов протокола занимает слишком много времени",
        )
        if not res:
            raise HTTPException(status_code=404, detail="Результаты не найдены")

        res = _apply_report_customization(res, sections, order)
        res = _enrich_run_data_for_report(res)

        docx_bytes = await _run_in_threadpool_with_timeout(
            lambda: generate_protocol_docx_report(
                res,
                dataset_name=f"Файл данных {dataset_id[:5]}...",
                style=style,
                options={"density": density, "accent": accent},
            ),
            240.0,
            "Формирование DOCX-отчёта занимает слишком много времени",
        )
        try:
            await _run_in_threadpool_with_timeout(
                lambda: pipeline.save_run_artifact(
                    pipeline.get_run_dir(dataset_id, run_id),
                    artifact_name,
                    docx_bytes,
                ),
                10.0,
                "",
            )
        except Exception:
            pass
        filename = f"protocol_report_{run_id}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать DOCX-отчёт: {str(e)}")


@router.get("/protocol/artifacts/{run_id}")
async def list_protocol_artifacts(run_id: str, dataset_id: str):
    try:
        run_dir = pipeline.get_run_dir(dataset_id, run_id)
        if not os.path.isdir(run_dir):
            raise HTTPException(status_code=404, detail="Запуск не найден")

        items: List[Dict[str, Any]] = []
        for base_name in ["protocol.json", "results.json"]:
            path = os.path.join(run_dir, base_name)
            if os.path.exists(path) and os.path.isfile(path):
                st = os.stat(path)
                items.append(
                    {
                        "name": base_name,
                        "size": int(st.st_size),
                        "updated_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                        "location": "run",
                    }
                )

        artifacts_dir = os.path.join(run_dir, "artifacts")
        if os.path.isdir(artifacts_dir):
            for name in sorted(os.listdir(artifacts_dir)):
                if not name or name.startswith("."):
                    continue
                path = os.path.join(artifacts_dir, name)
                if not os.path.isfile(path):
                    continue
                st = os.stat(path)
                items.append(
                    {
                        "name": name,
                        "size": int(st.st_size),
                        "updated_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                        "location": "artifacts",
                    }
                )

        return {"run_id": run_id, "dataset_id": dataset_id, "files": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось получить список артефактов: {str(e)}")


@router.get("/protocol/artifacts/{run_id}/download")
async def download_protocol_artifact(run_id: str, dataset_id: str, name: str):
    from fastapi.responses import Response

    try:
        safe_name = os.path.basename(str(name or "").strip())
        if not safe_name or safe_name in {".", ".."}:
            raise HTTPException(status_code=400, detail="Некорректное имя файла")
        if safe_name != str(name).strip():
            raise HTTPException(status_code=400, detail="Некорректное имя файла")

        if safe_name in {"protocol.json", "results.json"}:
            content = await _run_in_threadpool_with_timeout(
                lambda: _read_run_file(dataset_id, run_id, safe_name),
                60.0,
                "Чтение файла занимает слишком много времени",
            )
        else:
            content = await _run_in_threadpool_with_timeout(
                lambda: pipeline.read_run_artifact(dataset_id, run_id, safe_name),
                60.0,
                "Чтение файла занимает слишком много времени",
            )

        media_type = mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл не найден")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось скачать файл: {str(e)}")


@router.post("/export/docx")
async def export_docx(request: ExportDocxRequest):
    from fastapi.responses import StreamingResponse

    try:
        buffer = await _run_in_threadpool_with_timeout(
            lambda: create_results_document(
                request.results,
                dataset_name=request.dataset_name,
                style=request.style,
                options=request.format_options,
            ),
            240.0,
            "Экспорт DOCX занимает слишком много времени",
        )
        filename = request.filename or "results.docx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось экспортировать DOCX: {str(e)}")

@router.post("/protocol/run")
async def run_protocol_api(request: ProtocolRequest):
    """
    Executes a multi-step analysis protocol.
    Returns the run_id (analysis container ID).
    """
    try:
        df = await _run_in_threadpool_with_timeout(
            lambda: get_dataframe(request.dataset_id, DATA_DIR),
            60.0,
            "Загрузка данных занимает слишком много времени",
        )

        run_id = await _run_in_threadpool_with_timeout(
            lambda: protocol_engine.execute_protocol(request.dataset_id, df, request.protocol, alpha=request.alpha),
            240.0,
            "Запуск протокола занимает слишком много времени",
        )

        return {"status": "success", "run_id": run_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить протокол: {str(e)}")

@router.post("/run", response_model=AnalysisResult)
async def run_method_api(request: AnalysisRequest):
    df = await _run_in_threadpool_with_timeout(
        lambda: get_dataframe(request.dataset_id, DATA_DIR),
        60.0,
        "Загрузка данных занимает слишком много времени",
    )
    
    col_a = request.target_column
    col_b = request.features[0] # Single feature for now
    
    # 2. Determine Method
    method_id = request.method_override
    if not method_id:
        # Auto-detect
        types = {c: _infer_kind(df, c) for c in [col_a, col_b]}
        method_id = select_test(df, col_a, col_b, types, is_paired=request.is_paired)

    if not method_id:
        raise HTTPException(status_code=400, detail="Не удалось определить метод анализа.")

    # 3. Run (async via threadpool for CPU-bound operations)
    def execute_analysis():
        results = run_analysis(df, method_id, col_a, col_b, is_paired=request.is_paired)
        
        # Build AnalysisResult
        method_info = get_method(method_id)
        
        res = AnalysisResult(
            method=method_info,
            p_value=results["p_value"],
            effect_size=results.get("effect_size"),
            effect_size_name=results.get("effect_size_name"),
            effect_size_ci_lower=results.get("effect_size_ci_lower"),
            effect_size_ci_upper=results.get("effect_size_ci_upper"),
            power=results.get("power"),
            bf10=results.get("bf10"),
            stat_value=results["stat_value"],
            significant=results["significant"],
            groups=results.get("groups"),
            plot_data=results.get("plot_data"),
            plot_stats=results.get("plot_stats"),
            conclusion=""
        )
        return res
    
    try:
        res = await _run_in_threadpool_with_timeout(
            execute_analysis,
            180.0,
            "Анализ занимает слишком много времени",
        )
        
        try:
            from app.llm import get_ai_conclusion
            ai_conclusion = await asyncio.wait_for(get_ai_conclusion(res), timeout=20.0)
            if ai_conclusion:
                res.conclusion = ai_conclusion
        except Exception:
            pass
        return res
    except Exception as e:
        logger.error(f"Analysis execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")
    
    
    # 4. Format Result
    # Use Rule-Based Generator for "Dissertation Style"
    variables_map = {"target": col_a, "feature": col_b, "group": col_b} # standardized map
    base_conclusion = TextGenerator.generate_conclusion(results, variables_map)
    
    analysis_res = AnalysisResult(
        method=method_info,
        p_value=result["p_value"],
        stat_value=result["stat_value"],
        significant=result["significant"],
        groups=result.get("groups"),
        plot_data=result.get("plot_data"),
        plot_stats=result.get("plot_stats"),
        conclusion=base_conclusion
    )

    # AI Enhancement
    from app.core.config import settings
    if settings.GLM_ENABLED and settings.GLM_API_KEY:
        from app.llm import get_ai_conclusion
        try:
            ai_text = await get_ai_conclusion(analysis_res)
            if ai_text:
                analysis_res.conclusion = ai_text
        except Exception:
            pass # Keep base conclusion
            
    return analysis_res

@router.get("/report/{dataset_id}")
async def download_report(
    dataset_id: str, 
    target_col: str, 
    group_col: str, 
    method_id: str = None
):
    from fastapi.responses import HTMLResponse
    from app.modules.reporting import render_report
    
    try:
        df = await _run_in_threadpool_with_timeout(
            lambda: get_dataframe(dataset_id, DATA_DIR),
            60.0,
            "Загрузка данных занимает слишком много времени",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден или исходный файл отсутствует")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось загрузить файл данных: {str(e)}")

    dataset_name = f"Файл данных {dataset_id[:8]}"
    meta_path = os.path.join(DATA_DIR, dataset_id, "source", "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
                dataset_name = meta.get("original_filename") or dataset_name
        except Exception:
            pass
    
    # 2. Determine Method (if not provided)
    col_a = target_col
    col_b = group_col
    
    if not method_id:
        # Mini auto-detect
        types = {c: _infer_kind(df, c) for c in [col_a, col_b]}
        method_id = select_test(df, col_a, col_b, types)
    
    if not method_id:
        raise HTTPException(status_code=400, detail="Не удалось определить метод для отчёта.")

    
    # 3. Run Analysis
    try:
        res = await _run_in_threadpool_with_timeout(
            lambda: run_analysis(df, method_id, col_a, col_b),
            180.0,
            "Анализ для отчёта занимает слишком много времени",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    method_info = get_method(method_id)
    
    # 4. Create Result Object
    # Initial conclusion
    conclusion = f"{'Обнаружено статистически значимое различие' if res['significant'] else 'Статистически значимых различий не обнаружено'} (p={res['p_value']:.4f})."
    
    analysis_result = AnalysisResult(
        method=method_info,
        p_value=res["p_value"],
        effect_size=res.get("effect_size"),
        effect_size_name=res.get("effect_size_name"),
        effect_size_ci_lower=res.get("effect_size_ci_lower"),
        effect_size_ci_upper=res.get("effect_size_ci_upper"),
        power=res.get("power"),
        bf10=res.get("bf10"),
        stat_value=res["stat_value"],
        significant=res["significant"],
        groups=res.get("groups"),
        plot_data=res.get("plot_data"),
        plot_stats=res.get("plot_stats"),
        conclusion=conclusion
    )

    # 5. Enhace with AI (Async)
    from app.core.config import settings
    if settings.GLM_ENABLED and settings.GLM_API_KEY:
        from app.llm import get_ai_conclusion
        try:
            ai_text = await asyncio.wait_for(get_ai_conclusion(analysis_result), timeout=20.0)
            if ai_text:
                analysis_result.conclusion = ai_text
        except Exception as e:
            logger.warning(f"AI Enhancement failed: {e}", exc_info=True)
            
    # 6. Render HTML
    html_content = await _run_in_threadpool_with_timeout(
        lambda: render_report(analysis_result, target_col, group_col, dataset_name=dataset_name),
        60.0,
        "Формирование HTML-отчёта занимает слишком много времени",
    )
    
    return HTMLResponse(content=html_content)


@router.get("/report/{dataset_id}/pdf")
async def download_report_pdf(
    dataset_id: str,
    target_col: str,
    group_col: str,
    method_id: str = None
):
    from fastapi.responses import Response

    try:
        df = await _run_in_threadpool_with_timeout(
            lambda: get_dataframe(dataset_id, DATA_DIR),
            60.0,
            "Загрузка данных занимает слишком много времени",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Файл данных не найден или исходный файл отсутствует")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось загрузить файл данных: {str(e)}")

    col_a = target_col
    col_b = group_col

    if not method_id:
        types = {c: _infer_kind(df, c) for c in [col_a, col_b]}
        method_id = select_test(df, col_a, col_b, types)

    if not method_id:
        raise HTTPException(status_code=400, detail="Не удалось определить метод для отчёта.")

    try:
        res = await _run_in_threadpool_with_timeout(
            lambda: run_analysis(df, method_id, col_a, col_b),
            180.0,
            "Анализ для отчёта занимает слишком много времени",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    method_info = get_method(method_id)
    conclusion = f"{'Обнаружено статистически значимое различие' if res['significant'] else 'Статистически значимых различий не обнаружено'} (p={res['p_value']:.4f})."

    analysis_result = AnalysisResult(
        method=method_info,
        p_value=res["p_value"],
        effect_size=res.get("effect_size"),
        effect_size_name=res.get("effect_size_name"),
        effect_size_ci_lower=res.get("effect_size_ci_lower"),
        effect_size_ci_upper=res.get("effect_size_ci_upper"),
        power=res.get("power"),
        bf10=res.get("bf10"),
        stat_value=res["stat_value"],
        significant=res["significant"],
        groups=res.get("groups"),
        plot_data=res.get("plot_data"),
        plot_stats=res.get("plot_stats"),
        conclusion=conclusion
    )

    from app.core.config import settings
    if settings.GLM_ENABLED and settings.GLM_API_KEY:
        from app.llm import get_ai_conclusion
        try:
            ai_text = await asyncio.wait_for(get_ai_conclusion(analysis_result), timeout=20.0)
            if ai_text:
                analysis_result.conclusion = ai_text
        except Exception as e:
            logger.warning(f"AI Enhancement failed: {e}", exc_info=True)

    pdf_bytes = await _run_in_threadpool_with_timeout(
        lambda: generate_pdf_report(
            analysis_result.model_dump(),
            {"target": target_col, "group": group_col},
            dataset_id,
        ),
        240.0,
        "Формирование PDF-отчёта занимает слишком много времени",
    )

    filename = f"report_{dataset_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


class PdfExportRequest(BaseModel):
    results: Dict[str, Any]
    variables: Dict[str, Any]
    dataset_id: str
    style: Optional[str] = None
    format_options: Optional[Dict[str, Any]] = None


@router.post("/report/pdf")
async def export_report_pdf(req: PdfExportRequest):
    from fastapi.responses import Response

    pdf_bytes = await _run_in_threadpool_with_timeout(
        lambda: generate_pdf_report(req.results, req.variables, req.dataset_id, style=req.style, options=req.format_options),
        240.0,
        "Экспорт PDF занимает слишком много времени",
    )
    filename = f"report_{req.dataset_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

from app.schemas.analysis import BatchAnalysisResponse, BatchAnalysisRequest

def _sanitize(obj):
    """Recursively replace NaN/Inf with None."""
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj

@router.post("/batch", response_model=BatchAnalysisResponse)
async def run_batch_analysis(request: BatchAnalysisRequest):
    from app.schemas.analysis import DescriptiveStat, BatchAnalysisResponse, AnalysisResult
    from fastapi.concurrency import run_in_threadpool
    
    # 1. Load Data (sync function in threadpool)
    def load_batch_data():
        return get_dataframe(request.dataset_id, DATA_DIR)
    
    df = await run_in_threadpool(load_batch_data)

    # 2. Compute Descriptives (sync function in threadpool)
    def compute_descriptives_sync():
        from app.stats.engine import compute_descriptive_compare
        
        descriptives = []
        
        for col in request.target_columns:
            if col not in df.columns: continue
            
            # Get raw stats (returns dict keyed by group -> {mean, count...})
            raw_stats = compute_descriptive_compare(df, col, request.group_column)
            
            # Convert to DescriptiveStat objects
            for grp, stats in raw_stats.items():
                if grp == "overall" and len(raw_stats) > 1: continue 
                
                if not isinstance(stats, dict): continue
                
                ds = DescriptiveStat(
                    variable=col,
                    group=str(grp),
                    count=stats.get("count", 0),
                    missing=stats.get("missing"),
                    mean=stats.get("mean"),
                    median=stats.get("median"),
                    mode=stats.get("mode"),
                    sd=stats.get("std"),
                    se=stats.get("se"),
                    variance=stats.get("variance"),
                    cv=stats.get("cv"),
                    geometric_mean=stats.get("geometric_mean"),
                    range=stats.get("range"),
                    iqr=stats.get("iqr"),
                    skewness=stats.get("skewness"),
                    kurtosis=stats.get("kurtosis"),
                    ci_95_low=stats.get("ci_95_low"),
                    ci_95_high=stats.get("ci_95_high"),
                    shapiro_w=stats.get("shapiro_w"),
                    shapiro_p=stats.get("shapiro_p"),
                    is_normal=(stats.get("shapiro_p") is not None and stats.get("shapiro_p") >= 0.05)
                )
                descriptives.append(ds)
        return descriptives
    
    descriptives = await run_in_threadpool(compute_descriptives_sync)
    
    # Sanitize Descriptives
    descriptives = _sanitize(descriptives)
    
    # 3. Running Hypothesis Tests (sync function in threadpool)
    def run_tests_sync():
        results = {}
        group_col = request.group_column
        
        # Pre-calculate types for test selection
        if not isinstance(df[group_col].dtype, pd.CategoricalDtype) and df[group_col].nunique() < 10:
             pass
             
        for col in request.target_columns:
            if col not in df.columns: 
                continue
                
            # Select Method
            types = {col: "numeric", group_col: "categorical"}
            method_id = select_test(df, col, group_col, types)
            
            if not method_id:
                continue
                
            try:
                # Run with alpha parameter
                res = run_analysis(df, method_id, col, group_col, alpha=request.alpha)
                
                # SANITIZE RESULT
                res = _sanitize(res)
                
                # Format
                method_info = get_method(method_id)
                conclusion = f"p={res.get('p_value'):.4f}" if res.get('p_value') is not None else "p=н/д"
                
                result_obj = AnalysisResult(
                    method=method_info,
                    p_value=res.get("p_value"),
                    effect_size=res.get("effect_size"),
                    effect_size_name=res.get("effect_size_name"),
                    effect_size_ci_lower=res.get("effect_size_ci_lower"),
                    effect_size_ci_upper=res.get("effect_size_ci_upper"),
                    power=res.get("power"),
                    bf10=res.get("bf10"),
                    stat_value=res.get("stat_value"),
                    significant=res.get("significant", False),
                    groups=res.get("groups"),
                    plot_data=res.get("plot_data"),
                    plot_stats=res.get("plot_stats"),
                    conclusion=conclusion,
                    adjusted_p_value=res.get("p_value_adj"),
                    significant_adj=res.get("significant_adj")
                )
                
                results[col] = result_obj
                
            except Exception as e:
                logger.error(f"Batch analysis failed for {col}: {e}", exc_info=True)
                pass
        return results
    
    results = await run_in_threadpool(run_tests_sync)

    return BatchAnalysisResponse(descriptives=descriptives, results=results)
