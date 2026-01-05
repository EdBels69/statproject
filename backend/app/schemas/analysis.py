from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Literal


class IODescriptor(BaseModel):
    name: str
    kind: Literal[
        "target",
        "group",
        "feature",
        "duration",
        "event",
        "predictor",
        "covariate",
        "axis",
    ]
    dtype: Literal[
        "numeric",
        "categorical",
        "binary",
        "datetime",
        "any",
        "numeric_or_categorical",
    ]
    required: bool = True
    multiple: bool = False
    description: Optional[str] = None

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
    type: Literal["parametric", "non-parametric", "correlation", "categorical", "survival"]
    min_groups: int = 1
    max_groups: int = 100
    status: Literal["ready", "experimental", "disabled"] = "ready"
    inputs: List[IODescriptor] = Field(default_factory=list)

class AnalysisResult(BaseModel):
    method: StatMethod
    p_value: float
    effect_size: Optional[float] = None
    effect_size_name: Optional[str] = None  # Cohen's d, r, etc.
    stat_value: float
    significant: bool
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
    mean: float
    median: float
    sd: float
    shapiro_w: Optional[float] = None
    shapiro_p: Optional[float] = None
    is_normal: bool

class BatchAnalysisRequest(BaseModel):
    dataset_id: str
    target_columns: List[str]  # e.g., ["BMI", "Age"]
    group_column: str          # e.g., "Treatment"

class BatchAnalysisResponse(BaseModel):
    descriptives: List[DescriptiveStat]
    results: Dict[str, AnalysisResult] # Keyed by variable name
