import asyncio
import json

import app.llm as llm


def test_parse_json_response_repairs_missing_property_comma():
    raw = """
    {
      "status": "completed",
      "protocol": [{"id": "step_1", "name": "S1", "method": "auto", "config": {}}]
      "notes": ["ok"]
    }
    """

    parsed = llm._parse_json_response(raw)
    assert isinstance(parsed, dict)
    assert parsed.get("status") == "completed"
    assert parsed.get("notes") == ["ok"]


def test_parse_json_response_accepts_single_quotes_and_trailing_commas():
    raw = """
    ```json
    {'status': 'completed', 'protocol': [], 'notes': ['ok'],}
    ```
    """

    parsed = llm._parse_json_response(raw)
    assert isinstance(parsed, dict)
    assert parsed.get("status") == "completed"
    assert parsed.get("notes") == ["ok"]


def test_analyze_research_design_single_recovers_without_extra_llm_retry(monkeypatch):
    calls = []

    async def fake_chat_completion(*, model, prompt, temperature, max_tokens, timeout_s, response_format=None):
        calls.append(
            {
                "model": model,
                "response_format": response_format,
            }
        )
        payload = """
        {
          "status": "completed",
          "protocol_name": "json_recovery",
          "globals": {"analysis_mode": "focused"},
          "protocol": [
            {
              "id": "step_1",
              "name": "Compare outcome by group",
              "method": "descriptive_compare",
              "config": {"outcome": "outcome", "group": "group"}
            }
          ]
          "notes": ["Recovered with local parser"]
        }
        """
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "model_used": model,
        }
        return payload, usage

    monkeypatch.setattr(llm, "_chat_completion", fake_chat_completion)

    result = asyncio.run(
        llm._analyze_research_design_single(
            text="Compare outcome by group",
            dataset_meta={
                "summary": {"rows": 20},
                "columns": [
                    {"name": "group", "type": "categorical", "missing": 0},
                    {"name": "outcome", "type": "float", "missing": 0},
                ],
            },
            current_protocol=[],
            preferences={"return_usage": True},
            constraints={"max_steps": 5},
            role_models=None,
        )
    )

    assert isinstance(result, dict)
    assert result.get("status") == "completed"
    assert isinstance(result.get("protocol"), list) and len(result["protocol"]) == 1
    assert result.get("notes") == ["Recovered with local parser"]
    assert isinstance(result.get("usage"), dict)
    assert len(calls) == 1


def test_analyze_research_design_single_uses_json_fix_when_primary_unparseable(monkeypatch):
    calls = []
    monkeypatch.setenv("CLINIMETRIA_MODEL_JSON_FIX", "json-fix-model")

    async def fake_chat_completion(*, model, prompt, temperature, max_tokens, timeout_s, response_format=None):
        calls.append(str(model))
        if str(model) == "json-fix-model":
            payload = {
                "status": "completed",
                "protocol_name": "json_fix_recovery",
                "globals": {"analysis_mode": "focused"},
                "protocol": [
                    {
                        "id": "step_1",
                        "name": "Compare outcome by group",
                        "method": "descriptive_compare",
                        "config": {"outcome": "outcome", "group": "group"},
                    }
                ],
                "notes": ["Recovered by json_fix"],
            }
            return json.dumps(payload, ensure_ascii=False), {"total_tokens": 10, "model_used": model}

        broken = "status: completed protocol: ["
        return broken, {"total_tokens": 5, "model_used": model}

    monkeypatch.setattr(llm, "_chat_completion", fake_chat_completion)

    result = asyncio.run(
        llm._analyze_research_design_single(
            text="Compare outcome by group",
            dataset_meta={
                "summary": {"rows": 20},
                "columns": [
                    {"name": "group", "type": "categorical", "missing": 0},
                    {"name": "outcome", "type": "float", "missing": 0},
                ],
            },
            current_protocol=[],
            preferences={"return_usage": True},
            constraints={"max_steps": 5},
            role_models={"planner": "planner-model"},
        )
    )

    assert isinstance(result, dict)
    assert result.get("status") == "completed"
    assert result.get("notes") == ["Recovered by json_fix"]
    assert isinstance(result.get("usage"), dict)
    assert "planner-model" in calls
    assert "json-fix-model" in calls
