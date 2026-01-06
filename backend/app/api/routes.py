from fastapi import APIRouter
from app.api import datasets, analysis, quality

api_router = APIRouter()

api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(quality.router, prefix="/quality", tags=["quality"])

