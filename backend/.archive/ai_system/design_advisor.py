"""
Design Advisor: Expert LLM recommendations for study design and analysis plan.

Purpose:
    Analyze metadata → Recommend design, tests, and visualizations
"""
from typing import Dict, Any
import json
from .llm_client import MyLLMClient


class DesignAdvisor:
    """
    AI expert that recommends statistical analysis design.
    """
    
    def __init__(self):
        self.llm = MyLLMClient()
    
    async def recommend(
        self,
        metadata: Dict[str, Any],
        standardized_columns: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Get expert recommendations for study design and analysis.
        
        Args:
            metadata: From MetadataExtractor
            standardized_columns: Optional renamed columns
            
        Returns:
            Structured design recommendation
        """
        prompt = self._build_prompt(metadata, standardized_columns)
        
        try:
            response = await self.llm.ask(prompt, response_format="json")
            design = json.loads(response)
            return design
        except Exception as e:
            print(f"Design recommendation failed: {e}")
            return self._fallback_design(metadata)
    
    def _build_prompt(
        self,
        metadata: Dict[str, Any],
        standardized_columns: Dict[str, str] = None
    ) -> str:
        """Build expert consultation prompt."""
        
        # Use standardized names if available
        col_names = (
            list(standardized_columns.values())
            if standardized_columns
            else [c["name"] for c in metadata["columns"]]
        )
        
        prompt = f"""Ты биостатистик-эксперт мирового уровня. Проанализируй структуру данных и разработай план статистического анализа.

**МЕТАДАННЫЕ ИССЛЕДОВАНИЯ:**
```json
{{
    "shape": {json.dumps(metadata['shape'])},
    "structure": "{metadata.get('detected_structure', 'unknown')}",
    "families": {json.dumps(metadata.get('detected_families', []), ensure_ascii=False)},
    "quality": {json.dumps(metadata.get('quality_summary', {}))}
}}
```

**КОЛОНКИ (с ролями):**
```json
{json.dumps([
    {
        "name": c.get("standardized_name", c["name"]),
        "role": c.get("likely_role", "unknown"),
        "type": c["dtype"],
        "samples": c["sample_values"][:2]
    }
    for c in metadata["columns"][:30]
], ensure_ascii=False, indent=2)}
```

**ЗАДАЧА:**
Определи и верни структурированный план в JSON:

1. **study_design**: тип дизайна (RCT, observational, longitudinal, etc.)
2. **variables**:
   - group_col: основная группировочная переменная
   - subject_col: идентификатор субъекта
   - primary_endpoints: список первичных исходов
   - secondary_endpoints: вторичные исходы
   - covariates: ковариаты для корректировки
3. **recommended_analyses**: список рекомендуемых тестов
   - type: название теста (t-test, anova, mixed_anova, lmm, etc.)
   - description: объяснение зачем
   - variables: какие переменные
4. **visualizations**: рекомендуемые графики
   - type: тип (boxplot, spaghetti, forest, etc.)
   - variables: что отображать

**ФОРМАТ ОТВЕТА (строгий JSON):**
```json
{{
    "study_design": {{
        "type": "...",
        "structure": "...",
        "rationale": "почему так определили"
    }},
    "variables": {{
        "group_col": "...",
        "subject_col": "...",
        "primary_endpoints": [...],
        "secondary_endpoints": [...],
        "covariates": [...]
    }},
    "recommended_analyses": [
        {{
            "type": "...",
            "description": "...",
            "variables": {{...}}
        }}
    ],
    "visualizations": [
        {{
            "type": "...",
            "description": "...",
            "variables": {{...}}
        }}
    ]
}}
```
"""
        return prompt
    
    def _fallback_design(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback design if LLM fails."""
        # Find likely group column
        group_col = None
        for col in metadata["columns"]:
            if col.get("likely_role") == "grouping_variable":
                group_col = col["name"]
                break
        
        return {
            "study_design": {
                "type": metadata.get("detected_structure", "unknown"),
                "structure": metadata.get("detected_structure", "unknown"),
                "rationale": "Auto-detected from structure"
            },
            "variables": {
                "group_col": group_col,
                "subject_col": None,
                "primary_endpoints": [],
                "secondary_endpoints": [],
                "covariates": []
            },
            "recommended_analyses": [
                {
                    "type": "descriptive_statistics",
                    "description": "Basic summary statistics",
                    "variables": {}
                }
            ],
            "visualizations": [
                {
                    "type": "histogram",
                    "description": "Distribution plots",
                    "variables": {}
                }
            ]
        }
