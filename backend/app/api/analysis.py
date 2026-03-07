
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import os
import mimetypes
import hashlib
import io
import zipfile
from datetime import datetime
import pandas as pd
from pydantic import BaseModel
import json

from app.schemas.analysis import (
    AnalysisRequest, AnalysisResult,
    ProtocolRequest, DesignRequest, BatchAnalysisRequest
)
from app.stats.registry import get_method
from app.stats.engine import select_test, run_analysis
from app.core.pipeline import PipelineManager
from app.core.protocol_engine import ProtocolEngine
from app.modules.parsers import get_dataframe
from app.core.study_designer import StudyDesignEngine
from app.modules.reporting import generate_pdf_report, generate_protocol_pdf_report, generate_protocol_docx_report, render_protocol_report, _extract_protocol_findings
from app.modules.docx_generator import create_results_document
from app.modules.legacy_telemetry import record_legacy_hit
from app.modules.analysis_result_v2 import normalize_analysis_result_v2, normalize_run_data_results
from app.core.logging import logger
from app.core.config import settings
from app.llm import generate_protocol_summary

from app.api.datasets import DATA_DIR, WORKSPACE_DIR, _load_dataset_meta

from app.stats.assumptions import check_normality as check_normality_profile
from app.stats.assumptions import check_homogeneity as check_homogeneity_profile
from app.stats.assumptions import recommend_test as recommend_test_from_profile
from app.modules.reporting_contracts import build_report_integrity_context

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


def _build_legacy_analysis_result(
    raw_results: Dict[str, Any],
    *,
    method_id: str,
    engine: Optional[str] = None,
    conclusion: str = "",
    adjusted_p_value: Optional[float] = None,
    significant_adj: Optional[bool] = None,
) -> AnalysisResult:
    normalized = normalize_analysis_result_v2(
        raw_results,
        method_id=method_id,
        config={"engine": engine} if engine else {},
    )
    resolved_method_id = str(normalized.get("method_id") or method_id or "").strip() or "unknown"
    method_info = get_method(resolved_method_id) or get_method(str(method_id or "").strip())
    if method_info is None:
        method_info = {
            "id": resolved_method_id,
            "name": resolved_method_id.replace("_", " ").title(),
            "description": "Legacy shim statistical method",
            "type": "parametric",
            "min_groups": 1,
            "max_groups": 100,
        }

    significant_raw = raw_results.get("significant")
    significant = bool(significant_raw) if significant_raw is not None else False

    return AnalysisResult(
        method=method_info,
        method_id=resolved_method_id,
        engine=str(normalized.get("engine") or "python"),
        p_value=normalized.get("p_value"),
        effect_size=normalized.get("effect_size"),
        effect_size_name=raw_results.get("effect_size_name"),
        effect_size_ci_lower=raw_results.get("effect_size_ci_lower") or raw_results.get("effect_ci_lower"),
        effect_size_ci_upper=raw_results.get("effect_size_ci_upper") or raw_results.get("effect_ci_upper"),
        power=raw_results.get("power"),
        bf10=raw_results.get("bf10"),
        stat_value=normalized.get("stat_value"),
        significant=significant,
        adjusted_p_value=adjusted_p_value if adjusted_p_value is not None else raw_results.get("p_value_adj"),
        significant_adj=significant_adj if significant_adj is not None else raw_results.get("significant_adj"),
        diagnostics=normalized.get("diagnostics") if isinstance(normalized.get("diagnostics"), dict) else {},
        warnings=normalized.get("warnings") if isinstance(normalized.get("warnings"), list) else [],
        plots=normalized.get("plots") if isinstance(normalized.get("plots"), list) else [],
        groups=raw_results.get("groups"),
        plot_data=raw_results.get("plot_data"),
        plot_stats=raw_results.get("plot_stats"),
        conclusion=conclusion,
    )


def _legacy_result_conclusion(raw_results: Dict[str, Any]) -> str:
    significant = bool(raw_results.get("significant"))
    p_value = raw_results.get("p_value")
    try:
        p_text = f"{float(p_value):.4f}" if p_value is not None else "н/д"
    except Exception:
        p_text = "н/д"
    prefix = "Обнаружено статистически значимое различие" if significant else "Статистически значимых различий не обнаружено"
    return f"{prefix} (p={p_text})."


def _enrich_run_data_for_report(run_data: Any, dataset_id: str, run_id: str) -> Any:
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


class ExportDocxRequest(BaseModel):
    results: Dict[str, Any]
    dataset_id: Optional[str] = None
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
    normality_test = str(config.get("normality_test") or "shapiro").strip().lower()
    normality_decision = str(config.get("normality_decision") or "majority").strip().lower()
    homogeneity_test = str(config.get("homogeneity_test") or "levene").strip().lower()
    homogeneity_center = str(config.get("homogeneity_center") or "median").strip().lower()

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

    if method_id in {"pearson", "spearman", "kendall", "clustered_correlation"}:
        if len(targets) < 2:
            return {"alpha": alpha, "method_id": method_id, "shapiro_p": None, "levene_p": None}

        col_a, col_b = targets[0], targets[1]
        if col_a not in df.columns or col_b not in df.columns:
            raise HTTPException(status_code=400, detail="Выбранные столбцы не найдены")

        a = pd.to_numeric(df[col_a], errors="coerce").tolist()
        b = pd.to_numeric(df[col_b], errors="coerce").tolist()
        norm_a = check_normality_profile(a, alpha=alpha, method=normality_test, decision=normality_decision)
        norm_b = check_normality_profile(b, alpha=alpha, method=normality_test, decision=normality_decision)
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
        res = check_normality_profile(values, alpha=alpha, method=normality_test, decision=normality_decision)
        normality[str(g)] = res
        if res.get("p") is not None:
            per_group_p.append(res.get("p"))

    shapiro_p = min(per_group_p) if per_group_p else None
    homogeneity = check_homogeneity_profile(
        data_groups,
        alpha=alpha,
        method=homogeneity_test,
        center=homogeneity_center,
    )
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
    logger.warning(
        "Deprecated endpoint hit: /api/v1/analysis/design. Use /api/v1/v2/analysis/plan for canonical flow."
    )
    record_legacy_hit("/api/v1/analysis/design")
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

        variables = req.variables if isinstance(req.variables, dict) else {}
        meta = _load_dataset_meta(req.dataset_id)
        dataset_title = str(meta.get("original_filename") or meta.get("filename") or "").strip()
        if dataset_title and not variables.get("dataset_title"):
            variables = dict(variables)
            variables["dataset_title"] = dataset_title

        # 2. Generate Protocol
        designer = StudyDesignEngine()
        protocol = designer.suggest_protocol(req.goal, variables, metadata, template_id=req.template_id)
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
        return normalize_run_data_results(res)
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


def _normalize_summary_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None
    discussion = payload.get("discussion")
    conclusion = payload.get("conclusion") or payload.get("conclusions")

    def _norm(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
        if isinstance(value, (str, int, float)):
            s = str(value).strip()
            return [s] if s else []
        return []

    discussion_out = _norm(discussion)
    conclusion_out = _norm(conclusion)
    if not discussion_out and not conclusion_out:
        return None

    out = dict(payload)
    out["discussion"] = discussion_out
    out["conclusion"] = conclusion_out
    return out


async def _load_report_summary(dataset_id: str, run_id: str) -> Optional[Dict[str, Any]]:
    try:
        raw = await _run_in_threadpool_with_timeout(
            lambda: pipeline.read_run_artifact(dataset_id, run_id, "report_summary.json"),
            8.0,
            "",
        )
        if not raw:
            return None
        data = json.loads(raw.decode("utf-8", errors="replace"))
        return _normalize_summary_payload(data)
    except Exception:
        return None


async def _save_report_summary(dataset_id: str, run_id: str, summary: Dict[str, Any]) -> None:
    try:
        payload = json.dumps(summary, ensure_ascii=False).encode("utf-8")
        await _run_in_threadpool_with_timeout(
            lambda: pipeline.save_run_artifact(pipeline.get_run_dir(dataset_id, run_id), "report_summary.json", payload),
            8.0,
            "",
        )
    except Exception:
        pass


def _extract_llm_models(run_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(run_data, dict):
        return None
    candidates = []
    globals_data = run_data.get("globals")
    if isinstance(globals_data, dict):
        candidates.append(globals_data)
    protocol = run_data.get("protocol")
    if isinstance(protocol, dict):
        candidates.append(protocol)
        proto_globals = protocol.get("globals")
        if isinstance(proto_globals, dict):
            candidates.append(proto_globals)
    for item in candidates:
        models = item.get("llm_models") or item.get("role_models")
        if isinstance(models, dict) and models:
            return models
    return None


async def _attach_report_summary(run_data: Dict[str, Any], dataset_id: str, run_id: str, style: Optional[str]) -> Dict[str, Any]:
    if not isinstance(run_data, dict):
        return run_data

    lang = "ru" if str(style or "").strip().lower() in {"gost"} else "en"

    existing = _normalize_summary_payload(run_data.get("report_summary") if isinstance(run_data.get("report_summary"), dict) else None)
    if existing:
        summary_lang = existing.get("language")
        if summary_lang and str(summary_lang).lower() != lang:
            existing = None
        else:
            run_data = dict(run_data)
            run_data["report_summary"] = existing
            return run_data

    cached = await _load_report_summary(dataset_id, run_id)
    if cached:
        summary_lang = cached.get("language")
        if summary_lang and str(summary_lang).lower() != lang:
            cached = None
        else:
            run_data = dict(run_data)
            run_data["report_summary"] = cached
            return run_data

    findings = _extract_protocol_findings(run_data)
    role_models = _extract_llm_models(run_data)
    summary = await generate_protocol_summary(
        findings,
        language=lang,
        max_items=12,
        max_tokens=480,
        role_models=role_models,
    )
    normalized = _normalize_summary_payload(summary)
    if normalized:
        run_data = dict(run_data)
        run_data["report_summary"] = normalized
        await _save_report_summary(dataset_id, run_id, normalized)
    return run_data


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


def _check_study_design_ready(dataset_id: str) -> Tuple[bool, str]:
    dataset_id = str(dataset_id or "").strip()
    if not dataset_id:
        return False, "dataset_id missing"
    try:
        ds_dir = pipeline.get_dataset_dir(dataset_id)
    except Exception:
        return False, "dataset directory unavailable"
    study_path = os.path.join(ds_dir, "processed", "study_design.json")
    if not os.path.exists(study_path):
        return False, "study_design.json not found"
    try:
        with open(study_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return False, "study_design.json unreadable"
    if not isinstance(payload, dict):
        return False, "study_design.json invalid structure"
    design = payload.get("design")
    if not isinstance(design, dict) or not design:
        return False, "design section missing"
    return True, ""


def _enforce_report_design_gate(dataset_id: str) -> None:
    if not bool(getattr(settings, "CLINIMETRIA_REPORT_HARD_GATE_DESIGN", True)):
        return
    ok, reason = _check_study_design_ready(dataset_id)
    if ok:
        return
    raise HTTPException(
        status_code=409,
        detail=f"Экспорт отчёта заблокирован: дизайн исследования не подтверждён ({reason}).",
    )


def _check_report_methods_ready(run_data: Any) -> Tuple[bool, str]:
    if not isinstance(run_data, dict):
        return False, "results.json unavailable"

    findings = _extract_protocol_findings(run_data)
    items = findings.get("items") if isinstance(findings.get("items"), list) else []
    if not items:
        return False, "results section has no analyzable steps"

    missing_steps: List[str] = []
    placeholder_methods = {"unknown", "statistical test", "статистический тест"}
    method_optional_types = {"table_1", "descriptive", "batch_compare_by_factor"}
    inferential_types = {
        "compare",
        "hypothesis_test",
        "correlation",
        "regression",
        "survival",
        "mixed_effects",
        "clustered_correlation",
        "batch_analysis",
        "timepoint_batch_analysis",
        "delta_batch_analysis",
        "responders",
        "agreement",
        "time_series",
    }
    for item in items:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        method_raw = item.get("method")
        method = str(method_raw).strip() if method_raw is not None else ""
        if item_type in method_optional_types and not method:
            continue
        if method and method.lower() not in placeholder_methods:
            continue
        p_value = item.get("p_value")
        inferential = item_type in inferential_types or p_value is not None
        if not inferential:
            continue
        step_id = item.get("step_id")
        if isinstance(step_id, str) and step_id.strip():
            missing_steps.append(step_id.strip())
        else:
            missing_steps.append("unknown_step")

    if missing_steps:
        uniq = list(dict.fromkeys(missing_steps))
        preview = ", ".join(uniq[:6])
        if len(uniq) > 6:
            preview += ", ..."
        return False, f"method metadata missing for steps: {preview}"
    return True, ""


def _enforce_report_methods_gate(dataset_id: str, run_id: str) -> None:
    if not bool(getattr(settings, "CLINIMETRIA_REPORT_HARD_GATE_METHODS", True)):
        return

    try:
        run_data = pipeline.get_run_results(dataset_id, run_id)
    except Exception as e:
        raise HTTPException(
            status_code=409,
            detail=f"Экспорт отчёта заблокирован: не удалось прочитать результаты ({e}).",
        )

    ok, reason = _check_report_methods_ready(run_data)
    if ok:
        return
    raise HTTPException(
        status_code=409,
        detail=f"Экспорт отчёта заблокирован: секция Methods неполная ({reason}).",
    )


def _check_report_verification_ready(run_data: Any) -> Tuple[bool, str]:
    context = build_report_integrity_context(run_data)
    verification = context.get("verification") if isinstance(context.get("verification"), dict) else {}
    present = bool(verification.get("present"))
    if not present:
        return False, "verification.json missing in run payload"

    status = str(verification.get("status") or "").strip().lower()
    if status in {"passed", "ok"}:
        return True, ""

    failed_steps = verification.get("failed_steps")
    failed_steps = [str(x) for x in failed_steps if isinstance(x, str) and str(x).strip()] if isinstance(failed_steps, list) else []
    if failed_steps:
        preview = ", ".join(failed_steps[:6])
        if len(failed_steps) > 6:
            preview += ", ..."
        return False, f"verification status={status}; failed steps: {preview}"
    return False, f"verification status={status}"


def _enforce_report_verification_gate(dataset_id: str, run_id: str) -> None:
    if not bool(getattr(settings, "CLINIMETRIA_REPORT_HARD_GATE_VERIFICATION", False)):
        return

    try:
        run_data = pipeline.get_run_results(dataset_id, run_id)
    except Exception as e:
        raise HTTPException(
            status_code=409,
            detail=f"Экспорт отчёта заблокирован: не удалось прочитать результаты ({e}).",
        )

    ok, reason = _check_report_verification_ready(run_data)
    if ok:
        return
    raise HTTPException(
        status_code=409,
        detail=f"Экспорт отчёта заблокирован: верификация не пройдена ({reason}).",
    )


def _check_report_provenance_ready(
    dataset_id: str,
    run_id: str,
    run_data: Optional[Any] = None,
) -> Tuple[bool, str]:
    payload = run_data
    if payload is None:
        payload = pipeline.get_run_results(dataset_id, run_id)

    state_doc = pipeline.get_run_state(dataset_id, run_id)
    context = build_report_integrity_context(payload, run_state=state_doc)
    provenance = context.get("provenance") if isinstance(context.get("provenance"), dict) else {}

    reasons: List[str] = []
    if not bool(provenance.get("run_state_present")):
        reasons.append("run_state.json missing")
    else:
        state = str(provenance.get("state") or "").strip().lower()
        if state not in {"verify", "report", "release"}:
            reasons.append(f"run_state={state or 'unknown'}")
        missing_artifacts = provenance.get("missing_state_artifacts")
        if isinstance(missing_artifacts, list):
            missing = [str(x) for x in missing_artifacts if str(x).strip()]
            if missing:
                reasons.append(f"run_state missing artifacts: {', '.join(missing)}")

    if not bool(provenance.get("reproducibility_present")):
        reasons.append("reproducibility section missing")
    else:
        if not bool(provenance.get("reproducibility_ready")):
            reasons.append("reproducibility.ready is false")
        missing_fields = provenance.get("missing_reproducibility_fields")
        if isinstance(missing_fields, list):
            missing = [str(x) for x in missing_fields if str(x).strip()]
            if missing:
                reasons.append(f"reproducibility missing fields: {', '.join(missing)}")

    return (len(reasons) == 0, "; ".join(reasons))


def _enforce_report_provenance_gate(dataset_id: str, run_id: str) -> None:
    if not bool(getattr(settings, "CLINIMETRIA_REPORT_HARD_GATE_PROVENANCE", False)):
        return

    try:
        run_data = pipeline.get_run_results(dataset_id, run_id)
    except Exception as e:
        raise HTTPException(
            status_code=409,
            detail=f"Экспорт отчёта заблокирован: не удалось прочитать результаты ({e}).",
        )

    ok, reason = _check_report_provenance_ready(dataset_id, run_id, run_data=run_data)
    if ok:
        return
    raise HTTPException(
        status_code=409,
        detail=f"Экспорт отчёта заблокирован: provenance артефакты неполные ({reason}).",
    )


def _collect_run_artifact_names(dataset_id: str, run_id: str) -> List[str]:
    names: List[str] = []
    try:
        run_dir = pipeline.get_run_dir(dataset_id, run_id)
    except Exception:
        return names

    if not os.path.isdir(run_dir):
        return names

    for base_name in ["protocol.json", "results.json"]:
        path = os.path.join(run_dir, base_name)
        if os.path.isfile(path):
            names.append(base_name)

    artifacts_dir = os.path.join(run_dir, "artifacts")
    if os.path.isdir(artifacts_dir):
        for name in sorted(os.listdir(artifacts_dir)):
            if not name or name.startswith("."):
                continue
            path = os.path.join(artifacts_dir, name)
            if os.path.isfile(path):
                names.append(str(name))

    return names


def _hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _sha256_hex_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _release_reproduce_script_template() -> str:
    return """#!/usr/bin/env python3
\"\"\"Reproduce and verify Clinimetria release bundle.

Usage:
  python release/reproduce_run.py --bundle-dir .
  python release/reproduce_run.py --bundle-dir . --base-url http://127.0.0.1:8000/api/v1/v2 --reexecute
\"\"\"

import argparse
import hashlib
import json
import math
import pathlib
import urllib.request
import urllib.parse


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_bundle(bundle_dir: pathlib.Path) -> None:
    manifest_path = bundle_dir / "release" / "release_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files")
    if not isinstance(files, list):
        raise RuntimeError("Invalid manifest: files must be a list")

    checked = 0
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = row.get("path")
        sha = row.get("sha256")
        if not isinstance(rel, str) or not rel.strip():
            continue
        path = bundle_dir / rel
        if not path.exists():
            raise RuntimeError(f"Missing file from manifest: {rel}")
        if isinstance(sha, str) and sha.strip():
            real = _sha256(path)
            if real != sha:
                raise RuntimeError(f"Checksum mismatch: {rel}")
        checked += 1
    print(f"Manifest verification OK ({checked} files)")


def _safe_float(value):
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except Exception:
        return None


def _round_metric(value, ndigits=8):
    f = _safe_float(value)
    return round(f, ndigits) if f is not None else None


def _extract_step_map(payload):
    if not isinstance(payload, dict):
        return {}

    results = payload.get("results")
    if isinstance(results, dict):
        out = {}
        for sid, row in results.items():
            if isinstance(sid, str) and isinstance(row, dict):
                out[sid] = row
        if out:
            return out

    result_ir = payload.get("result_ir")
    if isinstance(result_ir, dict):
        blocks = result_ir.get("blocks")
        if isinstance(blocks, list):
            out = {}
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                sid = block.get("id")
                row = block.get("result")
                if not isinstance(row, dict):
                    row = block.get("payload")
                if isinstance(sid, str) and isinstance(row, dict):
                    out[sid] = row
            if out:
                return out

    return {}


def _load_run_results_payload(base_url, dataset_id, run_id):
    if not dataset_id or not run_id:
        return None
    root = base_url.rstrip("/")
    if root.endswith("/v2"):
        root = root[:-3]
    run_url = (
        root
        + "/analysis/run/"
        + urllib.parse.quote(str(run_id), safe="")
        + "?dataset_id="
        + urllib.parse.quote(str(dataset_id), safe="")
    )
    req = urllib.request.Request(run_url, method="GET")
    with urllib.request.urlopen(req, timeout=600) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body if isinstance(body, dict) else None


def _step_fingerprint(row):
    if not isinstance(row, dict):
        return {}
    return {
        "type": str(row.get("type") or ""),
        "p_value": _round_metric(row.get("p_value")),
        "p_value_adj": _round_metric(row.get("p_value_adj")),
        "effect_size": _round_metric(row.get("effect_size")),
        "stat_value": _round_metric(row.get("stat_value")),
        "n_obs": int(row.get("n_obs")) if isinstance(row.get("n_obs"), int) else None,
    }


def compare_results(bundle_dir: pathlib.Path, reproduced_payload):
    base_results_path = bundle_dir / "run" / "results.json"
    if not base_results_path.exists():
        raise RuntimeError(f"Missing bundled results: {base_results_path}")

    bundled = json.loads(base_results_path.read_text(encoding="utf-8"))
    bundled_steps = _extract_step_map(bundled)
    reproduced_steps = _extract_step_map(reproduced_payload if isinstance(reproduced_payload, dict) else {})

    bundled_ids = set(bundled_steps.keys())
    reproduced_ids = set(reproduced_steps.keys())
    missing_ids = sorted(list(bundled_ids - reproduced_ids))
    extra_ids = sorted(list(reproduced_ids - bundled_ids))

    value_mismatch = []
    for sid in sorted(list(bundled_ids & reproduced_ids)):
        fp_a = _step_fingerprint(bundled_steps.get(sid))
        fp_b = _step_fingerprint(reproduced_steps.get(sid))
        if fp_a != fp_b:
            value_mismatch.append(sid)

    summary = {
        "bundled_steps": len(bundled_ids),
        "reproduced_steps": len(reproduced_ids),
        "missing_step_ids": missing_ids[:25],
        "extra_step_ids": extra_ids[:25],
        "value_mismatch_step_ids": value_mismatch[:25],
        "missing_count": len(missing_ids),
        "extra_count": len(extra_ids),
        "value_mismatch_count": len(value_mismatch),
    }
    summary["mismatch_count"] = (
        summary["missing_count"] + summary["extra_count"] + summary["value_mismatch_count"]
    )
    return summary


def reexecute(bundle_dir: pathlib.Path, base_url: str, output_path: pathlib.Path, compare: bool):
    payload_path = bundle_dir / "release" / "reproduce_payload.json"
    if not payload_path.exists():
        raise RuntimeError(f"Missing payload: {payload_path}")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    url = base_url.rstrip("/") + "/analysis/execute"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved reproduce response: {output_path}")
    print(f"run_id={result.get('run_id')}")
    if not compare:
        return None

    compare_payload = result if isinstance(result, dict) else {}
    if not _extract_step_map(compare_payload):
        run_id = compare_payload.get("run_id") if isinstance(compare_payload, dict) else None
        dataset_id = payload.get("dataset_id") if isinstance(payload, dict) else None
        if run_id and dataset_id:
            try:
                loaded = _load_run_results_payload(base_url, dataset_id, run_id)
                if isinstance(loaded, dict):
                    compare_payload = loaded
                    print("Loaded run results for comparison via /analysis/run endpoint")
            except Exception as e:
                print(f"Warning: failed to load run results for comparison: {e}")

    summary = compare_results(bundle_dir, compare_payload)
    print("Comparison summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", default=".", help="Path to unpacked release bundle root")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1/v2", help="StatProject v2 API base URL")
    parser.add_argument("--output", default="release/reproduce_response.json", help="Path to store reproduce response JSON")
    parser.add_argument("--reexecute", action="store_true", help="POST payload to API after local integrity verification")
    compare_group = parser.add_mutually_exclusive_group()
    compare_group.add_argument(
        "--compare-results",
        dest="compare_results",
        action="store_true",
        help="Compare reproduced response with bundled run/results.json",
    )
    compare_group.add_argument(
        "--no-compare-results",
        dest="compare_results",
        action="store_false",
        help="Skip comparison with bundled run/results.json",
    )
    parser.set_defaults(compare_results=True)
    parser.add_argument(
        "--strict-compare",
        action="store_true",
        help="Fail with non-zero exit code if comparison finds mismatches",
    )
    args = parser.parse_args()

    bundle_dir = pathlib.Path(args.bundle_dir).resolve()
    verify_bundle(bundle_dir)
    if args.reexecute:
        output_path = (bundle_dir / args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        summary = reexecute(bundle_dir, args.base_url, output_path, compare=bool(args.compare_results))
        if bool(args.strict_compare) and isinstance(summary, dict) and int(summary.get("mismatch_count") or 0) > 0:
            raise RuntimeError("Strict comparison failed: reproduced response differs from bundled results")


if __name__ == "__main__":
    main()
"""


def _build_release_generated_assets(dataset_id: str, run_id: str, protocol: Dict[str, Any]) -> Dict[str, bytes]:
    protocol_payload = protocol if isinstance(protocol, dict) else {}
    protocol_steps = (
        protocol_payload.get("steps")
        if isinstance(protocol_payload.get("steps"), list)
        else []
    )
    protocol_name = str(protocol_payload.get("name") or protocol_payload.get("protocol_name") or "Protocol").strip() or "Protocol"
    alpha_raw = protocol_payload.get("alpha")
    try:
        alpha_value = float(alpha_raw)
    except Exception:
        alpha_value = 0.05
    globals_payload = (
        protocol_payload.get("globals")
        if isinstance(protocol_payload.get("globals"), dict)
        else {}
    )

    reproduce_payload = {
        "dataset_id": dataset_id,
        "protocol_name": protocol_name,
        "alpha": alpha_value,
        "globals": globals_payload,
        "protocol": protocol_steps,
    }

    readme = (
        "# Clinimetria Release Bundle\n\n"
        "Содержимое:\n"
        "- `run/` — protocol/results/run-state и артефакты запуска\n"
        "- `dataset/` — исходные и обработанные данные\n"
        "- `release/release_manifest.json` — контрольные sha256-хэши\n"
        "- `release/reproduce_run.py` — проверка целостности + опциональный re-execute + сравнение результатов\n\n"
        "Быстрый старт:\n"
        "1. `python release/reproduce_run.py --bundle-dir .`\n"
        "2. Для повторного запуска через локальный API:\n"
        "   `python release/reproduce_run.py --bundle-dir . --reexecute --base-url http://127.0.0.1:8000/api/v1/v2`\n"
        "3. Строгая проверка совпадения с fail-fast:\n"
        "   `python release/reproduce_run.py --bundle-dir . --reexecute --strict-compare`\n"
    )

    shell_script = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "python3 \"$(dirname \"$0\")/reproduce_run.py\" --bundle-dir \"$(cd \"$(dirname \"$0\")/..\" && pwd)\" \"$@\"\n"
    )

    return {
        os.path.join("release", "README.md"): readme.encode("utf-8"),
        os.path.join("release", "reproduce_payload.json"): json.dumps(
            reproduce_payload, ensure_ascii=False, indent=2
        ).encode("utf-8"),
        os.path.join("release", "reproduce_run.py"): _release_reproduce_script_template().encode("utf-8"),
        os.path.join("release", "reproduce_run.sh"): shell_script.encode("utf-8"),
    }


def _build_protocol_release_bundle(dataset_id: str, run_id: str) -> Tuple[bytes, Dict[str, Any]]:
    run_dir = pipeline.get_run_dir(dataset_id, run_id)
    if not os.path.isdir(run_dir):
        raise FileNotFoundError("run directory not found")

    dataset_dir = pipeline.get_dataset_dir(dataset_id)
    processed_dir = os.path.join(dataset_dir, "processed")
    source_dir = os.path.join(dataset_dir, "source")
    artifacts_dir = os.path.join(run_dir, "artifacts")

    entries: List[Tuple[str, str]] = []

    def _queue(src: str, arc: str) -> None:
        if not os.path.isfile(src):
            return
        entries.append((src, arc))

    protocol_payload: Dict[str, Any] = {}
    for name in ["protocol.json", "results.json", "run_state.json"]:
        _queue(os.path.join(run_dir, name), os.path.join("run", name))
        if name == "protocol.json":
            path = os.path.join(run_dir, name)
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        parsed = json.load(f)
                    if isinstance(parsed, dict):
                        protocol_payload = parsed
                except Exception:
                    protocol_payload = {}

    if os.path.isdir(artifacts_dir):
        for name in sorted(os.listdir(artifacts_dir)):
            if not name or name.startswith("."):
                continue
            if name.startswith("release_bundle_") and name.endswith(".zip"):
                continue
            _queue(os.path.join(artifacts_dir, name), os.path.join("run", "artifacts", name))

    if os.path.isdir(source_dir):
        for name in sorted(os.listdir(source_dir)):
            if not name or name.startswith("."):
                continue
            _queue(os.path.join(source_dir, name), os.path.join("dataset", "source", name))

    if os.path.isdir(processed_dir):
        for name in [
            f"{dataset_id}.parquet",
            "dtypes.json",
            "scan_report.json",
            "cleaning_log.json",
            "profile.json",
            "data_contract.json",
            "cleaning_plan.json",
            "data_lineage.json",
            "study_design.json",
            "analysis_set_hash.json",
            "analysis_set_current.json",
        ]:
            _queue(os.path.join(processed_dir, name), os.path.join("dataset", "processed", name))

        pointer_path = os.path.join(processed_dir, "analysis_set_current.json")
        if os.path.isfile(pointer_path):
            try:
                with open(pointer_path, "r", encoding="utf-8") as f:
                    pointer_payload = json.load(f)
                if isinstance(pointer_payload, dict):
                    set_id = pointer_payload.get("analysis_set_id")
                    if isinstance(set_id, str) and set_id.strip():
                        set_safe = set_id.strip()
                        set_name = f"{set_safe}.json"
                        _queue(
                            os.path.join(processed_dir, "analysis_sets", set_name),
                            os.path.join("dataset", "processed", "analysis_sets", set_name),
                        )
                        set_parquet = f"{set_safe}.parquet"
                        _queue(
                            os.path.join(processed_dir, "analysis_sets", set_parquet),
                            os.path.join("dataset", "processed", "analysis_sets", set_parquet),
                        )
            except Exception:
                pass

    file_rows: List[Dict[str, Any]] = []
    generated_assets = _build_release_generated_assets(dataset_id, run_id, protocol_payload)
    with io.BytesIO() as bio:
        with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for src, arc in entries:
                archive.write(src, arc)
                st = os.stat(src)
                file_rows.append(
                    {
                        "path": arc,
                        "size_bytes": int(st.st_size),
                        "sha256": _hash_file(src),
                        "updated_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    }
                )

            for arc, content in generated_assets.items():
                archive.writestr(arc, content)
                file_rows.append(
                    {
                        "path": arc,
                        "size_bytes": int(len(content)),
                        "sha256": _sha256_hex_bytes(content),
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                        "source": "generated",
                    }
                )

            manifest = {
                "schema": "clinimetria.release_bundle",
                "version": 1,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "dataset_id": dataset_id,
                "run_id": run_id,
                "files": file_rows,
                "file_count": len(file_rows),
                "entrypoint": os.path.join("release", "reproduce_run.sh"),
                "reproduce_payload": os.path.join("release", "reproduce_payload.json"),
            }
            archive.writestr(
                os.path.join("release", "release_manifest.json"),
                json.dumps(manifest, ensure_ascii=False, indent=2),
            )

        bundle_bytes = bio.getvalue()

    return bundle_bytes, manifest


def _evaluate_report_quality(
    run_data: Any,
    *,
    dataset_id: str,
    run_id: str,
    report_html: str,
    artifact_names: List[str],
    require_exports: bool,
    require_reproducibility: bool,
    require_verification: bool,
    require_provenance: bool,
) -> Dict[str, Any]:
    design_ok, design_reason = _check_study_design_ready(dataset_id)
    methods_ok, methods_reason = _check_report_methods_ready(run_data)
    verification_ok, verification_reason = _check_report_verification_ready(run_data)
    provenance_ok, provenance_reason = _check_report_provenance_ready(dataset_id, run_id, run_data=run_data)

    html_lower = str(report_html or "").lower()
    section_ids = ["design", "methods", "results", "discussion", "limitations"]
    section_checks: Dict[str, bool] = {}
    for sid in section_ids:
        section_checks[sid] = (f'id="{sid}"' in html_lower)
    sections_ok = all(bool(v) for v in section_checks.values())

    artifacts_set = set([str(x) for x in artifact_names if isinstance(x, str)])
    dataset_artifacts_required = [
        "analysis_dataset.parquet",
        "analysis_dataset.xlsx",
        "analysis_dataset.meta.json",
    ]
    dataset_artifacts_missing = [name for name in dataset_artifacts_required if name not in artifacts_set]
    dataset_artifacts_ok = not dataset_artifacts_missing

    reproducibility_required = [
        "reproduce_run.py",
        "reproduce_payload.json",
        "protocol_resolved.json",
        "reproducibility_manifest.json",
        "protocol_report_auto.html",
    ]
    reproducibility_missing = [name for name in reproducibility_required if name not in artifacts_set]
    reproducibility_ok = not reproducibility_missing

    export_presence = {
        "html": any(name.endswith(".html") and "protocol_report" in name for name in artifacts_set),
        "pdf": any(name.endswith(".pdf") and "protocol_report" in name for name in artifacts_set),
        "docx": any(name.endswith(".docx") and "protocol_report" in name for name in artifacts_set),
    }
    exports_ok = all(export_presence.values()) if require_exports else True

    checks = {
        "design_artifact": {"ok": design_ok, "reason": "" if design_ok else design_reason},
        "methods_metadata": {"ok": methods_ok, "reason": "" if methods_ok else methods_reason},
        "sections": {
            "ok": sections_ok,
            "required": section_checks,
        },
        "analysis_dataset_artifacts": {
            "ok": dataset_artifacts_ok,
            "missing": dataset_artifacts_missing,
        },
        "verification_gate": {
            "ok": verification_ok,
            "required": require_verification,
            "reason": "" if verification_ok else verification_reason,
        },
        "provenance_trace": {
            "ok": provenance_ok,
            "required": require_provenance,
            "reason": "" if provenance_ok else provenance_reason,
        },
        "reproducibility_artifacts": {
            "ok": reproducibility_ok,
            "required": require_reproducibility,
            "missing": reproducibility_missing,
        },
        "report_exports": {
            "ok": exports_ok,
            "required": require_exports,
            "present": export_presence,
        },
    }

    missing: List[str] = []
    if not design_ok:
        missing.append("design_artifact")
    if not methods_ok:
        missing.append("methods_metadata")
    if not sections_ok:
        missing.extend([f"section:{sid}" for sid, ok in section_checks.items() if not ok])
    if not dataset_artifacts_ok:
        missing.extend([f"artifact:{name}" for name in dataset_artifacts_missing])
    if require_verification and not verification_ok:
        missing.append("verification_gate")
    if require_provenance and not provenance_ok:
        missing.append("provenance_trace")
    if require_reproducibility and not reproducibility_ok:
        missing.extend([f"artifact:{name}" for name in reproducibility_missing])
    if require_exports and not all(export_presence.values()):
        missing.extend([f"export:{ext}" for ext, ok in export_presence.items() if not ok])

    ready = len(missing) == 0
    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "pass" if ready else "fail",
        "ready": ready,
        "missing": missing,
        "checks": checks,
        "artifacts_seen": sorted(list(artifacts_set)),
    }


@router.get("/protocol/report/{run_id}/quality")
async def get_protocol_report_quality(
    run_id: str,
    dataset_id: str,
    require_exports: bool = False,
    require_reproducibility: bool = False,
    require_verification: bool = False,
    require_provenance: bool = False,
    style: Optional[str] = None,
):
    """
    Returns a manuscript-ready quality checklist for a protocol run report.
    """
    try:
        res = await _run_in_threadpool_with_timeout(
            lambda: pipeline.get_run_results(dataset_id, run_id),
            60.0,
            "Получение результатов протокола занимает слишком много времени",
        )
        if not res:
            raise HTTPException(status_code=404, detail="Результаты не найдены")

        res = normalize_run_data_results(res)
        res = await _attach_report_summary(res, dataset_id, run_id, style)
        report_html = await _run_in_threadpool_with_timeout(
            lambda: render_protocol_report(
                res,
                dataset_name=f"Файл данных {dataset_id[:5]}...",
                style=style,
            ),
            60.0,
            "Оценка качества отчёта занимает слишком много времени",
        )
        artifact_names = await _run_in_threadpool_with_timeout(
            lambda: _collect_run_artifact_names(dataset_id, run_id),
            10.0,
            "",
        )
        require_verification_gate = bool(require_verification) or bool(
            getattr(settings, "CLINIMETRIA_REPORT_HARD_GATE_VERIFICATION", False)
        )
        require_provenance_gate = bool(require_provenance) or bool(
            getattr(settings, "CLINIMETRIA_REPORT_HARD_GATE_PROVENANCE", False)
        )
        quality_payload = _evaluate_report_quality(
            res,
            dataset_id=dataset_id,
            run_id=run_id,
            report_html=report_html,
            artifact_names=artifact_names,
            require_exports=bool(require_exports),
            require_reproducibility=bool(require_reproducibility),
            require_verification=require_verification_gate,
            require_provenance=require_provenance_gate,
        )
        try:
            await _run_in_threadpool_with_timeout(
                lambda: pipeline.save_run_artifact(
                    pipeline.get_run_dir(dataset_id, run_id),
                    "report_quality.json",
                    json.dumps(quality_payload, ensure_ascii=False).encode("utf-8"),
                ),
                10.0,
                "",
            )
        except Exception:
            pass
        return quality_payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось оценить качество отчёта: {str(e)}")

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
    
    try:
        _enforce_report_design_gate(dataset_id)
        _enforce_report_methods_gate(dataset_id, run_id)
        _enforce_report_verification_gate(dataset_id, run_id)
        _enforce_report_provenance_gate(dataset_id, run_id)
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

        res = normalize_run_data_results(res)
        res = _apply_report_customization(res, sections, order)
        res = _enrich_run_data_for_report(res, dataset_id, run_id)
        res = await _attach_report_summary(res, dataset_id, run_id, style)

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

    try:
        _enforce_report_design_gate(dataset_id)
        _enforce_report_methods_gate(dataset_id, run_id)
        _enforce_report_verification_gate(dataset_id, run_id)
        _enforce_report_provenance_gate(dataset_id, run_id)
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

        res = normalize_run_data_results(res)
        res = _apply_report_customization(res, sections, order)
        res = _enrich_run_data_for_report(res, dataset_id, run_id)
        res = await _attach_report_summary(res, dataset_id, run_id, style)

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

    try:
        _enforce_report_design_gate(dataset_id)
        _enforce_report_methods_gate(dataset_id, run_id)
        _enforce_report_verification_gate(dataset_id, run_id)
        _enforce_report_provenance_gate(dataset_id, run_id)
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

        res = normalize_run_data_results(res)
        res = _apply_report_customization(res, sections, order)
        res = _enrich_run_data_for_report(res, dataset_id, run_id)
        res = await _attach_report_summary(res, dataset_id, run_id, style)

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


@router.get("/protocol/release/{run_id}/zip")
async def download_protocol_release_bundle(
    run_id: str,
    dataset_id: str,
    allow_partial: bool = False,
    refresh: bool = False,
):
    from fastapi.responses import Response

    try:
        run_data = await _run_in_threadpool_with_timeout(
            lambda: pipeline.get_run_results(dataset_id, run_id),
            60.0,
            "Получение результатов протокола занимает слишком много времени",
        )
        if not isinstance(run_data, dict):
            raise HTTPException(status_code=404, detail="Результаты запуска не найдены")

        if not bool(allow_partial):
            ok_verification, reason_verification = _check_report_verification_ready(run_data)
            if not ok_verification:
                raise HTTPException(
                    status_code=409,
                    detail=f"Release bundle заблокирован: верификация не пройдена ({reason_verification}).",
                )
            ok_provenance, reason_provenance = _check_report_provenance_ready(
                dataset_id,
                run_id,
                run_data=run_data,
            )
            if not ok_provenance:
                raise HTTPException(
                    status_code=409,
                    detail=f"Release bundle заблокирован: provenance неполный ({reason_provenance}).",
                )

        artifact_name = f"release_bundle_{run_id}.zip"
        if not bool(refresh):
            try:
                cached = await _run_in_threadpool_with_timeout(
                    lambda: pipeline.read_run_artifact(dataset_id, run_id, artifact_name),
                    20.0,
                    "",
                )
                filename = f"release_bundle_{run_id}.zip"
                return Response(
                    content=cached,
                    media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                )
            except Exception:
                pass

        bundle_bytes, manifest = await _run_in_threadpool_with_timeout(
            lambda: _build_protocol_release_bundle(dataset_id, run_id),
            240.0,
            "Сборка release bundle занимает слишком много времени",
        )

        run_dir = pipeline.get_run_dir(dataset_id, run_id)
        try:
            await _run_in_threadpool_with_timeout(
                lambda: pipeline.save_run_artifact(run_dir, artifact_name, bundle_bytes),
                20.0,
                "",
            )
            await _run_in_threadpool_with_timeout(
                lambda: pipeline.save_run_artifact(
                    run_dir,
                    "release_manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
                ),
                20.0,
                "",
            )
        except Exception:
            pass

        filename = f"release_bundle_{run_id}.zip"
        return Response(
            content=bundle_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Не удалось сформировать release bundle: запуск не найден")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать release bundle: {str(e)}")


@router.post("/export/docx")
async def export_docx(request: ExportDocxRequest):
    from fastapi.responses import StreamingResponse

    try:
        dataset_id = str(request.dataset_id or request.results.get("dataset_id") or "").strip()
        if not dataset_id:
            raise HTTPException(status_code=400, detail="dataset_id обязателен для экспорта DOCX")
        _enforce_report_design_gate(dataset_id)
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
            lambda: protocol_engine.execute_protocol(
                request.dataset_id,
                df,
                request.protocol,
                alpha=request.alpha,
                engine=request.engine,
            ),
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
        results = run_analysis(
            df,
            method_id,
            col_a,
            col_b,
            is_paired=request.is_paired,
            engine=request.engine,
        )
        return _build_legacy_analysis_result(
            results,
            method_id=method_id,
            engine=request.engine,
            conclusion="",
        )
    
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
        _enforce_report_design_gate(dataset_id)
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
        
    analysis_result = _build_legacy_analysis_result(
        res,
        method_id=method_id,
        engine="python",
        conclusion=_legacy_result_conclusion(res),
    )

    # 5. Enhace with AI (Async)
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
        _enforce_report_design_gate(dataset_id)
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

    analysis_result = _build_legacy_analysis_result(
        res,
        method_id=method_id,
        engine="python",
        conclusion=_legacy_result_conclusion(res),
    )

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

    _enforce_report_design_gate(req.dataset_id)
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
    from app.schemas.analysis import DescriptiveStat, BatchAnalysisResponse
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

                p_value_raw = res.get("p_value")
                try:
                    conclusion = f"p={float(p_value_raw):.4f}" if p_value_raw is not None else "p=н/д"
                except Exception:
                    conclusion = "p=н/д"

                result_obj = _build_legacy_analysis_result(
                    res,
                    method_id=method_id,
                    engine="python",
                    conclusion=conclusion,
                    adjusted_p_value=res.get("p_value_adj"),
                    significant_adj=res.get("significant_adj"),
                )
                
                results[col] = result_obj
                
            except Exception as e:
                logger.error(f"Batch analysis failed for {col}: {e}", exc_info=True)
                pass
        return results
    
    results = await run_in_threadpool(run_tests_sync)

    return BatchAnalysisResponse(descriptives=descriptives, results=results)


# Protocol Templates
class ProtocolTemplateSave(BaseModel):
    name: str
    protocol: Dict[str, Any]

TEMPLATES_DIR = os.path.join(WORKSPACE_DIR, "templates", "protocols")
os.makedirs(TEMPLATES_DIR, exist_ok=True)

@router.post("/protocols/save")
def save_protocol_template(req: ProtocolTemplateSave):
    safe_name = "".join([c for c in req.name if c.isalnum() or c in (' ', '-', '_')]).strip()
    if not safe_name:
        raise HTTPException(400, "Invalid name")
    
    path = os.path.join(TEMPLATES_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "name": req.name,
            "protocol": req.protocol,
            "created_at": datetime.now().isoformat()
        }, f, indent=2)
    return {"status": "ok", "name": safe_name}

@router.get("/protocols/list")
def list_protocol_templates():
    if not os.path.exists(TEMPLATES_DIR):
        return []
    res = []
    for f in os.listdir(TEMPLATES_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(TEMPLATES_DIR, f), "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    res.append({
                        "name": data.get("name", f.replace(".json", "")),
                        "steps_count": len(data.get("protocol", {}).get("steps", [])),
                        "created_at": data.get("created_at")
                    })
            except:
                pass
    return sorted(res, key=lambda x: x.get("created_at", ""), reverse=True)

@router.get("/protocols/{name}")
def get_protocol_template(name: str):
    safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
    path = os.path.join(TEMPLATES_DIR, f"{safe_name}.json")
    if not os.path.exists(path):
        raise HTTPException(404, "Template not found")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data
