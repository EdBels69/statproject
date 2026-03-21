import time
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api.routes import api_router
from app.core.logging import logger, log_audit_event


def _mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 6:
        return "***"
    return f"{api_key[:3]}***{api_key[-3:]}"


class RateLimiter:
    def __init__(self, max_requests: int, window_sec: int):
        self.max_requests = max(1, int(max_requests))
        self.window_sec = max(1, int(window_sec))
        self._lock = Lock()
        self._buckets: dict[str, dict[str, float | int]] = {}

    def allow(self, key: str) -> tuple[bool, int, int]:
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket or now - float(bucket["start"]) >= self.window_sec:
                bucket = {"start": now, "count": 0}
                self._buckets[key] = bucket
            count = int(bucket["count"])
            if count >= self.max_requests:
                reset_in = int(self.window_sec - (now - float(bucket["start"])))
                return False, 0, max(reset_in, 0)
            bucket["count"] = count + 1
            remaining = max(self.max_requests - int(bucket["count"]), 0)
            reset_in = int(self.window_sec - (now - float(bucket["start"])))
            return True, remaining, max(reset_in, 0)


rate_limiter = RateLimiter(settings.RATE_LIMIT_REQUESTS, settings.RATE_LIMIT_WINDOW_SEC)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)


@app.middleware("http")
async def audit_and_rate_limit(request: Request, call_next):
    start = time.time()
    api_key = request.headers.get(settings.AUTH_HEADER)
    user = settings.get_user_by_key(api_key) if settings.AUTH_ENABLED else None
    identifier = f"key:{api_key}" if api_key else f"ip:{request.client.host if request.client else 'unknown'}"

    if settings.RATE_LIMIT_ENABLED:
        allowed, remaining, reset_in = rate_limiter.allow(identifier)
        if not allowed:
            log_audit_event(
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "method": request.method,
                    "path": request.url.path,
                    "status": 429,
                    "latency_ms": int((time.time() - start) * 1000),
                    "client_ip": request.client.host if request.client else None,
                    "user_role": user.get("role") if user else None,
                    "user_name": user.get("name") if user else None,
                    "key_id": _mask_key(api_key or ""),
                    "rate_limit_remaining": remaining,
                    "rate_limit_reset_sec": reset_in,
                }
            )
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
        log_audit_event(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "latency_ms": int((time.time() - start) * 1000),
                "client_ip": request.client.host if request.client else None,
                "user_role": user.get("role") if user else None,
                "user_name": user.get("name") if user else None,
                "key_id": _mask_key(api_key or ""),
            }
        )
        raise

    log_audit_event(
        {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": int((time.time() - start) * 1000),
            "client_ip": request.client.host if request.client else None,
            "user_role": user.get("role") if user else None,
            "user_name": user.get("name") if user else None,
            "key_id": _mask_key(api_key or ""),
        }
    )
    return response

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

@app.get("/")
async def root():
    return {"message": "Welcome to Stat Analyzer API"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
