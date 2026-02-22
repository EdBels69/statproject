import httpx
from typing import Optional
import logging
import json
from .base import AbstractLLMAdapter

logger = logging.getLogger(__name__)

class GLMAdapter(AbstractLLMAdapter):
    """
    Adapter for ZhipuAI (GLM-4) API.
    """
    
    def __init__(self, api_key: str, model: str = "glm-4-plus"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        
    async def complete(
        self, 
        prompt: str, 
        temperature: float = 0.3,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        if not self.api_key:
            logger.error("GLM API key is missing")
            return None
            
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"GLM API Error: {response.text}")
                    return None
                    
                data = response.json()
                return data["choices"][0]["message"]["content"]
                
        except Exception as e:
            logger.error(f"Failed to call GLM API: {str(e)}")
            return None

    async def health_check(self) -> bool:
        # Simple generation test
        res = await self.complete("Test", max_tokens=5)
        return res is not None
