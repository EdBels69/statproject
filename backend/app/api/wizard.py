from fastapi import APIRouter, HTTPException
from app.modules.expert_system import WizardRequest, WizardRecommendation, recommend_method

router = APIRouter()

@router.post("/recommend", response_model=WizardRecommendation)
async def get_wizard_recommendation(request: WizardRequest):
    """
    Returns a statistical method recommendation based on study design parameters.
    """
    try:
        return recommend_method(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
