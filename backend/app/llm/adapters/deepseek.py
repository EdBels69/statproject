import httpx
from typing import Optional
import logging

from .base import AbstractLLMAdapter

logger = logging.getLogger(__name__)


class DeepSeekAdapter(AbstractLLMAdapter):
    def __init__(self, api_key: str, model: str = "deepseek-chat", api_url: str = "https://api.deepseek.com/chat/completions"):
        self.api_key = api_key
        self.model = model
        self.api_url = api_url

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        if not self.api_key:
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                if response.status_code != 200:
                    return None
                data = response.json()
                msg = (data.get("choices") or [{}])[0].get("message") or {}
                content = str(msg.get("content") or "").strip()
                return content or None
        except Exception as e:
            logger.error(f"DeepSeek API Error: {e}")
            return None

    async def health_check(self) -> bool:
        res = await self.complete("ping", max_tokens=5)
        return res is not None
