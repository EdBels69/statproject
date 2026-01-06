from fastapi import APIRouter, Depends
from app.services.planning_service import PlanningService
from app.schemas.planning import PowerAnalysisRequest, PowerAnalysisResult

router = APIRouter()

def get_service():
    return PlanningService()

@router.post("/calculate", response_model=PowerAnalysisResult)
def calculate_power(req: PowerAnalysisRequest, service: PlanningService = Depends(get_service)):
    return service.calculate_sample_size(req)
