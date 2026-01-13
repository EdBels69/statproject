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

from app.core.logging import logger
from app.modules.parsers import get_dataframe
from app.core.pipeline import PipelineManager
from app.stats.mixed_effects import MixedEffectsEngine
from app.stats.clustered_correlation import ClusteredCorrelationEngine
from app.stats.engine import run_analysis
from app.api.datasets import DATA_DIR

router = APIRouter()

# Memory-efficient executor for CPU-intensive operations
analysis_executor = ProcessPoolExecutor(max_workers=2)  # Reduced for 8GB

# Standard statistical methods for protocol fallback
STANDARD_METHODS = [
    "t_test_independent",
    "t_test_paired",
    "anova_one_way",
    "anova_repeated",
    "correlation_pearson",
    "correlation_spearman",
    "chi_square",
    "regression_linear",
    "regression_logistic"
]

def convert_numpy_to_native(obj: Any) -> Any:
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
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
            raise HTTPException(status_code=400, detail=f"Columns not found: {missing_cols}")
        
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
        raise HTTPException(status_code=500, detail=f"Mixed effects analysis failed: {str(e)}")

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
            raise HTTPException(status_code=400, detail=f"Variables not found: {missing_vars}")
        
        # Limit variables for memory safety
        if len(request.variables) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 variables allowed for clustering")
        
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
        raise HTTPException(status_code=500, detail=f"Clustered correlation failed: {str(e)}")

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
        
        raise HTTPException(status_code=400, detail=f"Method {method_id} not implemented")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Protocol execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Protocol execution failed: {str(e)}")

# --- Helper Functions ---

async def load_dataset_async(dataset_id: str) -> pd.DataFrame:
    """Load dataset asynchronously with memory limits."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,  # Use default executor
        get_dataframe, dataset_id, DATA_DIR
    )

async def run_analysis_async(df: pd.DataFrame, method_id: str, col_a: str, col_b: str, alpha: float) -> Dict[str, Any]:
    """Run analysis asynchronously with memory management."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        analysis_executor,
        run_analysis, df, method_id, col_a, col_b, alpha
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

# --- AI Assistant Endpoints ---

class AISuggestTestsRequest(BaseModel):
    """Request model for AI test suggestions."""
    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: List[Dict[str, Any]] = Field(..., description="Current protocol for context")

@router.post("/ai/suggest-tests", response_model=Dict[str, Any])
async def ai_suggest_tests(request: AISuggestTestsRequest):
    """
    AI-powered test suggestions based on dataset characteristics and current protocol.
    
    Analyzes data types, distributions, and relationships to recommend appropriate
    statistical tests. Non-automatic - requires explicit user activation.
    """
    try:
        df = await load_dataset_async(request.dataset_id)
        
        # Analyze dataset characteristics
        recommendations = []
        
        # Get column types
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Check for time-series structure
        potential_time_cols = [col for col in numeric_cols if 'time' in col.lower() or 'date' in col.lower()]
        potential_group_cols = [col for col in categorical_cols if df[col].nunique() <= 10]
        potential_subject_cols = [col for col in categorical_cols if df[col].nunique() > 10 and df[col].nunique() <= 100]
        
        # Suggest mixed effects if longitudinal structure detected
        if len(potential_time_cols) > 0 and len(potential_group_cols) > 0 and len(potential_subject_cols) > 0:
            recommendations.append({
                test: {
                    id: "mixed_effects",
                    name: "Mixed Effects (LMM)",
                    config: {
                        outcome: numeric_cols[0] if numeric_cols else "Select outcome",
                        time: potential_time_cols[0],
                        group: potential_group_cols[0],
                        subject: potential_subject_cols[0],
                        random_slope: False
                    }
                },
                reason: "Обнаружена структура продольных данных. Mixed Effects Model позволит учесть повторные измерения и индивидуальную вариабельность.",
                confidence: 0.85
            })
        
        # Suggest clustered correlation if multiple numeric variables
        if len(numeric_cols) >= 3:
            recommendations.append({
                test: {
                    id: "clustered_correlation",
                    name: "Clustered Correlation",
                    config: {
                        variables: numeric_cols[:8],  # Top 8 variables
                        method: "pearson",
                        linkage_method: "ward"
                    }
                },
                reason: f"Обнаружено {len(numeric_cols)} числовых переменных. Кластерная корреляция выявит группы связанных переменных.",
                confidence: 0.90
            })
        
        # Suggest group comparison tests
        if len(potential_group_cols) > 0 and len(numeric_cols) > 0:
            recommendations.append({
                test: {
                    id: "mann_whitney",
                    name: "Mann-Whitney U",
                    config: {
                        outcome: numeric_cols[0],
                        group: potential_group_cols[0]
                    }
                },
                reason: "Сравнение групп с непараметрическим тестом подходит для данных с возможными выбросами.",
                confidence: 0.75
            })
        
        # Avoid duplicates with current protocol
        current_methods = {test.get("method") for test in request.protocol}
        recommendations = [
            rec for rec in recommendations 
            if rec.test.id not in current_methods
        ]
        
        return {
            "status": "completed",
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"AI suggestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI suggestion failed: {str(e)}")

# --- Protocol Execution Endpoints ---

class ExecuteProtocolRequest(BaseModel):
    """Request model for batch protocol execution."""
    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: List[Dict[str, Any]] = Field(..., description="List of analysis steps")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")

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
        
        for step in request.protocol:
            method_id = step.get("method")
            config = step.get("config", {})
            step_id = step.get("id", f"step_{len(results) + 1}")
            
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
                        df, outcome, time_col, group_col, subject_col,
                        covariates, random_slope, request.alpha
                    )
                    
                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": convert_numpy_to_native(result)
                    })
                
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
                        df, variables, method, linkage_method, n_clusters,
                        distance_threshold, show_p_values, request.alpha
                    )
                    
                    results.append({
                        "step_id": step_id,
                        "method": method_id,
                        "status": "completed",
                        "results": convert_numpy_to_native(result)
                    })
                
                # Standard methods fallback
                elif method_id in STANDARD_METHODS:
                    outcome = config.get("outcome")
                    group = config.get("group")
                    
                    if outcome and group:
                        result = await run_analysis_async(df, method_id, outcome, group, request.alpha)
                        
                        results.append({
                            "step_id": step_id,
                            "method": method_id,
                            "status": "completed",
                            "results": convert_numpy_to_native(result)
                        })
                    else:
                        raise ValueError(f"Missing required config for {method_id}")
                
                else:
                    raise ValueError(f"Method {method_id} not implemented")
                
                # Force garbage collection after each step
                gc.collect()
                
            except Exception as e:
                logger.error(f"Step {step_id} failed: {e}", exc_info=True)
                errors.append({
                    "step_id": step_id,
                    "method": method_id,
                    "error": str(e)
                })
        
        return {
            "status": "completed" if not errors else "partial",
            "results": results,
            "errors": errors,
            "total_steps": len(request.protocol),
            "completed_steps": len(results),
            "failed_steps": len(errors)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Protocol execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Protocol execution failed: {str(e)}")