import httpx
from typing import Optional
import logging

from .base import AbstractLLMAdapter

logger = logging.getLogger(__name__)


class GeminiAdapter(AbstractLLMAdapter):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", api_url: str = "https://generativelanguage.googleapis.com/v1beta/models"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url.rstrip("/")

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.api_key:
            return None

        url = f"{self.api_url}/{self.model}:generateContent"
        params = {"key": self.api_key}

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, json=payload)
                if response.status_code != 200:
                    return None
                data = response.json()
                candidates = data.get("candidates") or []
                if not candidates:
                    return None
                parts = (candidates[0].get("content") or {}).get("parts") or []
                if not parts:
                    return None
                text = str(parts[0].get("text") or "").strip()
                return text or None
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return None

    async def health_check(self) -> bool:
        res = await self.complete("ping", max_tokens=5)
        return res is not None
