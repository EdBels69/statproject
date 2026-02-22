
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import os
import mimetypes
import hashlib
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
from app.modules.interpretation_contract import (
    is_interpretation_contract_complete,
    is_inferential_payload as is_inferential_interpretation_payload,
)
from app.core.logging import logger
from app.core.config import settings
from app.llm import generate_protocol_summary

from app.api.datasets import DATA_DIR, WORKSPACE_DIR, _load_dataset_meta

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


def _load_study_design_payload(dataset_id: str) -> Dict[str, Any]:
    try:
        ds_dir = pipeline.get_dataset_dir(str(dataset_id))
    except Exception:
        return {}
    study_path = os.path.join(ds_dir, "processed", "study_design.json")
    if not os.path.exists(study_path):
        return {}
    try:
        with open(study_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _infer_publication_mode(run_data: Dict[str, Any]) -> bool:
    if not isinstance(run_data, dict):
        return False
    if bool(run_data.get("publication_mode")):
        return True
    mode = ""
    globals_in = run_data.get("globals") if isinstance(run_data.get("globals"), dict) else {}
    if isinstance(globals_in, dict):
        mode = str(globals_in.get("analysis_mode") or globals_in.get("mode") or "").strip().lower()
    if not mode:
        mode = str(run_data.get("analysis_mode") or "").strip().lower()
    return mode in {"publication", "expert_comprehensive"}


def _collect_step_meta(run_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    step_meta_map = run_data.get("step_meta") if isinstance(run_data, dict) else None
    if not isinstance(step_meta_map, dict):
        return []
    out: List[Dict[str, Any]] = []
    for item in step_meta_map.values():
        if isinstance(item, dict):
            out.append(item)
    return out


def _collect_methods_from_step_meta(step_meta_list: List[Dict[str, Any]]) -> List[str]:
    methods: List[str] = []
    for meta in step_meta_list:
        method = str(meta.get("method") or "").strip().lower()
        if method and method not in methods:
            methods.append(method)
    return methods


def _collect_covered_columns_from_step_meta(step_meta_list: List[Dict[str, Any]]) -> set:
    covered: set = set()
    for meta in step_meta_list:
        cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
        for key in ("outcome", "target", "group", "group1", "group2", "time", "subject", "subject_col", "split_by", "baseline", "follow"):
            value = cfg.get(key)
            if isinstance(value, str) and value.strip():
                covered.add(value.strip())
        for key in ("targets", "outcome_cols", "outcome_columns", "variables", "predictors", "covariates"):
            values = cfg.get(key)
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.strip():
                        covered.add(value.strip())
        pairs = cfg.get("pairs")
        if isinstance(pairs, list):
            for item in pairs:
                if not isinstance(item, dict):
                    continue
                for key in ("baseline", "follow"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        covered.add(value.strip())
    return covered


def _build_coverage_gate(dataset_id: str, run_data: Dict[str, Any]) -> Dict[str, Any]:
    study_payload = _load_study_design_payload(dataset_id)
    design = study_payload.get("design") if isinstance(study_payload.get("design"), dict) else {}
    target_outcomes: List[str] = []
    for value in [*(design.get("outcomes") or []), *(design.get("categorical_outcomes") or [])]:
        text = str(value or "").strip()
        if text and text not in target_outcomes:
            target_outcomes.append(text)

    step_meta = _collect_step_meta(run_data if isinstance(run_data, dict) else {})
    covered = _collect_covered_columns_from_step_meta(step_meta)
    covered_targets = [c for c in target_outcomes if c in covered]
    missing_targets = [c for c in target_outcomes if c not in covered]
    ratio = (len(covered_targets) / float(max(1, len(target_outcomes)))) if target_outcomes else 1.0
    return {
        "ok": bool(ratio >= 0.95),
        "target_total": int(len(target_outcomes)),
        "covered_total": int(len(covered_targets)),
        "coverage_ratio": float(round(ratio, 4)),
        "missing_outcomes": missing_targets[:120],
    }


def _build_reproducibility_gate(run_data: Dict[str, Any], publication_mode: bool) -> Dict[str, Any]:
    design_review = run_data.get("design_review") if isinstance(run_data.get("design_review"), dict) else {}
    analysis_set = run_data.get("analysis_set") if isinstance(run_data.get("analysis_set"), dict) else {}
    cleaning_artifact = run_data.get("cleaning_artifact") if isinstance(run_data.get("cleaning_artifact"), dict) else {}

    design_ok = bool(design_review.get("confirmed"))
    analysis_set_ok = bool(analysis_set.get("artifact_exists")) and bool(analysis_set.get("strict"))
    cleaning_ok = bool(cleaning_artifact.get("valid"))

    required = bool(publication_mode)
    ok = True if not required else bool(design_ok and analysis_set_ok and cleaning_ok)
    return {
        "ok": ok,
        "required": required,
        "design_review_confirmed": design_ok,
        "analysis_set_strict": analysis_set_ok,
        "cleaning_artifact_valid": cleaning_ok,
    }


def _build_interpretation_gate(run_data: Dict[str, Any], publication_mode: bool) -> Dict[str, Any]:
    run_data = normalize_run_data_results(run_data if isinstance(run_data, dict) else {})
    step_meta_map = run_data.get("step_meta") if isinstance(run_data.get("step_meta"), dict) else {}

    def iter_steps():
        results = run_data.get("results")
        if isinstance(results, dict):
            for step_id, payload in results.items():
                if isinstance(step_id, str) and isinstance(payload, dict):
                    yield step_id, payload
            return
        if isinstance(results, list):
            for idx, item in enumerate(results):
                if not isinstance(item, dict):
                    continue
                step_id = str(item.get("step_id") or item.get("id") or f"step_{idx + 1}")
                payload = item.get("results")
                if not isinstance(payload, dict):
                    payload = item.get("payload")
                if isinstance(payload, dict):
                    yield step_id, payload

    inferential_total = 0
    interpreted_contract_total = 0
    interpreted_fallback_total = 0
    missing_steps: List[str] = []

    for step_id, payload in iter_steps():
        if not is_inferential_interpretation_payload(payload):
            continue
        inferential_total += 1
        contract = payload.get("interpretation_contract")
        if is_interpretation_contract_complete(contract):
            interpreted_contract_total += 1
            continue
        conclusion = payload.get("conclusion") or payload.get("ai_interpretation")
        if isinstance(conclusion, str) and conclusion.strip():
            interpreted_fallback_total += 1
            if not publication_mode:
                continue
        missing_steps.append(step_id)

    if publication_mode:
        interpreted_total = interpreted_contract_total
    else:
        interpreted_total = interpreted_contract_total + interpreted_fallback_total

    ratio = (interpreted_total / float(max(1, inferential_total))) if inferential_total else 1.0
    required = bool(publication_mode)
    return {
        "ok": bool(ratio >= 0.95),
        "required": required,
        "inferential_blocks": int(inferential_total),
        "interpreted_blocks": int(interpreted_total),
        "contract_blocks": int(interpreted_contract_total),
        "fallback_only_blocks": int(interpreted_fallback_total),
        "coverage_ratio": float(round(ratio, 4)),
        "missing_steps": missing_steps[:120],
    }


def _build_figure_gate(
    run_data: Dict[str, Any],
    artifact_names: List[str],
    publication_mode: bool,
) -> Dict[str, Any]:
    run_data = normalize_run_data_results(run_data if isinstance(run_data, dict) else {})
    artifacts_set = set([str(x) for x in artifact_names if isinstance(x, str)])
    step_meta_map = run_data.get("step_meta") if isinstance(run_data.get("step_meta"), dict) else {}

    model_methods = {
        "linear_regression",
        "logistic_regression",
        "roc_analysis",
        "random_forest",
        "gradient_boosting",
        "knn",
        "svm",
        "external_validation",
    }
    corr_methods = {"clustered_correlation", "cluster_profiles", "pearson", "spearman"}
    group_methods = {"t_test_ind", "t_test_welch", "mann_whitney", "anova", "anova_welch", "kruskal", "bootstrap_pipeline"}
    trajectory_methods = {
        "mixed_effects",
        "rm_anova",
        "friedman",
        "batch_compare_by_factor",
        "timepoint_batch_analysis",
        "delta_batch_analysis",
        "responders",
    }
    survival_methods = {"survival", "survival_km"}

    def iter_steps():
        results = run_data.get("results")
        if isinstance(results, dict):
            for step_id, payload in results.items():
                if isinstance(step_id, str) and isinstance(payload, dict):
                    yield step_id, payload
            return
        if isinstance(results, list):
            for idx, item in enumerate(results):
                if not isinstance(item, dict):
                    continue
                step_id = str(item.get("step_id") or item.get("id") or f"step_{idx + 1}")
                payload = item.get("results")
                if not isinstance(payload, dict):
                    payload = item.get("payload")
                if isinstance(payload, dict):
                    yield step_id, payload

    def resolve_method(step_id: str, payload: Dict[str, Any]) -> str:
        meta = step_meta_map.get(step_id) if isinstance(step_meta_map.get(step_id), dict) else {}
        method = str(meta.get("method") or "").strip().lower()
        if method:
            return method
        method = str(payload.get("method_id") or "").strip().lower()
        if method:
            return method
        method_obj = payload.get("method")
        if isinstance(method_obj, dict):
            method = str(method_obj.get("id") or method_obj.get("name") or "").strip().lower()
            if method:
                return method
        if isinstance(method_obj, str) and method_obj.strip():
            return method_obj.strip().lower()
        return str(payload.get("type") or "").strip().lower()

    def has_plot_data(payload: Dict[str, Any]) -> bool:
        if isinstance(payload.get("plot_image_b64"), str) and payload.get("plot_image_b64").strip():
            return True
        if isinstance(payload.get("plot_data"), list) and payload.get("plot_data"):
            return True
        if isinstance(payload.get("plot_stats"), dict) and payload.get("plot_stats"):
            return True
        if isinstance(payload.get("plots"), list) and payload.get("plots"):
            return True
        return False

    def payload_supports(category: str, payload: Dict[str, Any], method_id: str) -> bool:
        if not isinstance(payload, dict):
            return False
        method_id = str(method_id or "").strip().lower()
        if category == "model_diagnostics":
            roc = payload.get("roc")
            if isinstance(roc, dict):
                if isinstance(roc.get("plot_data"), list) and roc.get("plot_data"):
                    return True
                if roc.get("auc") is not None:
                    return True
            if isinstance(payload.get("coefficients"), list) and payload.get("coefficients"):
                return True
            if payload.get("confusion_matrix") is not None or payload.get("calibration") is not None:
                return True
            return has_plot_data(payload) and method_id in model_methods
        if category == "correlation_visuals":
            if isinstance(payload.get("correlation_matrix"), dict) and payload.get("correlation_matrix"):
                return True
            if isinstance(payload.get("heatmap_data"), list) and payload.get("heatmap_data"):
                return True
            if isinstance(payload.get("cluster_assignments"), dict) and payload.get("cluster_assignments"):
                return True
            if isinstance(payload.get("dendrogram"), dict) and payload.get("dendrogram"):
                return True
            return has_plot_data(payload) and method_id in corr_methods
        if category == "group_distribution":
            plot_stats = payload.get("plot_stats")
            if isinstance(plot_stats, dict) and len(plot_stats) >= 2:
                return True
            plot_data = payload.get("plot_data")
            if isinstance(plot_data, list) and plot_data:
                for row in plot_data:
                    if isinstance(row, dict) and row.get("group") is not None and row.get("value") is not None:
                        return True
            return has_plot_data(payload) and method_id in group_methods
        if category == "trajectory":
            if isinstance(payload.get("estimated_means"), dict) and payload.get("estimated_means"):
                return True
            if isinstance(payload.get("by_visit"), dict) and payload.get("by_visit"):
                return True
            if isinstance(payload.get("slices"), dict) and payload.get("slices"):
                return True
            if isinstance(payload.get("pairs"), list) and payload.get("pairs"):
                return True
            if isinstance(payload.get("delta_summary"), dict) and payload.get("delta_summary"):
                return True
            return has_plot_data(payload) and method_id in trajectory_methods
        if category == "survival":
            if isinstance(payload.get("survival_curves"), list) and payload.get("survival_curves"):
                return True
            plot_data = payload.get("plot_data")
            if isinstance(plot_data, list) and plot_data:
                for row in plot_data:
                    if isinstance(row, dict) and row.get("time") is not None and row.get("probability") is not None:
                        return True
            return has_plot_data(payload) and method_id in survival_methods
        return False

    methods_seen: set = set()
    payload_rows: List[Tuple[str, Dict[str, Any], str]] = []
    for step_id, payload in iter_steps():
        method_id = resolve_method(step_id, payload)
        if method_id:
            methods_seen.add(method_id)
        payload_rows.append((step_id, payload, method_id))

    expected = {
        "model_diagnostics": bool(methods_seen.intersection(model_methods)),
        "correlation_visuals": bool(methods_seen.intersection(corr_methods)),
        "group_distribution": bool(methods_seen.intersection(group_methods)),
        "trajectory": bool(methods_seen.intersection(trajectory_methods)),
        "survival": bool(methods_seen.intersection(survival_methods)),
    }

    report_spec = run_data.get("report_spec") if isinstance(run_data.get("report_spec"), dict) else {}
    figure_requirements = report_spec.get("figure_requirements") if isinstance(report_spec.get("figure_requirements"), list) else []
    req_aliases = {
        "roc_curve": "model_diagnostics",
        "model_diagnostics": "model_diagnostics",
        "correlation_heatmap": "correlation_visuals",
        "correlation_visuals": "correlation_visuals",
        "group_distribution": "group_distribution",
        "trajectory": "trajectory",
        "trajectory_plot": "trajectory",
        "survival": "survival",
        "survival_km": "survival",
    }
    for row in figure_requirements:
        if not isinstance(row, dict):
            continue
        fig_id = str(row.get("id") or "").strip().lower()
        mapped = req_aliases.get(fig_id)
        if mapped:
            expected[mapped] = True

    present = {
        "model_diagnostics": any(("roc" in name.lower() or "calibration" in name.lower() or "confusion" in name.lower()) for name in artifacts_set),
        "correlation_visuals": any(("corr" in name.lower() or "heatmap" in name.lower() or "dendro" in name.lower()) for name in artifacts_set),
        "group_distribution": any(("box" in name.lower() or "violin" in name.lower() or "distribution" in name.lower()) for name in artifacts_set),
        "trajectory": any(("trajectory" in name.lower() or "delta" in name.lower() or "timepoint" in name.lower()) for name in artifacts_set),
        "survival": any(("survival" in name.lower() or "km" in name.lower() or "kaplan" in name.lower()) for name in artifacts_set),
    }

    for category in list(present.keys()):
        if present.get(category):
            continue
        for _, payload, method_id in payload_rows:
            if payload_supports(category, payload, method_id):
                present[category] = True
                break

    required = bool(publication_mode and any(bool(v) for v in expected.values()))
    missing: List[str] = []
    for category, need in expected.items():
        if need and not present.get(category):
            missing.append(category)

    return {
        "ok": bool((not required) or (len(missing) == 0)),
        "required": required,
        "expected": expected,
        "present": present,
        "missing": missing,
    }


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


def _evaluate_report_quality(
    run_data: Any,
    *,
    dataset_id: str,
    run_id: str,
    report_html: str,
    artifact_names: List[str],
    require_exports: bool,
) -> Dict[str, Any]:
    design_ok, design_reason = _check_study_design_ready(dataset_id)
    methods_ok, methods_reason = _check_report_methods_ready(run_data)
    publication_mode = _infer_publication_mode(run_data if isinstance(run_data, dict) else {})

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

    export_presence = {
        "html": any(name.endswith(".html") and "protocol_report" in name for name in artifacts_set),
        "pdf": any(name.endswith(".pdf") and "protocol_report" in name for name in artifacts_set),
        "docx": any(name.endswith(".docx") and "protocol_report" in name for name in artifacts_set),
    }
    exports_ok = all(export_presence.values()) if require_exports else True

    coverage_gate = _build_coverage_gate(dataset_id, run_data if isinstance(run_data, dict) else {})
    interpretation_gate = _build_interpretation_gate(run_data if isinstance(run_data, dict) else {}, publication_mode)
    figure_gate = _build_figure_gate(run_data if isinstance(run_data, dict) else {}, artifact_names, publication_mode)
    reproducibility_gate = _build_reproducibility_gate(run_data if isinstance(run_data, dict) else {}, publication_mode)

    checks = {
        "design_artifact": {"ok": design_ok, "reason": "" if design_ok else design_reason},
        "methods_metadata": {"ok": methods_ok, "reason": "" if methods_ok else methods_reason},
        "coverage": coverage_gate,
        "interpretation_completeness": interpretation_gate,
        "figure_completeness": figure_gate,
        "reproducibility": reproducibility_gate,
        "sections": {
            "ok": sections_ok,
            "required": section_checks,
        },
        "analysis_dataset_artifacts": {
            "ok": dataset_artifacts_ok,
            "missing": dataset_artifacts_missing,
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
    if publication_mode and not bool(coverage_gate.get("ok")):
        missing.append("coverage")
    if bool(interpretation_gate.get("required")) and not bool(interpretation_gate.get("ok")):
        missing.append("interpretation_completeness")
    if bool(figure_gate.get("required")) and not bool(figure_gate.get("ok")):
        missing.append("figure_completeness")
        missing.extend([f"figure:{name}" for name in (figure_gate.get("missing") or []) if isinstance(name, str)])
    if bool(reproducibility_gate.get("required")) and not bool(reproducibility_gate.get("ok")):
        missing.append("reproducibility")
    if not sections_ok:
        missing.extend([f"section:{sid}" for sid, ok in section_checks.items() if not ok])
    if not dataset_artifacts_ok:
        missing.extend([f"artifact:{name}" for name in dataset_artifacts_missing])
    if require_exports and not all(export_presence.values()):
        missing.extend([f"export:{ext}" for ext, ok in export_presence.items() if not ok])

    ready = len(missing) == 0
    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "status": "pass" if ready else "fail",
        "ready": ready,
        "publication_mode": publication_mode,
        "missing": missing,
        "checks": checks,
        "artifacts_seen": sorted(list(artifacts_set)),
    }


@router.get("/protocol/report/{run_id}/quality")
async def get_protocol_report_quality(
    run_id: str,
    dataset_id: str,
    require_exports: bool = False,
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
        quality_payload = _evaluate_report_quality(
            res,
            dataset_id=dataset_id,
            run_id=run_id,
            report_html=report_html,
            artifact_names=artifact_names,
            require_exports=bool(require_exports),
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
        _enforce_report_design_gate(dataset_id)
        _enforce_report_methods_gate(dataset_id, run_id)
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
        res = _enrich_run_data_for_report(res)
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
        _enforce_report_design_gate(dataset_id)
        _enforce_report_methods_gate(dataset_id, run_id)
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
        res = _enrich_run_data_for_report(res)
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
