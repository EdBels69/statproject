import os
from typing import Optional


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
        self.GLM_API_URL: str = os.getenv("GLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        self.GLM_MODEL: str = os.getenv("GLM_MODEL", "xiaomi/mimo-v2-flash:free")

        self.OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.OPENROUTER_API_URL: str = os.getenv(
            "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
        )


settings = Settings()
