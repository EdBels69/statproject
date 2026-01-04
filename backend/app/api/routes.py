from fastapi import APIRouter
from app.api import datasets, analysis, quality, jobs

api_router = APIRouter()

api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(analysis.router, prefix="/analyze", tags=["analysis"])
api_router.include_router(quality.router, prefix="/quality", tags=["quality"])
api_router.include_router(jobs.router, tags=["jobs"])
from app.api import wizard
api_router.include_router(wizard.router, prefix="/wizard", tags=["wizard"])
