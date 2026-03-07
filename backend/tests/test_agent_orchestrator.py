import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.copilot.orchestrator import AgentDecision, AgentOrchestrator
from app.core.run_state_machine import REQUIRED_ARTIFACTS, RunState


def _full_artifact_index() -> dict:
    out = {}
    for required in REQUIRED_ARTIFACTS.values():
        for key in required:
            out[str(key)] = f"artifacts/{key}.json"
    return out


def test_agent_orchestrator_happy_path_reaches_release():
    orchestrator = AgentOrchestrator(
        initial_state=RunState.INGEST,
        max_rounds=20,
        artifact_index=_full_artifact_index(),
    )

    result = orchestrator.run(until_state=RunState.RELEASE)

    assert result["status"] == "completed"
    assert result["state"] == RunState.RELEASE.value
    assert len(result["transitions"]) == 9
    assert result["rounds_executed"] <= 10


def test_agent_orchestrator_supports_retry_before_advance():
    calls = {"ingest": 0}
    artifacts = _full_artifact_index()
    artifacts.pop("source_raw", None)
    artifacts.pop("source_meta", None)

    def ingest_handler(state, artifact_index, round_no):
        assert state == RunState.INGEST
        calls["ingest"] += 1
        if calls["ingest"] == 1:
            return AgentDecision.retry(reason="upload pending")
        return AgentDecision.advance(
            target_state=RunState.PROFILE,
            reason="upload ready",
            artifact_updates={
                "source_raw": "source/original.raw",
                "source_meta": "source/meta.json",
            },
        )

    orchestrator = AgentOrchestrator(
        initial_state=RunState.INGEST,
        max_rounds=20,
        artifact_index=artifacts,
        role_handlers={"ingest": ingest_handler},
    )

    result = orchestrator.run(until_state=RunState.RELEASE)

    assert result["status"] == "completed"
    assert result["events"][0]["action"] == "retry"
    assert result["events"][0]["state"] == RunState.INGEST.value
    assert any(
        event.get("state") == RunState.INGEST.value
        and event.get("action") == "advance"
        and event.get("transition_applied") is True
        for event in result["events"]
    )


def test_agent_orchestrator_supports_reject_loop():
    calls = {"verify": 0}

    def verify_handler(state, artifact_index, round_no):
        assert state == RunState.VERIFY
        calls["verify"] += 1
        if calls["verify"] == 1:
            return AgentDecision.reject(
                target_state=RunState.COMPILE,
                reason="verification drift detected",
            )
        return AgentDecision.advance(
            target_state=RunState.REPORT,
            reason="verification passed after rerun",
        )

    orchestrator = AgentOrchestrator(
        initial_state=RunState.INGEST,
        max_rounds=25,
        artifact_index=_full_artifact_index(),
        role_handlers={"verifier": verify_handler},
    )

    result = orchestrator.run(until_state=RunState.RELEASE)

    assert result["status"] == "completed"
    assert any(
        event.get("state") == RunState.VERIFY.value and event.get("action") == "reject"
        for event in result["events"]
    )
    assert any(
        transition.get("from") == RunState.VERIFY.value and transition.get("to") == RunState.COMPILE.value
        for transition in result["transitions"]
    )


def test_agent_orchestrator_forbidden_reject_raises():
    def ingest_handler(state, artifact_index, round_no):
        return AgentDecision.reject(
            target_state=RunState.EXECUTE,
            reason="invalid jump for test",
        )

    orchestrator = AgentOrchestrator(
        initial_state=RunState.INGEST,
        max_rounds=5,
        artifact_index=_full_artifact_index(),
        role_handlers={"ingestor": ingest_handler},
    )

    with pytest.raises(ValueError, match="Forbidden transition"):
        orchestrator.step()


def test_agent_orchestrator_reflection_switches_method_strategy():
    class _ReflectStub:
        def __init__(self):
            self.calls = 0

        def reflect_run(self, _results):
            self.calls += 1
            if self.calls == 1:
                return {"overall_decision": "needs_revision", "total_issues": 1}
            return {"overall_decision": "accepted", "total_issues": 0}

    reflect_stub = _ReflectStub()
    artifacts = _full_artifact_index()
    artifacts["selected_method"] = "t_test_ind"

    orchestrator = None

    def compile_handler(state, artifact_index, round_no):
        assert state == RunState.COMPILE
        method = str(artifact_index.get("selected_method") or "")
        if method == "t_test_ind":
            return AgentDecision.advance(target_state=RunState.EXECUTE, reason="compile_parametric")
        return AgentDecision.advance(target_state=RunState.EXECUTE, reason="compile_nonparametric")

    def verify_handler(state, artifact_index, round_no):
        assert state == RunState.VERIFY
        method = str(artifact_index.get("selected_method") or "")
        if method == "t_test_ind":
            decision = orchestrator.reflect_on_results(
                {"s1": {"method_id": "t_test_ind", "p_value": 0.00001, "sample_size": 8}},
                round_number=round_no,
            )
            # Simulate planner switch after reflection reject.
            updates = dict(decision.artifact_updates or {})
            updates["selected_method"] = "mann_whitney"
            return AgentDecision.reject(
                target_state=RunState.COMPILE,
                reason="reflection_switch_to_nonparametric",
                artifact_updates=updates,
            )
        return orchestrator.reflect_on_results(
            {"s1": {"method_id": "mann_whitney", "p_value": 0.032, "sample_size": 30}},
            round_number=round_no,
        )

    orchestrator = AgentOrchestrator(
        initial_state=RunState.INGEST,
        max_rounds=25,
        artifact_index=artifacts,
        role_handlers={
            "compile": compile_handler,
            "verifier": verify_handler,
        },
        reflect_agent=reflect_stub,
    )

    result = orchestrator.run(until_state=RunState.RELEASE)

    assert result["status"] == "completed", result
    assert result["state"] == RunState.RELEASE.value
    assert result["artifacts"].get("selected_method") == "mann_whitney"
    assert any(
        event.get("state") == RunState.VERIFY.value
        and event.get("action") == "reject"
        and event.get("target_state") == RunState.COMPILE.value
        for event in result["events"]
    )
    assert ("verify", "compile") in {
        (str(item.get("from")), str(item.get("to")))
        for item in result["transitions"]
        if isinstance(item, dict)
    }
