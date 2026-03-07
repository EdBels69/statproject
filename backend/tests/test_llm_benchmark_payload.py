import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.api.v2 as v2_api


def test_normalize_llm_benchmark_auto_recommend_by_benchmark_score():
    payload = {
        "variants": [
            {
                "id": "gemini_single",
                "status": "ok",
                "quality_score": 84.0,
                "benchmark_score": 0.79,
                "elapsed_ms": 900,
            },
            {
                "id": "minimax_single",
                "status": "ok",
                "quality_score": 83.0,
                "benchmark_score": 0.92,
                "elapsed_ms": 1200,
            },
        ]
    }

    out = v2_api._normalize_llm_benchmark_payload(payload)
    assert isinstance(out, dict)
    assert out.get("recommended_id") == "minimax_single"
    assert out.get("recommendation_source") == "auto_metrics"
    rows = out.get("variants") or []
    flags = {str(row.get("id")): bool(row.get("recommended")) for row in rows if isinstance(row, dict)}
    assert flags.get("minimax_single") is True
    assert flags.get("gemini_single") is False


def test_normalize_llm_benchmark_penalizes_fallback_heavy_rows_without_benchmark_score():
    payload = {
        "variants": [
            {
                "id": "qwen_single",
                "status": "ok",
                "quality_score": 90.0,
                "fallback_used": True,
                "attempt_count": 4,
            },
            {
                "id": "glm5_single",
                "status": "ok",
                "quality_score": 88.0,
                "fallback_used": False,
                "attempt_count": 1,
            },
        ]
    }

    out = v2_api._normalize_llm_benchmark_payload(payload)
    assert isinstance(out, dict)
    assert out.get("recommended_id") == "glm5_single"
    assert out.get("recommendation_source") == "auto_metrics"


def test_normalize_llm_benchmark_extracts_recommended_models():
    payload = {
        "recommended_id": "routerai_combo",
        "variants": [
            {
                "id": "routerai_combo",
                "status": "ok",
                "recommended": True,
                "models": {
                    "planner": "minimax/minimax-m2.5",
                    "quality": "z-ai/glm-5",
                    "interpret": "qwen/qwen3.5-397b-a17b",
                    "report": "qwen/qwen3.5-397b-a17b",
                    "codegen": "deepseek/deepseek-chat-v3-0324:floor",
                },
            },
            {
                "id": "gemini_single",
                "status": "ok",
                "recommended": False,
            },
        ],
    }

    out = v2_api._normalize_llm_benchmark_payload(payload)
    assert isinstance(out, dict)
    assert out.get("recommended_id") == "routerai_combo"
    assert out.get("recommendation_source") == "input"
    recommended_models = out.get("recommended_models")
    assert isinstance(recommended_models, dict)
    assert recommended_models.get("planner") == "minimax/minimax-m2.5"
    assert recommended_models.get("quality") == "z-ai/glm-5"


def test_normalize_llm_benchmark_is_profile_aware_for_publication_vs_exploratory():
    base_variants = [
        {
            "id": "minimax_single",
            "status": "ok",
            "quality_score": 91.0,
            "elapsed_ms": 900,
            "token_total": 4200,
            "step_count": 10,
            "fallback_used": True,
            "attempt_count": 3,
        },
        {
            "id": "gemini_single",
            "status": "ok",
            "quality_score": 89.0,
            "elapsed_ms": 1200,
            "token_total": 4600,
            "step_count": 10,
            "fallback_used": False,
            "attempt_count": 1,
        },
    ]

    exploratory_payload = {
        "benchmark_context": {
            "analysis_mode": "exploratory",
            "validation_profile": "exploratory",
            "expected_step_count": 10,
        },
        "variants": base_variants,
    }
    publication_payload = {
        "benchmark_context": {
            "analysis_mode": "publication",
            "validation_profile": "publication",
            "expected_step_count": 10,
        },
        "variants": base_variants,
    }

    exploratory_out = v2_api._normalize_llm_benchmark_payload(exploratory_payload)
    publication_out = v2_api._normalize_llm_benchmark_payload(publication_payload)

    assert isinstance(exploratory_out, dict)
    assert isinstance(publication_out, dict)
    assert exploratory_out.get("recommended_id") == "minimax_single"
    assert publication_out.get("recommended_id") == "gemini_single"
    assert exploratory_out.get("benchmark_context", {}).get("validation_profile") == "exploratory"
    assert publication_out.get("benchmark_context", {}).get("validation_profile") == "publication"
