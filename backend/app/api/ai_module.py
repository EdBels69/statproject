import asyncio
import json
import math
import os
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.datasets import DATA_DIR
from app.core.logging import logger
from app.llm import analyze_research_design
from app.llm.smart_sampling import build_smart_sample
from app.modules.parsers import get_dataframe
from app.modules.ai_context import build_ai_context, safe_plan_constraints, enforce_protocol_constraints
from app.modules.legacy_telemetry import record_legacy_hit


AI_MODULE_DATE = "2026-01-17"


router = APIRouter()


def convert_numpy_to_native(obj: Any) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: convert_numpy_to_native(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [convert_numpy_to_native(item) for item in obj]
    return obj


async def load_dataset_async(dataset_id: str) -> pd.DataFrame:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_dataframe, dataset_id, DATA_DIR)


class AISuggestTestsRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset identifier")
    protocol: List[Dict[str, Any]] = Field(..., description="Current protocol for context")


@router.post("/ai/suggest-tests", response_model=Dict[str, Any])
async def ai_suggest_tests(request: AISuggestTestsRequest):
    try:
        df = await load_dataset_async(request.dataset_id)

        recommendations: List[Dict[str, Any]] = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

        potential_time_cols = [col for col in numeric_cols if "time" in col.lower() or "date" in col.lower()]
        potential_group_cols = [col for col in categorical_cols if df[col].nunique() <= 10]
        potential_subject_cols = [
            col for col in categorical_cols if df[col].nunique() > 10 and df[col].nunique() <= 100
        ]

        if potential_time_cols and potential_group_cols and potential_subject_cols:
            recommendations.append(
                {
                    "test": {
                        "id": "mixed_effects",
                        "name": "Mixed Effects (LMM)",
                        "config": {
                            "outcome": numeric_cols[0] if numeric_cols else "Select outcome",
                            "time": potential_time_cols[0],
                            "group": potential_group_cols[0],
                            "subject": potential_subject_cols[0],
                            "random_slope": False,
                        },
                    },
                    "reason": "Обнаружена структура продольных данных. Mixed Effects Model позволит учесть повторные измерения и индивидуальную вариабельность.",
                    "confidence": 0.85,
                }
            )

        if len(numeric_cols) >= 3:
            recommendations.append(
                {
                    "test": {
                        "id": "clustered_correlation",
                        "name": "Clustered Correlation",
                        "config": {
                            "variables": numeric_cols[:8],
                            "method": "pearson",
                            "linkage_method": "ward",
                        },
                    },
                    "reason": f"Обнаружено {len(numeric_cols)} числовых переменных. Кластерная корреляция выявит группы связанных переменных.",
                    "confidence": 0.90,
                }
            )

        if potential_group_cols and numeric_cols:
            recommendations.append(
                {
                    "test": {
                        "id": "mann_whitney",
                        "name": "Mann-Whitney U",
                        "config": {
                            "outcome": numeric_cols[0],
                            "group": potential_group_cols[0],
                        },
                    },
                    "reason": "Сравнение групп с непараметрическим тестом подходит для данных с возможными выбросами.",
                    "confidence": 0.75,
                }
            )

        current_methods = {test.get("method") for test in request.protocol}
        recommendations = [rec for rec in recommendations if rec.get("test", {}).get("id") not in current_methods]

        return {"status": "completed", "recommendations": recommendations}
    except Exception as e:
        logger.error(f"AI suggestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось получить рекомендации ИИ: {str(e)}")


class AIAnalyzeDesignRequest(BaseModel):
    dataset_id: str = Field(..., description="Dataset identifier")
    text: str = Field(..., description="Research design description")
    protocol: Optional[List[Dict[str, Any]]] = Field(None, description="Current protocol for context")
    preferences: Optional[Dict[str, Any]] = Field(None, description="Global preferences")


def _normalize_ai_protocol_item(item: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    raw_method = item.get("method") or item.get("test") or item.get("type")
    method = str(raw_method or "").strip().lower()
    if not method:
        return None
    if method == "mixed_model":
        method = "mixed_effects"

    raw_config = item.get("config")
    config = raw_config if isinstance(raw_config, dict) else {}
    name = str(item.get("name") or "").strip() or None
    step_id = str(item.get("id") or f"ai_{idx + 1}").strip()
    if not name:
        name = method.replace("_", " ").title()

    if "outcome" not in config and "target" in config:
        config = {**config, "outcome": config.get("target")}
    if "target" not in config and "outcome" in config and method == "descriptive_compare":
        config = {**config, "target": config.get("outcome")}
    if "group" not in config and "predictor" in config:
        config = {**config, "group": config.get("predictor")}

    return {"id": step_id, "name": name, "method": method, "config": config}


@router.post("/ai/analyze-design", response_model=Dict[str, Any])
async def ai_analyze_design(request: AIAnalyzeDesignRequest):
    logger.warning(
        "Deprecated endpoint hit: /api/v1/v2/ai/analyze-design. Use /api/v1/v2/analysis/plan for canonical flow."
    )
    record_legacy_hit("/api/v1/v2/ai/analyze-design")
    try:
        df = await load_dataset_async(request.dataset_id)
        dataset_meta = build_ai_context(dataset_id=request.dataset_id, base_dir=DATA_DIR, df=df)
        constraints = safe_plan_constraints(request.preferences)

        prefs = request.preferences if isinstance(request.preferences, dict) else {}
        role_models = prefs.get("llm_models") if isinstance(prefs.get("llm_models"), dict) else None
        use_sampling = bool(prefs.get("smart_sampling") or prefs.get("use_smart_sampling"))
        sample_mode = str(prefs.get("smart_sampling_mode") or "").strip().lower()
        if not sample_mode:
            sample_mode = "masked" if use_sampling else "off"
        if prefs.get("no_raw_sample") is True:
            sample_mode = "off"

        if sample_mode not in {"off", "none"}:
            max_rows = prefs.get("smart_sample_rows") or prefs.get("sample_rows") or 40
            max_cols = prefs.get("smart_sample_cols") or prefs.get("sample_cols") or 18
            redact_mode = "pii"
            if sample_mode in {"raw", "unsafe"}:
                redact_mode = "none"
            elif sample_mode in {"strict", "full"}:
                redact_mode = "strict"
            try:
                sample = build_smart_sample(
                    df,
                    max_rows=int(max_rows),
                    max_cols=int(max_cols),
                    redact_mode=redact_mode,
                )
                dataset_meta["sample_rows"] = sample.get("rows") or []
                dataset_meta["sample_info"] = {
                    "strategy": sample.get("strategy"),
                    "row_count": sample.get("row_count"),
                    "columns": sample.get("columns"),
                    "redact_mode": redact_mode,
                }
            except Exception:
                pass
        else:
            dataset_meta["sample_rows"] = []
            dataset_meta["sample_info"] = {"strategy": "disabled", "row_count": 0, "columns": []}

        ai_payload = await analyze_research_design(
            text=request.text,
            dataset_meta=dataset_meta,
            current_protocol=request.protocol or [],
            preferences=prefs,
            constraints=constraints,
            role_models=role_models,
        )

        if isinstance(ai_payload, dict):
            raw_steps = ai_payload.get("protocol") or ai_payload.get("steps")
            steps_in = raw_steps if isinstance(raw_steps, list) else []
            protocol_out: List[Dict[str, Any]] = []
            for i, step in enumerate(steps_in[:40]):
                norm = _normalize_ai_protocol_item(step, i)
                if norm:
                    protocol_out.append(norm)

            globals_in = ai_payload.get("globals")
            globals_out = globals_in if isinstance(globals_in, dict) else {}
            pref = request.preferences if isinstance(request.preferences, dict) else {}
            if "alternative" not in globals_out and "alternative" in pref:
                globals_out["alternative"] = pref.get("alternative")
            if "post_hoc" not in globals_out and "post_hoc" in pref:
                globals_out["post_hoc"] = pref.get("post_hoc")
            if "post_hoc_correction" not in globals_out and "post_hoc_correction" in pref:
                globals_out["post_hoc_correction"] = pref.get("post_hoc_correction")
            if role_models:
                globals_out["llm_models"] = role_models

            protocol_name = str(ai_payload.get("protocol_name") or "Протокол").strip() or "Протокол"
            notes = ai_payload.get("notes")
            notes_out = notes if isinstance(notes, list) else []

            if protocol_out:
                protocol_out = enforce_protocol_constraints(protocol_out, constraints)
                return {
                    "status": "completed",
                    "protocol_name": protocol_name,
                    "globals": globals_out,
                    "protocol": protocol_out,
                    "notes": notes_out,
                }

        numeric_cols = dataset_meta.get("numeric_cols") or []
        categorical_cols = dataset_meta.get("categorical_cols") or []

        proto: List[Dict[str, Any]] = []
        if numeric_cols and categorical_cols:
            proto.append(
                {
                    "id": "step_1",
                    "name": "Описательная статистика",
                    "method": "descriptive_compare",
                    "config": {"target": numeric_cols[0], "group": categorical_cols[0]},
                }
            )
            proto.append(
                {
                    "id": "step_2",
                    "name": "Сравнение групп (auto)",
                    "method": "auto",
                    "config": {"outcome": numeric_cols[0], "group": categorical_cols[0]},
                }
            )
        elif len(numeric_cols) >= 2:
            proto.append(
                {
                    "id": "step_1",
                    "name": "Корреляция",
                    "method": "spearman",
                    "config": {"outcome": numeric_cols[0], "group": numeric_cols[1]},
                }
            )

        return {
            "status": "partial",
            "protocol_name": "Протокол",
            "globals": request.preferences or {},
            "protocol": proto,
            "notes": ["ИИ недоступен или не вернул валидный JSON. Сформирован черновик по структуре датасета."],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analyze design failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Не удалось разобрать дизайн исследования: {str(e)}")
