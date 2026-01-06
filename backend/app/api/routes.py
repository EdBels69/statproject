from fastapi import APIRouter
from app.api import datasets, analysis, quality

api_router = APIRouter()

api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(quality.router, prefix="/quality", tags=["quality"])

from app.api import protocol, planning
api_router.include_router(protocol.router, prefix="/protocol", tags=["protocol"])
api_router.include_router(planning.router, prefix="/planning", tags=["planning"])

