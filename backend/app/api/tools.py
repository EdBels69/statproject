from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
import math
import statsmodels.stats.power as smp
import numpy as np

router = APIRouter()

class PowerAnalysisRequest(BaseModel):
    test_type: Literal["anova", "ttest_ind", "chisquare"] = Field(..., description="Type of statistical test")
    effect_size: float = Field(..., description="Effect size (f for ANOVA, d for t-test, w for chi-square)")
    alpha: float = Field(0.05, description="Significance level")
    power: float = Field(0.8, description="Statistical power")
    groups: Optional[int] = Field(None, description="Number of groups (for ANOVA)")
    n_obs: Optional[int] = Field(None, description="Total sample size (if calculating power)")

class PowerAnalysisResponse(BaseModel):
    n_per_group: Optional[int] = None
    total_n: Optional[int] = None
    actual_power: Optional[float] = None
    effect_size: float
    alpha: float
    groups: Optional[int] = None

@router.post("/power-analysis", response_model=PowerAnalysisResponse)
def calculate_power(request: PowerAnalysisRequest):
    try:
        # ANOVA (F-test)
        if request.test_type == "anova":
            if not request.groups or request.groups < 2:
                raise HTTPException(status_code=400, detail="Number of groups must be >= 2 for ANOVA")
            
            analysis = smp.FTestAnovaPower()
            
            # Solve for sample size (nobs)
            # ratio=1 means equal sample sizes
            # k_groups is number of groups
            
            # solve_power arguments: effect_size, nobs, alpha, power, k_groups
            # We want to find nobs (total sample size? No, statsmodels uses mean sample size per group usually, let's verify)
            # Documentation says: nobs: number of observations per group? Or total?
            # FTestAnovaPower.solve_power(effect_size=None, nobs=None, alpha=None, power=None, k_groups=2)
            # nobs: "sample size" - usually per group in statsmodels, but let's be careful.
            # Actually for FTestAnovaPower, nobs is "mean sample size".
            
            n_per_group = analysis.solve_power(
                effect_size=request.effect_size, 
                nobs=None, 
                alpha=request.alpha, 
                power=request.power, 
                k_groups=request.groups
            )
            
            n_per_group_ceil = math.ceil(n_per_group)
            total_n = n_per_group_ceil * request.groups
            
            # Recalculate actual power with ceil sample size
            actual_power = analysis.solve_power(
                effect_size=request.effect_size,
                nobs=n_per_group_ceil,
                alpha=request.alpha,
                k_groups=request.groups
            )
            
            return {
                "n_per_group": n_per_group_ceil,
                "total_n": total_n,
                "actual_power": round(actual_power, 4),
                "effect_size": request.effect_size,
                "alpha": request.alpha,
                "groups": request.groups
            }

        # T-Test Independent
        elif request.test_type == "ttest_ind":
            analysis = smp.TTestIndPower()
            # ratio=1 for equal sample size
            n_per_group = analysis.solve_power(
                effect_size=request.effect_size,
                nobs1=None,
                alpha=request.alpha,
                power=request.power,
                ratio=1.0
            )
            
            n_per_group_ceil = math.ceil(n_per_group)
            total_n = n_per_group_ceil * 2
            
            actual_power = analysis.solve_power(
                effect_size=request.effect_size,
                nobs1=n_per_group_ceil,
                alpha=request.alpha,
                ratio=1.0
            )
            
            return {
                "n_per_group": n_per_group_ceil,
                "total_n": total_n,
                "actual_power": round(actual_power, 4),
                "effect_size": request.effect_size,
                "alpha": request.alpha,
                "groups": 2
            }
            
        else:
            raise HTTPException(status_code=400, detail="Test type not implemented yet")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")
