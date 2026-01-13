from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Stat Analyzer"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:5173", 
        "http://localhost:5174", 
        "http://localhost:3000"
    ]

    # GLM API (Optional)
    GLM_ENABLED: bool = True
    GLM_API_KEY: Optional[str] = None
    GLM_API_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    GLM_MODEL: str = "xiaomi/mimo-v2-flash:free"

    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env"
    )

settings = Settings()
