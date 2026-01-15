from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Any, Dict, Literal

class ProtocolRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, description="Unique identifier for the dataset")
    protocol: Dict[str, Any] = Field(..., description="Analysis protocol configuration")
    alpha: float = Field(default=0.05, ge=0.001, le=0.25, description="Significance level (alpha) for p-value threshold")

    @field_validator("protocol")
    @classmethod
    def validate_protocol_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("protocol must contain at least one analysis step")
        return v

class DesignRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, description="Unique identifier for the dataset")
    goal: str = Field(..., min_length=1, description="Analysis goal: 'compare_groups', 'relationship', etc.")
    template_id: Optional[str] = Field(None, description="Optional template identifier")
    variables: Dict[str, Any] = Field(..., description="Variable mapping: {'target': 'Hb', 'group': 'Treat'}")
    
    @field_validator("goal")
    @classmethod
    def validate_goal(cls, v):
        valid_goals = {"compare_groups", "relationship", "association", "predict"}
        if v not in valid_goals:
            raise ValueError(f"goal must be one of: {', '.join(valid_goals)}")
        return v
    
    @field_validator("variables")
    @classmethod
    def validate_variables_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("variables must contain at least one variable mapping")
        return v

class AnalysisRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, description="Unique identifier for the dataset")
    target_column: str = Field(..., min_length=1, description="Target column for analysis")
    features: List[str] = Field(..., min_length=1, description="List of feature columns (at least one required)")
    
    # Optional overrides
    method_override: Optional[str] = Field(None, description="Override auto-selected statistical method")
    is_paired: bool = Field(default=False, description="Whether data is paired")
    
    @field_validator("features")
    @classmethod
    def validate_features_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("features must contain at least one column")
        return v

class StatMethod(BaseModel):
    id: str
    name: str
    description: str
    type: Literal["parametric", "non-parametric", "correlation", "categorical", "survival", "diagnostic"]
    min_groups: int = 1
    max_groups: int = 100

class AnalysisResult(BaseModel):
    method: StatMethod
    p_value: Optional[float] = None
    effect_size: Optional[float] = None
    effect_size_name: Optional[str] = None  # Cohen's d, r, etc.
    effect_size_ci_lower: Optional[float] = None
    effect_size_ci_upper: Optional[float] = None
    power: Optional[float] = None
    bf10: Optional[float] = None
    stat_value: Optional[float] = None
    significant: bool = False
    
    # FDR / Correction
    adjusted_p_value: Optional[float] = None
    significant_adj: Optional[bool] = None
    
    warnings: List[str] = []
    
    # Regression specific
    r_squared: Optional[float] = None
    coefficients: Optional[List[Dict[str, Any]]] = None
    
    groups: Optional[List[str]] = None
    
    # Visualization Data
    plot_data: Optional[List[Dict[str, Any]]] = None  # [{"group": "A", "value": 10}, ...]
    plot_stats: Optional[Dict[str, Dict[str, float]]] = None # {"GroupA": {"mean": 10, ...}}
    
    # Human readable conclusion
    conclusion: str

class DescriptiveStat(BaseModel):
    variable: str
    group: str
    count: int
    missing: Optional[int] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    mode: Optional[float] = None
    sd: Optional[float] = None
    se: Optional[float] = None
    variance: Optional[float] = None
    range: Optional[float] = None
    iqr: Optional[float] = None
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    ci_95_low: Optional[float] = None
    ci_95_high: Optional[float] = None
    shapiro_w: Optional[float] = None
    shapiro_p: Optional[float] = None
    is_normal: bool = False

class BatchAnalysisRequest(BaseModel):
    dataset_id: str = Field(..., min_length=1, description="Unique identifier for the dataset")
    target_columns: List[str] = Field(..., min_length=1, description="List of target columns (at least one required)")
    group_column: str = Field(..., min_length=1, description="Group column for comparison")
    alpha: float = Field(default=0.05, ge=0.001, le=0.25, description="Significance level (alpha) for p-value threshold")

    @field_validator("target_columns")
    @classmethod
    def validate_target_columns_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("target_columns must contain at least one column")
        return v

class BatchAnalysisResponse(BaseModel):
    descriptives: List[DescriptiveStat]
    results: Dict[str, AnalysisResult] # Keyed by variable name


# ============================================================
# API v2 Schemas: Advanced Statistical Methods
# ============================================================

class ClusteredCorrelationRequest(BaseModel):
    """Request schema for clustered correlation analysis (jYS-style)."""
    dataset_id: str = Field(..., min_length=1, description="Unique identifier for the dataset")
    variables: List[str] = Field(..., min_length=2, description="Variables to include in correlation matrix (at least 2)")
    method: Literal["pearson", "spearman"] = Field(default="pearson", description="Correlation method")
    linkage_method: Literal["ward", "complete", "average", "single"] = Field(default="ward", description="Hierarchical clustering linkage")
    n_clusters: Optional[int] = Field(None, ge=2, description="Number of clusters (auto-detect if None)")
    distance_threshold: Optional[float] = Field(None, gt=0, description="Distance threshold for clustering (alternative to n_clusters)")
    show_p_values: bool = Field(default=True, description="Calculate p-values for correlations")
    alpha: float = Field(default=0.05, ge=0.001, le=0.25, description="Significance level for p-values")


class ClusteredCorrelationResult(BaseModel):
    """Response schema for clustered correlation analysis."""
    method: str
    linkage: str
    n_observations: int
    n_variables: int
    n_clusters: int
    
    correlation_matrix: Dict[str, Any]
    original_order: List[str]
    cluster_assignments: Dict[str, int]  # Variable name -> Cluster ID
    
    clusters: List[Dict[str, Any]]
    submatrices: List[Dict[str, Any]]
    dendrogram: Dict[str, Any]
    heatmap_data: List[Dict[str, Any]]


class MixedEffectsRequest(BaseModel):
    """Request schema for Linear Mixed Model analysis."""
    dataset_id: str = Field(..., min_length=1, description="Unique identifier for the dataset")
    outcome: str = Field(..., min_length=1, description="Dependent variable column name")
    time_col: str = Field(..., min_length=1, description="Time/Visit variable column name")
    group_col: str = Field(..., min_length=1, description="Treatment group column name")
    subject_col: str = Field(..., min_length=1, description="Subject ID column name")
    covariates: Optional[List[str]] = Field(None, description="Additional covariates to include")
    random_slope: bool = Field(default=False, description="Include random slope for time")
    alpha: float = Field(default=0.05, ge=0.001, le=0.25, description="Significance level")


class MixedEffectsResult(BaseModel):
    """Response schema for Linear Mixed Model analysis."""
    method: str
    outcome: str
    formula: str
    n_observations: int
    n_subjects: int
    
    main_effect_time: Dict[str, Any]
    main_effect_group: Dict[str, Any]
    interaction: Dict[str, Any]
    
    fit: Dict[str, Any]
    coefficients: List[Dict[str, Any]]
