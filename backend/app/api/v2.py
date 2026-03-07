"""
API v2 Endpoints for Advanced Statistical Methods
===================================================
JAMOVI-style endpoints for mixed effects models, clustered correlation, and advanced analyses.
Memory-optimized for MacBook M1 8GB constraints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from typing import List, Dict, Any, Optional, Literal, Tuple
import pandas as pd
import numpy as np
import gc
import asyncio
from concurrent.futures import ProcessPoolExecutor
import os
import json
import math
import hashlib
import platform
import sys
import time
from pathlib import Path
from datetime import datetime
from importlib import metadata as importlib_metadata

from app.core.logging import logger
from app.core.config import settings
from app.llm import analyze_research_design
from app.modules.ai_context import build_ai_context, safe_plan_constraints, enforce_protocol_constraints, generate_prompt_brief
from app.llm.smart_sampling import build_smart_sample
from app.llm import critique_protocol
from app.modules.parsers import get_dataframe
from app.core.pipeline import PipelineManager
from app.stats.mixed_effects import MixedEffectsEngine
from app.stats.clustered_correlation import ClusteredCorrelationEngine
from app.stats.method_coverage import is_engine_supported, normalize_engine_name, supported_engines
from app.stats.engine import (
    run_analysis,
    select_test,
    compute_descriptive_compare,
    run_batch_analysis,
    _safe_bootstrap_samples,
    _bootstrap_ci_paired,
)
from app.core.study_designer import StudyDesignEngine
from app.modules.text_generator import TextGenerator
from app.modules.protocol_rules import build_exploratory_plan, merge_protocols
from app.modules.protocol_quality import evaluate_protocol_quality
from app.modules.hypothesis_discovery import build_hypothesis_discovery
from app.modules.legacy_telemetry import record_legacy_hit, get_legacy_snapshot
from app.modules.study_design import load_study_design
from app.modules.model_router_benchmark import (
    collect_llm_benchmark_artifacts,
    build_router_benchmark_report,
    build_router_benchmark_markdown,
    evaluate_benchmark_coverage,
)
from app.modules.design_review import load_design_review
from app.modules.analysis_set import (
    load_analysis_set as load_analysis_set_artifact,
    apply_analysis_set_to_df,
    validate_analysis_set_fingerprint,
)
from app.modules.analysis_result_v2 import (
    normalize_analysis_result_v2,
    normalize_results_map,
    normalize_results_list,
)
from app.copilot.orchestrator import AgentOrchestrator
from app.copilot.verification_policy import (
    iter_result_payload_entries as _vp_iter_result_payload_entries,
    extract_step_p_value as _vp_extract_step_p_value,
    repair_run_payload_multiplicity as _vp_repair_run_payload_multiplicity,
    repair_run_payload_p_bounds as _vp_repair_run_payload_p_bounds,
    attempt_verifier_reflection_repair as _vp_attempt_verifier_reflection_repair,
)
from app.copilot.validator import validate_protocol_step, build_protocol_validation_report
from app.copilot.verifier import verify_run_payload
from app.core.artifact_contracts import assert_artifact_contract
from app.api.datasets import DATA_DIR, _load_dataset_meta
from app.api.schemas import (
    MixedEffectsRequest,
    ClusteredCorrelationRequest,
    ProtocolV2Request,
    AnalysisTemplateListResponse,
    AnalysisTemplateDesignRequest,
    AnalysisPlanRequest,
    AnalysisBriefRequest,
    ExecuteProtocolRequest,
)
from app.api.helpers import (
    _ensure_method,
    _canonical_method_id,
    _normalize_plan_step,
    _to_int_or_none,
    _to_float_or_none,
    _runtime_elapsed_ms,
    _runtime_percentile_ms,
    _normalize_role_models_payload,
    _benchmark_clamp01,
    _normalize_benchmark_analysis_mode,
    _normalize_benchmark_validation_profile,
    _score_benchmark_latency,
    _score_benchmark_token_efficiency,
    _score_benchmark_step_coverage,
    _score_benchmark_retry_efficiency,
    _llm_benchmark_auto_score,
    _normalize_llm_benchmark_payload,
    _normalize_correction,
    _as_bool,
    _method_supports_bootstrap,
    _method_supports_multiplicity,
    _finite_float,
    _normalize_analysis_mode,
    _normalize_validation_profile,
    _as_str_list,
    _merge_plan_section,
)
from app.api.builders import (
    _resolve_llm_benchmark_score_profile,
    _normalize_bootstrap_samples,
    _resolve_multiplicity_policy,
    _attach_multiplicity_policy_to_plan_globals,
    _resolve_bootstrap_policy,
    _attach_bootstrap_policy_to_plan_globals,
    _analysis_runtime_kwargs,
    _build_batch_multiplicity_trace,
    _bootstrap_metric_preview,
    _build_bootstrap_trace_document,
    _count_adjusted_p_values,
    _build_multiplicity_trace_document,
    _iter_result_payload_entries,
    _extract_step_p_value,
    _repair_run_payload_multiplicity,
    _repair_run_payload_p_bounds,
    _attempt_verifier_reflection_repair,
    _sha256_hex,
    _build_environment_snapshot,
    _reproduce_script_template,
    _build_fallback_report_html,
    _create_run_reproducibility_artifacts,
    _collect_dataset_columns,
    _filter_protocol_steps,
    _resolve_runtime_validation_policy,
    _attach_validation_policy_to_plan_globals,
    _infer_protocol_column_sets,
    _build_cleaning_plan,
    _build_cohort_plan,
    _build_report_spec,
    _safe_build_hypothesis_discovery,
    _load_model_router_benchmark_capture_last,
)
from app.api.executor_dispatch import get_executor, is_engine_method
from app.utils import convert_numpy_to_native

pipeline = PipelineManager(DATA_DIR)

_text_generator = TextGenerator()


def _maybe_add_conclusion(payload: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    if payload.get("conclusion"):
        return payload
    try:
        payload["conclusion"] = _text_generator.interpret_result(payload, variables, style="ru")
    except Exception:
        pass
    return payload


router = APIRouter()

# Memory-efficient executor for CPU-intensive operations
analysis_executor = ProcessPoolExecutor(max_workers=2)  # Reduced for 8GB


def _get_analysis_executor() -> ProcessPoolExecutor:
    """Return a live process pool executor, recreating it if it was shut down."""
    global analysis_executor
    if analysis_executor is None or bool(getattr(analysis_executor, "_shutdown", False)):
        analysis_executor = ProcessPoolExecutor(max_workers=2)
    return analysis_executor

# Standard statistical methods for protocol fallback
STANDARD_METHODS = [
    "t_test_ind",
    "t_test_welch",
    "mann_whitney",
    "t_test_rel",
    "wilcoxon",
    "anova",
    "anova_welch",
    "kruskal",
    "chi_square",
    "fisher_exact",
    "pearson",
    "spearman",
    "kendall",
    "linear_regression",
    "logistic_regression",
    "roc_analysis",
    "bayes_anova",
    "bayes_chi_square",
    "bayes_linear_regression",
]

MAX_EXECUTE_PROTOCOL_STEPS = 20000

DEFAULT_BOOTSTRAP_SAMPLES = 1000

BOOTSTRAP_COMPATIBLE_METHODS = {
    "auto",
    "batch_analysis",
    "timepoint_batch_analysis",
    "delta_batch_analysis",
    "paired_wide",
    "t_test_one",
    "t_test_ind",
    "t_test_welch",
    "mann_whitney",
    "t_test_rel",
    "wilcoxon",
    "anova",
    "anova_welch",
    "kruskal",
    "pearson",
    "spearman",
    "kendall",
    "linear_regression",
    "logistic_regression",
    "ancova",
    "bayes_t_test_one",
    "bayes_t_test_ind",
    "bayes_t_test_rel",
    "bayes_correlation",
    "bayes_anova",
    "bayes_linear_regression",
}

MULTIPLICITY_BATCH_METHODS = {
    "batch_analysis",
    "timepoint_batch_analysis",
    "delta_batch_analysis",
}

MULTIPLICITY_POSTHOC_METHODS = {
    "auto",
    "anova",
    "anova_welch",
    "kruskal",
}

MULTIPLICITY_COMPATIBLE_METHODS = MULTIPLICITY_BATCH_METHODS.union(
    MULTIPLICITY_POSTHOC_METHODS
)

TEMPLATE_TO_V2_SUPPORTED_STEP_TYPES = {
    "descriptive_compare",
    "compare",
    "correlation",
}


@router.get("/analysis/templates", response_model=AnalysisTemplateListResponse)
async def list_analysis_templates(goal: Optional[str] = None):
    try:
        designer = StudyDesignEngine()
        return {"templates": designer.list_templates(goal=goal)}
    except Exception as e:
        logger.error(f"Template listing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить список шаблонов: {str(e)}")


@router.get("/telemetry/legacy", response_model=Dict[str, Any])
async def legacy_telemetry_snapshot(x_telemetry_token: Optional[str] = Header(default=None, alias="X-Telemetry-Token")):
    expected = getattr(settings, "CLINIMETRIA_TELEMETRY_TOKEN", None)
    if expected:
        provided = str(x_telemetry_token or "").strip()
        if provided != str(expected):
            raise HTTPException(status_code=403, detail="Telemetry access denied")
    return get_legacy_snapshot()


@router.get("/analysis/benchmark/model-router", response_model=Dict[str, Any])
async def model_router_benchmark_snapshot(
    min_runs: int = 0,
    include_markdown: bool = False,
    top_n: int = 10,
):
    try:
        workspace_dir = Path(DATA_DIR).resolve().parent
        artifacts = collect_llm_benchmark_artifacts(workspace_dir)
        report = build_router_benchmark_report(artifacts, workspace_dir=workspace_dir)
        min_runs_norm = max(0, int(min_runs))
        report["coverage_gate"] = evaluate_benchmark_coverage(report, min_runs=min_runs_norm)
        report["artifacts_collected"] = int(len(artifacts))
        report["capture_last"] = _load_model_router_benchmark_capture_last(workspace_dir)
        if include_markdown:
            report["markdown"] = build_router_benchmark_markdown(
                report,
                min_runs=min_runs_norm,
                top_n=max(1, min(50, int(top_n))),
            )
        return report
    except Exception as e:
        logger.error(f"model_router_benchmark_snapshot failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось собрать model-router benchmark: {str(e)}")


@router.post("/analysis/design", response_model=Dict[str, Any])
async def design_analysis_from_template(request: AnalysisTemplateDesignRequest):
    logger.warning(
        "Deprecated endpoint hit: /api/v1/v2/analysis/design. Use /api/v1/v2/analysis/plan for canonical flow."
    )
    record_legacy_hit("/api/v1/v2/analysis/design")
    try:
        metadata: Dict[str, Any] = {}
        scan_path = os.path.join(DATA_DIR, request.dataset_id, "processed", "scan_report.json")
        if os.path.exists(scan_path):
            with open(scan_path, "r") as f:
                report = json.load(f)
                metadata = report.get("columns", {}) or {}

        variables = request.variables if isinstance(request.variables, dict) else {}
        meta = _load_dataset_meta(request.dataset_id)
        dataset_title = str(meta.get("original_filename") or meta.get("filename") or "").strip()
        if dataset_title and not variables.get("dataset_title"):
            variables = dict(variables)
            variables["dataset_title"] = dataset_title

        designer = StudyDesignEngine()
        protocol_v1 = designer.suggest_protocol(
            request.goal,
            variables,
            metadata,
            template_id=request.template_id,
        )

        protocol_v2: List[Dict[str, Any]] = []
        skipped_steps: List[Dict[str, Any]] = []

        for step in protocol_v1.get("steps", []) or []:
            step_type = step.get("type")
            if step_type not in TEMPLATE_TO_V2_SUPPORTED_STEP_TYPES:
                skipped_steps.append(step)
                continue

            if step_type == "descriptive_compare":
                protocol_v2.append(
                    {
                        "id": step.get("id") or f"step_{len(protocol_v2) + 1}",
                        "method": "descriptive_compare",
                        "config": {"target": step.get("target"), "group": step.get("group")},
                    }
                )
                continue

            target = step.get("target")
            group = step.get("group") or step.get("predictor")
            method_val = step.get("method")
            if isinstance(method_val, dict):
                method_id = method_val.get("id")
            else:
                method_id = method_val
            if not method_id:
                method_id = "auto"

            protocol_v2.append(
                {
                    "id": step.get("id") or f"step_{len(protocol_v2) + 1}",
                    "method": method_id,
                    "config": {"outcome": target, "group": group},
                }
            )

        return {
            "status": "completed",
            "name": protocol_v1.get("name"),
            "goal": protocol_v1.get("goal") or request.goal,
            "protocol": protocol_v2,
            "skipped_steps": skipped_steps,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Template design failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось создать протокол по шаблону: {str(e)}")


@router.post("/analysis/brief", response_model=Dict[str, Any])
async def build_analysis_brief(request: AnalysisBriefRequest):
    try:
        dataset_id = str(request.dataset_id)
        prefs = request.preferences if isinstance(request.preferences, dict) else {}
        analysis_mode = _normalize_analysis_mode(prefs.get("analysis_mode") or prefs.get("mode"))
        validation_policy = _resolve_runtime_validation_policy(prefs, analysis_mode=analysis_mode)
        multiplicity_policy = _resolve_multiplicity_policy(prefs, analysis_mode=analysis_mode)
        bootstrap_policy = _resolve_bootstrap_policy(prefs, analysis_mode=analysis_mode)
        dataset_meta = build_ai_context(dataset_id=dataset_id, base_dir=DATA_DIR)
        hypotheses = _safe_build_hypothesis_discovery(
            dataset_meta=dataset_meta,
            preferences=prefs,
            protocol=None,
        )
        prompt = generate_prompt_brief(dataset_meta, request.preferences)
        return {
            "prompt": prompt,
            "analysis_mode": analysis_mode,
            "validation_policy": validation_policy,
            "multiplicity_policy": multiplicity_policy,
            "bootstrap_policy": bootstrap_policy,
            "hypotheses": hypotheses,
        }
    except Exception as e:
        logger.error(f"Brief generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать бриф: {str(e)}")


@router.post("/analysis/plan", response_model=Dict[str, Any])
async def plan_analysis_with_ai(request: AnalysisPlanRequest):
    try:
        df = await load_dataset_async(request.dataset_id)
        dataset_meta = build_ai_context(dataset_id=request.dataset_id, base_dir=DATA_DIR, df=df)
        constraints = safe_plan_constraints(request.preferences)
        prefs = request.preferences if isinstance(request.preferences, dict) else {}
        analysis_mode = _normalize_analysis_mode(prefs.get("analysis_mode") or prefs.get("mode"))
        role_models = prefs.get("llm_models") if isinstance(prefs.get("llm_models"), dict) else None
        design_review_confirmed = _as_bool(prefs.get("design_confirmed"), default=False)
        design_review_warning = None
        if not design_review_confirmed:
            design_review_warning = (
                "Design Review не подтверждён. Рекомендуется подтвердить роли group/time/subject/outcome перед планированием."
            )

        use_sampling = bool(prefs.get("smart_sampling") or prefs.get("use_smart_sampling"))
        sample_mode = str(prefs.get("smart_sampling_mode") or "").strip().lower()
        if not sample_mode:
            sample_mode = "masked" if use_sampling else "off"
        if prefs.get("no_raw_sample") is True:
            sample_mode = "off"

        if sample_mode not in {"off", "none"}:
            max_rows = prefs.get("smart_sample_rows") or prefs.get("sample_rows") or 40
            max_cols = prefs.get("smart_sample_cols") or prefs.get("sample_cols") or 18
            redact_mode = "pii"
            if sample_mode in {"raw", "unsafe"}:
                redact_mode = "none"
            elif sample_mode in {"strict", "full"}:
                redact_mode = "strict"
            try:
                sample = build_smart_sample(
                    df,
                    max_rows=int(max_rows),
                    max_cols=int(max_cols),
                    redact_mode=redact_mode,
                )
                dataset_meta["sample_rows"] = sample.get("rows") or []
                dataset_meta["sample_info"] = {
                    "strategy": sample.get("strategy"),
                    "row_count": sample.get("row_count"),
                    "columns": sample.get("columns"),
                    "redact_mode": redact_mode,
                }
            except Exception:
                pass
        else:
            dataset_meta["sample_rows"] = []
            dataset_meta["sample_info"] = {"strategy": "disabled", "row_count": 0, "columns": []}

        scan_report: Dict[str, Any] = {}
        scan_path = os.path.join(DATA_DIR, request.dataset_id, "processed", "scan_report.json")
        if os.path.exists(scan_path):
            try:
                with open(scan_path, "r", encoding="utf-8") as f:
                    scan_report = json.load(f)
            except Exception:
                scan_report = {}

        rules_plan = build_exploratory_plan(
            dataset_id=request.dataset_id,
            base_dir=DATA_DIR,
            preferences=prefs,
            constraints=constraints,
            scan_report=scan_report,
        )
        rules_protocol = rules_plan.get("protocol") if isinstance(rules_plan, dict) else []
        rules_globals = rules_plan.get("globals") if isinstance(rules_plan, dict) else {}
        rules_notes = rules_plan.get("notes") if isinstance(rules_plan, dict) else []
        column_selection_report = (
            rules_plan.get("column_selection_report")
            if isinstance(rules_plan, dict) and isinstance(rules_plan.get("column_selection_report"), dict)
            else {}
        )
        protocol_plan = {"column_selection_report": column_selection_report}

        ai_payload = await analyze_research_design(
            text=request.text,
            dataset_meta=dataset_meta,
            current_protocol=request.protocol or [],
            preferences=request.preferences or {},
            constraints=constraints,
            role_models=role_models,
        )

        if isinstance(ai_payload, dict):
            raw_steps = ai_payload.get("protocol") or ai_payload.get("steps")
            steps_in = raw_steps if isinstance(raw_steps, list) else []
            protocol_out: List[Dict[str, Any]] = []
            for i, step in enumerate(steps_in[:40]):
                norm = _normalize_plan_step(step, i)
                if norm:
                    protocol_out.append(norm)

            globals_in = ai_payload.get("globals")
            globals_out = globals_in if isinstance(globals_in, dict) else {}
            if "analysis_mode" not in globals_out:
                globals_out["analysis_mode"] = analysis_mode
            if "mode" not in globals_out:
                globals_out["mode"] = analysis_mode
            if "alternative" not in globals_out and "alternative" in prefs:
                globals_out["alternative"] = prefs.get("alternative")
            if "post_hoc" not in globals_out and "post_hoc" in prefs:
                globals_out["post_hoc"] = prefs.get("post_hoc")
            if "post_hoc_correction" not in globals_out and "post_hoc_correction" in prefs:
                globals_out["post_hoc_correction"] = prefs.get("post_hoc_correction")
            if role_models:
                globals_out["llm_models"] = role_models

            protocol_name = str(ai_payload.get("protocol_name") or "Протокол").strip() or "Протокол"
            notes = ai_payload.get("notes")
            notes_out = notes if isinstance(notes, list) else []
            usage_payload = ai_payload.get("usage") if isinstance(ai_payload.get("usage"), dict) else None

            if protocol_out:
                if design_review_warning:
                    notes_out.append(design_review_warning)
                protocol_out = enforce_protocol_constraints(protocol_out, constraints)
                protocol_out, filter_notes = _filter_protocol_steps(protocol_out, dataset_meta)
                if filter_notes:
                    notes_out.extend(filter_notes)

                study_design = load_study_design(DATA_DIR, request.dataset_id)
                quality = evaluate_protocol_quality(protocol_out, study_design=study_design, scan_report=scan_report)

                use_exploratory = analysis_mode == "exploratory" or bool(
                    prefs.get("allow_data_mining")
                )

                if use_exploratory:
                    protocol_out = merge_protocols(protocol_out, rules_protocol, constraints)
                    notes_out.append("Exploratory режим: протокол расширен rules-based шагами.")
                    globals_out = {**(rules_globals or {}), **globals_out}
                    protocol_out, filter_notes = _filter_protocol_steps(protocol_out, dataset_meta)
                    if filter_notes:
                        notes_out.extend(filter_notes)
                    quality = evaluate_protocol_quality(protocol_out, study_design=study_design, scan_report=scan_report)
                elif isinstance(quality, dict) and float(quality.get("score") or 0.0) < 55.0:
                    protocol_out = rules_protocol
                    globals_out = {**globals_out, **(rules_globals or {})}
                    protocol_name = "Exploratory protocol"
                    notes_out.append("LLM протокол низкого качества; использован rules-based вариант.")
                    if isinstance(rules_notes, list):
                        notes_out.extend(rules_notes)
                    protocol_out, filter_notes = _filter_protocol_steps(protocol_out, dataset_meta)
                    if filter_notes:
                        notes_out.extend(filter_notes)
                    quality = evaluate_protocol_quality(protocol_out, study_design=study_design, scan_report=scan_report)

                use_critic = prefs.get("use_critic")
                if use_critic is None:
                    use_critic = True
                critic_payload = None
                if use_critic and protocol_out:
                    try:
                        critic_payload = await critique_protocol(
                            protocol=protocol_out,
                            dataset_meta=dataset_meta,
                            preferences=prefs,
                            constraints=constraints,
                            role_models=role_models,
                        )
                        if isinstance(critic_payload, dict):
                            drop_ids = set(
                                str(s) for s in (critic_payload.get("drop_step_ids") or []) if isinstance(s, (str, int))
                            )
                            if drop_ids:
                                filtered = [s for s in protocol_out if str(s.get("id")) not in drop_ids]
                                if filtered:
                                    protocol_out = filtered
                                    notes_out.append("Critic: удалены шаги с ошибочной конфигурацией.")
                            critic_notes = critic_payload.get("notes")
                            if isinstance(critic_notes, list) and critic_notes:
                                notes_out.extend([str(n) for n in critic_notes if str(n).strip()])
                            critic_issues = critic_payload.get("issues")
                            if isinstance(critic_issues, list) and critic_issues:
                                notes_out.extend([f"Critic: {str(n)}" for n in critic_issues if str(n).strip()])
                    except Exception:
                        critic_payload = None

                cleaning_plan = _build_cleaning_plan(
                    scan_report=scan_report,
                    protocol=protocol_out,
                    analysis_mode=analysis_mode,
                )
                cohort_plan = _build_cohort_plan(
                    protocol=protocol_out,
                    preferences=prefs,
                    analysis_mode=analysis_mode,
                )
                report_spec = _build_report_spec(protocol=protocol_out, analysis_mode=analysis_mode)
                cleaning_plan = _merge_plan_section(cleaning_plan, ai_payload.get("cleaning_plan"))
                cohort_plan = _merge_plan_section(cohort_plan, ai_payload.get("cohort_plan"))
                report_spec = _merge_plan_section(report_spec, ai_payload.get("report_spec"))
                globals_out, validation_policy = _attach_validation_policy_to_plan_globals(
                    globals_out,
                    preferences=prefs,
                    analysis_mode=analysis_mode,
                )
                globals_out, multiplicity_policy = _attach_multiplicity_policy_to_plan_globals(
                    globals_out,
                    preferences=prefs,
                    analysis_mode=analysis_mode,
                )
                globals_out, bootstrap_policy = _attach_bootstrap_policy_to_plan_globals(
                    globals_out,
                    preferences=prefs,
                    analysis_mode=analysis_mode,
                )
                hypotheses = _safe_build_hypothesis_discovery(
                    dataset_meta=dataset_meta,
                    preferences=prefs,
                    protocol=protocol_out,
                )

                return {
                    "status": "completed",
                    "protocol_name": protocol_name,
                    "globals": globals_out,
                    "protocol": protocol_out,
                    "notes": notes_out,
                    "protocol_plan": protocol_plan,
                    "column_selection_report": column_selection_report,
                    "quality": quality,
                    "critic": critic_payload,
                    "usage": usage_payload,
                    "design_review_confirmed": design_review_confirmed,
                    "analysis_mode": analysis_mode,
                    "cleaning_plan": cleaning_plan,
                    "cohort_plan": cohort_plan,
                    "report_spec": report_spec,
                    "validation_policy": validation_policy,
                    "multiplicity_policy": multiplicity_policy,
                    "bootstrap_policy": bootstrap_policy,
                    "hypotheses": hypotheses,
                }

        # Fallback: rules-based exploratory plan
        fallback_protocol = rules_protocol or []
        fallback_globals = rules_globals or {}
        fallback_globals = {**fallback_globals, "analysis_mode": analysis_mode, "mode": analysis_mode}
        if role_models:
            fallback_globals = {**fallback_globals, "llm_models": role_models}
        fallback_notes = list(rules_notes) if isinstance(rules_notes, list) else []
        if design_review_warning:
            fallback_notes.append(design_review_warning)
        study_design = load_study_design(DATA_DIR, request.dataset_id)
        quality = evaluate_protocol_quality(fallback_protocol, study_design=study_design, scan_report=scan_report)
        fallback_protocol, filter_notes = _filter_protocol_steps(fallback_protocol, dataset_meta)
        if filter_notes:
            fallback_notes.extend(filter_notes)

        use_critic = prefs.get("use_critic")
        if use_critic is None:
            use_critic = True
        critic_payload = None
        if use_critic and fallback_protocol:
            try:
                critic_payload = await critique_protocol(
                    protocol=fallback_protocol,
                    dataset_meta=dataset_meta,
                    preferences=prefs,
                    constraints=constraints,
                    role_models=role_models,
                )
                if isinstance(critic_payload, dict):
                    drop_ids = set(
                        str(s) for s in (critic_payload.get("drop_step_ids") or []) if isinstance(s, (str, int))
                    )
                    if drop_ids:
                        filtered = [s for s in fallback_protocol if str(s.get("id")) not in drop_ids]
                        if filtered:
                            fallback_protocol = filtered
                            fallback_notes.append("Critic: удалены шаги с ошибочной конфигурацией.")
                    critic_notes = critic_payload.get("notes")
                    if isinstance(critic_notes, list) and critic_notes:
                        fallback_notes.extend([str(n) for n in critic_notes if str(n).strip()])
                    critic_issues = critic_payload.get("issues")
                    if isinstance(critic_issues, list) and critic_issues:
                        fallback_notes.extend([f"Critic: {str(n)}" for n in critic_issues if str(n).strip()])
            except Exception:
                critic_payload = None

        cleaning_plan = _build_cleaning_plan(
            scan_report=scan_report,
            protocol=fallback_protocol,
            analysis_mode=analysis_mode,
        )
        cohort_plan = _build_cohort_plan(
            protocol=fallback_protocol,
            preferences=prefs,
            analysis_mode=analysis_mode,
        )
        report_spec = _build_report_spec(protocol=fallback_protocol, analysis_mode=analysis_mode)
        cleaning_plan = _merge_plan_section(cleaning_plan, ai_payload.get("cleaning_plan") if isinstance(ai_payload, dict) else None)
        cohort_plan = _merge_plan_section(cohort_plan, ai_payload.get("cohort_plan") if isinstance(ai_payload, dict) else None)
        report_spec = _merge_plan_section(report_spec, ai_payload.get("report_spec") if isinstance(ai_payload, dict) else None)
        fallback_globals, validation_policy = _attach_validation_policy_to_plan_globals(
            fallback_globals,
            preferences=prefs,
            analysis_mode=analysis_mode,
        )
        fallback_globals, multiplicity_policy = _attach_multiplicity_policy_to_plan_globals(
            fallback_globals,
            preferences=prefs,
            analysis_mode=analysis_mode,
        )
        fallback_globals, bootstrap_policy = _attach_bootstrap_policy_to_plan_globals(
            fallback_globals,
            preferences=prefs,
            analysis_mode=analysis_mode,
        )
        hypotheses = _safe_build_hypothesis_discovery(
            dataset_meta=dataset_meta,
            preferences=prefs,
            protocol=fallback_protocol,
        )

        return {
            "status": "partial",
            "protocol_name": "Exploratory protocol",
            "globals": fallback_globals,
            "protocol": fallback_protocol,
            "notes": (fallback_notes or [])
            + ["ИИ недоступен или не вернул валидный JSON. Сформирован rules-based протокол."],
            "protocol_plan": protocol_plan,
            "column_selection_report": column_selection_report,
            "quality": quality,
            "critic": critic_payload,
            "usage": None,
            "design_review_confirmed": design_review_confirmed,
            "analysis_mode": analysis_mode,
            "cleaning_plan": cleaning_plan,
            "cohort_plan": cohort_plan,
            "report_spec": report_spec,
            "validation_policy": validation_policy,
            "multiplicity_policy": multiplicity_policy,
            "bootstrap_policy": bootstrap_policy,
            "hypotheses": hypotheses,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI plan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать план анализа: {str(e)}")

# --- Endpoints ---

@router.post("/mixed-effects", response_model=Dict[str, Any])
async def run_mixed_effects(request: MixedEffectsRequest):
    """
    Run Linear Mixed Model with Time×Group interaction.
    
    Supports random intercept and random slope models with covariates.
    Memory-optimized for large longitudinal datasets.
    """
    try:
        # Load dataset
        df = await load_dataset_async(request.dataset_id)
        
        # Validate columns exist
        required_cols = [request.outcome, request.time_col, request.group_col, request.subject_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise HTTPException(status_code=400, detail=f"Столбцы не найдены: {missing_cols}")
        
        # Run analysis in separate process to avoid memory bloat
        result = await _run_in_process_pool(
            _run_mixed_effects_sync,
            df, request.outcome, request.time_col, request.group_col,
            request.subject_col, request.covariates, request.random_slope, request.alpha
        )
        
        # Force garbage collection
        gc.collect()
        
        native = convert_numpy_to_native(result)
        payload = (
            {"type": "mixed_effects", "method": {"id": "mixed_effects", "name": "Mixed Effects"}, **native}
            if isinstance(native, dict)
            else {"type": "mixed_effects", "value": native}
        )
        return normalize_analysis_result_v2(payload, method_id="mixed_effects", config={"engine": "python"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mixed effects analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить анализ со смешанными эффектами: {str(e)}")

@router.post("/clustered-correlation", response_model=Dict[str, Any])
async def run_clustered_correlation(request: ClusteredCorrelationRequest):
    """
    Run jYS-style hierarchical clustering on correlation matrix.
    
    Returns reordered correlation matrix, dendrogram, and cluster assignments.
    Memory-optimized for large variable sets.
    """
    try:
        # Load dataset
        df = await load_dataset_async(request.dataset_id)
        
        # Validate variables exist
        missing_vars = [var for var in request.variables if var not in df.columns]
        if missing_vars:
            raise HTTPException(status_code=400, detail=f"Переменные не найдены: {missing_vars}")
        
        # Limit variables for memory safety
        if len(request.variables) > 50:
            raise HTTPException(status_code=400, detail="Для кластеризации допускается не более 50 переменных")
        
        # Run analysis in separate process
        result = await _run_in_process_pool(
            _run_clustered_correlation_sync,
            df, request.variables, request.method, request.linkage_method,
            request.n_clusters, request.distance_threshold, request.show_p_values, request.alpha
        )
        
        gc.collect()
        
        native = convert_numpy_to_native(result)
        payload = (
            {
                "type": "clustered_correlation",
                "method": {"id": "clustered_correlation", "name": "Clustered Correlation"},
                **native,
            }
            if isinstance(native, dict)
            else {"type": "clustered_correlation", "value": native}
        )
        return normalize_analysis_result_v2(payload, method_id="clustered_correlation", config={"engine": "python"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clustered correlation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить кластеризованную корреляцию: {str(e)}")

@router.post("/protocol", response_model=Dict[str, Any])
async def run_protocol_v2(request: ProtocolV2Request):
    """
    Execute v2 analysis protocol with support for advanced methods.
    
    Supports mixed effects, clustered correlation, and all standard methods.
    """
    try:
        df = await load_dataset_async(request.dataset_id)
        
        method_id = request.protocol.get("method")
        
        # Advanced methods
        if method_id == "mixed_effects":
            outcome = request.protocol["target_column"]
            time_col = request.protocol["time_column"]
            group_col = request.protocol["group_column"]
            subject_col = request.protocol["subject_column"]
            covariates = request.protocol.get("covariates", [])
            random_slope = request.protocol.get("random_slopes", False)
            raw_engine = (
                request.protocol.get("engine")
                or request.protocol.get("stats_engine")
                or request.protocol.get("analysis_engine")
            )
            engine_name = normalize_engine_name(str(raw_engine)) if raw_engine is not None else "python"
            if engine_name not in {"python", "r"}:
                raise HTTPException(status_code=400, detail=f"Неподдерживаемый движок: {raw_engine}")
            if not is_engine_supported(method_id, engine_name):
                allowed = ", ".join(supported_engines(method_id))
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Метод {method_id} не поддерживает движок {engine_name}. "
                        f"Доступные движки: {allowed or 'python'}."
                    ),
                )
            
            if engine_name == "r":
                result = await run_analysis_async(
                    df,
                    "mixed_effects",
                    outcome,
                    group_col,
                    request.alpha,
                    group_col=group_col,
                    time_col=time_col,
                    subject_col=subject_col,
                    covariates=covariates,
                    random_slope=random_slope,
                    engine=engine_name,
                )
            else:
                result = await _run_in_process_pool(
                    _run_mixed_effects_sync,
                    df, outcome, time_col, group_col, subject_col, covariates, random_slope, request.alpha
                )
            gc.collect()
            native = convert_numpy_to_native(result)
            payload = (
                {"type": "mixed_effects", "method": {"id": "mixed_effects", "name": "Mixed Effects"}, **native}
                if isinstance(native, dict)
                else {"type": "mixed_effects", "value": native}
            )
            return {
                "status": "completed",
                "results": normalize_analysis_result_v2(payload, method_id="mixed_effects", config={"engine": engine_name}),
            }
        
        elif method_id == "clustered_correlation":
            variables = request.protocol.get("variables", [])
            method = request.protocol.get("method_id") or request.protocol.get("method") or "pearson"
            linkage_method = request.protocol.get("linkage_method", "ward")
            n_clusters = request.protocol.get("n_clusters")
            distance_threshold = request.protocol.get("distance_threshold")
            show_p_values = request.protocol.get("show_p_values", True)

            raw_engine = (
                request.protocol.get("engine")
                or request.protocol.get("stats_engine")
                or request.protocol.get("analysis_engine")
            )
            engine_name = normalize_engine_name(str(raw_engine)) if raw_engine is not None else "python"
            if engine_name not in {"python", "r"}:
                raise HTTPException(status_code=400, detail=f"Неподдерживаемый движок: {raw_engine}")
            if not is_engine_supported(method_id, engine_name):
                allowed = ", ".join(supported_engines(method_id))
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Метод {method_id} не поддерживает движок {engine_name}. "
                        f"Доступные движки: {allowed or 'python'}."
                    ),
                )

            if engine_name == "r":
                if len(variables) < 2:
                    raise HTTPException(status_code=400, detail="Для clustered_correlation требуется минимум 2 переменные")
                result = await run_analysis_async(
                    df,
                    "clustered_correlation",
                    str(variables[0]),
                    str(variables[1]),
                    request.alpha,
                    variables=variables,
                    method=method,
                    linkage_method=linkage_method,
                    n_clusters=n_clusters,
                    distance_threshold=distance_threshold,
                    show_p_values=show_p_values,
                    engine=engine_name,
                )
            else:
                result = await _run_in_process_pool(
                    _run_clustered_correlation_sync,
                    df, variables, method, linkage_method, n_clusters,
                    distance_threshold, show_p_values, request.alpha
                )
            gc.collect()
            native = convert_numpy_to_native(result)
            payload = (
                {
                    "type": "clustered_correlation",
                    "method": {"id": "clustered_correlation", "name": "Clustered Correlation"},
                    **native,
                }
                if isinstance(native, dict)
                else {"type": "clustered_correlation", "value": native}
            )
            return {
                "status": "completed",
                "results": normalize_analysis_result_v2(
                    payload,
                    method_id="clustered_correlation",
                    config={"engine": engine_name},
                ),
            }

        elif method_id == "responders":
            outcome_columns = request.protocol.get("outcome_columns")
            time_labels = request.protocol.get("time_labels")
            group_col = request.protocol.get("group") or request.protocol.get("group_column")
            subject_col = request.protocol.get("subject") or request.protocol.get("subject_column")
            threshold = request.protocol.get("threshold", 0.0)
            direction = request.protocol.get("direction", "decrease")
            baseline_label = request.protocol.get("baseline_label") or request.protocol.get("baseline_time")
            baseline_index = request.protocol.get("baseline_index")
            group_merge = request.protocol.get("group_merge") or request.protocol.get("merge_groups") or request.protocol.get("group_map")

            try:
                threshold_val = float(threshold)
            except Exception:
                threshold_val = 0.0

            raw_engine = (
                request.protocol.get("engine")
                or request.protocol.get("stats_engine")
                or request.protocol.get("analysis_engine")
            )
            engine_name = normalize_engine_name(str(raw_engine)) if raw_engine is not None else "python"
            if engine_name not in {"python", "r"}:
                raise HTTPException(status_code=400, detail=f"Неподдерживаемый движок: {raw_engine}")
            if not is_engine_supported(method_id, engine_name):
                allowed = ", ".join(supported_engines(method_id))
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Метод {method_id} не поддерживает движок {engine_name}. "
                        f"Доступные движки: {allowed or 'python'}."
                    ),
                )

            result = await _run_in_process_pool(
                _run_responders_sync,
                df,
                outcome_columns if isinstance(outcome_columns, list) else [],
                time_labels if isinstance(time_labels, list) else None,
                str(group_col or ""),
                subject_col if isinstance(subject_col, str) else None,
                threshold_val,
                str(direction or "decrease"),
                baseline_label if isinstance(baseline_label, str) else None,
                baseline_index if isinstance(baseline_index, int) else None,
                group_merge,
                request.alpha,
                engine_name,
            )
            gc.collect()

            native = convert_numpy_to_native(result)
            payload = (
                {"type": "responders", "method": {"id": "responders", "name": "Responders"}, **native}
                if isinstance(native, dict)
                else {"type": "responders", "value": native}
            )

            by_visit = payload.get("by_visit") if isinstance(payload.get("by_visit"), dict) else {}
            if by_visit:
                payload["conclusion"] = f"Responder-анализ выполнен для {len(by_visit)} визит(ов)."

            return {
                "status": "completed",
                "results": normalize_analysis_result_v2(
                    payload,
                    method_id="responders",
                    config={"engine": engine_name},
                ),
            }
        
        # Standard methods fallback
        elif method_id and method_id in STANDARD_METHODS:
            target_col = request.protocol.get("target_column")
            group_col = request.protocol.get("group_column")
            
            if target_col and group_col:
                result = await run_analysis_async(df, method_id, target_col, group_col, request.alpha)
                native = convert_numpy_to_native(result)
                payload = native if isinstance(native, dict) else {"value": native}
                return {
                    "status": "completed",
                    "results": normalize_analysis_result_v2(payload, method_id=method_id, config=request.protocol),
                }
        
        raise HTTPException(status_code=400, detail=f"Метод {method_id} не реализован")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Protocol execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить протокол: {str(e)}")

# --- Helper Functions ---

async def load_dataset_async(dataset_id: str) -> pd.DataFrame:
    """Load dataset asynchronously with memory limits."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,  # Use default executor
        get_dataframe, dataset_id, DATA_DIR
    )


async def _run_in_process_pool(func, *args):
    """Run function in process pool with one automatic pool-recreate retry."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(_get_analysis_executor(), func, *args)
    except RuntimeError as e:
        msg = str(e).lower()
        transient_shutdown = (
            "cannot schedule new futures after shutdown" in msg
            or "after shutdown" in msg
        )
        if not transient_shutdown:
            raise
        logger.warning("analysis process pool was shut down; recreating and retrying once")
        global analysis_executor
        analysis_executor = ProcessPoolExecutor(max_workers=2)
        return await loop.run_in_executor(_get_analysis_executor(), func, *args)


def _run_analysis_sync(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, alpha: float, extra_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    return run_analysis(df, method_id, col_a, col_b, alpha=alpha, **(extra_kwargs or {}))


async def run_analysis_async(
    df: pd.DataFrame,
    method_id: str,
    col_a: str,
    col_b: str,
    alpha: float,
    **kwargs,
) -> Dict[str, Any]:
    """Run analysis asynchronously with memory management."""
    return await _run_in_process_pool(
        _run_analysis_sync,
        df,
        method_id,
        col_a,
        col_b,
        alpha,
        kwargs,
    )

def _run_mixed_effects_sync(
    df: pd.DataFrame, outcome: str, time_col: str, group_col: str,
    subject_col: str, covariates: List[str], random_slope: bool, alpha: float
) -> Dict[str, Any]:
    """Synchronous mixed effects execution."""
    engine = MixedEffectsEngine(max_memory_mb=800)  # Conservative limit
    return engine.fit(df, outcome, time_col, group_col, subject_col, covariates, random_slope, alpha)

def _run_clustered_correlation_sync(
    df: pd.DataFrame, variables: List[str], method: str, linkage_method: str,
    n_clusters: Optional[int], distance_threshold: Optional[float],
    show_p_values: bool, alpha: float
) -> Dict[str, Any]:
    """Synchronous clustered correlation execution."""
    engine = ClusteredCorrelationEngine()
    return engine.analyze(
        df, variables, method, linkage_method, n_clusters,
        distance_threshold, show_p_values, alpha
    )


def _run_responders_sync(
    df: pd.DataFrame,
    outcome_columns: List[str],
    time_labels: Optional[List[str]],
    group_col: str,
    subject_col: Optional[str],
    threshold: float,
    direction: str,
    baseline_label: Optional[str],
    baseline_index: Optional[int],
    group_merge: Optional[Any],
    alpha: float,
    engine: Optional[str] = None,
) -> Dict[str, Any]:
    if not group_col or group_col not in df.columns:
        return {"type": "responders", "error": "Missing group column"}
    if not isinstance(outcome_columns, list) or len(outcome_columns) < 2:
        return {"type": "responders", "error": "Insufficient outcome columns"}

    cols = [c for c in outcome_columns if isinstance(c, str) and c in df.columns]
    if len(cols) < 2:
        return {"type": "responders", "error": "Insufficient outcome columns"}

    labels = time_labels if isinstance(time_labels, list) and len(time_labels) == len(cols) else [str(i) for i in range(len(cols))]
    baseline_idx = 0
    if isinstance(baseline_index, int) and 0 <= baseline_index < len(cols):
        baseline_idx = int(baseline_index)
    elif isinstance(baseline_label, str) and baseline_label in labels:
        baseline_idx = int(labels.index(baseline_label))

    baseline_col = str(cols[baseline_idx])
    baseline_time = str(labels[baseline_idx])

    mapping: Dict[str, str] = {}
    buckets: List[Dict[str, Any]] = []
    if isinstance(group_merge, dict):
        for k, v in group_merge.items():
            if k is None or v is None:
                continue
            mapping[str(k)] = str(v)
    elif isinstance(group_merge, list):
        for item in group_merge:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            values = item.get("values")
            if isinstance(name, str) and isinstance(values, list) and values:
                buckets.append({"name": name, "values": {str(v) for v in values if v is not None}})

    def _map_group(value: Any) -> str:
        raw = "-" if value is None else str(value)
        if raw in mapping:
            return mapping[raw]
        for b in buckets:
            if raw in b.get("values", set()):
                return str(b.get("name"))
        return raw

    visits: List[Dict[str, str]] = []
    for idx, col in enumerate(cols):
        if idx == baseline_idx:
            continue
        visits.append({"time": str(labels[idx]), "column": str(col)})
    if not visits:
        return {"type": "responders", "error": "No follow-up visits"}

    direction_norm = str(direction or "decrease").strip().lower()
    if direction_norm not in {"decrease", "increase"}:
        direction_norm = "decrease"

    by_visit: Dict[str, Any] = {}
    for visit in visits:
        visit_time = visit["time"]
        visit_col = visit["column"]
        use_cols = [group_col, baseline_col, visit_col]
        if isinstance(subject_col, str) and subject_col in df.columns:
            use_cols = [subject_col, *use_cols]

        tmp = df[use_cols].copy()
        tmp[baseline_col] = pd.to_numeric(tmp[baseline_col], errors="coerce")
        tmp[visit_col] = pd.to_numeric(tmp[visit_col], errors="coerce")
        tmp = tmp.dropna(subset=[group_col, baseline_col, visit_col])
        if tmp.empty:
            continue

        tmp["__group__"] = tmp[group_col].map(_map_group)
        if direction_norm == "increase":
            tmp["__delta__"] = tmp[visit_col] - tmp[baseline_col]
        else:
            tmp["__delta__"] = tmp[baseline_col] - tmp[visit_col]
        tmp["__responder__"] = (tmp["__delta__"] >= float(threshold)).astype(int)

        group_stats: Dict[str, Any] = {}
        for g, sub in tmp.groupby("__group__", dropna=False):
            total = int(len(sub))
            responders = int(sub["__responder__"].sum())
            rate = (responders / total) if total else 0.0
            group_stats[str(g)] = {"responders": responders, "total": total, "rate": rate}

        test_res = None
        groups_present = [k for k, v in group_stats.items() if isinstance(v, dict) and int(v.get("total", 0)) > 0]
        if len(groups_present) >= 2:
            try:
                test_res = run_analysis(
                    tmp[["__group__", "__responder__"]].copy(),
                    "chi_square",
                    "__group__",
                    "__responder__",
                    alpha=alpha,
                    engine=engine,
                )
            except Exception:
                test_res = None

        by_visit[str(visit_time)] = {
            "visit": str(visit_time),
            "baseline": baseline_time,
            "threshold": float(threshold),
            "direction": direction_norm,
            "groups": group_stats,
            "test": test_res,
        }

    if not by_visit:
        return {"type": "responders", "error": "No responder results computed"}

    test_p: List[float] = []
    for item in by_visit.values():
        test = item.get("test") if isinstance(item, dict) else None
        if not isinstance(test, dict):
            continue
        try:
            p = float(test.get("p_value"))
            if math.isfinite(p):
                test_p.append(p)
        except Exception:
            continue

    result: Dict[str, Any] = {
        "type": "responders",
        "group_column": group_col,
        "subject_column": subject_col,
        "baseline": {"time": baseline_time, "column": baseline_col},
        "visits": visits,
        "threshold": float(threshold),
        "direction": direction_norm,
        "group_merge": group_merge if group_merge is not None else None,
        "by_visit": by_visit,
    }
    if test_p:
        result["p_value"] = float(min(test_p))
        result["significant"] = bool(result["p_value"] < alpha)
    else:
        result["p_value"] = None
        result["significant"] = False
    return result

# --- Protocol Execution Endpoints ---

@router.post("/analysis/execute", response_model=Dict[str, Any])
async def execute_protocol(request: ExecuteProtocolRequest, background_tasks: BackgroundTasks):
    """
    Execute analysis protocol with batch processing.
    
    Runs multiple statistical tests in sequence with memory management.
    Supports mixed effects, clustered correlation, and all standard methods.
    """
    try:
        execute_started_at = datetime.utcnow().isoformat() + "Z"
        execute_started_perf = time.perf_counter()
        df = await load_dataset_async(request.dataset_id)
        globals_in = request.globals if isinstance(request.globals, dict) else {}
        protocol_plan_in = request.protocol_plan if isinstance(request.protocol_plan, dict) else {}
        column_selection_report = (
            request.column_selection_report if isinstance(request.column_selection_report, dict) else None
        )
        if not isinstance(column_selection_report, dict):
            column_selection_report = (
                protocol_plan_in.get("column_selection_report")
                if isinstance(protocol_plan_in.get("column_selection_report"), dict)
                else None
            )
        if not isinstance(column_selection_report, dict):
            column_selection_report = (
                globals_in.get("column_selection_report")
                if isinstance(globals_in.get("column_selection_report"), dict)
                else None
            )
        if not isinstance(column_selection_report, dict):
            globals_protocol_plan = globals_in.get("protocol_plan") if isinstance(globals_in.get("protocol_plan"), dict) else {}
            column_selection_report = (
                globals_protocol_plan.get("column_selection_report")
                if isinstance(globals_protocol_plan.get("column_selection_report"), dict)
                else None
            )
        if not isinstance(column_selection_report, dict):
            column_selection_report = {}
        protocol_plan_in = {**protocol_plan_in, "column_selection_report": column_selection_report}
        analysis_mode = _normalize_analysis_mode(globals_in.get("analysis_mode") or globals_in.get("mode"))
        validation_policy = _resolve_runtime_validation_policy(globals_in, analysis_mode=analysis_mode)
        multiplicity_policy = _resolve_multiplicity_policy(globals_in, analysis_mode=analysis_mode)
        bootstrap_policy = _resolve_bootstrap_policy(globals_in, analysis_mode=analysis_mode)
        llm_benchmark = _normalize_llm_benchmark_payload(globals_in.get("llm_benchmark"))
        publication_mode = analysis_mode == "publication"
        globals_patch: Dict[str, Any] = {}
        if "analysis_mode" not in globals_in:
            globals_patch["analysis_mode"] = analysis_mode
        if "mode" not in globals_in:
            globals_patch["mode"] = analysis_mode
        if "validation_profile" not in globals_in:
            globals_patch["validation_profile"] = validation_policy.get("profile")
        if "multiplicity_correction" not in globals_in:
            globals_patch["multiplicity_correction"] = multiplicity_policy.get("correction")
        if "post_hoc_correction" not in globals_in:
            globals_patch["post_hoc_correction"] = multiplicity_policy.get("post_hoc_correction")
        if "bootstrap_ci" not in globals_in:
            globals_patch["bootstrap_ci"] = bool(bootstrap_policy.get("enabled"))
        if "bootstrap_samples" not in globals_in:
            globals_patch["bootstrap_samples"] = int(bootstrap_policy.get("samples") or DEFAULT_BOOTSTRAP_SAMPLES)
        if "bootstrap_ci_level" not in globals_in:
            globals_patch["bootstrap_ci_level"] = float(bootstrap_policy.get("ci_level") or 0.95)
        if globals_patch:
            globals_in = {**globals_in, **globals_patch}
        globals_in["multiplicity_correction"] = _normalize_correction(
            globals_in.get("multiplicity_correction")
        ) or str(multiplicity_policy.get("correction") or "fdr_bh")
        globals_in["post_hoc_correction"] = _normalize_correction(
            globals_in.get("post_hoc_correction")
        ) or str(multiplicity_policy.get("post_hoc_correction") or globals_in.get("multiplicity_correction"))
        globals_in["bootstrap_ci"] = _as_bool(globals_in.get("bootstrap_ci"), default=False)
        globals_in["bootstrap_samples"] = _normalize_bootstrap_samples(
            globals_in.get("bootstrap_samples"),
            default=DEFAULT_BOOTSTRAP_SAMPLES,
        )
        try:
            globals_in["bootstrap_ci_level"] = float(globals_in.get("bootstrap_ci_level") or 0.95)
        except Exception:
            globals_in["bootstrap_ci_level"] = 0.95
        multiplicity_policy = _resolve_multiplicity_policy(globals_in, analysis_mode=analysis_mode)
        multiplicity_policy_correction = _normalize_correction(multiplicity_policy.get("correction")) or "fdr_bh"
        multiplicity_policy_post_hoc = _normalize_correction(multiplicity_policy.get("post_hoc_correction")) or (
            "none" if multiplicity_policy_correction == "none" else multiplicity_policy_correction
        )
        multiplicity_policy_enabled = bool(multiplicity_policy_correction != "none")
        multiplicity_policy_applied_steps: List[str] = []
        multiplicity_policy_ignored_steps: List[str] = []
        bootstrap_policy = _resolve_bootstrap_policy(globals_in, analysis_mode=analysis_mode)
        bootstrap_policy_enabled = bool(bootstrap_policy.get("enabled"))
        bootstrap_policy_samples = _normalize_bootstrap_samples(
            bootstrap_policy.get("samples"),
            default=DEFAULT_BOOTSTRAP_SAMPLES,
        )
        bootstrap_policy_applied_steps: List[str] = []
        bootstrap_policy_ignored_steps: List[str] = []

        analysis_set_id_raw = globals_in.get("analysis_set_id") or globals_in.get("analysis_set")
        analysis_set_id = str(analysis_set_id_raw).strip() if analysis_set_id_raw is not None else ""
        analysis_set_enforce_raw = globals_in.get("analysis_set_enforce") or globals_in.get("analysis_set_apply")
        analysis_set_enforce = str(analysis_set_enforce_raw or "").strip().lower() or None
        analysis_set_strict = _as_bool(globals_in.get("analysis_set_strict"), default=True)

        require_design_review = bool(getattr(settings, "CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True))
        globals_design_review_confirmed = _as_bool(globals_in.get("design_confirmed"), default=False)
        design_review_artifact = load_design_review(DATA_DIR, request.dataset_id)
        design_review_artifact_exists = isinstance(design_review_artifact, dict)
        design_review_artifact_confirmed = _as_bool(
            design_review_artifact.get("confirmed") if design_review_artifact_exists else None,
            default=False,
        )
        design_review_confirmed = design_review_artifact_confirmed
        artifact_timestamp = design_review_artifact.get("confirmed_at") if design_review_artifact_exists else None
        design_review_timestamp = artifact_timestamp if isinstance(artifact_timestamp, str) else None
        design_review_confirmed_by = (
            design_review_artifact.get("confirmed_by")
            if design_review_artifact_exists and isinstance(design_review_artifact.get("confirmed_by"), str)
            else None
        )
        design_review_confirmed_source = (
            design_review_artifact.get("confirmed_source")
            if design_review_artifact_exists and isinstance(design_review_artifact.get("confirmed_source"), str)
            else None
        )
        allow_unconfirmed_design = _as_bool(globals_in.get("allow_unconfirmed_design"), default=False) or _as_bool(
            globals_in.get("advanced_mode"),
            default=False,
        )
        if publication_mode and not design_review_confirmed:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Publication mode требует подтверждённый backend-артефакт Design Review; "
                    "bypass через advanced_mode/allow_unconfirmed_design недоступен."
                ),
            )
        if require_design_review and not design_review_confirmed and not allow_unconfirmed_design:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Design Review не подтверждён в backend-артефакте датасета. Подтвердите дизайн перед выполнением "
                    "или включите advanced_mode/allow_unconfirmed_design для ручного обхода."
                ),
            )
        if design_review_confirmed and not design_review_timestamp:
            design_review_timestamp = datetime.utcnow().isoformat()
        warnings: List[str] = []
        if globals_design_review_confirmed and not design_review_confirmed:
            warnings.append(
                "Передан globals.design_confirmed=true, но backend-артефакт Design Review не подтверждён; используется состояние артефакта."
            )
        if not design_review_confirmed and allow_unconfirmed_design:
            warnings.append(
                "Design Review не подтверждён. Результаты могут не соответствовать ожидаемой структуре исследования."
            )
        elif not design_review_confirmed and not require_design_review:
            warnings.append(
                "Design Review не подтверждён, но проверка отключена конфигом CLINIMETRIA_REQUIRE_DESIGN_REVIEW."
            )
        protocol_steps = request.protocol if isinstance(request.protocol, list) else []
        protocol_len = len(protocol_steps)
        if protocol_len > MAX_EXECUTE_PROTOCOL_STEPS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Слишком длинный протокол: {protocol_len} шагов. "
                    f"Текущий hard-limit = {MAX_EXECUTE_PROTOCOL_STEPS} шагов."
                ),
            )
        if protocol_len > 2000:
            warnings.append(
                f"Очень длинный протокол ({protocol_len} шагов): ожидается длительный расчёт и большой объём артефактов."
            )
        if publication_mode:
            warnings.append("Publication mode включён: активированы строгие проверки reproducibility.")
            if not analysis_set_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Publication mode требует fixed cohort. Передайте globals.analysis_set_id "
                        "или сначала вызовите /api/v1/datasets/{dataset_id}/analysis_set/freeze."
                    ),
                )
            if not analysis_set_strict:
                raise HTTPException(
                    status_code=400,
                    detail="Publication mode требует globals.analysis_set_strict=true.",
                )

        analysis_set_artifact: Optional[Dict[str, Any]] = None
        analysis_set_covered_cols: Optional[set] = None
        df_models_fixed: Optional[pd.DataFrame] = None

        if analysis_set_id:
            analysis_set_artifact = load_analysis_set_artifact(DATA_DIR, request.dataset_id, analysis_set_id=analysis_set_id)
            if not isinstance(analysis_set_artifact, dict):
                raise HTTPException(
                    status_code=400,
                    detail=f"analysis_set_id не найден: {analysis_set_id}. Сначала заморозьте выборку для датасета.",
                )

            artifact_enforce = str(analysis_set_artifact.get("enforce") or "").strip().lower()
            if not analysis_set_enforce:
                analysis_set_enforce = artifact_enforce or "models"
            if analysis_set_enforce not in {"models", "all"}:
                analysis_set_enforce = "models"

            if publication_mode:
                fp_ok, fp_info = validate_analysis_set_fingerprint(
                    DATA_DIR,
                    request.dataset_id,
                    analysis_set_artifact,
                    df=df,
                )
                if not fp_ok:
                    mismatches = fp_info.get("mismatches") if isinstance(fp_info, dict) else None
                    mismatch_text = ", ".join([str(x) for x in (mismatches or [])]) or "unknown"
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Publication mode: fingerprint analysis_set не совпадает с текущим processed dataset "
                            f"({mismatch_text}). Перезаморозьте cohort."
                        ),
                    )

            req_cols = analysis_set_artifact.get("required_non_missing")
            imp_cols = analysis_set_artifact.get("impute_columns")
            req_cols_list = req_cols if isinstance(req_cols, list) else []
            imp_cols_list = imp_cols if isinstance(imp_cols, list) else []
            analysis_set_covered_cols = set([str(c) for c in [*req_cols_list, *imp_cols_list] if c is not None and str(c).strip()])

            try:
                df_models_fixed, analysis_set_apply_info = apply_analysis_set_to_df(df, analysis_set_artifact)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Не удалось применить analysis_set: {str(e)}")

            n_selected = int(analysis_set_artifact.get("n_selected") or len(df_models_fixed))
            mode_label = str(analysis_set_artifact.get("mode") or "").strip().lower() or "complete_case"
            warnings.append(
                f"Fixed cohort включён: analysis_set_id={analysis_set_id}, N={n_selected}, mode={mode_label}, enforce={analysis_set_enforce}, strict={analysis_set_strict}."
            )
            if isinstance(analysis_set_apply_info, dict):
                normalized_missing = int(analysis_set_apply_info.get("normalized_string_missing") or 0)
                if normalized_missing > 0:
                    warnings.append(f"analysis_set: нормализовано строковых пропусков: {normalized_missing}.")
            if analysis_set_enforce == "models":
                warnings.append("Fixed cohort применяется только к linear_regression/logistic_regression шагам.")
            else:
                warnings.append("Fixed cohort применяется ко всем шагам протокола (возможны дополнительные dropna внутри методов).")

            if analysis_set_strict and analysis_set_covered_cols is not None:
                required_for_models: set = set()
                missing_coverage: set = set()
                for raw_step in request.protocol:
                    if not isinstance(raw_step, dict):
                        continue
                    method_tmp = _canonical_method_id(raw_step.get("method"))
                    if method_tmp not in {"linear_regression", "logistic_regression"}:
                        continue
                    raw_cfg = raw_step.get("config")
                    cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
                    if globals_in:
                        cfg = {**globals_in, **cfg}

                    outcome = cfg.get("outcome") or cfg.get("target")
                    group = cfg.get("group")
                    predictors = cfg.get("predictors")
                    covariates = cfg.get("covariates")
                    predictors_list = predictors if isinstance(predictors, list) else []
                    covariates_list = covariates if isinstance(covariates, list) else []

                    cols = []
                    for c in [outcome, group, *predictors_list, *covariates_list]:
                        if isinstance(c, str) and c.strip():
                            cols.append(c.strip())
                    if cols:
                        required_for_models.update(cols)

                if required_for_models:
                    missing_coverage = set([c for c in required_for_models if c not in analysis_set_covered_cols])
                    if missing_coverage:
                        missing_sorted = ", ".join(sorted(missing_coverage, key=lambda x: str(x)))
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Фиксированная выборка (analysis_set) не покрывает колонки, которые используются в моделях: "
                                f"{missing_sorted}. Пересоздайте analysis_set, добавив их в required_non_missing (complete_case) "
                                "или в impute_columns (simple_impute)."
                            ),
                        )
                    if df_models_fixed is not None:
                        still_missing = [c for c in required_for_models if c in df_models_fixed.columns and bool(df_models_fixed[c].isna().any())]
                        if still_missing:
                            still_missing_sorted = ", ".join(sorted(still_missing, key=lambda x: str(x)))
                            raise HTTPException(
                                status_code=400,
                                detail=(
                                    "После применения analysis_set в моделях остались пропуски в колонках: "
                                    f"{still_missing_sorted}. Используйте simple_impute или пересоздайте выборку."
                                ),
                            )
        
        results = []
        errors = []
        results_map: Dict[str, Any] = {}
        step_meta_map: Dict[str, Any] = {}
        normalized_steps: List[Dict[str, Any]] = []
        runtime_steps: List[Dict[str, Any]] = []
        validator_enabled = bool(validation_policy.get("validator_enabled"))
        validator_strict = bool(validation_policy.get("validator_strict"))
        protocol_validation_steps: List[Dict[str, Any]] = []
        protocol_validation_global_errors: List[Dict[str, Any]] = []
        seen_step_ids: set = set()
        dataset_rows = int(len(df))
        dataset_cols = int(len(df.columns))

        def _append_run_error(step_id: str, method: str, message: str) -> None:
            msg = str(message or "").strip()
            if not msg:
                return
            for item in errors:
                if (
                    isinstance(item, dict)
                    and str(item.get("step_id") or "") == str(step_id)
                    and str(item.get("error") or "") == msg
                ):
                    return
            errors.append({"step_id": str(step_id), "method": str(method), "error": msg})

        def _record_runtime_step(
            *,
            step_id: str,
            method: str,
            status: str,
            started_perf: float,
            row_count: Optional[int],
            engine: Optional[str],
            analysis_set_applied: bool,
            error: Optional[str] = None,
        ) -> None:
            row_value: Optional[int] = None
            if isinstance(row_count, (int, float)):
                try:
                    row_value = max(0, int(row_count))
                except Exception:
                    row_value = None

            runtime_steps.append(
                {
                    "step_id": str(step_id),
                    "method": str(method),
                    "status": str(status or "unknown"),
                    "elapsed_ms": _runtime_elapsed_ms(started_perf),
                    "rows": row_value,
                    "engine": str(engine or "python").strip().lower() or "python",
                    "analysis_set_applied": bool(analysis_set_applied),
                    "error": (str(error).strip()[:500] if isinstance(error, str) and str(error).strip() else None),
                }
            )

        for step in protocol_steps:
            step_started_perf = time.perf_counter()
            method_id = _canonical_method_id(step.get("method"))
            raw_config = step.get("config", {})
            config = raw_config if isinstance(raw_config, dict) else {}
            step_id = step.get("id", f"step_{len(normalized_steps) + 1}")
            if globals_in:
                config = {**globals_in, **config}
            raw_has_bootstrap_ci = isinstance(raw_config, dict) and "bootstrap_ci" in raw_config
            raw_has_bootstrap_samples = isinstance(raw_config, dict) and "bootstrap_samples" in raw_config
            raw_has_bootstrap = raw_has_bootstrap_ci or raw_has_bootstrap_samples
            raw_has_multiplicity_correction = isinstance(raw_config, dict) and "multiplicity_correction" in raw_config
            raw_has_post_hoc_correction = isinstance(raw_config, dict) and "post_hoc_correction" in raw_config
            raw_has_multiplicity = raw_has_multiplicity_correction or raw_has_post_hoc_correction
            method_supports_bootstrap = _method_supports_bootstrap(method_id)
            if method_supports_bootstrap:
                if bootstrap_policy_enabled and not raw_has_bootstrap_ci:
                    config["bootstrap_ci"] = True
                if bootstrap_policy_enabled and not raw_has_bootstrap_samples:
                    config["bootstrap_samples"] = int(bootstrap_policy_samples)
                if "bootstrap_ci" in config:
                    config["bootstrap_ci"] = _as_bool(config.get("bootstrap_ci"), default=False)
                if "bootstrap_samples" in config:
                    config["bootstrap_samples"] = _normalize_bootstrap_samples(
                        config.get("bootstrap_samples"),
                        default=bootstrap_policy_samples,
                    )
                if bootstrap_policy_enabled and not raw_has_bootstrap:
                    bootstrap_policy_applied_steps.append(str(step_id))
            else:
                if ("bootstrap_ci" in config) or ("bootstrap_samples" in config):
                    bootstrap_policy_ignored_steps.append(str(step_id))
                config.pop("bootstrap_ci", None)
                config.pop("bootstrap_samples", None)
            method_supports_multiplicity = _method_supports_multiplicity(method_id)
            if method_supports_multiplicity:
                multiplicity_applied = False
                if method_id in MULTIPLICITY_BATCH_METHODS:
                    if not raw_has_multiplicity_correction:
                        config["multiplicity_correction"] = multiplicity_policy_correction
                        multiplicity_applied = True
                    if "multiplicity_correction" in config:
                        config["multiplicity_correction"] = (
                            _normalize_correction(config.get("multiplicity_correction")) or multiplicity_policy_correction
                        )
                if method_id in MULTIPLICITY_POSTHOC_METHODS:
                    if not raw_has_post_hoc_correction:
                        config["post_hoc_correction"] = multiplicity_policy_post_hoc
                        multiplicity_applied = multiplicity_applied or bool(multiplicity_policy_post_hoc != "none")
                    if "post_hoc_correction" in config:
                        config["post_hoc_correction"] = (
                            _normalize_correction(config.get("post_hoc_correction")) or multiplicity_policy_post_hoc
                        )
                if multiplicity_policy_enabled and multiplicity_applied:
                    multiplicity_policy_applied_steps.append(str(step_id))
            else:
                if multiplicity_policy_enabled or raw_has_multiplicity:
                    multiplicity_policy_ignored_steps.append(str(step_id))
                config.pop("multiplicity_correction", None)
                config.pop("post_hoc_correction", None)
            engine_pref = config.get("engine") or config.get("stats_engine") or config.get("analysis_engine")
            if engine_pref and "engine" not in config:
                config["engine"] = engine_pref
            if engine_pref is not None and str(engine_pref).strip():
                engine_name = normalize_engine_name(str(engine_pref))
                if engine_name not in {"python", "r"}:
                    raise HTTPException(status_code=400, detail=f"Неподдерживаемый движок: {engine_pref}")
                config["engine"] = engine_name
                if not is_engine_supported(method_id, engine_name):
                    allowed = ", ".join(supported_engines(method_id))
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Метод {method_id} не поддерживает движок {engine_name}. "
                            f"Доступные движки: {allowed or 'python'}."
                        ),
                    )
            step_engine_name = str(config.get("engine") or "python").strip().lower() or "python"
            df_step = df
            analysis_set_applied = False
            if analysis_set_artifact is not None and df_models_fixed is not None:
                if analysis_set_enforce == "all":
                    df_step = df_models_fixed
                    analysis_set_applied = True
                elif analysis_set_enforce == "models" and method_id in {"linear_regression", "logistic_regression"}:
                    df_step = df_models_fixed
                    analysis_set_applied = True

            where = raw_config.get("filter") if isinstance(raw_config, dict) else None
            if where is None:
                where = step.get("filter")
            if where is not None:
                if not isinstance(where, dict):
                    raise ValueError("filter должен быть объектом")
                col = where.get("col") or where.get("column")
                if not col or not isinstance(col, str):
                    raise ValueError("filter.col обязателен")
                if col not in df_step.columns:
                    raise ValueError(f"Колонка фильтра не найдена: {col}")

                op = (where.get("op") or where.get("operator") or "=")
                op = str(op).strip().lower()

                if "values" in where and isinstance(where.get("values"), list):
                    values = where.get("values")
                    if op in {"in", "==", "=", "eq"}:
                        df_step = df_step[df_step[col].isin(values)]
                    elif op in {"not_in", "nin", "!in"}:
                        df_step = df_step[~df_step[col].isin(values)]
                    else:
                        raise ValueError(f"Неподдерживаемый оператор для values: {op}")
                elif "value" in where:
                    value = where.get("value")
                    if op in {"==", "=", "eq"}:
                        df_step = df_step[df_step[col] == value]
                    elif op in {"!=", "neq", "ne"}:
                        df_step = df_step[df_step[col] != value]
                    elif op in {">", "gt"}:
                        df_step = df_step[df_step[col] > value]
                    elif op in {">=", "gte"}:
                        df_step = df_step[df_step[col] >= value]
                    elif op in {"<", "lt"}:
                        df_step = df_step[df_step[col] < value]
                    elif op in {"<=", "lte"}:
                        df_step = df_step[df_step[col] <= value]
                    elif op in {"in"}:
                        df_step = df_step[df_step[col].isin([value])]
                    else:
                        raise ValueError(f"Неподдерживаемый оператор: {op}")
                else:
                    raise ValueError("filter.value или filter.values обязателен")
            step_row_count = int(len(df_step))

            normalized_step = dict(step) if isinstance(step, dict) else {"method": method_id}
            normalized_step["id"] = step_id
            normalized_step["method"] = method_id
            normalized_step["config"] = config
            if where is not None:
                normalized_step["filter"] = where
            step_meta_map[str(step_id)] = {
                "id": step_id,
                "method": method_id,
                "config": config if isinstance(config, dict) else {},
                "filter": where,
                "title": step.get("title") or step.get("name") or step.get("label"),
                "task": (config.get("task") if isinstance(config, dict) else None) or step.get("task"),
                "analysis_set_applied": bool(analysis_set_applied),
                "analysis_set_id": analysis_set_id if analysis_set_applied else None,
                "analysis_set_n": int(len(df_step)) if analysis_set_applied else None,
                "analysis_set_mode": (
                    str(analysis_set_artifact.get("mode") or "").strip()
                    if analysis_set_applied and isinstance(analysis_set_artifact, dict)
                    else None
                ),
            }
            normalized_steps.append(normalized_step)

            step_id_key = str(step_id)
            if step_id_key in seen_step_ids:
                dup_message = f"Duplicate step id: {step_id_key}. IDs must be unique."
                protocol_validation_global_errors.append(
                    {"code": "duplicate_step_id", "step_id": step_id_key, "message": dup_message}
                )
                protocol_validation_steps.append(
                    {
                        "step_id": step_id_key,
                        "method": method_id,
                        "status": "failed",
                        "errors": [dup_message],
                        "warnings": [],
                        "checks": [{"check": "duplicate_step_id"}],
                    }
                )
                step_meta_map[step_id_key]["validator"] = {"status": "failed", "errors": [dup_message]}
                _append_run_error(step_id_key, "validator", dup_message)
                _record_runtime_step(
                    step_id=step_id_key,
                    method=method_id,
                    status="blocked_duplicate_step_id",
                    started_perf=step_started_perf,
                    row_count=step_row_count,
                    engine=step_engine_name,
                    analysis_set_applied=analysis_set_applied,
                    error=dup_message,
                )
                continue
            seen_step_ids.add(step_id_key)

            if validator_enabled:
                step_validation = validate_protocol_step(
                    normalized_step,
                    df_step,
                    alpha=float(request.alpha),
                )
                protocol_validation_steps.append(step_validation)
                step_meta_map[step_id_key]["validator"] = {
                    "status": step_validation.get("status"),
                    "errors": step_validation.get("errors"),
                    "warnings": step_validation.get("warnings"),
                }
                if str(step_validation.get("status") or "").strip().lower() != "passed":
                    step_errors = step_validation.get("errors") if isinstance(step_validation.get("errors"), list) else []
                    if step_errors:
                        for msg in step_errors:
                            _append_run_error(step_id_key, "validator", str(msg))
                    else:
                        _append_run_error(step_id_key, "validator", "Protocol validator failed for step.")
                    if validator_strict:
                        _record_runtime_step(
                            step_id=step_id_key,
                            method=method_id,
                            status="blocked_by_validator",
                            started_perf=step_started_perf,
                            row_count=step_row_count,
                            engine=step_engine_name,
                            analysis_set_applied=analysis_set_applied,
                            error="; ".join([str(msg) for msg in step_errors]) if step_errors else "Protocol validator failed for step.",
                        )
                        continue
                    warnings.append(
                        f"Validator warning on step {step_id_key}: "
                        + "; ".join([str(msg) for msg in step_errors[:3]])
                    )
            else:
                step_meta_map[step_id_key]["validator"] = {"status": "skipped"}
            
            step_runtime_status = "completed"
            step_runtime_error: Optional[str] = None
            try:
                # Registry-first dispatch for extracted executors.
                # Existing elif-chain below stays as backward-compatible fallback.
                executor_fn = get_executor(method_id)
                if executor_fn is not None and not is_engine_method(method_id):
                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    try:
                        payload = executor_fn(
                            df_step,
                            config,
                            request.alpha,
                            runtime_kwargs=runtime_kwargs,
                        )
                    except TypeError:
                        payload = executor_fn(df_step, config, request.alpha)

                    if asyncio.iscoroutine(payload):
                        payload = await payload

                    payload = convert_numpy_to_native(payload)
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload
                    continue

                # Advanced methods
                if method_id == "mixed_effects":
                    from app.stats.executors.mixed_effects import execute_mixed_effects

                    payload = await execute_mixed_effects(df_step, config, request.alpha)

                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": payload
                    })
                    results_map[step_id] = payload
                
                elif method_id == "clustered_correlation":
                    variables = config.get("variables", [])
                    method = config.get("method") or config.get("method_id") or "pearson"
                    linkage_method = config.get("linkage_method", "ward")
                    n_clusters = config.get("n_clusters")
                    distance_threshold = config.get("distance_threshold")
                    show_p_values = config.get("show_p_values", True)

                    engine_mode = str(config.get("engine") or "").strip().lower()
                    if engine_mode in {"r", "r_engine", "rstats"}:
                        if not isinstance(variables, list) or len(variables) < 2:
                            raise ValueError("clustered_correlation требует минимум 2 переменные")
                        result = await run_analysis_async(
                            df_step,
                            "clustered_correlation",
                            str(variables[0]),
                            str(variables[1]),
                            request.alpha,
                            variables=variables,
                            method=method,
                            linkage_method=linkage_method,
                            n_clusters=n_clusters,
                            distance_threshold=distance_threshold,
                            show_p_values=show_p_values,
                            engine=config.get("engine"),
                        )
                    else:
                        result = await _run_in_process_pool(
                            _run_clustered_correlation_sync,
                            df_step, variables, method, linkage_method, n_clusters,
                            distance_threshold, show_p_values, request.alpha
                        )
                    
                    payload = {
                        "type": "clustered_correlation",
                        "method": {"id": "clustered_correlation", "name": "Clustered Correlation"},
                        **convert_numpy_to_native(result)
                    }

                    n_vars = payload.get("n_variables")
                    n_clusters_out = payload.get("n_clusters")
                    if isinstance(n_vars, (int, float)) and isinstance(n_clusters_out, (int, float)):
                        payload["conclusion"] = f"Обнаружено {int(n_clusters_out)} кластер(ов) среди {int(n_vars)} переменных."

                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": payload
                    })
                    results_map[step_id] = payload

                elif method_id == "responders":
                    outcome_columns = config.get("outcome_columns") or config.get("outcomes")
                    time_labels = config.get("time_labels")
                    group_col = config.get("group") or config.get("group_column")
                    subject_col = config.get("subject") or config.get("subject_column")
                    threshold = config.get("threshold", 0.0)
                    direction = config.get("direction", "decrease")
                    baseline_label = config.get("baseline_label") or config.get("baseline_time")
                    baseline_index = config.get("baseline_index")
                    group_merge = config.get("group_merge") or config.get("merge_groups") or config.get("group_map")

                    if not isinstance(outcome_columns, list) or len(outcome_columns) < 2:
                        raise ValueError("responders требует outcome_columns минимум из 2 колонок")
                    if not isinstance(group_col, str) or not group_col:
                        raise ValueError("responders требует group/group_column")

                    try:
                        threshold_val = float(threshold)
                    except Exception:
                        threshold_val = 0.0

                    result = await _run_in_process_pool(
                        _run_responders_sync,
                        df_step,
                        outcome_columns,
                        time_labels if isinstance(time_labels, list) else None,
                        group_col,
                        subject_col if isinstance(subject_col, str) else None,
                        threshold_val,
                        str(direction or "decrease"),
                        baseline_label if isinstance(baseline_label, str) else None,
                        baseline_index if isinstance(baseline_index, int) else None,
                        group_merge,
                        request.alpha,
                        config.get("engine"),
                    )

                    payload = {
                        "type": "responders",
                        "method": {"id": "responders", "name": "Responders"},
                        **convert_numpy_to_native(result)
                    }
                    by_visit = payload.get("by_visit") if isinstance(payload.get("by_visit"), dict) else {}
                    if by_visit:
                        payload["conclusion"] = f"Responder-анализ выполнен для {len(by_visit)} визит(ов)."

                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": payload
                    })
                    results_map[step_id] = payload

                elif method_id == "responder_analysis":
                    from app.stats.executors.responder_analysis import execute_responder_analysis

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    payload = execute_responder_analysis(df_step, config, request.alpha, runtime_kwargs=runtime_kwargs)
                    payload = convert_numpy_to_native(payload)
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "batch_analysis":
                    group = config.get("group")
                    targets = config.get("targets")
                    if not group or not isinstance(targets, list) or not targets:
                        raise ValueError("batch_analysis требует group и targets")

                    method_id_batch = config.get("method_id") or config.get("method") or "t_test_ind"
                    multiplicity = _normalize_correction(config.get("multiplicity_correction")) or "fdr_bh"
                    post_hoc = config.get("post_hoc")
                    post_hoc_correction = _normalize_correction(config.get("post_hoc_correction"))
                    auto_fallback = bool(config.get("auto_fallback", True))
                    alternative = config.get("alternative")
                    runtime_kwargs = _analysis_runtime_kwargs(config)

                    items = run_batch_analysis(
                        df_step,
                        targets,
                        group_col=group,
                        method_id=method_id_batch,
                        alpha=request.alpha,
                        auto_fallback=auto_fallback,
                        multiplicity_correction=multiplicity,
                        post_hoc=post_hoc,
                        post_hoc_correction=post_hoc_correction,
                        engine=config.get("engine"),
                        **({"alternative": alternative} if alternative else {}),
                        **runtime_kwargs,
                    )

                    payload = {
                        "type": "batch_analysis",
                        "method_id": method_id_batch,
                        "group": group,
                        "items": convert_numpy_to_native(items),
                        "multiplicity_correction": multiplicity,
                        "multiplicity_trace": _build_batch_multiplicity_trace(
                            items,
                            alpha=float(request.alpha),
                            correction=multiplicity,
                            scope="batch",
                        ),
                        "post_hoc": post_hoc,
                        "post_hoc_correction": post_hoc_correction,
                    }

                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "timepoint_batch_analysis":
                    split_by = config.get("split_by") or config.get("timepoint") or config.get("time")
                    group = config.get("group")
                    if not split_by or not group:
                        raise ValueError("timepoint_batch_analysis требует split_by и group")
                    if split_by not in df_step.columns:
                        raise ValueError(f"Колонка split_by не найдена: {split_by}")
                    if group not in df_step.columns:
                        raise ValueError(f"Колонка group не найдена: {group}")

                    targets = config.get("targets")
                    if not isinstance(targets, list) or not targets:
                        targets = [
                            str(c)
                            for c in df_step.columns
                            if c not in {split_by, group}
                            and hasattr(df_step[c], "dtype")
                            and pd.api.types.is_numeric_dtype(df_step[c])
                        ]
                    if not targets:
                        raise ValueError("Не найдены числовые показатели для timepoint_batch_analysis")

                    method_id_batch = config.get("method_id") or "kruskal"
                    multiplicity = _normalize_correction(config.get("multiplicity_correction")) or "fdr_bh"
                    post_hoc = config.get("post_hoc")
                    post_hoc_correction = _normalize_correction(config.get("post_hoc_correction"))
                    auto_fallback = bool(config.get("auto_fallback", True))
                    alternative = config.get("alternative")
                    runtime_kwargs = _analysis_runtime_kwargs(config)

                    slices: Dict[str, Any] = {}
                    for val in sorted(df_step[split_by].dropna().unique(), key=lambda x: str(x)):
                        sub_df = df_step[df_step[split_by] == val]
                        items = run_batch_analysis(
                            sub_df,
                            targets,
                            group_col=group,
                            method_id=method_id_batch,
                            alpha=request.alpha,
                            auto_fallback=auto_fallback,
                            multiplicity_correction=multiplicity,
                            post_hoc=post_hoc,
                            post_hoc_correction=post_hoc_correction,
                            engine=config.get("engine"),
                            **({"alternative": alternative} if alternative else {}),
                            **runtime_kwargs,
                        )
                        slices[str(val)] = {
                            "type": "batch_analysis",
                            "method_id": method_id_batch,
                            "group": group,
                            "items": convert_numpy_to_native(items),
                            "multiplicity_correction": multiplicity,
                            "multiplicity_trace": _build_batch_multiplicity_trace(
                                items,
                                alpha=float(request.alpha),
                                correction=multiplicity,
                                scope=f"timepoint:{val}",
                            ),
                            "post_hoc": post_hoc,
                            "post_hoc_correction": post_hoc_correction,
                        }

                    payload = {
                        "type": "timepoint_batch_analysis",
                        "method_id": method_id_batch,
                        "group": group,
                        "split_by": split_by,
                        "targets": targets,
                        "slices": slices,
                        "multiplicity_correction": multiplicity,
                        "multiplicity_trace_by_slice": {
                            str(k): (
                                v.get("multiplicity_trace")
                                if isinstance(v, dict)
                                else None
                            )
                            for k, v in slices.items()
                            if isinstance(v, dict)
                        },
                        "post_hoc": post_hoc,
                        "post_hoc_correction": post_hoc_correction,
                    }

                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "paired_wide":
                    from app.stats.executors.paired_wide import execute_paired_wide

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    payload = await execute_paired_wide(
                        df_step,
                        config,
                        request.alpha,
                        runtime_kwargs=runtime_kwargs,
                    )
                    payload = convert_numpy_to_native(payload)
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "delta_batch_analysis":
                    from app.stats.executors.delta_batch import execute_delta_batch_analysis

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    payload = await execute_delta_batch_analysis(
                        df_step,
                        config,
                        request.alpha,
                        runtime_kwargs=runtime_kwargs,
                    )
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "descriptive_compare":
                    target = config.get("target") or config.get("outcome")
                    group = config.get("group")
                    if not target or not group:
                        raise ValueError("Отсутствуют обязательные параметры для descriptive_compare")
                    table = compute_descriptive_compare(df_step, target, group)
                    payload = {"type": "table_1", "data": convert_numpy_to_native(table)}
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "auto":
                    outcome = config.get("outcome")
                    group = config.get("group")
                    is_paired = bool(config.get("is_paired", False))
                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    if not outcome or not group:
                        raise ValueError("Отсутствуют обязательные параметры для auto")

                    types = {
                        outcome: "numeric" if pd.api.types.is_numeric_dtype(df_step[outcome]) else "categorical",
                        group: "numeric" if pd.api.types.is_numeric_dtype(df_step[group]) else "categorical",
                    }
                    selected = select_test(df_step, outcome, group, types, is_paired=is_paired)
                    if not selected:
                        raise ValueError("Не удалось автоматически выбрать метод")

                    result = await run_analysis_async(
                        df_step,
                        selected,
                        outcome,
                        group,
                        request.alpha,
                        is_paired=is_paired,
                        **runtime_kwargs,
                    )

                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test", "auto_selected": selected})
                    payload = _ensure_method(payload, selected)
                    variables = {"target": outcome, "group": group}
                    if selected in {"pearson", "spearman", "kendall"}:
                        variables = {"target": outcome, "predictor": group}
                    payload = _maybe_add_conclusion(payload, variables)
                    results.append(
                        {
                            "step_id": step_id,
                            "method": selected,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "anova_twoway":
                    outcome = config.get("outcome") or config.get("target")
                    group1 = config.get("group1")
                    group2 = config.get("group2")
                    if not outcome or not group1 or not group2:
                        raise ValueError("Отсутствуют обязательные параметры для anova_twoway")

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        outcome,
                        group1,
                        request.alpha,
                        group1=group1,
                        group2=group2,
                        engine=config.get("engine"),
                    )

                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": outcome, "group": group1})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "rm_anova":
                    outcome_cols = config.get("outcome_cols")
                    subject_col = config.get("subject_col")
                    group_col = config.get("group_col")
                    if not isinstance(outcome_cols, list) or len(outcome_cols) < 2:
                        raise ValueError("outcome_cols требует минимум 2 колонки")
                    if not subject_col:
                        raise ValueError("subject_col обязателен для rm_anova")

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome_cols[0]),
                        str(subject_col),
                        request.alpha,
                        outcome_cols=outcome_cols,
                        subject_col=subject_col,
                        group_col=group_col,
                    )

                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome_cols[0]), "group": str(group_col or subject_col)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "friedman":
                    outcome_cols = config.get("outcome_cols")
                    if not isinstance(outcome_cols, list) or len(outcome_cols) < 3:
                        raise ValueError("outcome_cols требует минимум 3 колонки")

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome_cols[0]),
                        str(outcome_cols[1]),
                        request.alpha,
                        outcome_cols=outcome_cols,
                    )

                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome_cols[0]), "group": str(outcome_cols[1])})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload
                
                elif method_id == "survival_km":
                    outcome = config.get("outcome") or config.get("target")
                    event = config.get("event")
                    group = config.get("group")
                    if not outcome or not event:
                        raise ValueError("survival_km требует outcome/target и event")
                    extra = {}
                    if group:
                        extra["group_col"] = group
                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        outcome,
                        event,
                        request.alpha,
                        **extra,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": outcome, "group": str(group or event)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id in {"t_test_one", "bayes_t_test_one"}:
                    outcome = config.get("outcome") or config.get("target")
                    if not outcome:
                        raise ValueError(f"{method_id} требует outcome")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    method_kwargs: Dict[str, Any] = {
                        "outcome": str(outcome),
                        "test_value": config.get("test_value", 0.0),
                        "alternative": config.get("alternative"),
                        "engine": config.get("engine"),
                    }
                    method_kwargs.update(runtime_kwargs)

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        "",
                        request.alpha,
                        **method_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": "sample"})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id in {"bayes_t_test_ind", "bayes_t_test_rel", "bayes_correlation"}:
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group") or config.get("predictor")
                    if not outcome or not group:
                        raise ValueError(f"{method_id} требует outcome и group")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    method_kwargs: Dict[str, Any] = {
                        "outcome": str(outcome),
                        "group": str(group),
                        "alternative": config.get("alternative"),
                        "correlation_method": config.get("correlation_method"),
                        "engine": config.get("engine"),
                    }
                    method_kwargs.update(runtime_kwargs)

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        str(group),
                        request.alpha,
                        **method_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": str(group)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "time_series_analysis":
                    outcome = config.get("outcome") or config.get("target")
                    if not outcome:
                        raise ValueError("time_series_analysis требует outcome")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    method_kwargs: Dict[str, Any] = {
                        "outcome": str(outcome),
                        "time": config.get("time") or config.get("time_col"),
                        "seasonal_period": config.get("seasonal_period"),
                        "decompose_model": config.get("decompose_model"),
                        "acf_lags": config.get("acf_lags"),
                        "ljung_lags": config.get("ljung_lags"),
                        "forecast_horizon": config.get("forecast_horizon"),
                        "engine": config.get("engine"),
                    }
                    method_kwargs.update(runtime_kwargs)

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        "",
                        request.alpha,
                        **method_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "time_series"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": "time"})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "ancova":
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group") or config.get("group_col")
                    covariates = config.get("covariates")
                    if not outcome or not group:
                        raise ValueError("ancova требует outcome и group")
                    if not isinstance(covariates, list) or not covariates:
                        raise ValueError("ancova требует covariates (>=1)")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        str(group),
                        request.alpha,
                        covariates=[str(c) for c in covariates if c is not None],
                        group=str(group),
                        outcome=str(outcome),
                        engine=config.get("engine"),
                        **runtime_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": str(group)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id in {"pca", "efa", "kmeans", "hierarchical_clustering", "cronbach_alpha"}:
                    variables = config.get("variables")
                    if not isinstance(variables, list) or not variables:
                        raise ValueError(f"{method_id} требует variables")
                    if method_id in {"pca", "cronbach_alpha"} and len(variables) < 2:
                        raise ValueError(f"{method_id} требует минимум 2 переменные")
                    if method_id == "efa" and len(variables) < 3:
                        raise ValueError("efa требует минимум 3 переменные")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    primary = str(variables[0])
                    secondary = str(variables[1]) if len(variables) > 1 else ""

                    method_kwargs: Dict[str, Any] = {
                        "variables": [str(v) for v in variables if v is not None],
                        "engine": config.get("engine"),
                    }
                    for key in [
                        "scale",
                        "n_components",
                        "n_factors",
                        "rotation",
                        "n_clusters",
                        "k",
                        "random_state",
                        "linkage_method",
                        "linkage",
                        "distance_threshold",
                    ]:
                        if key in config:
                            method_kwargs[key] = config.get(key)
                    method_kwargs.update(runtime_kwargs)

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        primary,
                        secondary,
                        request.alpha,
                        **method_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    if method_id in {"kmeans", "hierarchical_clustering"}:
                        payload = _maybe_add_conclusion(payload, {"target": "clusters", "group": "variables"})
                    else:
                        payload = _maybe_add_conclusion(payload, {"target": primary, "group": "components"})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "shapiro_wilk":
                    outcome = config.get("outcome") or config.get("target")
                    if not outcome:
                        raise ValueError("shapiro_wilk требует outcome")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        "",
                        request.alpha,
                        outcome=str(outcome),
                        engine=config.get("engine"),
                        **runtime_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "assumption_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": "normality"})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "bland_altman":
                    from app.stats.executors.bland_altman import execute_bland_altman

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    payload = await execute_bland_altman(
                        df_step,
                        config,
                        request.alpha,
                        runtime_kwargs=runtime_kwargs,
                    )
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "icc":
                    outcome = config.get("outcome") or config.get("target")
                    subject_col = config.get("subject_col") or config.get("subject")
                    rater_col = config.get("rater_col") or config.get("rater")
                    if not outcome or not subject_col or not rater_col:
                        raise ValueError("icc требует outcome, subject_col и rater_col")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        str(rater_col),
                        request.alpha,
                        outcome=str(outcome),
                        subject_col=str(subject_col),
                        rater_col=str(rater_col),
                        icc_type=config.get("icc_type"),
                        engine=config.get("engine"),
                        **runtime_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": str(rater_col)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id in {"cohens_kappa", "mcnemar", "point_biserial"}:
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group") or config.get("predictor")
                    if not outcome or not group:
                        raise ValueError(f"{method_id} требует outcome и group")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    method_kwargs: Dict[str, Any] = {
                        "outcome": str(outcome),
                        "group": str(group),
                        "engine": config.get("engine"),
                    }
                    for key in ["rater_a", "rater_b", "before", "after", "exact"]:
                        if key in config:
                            method_kwargs[key] = config.get(key)
                    method_kwargs.update(runtime_kwargs)

                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        str(group),
                        request.alpha,
                        **method_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "group": str(group)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "cochran_q":
                    outcome_cols = config.get("outcome_cols") or config.get("variables") or config.get("targets")
                    if not isinstance(outcome_cols, list) or len(outcome_cols) < 3:
                        raise ValueError("cochran_q требует outcome_cols (>=3)")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    col_a = str(outcome_cols[0])
                    col_b = str(outcome_cols[1])
                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        col_a,
                        col_b,
                        request.alpha,
                        outcome_cols=[str(v) for v in outcome_cols if v is not None],
                        engine=config.get("engine"),
                        **runtime_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": col_a, "group": "conditions"})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                elif method_id == "partial_correlation":
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group") or config.get("predictor")
                    covariates = config.get("covariates")
                    if not outcome or not group:
                        raise ValueError("partial_correlation требует outcome и group")
                    if not isinstance(covariates, list) or not covariates:
                        raise ValueError("partial_correlation требует covariates (>=1)")

                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    result = await run_analysis_async(
                        df_step,
                        method_id,
                        str(outcome),
                        str(group),
                        request.alpha,
                        outcome=str(outcome),
                        group=str(group),
                        covariates=[str(c) for c in covariates if c is not None],
                        correlation_method=config.get("correlation_method"),
                        engine=config.get("engine"),
                        **runtime_kwargs,
                    )
                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                    payload = _ensure_method(payload, method_id)
                    payload = _maybe_add_conclusion(payload, {"target": str(outcome), "predictor": str(group)})
                    results.append(
                        {
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": payload,
                        }
                    )
                    results_map[step_id] = payload

                # Standard methods fallback
                elif method_id in STANDARD_METHODS or method_id == "anova_twoway":
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group")
                    predictors = config.get("predictors")
                    covariates = config.get("covariates")
                    post_hoc = config.get("post_hoc")
                    post_hoc_correction = config.get("post_hoc_correction")
                    alternative = config.get("alternative")
                    runtime_kwargs = _analysis_runtime_kwargs(config)
                    method_used = method_id
                    if method_id in {"pearson", "spearman", "kendall"}:
                        corr_method = runtime_kwargs.get("correlation_method")
                        if isinstance(corr_method, str) and corr_method in {"pearson", "spearman", "kendall"}:
                            method_used = corr_method

                    if method_id == "anova_twoway":
                        group1 = config.get("group1")
                        group2 = config.get("group2")
                        if not outcome or not group1 or not group2:
                            raise ValueError("anova_twoway требует outcome, group1 и group2")
                        result = await run_analysis_async(
                            df_step,
                            method_used,
                            outcome,
                            group1,
                            request.alpha,
                            group1=group1,
                            group2=group2,
                            engine=config.get("engine"),
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_used)
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "group1": group1, "group2": group2})
                        results.append(
                            {
                                "step_id": step_id,
                                "method": method_used,
                                "status": "completed",
                                "results": payload,
                            }
                        )
                        results_map[step_id] = payload
                        continue

                    if method_id in ["linear_regression", "logistic_regression", "bayes_linear_regression"]:
                        if not outcome:
                            raise ValueError(f"Отсутствуют обязательные параметры для {method_id}")
                        if not isinstance(predictors, list):
                            predictors = []
                        if not isinstance(covariates, list):
                            covariates = []
                        col_b = group or (predictors[0] if predictors else None)
                        if not col_b:
                            raise ValueError(f"Не указаны предикторы для {method_id}")

                        result = await run_analysis_async(
                            df_step,
                            method_used,
                            outcome,
                            col_b,
                            request.alpha,
                            predictors=predictors,
                            covariates=covariates,
                            show_or=bool(config.get("show_or", True)),
                            show_roc=bool(config.get("show_roc", True)),
                            one_vs_rest=bool(config.get("one_vs_rest", False)),
                            positive_label=config.get("positive_label"),
                            **runtime_kwargs,
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_used)
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "predictor": col_b})
                        results.append(
                            {
                                "step_id": step_id,
                                "method": method_used,
                                "status": "completed",
                                "results": payload,
                            }
                        )
                        results_map[step_id] = payload
                        continue

                    if outcome and group:
                        extra = {}
                        if method_id in {"anova", "anova_welch", "kruskal"}:
                            if post_hoc is not None:
                                extra["post_hoc"] = post_hoc
                            if post_hoc_correction is not None:
                                extra["post_hoc_correction"] = post_hoc_correction
                        if alternative is not None and method_used in {"t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon", "pearson", "spearman", "kendall"}:
                            extra["alternative"] = alternative
                        elif alternative is not None and method_used in {"chi_square"}:
                            pass

                        result = await run_analysis_async(
                            df_step,
                            method_used,
                            outcome,
                            group,
                            request.alpha,
                            is_paired=bool(config.get("is_paired", False)),
                            predictors=predictors,
                            **extra,
                            **runtime_kwargs,
                        )

                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_used)
                        variables = {"target": outcome, "group": group}
                        if method_used in {"pearson", "spearman", "kendall"}:
                            variables = {"target": outcome, "predictor": group}
                        payload = _maybe_add_conclusion(payload, variables)
                        results.append(
                            {
                                "step_id": step_id,
                                "method": method_used,
                                "status": "completed",
                                "results": payload,
                            }
                        )
                        results_map[step_id] = payload
                    else:
                        raise ValueError(f"Отсутствуют обязательные параметры для {method_id}")
                
                else:
                    raise ValueError(f"Метод {method_id} не реализован")
                
            except Exception as e:
                step_runtime_status = "failed"
                step_runtime_error = str(e)
                logger.error(f"Step {step_id} failed: {e}", exc_info=True)
                _append_run_error(str(step_id), str(method_id), str(e))
            finally:
                _record_runtime_step(
                    step_id=step_id_key,
                    method=method_id,
                    status=step_runtime_status,
                    started_perf=step_started_perf,
                    row_count=step_row_count,
                    engine=step_engine_name,
                    analysis_set_applied=analysis_set_applied,
                    error=step_runtime_error,
                )
                # Force garbage collection after each step.
                gc.collect()

        # Compute global descriptive stats for the report.
        global_desc: Dict[str, Any] = {}
        try:
            numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
            for col in numeric_cols[:60]:
                s = df[col].dropna()
                if s.empty:
                    continue
                q1 = float(s.quantile(0.25))
                q3 = float(s.quantile(0.75))
                global_desc[str(col)] = {
                    "n": int(len(s)),
                    "mean": float(s.mean()),
                    "std": float(s.std(ddof=1)) if len(s) > 1 else None,
                    "median": float(s.median()),
                    "q1": q1,
                    "q3": q3,
                    "iqr": q3 - q1,
                    "min": float(s.min()),
                    "max": float(s.max()),
                }
        except Exception:
            global_desc = {}

        results_map = normalize_results_map(results_map, step_meta=step_meta_map)
        results = normalize_results_list(results, step_meta=step_meta_map)
        applied_multiplicity_steps = sorted(list({str(v) for v in multiplicity_policy_applied_steps if str(v).strip()}))
        ignored_multiplicity_steps = sorted(list({str(v) for v in multiplicity_policy_ignored_steps if str(v).strip()}))
        multiplicity_policy_doc: Dict[str, Any] = {
            "enabled": bool(multiplicity_policy_enabled),
            "correction": multiplicity_policy_correction,
            "multiplicity_correction": multiplicity_policy_correction,
            "post_hoc_correction": multiplicity_policy_post_hoc,
            "analysis_mode": analysis_mode,
            "scope": "global_defaults",
            "methods": (
                [str(v) for v in (multiplicity_policy.get("methods") or []) if isinstance(v, str) and v.strip()]
                or sorted(list(MULTIPLICITY_COMPATIBLE_METHODS))
            ),
            "compatible_methods": sorted(list(MULTIPLICITY_COMPATIBLE_METHODS)),
            "n_applied_steps": int(len(applied_multiplicity_steps)),
            "n_ignored_steps": int(len(ignored_multiplicity_steps)),
            "applied_steps": applied_multiplicity_steps,
            "ignored_steps": ignored_multiplicity_steps,
        }
        applied_bootstrap_steps = sorted(list({str(v) for v in bootstrap_policy_applied_steps if str(v).strip()}))
        ignored_bootstrap_steps = sorted(list({str(v) for v in bootstrap_policy_ignored_steps if str(v).strip()}))
        bootstrap_policy_doc: Dict[str, Any] = {
            "enabled": bool(bootstrap_policy_enabled),
            "samples": int(bootstrap_policy_samples),
            "ci_level": float(bootstrap_policy.get("ci_level") or 0.95),
            "analysis_mode": analysis_mode,
            "scope": "global_defaults",
            "methods": (
                [str(v) for v in (bootstrap_policy.get("methods") or []) if isinstance(v, str) and v.strip()]
                or sorted(list(BOOTSTRAP_COMPATIBLE_METHODS))
            ),
            "compatible_methods": sorted(list(BOOTSTRAP_COMPATIBLE_METHODS)),
            "n_applied_steps": int(len(applied_bootstrap_steps)),
            "n_ignored_steps": int(len(ignored_bootstrap_steps)),
            "applied_steps": applied_bootstrap_steps,
            "ignored_steps": ignored_bootstrap_steps,
        }
        protocol_validation_doc = build_protocol_validation_report(
            steps=normalized_steps,
            step_reports=protocol_validation_steps,
            validator_enabled=validator_enabled,
            validator_strict=validator_strict,
            alpha=float(request.alpha),
            global_errors=protocol_validation_global_errors,
        )
        if isinstance(protocol_validation_doc, dict):
            protocol_validation_doc["policy_profile"] = validation_policy.get("profile")
            policy_doc = dict(validation_policy)
            policy_doc["multiplicity_correction"] = multiplicity_policy_correction
            policy_doc["post_hoc_correction"] = multiplicity_policy_post_hoc
            policy_doc["bootstrap_enabled"] = bool(bootstrap_policy_doc.get("enabled"))
            policy_doc["bootstrap_samples"] = int(bootstrap_policy_doc.get("samples") or DEFAULT_BOOTSTRAP_SAMPLES)
            protocol_validation_doc["policy"] = policy_doc
            protocol_validation_doc["multiplicity_policy"] = multiplicity_policy_doc
            protocol_validation_doc["bootstrap_policy"] = bootstrap_policy_doc

        protocol_name = str(request.protocol_name or "Протокол").strip() or "Протокол"
        run_dir = pipeline.create_analysis_run(
            request.dataset_id,
            {
                "name": protocol_name,
                "alpha": request.alpha,
                "globals": globals_in,
                "steps": normalized_steps or request.protocol,
            },
        )
        run_id = os.path.basename(run_dir)
        protocol_validation_artifact_path: Optional[str] = None
        if isinstance(protocol_validation_doc, dict):
            protocol_validation_doc["run_id"] = run_id
            protocol_validation_doc["dataset_id"] = request.dataset_id
            if hasattr(pipeline, "save_run_artifact"):
                try:
                    assert_artifact_contract("protocol_validation.json", protocol_validation_doc)
                    pipeline.save_run_artifact(
                        run_dir,
                        "protocol_validation.json",
                        json.dumps(protocol_validation_doc, ensure_ascii=False, indent=2).encode("utf-8"),
                    )
                    protocol_validation_artifact_path = os.path.join("artifacts", "protocol_validation.json")
                except Exception as e:
                    warnings.append(f"Не удалось сохранить protocol_validation.json: {e}")
                    _append_run_error("protocol_validation", "validator", str(e))
            else:
                warnings.append("Pipeline backend не поддерживает save_run_artifact; protocol_validation.json не сохранён.")
        bootstrap_trace_doc: Optional[Dict[str, Any]] = None
        bootstrap_trace_artifact_path: Optional[str] = None
        try:
            candidate_bootstrap_trace = _build_bootstrap_trace_document(
                dataset_id=request.dataset_id,
                run_id=run_id,
                results_map=results_map,
                step_meta_map=step_meta_map,
            )
            summary = (
                candidate_bootstrap_trace.get("summary")
                if isinstance(candidate_bootstrap_trace.get("summary"), dict)
                else {}
            )
            steps_with_bootstrap = int(summary.get("steps_with_bootstrap") or 0)
            if steps_with_bootstrap > 0:
                bootstrap_trace_doc = candidate_bootstrap_trace
                if hasattr(pipeline, "save_run_artifact"):
                    try:
                        assert_artifact_contract("bootstrap_trace.json", bootstrap_trace_doc)
                        pipeline.save_run_artifact(
                            run_dir,
                            "bootstrap_trace.json",
                            json.dumps(bootstrap_trace_doc, ensure_ascii=False, indent=2).encode("utf-8"),
                        )
                        bootstrap_trace_artifact_path = os.path.join("artifacts", "bootstrap_trace.json")
                    except Exception as e:
                        warnings.append(f"Не удалось сохранить bootstrap_trace.json: {e}")
                        _append_run_error("bootstrap_trace", "bootstrap", str(e))
                else:
                    warnings.append("Pipeline backend не поддерживает save_run_artifact; bootstrap_trace.json не сохранён.")
        except Exception as e:
            warnings.append(f"Не удалось собрать bootstrap_trace: {e}")
            _append_run_error("bootstrap_trace", "bootstrap", str(e))
        multiplicity_trace_doc: Optional[Dict[str, Any]] = None
        multiplicity_trace_artifact_path: Optional[str] = None
        try:
            candidate_multiplicity_trace = _build_multiplicity_trace_document(
                dataset_id=request.dataset_id,
                run_id=run_id,
                results_map=results_map,
                step_meta_map=step_meta_map,
            )
            summary = (
                candidate_multiplicity_trace.get("summary")
                if isinstance(candidate_multiplicity_trace.get("summary"), dict)
                else {}
            )
            steps_with_multiplicity = int(summary.get("steps_with_multiplicity") or 0)
            if steps_with_multiplicity > 0:
                multiplicity_trace_doc = candidate_multiplicity_trace
                if hasattr(pipeline, "save_run_artifact"):
                    try:
                        assert_artifact_contract("multiplicity_trace.json", multiplicity_trace_doc)
                        pipeline.save_run_artifact(
                            run_dir,
                            "multiplicity_trace.json",
                            json.dumps(multiplicity_trace_doc, ensure_ascii=False, indent=2).encode("utf-8"),
                        )
                        multiplicity_trace_artifact_path = os.path.join("artifacts", "multiplicity_trace.json")
                    except Exception as e:
                        warnings.append(f"Не удалось сохранить multiplicity_trace.json: {e}")
                        _append_run_error("multiplicity_trace", "multiplicity", str(e))
                else:
                    warnings.append("Pipeline backend не поддерживает save_run_artifact; multiplicity_trace.json не сохранён.")
        except Exception as e:
            warnings.append(f"Не удалось собрать multiplicity_trace: {e}")
            _append_run_error("multiplicity_trace", "multiplicity", str(e))

        hypothesis_discovery_doc = _safe_build_hypothesis_discovery(
            dataset_meta=build_ai_context(
                dataset_id=request.dataset_id,
                base_dir=DATA_DIR,
                df=df,
            ),
            preferences=globals_in if isinstance(globals_in, dict) else {},
            protocol=normalized_steps if isinstance(normalized_steps, list) else request.protocol,
        )
        hypothesis_discovery_artifact_path: Optional[str] = None
        if (
            isinstance(hypothesis_discovery_doc, dict)
            and isinstance(hypothesis_discovery_doc.get("items"), list)
            and len(hypothesis_discovery_doc.get("items") or []) > 0
        ):
            if hasattr(pipeline, "save_run_artifact"):
                try:
                    assert_artifact_contract("hypothesis_discovery.json", hypothesis_discovery_doc)
                    pipeline.save_run_artifact(
                        run_dir,
                        "hypothesis_discovery.json",
                        json.dumps(hypothesis_discovery_doc, ensure_ascii=False, indent=2).encode("utf-8"),
                    )
                    hypothesis_discovery_artifact_path = os.path.join("artifacts", "hypothesis_discovery.json")
                except Exception as e:
                    warnings.append(f"Не удалось сохранить hypothesis_discovery.json: {e}")
                    _append_run_error("hypothesis_discovery", "planning", str(e))
            else:
                warnings.append("Pipeline backend не поддерживает save_run_artifact; hypothesis_discovery.json не сохранён.")
        orchestrator_settings_enabled = _as_bool(
            getattr(settings, "CLINIMETRIA_AGENT_ORCHESTRATOR_ENABLED", False),
            default=False,
        )
        agent_orchestrator_enabled = _as_bool(
            globals_in.get("agent_orchestrator_enabled", globals_in.get("agent_orchestrator")),
            default=orchestrator_settings_enabled,
        )
        orchestrator_default_rounds = int(
            getattr(settings, "CLINIMETRIA_AGENT_ORCHESTRATOR_MAX_ROUNDS", 10) or 10
        )
        orchestrator_rounds_raw = globals_in.get(
            "agent_orchestrator_max_rounds",
            globals_in.get("max_rounds", orchestrator_default_rounds),
        )
        try:
            agent_orchestrator_max_rounds = int(orchestrator_rounds_raw)
        except Exception:
            agent_orchestrator_max_rounds = int(orchestrator_default_rounds)
        agent_orchestrator_max_rounds = max(1, min(50, int(agent_orchestrator_max_rounds)))
        agent_orchestrator: Optional[AgentOrchestrator] = None
        agent_orchestrator_events: List[Dict[str, Any]] = []

        if agent_orchestrator_enabled:
            seed_doc = pipeline.get_run_state(request.dataset_id, run_id)
            seed_state = (
                str(seed_doc.get("state")).strip().lower()
                if isinstance(seed_doc, dict) and isinstance(seed_doc.get("state"), str)
                else "compile"
            )
            seed_artifacts = (
                dict(seed_doc.get("artifacts"))
                if isinstance(seed_doc, dict) and isinstance(seed_doc.get("artifacts"), dict)
                else {}
            )
            try:
                agent_orchestrator = AgentOrchestrator(
                    initial_state=seed_state,
                    max_rounds=agent_orchestrator_max_rounds,
                    artifact_index=seed_artifacts,
                )
            except Exception as e:
                warnings.append(f"Agent orchestrator disabled: {e}")
                agent_orchestrator_enabled = False
                agent_orchestrator = None

        analysis_dataset_artifacts: Optional[Dict[str, Any]] = None
        df_for_artifacts = df_models_fixed if analysis_set_artifact is not None and analysis_set_enforce == "all" and df_models_fixed is not None else df
        try:
            loop = asyncio.get_event_loop()
            analysis_dataset_artifacts = await loop.run_in_executor(
                None,
                lambda: pipeline.save_run_analysis_dataset(run_dir, df_for_artifacts),
            )
            if isinstance(analysis_dataset_artifacts, dict):
                xlsx_status = str(analysis_dataset_artifacts.get("xlsx_status") or "").strip().lower()
                if xlsx_status and xlsx_status != "exported":
                    xlsx_reason = analysis_dataset_artifacts.get("xlsx_reason")
                    warnings.append(
                        "Экспорт analysis_dataset.xlsx не выполнен: "
                        f"{xlsx_reason or xlsx_status}"
                    )
        except Exception as e:
            warnings.append(f"Не удалось сохранить analysis_dataset артефакты: {e}")

        runtime_elapsed_values = [
            max(0, int(item.get("elapsed_ms") or 0))
            for item in runtime_steps
            if isinstance(item, dict)
        ]
        runtime_total_elapsed_ms = _runtime_elapsed_ms(execute_started_perf)
        runtime_steps_elapsed_ms = int(sum(runtime_elapsed_values))
        runtime_non_step_elapsed_ms = max(0, int(runtime_total_elapsed_ms - runtime_steps_elapsed_ms))
        runtime_status_counts: Dict[str, int] = {}
        for item in runtime_steps:
            if not isinstance(item, dict):
                continue
            status_key = str(item.get("status") or "unknown").strip().lower() or "unknown"
            runtime_status_counts[status_key] = int(runtime_status_counts.get(status_key, 0) + 1)

        runtime_method_rollup: Dict[str, Dict[str, Any]] = {}
        for item in runtime_steps:
            if not isinstance(item, dict):
                continue
            method_key = str(item.get("method") or "unknown").strip().lower() or "unknown"
            status_key = str(item.get("status") or "unknown").strip().lower() or "unknown"
            elapsed_ms = max(0, int(item.get("elapsed_ms") or 0))
            bucket = runtime_method_rollup.setdefault(
                method_key,
                {
                    "method": method_key,
                    "count": 0,
                    "failed_count": 0,
                    "blocked_count": 0,
                    "total_elapsed_ms": 0,
                },
            )
            bucket["count"] = int(bucket["count"] + 1)
            bucket["total_elapsed_ms"] = int(bucket["total_elapsed_ms"] + elapsed_ms)
            if status_key == "failed":
                bucket["failed_count"] = int(bucket["failed_count"] + 1)
            if status_key.startswith("blocked"):
                bucket["blocked_count"] = int(bucket["blocked_count"] + 1)
        runtime_method_summary = sorted(
            [
                {
                    **bucket,
                    "mean_elapsed_ms": int(round(bucket["total_elapsed_ms"] / bucket["count"])) if int(bucket["count"]) > 0 else 0,
                }
                for bucket in runtime_method_rollup.values()
            ],
            key=lambda item: (
                int(item.get("total_elapsed_ms") or 0),
                int(item.get("count") or 0),
            ),
            reverse=True,
        )

        runtime_profile_doc: Dict[str, Any] = {
            "schema": "clinimetria.runtime_profile",
            "version": 1,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "run_started_at": execute_started_at,
            "run_finished_at": datetime.utcnow().isoformat() + "Z",
            "run_id": run_id,
            "dataset_id": request.dataset_id,
            "analysis_mode": analysis_mode,
            "publication_mode": publication_mode,
            "summary": {
                "total_steps": int(len(protocol_steps)),
                "profiled_steps": int(len(runtime_steps)),
                "completed_steps": int(runtime_status_counts.get("completed", 0)),
                "failed_steps": int(runtime_status_counts.get("failed", 0)),
                "blocked_steps": int(
                    sum(
                        count
                        for key, count in runtime_status_counts.items()
                        if str(key).startswith("blocked")
                    )
                ),
                "dataset_rows": int(dataset_rows),
                "dataset_cols": int(dataset_cols),
                "total_elapsed_ms": int(runtime_total_elapsed_ms),
                "steps_elapsed_ms": int(runtime_steps_elapsed_ms),
                "non_step_elapsed_ms": int(runtime_non_step_elapsed_ms),
                "mean_step_elapsed_ms": int(round(runtime_steps_elapsed_ms / len(runtime_elapsed_values))) if runtime_elapsed_values else 0,
                "p95_step_elapsed_ms": int(_runtime_percentile_ms(runtime_elapsed_values, 0.95)),
                "max_step_elapsed_ms": int(max(runtime_elapsed_values) if runtime_elapsed_values else 0),
            },
            "status_counts": runtime_status_counts,
            "methods": runtime_method_summary,
            "steps": runtime_steps,
        }

        runtime_profile_artifact_path: Optional[str] = None
        if hasattr(pipeline, "save_run_artifact"):
            try:
                assert_artifact_contract("runtime_profile.json", runtime_profile_doc)
                pipeline.save_run_artifact(
                    run_dir,
                    "runtime_profile.json",
                    json.dumps(runtime_profile_doc, ensure_ascii=False, indent=2).encode("utf-8"),
                )
                runtime_profile_artifact_path = os.path.join("artifacts", "runtime_profile.json")
            except Exception as e:
                warnings.append(f"Не удалось сохранить runtime_profile.json: {e}")
                _append_run_error("runtime_profile", "runtime_profile", str(e))
        else:
            warnings.append("Pipeline backend не поддерживает save_run_artifact; runtime_profile.json не сохранён.")

        analysis_set_payload: Optional[Dict[str, Any]] = (
            {
                "analysis_set_id": analysis_set_id or None,
                "enforce": analysis_set_enforce,
                "strict": bool(analysis_set_strict),
                "artifact_exists": bool(isinstance(analysis_set_artifact, dict)),
                "mode": (
                    str(analysis_set_artifact.get("mode") or "").strip()
                    if isinstance(analysis_set_artifact, dict)
                    else None
                ),
                "n_selected": (
                    int(analysis_set_artifact.get("n_selected"))
                    if isinstance(analysis_set_artifact, dict)
                    and isinstance(analysis_set_artifact.get("n_selected"), (int, float))
                    else None
                ),
            }
            if analysis_set_id
            else None
        )
        if global_desc:
            if not isinstance(analysis_set_payload, dict):
                analysis_set_payload = {}
            analysis_set_payload["descriptive"] = global_desc

        run_payload: Dict[str, Any] = {
            "protocol_name": protocol_name,
            "dataset_id": request.dataset_id,
            "alpha": request.alpha,
            "analysis_mode": analysis_mode,
            "publication_mode": publication_mode,
            "globals": globals_in,
            "validation_policy": validation_policy,
            "multiplicity_policy": multiplicity_policy_doc,
            "bootstrap_policy": bootstrap_policy_doc,
            "results": results_map,
            "step_meta": step_meta_map,
            "status": "completed" if not errors else "partial",
            "errors": errors,
            "total_steps": len(request.protocol),
            "completed_steps": len(results_map),
            "failed_steps": len(errors),
            "warnings": warnings,
            "analysis_dataset": analysis_dataset_artifacts,
            "runtime_profile": runtime_profile_doc,
            "protocol_validation": protocol_validation_doc if isinstance(protocol_validation_doc, dict) else None,
            "multiplicity_trace": multiplicity_trace_doc if isinstance(multiplicity_trace_doc, dict) else None,
            "bootstrap_trace": bootstrap_trace_doc if isinstance(bootstrap_trace_doc, dict) else None,
            "hypotheses": hypothesis_discovery_doc if isinstance(hypothesis_discovery_doc, dict) else None,
            "protocol_plan": protocol_plan_in,
            "column_selection_report": column_selection_report,
            "analysis_set": analysis_set_payload,
            "design_review": {
                "required": require_design_review,
                "confirmed": design_review_confirmed,
                "timestamp": design_review_timestamp,
                "artifact_exists": design_review_artifact_exists,
                "artifact_confirmed": design_review_artifact_confirmed,
                "confirmed_by": design_review_confirmed_by,
                "confirmed_source": design_review_confirmed_source,
            },
            "llm_benchmark": llm_benchmark,
        }

        run_state_doc: Optional[Dict[str, Any]] = None
        agent_orchestration: Optional[Dict[str, Any]] = None

        def _record_agent_orchestrator_event(
            *,
            action: str = "advance",
            to_state: Optional[str] = None,
            artifact_updates: Optional[Dict[str, Any]] = None,
            reason: Optional[str] = None,
            run_state_applied: bool = True,
        ) -> None:
            if not isinstance(agent_orchestrator, AgentOrchestrator):
                return

            action_norm = str(action or "").strip().lower()
            if action_norm not in {"advance", "retry", "reject", "complete"}:
                action_norm = "retry"

            target_state = str(to_state or "").strip().lower() or None
            decision: Dict[str, Any] = {
                "action": action_norm,
                "reason": str(reason or "").strip(),
            }
            if isinstance(artifact_updates, dict) and artifact_updates:
                decision["artifact_updates"] = dict(artifact_updates)
            if action_norm in {"advance", "reject"} and target_state:
                decision["target_state"] = target_state
            if action_norm in {"advance", "reject"} and not decision.get("target_state"):
                decision["action"] = "retry"
                decision.pop("target_state", None)

            current_state_key = agent_orchestrator.machine.state_value

            def _handler(_state: Any, _artifacts: Any, _round: Any) -> Dict[str, Any]:
                return dict(decision)

            agent_orchestrator.role_handlers[current_state_key] = _handler
            try:
                event = agent_orchestrator.step()
                if isinstance(event, dict):
                    event["run_state_applied"] = bool(run_state_applied)
                    if target_state:
                        event["expected_state"] = target_state
                    agent_orchestrator_events.append(event)
            except Exception as e:
                warnings.append(f"Agent orchestrator warning: {e}")
            finally:
                agent_orchestrator.role_handlers.pop(current_state_key, None)

        def _set_run_state(
            *,
            to_state: Optional[str] = None,
            artifact_updates: Optional[Dict[str, Any]] = None,
            reason: Optional[str] = None,
            strict_artifacts: bool = False,
        ) -> bool:
            nonlocal run_state_doc
            try:
                run_state_doc = pipeline.update_run_state(
                    run_dir,
                    to_state=to_state,
                    artifact_updates=artifact_updates,
                    reason=reason,
                    strict_artifacts=strict_artifacts,
                )
                return True
            except Exception as e:
                warnings.append(f"Run state warning: {e}")
                return False

        execute_artifacts: Dict[str, Any] = {"results": "results.json"}
        if isinstance(protocol_validation_artifact_path, str) and protocol_validation_artifact_path:
            execute_artifacts["protocol_validation"] = protocol_validation_artifact_path
        if isinstance(bootstrap_trace_artifact_path, str) and bootstrap_trace_artifact_path:
            execute_artifacts["bootstrap_trace"] = bootstrap_trace_artifact_path
        if isinstance(multiplicity_trace_artifact_path, str) and multiplicity_trace_artifact_path:
            execute_artifacts["multiplicity_trace"] = multiplicity_trace_artifact_path
        if isinstance(hypothesis_discovery_artifact_path, str) and hypothesis_discovery_artifact_path:
            execute_artifacts["hypothesis_discovery"] = hypothesis_discovery_artifact_path
        if isinstance(runtime_profile_artifact_path, str) and runtime_profile_artifact_path:
            execute_artifacts["runtime_profile"] = runtime_profile_artifact_path

        execute_state_applied = _set_run_state(
            to_state="execute",
            artifact_updates=execute_artifacts,
            reason="protocol_executed",
            strict_artifacts=True,
        )
        _record_agent_orchestrator_event(
            action="advance" if execute_state_applied else "retry",
            to_state="execute",
            artifact_updates=execute_artifacts,
            reason="protocol_executed",
            run_state_applied=execute_state_applied,
        )

        verification_artifact_path: Optional[str] = None
        verification_artifact_error: Optional[str] = None

        def _save_verification_artifact(payload: Dict[str, Any]) -> None:
            nonlocal verification_artifact_path, verification_artifact_error
            if not hasattr(pipeline, "save_run_artifact"):
                verification_artifact_error = "Pipeline backend не поддерживает save_run_artifact; verification.json не сохранён."
                warnings.append(verification_artifact_error)
                return
            try:
                assert_artifact_contract("verification.json", payload)
                pipeline.save_run_artifact(
                    run_dir,
                    "verification.json",
                    json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                )
                verification_artifact_path = os.path.join("artifacts", "verification.json")
                verification_artifact_error = None
            except Exception as e:
                verification_artifact_error = str(e)
                warnings.append(f"Не удалось сохранить verification.json: {e}")
                _append_run_error("verification", "verifier", str(e))

        verifier_reflection_enabled = bool(validation_policy.get("reflection_enabled"))
        verifier_reflection_max_rounds = max(
            1,
            min(10, int(validation_policy.get("reflection_max_rounds") or 1)),
        )
        verifier_repair_correction = _normalize_correction(
            validation_policy.get("repair_correction")
        ) or "fdr_bh"

        reflection_rounds: List[Dict[str, Any]] = []

        verification = verify_run_payload(run_payload, alpha=float(request.alpha))
        run_payload["verification"] = verification
        _save_verification_artifact(verification if isinstance(verification, dict) else {})
        verify_artifacts = (
            {"verification": verification_artifact_path}
            if isinstance(verification_artifact_path, str) and verification_artifact_path
            else None
        )
        verify_state_applied = _set_run_state(
            to_state="verify",
            reason="verification_completed",
            strict_artifacts=True,
        )
        _record_agent_orchestrator_event(
            action="advance" if verify_state_applied else "retry",
            to_state="verify",
            artifact_updates=verify_artifacts,
            reason="verification_completed",
            run_state_applied=verify_state_applied,
        )

        verification_status = (
            str(verification.get("status") or "").strip().lower()
            if isinstance(verification, dict)
            else "failed"
        )
        reflection_rounds.append(
            {
                "round": 0,
                "stage": "initial_verify",
                "verification_status": verification_status,
                "summary": verification.get("summary") if isinstance(verification, dict) else {},
                "failure_checks": sorted(
                    list(
                        {
                            str(item.get("check") or "").strip().lower()
                            for item in (
                                verification.get("failures")
                                if isinstance(verification, dict)
                                and isinstance(verification.get("failures"), list)
                                else []
                            )
                            if isinstance(item, dict)
                        }
                    )
                ),
            }
        )

        if verification_status != "passed" and verifier_reflection_enabled:
            for round_idx in range(1, verifier_reflection_max_rounds + 1):
                repair = _attempt_verifier_reflection_repair(
                    run_payload,
                    verification=verification if isinstance(verification, dict) else {},
                    alpha=float(request.alpha),
                    correction=verifier_repair_correction,
                )
                if not repair.get("applied"):
                    reflection_rounds.append(
                        {
                            "round": round_idx,
                            "stage": "reflection_stop",
                            "action": "no_repair",
                            "reason": repair.get("reason"),
                            "checks": repair.get("checks") if isinstance(repair.get("checks"), list) else [],
                        }
                    )
                    break

                compile_state_applied = _set_run_state(
                    to_state="compile",
                    reason=f"verifier_reject_round_{round_idx}",
                    strict_artifacts=True,
                )
                _record_agent_orchestrator_event(
                    action="reject" if compile_state_applied else "retry",
                    to_state="compile",
                    artifact_updates={"protocol": "protocol.json"},
                    reason=f"verifier_reject_round_{round_idx}",
                    run_state_applied=compile_state_applied,
                )

                execute_retry_applied = _set_run_state(
                    to_state="execute",
                    artifact_updates=execute_artifacts,
                    reason=f"verifier_repair_round_{round_idx}",
                    strict_artifacts=True,
                )
                _record_agent_orchestrator_event(
                    action="advance" if execute_retry_applied else "retry",
                    to_state="execute",
                    artifact_updates=execute_artifacts,
                    reason=f"verifier_repair_round_{round_idx}",
                    run_state_applied=execute_retry_applied,
                )

                verification = verify_run_payload(run_payload, alpha=float(request.alpha))
                run_payload["verification"] = verification
                _save_verification_artifact(verification if isinstance(verification, dict) else {})
                verify_artifacts = (
                    {"verification": verification_artifact_path}
                    if isinstance(verification_artifact_path, str) and verification_artifact_path
                    else None
                )
                verify_retry_applied = _set_run_state(
                    to_state="verify",
                    reason=f"verification_round_{round_idx}",
                    strict_artifacts=True,
                )
                _record_agent_orchestrator_event(
                    action="advance" if verify_retry_applied else "retry",
                    to_state="verify",
                    artifact_updates=verify_artifacts,
                    reason=f"verification_round_{round_idx}",
                    run_state_applied=verify_retry_applied,
                )

                verification_status = (
                    str(verification.get("status") or "").strip().lower()
                    if isinstance(verification, dict)
                    else "failed"
                )
                reflection_rounds.append(
                    {
                        "round": round_idx,
                        "stage": "reflection_retry",
                        "action": "repair_applied",
                        "reason": repair.get("reason"),
                        "details": repair.get("details") if isinstance(repair.get("details"), dict) else {},
                        "verification_status": verification_status,
                        "summary": verification.get("summary") if isinstance(verification, dict) else {},
                    }
                )
                if verification_status == "passed":
                    break

        verification_error = None
        if verification_status != "passed":
            verification_error = "Verifier gate failed: report/release blocked."
            _append_run_error("verification", "verifier", verification_error)
            warnings.append("Verifier gate blocked report and release artifacts.")
            run_payload["status"] = "partial"
        if isinstance(verification_artifact_error, str) and verification_artifact_error.strip():
            if verification_error is None:
                verification_error = verification_artifact_error
                run_payload["status"] = "partial"

        reflection_log_path: Optional[str] = None
        if verifier_reflection_enabled or reflection_rounds:
            reflection_log_doc = {
                "schema": "clinimetria.reflection_log",
                "version": 1,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "run_id": run_id,
                "dataset_id": request.dataset_id,
                "enabled": bool(verifier_reflection_enabled),
                "max_rounds": int(verifier_reflection_max_rounds),
                "repair_correction": verifier_repair_correction,
                "policy_profile": validation_policy.get("profile"),
                "policy": dict(validation_policy),
                "rounds": reflection_rounds,
                "final_verification_status": verification_status,
            }
            if hasattr(pipeline, "save_run_artifact"):
                try:
                    assert_artifact_contract("reflection_log.json", reflection_log_doc)
                    pipeline.save_run_artifact(
                        run_dir,
                        "reflection_log.json",
                        json.dumps(reflection_log_doc, ensure_ascii=False, indent=2).encode("utf-8"),
                    )
                    reflection_log_path = os.path.join("artifacts", "reflection_log.json")
                except Exception as e:
                    warnings.append(f"Не удалось сохранить reflection_log.json: {e}")
                    _append_run_error("reflection", "verifier", str(e))
            else:
                warnings.append("Pipeline backend не поддерживает save_run_artifact; reflection_log.json не сохранён.")
            run_payload["reflection_log"] = reflection_log_doc

        reproducibility: Optional[Dict[str, Any]] = None
        if verification_error is None:
            result_ir = pipeline.build_result_ir(run_payload)
            reproducibility = _create_run_reproducibility_artifacts(
                run_dir=run_dir,
                run_id=run_id,
                dataset_id=request.dataset_id,
                protocol_name=protocol_name,
                alpha=float(request.alpha),
                globals_in=globals_in,
                normalized_steps=normalized_steps or request.protocol,
                run_payload=run_payload,
                result_ir=result_ir,
                analysis_dataset_artifacts=analysis_dataset_artifacts,
                llm_benchmark=llm_benchmark,
                runtime_profile=runtime_profile_doc,
            )
            if isinstance(reproducibility, dict):
                run_payload["reproducibility"] = reproducibility
                repro_errors = reproducibility.get("errors")
                if isinstance(repro_errors, list):
                    for err in repro_errors:
                        warnings.append(f"Reproducibility artifact warning: {err}")
                run_payload["warnings"] = warnings
            report_artifacts: Dict[str, Any] = {}
            if isinstance(reproducibility, dict):
                report_html_name = reproducibility.get("report_html")
                if isinstance(report_html_name, str) and report_html_name.strip():
                    report_artifacts["report_html"] = os.path.join("artifacts", report_html_name.strip())
            report_state_applied = _set_run_state(
                to_state="report",
                reason="report_generated",
                strict_artifacts=True,
            )
            _record_agent_orchestrator_event(
                action="advance" if report_state_applied else "retry",
                to_state="report",
                artifact_updates=report_artifacts or None,
                reason="report_generated",
                run_state_applied=report_state_applied,
            )
            release_artifacts: Dict[str, Any] = {}
            if isinstance(reproducibility, dict):
                for artifact_key, repro_key in [
                    ("reproducibility_manifest", "manifest"),
                    ("reproduce_script", "script"),
                    ("reproduce_payload", "payload"),
                    ("protocol_resolved", "protocol"),
                    ("environment", "environment"),
                    ("hypothesis_discovery", "hypothesis_discovery"),
                    ("multiplicity_trace", "multiplicity_trace"),
                    ("bootstrap_trace", "bootstrap_trace"),
                    ("runtime_profile", "runtime_profile"),
                ]:
                    filename = reproducibility.get(repro_key)
                    if isinstance(filename, str) and filename.strip():
                        release_artifacts[artifact_key] = os.path.join("artifacts", filename.strip())
            release_state_applied = _set_run_state(
                to_state="release",
                reason="release_ready",
                strict_artifacts=True,
            )
            _record_agent_orchestrator_event(
                action="advance" if release_state_applied else "retry",
                to_state="release",
                artifact_updates=release_artifacts or None,
                reason="release_ready",
                run_state_applied=release_state_applied,
            )
        else:
            reproducibility = {
                "ready": False,
                "errors": [verification_error],
                "notes": ["Run stopped at verification gate."],
            }
            run_payload["reproducibility"] = reproducibility
            run_payload["warnings"] = warnings
            _record_agent_orchestrator_event(
                action="retry",
                artifact_updates=verify_artifacts,
                reason="verification_failed",
                run_state_applied=False,
            )

        if isinstance(agent_orchestrator, AgentOrchestrator):
            agent_orchestration = {
                "enabled": True,
                "status": (
                    "completed"
                    if agent_orchestrator.machine.state_value == "release"
                    else "incomplete"
                ),
                "state": agent_orchestrator.machine.state_value,
                "rounds_executed": int(agent_orchestrator.rounds_executed),
                "max_rounds": int(agent_orchestrator.max_rounds),
                "missing_required_artifacts": agent_orchestrator.machine.missing_required_artifacts(
                    agent_orchestrator.artifacts
                ),
                "artifacts": dict(agent_orchestrator.artifacts),
                "reflection_log": reflection_log_path,
                "reflection_rounds": reflection_rounds,
                "events": list(agent_orchestrator_events),
                "transitions": agent_orchestrator.machine.transitions,
            }
            run_payload["agent_orchestration"] = agent_orchestration

        if isinstance(run_state_doc, dict):
            run_payload["run_state"] = run_state_doc

        result_ir = pipeline.build_result_ir(run_payload)
        pipeline.save_run_results(run_dir, run_payload)
        
        return {
            "run_id": run_id,
            "status": "completed" if not errors else "partial",
            "results": results,
            "result_ir": result_ir,
            "errors": errors,
            "warnings": warnings,
            "analysis_mode": analysis_mode,
            "publication_mode": publication_mode,
            "design_review_confirmed": design_review_confirmed,
            "design_review_required": require_design_review,
            "design_review_artifact_exists": design_review_artifact_exists,
            "design_review_artifact_confirmed": design_review_artifact_confirmed,
            "analysis_dataset": analysis_dataset_artifacts,
            "runtime_profile": runtime_profile_doc,
            "analysis_set": (
                {
                    "analysis_set_id": analysis_set_id or None,
                    "enforce": analysis_set_enforce,
                    "strict": bool(analysis_set_strict),
                    "artifact_exists": bool(isinstance(analysis_set_artifact, dict)),
                    "mode": (
                        str(analysis_set_artifact.get("mode") or "").strip()
                        if isinstance(analysis_set_artifact, dict)
                        else None
                    ),
                    "n_selected": (
                        int(analysis_set_artifact.get("n_selected"))
                        if isinstance(analysis_set_artifact, dict)
                        and isinstance(analysis_set_artifact.get("n_selected"), (int, float))
                        else None
                    ),
                }
                if analysis_set_id
                else None
            ),
            "run_state": run_state_doc,
            "protocol_validation": protocol_validation_doc if isinstance(protocol_validation_doc, dict) else None,
            "multiplicity_trace": multiplicity_trace_doc if isinstance(multiplicity_trace_doc, dict) else None,
            "bootstrap_trace": bootstrap_trace_doc if isinstance(bootstrap_trace_doc, dict) else None,
            "hypotheses": hypothesis_discovery_doc if isinstance(hypothesis_discovery_doc, dict) else None,
            "protocol_plan": protocol_plan_in,
            "column_selection_report": column_selection_report,
            "validation_policy": validation_policy,
            "multiplicity_policy": multiplicity_policy_doc,
            "bootstrap_policy": bootstrap_policy_doc,
            "reproducibility": reproducibility,
            "agent_orchestration": agent_orchestration,
            "llm_benchmark": llm_benchmark,
            "total_steps": len(request.protocol),
            "completed_steps": len(results),
            "failed_steps": len(errors)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Protocol execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить протокол: {str(e)}")
