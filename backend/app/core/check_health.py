
import asyncio
import logging
from app.core.config import settings
from app.llm import _resolve_llm_target, _normalize_chat_completions_url
import httpx

logger = logging.getLogger(__name__)

async def check_llm_availability():
    """
    Check if configured LLM models are accessible.
    Logs warnings if models are not found or API is unreachable.
    """
    models = {
        "PLANNER": settings.COPILOT_MODEL_PLANNER,
        "CODER": settings.COPILOT_MODEL_CODER,
        "INTERPRETER": settings.COPILOT_MODEL_INTERPRETER
    }
    
    logger.info("🏥 checking LLM model availability...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for role, model in models.items():
            try:
                url, api_key = _resolve_llm_target(model)
                url = _normalize_chat_completions_url(url)
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # Minimal payload to check model existence
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 1
                }
                
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    logger.info(f"✅ {role}: {model} is OK")
                elif response.status_code in (400, 404):
                    logger.error(f"❌ {role}: {model} NOT FOUND (Status {response.status_code}). Check config!")
                    logger.error(f"Response: {response.text}")
                else:
                    logger.warning(f"⚠️ {role}: {model} returned status {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ {role}: Connection failed for {model}: {e}")
