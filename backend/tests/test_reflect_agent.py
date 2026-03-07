"""Tests for ReflectAgent — multi-round result sanity checking."""
from __future__ import annotations

import pytest


class TestReflectAgent:

    def test_accept_clean_result(self):
        from app.copilot.reflect_agent import ReflectAgent, ReflectDecision

        agent = ReflectAgent()
        result = {
            "p_value": 0.032,
            "effect_size": 0.45,
            "effect_size_ci_lower": 0.1,
            "effect_size_ci_upper": 0.8,
            "sample_size": 50,
            "method_id": "t_test_ind",
        }
        ref = agent.reflect("step_1", result)

        assert ref.decision == ReflectDecision.ACCEPT
        assert ref.confidence > 0.9
        assert len(ref.issues) == 0

    def test_flag_suspiciously_small_p(self):
        from app.copilot.reflect_agent import ReflectAgent, ReflectDecision

        agent = ReflectAgent()
        result = {
            "p_value": 0.00001,
            "effect_size": 1.5,
            "sample_size": 5,
            "method_id": "t_test_ind",
        }
        ref = agent.reflect("step_1", result)

        assert ref.decision in (ReflectDecision.RETRY, ReflectDecision.FLAG)
        assert any("suspiciously" in i.lower() or "small p" in i.lower() for i in ref.issues)

    def test_retry_p_value_out_of_range(self):
        from app.copilot.reflect_agent import ReflectAgent, ReflectDecision

        agent = ReflectAgent()
        result = {"p_value": -0.5, "method_id": "t_test_ind"}
        ref = agent.reflect("step_1", result)

        assert ref.decision == ReflectDecision.RETRY
        assert any("out of range" in i.lower() for i in ref.issues)

    def test_ci_logic_violated(self):
        from app.copilot.reflect_agent import ReflectAgent, ReflectDecision

        agent = ReflectAgent()
        result = {
            "p_value": 0.05,
            "effect_size": 0.5,
            "effect_size_ci_lower": 0.8,
            "effect_size_ci_upper": 0.2,  # lower > upper
        }
        ref = agent.reflect("step_1", result)

        assert ref.decision in (ReflectDecision.RETRY, ReflectDecision.FLAG)
        assert any("ci" in i.lower() for i in ref.issues)

    def test_effect_outside_ci(self):
        from app.copilot.reflect_agent import ReflectAgent, ReflectDecision

        agent = ReflectAgent()
        result = {
            "p_value": 0.05,
            "effect_size": 2.0,  # outside CI
            "effect_size_ci_lower": 0.1,
            "effect_size_ci_upper": 0.5,
        }
        ref = agent.reflect("step_1", result)

        assert any("outside ci" in i.lower() for i in ref.issues)

    def test_reflect_run_overall(self):
        from app.copilot.reflect_agent import ReflectAgent

        agent = ReflectAgent()
        results = {
            "step_1": {"p_value": 0.03, "effect_size": 0.4, "sample_size": 50},
            "step_2": {"p_value": 0.8, "effect_size": 0.05, "sample_size": 100},
            "step_3": {"p_value": -0.5},  # invalid
        }
        summary = agent.reflect_run(results)

        assert summary["schema"] == "clinimetria.reflection"
        assert summary["total_steps"] == 3
        assert summary["overall_decision"] in ("needs_revision", "accepted_with_flags")
        assert "step_3" in summary["steps"]

    def test_sample_size_warning(self):
        from app.copilot.reflect_agent import ReflectAgent, ReflectDecision

        agent = ReflectAgent()
        result = {
            "p_value": 0.04,
            "effect_size": 0.3,
            "sample_size": 8,
            "method_id": "anova",
        }
        ref = agent.reflect("step_1", result)

        assert any("anova" in i.lower() or "power" in i.lower() for i in ref.issues)

    def test_history_tracking(self):
        from app.copilot.reflect_agent import ReflectAgent

        agent = ReflectAgent()
        agent.reflect("step_1", {"p_value": 0.05})
        agent.reflect("step_2", {"p_value": 0.01})

        assert len(agent.history) == 2
        assert agent.history[0]["metadata"]["step_id"] == "step_1"
        assert agent.history[1]["metadata"]["step_id"] == "step_2"
