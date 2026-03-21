"""
API v2 Endpoints for Advanced Statistical Methods
===================================================
JAMOVI-style endpoints for mixed effects models, clustered correlation, and advanced analyses.
Memory-optimized for MacBook M1 8GB constraints.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
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

from app.core.logging import logger
from app.modules.parsers import get_dataframe, get_dataset_columns, get_dataframe_window
from app.core.pipeline import PipelineManager
from app.core.protocol_engine import ProtocolEngine
from app.stats.mixed_effects import MixedEffectsEngine
from app.stats.clustered_correlation import ClusteredCorrelationEngine
from app.stats.engine import run_analysis, select_test, compute_descriptive_compare
from app.core.study_designer import StudyDesignEngine
from app.core.study_designer import OmniReportDesignEngine, OmniReportPlanner
from app.modules.text_generator import TextGenerator
from app.api.datasets import DATA_DIR
from app.schemas.analysis import (
    OmniReportDesignSuggestRequest,
    OmniReportDesignParseRequest,
    OmniReportDesignSuggestResponse,
    OmniReportProtocolBuildRequest,
    OmniReportProtocolBuildResponse,
    OmniReportDesignSpec,
)

pipeline = PipelineManager(DATA_DIR)

_protocol_engine_v1 = ProtocolEngine(pipeline)

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

router = APIRouter()

# Memory-efficient executor for CPU-intensive operations
analysis_executor = ProcessPoolExecutor(max_workers=2)  # Reduced for 8GB

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
    "pearson",
    "spearman",
    "linear_regression",
    "logistic_regression",
    "roc_analysis",
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


@router.post("/analysis/design", response_model=Dict[str, Any])
async def design_analysis_from_template(request: AnalysisTemplateDesignRequest):
    try:
        metadata: Dict[str, Any] = {}
        scan_path = os.path.join(DATA_DIR, request.dataset_id, "processed", "scan_report.json")
        if os.path.exists(scan_path):
            with open(scan_path, "r") as f:
                report = json.load(f)
                metadata = report.get("columns", {}) or {}

        designer = StudyDesignEngine()
        protocol_v1 = designer.suggest_protocol(
            request.goal,
            request.variables,
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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            analysis_executor,
            _run_mixed_effects_sync,
            df, request.outcome, request.time_col, request.group_col,
            request.subject_col, request.covariates, request.random_slope, request.alpha
        )
        
        # Force garbage collection
        gc.collect()
        
        return convert_numpy_to_native(result)
        
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
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            analysis_executor,
            _run_clustered_correlation_sync,
            df, request.variables, request.method, request.linkage_method,
            request.n_clusters, request.distance_threshold, request.show_p_values, request.alpha
        )
        
        gc.collect()
        
        return convert_numpy_to_native(result)
        
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
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                analysis_executor,
                _run_mixed_effects_sync,
                df, outcome, time_col, group_col, subject_col, covariates, random_slope, request.alpha
            )
            gc.collect()
            return {"status": "completed", "results": convert_numpy_to_native(result)}
        
        elif method_id == "clustered_correlation":
            variables = request.protocol.get("variables", [])
            method = request.protocol.get("method_id", "pearson")
            linkage_method = request.protocol.get("linkage_method", "ward")
            n_clusters = request.protocol.get("n_clusters")
            distance_threshold = request.protocol.get("distance_threshold")
            show_p_values = request.protocol.get("show_p_values", True)
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                analysis_executor,
                _run_clustered_correlation_sync,
                df, variables, method, linkage_method, n_clusters,
                distance_threshold, show_p_values, request.alpha
            )
            gc.collect()
            return {"status": "completed", "results": convert_numpy_to_native(result)}
        
        # Standard methods fallback
        elif method_id and method_id in STANDARD_METHODS:
            target_col = request.protocol.get("target_column")
            group_col = request.protocol.get("group_column")
            
            if target_col and group_col:
                result = await run_analysis_async(df, method_id, target_col, group_col, request.alpha)
                return {"status": "completed", "results": convert_numpy_to_native(result)}
        
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
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        analysis_executor,
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

# --- Protocol Execution Endpoints ---

class ExecuteProtocolRequest(BaseModel):
    """Request model for batch protocol execution."""
    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: List[Dict[str, Any]] = Field(..., description="List of analysis steps")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")
    protocol_name: Optional[str] = Field(None, description="Human-readable protocol name")

@router.post("/analysis/execute", response_model=Dict[str, Any])
async def execute_protocol(request: ExecuteProtocolRequest, background_tasks: BackgroundTasks):
    """
    Execute analysis protocol with batch processing.
    
    Runs multiple statistical tests in sequence with memory management.
    Supports mixed effects, clustered correlation, and all standard methods.
    """
    try:
        df = await load_dataset_async(request.dataset_id)
        
        results = []
        errors = []
        results_map: Dict[str, Any] = {}
        
        for step in request.protocol:
            method_id = step.get("method")
            config = step.get("config", {})
            step_id = step.get("id", f"step_{len(results) + 1}")
            df_step = df

            where = config.get("filter")
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
            
            try:
                # Advanced methods
                if method_id == "mixed_effects":
                    outcome = config.get("outcome")
                    time_col = config.get("time")
                    group_col = config.get("group")
                    subject_col = config.get("subject")
                    covariates = config.get("covariates", [])
                    random_slope = config.get("random_slope", False)
                    
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        analysis_executor,
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
                    method = config.get("method", "pearson")
                    linkage_method = config.get("linkage_method", "ward")
                    n_clusters = config.get("n_clusters")
                    distance_threshold = config.get("distance_threshold")
                    show_p_values = config.get("show_p_values", True)
                    
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(
                        analysis_executor,
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
                
                # Standard methods fallback
                elif method_id in STANDARD_METHODS:
                    outcome = config.get("outcome") or config.get("target")
                    group = config.get("group")
                    predictors = config.get("predictors")
                    covariates = config.get("covariates")
                    post_hoc = config.get("post_hoc")
                    post_hoc_correction = config.get("post_hoc_correction")
                    alternative = config.get("alternative")

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

        protocol_name = str(request.protocol_name or "Протокол").strip() or "Протокол"
        run_dir = pipeline.create_analysis_run(
            request.dataset_id,
            {
                "name": protocol_name,
                "alpha": request.alpha,
                "steps": request.protocol,
            },
        )
        run_id = os.path.basename(run_dir)

        pipeline.save_run_results(
            run_dir,
            {
                "protocol_name": protocol_name,
                "dataset_id": request.dataset_id,
                "results": results_map,
                "status": "completed" if not errors else "partial",
                "errors": errors,
                "total_steps": len(request.protocol),
                "completed_steps": len(results_map),
                "failed_steps": len(errors),
            },
        )

        result_ir = pipeline.build_result_ir(
            {
                "protocol_name": protocol_name,
                "dataset_id": request.dataset_id,
                "results": results_map,
                "status": "completed" if not errors else "partial",
                "errors": errors,
                "total_steps": len(request.protocol),
                "completed_steps": len(results_map),
                "failed_steps": len(errors),
            }
        )
        
        return {
            "run_id": run_id,
            "status": "completed" if not errors else "partial",
            "results": results,
            "result_ir": result_ir,
            "errors": errors,
            "total_steps": len(request.protocol),
            "completed_steps": len(results),
            "failed_steps": len(errors)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Protocol execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось выполнить протокол: {str(e)}")


@router.post("/omnireport/design/suggest", response_model=OmniReportDesignSuggestResponse)
async def omnireport_design_suggest(request: OmniReportDesignSuggestRequest):
    try:
        columns = get_dataset_columns(request.dataset_id, DATA_DIR)
        sample_cols = []
        for c in columns:
            lc = str(c).lower()
            if any(k in lc for k in ["id", "subject", "patient", "group", "arm", "treat", "cohort", "группа", "пациент", "субъект"]):
                sample_cols.append(str(c))
        sample_cols = list(dict.fromkeys(sample_cols))
        sample_df = get_dataframe_window(request.dataset_id, DATA_DIR, sample_cols[:50], 0, 5000) if sample_cols else get_dataframe_window(request.dataset_id, DATA_DIR, [], 0, 200)

        engine = OmniReportDesignEngine()
        out = engine.suggest_design_spec(request.dataset_id, sample_df, columns)
        design_spec = OmniReportDesignSpec(**out.get("design_spec"))
        confidence = float(out.get("confidence") or 0.0)
        issues = out.get("issues") if isinstance(out.get("issues"), list) else []
        return {"design_spec": design_spec, "confidence": confidence, "issues": [str(x) for x in issues if x is not None]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OmniReport design suggest failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось предложить дизайн: {str(e)}")


@router.post("/omnireport/design/parse", response_model=OmniReportDesignSuggestResponse)
async def omnireport_design_parse(request: OmniReportDesignParseRequest):
    try:
        columns = get_dataset_columns(request.dataset_id, DATA_DIR)
        sample_df = get_dataframe_window(request.dataset_id, DATA_DIR, [], 0, 5000)

        engine = OmniReportDesignEngine()
        out = engine.parse_design_spec(request.dataset_id, sample_df, columns, request.text)
        design_spec = OmniReportDesignSpec(**out.get("design_spec"))
        confidence = float(out.get("confidence") or 0.0)
        issues = out.get("issues") if isinstance(out.get("issues"), list) else []
        return {"design_spec": design_spec, "confidence": confidence, "issues": [str(x) for x in issues if x is not None]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OmniReport design parse failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось распознать дизайн: {str(e)}")


@router.post("/omnireport/protocol/build", response_model=OmniReportProtocolBuildResponse)
async def omnireport_protocol_build(request: OmniReportProtocolBuildRequest):
    try:
        planner = OmniReportPlanner()
        protocol = planner.build_protocol(request.dataset_id, request.design_spec.model_dump(), alpha=float(request.alpha))
        return {"protocol": protocol}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OmniReport protocol build failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось собрать протокол OmniReport: {str(e)}")


class OmniReportRunRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1)
    design_spec: Optional[OmniReportDesignSpec] = None
    alpha: float = Field(default=0.05, ge=0.001, le=0.25)


@router.post("/omnireport/run", response_model=Dict[str, Any])
async def omnireport_run(request: OmniReportRunRequest):
    try:
        df = await load_dataset_async(request.dataset_id)

        if request.design_spec is None:
            columns = list(df.columns)
            engine = OmniReportDesignEngine()
            suggest = engine.suggest_design_spec(request.dataset_id, df.iloc[:5000], [str(c) for c in columns])
            design_spec = OmniReportDesignSpec(**suggest.get("design_spec"))
        else:
            design_spec = request.design_spec

        planner = OmniReportPlanner()
        protocol = planner.build_protocol(request.dataset_id, design_spec.model_dump(), alpha=float(request.alpha))

        run_id = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _protocol_engine_v1.execute_protocol(request.dataset_id, df, protocol, alpha=float(request.alpha)),
        )

        return {
            "status": "success",
            "run_id": run_id,
            "dataset_id": request.dataset_id,
            "protocol_name": protocol.get("name"),
            "design_spec": design_spec,
            "links": {
                "results": f"/api/v1/analysis/run/{run_id}?dataset_id={request.dataset_id}",
                "docx": f"/api/v1/analysis/protocol/report/{run_id}/docx?dataset_id={request.dataset_id}",
                "pdf": f"/api/v1/analysis/protocol/report/{run_id}/pdf?dataset_id={request.dataset_id}",
                "artifacts": f"/api/v1/analysis/protocol/artifacts/{run_id}?dataset_id={request.dataset_id}",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OmniReport run failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось запустить OmniReport: {str(e)}")
