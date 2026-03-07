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


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(raw.strip())
    except Exception:
        return int(default)


class Settings:
    def __init__(self):
        self.PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Stat Analyzer")
        self.API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
        self.CLINIMETRIA_REQUIRE_DESIGN_REVIEW: bool = _env_bool("CLINIMETRIA_REQUIRE_DESIGN_REVIEW", True)
        self.CLINIMETRIA_REPORT_HARD_GATE_DESIGN: bool = _env_bool("CLINIMETRIA_REPORT_HARD_GATE_DESIGN", True)
        self.CLINIMETRIA_REPORT_HARD_GATE_METHODS: bool = _env_bool("CLINIMETRIA_REPORT_HARD_GATE_METHODS", True)
        self.CLINIMETRIA_REPORT_HARD_GATE_VERIFICATION: bool = _env_bool(
            "CLINIMETRIA_REPORT_HARD_GATE_VERIFICATION", False
        )
        self.CLINIMETRIA_REPORT_HARD_GATE_PROVENANCE: bool = _env_bool(
            "CLINIMETRIA_REPORT_HARD_GATE_PROVENANCE", False
        )
        self.CLINIMETRIA_AGENT_ORCHESTRATOR_ENABLED: bool = _env_bool(
            "CLINIMETRIA_AGENT_ORCHESTRATOR_ENABLED",
            False,
        )
        self.CLINIMETRIA_AGENT_ORCHESTRATOR_MAX_ROUNDS: int = max(
            1,
            min(50, _env_int("CLINIMETRIA_AGENT_ORCHESTRATOR_MAX_ROUNDS", 10)),
        )
        telemetry_path = os.getenv("CLINIMETRIA_LEGACY_TELEMETRY_PATH", "").strip()
        self.CLINIMETRIA_LEGACY_TELEMETRY_PATH: Optional[str] = telemetry_path or None
        telemetry_token = os.getenv("CLINIMETRIA_TELEMETRY_TOKEN", "").strip()
        self.CLINIMETRIA_TELEMETRY_TOKEN: Optional[str] = telemetry_token or None

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
        self.GLM_MODEL: str = os.getenv("GLM_MODEL", "google/gemini-2.5-flash")

        # Copilot hybrid model routing
        self.COPILOT_MODEL_PLANNER: str = os.getenv("COPILOT_MODEL_PLANNER", "google/gemini-2.5-flash")
        self.COPILOT_MODEL_CODER: str = os.getenv("COPILOT_MODEL_CODER", "deepseek/deepseek-chat")
        self.COPILOT_MODEL_INTERPRETER: str = os.getenv("COPILOT_MODEL_INTERPRETER", "google/gemini-2.5-flash")
        self.COPILOT_MODEL_FALLBACK: str = os.getenv("COPILOT_MODEL_FALLBACK", self.COPILOT_MODEL_INTERPRETER)

        self.OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
        self.OPENROUTER_API_URL: str = os.getenv(
            "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
        )

        self.ZAI_API_KEY: Optional[str] = os.getenv("ZAI_API_KEY")
        self.ZAI_API_URL: str = os.getenv("ZAI_API_URL", "https://api.z.ai/api/coding/paas/v4")
        self.CLINIMETRIA_ZAI_DIRECT: bool = _env_bool("CLINIMETRIA_ZAI_DIRECT", False)
        self.CLINIMETRIA_LLM_FAILOVER_ENABLED: bool = _env_bool("CLINIMETRIA_LLM_FAILOVER_ENABLED", True)
        self.CLINIMETRIA_MODEL_API_FALLBACK: str = os.getenv(
            "CLINIMETRIA_MODEL_API_FALLBACK",
            "google/gemini-2.5-flash",
        )


settings = Settings()
