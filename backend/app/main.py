import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import api_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.core.check_health import check_llm_availability

    task = asyncio.create_task(check_llm_availability())
    try:
        yield
    finally:
        if not task.done():
            task.cancel()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

# NEW: Copilot - Chat-first statistical analysis
from app.copilot.router import router as copilot_router
app.include_router(copilot_router, prefix="/api/v2/copilot", tags=["Copilot"])

@app.get("/")
async def root():
    return {"message": "Welcome to Stat Analyzer API"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
