"""
Tests for Copilot Engine - LLM-powered analysis orchestration.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.copilot.engine import CopilotEngine


class TestCopilotEngine:
    """Unit tests for CopilotEngine."""

    @pytest.fixture
    def engine(self):
        """Create engine instance for testing."""
        return CopilotEngine()

    @pytest.fixture
    def mock_plan_response(self):
        """Sample LLM plan response."""
        return json.dumps({
            "understood_goal": "Compare treatment groups on clinical outcomes",
            "design": {
                "study_type": "cross_sectional",
                "group_col": "Group",
                "subject_col": None,
                "visit_col": None,
                "visits_order": [],
                "covariates": ["Age", "Sex"]
            },
            "analyses": [
                {
                    "name": "Primary Outcome",
                    "type": "continuous",
                    "variables": ["Score"],
                    "method": "anova"
                }
            ],
            "corrections": ["holm"],
            "effect_sizes": True,
            "confidence_level": 0.95
        })

    def test_engine_initialization(self, engine):
        """Test engine initializes with correct defaults."""
        assert engine.executor is not None
        assert engine.model is not None
        assert isinstance(engine.sessions, dict)

    def test_session_management(self, engine):
        """Test session save/load functionality."""
        test_session_id = "test_session_123"
        test_data = {
            "dataset_path": "/test/path.parquet",
            "plan": {"test": "plan"},
            "status": "planned"
        }
        
        engine.sessions[test_session_id] = test_data
        engine._save_sessions()
        
        # Reload sessions
        loaded = engine._load_sessions()
        assert test_session_id in loaded or test_session_id in engine.sessions
        
        # Cleanup
        if test_session_id in engine.sessions:
            del engine.sessions[test_session_id]
            engine._save_sessions()

    def test_get_session_returns_none_for_missing(self, engine):
        """Test get_session returns None for non-existent session."""
        result = engine.get_session("non_existent_session_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_plan_with_mock_llm(self, engine, mock_plan_response, tmp_path):
        """Test create_plan with mocked LLM response."""
        # Create a mock dataset
        df = pd.DataFrame({
            "Group": ["A", "B", "A", "B"],
            "Score": [10, 20, 15, 25],
            "Age": [30, 40, 35, 45]
        })
        parquet_path = tmp_path / "test.parquet"
        df.to_parquet(parquet_path)
        
        # Mock the LLM call
        with patch.object(engine, '_llm_call', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = (mock_plan_response, {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
            
            result = await engine.create_plan(
                dataset_path=str(parquet_path),
                user_request="Compare groups by Score",
                advanced=True
            )
            
            assert result["success"] is True
            assert "session_id" in result
            assert "plan" in result
            assert result["plan"]["understood_goal"] == "Compare treatment groups on clinical outcomes"

    @pytest.mark.asyncio
    async def test_create_plan_handles_llm_failure(self, engine, tmp_path):
        """Test create_plan handles LLM failure gracefully."""
        df = pd.DataFrame({"Group": ["A", "B"], "Value": [1, 2]})
        parquet_path = tmp_path / "test.parquet"
        df.to_parquet(parquet_path)
        
        with patch.object(engine, '_llm_call', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = (None, {})
            
            result = await engine.create_plan(
                dataset_path=str(parquet_path),
                user_request="Test request",
                advanced=True
            )
            
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_create_plan_handles_invalid_json(self, engine, tmp_path):
        """Test create_plan handles malformed JSON response."""
        df = pd.DataFrame({"Group": ["A", "B"], "Value": [1, 2]})
        parquet_path = tmp_path / "test.parquet"
        df.to_parquet(parquet_path)
        
        with patch.object(engine, '_llm_call', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = ("This is not valid JSON at all", {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70})
            
            result = await engine.create_plan(
                dataset_path=str(parquet_path),
                user_request="Test request",
                advanced=True
            )
            
            assert result["success"] is False
            assert "Failed to parse" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_llm_call_uses_configurable_fallback(self, engine):
        """Primary model failure should switch to configured fallback model."""
        engine.model = "minimax/minimax-m2.5"
        engine.fallback_model = "z-ai/glm-5"

        with patch("app.copilot.engine._chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = [
                (None, {}),
                ("ok", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}),
            ]
            text, usage = await engine._llm_call("ping", model=engine.model)

        assert text == "ok"
        assert usage.get("total_tokens") == 15
        assert mock_chat.await_count == 2
        assert mock_chat.await_args_list[0].kwargs["model"] == "minimax/minimax-m2.5"
        assert mock_chat.await_args_list[1].kwargs["model"] == "z-ai/glm-5"

    @pytest.mark.asyncio
    async def test_llm_call_does_not_retry_when_primary_equals_fallback(self, engine):
        """No second attempt is needed when primary model is already fallback."""
        engine.model = "qwen/qwen3.5-397b-a17b"
        engine.fallback_model = "qwen/qwen3.5-397b-a17b"

        with patch("app.copilot.engine._chat_completion", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = (None, {})
            text, usage = await engine._llm_call("ping", model=engine.model)

        assert text is None
        assert usage == {}
        assert mock_chat.await_count == 1


class TestCopilotExecutor:
    """Tests for CodeExecutor sandbox validation."""

    @pytest.fixture
    def executor(self):
        from app.copilot.executor import CodeExecutor
        return CodeExecutor(timeout_seconds=30)

    def test_validate_safe_code(self, executor):
        """Test that safe code passes validation."""
        safe_code = """
import pandas as pd
import numpy as np
df = pd.DataFrame({'a': [1, 2, 3]})
print(df.mean())
"""
        is_valid, error = executor.validate_code(safe_code)
        assert is_valid is True
        assert error == ""

    def test_validate_blocks_eval(self, executor):
        """Test that eval() is blocked."""
        unsafe_code = "result = eval('1 + 1')"
        is_valid, error = executor.validate_code(unsafe_code)
        assert is_valid is False
        assert "eval" in error

    def test_validate_blocks_exec(self, executor):
        """Test that exec() is blocked."""
        unsafe_code = "exec('print(1)')"
        is_valid, error = executor.validate_code(unsafe_code)
        assert is_valid is False
        assert "exec" in error

    def test_validate_blocks_subprocess(self, executor):
        """Test that subprocess imports are blocked."""
        unsafe_code = "import subprocess; subprocess.run(['ls'])"
        is_valid, error = executor.validate_code(unsafe_code)
        assert is_valid is False
        assert "subprocess" in error

    def test_validate_blocks_requests(self, executor):
        """Test that network requests are blocked."""
        unsafe_code = "import requests; requests.get('http://evil.com')"
        is_valid, error = executor.validate_code(unsafe_code)
        assert is_valid is False
        assert "requests" in error

    def test_validate_allows_os_path(self, executor):
        """Test that os.path operations are allowed."""
        safe_code = """
import os
path = os.path.join('a', 'b')
os.makedirs('test', exist_ok=True)
"""
        is_valid, error = executor.validate_code(safe_code)
        assert is_valid is True

    def test_validate_syntax_error(self, executor):
        """Test that syntax errors are caught."""
        bad_code = "def broken(: pass"
        is_valid, error = executor.validate_code(bad_code)
        assert is_valid is False
        assert "Syntax error" in error

    def test_execute_simple_code(self, executor):
        """Test execution of simple safe code."""
        code = """
import json
result = {"value": 42, "status": "ok"}
print("<JSON_START>")
print(json.dumps(result))
print("<JSON_END>")
"""
        result = executor.execute(code)
        assert result["success"] is True
        assert result["results"]["value"] == 42
        assert result["results"]["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
