---
description: Как добавить поддержку нового LLM провайдера
---

# Добавление LLM провайдера

## Когда использовать

- Нужно добавить новую модель (DeepSeek, OpenAI, Anthropic, etc.)
- Нужно изменить формат запросов к API

## Шаги

### 1. Создать адаптер

```bash
# Создать файл
touch backend/app/llm/adapters/new_provider.py
```

```python
# backend/app/llm/adapters/new_provider.py
from typing import Optional
import httpx
from .base import AbstractLLMAdapter

class NewProviderAdapter(AbstractLLMAdapter):
    """Адаптер для New Provider API."""
    
    def __init__(self, api_key: str, api_url: str, model: str):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
    
    async def complete(
        self, 
        prompt: str, 
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Optional[str]:
        """Выполнить completion запрос."""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return data["choices"][0]["message"]["content"]
```

### 2. Зарегистрировать адаптер

```python
# backend/app/llm/__init__.py

from .adapters.new_provider import NewProviderAdapter

def get_adapter(model: str) -> AbstractLLMAdapter:
    if model.startswith("new-provider/"):
        return NewProviderAdapter(
            api_key=settings.NEW_PROVIDER_API_KEY,
            api_url=settings.NEW_PROVIDER_API_URL,
            model=model.replace("new-provider/", "")
        )
    # ... other adapters
```

### 3. Добавить конфигурацию

```python
# backend/app/core/config.py

class Settings(BaseSettings):
    # ... existing
    NEW_PROVIDER_API_KEY: Optional[str] = None
    NEW_PROVIDER_API_URL: str = "https://api.newprovider.com/v1/chat/completions"
```

### 4. Добавить в .env

```bash
echo "NEW_PROVIDER_API_KEY=your_key" >> backend/.env
```

// turbo

### 5. Тестировать

```bash
cd backend && python -c "
from app.llm import get_adapter
adapter = get_adapter('new-provider/model-name')
print(adapter)
"
```

## Чеклист

- [ ] Адаптер создан в `llm/adapters/`
- [ ] Наследует от AbstractLLMAdapter
- [ ] Зарегистрирован в `get_adapter()`
- [ ] Конфигурация добавлена в Settings
- [ ] Переменные окружения документированы
