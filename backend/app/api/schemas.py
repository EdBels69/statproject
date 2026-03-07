"""Pydantic models for V2 API."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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
    method: Literal["pearson", "spearman", "kendall"] = Field("pearson", description="Correlation method")
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


class ExecuteProtocolRequest(BaseModel):
    """Request model for batch protocol execution."""

    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: List[Dict[str, Any]] = Field(..., description="List of analysis steps")
    alpha: float = Field(0.05, ge=0.01, le=0.10, description="Significance level")
    protocol_name: Optional[str] = Field(None, description="Human-readable protocol name")
    globals: Optional[Dict[str, Any]] = Field(None, description="Global analysis settings")
    protocol_plan: Optional[Dict[str, Any]] = Field(None, description="Planning artifacts from /analysis/plan")
    column_selection_report: Optional[Dict[str, Any]] = Field(
        None,
        description="Column selection report passthrough for reporting",
    )
