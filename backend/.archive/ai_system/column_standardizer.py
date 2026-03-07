"""
Column Standardizer: Uses LLM to standardize column names to best practices.

Purpose:
    "Unnamed: 0", "пац_ид", "УПДРС_м0" → "row_id", "patient_id", "updrs_m0"
"""
from typing import Dict, Any, List
import json
from .llm_client import MyLLMClient


class ColumnStandardizer:
    """
    Uses LLM to create standardized, clean column names.
    """
    
    def __init__(self):
        self.llm = MyLLMClient()
    
    async def standardize(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate standardized column name mapping.
        
        Args:
            metadata: Output from MetadataExtractor
            
        Returns:
            {"old_name": "new_standardized_name"}
        """
        prompt = self._build_prompt(metadata)
        
        try:
            response = await self.llm.ask(prompt, response_format="json")
            mapping = json.loads(response)
            
            # Validate mapping
            if isinstance(mapping, dict):
                return mapping
            else:
                # Fallback: no changes
                return {col["name"]: col["name"] for col in metadata["columns"]}
        except Exception as e:
            print(f"Standardization failed: {e}")
            # Return identity mapping
            return {col["name"]: col["name"] for col in metadata["columns"]}
    
    def _build_prompt(self, metadata: Dict[str, Any]) -> str:
        """Build expert prompt for LLM."""
        
        # Prepare column summaries
        col_summaries = []
        for col in metadata["columns"][:50]:  # Limit to first 50 for context
            summary = {
                "current_name": col["name"],
                "dtype": col["dtype"],
                "sample_values": col["sample_values"][:3],
                "likely_role": col.get("likely_role", "unknown"),
                "detected_pattern": col.get("detected_pattern")
            }
            col_summaries.append(summary)
        
        prompt = f"""Ты эксперт по data science и биостатистике. Стандартизируй названия колонок.

**ПРАВИЛА:**
1. **snake_case** (lowercase с подчёркиваниями)
2. **Английский язык** (транслитерировать русские названия)
3. **Краткость** (max 30 символов)
4. **Сохранить медицинские аббревиатуры** (UPDRS → updrs, МоСА → moca)
5. **Временные точки:** сохранять как суффикс
   - "УПДРС М0" → "updrs_m0"
   - "Pain Pre" → "pain_pre"
   - "Score_1" → "score_t1"
6. **Специальные роли:**
   - Unnamed: 0 → row_id
   - ID колонки → patient_id / subject_id
   - Группы → treatment_group / group

**МЕТАДАННЫЕ ДАТАСЕТА:**
- Rows: {metadata['shape']['rows']}
- Columns: {metadata['shape']['cols']}
- Structure: {metadata.get('detected_structure', 'unknown')}

**КОЛОНКИ:**
```json
{json.dumps(col_summaries, ensure_ascii=False, indent=2)}
```

**Detected families:**
{json.dumps(metadata.get('detected_families', []), ensure_ascii=False, indent=2)}

**ЗАДАЧА:**
Верни JSON-маппинг вида:
{{
    "старое_название": "new_standardized_name",
    "другое_название": "another_standardized_name"
}}

Для **всех** колонок в списке, даже если название уже хорошее (тогда можно оставить как есть).
"""
        
        return prompt
