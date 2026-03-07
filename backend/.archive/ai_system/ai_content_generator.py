"""
AI Content Generator: Auto-generate scientific discussions and conclusions.

Uses LLM to write expert-level interpretations based on statistical results.
"""
from typing import Dict, Any, List, Optional
import json
import os
from app.llm import _chat_completion
from app.core.config import settings


class AIContentGenerator:
    """
    Generate scientific text (discussion, conclusions) from statistical results.
    """
    
    def __init__(self):
        # Use settings for model choice
        self.model = os.getenv("LLM_MODEL_ID", "glm-4-flash")
    
    async def _ask_llm(self, prompt: str) -> Optional[str]:
        """Call LLM with prompt."""
        return await _chat_completion(
            model=self.model,
            prompt=prompt,
            temperature=0.3,
            max_tokens=2000,
            timeout_s=60.0
        )
    
    async def generate_discussion(
        self,
        results: Dict[str, Any],
        study_context: Dict[str, Any],
        chunk_size: int = 3
    ) -> Dict[str, List[str]]:
        """
        Generate discussion section for statistical report.
        
        Args:
            results: Statistical results by endpoint
            study_context: Goals, hypotheses, design info
            chunk_size: Endpoints per LLM call
            
        Returns:
            {"discussion": [...], "conclusions": [...]}
        """
        endpoints = list(results.keys())
        
        if not endpoints:
            return {"discussion": [], "conclusions": []}
        
        # Chunk endpoints for manageable prompts
        chunks = [endpoints[i:i+chunk_size] for i in range(0, len(endpoints), chunk_size)]
        
        discussion_parts = []
        
        for chunk in chunks:
            chunk_data = {ep: results[ep] for ep in chunk}
            prompt = self._build_discussion_prompt(chunk_data, study_context)
            
            try:
                response = await self._ask_llm(prompt)
                if response:
                    discussion_parts.append(response.strip())
            except Exception as e:
                print(f"Discussion generation failed: {e}")
        
        # Generate conclusions
        conclusions = await self._generate_conclusions(results, study_context)
        
        # Parse into paragraphs
        paragraphs = []
        for part in discussion_parts:
            for para in part.split("\n\n"):
                text = para.strip()
                if text and len(text) > 50:
                    paragraphs.append(text)
        
        return {
            "discussion": paragraphs,
            "conclusions": conclusions,
        }
    
    async def generate_interpretation(
        self,
        test_result: Dict[str, Any],
        endpoint_name: str,
        context: str = ""
    ) -> str:
        """
        Generate clinical interpretation for a single test result.
        """
        prompt = f"""Ты — клинический биостатистик. Напиши краткую интерпретацию результата теста.

**Показатель:** {endpoint_name}
**Результат:**
```json
{json.dumps(test_result, ensure_ascii=False, indent=2)}
```
{f"**Контекст:** {context}" if context else ""}

**Требования:**
- 2-3 предложения
- Упомяни p-value, effect size, клиническую значимость
- Научный стиль, без воды
- Не упоминай AI/модель
"""
        
        try:
            response = await self._ask_llm(prompt)
            return response.strip() if response else ""
        except:
            return ""
    
    async def _generate_conclusions(
        self,
        results: Dict[str, Any],
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate conclusions as bullet points."""
        prompt = f"""Ты — клинический биостатистик. Составь раздел "Выводы" на основе результатов.

**Результаты исследования:**
```json
{json.dumps(results, ensure_ascii=False, default=str)[:4000]}
```

**Контекст:**
```json
{json.dumps(context, ensure_ascii=False, default=str)[:1000]}
```

**Требования:**
- 6-10 коротких пунктов (каждый начинается с "• ")
- Каждый пункт должен быть проверяемым по данным
- 1-2 пункта про ограничения
- Не упоминай AI/модель
- Научный стиль
"""
        
        try:
            response = await self._ask_llm(prompt)
            if not response:
                return []
            
            conclusions = []
            for line in response.strip().split("\n"):
                text = line.strip()
                if text.startswith("•"):
                    conclusions.append(text)
                elif text.startswith("-"):
                    conclusions.append("• " + text.lstrip("- ").strip())
            
            return conclusions
        except:
            return []
    
    def _build_discussion_prompt(
        self,
        results: Dict[str, Any],
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for discussion section."""
        return f"""Ты — клинический биостатистик. Напиши часть раздела "Обсуждение" на русском.

**Цели исследования:**
{json.dumps(context.get("goals", []), ensure_ascii=False)}

**Гипотезы:**
{json.dumps(context.get("hypotheses", []), ensure_ascii=False)}

**Результаты для обсуждения:**
```json
{json.dumps(results, ensure_ascii=False, default=str)[:6000]}
```

**Требования:**
1. Привяжи интерпретацию к целям и гипотезам
2. Для каждого показателя: опиши результаты и клиническую значимость
3. Упоминай p-value (после коррекции Холма), BF₁₀, effect size
4. Если значимых различий нет — укажи это явно
5. 3-5 абзацев, БЕЗ списков
6. Научный стиль, без воды
7. Не упоминай AI/GLM/модель

Напиши обсуждение:
"""


class InterpretationLibrary:
    """
    Pre-built interpretations for common statistical scenarios.
    """
    
    @staticmethod
    def interpret_p_value(p: float, corrected: bool = False) -> str:
        """Standard p-value interpretation."""
        correction = " (после коррекции)" if corrected else ""
        
        if p < 0.001:
            return f"высокозначимо (p < 0.001{correction})"
        if p < 0.01:
            return f"значимо (p < 0.01{correction})"
        if p < 0.05:
            return f"значимо (p < 0.05{correction})"
        if p < 0.10:
            return f"тенденция к значимости (p = {p:.3f}{correction})"
        return f"незначимо (p = {p:.3f}{correction})"
    
    @staticmethod
    def interpret_trend(baseline: float, followup: float, direction: str) -> str:
        """Interpret change direction."""
        change = followup - baseline
        pct_change = (change / abs(baseline)) * 100 if baseline != 0 else 0
        
        if direction == "lower_is_better":
            if change < 0:
                return f"улучшение на {abs(pct_change):.1f}%"
            elif change > 0:
                return f"ухудшение на {pct_change:.1f}%"
            else:
                return "без изменений"
        else:
            if change > 0:
                return f"улучшение на {pct_change:.1f}%"
            elif change < 0:
                return f"ухудшение на {abs(pct_change):.1f}%"
            else:
                return "без изменений"
    
    @staticmethod
    def format_mean_sd(mean: float, sd: float) -> str:
        """Format mean ± SD."""
        return f"{mean:.2f} ± {sd:.2f}"
    
    @staticmethod
    def format_median_iqr(median: float, q1: float, q3: float) -> str:
        """Format median [IQR]."""
        return f"{median:.2f} [{q1:.2f}–{q3:.2f}]"
