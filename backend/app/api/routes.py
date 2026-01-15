from fastapi import APIRouter
from app.api import datasets, analysis, quality
from app.api.v2 import router as v2_router
from app.api import knowledge

api_router = APIRouter()

api_router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(quality.router, prefix="/quality", tags=["quality"])
api_router.include_router(v2_router, prefix="/v2", tags=["v2"])
api_router.include_router(knowledge.router, prefix="/v2", tags=["knowledge"])

