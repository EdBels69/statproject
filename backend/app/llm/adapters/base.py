from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class AbstractLLMAdapter(ABC):
    """
    Abstract base class for LLM providers.
    """
    
    @abstractmethod
    async def complete(
        self, 
        prompt: str, 
        temperature: float = 0.3,
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """
        Execute a completion request.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system instruction
            
        Returns:
            Generated text content or None if failed
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the API is accessible.
        """
        pass
