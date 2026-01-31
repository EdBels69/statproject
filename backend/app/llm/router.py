from typing import Dict, Optional, List

from app.llm.adapters.base import AbstractLLMAdapter


class LLMRouter:
    def __init__(self, adapters: Dict[str, AbstractLLMAdapter]):
        self.adapters = adapters

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
        provider_order: Optional[List[str]] = None,
    ) -> Optional[str]:
        order = provider_order or []
        for provider in order:
            adapter = self.adapters.get(provider)
            if not adapter:
                continue
            content = await adapter.complete(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
            )
            if content:
                return content
        return None
