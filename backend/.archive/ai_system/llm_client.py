"""
LLM Client Wrapper for AI System modules.

Provides a simple class interface for LLM calls using the app.llm module.
"""
import os
from typing import Optional
from app.llm import _chat_completion


class MyLLMClient:
    """
    Simple LLM client wrapper for async calls.
    """
    
    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("LLM_MODEL_ID", "glm-4-flash")
    
    async def ask(self, prompt: str, temperature: float = 0.3, max_tokens: int = 2000) -> Optional[str]:
        """
        Send a prompt to the LLM and get a response.
        
        Args:
            prompt: The prompt text
            temperature: Sampling temperature (0-1)
            max_tokens: Max tokens to generate
            
        Returns:
            Response text or None if failed
        """
        return await _chat_completion(
            model=self.model,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_s=60.0
        )
    
    async def ask_json(self, prompt: str) -> Optional[str]:
        """
        Ask for JSON response (lower temperature for more consistent output).
        """
        return await self.ask(prompt, temperature=0.1, max_tokens=4000)
