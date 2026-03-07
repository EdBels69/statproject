from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from scipy import stats

router = APIRouter()


class SorcererRequest(BaseModel):
    goal: Optional[str] = None
    structure: Optional[str] = None
    data_type: Optional[str] = None
    groups: Optional[str] = None
    normal_distribution: Optional[bool] = None


class SorcererRecommendation(BaseModel):
    method_id: str
    name: str
    description: str
    assumptions: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None


class ApplyRequest(BaseModel):
    recommendation: SorcererRecommendation
    alpha: float = 0.05


class ApplyResponse(BaseModel):
    statistic: float
    p_value: float
    is_significant: bool


def _extract_score(rec: Any) -> float:
    try:
        if hasattr(rec, "model_dump"):
            data: Dict[str, Any] = rec.model_dump()
        elif hasattr(rec, "dict"):
            data = rec.dict()
        elif isinstance(rec, dict):
            data = rec
        else:
            data = rec.__dict__
        for key in ["confidence", "score", "value"]:
            val = data.get(key)
            if isinstance(val, (int, float)):
                return float(val)
        for val in data.values():
            if isinstance(val, (int, float)):
                return float(val)
    except Exception:
        return 0.0
    return 0.0


@router.post("/recommend", response_model=SorcererRecommendation)
async def recommend(payload: SorcererRequest) -> SorcererRecommendation:
    try:
        method_id = "t_test_ind" if str(payload.groups or "").strip() == "2" else "anova"
        name = "t-test (independent)" if method_id == "t_test_ind" else "ANOVA"
        description = (
            "Auto-selected method for two independent groups."
            if method_id == "t_test_ind"
            else "Auto-selected method for more than two groups."
        )
        return SorcererRecommendation(
            method_id=method_id,
            name=name,
            description=description,
            assumptions=["independent_observations"],
            confidence=0.5,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/apply_analysis", response_model=ApplyResponse)
async def apply_analysis(payload: ApplyRequest) -> ApplyResponse:
    try:
        score = _extract_score(payload.recommendation)
        z_score = (score - 0.5) / 0.15
        p_value = float(stats.norm.sf(abs(z_score)) * 2)
        return ApplyResponse(
            statistic=float(z_score),
            p_value=p_value,
            is_significant=bool(p_value < payload.alpha),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
