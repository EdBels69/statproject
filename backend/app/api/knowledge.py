"""
Knowledge API endpoints for contextual statistical education.

Endpoints:
- GET /api/v2/knowledge/terms - List all terms
- GET /api/v2/knowledge/terms/{term} - Get term explanation
- GET /api/v2/knowledge/tests - List all tests
- GET /api/v2/knowledge/tests/{test_id} - Get test rationale
- GET /api/v2/knowledge/effect-size - Interpret effect size
- GET /api/v2/knowledge/power - Get power recommendation
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.modules.stat_knowledge import (
    get_explanation,
    get_test_rationale,
    get_effect_size_interpretation,
    get_power_recommendation,
    get_all_terms,
    get_all_tests
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


class TermExplanation(BaseModel):
    term: str
    term_ru: str
    definition: str
    common_mistakes: list
    what_to_check: list
    emoji: str


class TestRationale(BaseModel):
    test_id: str
    name: str
    name_ru: str
    when_to_use: list
    why_it_works: str
    assumptions: list
    alternatives: dict
    effect_size: Optional[str]
    emoji: str


@router.get("/terms")
async def list_terms():
    """Get list of all available statistical terms."""
    return {"terms": get_all_terms()}


@router.get("/terms/{term}")
async def get_term_explanation(
    term: str,
    level: str = Query("junior", pattern="^(junior|mid|senior)$")
):
    """
    Get explanation for a statistical term.
    
    Args:
        term: Term key (e.g., "p_value", "effect_size", "power")
        level: Explanation depth - "junior", "mid", or "senior"
    """
    explanation = get_explanation(term, level)
    if not explanation:
        raise HTTPException(status_code=404, detail=f"Term '{term}' not found")
    return explanation


@router.get("/tests")
async def list_tests():
    """Get list of all available statistical tests with info."""
    return {"tests": get_all_tests()}


@router.get("/tests/{test_id}")
async def get_test_info(
    test_id: str,
    level: str = Query("junior", pattern="^(junior|mid|senior)$"),
    shapiro_p: Optional[float] = None,
    levene_p: Optional[float] = None
):
    """
    Get rationale for why a test is appropriate.
    
    Args:
        test_id: Test identifier (e.g., "t_test_ind", "anova", "mann_whitney")
        level: Explanation depth
        shapiro_p: Optional Shapiro-Wilk p-value for normality check
        levene_p: Optional Levene's test p-value for homogeneity check
    """
    data_profile = {}
    if shapiro_p is not None:
        data_profile["shapiro_p"] = shapiro_p
    if levene_p is not None:
        data_profile["levene_p"] = levene_p
    
    rationale = get_test_rationale(test_id, data_profile or None, level)
    if not rationale:
        raise HTTPException(status_code=404, detail=f"Test '{test_id}' not found")
    return rationale


@router.get("/effect-size")
async def interpret_effect_size(
    type: str = Query(..., description="Effect size type: cohens_d, eta_squared, r"),
    value: float = Query(..., description="Effect size value")
):
    """
    Get interpretation of an effect size value.
    
    Args:
        type: Effect size type (cohens_d, partial_eta_squared, r, etc.)
        value: Numeric effect size value
    """
    interpretation = get_effect_size_interpretation(type, value)
    return interpretation


@router.get("/power")
async def get_power_info(
    power: float = Query(..., ge=0, le=1, description="Statistical power (0-1)")
):
    """
    Get recommendation based on statistical power.
    
    Args:
        power: Power value between 0 and 1
    """
    recommendation = get_power_recommendation(power)
    return recommendation
