from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from scipy import stats
from typing import Optional, Any, Dict
import inspect

# 1. IMPORT specific modules
from app.modules.expert_system import WizardRequest, WizardRecommendation, recommend_method

router = APIRouter()

# 3. Update ApplyRequest to use the imported WizardRecommendation
class ApplyRequest(BaseModel):
    recommendation: WizardRecommendation
    alpha: Optional[float] = 0.05

class ApplyResponse(BaseModel):
    statistic: float
    p_value: float
    is_significant: bool

# 2. RESTORE the /recommend endpoint
@router.post("/recommend", response_model=WizardRecommendation)
async def recommend(request: WizardRequest):
    """
    Generates a wizard recommendation based on the provided request data.
    """
    try:
        if inspect.iscoroutinefunction(recommend_method):
            return await recommend_method(request)
        else:
            return recommend_method(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. KEEP apply_analysis (updated logic)
# 4. KEEP the scipy.stats logic
@router.post("/apply_analysis", response_model=ApplyResponse)
async def apply_analysis(payload: ApplyRequest):
    """
    Applies statistical analysis to the wizard recommendation.
    """
    def extract_score(rec: Any) -> float:
        """Helper to extract a numeric score from various object types."""
        try:
            # Handle Pydantic models (V1 and V2) and standard objects/dicts
            if hasattr(rec, 'model_dump'):
                data: Dict[str, Any] = rec.model_dump()
            elif hasattr(rec, 'dict'):
                data: Dict[str, Any] = rec.dict()
            elif isinstance(rec, dict):
                data = rec
            else:
                data = rec.__dict__

            # Try specific fields likely to hold the metric
            for key in ['confidence', 'score', 'value']:
                if key in data and isinstance(data[key], (int, float)):
                    return float(data[key])
            
            # Fallback: Scan for any float value in the data
            for val in data.values():
                if isinstance(val, (int, float)):
                    return float(val)
            
            return 0.0
        except Exception:
            return 0.0

    try:
        score = extract_score(payload.recommendation)
        
        # 4. Scipy.stats logic:
        population_mean = 0.5
        std_dev = 0.15
        
        # Calculate Z-score
        z_score = (score - population_mean) / std_dev
        
        # Calculate p-value (two-tailed test)
        p_value = stats.norm.sf(abs(z_score)) * 2
        
        # Determine significance based on the provided alpha
        is_significant = p_value < payload.alpha

        return ApplyResponse(
            statistic=z_score,
            p_value=p_value,
            is_significant=is_significant
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")