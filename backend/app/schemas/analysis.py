from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal

class AnalysisRequest(BaseModel):
    dataset_id: str
    target_column: str  # e.g., "Disease Status" (Group) or "BMI" (Numeric)
    features: List[str]  # e.g., ["Age", "Glucose"]
    
    # Optional overrides
    method_override: Optional[str] = None
    is_paired: bool = False

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
    mean: Optional[float] = None
    median: Optional[float] = None
    sd: Optional[float] = None
    shapiro_w: Optional[float] = None
    shapiro_p: Optional[float] = None
    is_normal: bool = False

class BatchAnalysisRequest(BaseModel):
    dataset_id: str
    target_columns: List[str]  # e.g., ["BMI", "Age"]
    group_column: str          # e.g., "Treatment"
    options: Optional[Dict[str, Any]] = None # e.g. {"conf_level": 0.95, "correction": "bonferroni"}

class BatchAnalysisResponse(BaseModel):
    descriptives: List[DescriptiveStat]
    results: Dict[str, AnalysisResult] # Keyed by variable name

class ProtocolRequest(BaseModel):
    dataset_id: str
    protocol: Dict[str, Any]

class DesignRequest(BaseModel):
    dataset_id: str
    goal: str # 'compare_groups', 'relationship', etc.
    variables: Dict[str, Any] # {'target': 'Hb', 'group': 'Treat'}

class PlotUpdateParams(BaseModel):
    title: str
    xlabel: str
    ylabel: str
    theme: str
    color: str

class SelectiveExportRequest(BaseModel):
    variables: List[str]
    show_mean: bool = True
    show_median: bool = False
    show_quartiles: bool = False

class RiskAnalysisRequest(BaseModel):
    dataset_id: str
    target_column: str          # Outcome (e.g. "Disease")
    group_column: str           # Exposure (e.g. "Smoker")
    target_positive_val: Optional[str] = None # Value considered "Positive" (e.g. "Yes")
    group_exposure_val: Optional[str] = None  # Value considered "Exposed" (e.g. "Yes")

class RiskMetric(BaseModel):
    name: str # "Relative Risk", "Odds Ratio", "Risk Difference"
    value: float
    ci_lower: float
    ci_upper: float
    p_value: Optional[float] = None
    significant: bool = False

class RiskAnalysisResponse(BaseModel):
    metrics: List[RiskMetric]
    contingency_table: Dict[str, Dict[str, int]] # {"Exp+": {"Out+": 10, "Out-": 5}, ...}
    conclusion: str

class ReportPreviewRequest(BaseModel):
    dataset_name: str
    results: Dict[str, Any]
    export_settings: Optional[Dict[str, Any]] = None

class CorrelationMatrixRequest(BaseModel):
    dataset_id: str
    features: List[str]
    method: str = "pearson" # pearson, spearman, kendall
    cluster_variables: bool = False

class CorrelationMatrixResponse(BaseModel):
    method: str
    corr_matrix: Dict[str, Dict[str, float]] # Nested
    p_values: Dict[str, Dict[str, float]]
    plot_image: Optional[str] # base64
    variables: List[str] # Reordered if clustered
    clustered: bool
    n_obs: int
