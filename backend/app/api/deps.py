from typing import Callable, Iterable

from fastapi import HTTPException, Request

from app.core.config import settings


def _mask_key(api_key: str) -> str:
    if len(api_key) <= 6:
        return "***"
    return f"{api_key[:3]}***{api_key[-3:]}"


async def get_current_user(request: Request) -> dict[str, str]:
    if not settings.AUTH_ENABLED:
        return {"role": "system", "name": "anonymous"}
    header_name = settings.AUTH_HEADER
    api_key = request.headers.get(header_name)
    user = settings.get_user_by_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {
        "role": user.get("role", "user"),
        "name": user.get("name", "api_user"),
        "key_id": _mask_key(user.get("key", "")),
    }


def require_roles(roles: Iterable[str]) -> Callable:
    role_set = {r for r in roles if isinstance(r, str) and r}

    async def _dependency(request: Request) -> dict[str, str]:
        user = await get_current_user(request)
        if not settings.AUTH_ENABLED:
            return user
        if not role_set:
            return user
        if user.get("role") not in role_set:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _dependency
