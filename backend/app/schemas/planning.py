from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any

class PowerAnalysisRequest(BaseModel):
    test_type: Literal["t_test_ind", "t_test_paired", "anova", "chi_square", "correlation"]
    alpha: float = Field(0.05, description="Significance level (Type I error)")
    power: float = Field(0.80, description="Statistical Power (1 - Type II error)")
    effect_size: float = Field(..., description="Cohen's d, f, or w/phi depending on test")
    n_groups: Optional[int] = Field(2, description="Number of groups (for ANOVA)")
    ratio: Optional[float] = Field(1.0, description="Ratio of sample sizes (n2/n1)")

class PowerAnalysisResult(BaseModel):
    test_type: str
    required_n: int     # Total sample size
    group_n: int        # Sample size per group
    parameters: Dict[str, Any]
    description: str
