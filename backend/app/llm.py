import httpx
from app.core.config import settings
from app.schemas.analysis import AnalysisResult
from app.core.logging import logger

async def get_ai_conclusion(result: AnalysisResult) -> str:
    """
    Calls GLM-4 model to generate a human-readable conclusion based on analysis results.
    """
    if not settings.GLM_API_KEY:
        return result.conclusion # Fallback to default

    # Prepare the prompt
    stats_summary = ""
    if result.plot_stats:
        for group, stats in result.plot_stats.items():
            stats_summary += f"- {group}: Mean={stats['mean']:.2f}, Median={stats['median']:.2f}\n"

    prompt = f"""
You are an expert statistician and data analyst. 
Interpret the following statistical test results and provide a concise, professional conclusion (2-3 sentences) in Russian.

Context:
- Test Used: {result.method.name} ({result.method.type})
- P-Value: {result.p_value:.5f}
- Significant Difference: {"Yes" if result.significant else "No"}
- Group Statistics:
{stats_summary}

Instructions:
1. State clearly if the difference is statistically significant.
2. If significant, mention which group has higher values.
3. Keep it professional and strictly based on the provided data.
4. Do NOT mention "GLM" or "AI".
"""

    headers = {
        "Authorization": f"Bearer {settings.GLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": settings.GLM_MODEL, 
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 150
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.GLM_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            conclusion = data["choices"][0]["message"]["content"].strip()
            return conclusion
    except Exception as e:
        logger.error(f"LLM Error: {e}", exc_info=True)
        return result.conclusion # Fallback on error

async def scan_data_quality(csv_head: str, columns_info: str) -> list:
    """
    Calls GLM-4 to identify potential data quality issues (PII, Logic, Mixed Types).
    Returns a list of dictionaries (issues).
    """
    if not settings.GLM_API_KEY:
        return []

    prompt = f"""
You are a Data Quality Auditor. Analyze the following dataset snippet (first 10 rows) and column metadata.
Identify POTENTIAL issues:
1. PII (Personal Identifiable Information) - e.g. names, phones, emails.
2. Logic Errors - e.g. Age > 120, negative values where positive expected.
3. Mixed Types - e.g. text in numeric columns.
4. Typos / Inconsistencies - e.g. "Moscow" vs "moscow".

Dataset Snippet:
{csv_head}

Column Metadata:
{columns_info}

Return a list of issues in JSON format.
Format:
[
  {{
    "column": "ColumnName",
    "issue_type": "pii" | "logic" | "mixed_type" | "typo",
    "severity": "high" | "medium" | "low",
    "description": "Short explanation",
    "suggestion": "Actionable advice"
  }}
]
Return ONLY JSON. No markdown, no commentary.
"""

    headers = {
        "Authorization": f"Bearer {settings.GLM_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": settings.GLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1, # Low temp for structured output
        "max_tokens": 1000
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(settings.GLM_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            # Cleanup markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            
            import json
            return json.loads(content.strip())
    except Exception as e:
        logger.error(f"LLM Quality Scan Error: {e}", exc_info=True)
        return []
