"""
API v2 Endpoints for Advanced Statistical Methods
===================================================
JAMOVI-style endpoints for mixed effects models, clustered correlation, and advanced analyses.
Memory-optimized for MacBook M1 8GB constraints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
import gc
import asyncio
from concurrent.futures import ProcessPoolExecutor
import os
import json
import math
from datetime import datetime

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
from app.stats.engine import run_analysis, select_test, compute_descriptive_compare, run_batch_analysis
from app.core.study_designer import StudyDesignEngine
from app.modules.text_generator import TextGenerator
from app.modules.protocol_rules import build_exploratory_plan, merge_protocols
from app.modules.protocol_quality import evaluate_protocol_quality
from app.modules.legacy_telemetry import record_legacy_hit, get_legacy_snapshot
from app.modules.study_design import load_study_design
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
from app.modules.cleaning_run import (
    load_cleaning_run_artifact,
    validate_cleaning_run_artifact,
    dataframe_fingerprint as cleaning_run_dataframe_fingerprint,
)
from app.modules.interpretation_contract import (
    normalize_interpretation_contract,
    is_interpretation_contract_complete,
    is_inferential_payload as is_inferential_interpretation_payload,
)
from app.api.datasets import DATA_DIR, _load_dataset_meta

pipeline = PipelineManager(DATA_DIR)

_text_generator = TextGenerator()


def _ensure_method(payload: Dict[str, Any], method_id: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    if payload.get("method"):
        return payload
    payload["method"] = {"id": method_id, "name": method_id}
    return payload


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


def _canonical_method_id(raw_method: Any) -> str:
    method = str(raw_method or "").strip().lower()
    if not method:
        return ""
    method = "_".join(method.replace("-", "_").split())
    aliases = {
        "mixed_model": "mixed_effects",
        "fisher": "fisher_exact",
        "welch_t_test": "t_test_welch",
        "kruskal_wallis": "kruskal",
        "bootstrap": "bootstrap_pipeline",
        "bootstrap_ci": "bootstrap_pipeline",
        "bootstrap_effect": "bootstrap_pipeline",
        "cluster_profile": "cluster_profiles",
        "clustering_profiles": "cluster_profiles",
        "external_validate": "external_validation",
        "external_validation_dataset": "external_validation",
        "randomforest": "random_forest",
        "random_forest_classifier": "random_forest",
        "random_forest_regressor": "random_forest",
        "gradientboosting": "gradient_boosting",
        "gradient_boosting_classifier": "gradient_boosting",
        "gradient_boosting_regressor": "gradient_boosting",
        "k_nearest_neighbors": "knn",
        "nearest_neighbors": "knn",
        "support_vector_machine": "svm",
    }
    return aliases.get(method, method)


def _payload_variables_from_config(config: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = config if isinstance(config, dict) else {}
    data = payload if isinstance(payload, dict) else {}
    variables: Dict[str, Any] = {}
    target = cfg.get("target") or cfg.get("outcome") or data.get("target") or data.get("outcome")
    if isinstance(target, str) and target.strip():
        variables["target"] = target.strip()
        variables["outcome"] = target.strip()

    group = (
        cfg.get("group")
        or cfg.get("predictor")
        or cfg.get("group1")
        or data.get("group")
        or data.get("group_label")
        or data.get("group_column")
    )
    if isinstance(group, str) and group.strip():
        variables["group"] = group.strip()

    predictor = cfg.get("predictor")
    if isinstance(predictor, str) and predictor.strip():
        variables["predictor"] = predictor.strip()

    return variables


def _attach_interpretation_contracts(
    *,
    results_map: Dict[str, Any],
    step_meta_map: Dict[str, Any],
    publication_mode: bool,
    warnings: List[str],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for step_id, payload in (results_map or {}).items():
        if not isinstance(payload, dict):
            out[step_id] = payload
            continue
        meta = step_meta_map.get(step_id) if isinstance(step_meta_map, dict) else None
        meta = meta if isinstance(meta, dict) else {}
        cfg = meta.get("config") if isinstance(meta.get("config"), dict) else {}
        variables = _payload_variables_from_config(cfg, payload)
        contract = normalize_interpretation_contract(
            payload.get("interpretation_contract"),
            payload,
            variables=variables,
            locale="ru",
        )
        next_payload = dict(payload)
        next_payload["interpretation_contract"] = contract

        # Publication mode: attach explicit conclusion from contract claim if absent.
        if publication_mode:
            has_conclusion = isinstance(next_payload.get("conclusion"), str) and str(next_payload.get("conclusion")).strip()
            if not has_conclusion:
                claim = str(contract.get("claim") or "").strip()
                if claim:
                    next_payload["conclusion"] = claim
            if is_inferential_interpretation_payload(next_payload) and not is_interpretation_contract_complete(contract):
                warnings.append(
                    f"Шаг {step_id}: interpretation_contract неполный; отчёт quality gate может вернуть fail."
                )

        out[step_id] = next_payload
    return out


def _normalize_plan_step(item: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    raw_method = item.get("method") or item.get("test") or item.get("type")
    method = _canonical_method_id(raw_method)
    if not method:
        return None

    raw_config = item.get("config")
    config = raw_config if isinstance(raw_config, dict) else {}
    name = str(item.get("name") or "").strip() or None
    step_id = str(item.get("id") or f"ai_{idx + 1}").strip()
    if not name:
        name = method.replace("_", " ").title()

    if "outcome" not in config and "target" in config:
        config = {**config, "outcome": config.get("target")}
    if "target" not in config and "outcome" in config and method == "descriptive_compare":
        config = {**config, "target": config.get("outcome")}
    if "group" not in config and "predictor" in config:
        config = {**config, "group": config.get("predictor")}

    return {"id": step_id, "name": name, "method": method, "config": config}

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
    "linear_regression",
    "logistic_regression",
    "roc_analysis",
    "bootstrap_pipeline",
    "cluster_profiles",
    "external_validation",
    "random_forest",
    "gradient_boosting",
    "knn",
    "svm",
]

TEMPLATE_TO_V2_SUPPORTED_STEP_TYPES = {
    "descriptive_compare",
    "compare",
    "correlation",
}

def convert_numpy_to_native(obj: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_to_native(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_to_native(item) for item in obj]
    else:
        return obj


def _normalize_correction(value: Any) -> Optional[str]:
    if value is None:
        return None
    corr = str(value).strip().lower()
    if not corr:
        return None
    if corr in {"bh", "fdr_bh"}:
        return "fdr_bh"
    if corr in {"by", "fdr_by"}:
        return "fdr_by"
    if corr in {"bky", "fdr_bky", "fdr_tsbky"}:
        return "fdr_tsbky"
    if corr in {"bonferroni", "bonf"}:
        return "bonferroni"
    if corr in {"holm"}:
        return "holm"
    if corr in {"sidak"}:
        return "sidak"
    if corr in {"holm-sidak", "holmsidak", "holm_sidak"}:
        return "holm-sidak"
    if corr in {"none", "off", "no"}:
        return "none"
    return corr


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _collect_dataset_columns(dataset_meta: Dict[str, Any]) -> set:
    cols = dataset_meta.get("columns") if isinstance(dataset_meta, dict) else None
    names: set = set()
    if isinstance(cols, list):
        for item in cols:
            if isinstance(item, dict):
                name = item.get("name")
            else:
                name = item
            if name:
                names.add(str(name))
    return names


def _filter_protocol_steps(protocol: List[Dict[str, Any]], dataset_meta: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str]]:
    available = _collect_dataset_columns(dataset_meta)
    if not available:
        return protocol, []

    def _keep_col(val):
        if isinstance(val, str) and val in available:
            return val
        return None

    def _keep_list(lst):
        if not isinstance(lst, list):
            return []
        return [str(v) for v in lst if isinstance(v, str) and v in available]

    notes: List[str] = []
    filtered: List[Dict[str, Any]] = []

    for step in protocol:
        if not isinstance(step, dict):
            continue
        method = str(step.get("method") or "").strip()
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}
        cfg = dict(cfg)

        if "outcome" not in cfg and "target" in cfg:
            cfg["outcome"] = cfg.get("target")
        if "group" not in cfg and "predictor" in cfg:
            cfg["group"] = cfg.get("predictor")
        if "split_by" not in cfg:
            if "timepoint" in cfg:
                cfg["split_by"] = cfg.get("timepoint")
            elif "time" in cfg:
                cfg["split_by"] = cfg.get("time")

        for key in ["outcome", "group", "group1", "group2", "subject", "subject_col", "time", "baseline", "follow", "split_by", "predictor"]:
            if key in cfg:
                cfg[key] = _keep_col(cfg.get(key))

        for key in ["predictors", "covariates", "variables", "outcome_cols", "targets", "outcome_columns"]:
            if key in cfg:
                cfg[key] = _keep_list(cfg.get(key))

        if "pairs" in cfg and isinstance(cfg.get("pairs"), list):
            pairs = []
            for pair in cfg.get("pairs"):
                if not isinstance(pair, dict):
                    continue
                baseline = _keep_col(pair.get("baseline"))
                follow = _keep_col(pair.get("follow"))
                if baseline and follow:
                    pairs.append({**pair, "baseline": baseline, "follow": follow})
            cfg["pairs"] = pairs

        required = []
        if method in {"descriptive_compare", "auto", "t_test_ind", "t_test_welch", "mann_whitney", "anova", "anova_welch", "kruskal", "chi_square", "pearson", "spearman", "t_test_rel", "wilcoxon"}:
            required = ["outcome", "group"]
        elif method in {
            "linear_regression",
            "logistic_regression",
            "random_forest",
            "gradient_boosting",
            "knn",
            "svm",
        }:
            required = ["outcome", "predictors"]
        elif method == "external_validation":
            required = ["outcome", "predictors", "external_dataset_id"]
        elif method == "bootstrap_pipeline":
            required = ["outcome"]
        elif method == "cluster_profiles":
            required = ["variables"]
        elif method == "roc_analysis":
            required = ["outcome", "group"]
        elif method == "mixed_effects":
            required = ["outcome", "time", "group", "subject"]
        elif method == "clustered_correlation":
            required = ["variables"]
        elif method == "responders":
            required = ["outcome_columns", "group"]
        elif method == "anova_twoway":
            required = ["outcome", "group1", "group2"]
        elif method == "rm_anova":
            required = ["outcome_cols", "subject_col"]
        elif method == "friedman":
            required = ["outcome_cols"]
        elif method == "paired_wide":
            required = ["baseline", "follow"]
        elif method == "batch_analysis":
            required = ["group"]
        elif method == "timepoint_batch_analysis":
            required = ["group", "split_by"]
        elif method == "delta_batch_analysis":
            required = ["group", "pairs"]

        def _missing(key: str) -> bool:
            if key not in cfg or cfg.get(key) in (None, ""):
                return True
            if key in {"predictors", "covariates", "variables", "outcome_cols", "targets", "pairs", "outcome_columns"}:
                return not isinstance(cfg.get(key), list) or len(cfg.get(key)) == 0
            return False

        if required and any(_missing(k) for k in required):
            notes.append(f"Шаг {step.get('id') or method}: удалён (нет обязательных колонок).")
            continue

        if method == "clustered_correlation" and len(cfg.get("variables", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 переменных).")
            continue
        if method == "cluster_profiles" and len(cfg.get("variables", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 переменных).")
            continue
        if method == "responders" and len(cfg.get("outcome_columns", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 outcome_columns).")
            continue
        if method == "rm_anova" and len(cfg.get("outcome_cols", [])) < 2:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥2 outcome_cols).")
            continue
        if method == "friedman" and len(cfg.get("outcome_cols", [])) < 3:
            notes.append(f"Шаг {step.get('id') or method}: удалён (нужно ≥3 outcome_cols).")
            continue

        step = dict(step)
        step["config"] = cfg
        filtered.append(step)

    return filtered, notes


def _normalize_analysis_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"publication", "publish", "manuscript", "article", "confirmatory", "confirmation", "strict"}:
        return "publication"
    if mode in {"data_prep", "data-prep", "prepare", "preparation", "prep", "cleaning", "quality"}:
        return "data_prep"
    if mode in {"discovery", "hypothesis", "hypothesis_generation", "hypothesis-gen", "idea_mining"}:
        return "discovery"
    if mode in {"expert_comprehensive", "expert-comprehensive", "expert", "expert_full", "exhaustive"}:
        return "expert_comprehensive"
    if mode in {"comprehensive", "full", "broad_full"}:
        return "comprehensive"
    if mode in {"focused", "standard", "targeted"}:
        return "focused"
    if mode in {"exploratory", "maximal", "broad", "deep", "mining"}:
        return "exploratory"
    return "exploratory"


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _infer_protocol_column_sets(protocol: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    required_all: set = set()
    predictor_like: set = set()
    outcomes: set = set()
    methods: set = set()

    for step in protocol:
        if not isinstance(step, dict):
            continue
        method = _canonical_method_id(step.get("method"))
        if method:
            methods.add(method)
        cfg = step.get("config") if isinstance(step.get("config"), dict) else {}

        for key in ["outcome", "target", "group", "group1", "group2", "subject", "subject_col", "time", "baseline", "follow", "split_by"]:
            val = cfg.get(key)
            if isinstance(val, str) and val.strip():
                required_all.add(val.strip())
                if key in {"outcome", "target"}:
                    outcomes.add(val.strip())

        for key in ["predictors", "covariates"]:
            for val in _as_str_list(cfg.get(key)):
                required_all.add(val)
                predictor_like.add(val)

        for key in ["variables", "outcome_cols", "outcome_columns", "targets"]:
            for val in _as_str_list(cfg.get(key)):
                required_all.add(val)
                if key in {"outcome_cols", "outcome_columns", "targets"}:
                    outcomes.add(val)

    return {
        "required_all": sorted(required_all),
        "predictor_like": sorted(predictor_like),
        "outcomes": sorted(outcomes),
        "methods": sorted(methods),
    }


def _build_cleaning_plan(
    *,
    scan_report: Dict[str, Any],
    protocol: List[Dict[str, Any]],
    analysis_mode: str,
) -> Dict[str, Any]:
    strict_mode = analysis_mode in {"publication", "expert_comprehensive"}
    prep_mode = analysis_mode == "data_prep"
    inferred = _infer_protocol_column_sets(protocol)
    critical_cols = set(inferred.get("required_all") or [])
    columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else None
    columns_meta = columns_meta if isinstance(columns_meta, dict) else {}
    missing_report = scan_report.get("missing_report") if isinstance(scan_report, dict) else None
    missing_by_col = missing_report.get("by_column") if isinstance(missing_report, dict) else None
    missing_by_col = missing_by_col if isinstance(missing_by_col, list) else []

    operations: List[Dict[str, Any]] = [
        {
            "type": "normalize_missing_tokens",
            "columns": "__all__",
            "tokens": ["", "na", "n/a", "none", "null", "nan"],
        }
    ]

    for col, rep in list(columns_meta.items())[:500]:
        if not isinstance(rep, dict):
            continue
        if rep.get("mixed_type_suspected") is not True:
            continue
        try:
            pct = float(rep.get("numeric_convertible_percent") or 0.0)
        except Exception:
            pct = 0.0
        if pct >= 90.0:
            operations.append(
                {
                    "type": "to_numeric",
                    "columns": [str(col)],
                    "when": {"numeric_convertible_percent_gte": 90.0},
                }
            )

    for row in missing_by_col[:80]:
        if not isinstance(row, dict):
            continue
        col = row.get("column")
        if not isinstance(col, str) or not col.strip():
            continue
        col = col.strip()
        try:
            missing_percent = float(row.get("missing_percent") or 0.0)
        except Exception:
            missing_percent = 0.0
        if missing_percent <= 0:
            continue

        rep = columns_meta.get(col) if isinstance(columns_meta, dict) else None
        dtype = str(rep.get("type") if isinstance(rep, dict) else "").strip().lower()
        is_numeric = any(token in dtype for token in ["int", "float", "double", "number", "numeric", "decimal"])
        is_critical = col in critical_cols

        if missing_percent >= 60.0 and not is_critical:
            operations.append(
                {
                    "type": "exclude_from_models",
                    "columns": [col],
                    "when": {"missing_percent_gte": 60.0},
                }
            )
            continue

        if is_numeric:
            if missing_percent <= 20.0:
                operations.append(
                    {
                        "type": "fill_median",
                        "columns": [col],
                        "when": {"missing_percent_lte": 20.0},
                    }
                )
            elif is_critical:
                operations.append(
                    {
                        "type": "mice",
                        "columns": [col],
                        "when": {"missing_percent_gt": 20.0},
                    }
                )
            continue

        if missing_percent <= 10.0:
            operations.append(
                {
                    "type": "fill_mode",
                    "columns": [col],
                    "when": {"missing_percent_lte": 10.0},
                }
            )
        elif is_critical:
            operations.append(
                {
                    "type": "fill_mode",
                    "columns": [col],
                    "when": {"missing_percent_gt": 10.0},
                    "note": "critical_column",
                }
            )

    notes: List[str] = []
    if strict_mode:
        notes.append(
            "Strict mode (publication/expert): cleaning plan должен быть применён и зафиксирован в cleaning_log перед execute."
        )
    if prep_mode:
        notes.append("Data Prep mode: сначала завершите интерактивную очистку и только затем переходите к планированию/execute.")
    if len(operations) <= 1:
        notes.append("Критичных авто-операций по scan_report не найдено; проверьте plan вручную.")

    return {
        "version": 1,
        "required": bool(strict_mode or prep_mode),
        "operations": operations,
        "notes": notes,
    }


def _read_cleaning_log(base_dir: str, dataset_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(str(base_dir), str(dataset_id), "processed", "cleaning_log.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _build_cleaning_artifact_info(
    *,
    base_dir: str,
    dataset_id: str,
    df: pd.DataFrame,
) -> Dict[str, Any]:
    artifact = load_cleaning_run_artifact(base_dir, dataset_id)
    if isinstance(artifact, dict):
        valid, reason = validate_cleaning_run_artifact(artifact, current_df=df)
        operations = artifact.get("operations") if isinstance(artifact.get("operations"), list) else []
        after = artifact.get("after") if isinstance(artifact.get("after"), dict) else {}
        return {
            "artifact_exists": True,
            "artifact_kind": "cleaning_run",
            "valid": bool(valid),
            "reason": str(reason or "unknown"),
            "operations_count": int(len([x for x in operations if isinstance(x, dict)])),
            "fingerprint": str(after.get("fingerprint") or cleaning_run_dataframe_fingerprint(df)),
            "artifact": artifact,
        }

    legacy = _read_cleaning_log(base_dir, dataset_id)
    if isinstance(legacy, dict):
        operations_count = 0
        if isinstance(legacy.get("operations"), list):
            operations_count = len([x for x in legacy.get("operations") if isinstance(x, dict)])
        elif isinstance(legacy.get("auto"), dict) and isinstance(legacy.get("auto", {}).get("actions"), list):
            operations_count = len([x for x in legacy.get("auto", {}).get("actions") if isinstance(x, dict)])
        elif isinstance(legacy.get("action"), str) and legacy.get("action").strip():
            operations_count = 1
        return {
            "artifact_exists": True,
            "artifact_kind": "cleaning_log_legacy",
            "valid": False,
            "reason": "legacy_cleaning_log_only",
            "operations_count": int(operations_count),
            "fingerprint": cleaning_run_dataframe_fingerprint(df),
            "artifact": legacy,
        }

    return {
        "artifact_exists": False,
        "artifact_kind": "missing",
        "valid": False,
        "reason": "missing_cleaning_run",
        "operations_count": 0,
        "fingerprint": cleaning_run_dataframe_fingerprint(df),
    }


def _build_cohort_plan(
    *,
    protocol: List[Dict[str, Any]],
    preferences: Dict[str, Any],
    analysis_mode: str,
) -> Dict[str, Any]:
    if analysis_mode == "data_prep":
        return {
            "version": 1,
            "required": False,
            "mode": None,
            "enforce": None,
            "strict": False,
            "analysis_set_id": None,
            "required_non_missing": [],
            "impute_columns": [],
            "notes": [
                "Data Prep mode: fixed cohort отключён. Сначала очистите/подготовьте датасет, затем переключитесь в discovery/confirmatory."
            ],
        }

    strict_mode = analysis_mode in {"publication", "expert_comprehensive"}
    inferred = _infer_protocol_column_sets(protocol)
    required_all = inferred.get("required_all") or []
    predictor_like = inferred.get("predictor_like") or []
    outcomes = inferred.get("outcomes") or []

    mode_raw = (
        preferences.get("analysis_set_mode")
        or preferences.get("fixed_cohort_mode")
        or preferences.get("cohort_mode")
        or "complete_case"
    )
    mode = str(mode_raw or "").strip().lower() or "complete_case"
    if mode not in {"complete_case", "simple_impute"}:
        mode = "complete_case"

    enforce_raw = preferences.get("analysis_set_enforce") or preferences.get("fixed_cohort_enforce") or "models"
    enforce = str(enforce_raw or "").strip().lower() or "models"
    if enforce not in {"models", "all"}:
        enforce = "models"

    strict = _as_bool(preferences.get("analysis_set_strict"), default=True)
    if strict_mode:
        strict = True

    impute_columns: List[str] = []
    required_non_missing: List[str] = list(required_all)
    if mode == "simple_impute":
        impute_columns = sorted([c for c in predictor_like if c in set(required_all)])
        required_non_missing = sorted([c for c in required_all if c not in set(impute_columns)])
        if not required_non_missing:
            required_non_missing = sorted(outcomes[:1] or required_all[:1])

    analysis_set_id = str(preferences.get("analysis_set_id") or preferences.get("analysis_set") or "").strip() or None
    required = bool(required_all) or strict_mode

    notes: List[str] = []
    if strict_mode:
        notes.append("Strict mode (publication/expert): freeze cohort обязателен, иначе execute будет отклонён.")
    if not required_all:
        notes.append("В текущем протоколе не найдено регрессионных шагов; зафиксируйте cohort вручную при необходимости.")

    return {
        "version": 1,
        "required": required,
        "mode": mode,
        "enforce": enforce,
        "strict": strict,
        "analysis_set_id": analysis_set_id,
        "required_non_missing": required_non_missing,
        "impute_columns": impute_columns,
        "notes": notes,
    }


def _build_report_spec(*, protocol: List[Dict[str, Any]], analysis_mode: str) -> Dict[str, Any]:
    if analysis_mode == "data_prep":
        return {
            "version": 1,
            "style": "prep",
            "sections": [
                {"id": "data_quality", "title": "Data Quality", "required": True},
                {"id": "cleaning_actions", "title": "Cleaning Actions", "required": True},
            ],
            "table_requirements": [
                {"id": "missingness_before_after", "required": True, "description": "Missingness before/after cleaning."}
            ],
            "figure_requirements": [],
            "interpretation_rules": {
                "per_table": True,
                "per_figure": False,
                "link_to_research_question": False,
            },
            "strict_interpretations": False,
            "export_formats": ["html", "docx", "pdf"],
        }

    inferred = _infer_protocol_column_sets(protocol)
    methods = set(inferred.get("methods") or [])
    strict_mode = analysis_mode in {"publication", "expert_comprehensive"}

    sections = [
        {"id": "design", "title": "Design", "required": True},
        {"id": "methods", "title": "Methods", "required": True},
        {"id": "results", "title": "Results", "required": True},
        {"id": "discussion", "title": "Discussion", "required": True},
        {"id": "limitations", "title": "Limitations", "required": True},
    ]

    table_requirements: List[Dict[str, Any]] = [
        {"id": "baseline", "required": True, "description": "Baseline descriptives by group/time."},
        {"id": "inferential_summary", "required": True, "description": "Inferential summary with p and p(adj)."},
    ]

    if methods & {"linear_regression", "logistic_regression"}:
        table_requirements.append(
            {"id": "model_coefficients", "required": True, "description": "Regression coefficients/OR with CI."}
        )
    if methods & {"bootstrap_pipeline"}:
        table_requirements.append(
            {"id": "bootstrap_stability", "required": True, "description": "Bootstrap CI and effect stability summary."}
        )
    if methods & {"cluster_profiles"}:
        table_requirements.append(
            {"id": "cluster_profiles", "required": True, "description": "Cluster composition and profile table."}
        )
    if methods & {"external_validation"}:
        table_requirements.append(
            {"id": "external_validation", "required": True, "description": "Internal vs external validation metrics."}
        )
    if methods & {"random_forest", "gradient_boosting", "knn", "svm"}:
        table_requirements.append(
            {"id": "ml_benchmark", "required": True, "description": "ML performance metrics with train/test split."}
        )
    if methods & {"batch_analysis", "timepoint_batch_analysis", "delta_batch_analysis"}:
        table_requirements.append(
            {"id": "multiplicity", "required": True, "description": "Multiplicity correction and adjusted p-values."}
        )

    figure_requirements: List[Dict[str, Any]] = []
    if methods & {
        "linear_regression",
        "logistic_regression",
        "roc_analysis",
        "random_forest",
        "gradient_boosting",
        "knn",
        "svm",
        "external_validation",
    }:
        figure_requirements.append({"id": "model_diagnostics", "required": strict_mode})
        figure_requirements.append({"id": "roc_curve", "required": strict_mode})
    if methods & {"clustered_correlation", "pearson", "spearman", "cluster_profiles"}:
        figure_requirements.append({"id": "correlation_heatmap", "required": strict_mode})
    if methods & {"t_test_ind", "t_test_welch", "mann_whitney", "anova", "anova_welch", "kruskal", "bootstrap_pipeline"}:
        figure_requirements.append({"id": "group_distribution", "required": strict_mode})
    if methods & {"mixed_effects", "rm_anova", "friedman", "timepoint_batch_analysis", "delta_batch_analysis", "responders"}:
        figure_requirements.append({"id": "trajectory", "required": strict_mode})

    return {
        "version": 1,
        "style": "expert" if analysis_mode == "expert_comprehensive" else ("publication" if analysis_mode == "publication" else ("discovery" if analysis_mode == "discovery" else "standard")),
        "sections": sections,
        "table_requirements": table_requirements,
        "figure_requirements": figure_requirements,
        "interpretation_rules": {
            "per_table": True,
            "per_figure": True,
            "link_to_research_question": True,
        },
        "strict_interpretations": strict_mode,
        "export_formats": ["html", "docx", "pdf"],
    }


def _build_protocol_coverage_report(
    *,
    protocol: List[Dict[str, Any]],
    study_design: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    inferred = _infer_protocol_column_sets(protocol)
    covered = set(inferred.get("outcomes") or [])

    design = study_design.get("design") if isinstance(study_design, dict) else {}
    design = design if isinstance(design, dict) else {}
    target_outcomes = []
    for col in [*(design.get("outcomes") or []), *(design.get("categorical_outcomes") or [])]:
        text = str(col or "").strip()
        if text and text not in target_outcomes:
            target_outcomes.append(text)

    if not target_outcomes:
        target_outcomes = list(dict.fromkeys([str(c) for c in (inferred.get("outcomes") or []) if str(c).strip()]))

    covered_targets = [c for c in target_outcomes if c in covered]
    missing_targets = [c for c in target_outcomes if c not in covered]
    ratio = (len(covered_targets) / float(max(1, len(target_outcomes)))) if target_outcomes else 1.0
    return {
        "target_total": int(len(target_outcomes)),
        "covered_total": int(len(covered_targets)),
        "coverage_ratio": float(round(ratio, 4)),
        "covered_outcomes": covered_targets[:200],
        "missing_outcomes": missing_targets[:200],
        "status": "ok" if ratio >= 0.95 else "partial",
    }


def _merge_plan_section(default_section: Dict[str, Any], incoming: Any) -> Dict[str, Any]:
    if not isinstance(default_section, dict):
        return default_section
    if not isinstance(incoming, dict):
        return default_section
    out = dict(default_section)
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        out[key] = value
    return out

# --- Request Models ---

class MixedEffectsRequest(BaseModel):
    """Request model for Linear Mixed Models."""
    dataset_id: str = Field(..., description="Dataset identifier")
    outcome: str = Field(..., description="Dependent variable column")
    time_col: str = Field(..., description="Time variable column")
    group_col: str = Field(..., description="Group variable column")
    subject_col: str = Field(..., description="Subject ID column")
    covariates: Optional[List[str]] = Field([], description="Covariate columns")
    random_slope: bool = Field(False, description="Include random slopes")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")

class ClusteredCorrelationRequest(BaseModel):
    """Request model for jYS-style clustered correlation."""
    dataset_id: str = Field(..., description="Dataset identifier")
    variables: List[str] = Field(..., description="Variables to include in correlation matrix")
    method: Literal["pearson", "spearman"] = Field("pearson", description="Correlation method")
    linkage_method: Literal["ward", "complete", "average", "single"] = Field("ward", description="Clustering linkage")
    n_clusters: Optional[int] = Field(None, ge=1, le=20, description="Number of clusters (auto-detect if None)")
    distance_threshold: Optional[float] = Field(None, ge=0.0, le=2.0, description="Distance threshold for clustering")
    show_p_values: bool = Field(True, description="Include p-values in results")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")

class ProtocolV2Request(BaseModel):
    """Request model for v2 analysis protocol."""
    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: Dict[str, Any] = Field(..., description="Analysis protocol configuration")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")


class AnalysisTemplateListResponse(BaseModel):
    templates: List[Dict[str, str]]


@router.get("/analysis/templates", response_model=AnalysisTemplateListResponse)
async def list_analysis_templates(goal: Optional[str] = None):
    try:
        designer = StudyDesignEngine()
        return {"templates": designer.list_templates(goal=goal)}
    except Exception as e:
        logger.error(f"Template listing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить список шаблонов: {str(e)}")


class AnalysisTemplateDesignRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset identifier")
    goal: str = Field(..., description="Study goal")
    template_id: Optional[str] = Field(None, description="Template identifier")
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variable mapping")


class AnalysisPlanRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset identifier")
    text: str = Field(..., description="Research design description")
    protocol: Optional[List[Dict[str, Any]]] = Field(None, description="Current protocol for context")
    preferences: Optional[Dict[str, Any]] = Field(None, description="Global preferences")


class AnalysisBriefRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset identifier")
    preferences: Optional[Dict[str, Any]] = Field(None, description="Global preferences")


@router.get("/telemetry/legacy", response_model=Dict[str, Any])
async def legacy_telemetry_snapshot(x_telemetry_token: Optional[str] = Header(default=None, alias="X-Telemetry-Token")):
    expected = getattr(settings, "CLINIMETRIA_TELEMETRY_TOKEN", None)
    if expected:
        provided = str(x_telemetry_token or "").strip()
        if provided != str(expected):
            raise HTTPException(status_code=403, detail="Telemetry access denied")
    return get_legacy_snapshot()


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
        dataset_meta = build_ai_context(dataset_id=dataset_id, base_dir=DATA_DIR)
        prompt = generate_prompt_brief(dataset_meta, request.preferences)
        return {"prompt": prompt}
    except Exception as e:
        logger.error(f"Brief generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать бриф: {str(e)}")


@router.post("/analysis/plan", response_model=Dict[str, Any])
async def plan_analysis_with_ai(request: AnalysisPlanRequest):
    try:
        df = await load_dataset_async(request.dataset_id)
        dataset_meta = build_ai_context(dataset_id=request.dataset_id, base_dir=DATA_DIR, df=df)
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

        prefs_enriched = dict(prefs)
        prefs_enriched["analysis_mode"] = analysis_mode
        prefs_enriched["mode"] = analysis_mode
        columns_meta = scan_report.get("columns") if isinstance(scan_report, dict) else {}
        if isinstance(columns_meta, dict):
            prefs_enriched["n_columns"] = int(len(columns_meta))
        study_design_for_constraints = load_study_design(DATA_DIR, request.dataset_id)
        design_for_constraints = (
            study_design_for_constraints.get("design")
            if isinstance(study_design_for_constraints, dict) and isinstance(study_design_for_constraints.get("design"), dict)
            else {}
        )
        if isinstance(design_for_constraints, dict):
            outcome_count = len([*(design_for_constraints.get("outcomes") or []), *(design_for_constraints.get("categorical_outcomes") or [])])
            if outcome_count > 0:
                prefs_enriched["n_outcomes"] = int(outcome_count)
        constraints = safe_plan_constraints(prefs_enriched)

        if analysis_mode == "data_prep":
            empty_protocol: List[Dict[str, Any]] = []
            cleaning_plan = _build_cleaning_plan(
                scan_report=scan_report,
                protocol=empty_protocol,
                analysis_mode=analysis_mode,
            )
            cohort_plan = _build_cohort_plan(
                protocol=empty_protocol,
                preferences=prefs_enriched,
                analysis_mode=analysis_mode,
            )
            report_spec = _build_report_spec(protocol=empty_protocol, analysis_mode=analysis_mode)
            globals_out = {"analysis_mode": analysis_mode, "mode": analysis_mode}
            if role_models:
                globals_out["llm_models"] = role_models
            notes_out = [
                "Режим Data Prep: генерация статистического протокола отключена.",
                "Сфокусируйтесь на очистке первички, variable mapping и подтверждении design review.",
                "После подготовки переключитесь в Discovery для генерации гипотез или Confirmatory для строгого анализа.",
            ]
            if design_review_warning:
                notes_out.append(design_review_warning)
            return {
                "status": "completed",
                "protocol_name": "Data Preparation Workflow",
                "globals": globals_out,
                "protocol": empty_protocol,
                "notes": notes_out,
                "quality": {"score": 100.0, "issues": []},
                "critic": None,
                "usage": None,
                "design_review_confirmed": design_review_confirmed,
                "analysis_mode": analysis_mode,
                "cleaning_plan": cleaning_plan,
                "cohort_plan": cohort_plan,
                "report_spec": report_spec,
                "coverage_report": {
                    "status": "n/a",
                    "target_outcomes": [],
                    "covered_outcomes": [],
                    "missing_outcomes": [],
                    "coverage_ratio": 1.0,
                },
            }

        rules_plan = build_exploratory_plan(
            dataset_id=request.dataset_id,
            base_dir=DATA_DIR,
            preferences=prefs_enriched,
            constraints=constraints,
            scan_report=scan_report,
            study_design=study_design_for_constraints,
        )
        rules_protocol = rules_plan.get("protocol") if isinstance(rules_plan, dict) else []
        rules_globals = rules_plan.get("globals") if isinstance(rules_plan, dict) else {}
        rules_notes = rules_plan.get("notes") if isinstance(rules_plan, dict) else []

        ai_payload = await analyze_research_design(
            text=request.text,
            dataset_meta=dataset_meta,
            current_protocol=request.protocol or [],
            preferences=prefs_enriched,
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

                use_exploratory = analysis_mode in {"exploratory", "expert_comprehensive", "discovery"} or bool(
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
                coverage_report = _build_protocol_coverage_report(protocol=protocol_out, study_design=study_design)
                rules_coverage = rules_plan.get("coverage_report") if isinstance(rules_plan, dict) else None
                if isinstance(rules_coverage, dict):
                    coverage_report["rules_coverage"] = rules_coverage
                if coverage_report.get("status") != "ok":
                    notes_out.append(
                        "Coverage report: часть целевых outcomes не покрыта текущим протоколом; "
                        "увеличьте лимиты или примените discovery/comprehensive/publication/expert_comprehensive режим."
                    )

                return {
                    "status": "completed",
                    "protocol_name": protocol_name,
                    "globals": globals_out,
                    "protocol": protocol_out,
                    "notes": notes_out,
                    "quality": quality,
                    "critic": critic_payload,
                    "usage": usage_payload,
                    "design_review_confirmed": design_review_confirmed,
                    "analysis_mode": analysis_mode,
                    "cleaning_plan": cleaning_plan,
                    "cohort_plan": cohort_plan,
                    "report_spec": report_spec,
                    "coverage_report": coverage_report,
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
        coverage_report = _build_protocol_coverage_report(protocol=fallback_protocol, study_design=study_design)
        rules_coverage = rules_plan.get("coverage_report") if isinstance(rules_plan, dict) else None
        if isinstance(rules_coverage, dict):
            coverage_report["rules_coverage"] = rules_coverage
        if coverage_report.get("status") != "ok":
            fallback_notes.append(
                "Coverage report: часть целевых outcomes не покрыта текущим протоколом; "
                "увеличьте лимиты или примените discovery/comprehensive/publication/expert_comprehensive режим."
            )

        return {
            "status": "partial",
            "protocol_name": "Exploratory protocol",
            "globals": fallback_globals,
            "protocol": fallback_protocol,
            "notes": (fallback_notes or [])
            + ["ИИ недоступен или не вернул валидный JSON. Сформирован rules-based протокол."],
            "quality": quality,
            "critic": critic_payload,
            "usage": None,
            "design_review_confirmed": design_review_confirmed,
            "analysis_mode": analysis_mode,
            "cleaning_plan": cleaning_plan,
            "cohort_plan": cohort_plan,
            "report_spec": report_spec,
            "coverage_report": coverage_report,
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

        elif method_id in {"bootstrap_pipeline", "cluster_profiles", "external_validation"}:
            outcome = (
                request.protocol.get("outcome")
                or request.protocol.get("target")
                or request.protocol.get("target_column")
            )
            group = request.protocol.get("group") or request.protocol.get("group_column")
            predictors = request.protocol.get("predictors")
            variables = request.protocol.get("variables")
            task = request.protocol.get("task")
            model_method = request.protocol.get("model_method")
            external_dataset_id = request.protocol.get("external_dataset_id")

            extra: Dict[str, Any] = {
                "predictors": predictors,
                "variables": variables,
                "task": task,
                "model_method": model_method,
                "random_state": request.protocol.get("random_state"),
                "test_size": request.protocol.get("test_size"),
                "n_resamples": request.protocol.get("n_resamples"),
                "ci_level": request.protocol.get("ci_level"),
                "n_clusters": request.protocol.get("n_clusters"),
                "positive_label": request.protocol.get("positive_label"),
            }

            col_a = outcome
            col_b = group

            if method_id == "cluster_profiles":
                vars_list = variables if isinstance(variables, list) else []
                if not vars_list:
                    raise HTTPException(status_code=400, detail="cluster_profiles требует variables (list)")
                col_a = str(vars_list[0])
                col_b = str(vars_list[1]) if len(vars_list) > 1 else str(vars_list[0])

            if method_id == "external_validation":
                ext_id = str(external_dataset_id or "").strip()
                if not ext_id:
                    raise HTTPException(status_code=400, detail="external_validation требует external_dataset_id")
                external_df = await load_dataset_async(ext_id)
                extra["external_dataset_id"] = ext_id
                extra["external_df"] = external_df
                if not col_a:
                    raise HTTPException(status_code=400, detail="external_validation требует outcome/target")
                predictors_list = predictors if isinstance(predictors, list) else []
                if predictors_list and not col_b:
                    col_b = str(predictors_list[0])
                if not col_b:
                    raise HTTPException(status_code=400, detail="external_validation требует predictors")

            if method_id == "bootstrap_pipeline":
                if not col_a:
                    raise HTTPException(status_code=400, detail="bootstrap_pipeline требует outcome/target")
                if not col_b:
                    col_b = str(request.protocol.get("group") or request.protocol.get("group_column") or "")

            if not isinstance(col_a, str) or not col_a.strip():
                raise HTTPException(status_code=400, detail=f"Метод {method_id} требует outcome/target")
            if not isinstance(col_b, str):
                col_b = str(col_b or "")

            result = await run_analysis_async(
                df,
                method_id,
                col_a.strip(),
                col_b.strip(),
                request.alpha,
                **{k: v for k, v in extra.items() if v is not None},
            )
            native = convert_numpy_to_native(result)
            payload = native if isinstance(native, dict) else {"value": native}
            payload = _ensure_method(payload, method_id)
            payload = _maybe_add_conclusion(payload, {"target": col_a.strip(), "group": col_b.strip()})
            return {
                "status": "completed",
                "results": normalize_analysis_result_v2(payload, method_id=method_id, config=request.protocol),
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

class ExecuteProtocolRequest(BaseModel):
    """Request model for batch protocol execution."""
    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: List[Dict[str, Any]] = Field(..., description="List of analysis steps")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")
    protocol_name: Optional[str] = Field(None, description="Human-readable protocol name")
    globals: Optional[Dict[str, Any]] = Field(None, description="Global analysis settings")

@router.post("/analysis/execute", response_model=Dict[str, Any])
async def execute_protocol(request: ExecuteProtocolRequest, background_tasks: BackgroundTasks):
    """
    Execute analysis protocol with batch processing.
    
    Runs multiple statistical tests in sequence with memory management.
    Supports mixed effects, clustered correlation, and all standard methods.
    """
    try:
        df = await load_dataset_async(request.dataset_id)
        globals_in = request.globals if isinstance(request.globals, dict) else {}
        analysis_mode = _normalize_analysis_mode(globals_in.get("analysis_mode") or globals_in.get("mode"))
        if analysis_mode == "data_prep":
            raise HTTPException(
                status_code=400,
                detail=(
                    "analysis_mode=data_prep предназначен только для подготовки данных. "
                    "Перейдите в /prepare/:id, затем используйте analysis_mode=discovery или publication для execute."
                ),
            )
        publication_mode = analysis_mode in {"publication", "expert_comprehensive"}
        if "analysis_mode" not in globals_in:
            globals_in = {**globals_in, "analysis_mode": analysis_mode}

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

        cleaning_artifact_info = _build_cleaning_artifact_info(
            base_dir=DATA_DIR,
            dataset_id=request.dataset_id,
            df=df,
        )
        if publication_mode and not bool(cleaning_artifact_info.get("valid")):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Publication mode требует применённый cleaning_run artifact "
                    "(processed/cleaning_run.json, fingerprint совпадает с текущим processed dataset). "
                    "Выполните prepare/очистку датасета перед execute."
                ),
            )
        if not publication_mode and not bool(cleaning_artifact_info.get("valid")):
            warnings.append(
                "Cleaning artifact не найден или невалиден; reproducibility для preprocessing может быть ограничена."
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
        external_dataset_cache: Dict[str, pd.DataFrame] = {}
        
        for step in request.protocol:
            method_id = _canonical_method_id(step.get("method"))
            raw_config = step.get("config", {})
            config = raw_config if isinstance(raw_config, dict) else {}
            if globals_in:
                config = {**globals_in, **config}
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
            step_id = step.get("id", f"step_{len(results) + 1}")
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
            
            try:
                # Advanced methods
                if method_id == "mixed_effects":
                    outcome = config.get("outcome")
                    time_col = config.get("time")
                    group_col = config.get("group")
                    subject_col = config.get("subject")
                    covariates = config.get("covariates", [])
                    random_slope = config.get("random_slope", False)
                    engine_mode = str(config.get("engine") or "").strip().lower()

                    if engine_mode in {"r", "r_engine", "rstats"}:
                        result = await run_analysis_async(
                            df_step,
                            "mixed_effects",
                            outcome,
                            group_col,
                            request.alpha,
                            group_col=group_col,
                            time_col=time_col,
                            subject_col=subject_col,
                            covariates=covariates,
                            random_slope=random_slope,
                            engine=config.get("engine"),
                        )
                    else:
                        result = await _run_in_process_pool(
                            _run_mixed_effects_sync,
                            df_step, outcome, time_col, group_col, subject_col,
                            covariates, random_slope, request.alpha
                        )
                    
                    payload = {
                        "type": "mixed_effects",
                        "method": {"id": "mixed_effects", "name": "Mixed Effects"},
                        **convert_numpy_to_native(result)
                    }

                    p_value = payload.get("interaction_p_value")
                    if p_value is None:
                        interaction = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else None
                        p_value = interaction.get("min_p_value") if interaction else None
                    if p_value is None:
                        p_value = payload.get("p_value")
                    payload["p_value"] = p_value
                    payload["significant"] = (bool(p_value < request.alpha) if isinstance(p_value, (int, float)) else None)

                    interaction = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else None
                    interpretation = interaction.get("interpretation") if interaction else None
                    if isinstance(interpretation, str) and interpretation.strip():
                        payload["conclusion"] = interpretation.strip()

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
                    )

                    payload = {
                        "type": "batch_analysis",
                        "method_id": method_id_batch,
                        "group": group,
                        "items": convert_numpy_to_native(items),
                        "multiplicity_correction": multiplicity,
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
                        )
                        slices[str(val)] = {
                            "type": "batch_analysis",
                            "method_id": method_id_batch,
                            "group": group,
                            "items": convert_numpy_to_native(items),
                            "multiplicity_correction": multiplicity,
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
                    baseline = config.get("baseline")
                    follow = config.get("follow")
                    method_used = str(config.get("method") or config.get("method_id") or "t_test_rel").strip()
                    alternative = config.get("alternative") or "two-sided"
                    if not baseline or not follow:
                        raise ValueError("paired_wide требует baseline и follow")
                    if baseline not in df_step.columns or follow not in df_step.columns:
                        raise ValueError("paired_wide: колонка baseline/follow не найдена")

                    local = df_step[[baseline, follow]].copy()
                    local[baseline] = pd.to_numeric(local[baseline], errors="coerce")
                    local[follow] = pd.to_numeric(local[follow], errors="coerce")
                    local = local.dropna(subset=[baseline, follow])
                    if local.empty:
                        raise ValueError("paired_wide: нет данных после фильтрации пропусков")

                    x = local[baseline]
                    y = local[follow]
                    delta = y - x
                    n = int(delta.shape[0])

                    stat_val = None
                    p_val = None
                    eff_size = None
                    eff_size_name = None
                    eff_ci_lower = None
                    eff_ci_upper = None
                    power = None
                    bf10 = None

                    try:
                        import pingouin as pg  # type: ignore

                        if method_used == "wilcoxon":
                            res = pg.wilcoxon(x, y, alternative=alternative)
                            stat_val = float(res["W-val"].iloc[0]) if "W-val" in res.columns else float(res["W"].iloc[0])
                            p_val = float(res["p-val"].iloc[0])
                            if "RBC" in res.columns:
                                eff_size = float(res["RBC"].iloc[0])
                                eff_size_name = "rbc"
                        else:
                            method_used = "t_test_rel"
                            res = pg.ttest(x, y, paired=True, alternative=alternative, correction=False)
                            stat_val = float(res["T"].iloc[0])
                            p_val = float(res["p-val"].iloc[0])
                            if "cohen-d" in res.columns:
                                eff_size = float(res["cohen-d"].iloc[0])
                                eff_size_name = "cohen-d"
                            if "CI95%" in res.columns:
                                ci = res["CI95%"].iloc[0]
                                if isinstance(ci, (list, tuple)) and len(ci) == 2:
                                    eff_ci_lower, eff_ci_upper = float(ci[0]), float(ci[1])
                            if "power" in res.columns:
                                try:
                                    power = float(res["power"].iloc[0])
                                except Exception:
                                    power = None
                            if "BF10" in res.columns:
                                try:
                                    bf10 = float(res["BF10"].iloc[0])
                                except Exception:
                                    bf10 = None
                    except Exception as e:
                        raise ValueError(f"paired_wide: ошибка вычисления ({e})")

                    engine_mode = str(config.get("engine") or "").strip().lower()
                    if engine_mode in {"r", "r_engine", "rstats"}:
                        try:
                            from app.stats.r_engine import run_analysis_r
                            r_method = "wilcoxon" if method_used == "wilcoxon" else "t_test_rel"
                            r_res = run_analysis_r(
                                df_step,
                                r_method,
                                baseline,
                                follow,
                                is_paired=True,
                                alpha=request.alpha,
                                python_fallback=None,
                                alternative=alternative,
                            )
                            if isinstance(r_res, dict):
                                if r_res.get("p_value") is not None:
                                    p_val = r_res.get("p_value")
                                if r_res.get("stat_value") is not None:
                                    stat_val = r_res.get("stat_value")
                                if r_res.get("effect_size") is not None:
                                    eff_size = r_res.get("effect_size")
                                    eff_size_name = r_res.get("effect_size_name") or eff_size_name
                        except Exception as e:
                            logger.warning(f"paired_wide R engine failed: {e}")

                    if eff_size is None and n > 1:
                        try:
                            sd = float(delta.std(ddof=1))
                            mean_d = float(delta.mean())
                            if sd != 0:
                                eff_size = mean_d / sd
                                eff_size_name = eff_size_name or "cohen-d"
                        except Exception:
                            pass

                    payload = {
                        "type": "hypothesis_test",
                        "method": {"id": "paired_wide", "name": "Paired Wide"},
                        "test_used": method_used,
                        "baseline": baseline,
                        "follow": follow,
                        "n": n,
                        "stat_value": stat_val,
                        "p_value": p_val,
                        "significant": bool(p_val is not None and p_val < request.alpha),
                        "effect_size": eff_size,
                        "effect_size_name": eff_size_name,
                        "effect_ci_lower": eff_ci_lower,
                        "effect_ci_upper": eff_ci_upper,
                        "power": power,
                        "bf10": bf10,
                        "delta_summary": {
                            "mean": float(delta.mean()) if n else None,
                            "median": float(delta.median()) if n else None,
                            "std": float(delta.std(ddof=1)) if n > 1 else None,
                            "min": float(delta.min()) if n else None,
                            "max": float(delta.max()) if n else None,
                        },
                    }

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
                    group = config.get("group")
                    pairs = config.get("pairs")
                    if not group or not isinstance(pairs, list) or not pairs:
                        raise ValueError("delta_batch_analysis требует group и pairs")
                    if group not in df_step.columns:
                        raise ValueError(f"delta_batch_analysis: колонка group не найдена: {group}")

                    method_id_batch = config.get("method_id") or config.get("method") or "auto"
                    multiplicity = _normalize_correction(config.get("multiplicity_correction")) or "fdr_bh"
                    post_hoc = config.get("post_hoc")
                    post_hoc_correction = _normalize_correction(config.get("post_hoc_correction"))
                    auto_fallback = bool(config.get("auto_fallback", True))
                    alternative = config.get("alternative")

                    local = df_step.copy()
                    delta_cols: List[str] = []
                    pair_meta: Dict[str, Dict[str, Any]] = {}

                    for idx, pair in enumerate(pairs):
                        if not isinstance(pair, dict):
                            continue
                        baseline = pair.get("baseline")
                        follow = pair.get("follow")
                        if not baseline or not follow:
                            continue
                        if baseline not in df_step.columns or follow not in df_step.columns:
                            continue
                        delta_col = f"delta_{idx+1}"
                        local[delta_col] = pd.to_numeric(local[follow], errors="coerce") - pd.to_numeric(
                            local[baseline], errors="coerce"
                        )
                        delta_cols.append(delta_col)
                        pair_meta[delta_col] = {
                            "baseline": baseline,
                            "follow": follow,
                            "label": pair.get("label"),
                        }

                    if not delta_cols:
                        raise ValueError("delta_batch_analysis: не удалось сформировать Δ-колонки")

                    items = run_batch_analysis(
                        local,
                        delta_cols,
                        group_col=group,
                        method_id=method_id_batch,
                        alpha=request.alpha,
                        auto_fallback=auto_fallback,
                        multiplicity_correction=multiplicity,
                        post_hoc=post_hoc,
                        post_hoc_correction=post_hoc_correction,
                        engine=config.get("engine"),
                        **({"alternative": alternative} if alternative else {}),
                    )

                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        meta = pair_meta.get(item.get("target"))
                        if meta:
                            item.update(meta)

                    payload = {
                        "type": "batch_analysis",
                        "mode": "delta",
                        "group": group,
                        "method_id": method_id_batch,
                        "items": convert_numpy_to_native(items),
                        "pairs": list(pair_meta.values()),
                        "multiplicity_correction": multiplicity,
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
                    )

                    payload = convert_numpy_to_native({**result, "type": "hypothesis_test", "auto_selected": selected})
                    payload = _ensure_method(payload, selected)
                    variables = {"target": outcome, "group": group}
                    if selected in {"pearson", "spearman"}:
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

                # Standard methods fallback
                elif method_id in STANDARD_METHODS or method_id == "anova_twoway":
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group")
                    predictors = config.get("predictors")
                    covariates = config.get("covariates")
                    post_hoc = config.get("post_hoc")
                    post_hoc_correction = config.get("post_hoc_correction")
                    alternative = config.get("alternative")

                    if method_id == "anova_twoway":
                        group1 = config.get("group1")
                        group2 = config.get("group2")
                        if not outcome or not group1 or not group2:
                            raise ValueError("anova_twoway требует outcome, group1 и group2")
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
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "group1": group1, "group2": group2})
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

                    if method_id == "bootstrap_pipeline":
                        group_for_bootstrap = group
                        if not outcome:
                            raise ValueError("bootstrap_pipeline требует outcome/target")
                        if not isinstance(group_for_bootstrap, str):
                            group_for_bootstrap = ""

                        result = await run_analysis_async(
                            df_step,
                            method_id,
                            outcome,
                            group_for_bootstrap,
                            request.alpha,
                            statistic=config.get("statistic"),
                            n_resamples=config.get("n_resamples"),
                            ci_level=config.get("ci_level"),
                            random_state=config.get("random_state"),
                            null_value=config.get("null_value"),
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_id)
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "group": group_for_bootstrap})
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

                    if method_id == "cluster_profiles":
                        vars_in = config.get("variables")
                        if not isinstance(vars_in, list) or len(vars_in) < 2:
                            raise ValueError("cluster_profiles требует variables (минимум 2)")
                        col_a_cluster = str(vars_in[0])
                        col_b_cluster = str(vars_in[1]) if len(vars_in) > 1 else str(vars_in[0])
                        result = await run_analysis_async(
                            df_step,
                            method_id,
                            col_a_cluster,
                            col_b_cluster,
                            request.alpha,
                            variables=vars_in,
                            n_clusters=config.get("n_clusters"),
                            scale=config.get("scale"),
                            random_state=config.get("random_state"),
                            include_embedding=config.get("include_embedding"),
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_id)
                        payload = _maybe_add_conclusion(payload, {"target": col_a_cluster})
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

                    if method_id == "external_validation":
                        if not outcome:
                            raise ValueError("external_validation требует outcome/target")
                        if not isinstance(predictors, list):
                            predictors = []
                        predictors = [str(p) for p in predictors if isinstance(p, str) and p.strip()]
                        if not predictors and isinstance(group, str) and group.strip():
                            predictors = [group.strip()]
                        if not predictors:
                            raise ValueError("external_validation требует predictors")

                        external_dataset_id = str(
                            config.get("external_dataset_id")
                            or config.get("validation_dataset_id")
                            or ""
                        ).strip()
                        if not external_dataset_id:
                            raise ValueError("external_validation требует external_dataset_id")

                        if external_dataset_id not in external_dataset_cache:
                            external_dataset_cache[external_dataset_id] = await load_dataset_async(external_dataset_id)
                        external_df = external_dataset_cache[external_dataset_id]

                        col_b = predictors[0]
                        task = str(config.get("task") or "").strip().lower()
                        if task not in {"classification", "regression"}:
                            task = "regression"
                            try:
                                if outcome in df_step.columns:
                                    uniq = int(df_step[outcome].dropna().nunique())
                                    if 1 < uniq <= 2:
                                        task = "classification"
                            except Exception:
                                task = "regression"

                        result = await run_analysis_async(
                            df_step,
                            method_id,
                            outcome,
                            col_b,
                            request.alpha,
                            predictors=predictors,
                            task=task,
                            model_method=config.get("model_method"),
                            test_size=float(config.get("test_size") or 0.25),
                            random_state=config.get("random_state"),
                            positive_label=config.get("positive_label"),
                            external_dataset_id=external_dataset_id,
                            external_df=external_df,
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_id)
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "predictor": col_b})
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

                    if method_id in ["linear_regression", "logistic_regression"]:
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
                            method_id,
                            outcome,
                            col_b,
                            request.alpha,
                            predictors=predictors,
                            covariates=covariates,
                            show_or=bool(config.get("show_or", True)),
                            show_roc=bool(config.get("show_roc", True)),
                            one_vs_rest=bool(config.get("one_vs_rest", False)),
                            positive_label=config.get("positive_label"),
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_id)
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "predictor": col_b})
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

                    if method_id in {"random_forest", "gradient_boosting", "knn", "svm"}:
                        if not outcome:
                            raise ValueError(f"Отсутствуют обязательные параметры для {method_id}")
                        if not isinstance(predictors, list):
                            predictors = []
                        predictors = [str(p) for p in predictors if isinstance(p, str) and p.strip()]
                        if not predictors and isinstance(group, str) and group.strip():
                            predictors = [group.strip()]
                        if not predictors:
                            raise ValueError(f"Не указаны предикторы для {method_id}")

                        col_b = predictors[0]
                        task = str(config.get("task") or "").strip().lower()
                        if task not in {"classification", "regression"}:
                            task = "regression"
                            try:
                                if outcome in df_step.columns:
                                    uniq = int(df_step[outcome].dropna().nunique())
                                    if 1 < uniq <= 2:
                                        task = "classification"
                            except Exception:
                                task = "regression"

                        result = await run_analysis_async(
                            df_step,
                            method_id,
                            outcome,
                            col_b,
                            request.alpha,
                            predictors=predictors,
                            task=task,
                            test_size=float(config.get("test_size") or 0.25),
                            random_state=config.get("random_state"),
                            n_neighbors=config.get("n_neighbors"),
                            C=config.get("C"),
                            kernel=config.get("kernel"),
                            positive_label=config.get("positive_label"),
                        )
                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_id)
                        payload = _maybe_add_conclusion(payload, {"target": outcome, "predictor": col_b})
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

                    if outcome and group:
                        extra = {}
                        if method_id in {"anova", "anova_welch", "kruskal"}:
                            if post_hoc is not None:
                                extra["post_hoc"] = post_hoc
                            if post_hoc_correction is not None:
                                extra["post_hoc_correction"] = post_hoc_correction
                        if alternative is not None and method_id in {"t_test_ind", "t_test_welch", "mann_whitney", "t_test_rel", "wilcoxon", "pearson", "spearman"}:
                            extra["alternative"] = alternative
                        elif alternative is not None and method_id in {"chi_square"}:
                            pass

                        result = await run_analysis_async(
                            df_step,
                            method_id,
                            outcome,
                            group,
                            request.alpha,
                            is_paired=bool(config.get("is_paired", False)),
                            predictors=predictors,
                            **extra,
                        )

                        payload = convert_numpy_to_native({**result, "type": "hypothesis_test"})
                        payload = _ensure_method(payload, method_id)
                        variables = {"target": outcome, "group": group}
                        if method_id in {"pearson", "spearman"}:
                            variables = {"target": outcome, "predictor": group}
                        payload = _maybe_add_conclusion(payload, variables)
                        results.append(
                            {
                                "step_id": step_id,
                                "method": method_id,
                                "status": "completed",
                                "results": payload,
                            }
                        )
                        results_map[step_id] = payload
                    else:
                        raise ValueError(f"Отсутствуют обязательные параметры для {method_id}")
                
                else:
                    raise ValueError(f"Метод {method_id} не реализован")
                
                # Force garbage collection after each step
                gc.collect()
                
            except Exception as e:
                logger.error(f"Step {step_id} failed: {e}", exc_info=True)
                errors.append({
                    "step_id": step_id,
                    "method": method_id,
                    "error": str(e)
                })

        results_map = normalize_results_map(results_map, step_meta=step_meta_map)
        results_map = _attach_interpretation_contracts(
            results_map=results_map,
            step_meta_map=step_meta_map,
            publication_mode=publication_mode,
            warnings=warnings,
        )
        results = normalize_results_list(results, step_meta=step_meta_map)
        for idx, item in enumerate(results):
            if not isinstance(item, dict):
                continue
            step_id = str(item.get("step_id") or "").strip()
            if not step_id:
                continue
            payload = results_map.get(step_id)
            if isinstance(payload, dict):
                next_item = dict(item)
                next_item["results"] = payload
                results[idx] = next_item

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

        pipeline.save_run_results(
            run_dir,
            {
                "protocol_name": protocol_name,
                "dataset_id": request.dataset_id,
                "alpha": request.alpha,
                "analysis_mode": analysis_mode,
                "publication_mode": publication_mode,
                "globals": globals_in,
                "results": results_map,
                "step_meta": step_meta_map,
                "status": "completed" if not errors else "partial",
                "errors": errors,
                "total_steps": len(request.protocol),
                "completed_steps": len(results_map),
                "failed_steps": len(errors),
                "warnings": warnings,
                "analysis_dataset": analysis_dataset_artifacts,
                "cleaning_artifact": {
                    "artifact_exists": bool(cleaning_artifact_info.get("artifact_exists")),
                    "artifact_kind": cleaning_artifact_info.get("artifact_kind"),
                    "valid": bool(cleaning_artifact_info.get("valid")),
                    "reason": cleaning_artifact_info.get("reason"),
                    "operations_count": int(cleaning_artifact_info.get("operations_count") or 0),
                    "fingerprint": cleaning_artifact_info.get("fingerprint"),
                },
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
                "design_review": {
                    "required": require_design_review,
                    "confirmed": design_review_confirmed,
                    "timestamp": design_review_timestamp,
                    "artifact_exists": design_review_artifact_exists,
                    "artifact_confirmed": design_review_artifact_confirmed,
                    "confirmed_by": design_review_confirmed_by,
                    "confirmed_source": design_review_confirmed_source,
                },
            },
        )

        result_ir = pipeline.build_result_ir(
            {
                "protocol_name": protocol_name,
                "dataset_id": request.dataset_id,
                "analysis_mode": analysis_mode,
                "publication_mode": publication_mode,
                "results": results_map,
                "step_meta": step_meta_map,
                "status": "completed" if not errors else "partial",
                "errors": errors,
                "total_steps": len(request.protocol),
                "completed_steps": len(results_map),
                "failed_steps": len(errors),
                "warnings": warnings,
                "analysis_dataset": analysis_dataset_artifacts,
                "cleaning_artifact": {
                    "artifact_exists": bool(cleaning_artifact_info.get("artifact_exists")),
                    "artifact_kind": cleaning_artifact_info.get("artifact_kind"),
                    "valid": bool(cleaning_artifact_info.get("valid")),
                    "reason": cleaning_artifact_info.get("reason"),
                    "operations_count": int(cleaning_artifact_info.get("operations_count") or 0),
                    "fingerprint": cleaning_artifact_info.get("fingerprint"),
                },
            }
        )
        
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
            "cleaning_artifact": {
                "artifact_exists": bool(cleaning_artifact_info.get("artifact_exists")),
                "artifact_kind": cleaning_artifact_info.get("artifact_kind"),
                "valid": bool(cleaning_artifact_info.get("valid")),
                "reason": cleaning_artifact_info.get("reason"),
                "operations_count": int(cleaning_artifact_info.get("operations_count") or 0),
                "fingerprint": cleaning_artifact_info.get("fingerprint"),
            },
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
            "total_steps": len(request.protocol),
            "completed_steps": len(results),
            "failed_steps": len(errors)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Protocol execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить протокол: {str(e)}")
