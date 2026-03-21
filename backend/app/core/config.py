import os
from typing import Dict, Optional


def _load_dotenv(env_path: str) -> None:
    try:
        if not os.path.exists(env_path):
            return

        with open(env_path, "r") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if not key:
                    continue
                if key in os.environ:
                    continue
                os.environ[key] = value
    except Exception:
        return


_load_dotenv(os.path.join(os.getcwd(), ".env"))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    items = [p.strip() for p in raw.split(",")]
    return [p for p in items if p]


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        return default


class Settings:
    def __init__(self):
        self.PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Stat Analyzer")
        self.API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")

        self.BACKEND_CORS_ORIGINS: list[str] = _env_list(
            "BACKEND_CORS_ORIGINS",
            [
                "http://localhost:5173",
                "http://localhost:5174",
                "http://localhost:3000",
            ],
        )

        self.GLM_ENABLED: bool = _env_bool("GLM_ENABLED", True)
        self.GLM_API_KEY: Optional[str] = os.getenv("GLM_API_KEY")
        self.GLM_API_URL: str = os.getenv("GLM_API_URL", "https://api.z.ai/api/coding/paas/v4")
        self.GLM_MODEL: str = os.getenv("GLM_MODEL", "glm-4.7")

        self.OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.OPENROUTER_API_URL: str = os.getenv(
            "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
        )

        self.AUTH_ENABLED: bool = _env_bool("AUTH_ENABLED", False)
        self.AUTH_HEADER: str = os.getenv("AUTH_HEADER", "X-API-Key")
        self.API_KEYS_RAW: str = os.getenv("API_KEYS", "")
        self.AUDIT_LOG_PATH: str = os.getenv("AUDIT_LOG_PATH", "workspace/audit.log")

        self.RATE_LIMIT_ENABLED: bool = _env_bool("RATE_LIMIT_ENABLED", True)
        self.RATE_LIMIT_REQUESTS: int = _env_int("RATE_LIMIT_REQUESTS", 300)
        self.RATE_LIMIT_WINDOW_SEC: int = _env_int("RATE_LIMIT_WINDOW_SEC", 60)

        self.API_KEYS = self._parse_api_keys(self.API_KEYS_RAW)

    def _parse_api_keys(self, raw: str) -> Dict[str, Dict[str, str]]:
        keys: Dict[str, Dict[str, str]] = {}
        if not raw:
            return keys
        for entry in raw.split(","):
            item = entry.strip()
            if not item:
                continue
            parts = [p.strip() for p in item.split(":") if p.strip()]
            if len(parts) < 2:
                continue
            key = parts[0]
            role = parts[1] if len(parts) > 1 else "user"
            name = parts[2] if len(parts) > 2 else "api_user"
            keys[key] = {"role": role, "name": name}
        return keys

    def get_user_by_key(self, api_key: Optional[str] = None) -> Optional[Dict[str, str]]:
        if not api_key:
            return None
        user = self.API_KEYS.get(api_key)
        if not user:
            return None
        return {"key": api_key, **user}


settings = Settings()
