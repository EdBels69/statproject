"""
nlq_router.py — Natural Language Query → Protocol → Execute pipeline.

Parses free-text research questions, selects the best domain template,
builds a protocol, and orchestrates execution. Falls back to generic
LLM-based planning when no template fits.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.modules.domain_templates import list_templates, build_protocol, get_template

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent Classification (keyword-based, fast, deterministic)
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "rct_two_arm": [
        "рки", "рандоми",  "clinical trial", "rct", "контроль",
        "плацебо", "placebo", "treatment arm", "две группы", "two arm",
        "двух групп", "лечение vs", "активный vs", "препарат",
    ],
    "before_after": [
        "до и после", "before after", "before and after", "pre-post",
        "paired", "парн", "до лечения", "после лечения", "динами",
        "изменени", "дельта", "до/после", "до-после",
    ],
    "cross_sectional": [
        "поперечн", "cross-sectional", "survey", "опрос",
        "наблюдатель", "observational", "связь между", "association",
        "аcсоциац", "корреляц", "correlation", "предиктор",
    ],
    "longitudinal": [
        "продольн", "longitudinal", "повторн", "repeated measure",
        "визит", "visit", "время", "time", "динамик",
        "mixed effect", "смешанн", "lmm", "временной",
    ],
    "responder_analysis": [
        "респондер", "responder", "ответивш", "response rate",
        "nnt", "порог ответа", "threshold", "enrichment",
        "responder rate",
    ],
}


def classify_intent(query: str) -> Tuple[Optional[str], float]:
    """
    Classify a free-text query into a template ID.

    Returns:
        (template_id, confidence) — template_id is None if no match.
        confidence is a float in [0, 1].
    """
    q = query.lower().strip()
    scores: Dict[str, int] = {}

    for template_id, keywords in _INTENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in q:
                score += 1
        if score > 0:
            scores[template_id] = score

    if not scores:
        return None, 0.0

    best_id = max(scores, key=scores.get)  # type: ignore[arg-type]
    best_score = scores[best_id]
    total_keywords = len(_INTENT_KEYWORDS[best_id])
    confidence = min(1.0, best_score / max(1, total_keywords / 2))

    return best_id, round(confidence, 2)


# ---------------------------------------------------------------------------
# Variable Extraction (heuristic from query + DataFrame columns)
# ---------------------------------------------------------------------------

def extract_variables(
    query: str,
    columns: List[str],
    template_id: str,
) -> Dict[str, Any]:
    """
    Attempt to extract variable assignments from the query text
    and available DataFrame columns.

    Returns a dict with template-appropriate keys.
    """
    q_lower = query.lower()
    variables: Dict[str, Any] = {}

    # Heuristic: find columns mentioned in the query
    mentioned = [c for c in columns if c.lower() in q_lower or c in query]

    # Group column detection
    group_hints = ["group", "группа", "arm", "treatment", "препарат", "cohort"]
    group_cols = [c for c in columns if any(h in c.lower() for h in group_hints)]

    # Outcome column detection
    outcome_hints = ["score", "балл", "значение", "value", "result", "outcome", "шкала"]
    outcome_cols = [c for c in columns if any(h in c.lower() for h in outcome_hints)]

    # Subject / ID column detection
    id_hints = ["id", "patient", "пациент", "subject", "субъект", "номер"]
    id_cols = [c for c in columns if any(h in c.lower() for h in id_hints)]

    # Time / visit column detection
    time_hints = ["time", "время", "visit", "визит", "v1", "v2", "v3"]
    time_cols = [c for c in columns if any(h in c.lower() for h in time_hints)]

    # Assign based on template type
    if template_id == "rct_two_arm":
        variables["group"] = group_cols[0] if group_cols else (mentioned[0] if mentioned else "")
        variables["outcome"] = outcome_cols[0] if outcome_cols else (mentioned[1] if len(mentioned) > 1 else "")
        secondary = [c for c in (outcome_cols or mentioned) if c != variables["outcome"]]
        variables["secondary_outcomes"] = secondary[:3]

    elif template_id == "before_after":
        candidates = time_cols or outcome_cols or mentioned
        variables["before"] = candidates[0] if len(candidates) >= 1 else ""
        variables["after"] = candidates[1] if len(candidates) >= 2 else ""
        variables["group"] = group_cols[0] if group_cols else None
        variables["subject"] = id_cols[0] if id_cols else None

    elif template_id == "cross_sectional":
        variables["outcome"] = outcome_cols[0] if outcome_cols else (mentioned[0] if mentioned else "")
        predictors = [c for c in columns if c != variables["outcome"] and c not in id_cols]
        variables["predictors"] = predictors[:5]
        variables["group"] = group_cols[0] if group_cols else None

    elif template_id == "longitudinal":
        variables["outcome_columns"] = time_cols or outcome_cols[:4]
        variables["group"] = group_cols[0] if group_cols else ""
        variables["subject"] = id_cols[0] if id_cols else ""
        variables["outcome"] = outcome_cols[0] if outcome_cols else ""

    elif template_id == "responder_analysis":
        variables["outcome_columns"] = time_cols or outcome_cols[:4]
        variables["group"] = group_cols[0] if group_cols else ""
        variables["subject"] = id_cols[0] if id_cols else None
        variables["response_threshold"] = 0.0

    return variables


# ---------------------------------------------------------------------------
# NLQ Pipeline
# ---------------------------------------------------------------------------

def nlq_to_protocol(
    query: str,
    columns: List[str],
    *,
    alpha: float = 0.05,
    min_confidence: float = 0.3,
) -> Dict[str, Any]:
    """
    Convert a natural language query into a protocol.

    Args:
        query: Free-text research question.
        columns: List of DataFrame column names.
        alpha: Significance level.
        min_confidence: Minimum confidence for template match.

    Returns:
        Dict with:
            - protocol: The built protocol dict (or None).
            - template_id: Matched template (or None).
            - confidence: Classification confidence.
            - variables: Extracted variable assignments.
            - fallback: True if no template matched (needs LLM planning).
    """
    template_id, confidence = classify_intent(query)

    if template_id is None or confidence < min_confidence:
        return {
            "protocol": None,
            "template_id": None,
            "confidence": confidence,
            "variables": {},
            "fallback": True,
            "message": "No domain template matched. Use LLM-based planning.",
        }

    variables = extract_variables(query, columns, template_id)
    protocol = build_protocol(template_id, variables=variables, alpha=alpha)

    return {
        "protocol": protocol,
        "template_id": template_id,
        "confidence": confidence,
        "variables": variables,
        "fallback": False,
        "message": f"Matched template: {template_id} (confidence={confidence}).",
    }
