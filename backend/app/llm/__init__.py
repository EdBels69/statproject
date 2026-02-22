import json
import asyncio
import hashlib
import time
import os
import math
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import AnalysisResult
from app.modules.knowledge_store import search_documents, route_documents, get_document


_LLM_CACHE: "OrderedDict[str, Tuple[float, str]]" = OrderedDict()
_LLM_CACHE_MAX = 256
_LLM_CACHE_TTL_S = 600
_ROLE_MODEL_OVERRIDES: ContextVar[Dict[str, str]] = ContextVar("clinimetria_role_model_overrides", default={})


def _normalize_role_models(role_models: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not isinstance(role_models, dict):
        return {}
    normalized: Dict[str, str] = {}
    for key, value in role_models.items():
        if value is None:
            continue
        key_norm = str(key).strip().lower()
        value_norm = str(value).strip()
        if key_norm and value_norm:
            normalized[key_norm] = value_norm
    return normalized


@contextmanager
def role_model_overrides(role_models: Optional[Dict[str, Any]]):
    normalized = _normalize_role_models(role_models)
    if not normalized:
        yield
        return
    token = _ROLE_MODEL_OVERRIDES.set(normalized)
    try:
        yield
    finally:
        _ROLE_MODEL_OVERRIDES.reset(token)


def _get_role_model(role: str) -> str:
    role_key_raw = str(role or "").strip()
    if role_key_raw:
        overrides = _ROLE_MODEL_OVERRIDES.get()
        override = overrides.get(role_key_raw.lower()) if isinstance(overrides, dict) else None
        if override:
            return override

    role_key = role_key_raw.upper()
    env_key = f"CLINIMETRIA_MODEL_{role_key}"
    model = os.getenv(env_key)
    if model:
        return model
    return settings.GLM_MODEL


def _get_role_model_optional(role: str) -> Optional[str]:
    role_key_raw = str(role or "").strip()
    if role_key_raw:
        overrides = _ROLE_MODEL_OVERRIDES.get()
        override = overrides.get(role_key_raw.lower()) if isinstance(overrides, dict) else None
        if override:
            return override

    role_key = role_key_raw.upper()
    env_key = f"CLINIMETRIA_MODEL_{role_key}"
    model = os.getenv(env_key)
    return model or None


def _llm_cache_get(key: str) -> Optional[str]:
    item = _LLM_CACHE.get(key)
    if not item:
        return None
    ts, value = item
    if (time.time() - ts) > _LLM_CACHE_TTL_S:
        try:
            del _LLM_CACHE[key]
        except KeyError:
            pass
        return None
    _LLM_CACHE.move_to_end(key)
    return value


def _llm_cache_set(key: str, value: str) -> None:
    if not key or not value:
        return
    _LLM_CACHE[key] = (time.time(), value)
    _LLM_CACHE.move_to_end(key)
    while len(_LLM_CACHE) > _LLM_CACHE_MAX:
        _LLM_CACHE.popitem(last=False)


def _make_llm_cache_key(*, model: str, url: str, payload: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(str(model or "").encode("utf-8", errors="ignore"))
    h.update(b"\n")
    h.update(str(url or "").encode("utf-8", errors="ignore"))
    h.update(b"\n")
    h.update(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8", errors="ignore"))
    return h.hexdigest()


def _is_openrouter_model(model: str) -> bool:
    return "/" in model


def _resolve_llm_target(model: str) -> Tuple[str, Optional[str]]:
    model_id = str(model or "").strip().lower()
    direct_zai = bool(getattr(settings, "CLINIMETRIA_ZAI_DIRECT", False))
    zai_key = getattr(settings, "ZAI_API_KEY", None)
    zai_url = getattr(settings, "ZAI_API_URL", None) or settings.GLM_API_URL

    if direct_zai and model_id.startswith("z-ai/") and zai_key:
        return zai_url, zai_key

    if _is_openrouter_model(model):
        url = getattr(settings, "OPENROUTER_API_URL", settings.GLM_API_URL)
        api_key = getattr(settings, "OPENROUTER_API_KEY", None) or settings.GLM_API_KEY
        return url, api_key
    return settings.GLM_API_URL, settings.GLM_API_KEY


def _normalize_chat_completions_url(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        return u
    if "/chat/completions" in u:
        return u
    u = u.rstrip("/")
    if "api.z.ai" in u:
        return u
    if u.endswith("/paas/v4") or u.endswith("/coding/paas/v4"):
        return u + "/chat/completions"
    return u


async def _chat_completion(
    *,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    timeout_s: float,
    response_format: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Dict[str, int]]:
    """
    Returns (content, usage_dict).
    usage_dict example: {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    """
    if not getattr(settings, "GLM_ENABLED", True):
        print("DEBUG: GLM_ENABLED is False")
        return None, {}

    url, api_key = _resolve_llm_target(model)
    url = _normalize_chat_completions_url(url)
    if not api_key:
        print(f"DEBUG: Missing API Key for model {model}. Settings keys: {settings.dict().keys() if hasattr(settings, 'dict') else dir(settings)}")
        return None, {}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept-Language": "ru-RU,ru",
    }
    
    # Special header for RouterAI/OpenRouter to identify app
    if "routerai" in url or "openrouter" in url:
        headers["HTTP-Referer"] = "https://clinimetria.app"
        headers["X-Title"] = "Clinimetria"

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format
    if "api.z.ai" in str(url):
        thinking_pref = str(os.getenv("CLINIMETRIA_GLM_THINKING", "")).strip().lower()
        if thinking_pref in {"disabled", "off", "false", "0"}:
            payload["thinking"] = {"type": "disabled"}
        elif thinking_pref in {"enabled", "on", "true", "1"}:
            payload["thinking"] = {"type": "enabled"}

    # Cache logic (ignoring usage for cached items for now, or could store it)
    cache_key = _make_llm_cache_key(model=model, url=str(url), payload=payload)
    cached = _llm_cache_get(cache_key)
    if cached:
        # Return 0 usage for cached hits to indicate no cost
        return cached, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached": 1}

    retry_attempts = 3
    retry_delay_s = 0.35
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        for attempt in range(retry_attempts):
            try:
                resp = await client.post(url, json=payload, headers=headers)
                status_code = getattr(resp, "status_code", None)
                if isinstance(status_code, int) and (status_code == 429 or status_code >= 500):
                    raise httpx.HTTPStatusError(
                        "retryable status",
                        request=resp.request,
                        response=resp,
                    )

                resp.raise_for_status()
                data = resp.json()
                
                # Extract usage
                usage = data.get("usage") or {}
                if not usage:
                    # Estimate if missing
                    usage = {
                        "prompt_tokens": len(prompt) // 4,
                        "completion_tokens": 0,
                        "total_tokens": len(prompt) // 4
                    }

                msg = (data.get("choices") or [{}])[0].get("message") or {}
                content = str(msg.get("content") or "").strip()
                if not content:
                    content = str(msg.get("reasoning_content") or "").strip()
                content = content.strip()
                
                # Update completion tokens if we have content
                if usage.get("completion_tokens", 0) == 0 and content:
                    usage["completion_tokens"] = len(content) // 4
                    usage["total_tokens"] = usage.get("prompt_tokens", 0) + usage["completion_tokens"]

                if content:
                    _llm_cache_set(cache_key, content)
                    return content, usage
                return None, {}
            except Exception as e:
                if attempt >= retry_attempts - 1:
                    logger.error(f"LLM Error: {e}", exc_info=True)
                    return None, {}
                await asyncio.sleep(retry_delay_s * (2**attempt))

    return None, {}


async def get_ai_conclusion(result: AnalysisResult, role_models: Optional[Dict[str, Any]] = None) -> str:
    if not getattr(settings, "GLM_ENABLED", True):
        return result.conclusion

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

    with role_model_overrides(role_models):
        conclusion, _ = await _chat_completion(
            model=_get_role_model("interpret"),
            prompt=prompt,
            temperature=0.5,
            max_tokens=150,
            timeout_s=15.0,
        )
        return conclusion or result.conclusion


async def scan_data_quality(csv_head: Any, columns_info: Optional[str] = None, role_models: Optional[Dict[str, Any]] = None) -> list:
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

    with role_model_overrides(role_models):
        content, _ = await _chat_completion(
            model=_get_role_model("quality"),
            prompt=prompt,
            temperature=0.1,
            max_tokens=1000,
            timeout_s=20.0,
        )
    if not content:
        return []

    text = str(content).strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    try:
        parsed = json.loads(text.strip())
        if isinstance(parsed, dict) and isinstance(parsed.get("issues"), list):
            return parsed["issues"]
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception as e:
        logger.error(f"LLM Quality Scan Error: {e}", exc_info=True)
        return []


def _strip_json_fences(content: str) -> str:
    text = str(content or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _extract_json_object(text: str) -> str:
    if not text:
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _parse_json_response(content: str) -> Optional[Any]:
    text = _extract_json_object(_strip_json_fences(content))
    try:
        return json.loads(text)
    except Exception:
        return None


async def _repair_json_with_llm(raw: str, *, role: str = "planner", max_tokens: int = 1200, role_models: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if not raw:
        return None
    prompt = f"""
Ты — JSON-редактор. Исправь ввод так, чтобы получился валидный JSON.
Требования:
- Верни ТОЛЬКО JSON, без markdown и комментариев.
- Сохрани исходную структуру как можно ближе.

Вход:
{raw}
"""
    with role_model_overrides(role_models):
        content, _ = await _chat_completion(
            model=_get_role_model(role),
            prompt=prompt,
            temperature=0.0,
            max_tokens=max_tokens,
            timeout_s=25.0,
        )
        return content


async def critique_protocol(
    *,
    protocol: List[Dict[str, Any]],
    dataset_meta: Dict[str, Any],
    preferences: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    role_models: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not getattr(settings, "GLM_ENABLED", True):
        return None

    prefs = preferences if isinstance(preferences, dict) else {}
    constrained = constraints if isinstance(constraints, dict) else {}

    cols = dataset_meta.get("columns") if isinstance(dataset_meta, dict) else []
    if isinstance(cols, list):
        cols = cols[:200]
    summary = {
        "summary": dataset_meta.get("summary") if isinstance(dataset_meta, dict) else None,
        "columns": cols,
    }

    payload = {
        "dataset_meta": summary,
        "protocol": protocol[:60],
        "preferences": prefs,
        "constraints": constrained,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)

    prompt = f"""
Ты — строгий рецензент статистического протокола. Проверь, что шаги протокола валидны по данным.

Правила:
- Удаляй шаг ТОЛЬКО если он невозможен (нет колонок, нет обязательных полей, метод не применим).
- Не удаляй шаги просто из-за “слабой идеи”.
- Верни JSON без markdown.

Формат ответа:
{{
  "score": 0-100,
  "drop_step_ids": ["step_1", ...],
  "issues": ["..."],
  "notes": ["..."]
}}

Вход:
{payload_json}
"""

    json_mode = str(os.getenv("CLINIMETRIA_LLM_JSON_MODE", "")).strip().lower()
    response_format = {"type": "json_object"} if json_mode in {"1", "true", "yes", "on", "json"} else None

    with role_model_overrides(role_models):
        content, _ = await _chat_completion(
            model=_get_role_model("quality"),
            prompt=prompt,
            temperature=0.0,
            max_tokens=700,
            timeout_s=20.0,
            response_format=response_format,
        )
    if not content:
        return None

    payload_raw = _extract_json_object(_strip_json_fences(content))
    try:
        parsed = json.loads(payload_raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        try:
            repaired = await _repair_json_with_llm(payload_raw, role="quality", max_tokens=700, role_models=role_models)
            if repaired:
                fixed = _extract_json_object(_strip_json_fences(repaired))
                parsed = json.loads(fixed)
                return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        num = float(value)
        if not math.isfinite(num):
            return None
        return num
    except Exception:
        return None


async def _summarize_protocol_chunk(
    *,
    language: str,
    stats: Dict[str, Any],
    items: List[Dict[str, Any]],
    max_tokens: int,
) -> Optional[List[str]]:
    lang = "ru" if str(language or "").lower().startswith("ru") else "en"
    stats_json = json.dumps(stats, ensure_ascii=False)
    items_json = json.dumps(items, ensure_ascii=False)
    prompt = f"""
You are a senior biostatistician. Summarize protocol step findings into short notes.

Constraints:
- Return ONLY JSON, no markdown.
- Output format: {{ "notes": ["..."] }}
- Each note should be 1 sentence.
- Use {("Russian" if lang == "ru" else "English")}.
- Do NOT mention "AI" or model names.
- Use only provided data (no assumptions).

Study stats:
{stats_json}

Step items:
{items_json}
"""

    content, _ = await _chat_completion(
        model=_get_role_model("report"),
        prompt=prompt,
        temperature=0.35,
        max_tokens=max_tokens,
        timeout_s=25.0,
    )
    if not content:
        return None
    parsed = _parse_json_response(content)
    if isinstance(parsed, dict) and isinstance(parsed.get("notes"), list):
        return [str(n) for n in parsed.get("notes") if isinstance(n, (str, int, float)) and str(n).strip()]
    if isinstance(parsed, list):
        return [str(n) for n in parsed if isinstance(n, (str, int, float)) and str(n).strip()]
    return None


async def generate_protocol_summary(
    findings: Dict[str, Any],
    *,
    language: str = "ru",
    max_items: int = 12,
    max_tokens: int = 450,
    role_models: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not getattr(settings, "GLM_ENABLED", True):
        return None

    items = findings.get("items") if isinstance(findings, dict) else None
    items = items if isinstance(items, list) else []

    def _rank(item: Dict[str, Any]) -> tuple:
        sig = item.get("significant")
        p = _safe_float(item.get("p_value"))
        return (0 if sig else 1, p if p is not None else 1.0)

    prepared: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        prepared.append(
            {
                "step_id": item.get("step_id"),
                "type": item.get("type"),
                "method": item.get("method"),
                "target": item.get("target"),
                "group": item.get("group"),
                "visit": item.get("visit"),
                "p_value": _safe_float(item.get("p_value")),
                "significant": item.get("significant"),
                "effect_size": _safe_float(item.get("effect_size")),
                "conclusion": item.get("conclusion"),
            }
        )

    prepared = sorted(prepared, key=_rank)
    if max_items and len(prepared) > max_items:
        prepared = prepared[:max_items]

    stats = {
        "total_steps": findings.get("unique_steps") or findings.get("total_steps"),
        "significant_steps": findings.get("significant_steps"),
        "alpha": _safe_float(findings.get("alpha")),
    }

    lang = "ru" if str(language or "").lower().startswith("ru") else "en"

    if not prepared:
        return None

    with role_model_overrides(role_models):
        chunk_size = 6
        max_chunks = 3
        notes: List[str] = []
        if len(prepared) > chunk_size:
            for i in range(0, min(len(prepared), chunk_size * max_chunks), chunk_size):
                chunk = prepared[i : i + chunk_size]
                chunk_notes = await _summarize_protocol_chunk(
                    language=lang,
                    stats=stats,
                    items=chunk,
                    max_tokens=min(220, max_tokens),
                )
                if chunk_notes:
                    notes.extend(chunk_notes)
        else:
            notes = []

        payload = {
            "stats": stats,
            "notes": notes[:12],
            "items": prepared[:8],
        }
        payload_json = json.dumps(payload, ensure_ascii=False)

        prompt = f"""
You are a senior biostatistician writing a report discussion and conclusions.

Constraints:
- Return ONLY JSON (no markdown).
- Output format:
{{ "discussion": ["..."], "conclusion": ["..."] }}
- discussion: 2-4 sentences.
- conclusion: 3-6 short bullet sentences.
- Use {("Russian" if lang == "ru" else "English")}.
- Do NOT mention "AI" or model names.
- Use only provided data; avoid speculation.

Input:
{payload_json}
"""

        content, _ = await _chat_completion(
            model=_get_role_model("report"),
            prompt=prompt,
            temperature=0.35,
            max_tokens=max_tokens,
            timeout_s=30.0,
        )
    if not content:
        return None

    parsed = _parse_json_response(content)
    if not isinstance(parsed, dict):
        return None

    discussion = parsed.get("discussion")
    conclusions = parsed.get("conclusion") or parsed.get("conclusions")

    def _norm_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, (str, int, float)) and str(v).strip()]
        if isinstance(value, (str, int, float)):
            v = str(value).strip()
            return [v] if v else []
        return []

    discussion_out = _norm_list(discussion)
    conclusion_out = _norm_list(conclusions)

    if not discussion_out and not conclusion_out:
        return None

    return {
        "discussion": discussion_out,
        "conclusion": conclusion_out,
        "language": lang,
        "model": _get_role_model("report"),
    }


def _slice_dataset_meta_for_chunk(dataset_meta: Dict[str, Any], column_names: List[str]) -> Dict[str, Any]:
    if not isinstance(dataset_meta, dict):
        return {}
    col_set = {str(c) for c in column_names if c}
    meta = dict(dataset_meta)

    cols = meta.get("columns") if isinstance(meta.get("columns"), list) else []
    filtered_cols = [c for c in cols if isinstance(c, dict) and c.get("name") in col_set]
    meta["columns"] = filtered_cols

    numeric_cols = meta.get("numeric_cols") if isinstance(meta.get("numeric_cols"), list) else []
    meta["numeric_cols"] = [c for c in numeric_cols if c in col_set]

    categorical_cols = meta.get("categorical_cols") if isinstance(meta.get("categorical_cols"), list) else []
    meta["categorical_cols"] = [c for c in categorical_cols if c in col_set]

    sample_rows = meta.get("sample_rows") if isinstance(meta.get("sample_rows"), list) else []
    filtered_rows: List[Dict[str, Any]] = []
    for row in sample_rows:
        if isinstance(row, dict):
            filtered_rows.append({k: v for k, v in row.items() if k in col_set})
    meta["sample_rows"] = filtered_rows

    sample_info = meta.get("sample_info")
    if isinstance(sample_info, dict):
        sample_cols = sample_info.get("columns") if isinstance(sample_info.get("columns"), list) else []
        sample_info = dict(sample_info)
        sample_info["columns"] = [c for c in sample_cols if c in col_set]
        meta["sample_info"] = sample_info

    summary = meta.get("summary")
    if isinstance(summary, dict):
        summary = dict(summary)
        summary["columns_scanned"] = len(filtered_cols)
        meta["summary"] = summary

    return meta


def _merge_planner_payloads(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {
        "status": "completed",
        "protocol_name": "Протокол",
        "globals": {},
        "protocol": [],
        "notes": [],
    }
    if not payloads:
        return merged

    globals_out: Dict[str, Any] = {}
    notes_out: List[str] = []
    protocol_out: List[Dict[str, Any]] = []
    seen: set = set()

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        name = payload.get("protocol_name")
        if name and merged.get("protocol_name") == "Протокол":
            merged["protocol_name"] = str(name)
        globals_in = payload.get("globals") if isinstance(payload.get("globals"), dict) else {}
        for key, value in globals_in.items():
            if key not in globals_out and value is not None:
                globals_out[key] = value
        notes_in = payload.get("notes") if isinstance(payload.get("notes"), list) else []
        for note in notes_in:
            note_str = str(note).strip()
            if note_str and note_str not in notes_out:
                notes_out.append(note_str)
        steps = payload.get("protocol") if isinstance(payload.get("protocol"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            key = json.dumps(
                {"method": step.get("method"), "config": step.get("config")},
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            if key in seen:
                continue
            seen.add(key)
            protocol_out.append(step)

    merged["globals"] = globals_out
    merged["notes"] = notes_out
    merged["protocol"] = protocol_out
    return merged


async def _analyze_research_design_single(
    *,
    text: str,
    dataset_meta: Dict[str, Any],
    current_protocol: Optional[List[Dict[str, Any]]] = None,
    preferences: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    role_models: Optional[Dict[str, Any]] = None,
    chunk_info: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not getattr(settings, "GLM_ENABLED", True):
        return None

    meta_json = json.dumps(dataset_meta, ensure_ascii=False)
    protocol_json = json.dumps(current_protocol or [], ensure_ascii=False)
    prefs_json = json.dumps(preferences or {}, ensure_ascii=False)
    constraints_json = json.dumps(constraints or {}, ensure_ascii=False)
    sample_rows = []
    if isinstance(dataset_meta, dict) and isinstance(dataset_meta.get("sample_rows"), list):
        sample_rows = dataset_meta.get("sample_rows") or []
    sample_json = json.dumps(sample_rows, ensure_ascii=False)

    knowledge_snippets: List[Dict[str, Any]] = []
    prefs = preferences if isinstance(preferences, dict) else {}
    if prefs.get("use_knowledge_base", True):
        query = str(text or "").strip()
        if not query:
            cols = dataset_meta.get("columns") if isinstance(dataset_meta, dict) else None
            if isinstance(cols, list):
                query = " ".join([str(c.get("name")) for c in cols if isinstance(c, dict) and c.get("name")])
        if query:
            try:
                routed = route_documents(query, top_k=5)
                knowledge_snippets = []
                for idx, r in enumerate(routed):
                    snippet = None
                    if idx < 2:
                        doc = get_document(str(r.get("doc_id"))) if r.get("doc_id") else None
                        if isinstance(doc, dict):
                            chunks = doc.get("chunks") if isinstance(doc.get("chunks"), list) else []
                            if chunks:
                                snippet = str(chunks[0])[:300]
                            else:
                                snippet = str(doc.get("text") or "")[:300]
                    knowledge_snippets.append(
                        {
                            "title": r.get("title"),
                            "tags": r.get("tags") or [],
                            "keywords": r.get("keywords") or [],
                            "snippet": snippet or r.get("preview") or "",
                            "score": r.get("score"),
                        }
                    )
            except Exception:
                knowledge_snippets = []
    knowledge_json = json.dumps(knowledge_snippets or [], ensure_ascii=False)

    chunk_note = ""
    if isinstance(chunk_info, dict):
        idx = chunk_info.get("index")
        total = chunk_info.get("total")
        if idx and total:
            chunk_note = f"- Сейчас виден только чанк колонок {idx}/{total}. Планируй шаги только для этих колонок."

    prompt = f"""
Ты — методолог-биостатистик. По описанию исследования составь исполнимый протокол анализа.

Вход:
1) Описание исследования (текст пользователя)
2) Метаданные датасета (агрегаты: имена/типы/пропуски/роль/диапазоны)
3) Smart-sample строк (если есть) — это небольшой репрезентативный срез, использовать ТОЛЬКО для понимания семантики столбцов, НЕ для статистических выводов
3) Текущий протокол (если есть)
4) Предпочтения (глобальные настройки)
5) Ограничения по размеру протокола

Опорные материалы (из базы знаний, если есть):
{knowledge_json}

Smart-sample (если пусто — не использовать):
{sample_json}

Ограничения:
- Не выдумывай столбцы: используй только из dataset_meta.columns.
- Верни ТОЛЬКО JSON без markdown.
- protocol: массив шагов в порядке выполнения.
- method: один из идентификаторов: descriptive_compare, auto, t_test_ind, t_test_welch, mann_whitney, t_test_rel, wilcoxon, anova, anova_welch, kruskal, chi_square, pearson, spearman, linear_regression, logistic_regression, roc_analysis, mixed_effects, clustered_correlation, responders, anova_twoway, rm_anova, friedman, batch_analysis, timepoint_batch_analysis, paired_wide, delta_batch_analysis.
- config:
  - Для сравнений: outcome и group обязательны.
  - Для корреляций: outcome и group обязательны.
  - Для регрессий: outcome, predictors (массив) и covariates (массив) при необходимости. Для логистической регрессии можно добавить one_vs_rest=true и positive_label (если исход многоклассовый).
  - Для mixed_effects: outcome, time, group, subject.
  - Для clustered_correlation: variables (массив).
  - Для responders: outcome_columns (массив), time_labels (массив), group, subject, threshold, direction.
  - Для batch_analysis: targets (массив), group, method_id, multiplicity_correction.
  - Для timepoint_batch_analysis: split_by, group, targets (массив), method_id, multiplicity_correction.
  - Для anova_twoway: outcome, group1, group2.
  - Для paired_wide: baseline, follow, method (t_test_rel или wilcoxon).
  - Для delta_batch_analysis: group, pairs (массив {{baseline, follow, label}}), method_id, multiplicity_correction.
- Соблюдай ограничения constraints (max_steps, max_variables_per_step, max_predictors).
{chunk_note}

Формат ответа:
{{
  "status": "completed",
  "protocol_name": "...",
  "globals": {{
    "alternative": "two-sided" | "less" | "greater" | null,
    "post_hoc": "tukey" | "dunn" | "none" | null,
    "post_hoc_correction": "bh" | "bky" | "none" | null
  }},
  "protocol": [
    {{"id": "step_1", "name": "...", "method": "...", "config": {{}}}}
  ],
  "notes": ["..."]
}}

Описание исследования:
{str(text or "").strip()}

dataset_meta:
{meta_json}

current_protocol:
{protocol_json}

preferences:
{prefs_json}

constraints:
{constraints_json}
"""

    json_mode = str(os.getenv("CLINIMETRIA_LLM_JSON_MODE", "")).strip().lower()
    json_mode_enabled = json_mode in {"1", "true", "yes", "on", "json"}
    response_format = {"type": "json_object"} if json_mode_enabled else None
    planner_temp = 0.0 if json_mode_enabled else 0.2

    usage_log: Dict[str, Any] = {}

    with role_model_overrides(role_models):
        content, usage_primary = await _chat_completion(
            model=_get_role_model("planner"),
            prompt=prompt,
            temperature=planner_temp,
            max_tokens=1200,
            timeout_s=30.0,
            response_format=response_format,
        )
        if usage_primary:
            usage_log["planner"] = usage_primary
    if not content:
        return None
    raw_content = content

    try:
        payload = _extract_json_object(_strip_json_fences(content))
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            if usage_log and isinstance(preferences, dict) and preferences.get("return_usage"):
                parsed["usage"] = usage_log
            return parsed
        return None
    except Exception as e:
        logger.error(f"LLM Research Design Error: {e}", exc_info=True)
        json_fix_model = _get_role_model_optional("json_fix")
        if json_fix_model:
            fix_prompt = f"""
Ты — JSON-фиксатор. Преобразуй ответ планировщика в валидный JSON по схеме.
Требования:
- Верни ТОЛЬКО JSON (без markdown).
- Используй только колонки из dataset_meta.
- Следуй схеме ответа из основного промпта.

Черновой ответ:
{raw_content}

dataset_meta:
{meta_json}

preferences:
{prefs_json}

constraints:
{constraints_json}
"""
            try:
                with role_model_overrides(role_models):
                    fixed_content, usage_fix = await _chat_completion(
                        model=json_fix_model,
                        prompt=fix_prompt,
                        temperature=0.0,
                        max_tokens=1200,
                        timeout_s=30.0,
                        response_format={"type": "json_object"},
                    )
                if usage_fix:
                    usage_log["json_fix"] = usage_fix
                if fixed_content:
                    fixed_payload = _extract_json_object(_strip_json_fences(fixed_content))
                    parsed = json.loads(fixed_payload)
                    if isinstance(parsed, dict):
                        if usage_log and isinstance(preferences, dict) and preferences.get("return_usage"):
                            parsed["usage"] = usage_log
                        return parsed
            except Exception:
                pass
        try:
            repair_role = "planner_fallback" if _get_role_model_optional("planner_fallback") else "planner"
            repaired = await _repair_json_with_llm(payload, role=repair_role, max_tokens=1200, role_models=role_models)
            if repaired:
                fixed = _extract_json_object(_strip_json_fences(repaired))
                parsed = json.loads(fixed)
                if isinstance(parsed, dict):
                    if usage_log and isinstance(preferences, dict) and preferences.get("return_usage"):
                        parsed["usage"] = usage_log
                    return parsed
        except Exception as e2:
            logger.error(f"LLM JSON Repair Error: {e2}", exc_info=True)
        try:
            strict_prompt = prompt + "\nВАЖНО: Верни валидный JSON, двойные кавычки, без комментариев и без markdown."
            with role_model_overrides(role_models):
                retry_content, usage_retry = await _chat_completion(
                    model=_get_role_model("planner_fallback") if _get_role_model_optional("planner_fallback") else _get_role_model("planner"),
                    prompt=strict_prompt,
                    temperature=0.0,
                    max_tokens=1200,
                    timeout_s=30.0,
                    response_format=response_format,
                )
            if usage_retry:
                usage_log["planner_retry"] = usage_retry
            if retry_content:
                retry_payload = _extract_json_object(_strip_json_fences(retry_content))
                parsed = json.loads(retry_payload)
                if isinstance(parsed, dict):
                    if usage_log and isinstance(preferences, dict) and preferences.get("return_usage"):
                        parsed["usage"] = usage_log
                    return parsed
        except Exception:
            pass
        try:
            fallback_model = _get_role_model_optional("planner_fallback")
            if fallback_model:
                logger.info(f"Planner fallback model in use: {fallback_model}")
                convert_prompt = f"""
Ты — конвертер протоколов. Преобразуй черновой ответ планировщика в валидный JSON протокола.
Требования:
- Верни ТОЛЬКО JSON (без markdown).
- Используй только колонки из dataset_meta.
- Следуй схеме ответа из основного промпта.

Черновик планировщика:
{raw_content}

dataset_meta:
{meta_json}

preferences:
{prefs_json}

constraints:
{constraints_json}
"""
                with role_model_overrides(role_models):
                    fallback_content, usage_fallback = await _chat_completion(
                        model=fallback_model,
                        prompt=convert_prompt,
                        temperature=0.0,
                        max_tokens=1200,
                        timeout_s=30.0,
                        response_format={"type": "json_object"},
                    )
                if usage_fallback:
                    usage_log["planner_fallback"] = usage_fallback
                if fallback_content:
                    fallback_payload = _extract_json_object(_strip_json_fences(fallback_content))
                    parsed = json.loads(fallback_payload)
                    if isinstance(parsed, dict):
                        if usage_log and isinstance(preferences, dict) and preferences.get("return_usage"):
                            parsed["usage"] = usage_log
                        return parsed
        except Exception:
            pass
        return None


async def analyze_research_design(
    *,
    text: str,
    dataset_meta: Dict[str, Any],
    current_protocol: Optional[List[Dict[str, Any]]] = None,
    preferences: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    role_models: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    prefs = preferences if isinstance(preferences, dict) else {}
    use_chunking = bool(prefs.get("llm_chunk_plan"))
    chunk_size_raw = prefs.get("llm_chunk_size") or prefs.get("llm_chunk_plan_size")
    max_chunks_raw = prefs.get("llm_chunk_max_chunks")
    try:
        chunk_size = int(chunk_size_raw)
    except Exception:
        chunk_size = 30
    try:
        max_chunks = int(max_chunks_raw)
    except Exception:
        max_chunks = 4

    if not use_chunking or chunk_size < 5 or not isinstance(dataset_meta, dict):
        return await _analyze_research_design_single(
            text=text,
            dataset_meta=dataset_meta,
            current_protocol=current_protocol,
            preferences=preferences,
            constraints=constraints,
            role_models=role_models,
        )

    cols = dataset_meta.get("columns") if isinstance(dataset_meta.get("columns"), list) else []
    col_names = [str(c.get("name")) for c in cols if isinstance(c, dict) and c.get("name")]

    if not col_names or len(col_names) <= chunk_size:
        return await _analyze_research_design_single(
            text=text,
            dataset_meta=dataset_meta,
            current_protocol=current_protocol,
            preferences=preferences,
            constraints=constraints,
            role_models=role_models,
        )

    chunks: List[List[str]] = []
    for i in range(0, len(col_names), chunk_size):
        chunks.append(col_names[i : i + chunk_size])
        if max_chunks and len(chunks) >= max_chunks:
            break

    if len(chunks) <= 1:
        return await _analyze_research_design_single(
            text=text,
            dataset_meta=dataset_meta,
            current_protocol=current_protocol,
            preferences=preferences,
            constraints=constraints,
            role_models=role_models,
        )

    max_steps = None
    if isinstance(constraints, dict):
        try:
            max_steps = int(constraints.get("max_steps"))
        except Exception:
            max_steps = None
    per_chunk_steps = None
    if max_steps:
        per_chunk_steps = max(3, int(math.ceil(max_steps / float(len(chunks)))))

    payloads: List[Dict[str, Any]] = []
    usage_chunks: List[Dict[str, Any]] = []
    for idx, chunk_cols in enumerate(chunks, start=1):
        chunk_meta = _slice_dataset_meta_for_chunk(dataset_meta, chunk_cols)
        chunk_constraints = dict(constraints or {})
        if per_chunk_steps:
            chunk_constraints["max_steps"] = per_chunk_steps
        payload = await _analyze_research_design_single(
            text=text,
            dataset_meta=chunk_meta,
            current_protocol=current_protocol,
            preferences=preferences,
            constraints=chunk_constraints,
            role_models=role_models,
            chunk_info={"index": idx, "total": len(chunks)},
        )
        if not isinstance(payload, dict):
            continue
        usage_chunk = payload.pop("usage", None)
        if usage_chunk:
            usage_chunks.append({"chunk": idx, "usage": usage_chunk})
        payloads.append(payload)

    if not payloads:
        return await _analyze_research_design_single(
            text=text,
            dataset_meta=dataset_meta,
            current_protocol=current_protocol,
            preferences=preferences,
            constraints=constraints,
            role_models=role_models,
        )

    merged = _merge_planner_payloads(payloads)
    if prefs.get("return_usage") and usage_chunks:
        merged["usage"] = {"chunks": usage_chunks}
    return merged
