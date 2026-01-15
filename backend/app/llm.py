import httpx
import json
from typing import Any, Optional, Tuple
from app.core.config import settings
from app.schemas.analysis import AnalysisResult
from app.core.logging import logger


def _is_openrouter_model(model: str) -> bool:
    return "/" in model


def _resolve_llm_target(model: str) -> Tuple[str, Optional[str]]:
    if _is_openrouter_model(model):
        url = getattr(settings, "OPENROUTER_API_URL", settings.GLM_API_URL)
        api_key = getattr(settings, "OPENROUTER_API_KEY", None) or settings.GLM_API_KEY
        return url, api_key
    return settings.GLM_API_URL, settings.GLM_API_KEY


async def _chat_completion(
    *,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
) -> Optional[str]:
    if not getattr(settings, "GLM_ENABLED", True):
        return None

    url, api_key = _resolve_llm_target(model)
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content
    except Exception as e:
        logger.error(f"LLM Error: {e}", exc_info=True)
        return None

async def get_ai_conclusion(result: AnalysisResult) -> str:
    """
    Calls GLM-4 model to generate a human-readable conclusion based on analysis results.
    """
    if not getattr(settings, "GLM_ENABLED", True):
        return result.conclusion

    # Prepare the prompt
    stats_summary = ""
    if result.plot_stats:
        for group, stats in result.plot_stats.items():
            stats_summary += f"- {group}: Mean={stats['mean']:.2f}, Median={stats['median']:.2f}\n"

    p_value_str = f"{result.p_value:.5f}" if result.p_value is not None else "N/A"

    prompt = f"""
You are an expert statistician and data analyst. 
Interpret the following statistical test results and provide a concise, professional conclusion (2-3 sentences) in Russian.

Context:
- Test Used: {result.method.name} ({result.method.type})
- P-Value: {p_value_str}
- Significant Difference: {"Yes" if result.significant else "No"}
- Group Statistics:
{stats_summary}

Instructions:
1. State clearly if the difference is statistically significant.
2. If significant, mention which group has higher values.
3. Keep it professional and strictly based on the provided data.
4. Do NOT mention "GLM" or "AI".
"""

    conclusion = await _chat_completion(
        model=settings.GLM_MODEL,
        prompt=prompt,
        temperature=0.5,
        max_tokens=150,
        timeout_s=15.0,
    )
    return conclusion or result.conclusion

async def scan_data_quality(csv_head: Any, columns_info: Optional[str] = None) -> list:
    """
    Calls GLM-4 to identify potential data quality issues (PII, Logic, Mixed Types).
    Returns a list of dictionaries (issues).
    """
    if not getattr(settings, "GLM_ENABLED", True):
        return []

    if columns_info is None and not isinstance(csv_head, str):
        df = csv_head
        head_csv = df.head(10).to_csv(index=False)
        meta_lines = []
        for col in df.columns:
            series = df[col]
            meta_lines.append(
                f"- {col}: dtype={series.dtype}, missing={int(series.isna().sum())}, unique={int(series.nunique(dropna=True))}"
            )
        columns_info = "\n".join(meta_lines)
        csv_head = head_csv
    else:
        csv_head = str(csv_head)
        columns_info = str(columns_info or "")

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

    content = await _chat_completion(
        model=settings.GLM_MODEL,
        prompt=prompt,
        temperature=0.1,
        max_tokens=1000,
        timeout_s=20.0,
    )
    if not content:
        return []

    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        parsed = json.loads(content.strip())
        if isinstance(parsed, dict) and isinstance(parsed.get("issues"), list):
            return parsed["issues"]
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception as e:
        logger.error(f"LLM Quality Scan Error: {e}", exc_info=True)
        return []
