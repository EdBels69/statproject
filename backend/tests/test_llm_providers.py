import asyncio

import pandas as pd

from app.llm import get_ai_conclusion, scan_data_quality
from app.schemas.analysis import AnalysisResult, StatMethod
from app.core.config import settings


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _DummyAsyncClient:
    def __init__(self, *, timeout: float, on_post):
        self._timeout = timeout
        self._on_post = on_post

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        return self._on_post(url, json, headers)


def test_get_ai_conclusion_uses_openrouter_when_model_is_openrouter(monkeypatch):
    captured = {}

    def on_post(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return _DummyResponse({"choices": [{"message": {"content": "ok"}}]})

    import app.llm as llm_mod

    monkeypatch.setattr(settings, "GLM_ENABLED", True)
    monkeypatch.setattr(settings, "GLM_MODEL", "qwen/qwen3-coder:free")
    monkeypatch.setattr(settings, "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "GLM_API_URL", "https://api.z.ai/api/coding/paas/v4")
    monkeypatch.setattr(settings, "GLM_API_KEY", "glm-key")
    monkeypatch.setattr(
        llm_mod.httpx,
        "AsyncClient",
        lambda timeout: _DummyAsyncClient(timeout=timeout, on_post=on_post),
    )

    res = AnalysisResult(
        method=StatMethod(
            id="t_test",
            name="T-Test",
            description="",
            type="parametric",
            min_groups=2,
            max_groups=2,
        ),
        p_value=0.01,
        significant=True,
        conclusion="fallback",
        plot_stats={"A": {"mean": 1.0, "median": 1.0}},
    )

    out = asyncio.run(get_ai_conclusion(res))
    assert out == "ok"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer openrouter-key"
    assert captured["payload"]["model"] == "qwen/qwen3-coder:free"


def test_get_ai_conclusion_uses_glm_when_model_is_not_openrouter(monkeypatch):
    captured = {}

    def on_post(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return _DummyResponse({"choices": [{"message": {"content": "ok"}}]})

    import app.llm as llm_mod

    monkeypatch.setattr(settings, "GLM_ENABLED", True)
    monkeypatch.setattr(settings, "GLM_MODEL", "glm-4.7")
    monkeypatch.setattr(settings, "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "GLM_API_URL", "https://api.z.ai/api/coding/paas/v4")
    monkeypatch.setattr(settings, "GLM_API_KEY", "glm-key")
    monkeypatch.setattr(
        llm_mod.httpx,
        "AsyncClient",
        lambda timeout: _DummyAsyncClient(timeout=timeout, on_post=on_post),
    )

    res = AnalysisResult(
        method=StatMethod(
            id="t_test",
            name="T-Test",
            description="",
            type="parametric",
            min_groups=2,
            max_groups=2,
        ),
        p_value=0.01,
        significant=True,
        conclusion="fallback",
    )

    out = asyncio.run(get_ai_conclusion(res))
    assert out == "ok"
    assert captured["url"] == "https://api.z.ai/api/coding/paas/v4"
    assert captured["headers"]["Authorization"] == "Bearer glm-key"
    assert captured["payload"]["model"] == "glm-4.7"


def test_scan_data_quality_accepts_dataframe(monkeypatch):
    captured = {}

    def on_post(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return _DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": '[{"column":"email","issue_type":"pii","severity":"high","description":"Looks like email","suggestion":"Remove"}]'
                        }
                    }
                ]
            }
        )

    import app.llm as llm_mod

    monkeypatch.setattr(settings, "GLM_ENABLED", True)
    monkeypatch.setattr(settings, "GLM_MODEL", "deepseek/deepseek-tng-r1t2-chimera:free")
    monkeypatch.setattr(settings, "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(
        llm_mod.httpx,
        "AsyncClient",
        lambda timeout: _DummyAsyncClient(timeout=timeout, on_post=on_post),
    )

    df = pd.DataFrame({"email": ["a@b.com", "c@d.com"], "age": [10, 20]})
    out = asyncio.run(scan_data_quality(df))
    assert isinstance(out, list)
    assert out and out[0]["issue_type"] == "pii"
    assert captured["payload"]["model"] == "deepseek/deepseek-tng-r1t2-chimera:free"
