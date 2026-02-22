"""
Knowledge API endpoints for contextual statistical education.

Endpoints:
- GET /api/v2/knowledge/terms - List all terms
- GET /api/v2/knowledge/terms/{term} - Get term explanation
- GET /api/v2/knowledge/tests - List all tests
- GET /api/v2/knowledge/tests/{test_id} - Get test rationale
- GET /api/v2/knowledge/effect-size - Interpret effect size
- GET /api/v2/knowledge/power - Get power recommendation
- POST /api/v2/knowledge/upload - Upload knowledge file
- GET /api/v2/knowledge/library - List uploaded docs
- GET /api/v2/knowledge/catalog - List docs with keywords/topics
- GET /api/v2/knowledge/search - Search uploaded docs
- GET /api/v2/knowledge/doc/{id} - Get full document
- DELETE /api/v2/knowledge/doc/{id} - Remove document
"""

from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Form
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel

from app.modules.stat_knowledge import (
    get_explanation,
    get_test_rationale,
    get_effect_size_interpretation,
    get_power_recommendation,
    get_all_terms,
    get_all_tests
)
from app.modules.knowledge_store import add_document, list_documents, search_documents, get_document, delete_document, route_documents

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


class KnowledgeUploadResponse(BaseModel):
    id: str
    warnings: List[str] = []
    preview: Optional[str] = None
    text_chars: int = 0
    num_chunks: int = 0


class KnowledgeDocListResponse(BaseModel):
    docs: List[dict]


class KnowledgeSearchResponse(BaseModel):
    results: List[dict]


class KnowledgeCatalogResponse(BaseModel):
    docs: List[dict]


class KnowledgeRouteResponse(BaseModel):
    docs: List[dict]


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
        raise HTTPException(status_code=404, detail=f"Термин «{term}» не найден")
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
        raise HTTPException(status_code=404, detail=f"Тест «{test_id}» не найден")
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


@router.get("/manual")
async def get_user_manual(
    lang: str = Query("ru", pattern="^(ru|en)$")
):
    repo_root = Path(__file__).resolve().parents[3]
    file_name = "USER_MANUAL.md" if lang == "ru" else "USER_MANUAL_EN.md"
    manual_path = repo_root / "docs" / file_name
    if not manual_path.exists():
        if lang != "ru":
            manual_path = repo_root / "docs" / "USER_MANUAL.md"
        if not manual_path.exists():
            raise HTTPException(status_code=404, detail="Мануал не найден")
    return {"markdown": manual_path.read_text(encoding="utf-8")}


@router.post("/upload", response_model=KnowledgeUploadResponse)
async def upload_knowledge_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
):
    if not file:
        raise HTTPException(status_code=400, detail="Файл не передан")
    try:
        data = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Не удалось прочитать файл: {str(e)}")

    if data is None or len(data) == 0:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Файл слишком большой (лимит 25MB)")

    tag_list: Optional[List[str]] = None
    if tags:
        tag_list = [t.strip() for t in str(tags).split(",") if t.strip()]

    res = add_document(
        file_bytes=data,
        filename=str(file.filename or "document"),
        title=title,
        tags=tag_list,
    )
    return KnowledgeUploadResponse(**res)


@router.get("/library", response_model=KnowledgeDocListResponse)
async def list_knowledge_library():
    return KnowledgeDocListResponse(docs=list_documents())


@router.get("/catalog", response_model=KnowledgeCatalogResponse)
async def list_knowledge_catalog():
    docs = []
    for doc in list_documents():
        docs.append(
            {
                "id": doc.get("id"),
                "title": doc.get("title") or doc.get("filename"),
                "tags": doc.get("tags") or [],
                "keywords": doc.get("keywords") or [],
                "preview": doc.get("preview"),
                "source_type": doc.get("source_type"),
            }
        )
    return KnowledgeCatalogResponse(docs=docs)


@router.get("/route", response_model=KnowledgeRouteResponse)
async def route_knowledge_catalog(q: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20)):
    docs = route_documents(q, top_k=top_k)
    return KnowledgeRouteResponse(docs=docs)

@router.get("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(q: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20)):
    results = search_documents(q, top_k=top_k)
    return KnowledgeSearchResponse(results=results)


@router.get("/doc/{doc_id}")
async def get_knowledge_doc(doc_id: str):
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return doc


@router.delete("/doc/{doc_id}")
async def delete_knowledge_doc(doc_id: str):
    ok = delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return {"status": "deleted", "id": doc_id}
