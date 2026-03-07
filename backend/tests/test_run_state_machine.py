import pytest

from app.core.run_state_machine import RunState, RunStateMachine


def test_run_state_machine_happy_path_reaches_release():
    machine = RunStateMachine(initial_state=RunState.INGEST)
    for state in [
        RunState.PROFILE,
        RunState.CLEAN,
        RunState.DESIGN,
        RunState.FREEZE,
        RunState.COMPILE,
        RunState.EXECUTE,
        RunState.VERIFY,
        RunState.REPORT,
        RunState.RELEASE,
    ]:
        machine.transition(state)

    assert machine.state == RunState.RELEASE
    assert len(machine.transitions) == 9


def test_run_state_machine_reject_loops_supported():
    machine = RunStateMachine(initial_state=RunState.DESIGN)
    machine.transition(RunState.CLEAN, reason="design_invalid")
    machine.transition(RunState.DESIGN, reason="clean_done")
    machine.transition(RunState.FREEZE, reason="design_confirmed")

    assert machine.state == RunState.FREEZE
    assert [item["to"] for item in machine.transitions] == ["clean", "design", "freeze"]


def test_run_state_machine_forbidden_transition_raises():
    machine = RunStateMachine(initial_state=RunState.COMPILE)
    with pytest.raises(ValueError, match="Forbidden transition"):
        machine.transition(RunState.RELEASE)


def test_run_state_machine_required_artifacts():
    machine = RunStateMachine(initial_state=RunState.VERIFY)
    assert machine.missing_required_artifacts({}) == ["verification"]
    doc = machine.to_document({"verification": "artifacts/verification.json"})
    assert doc["missing_artifacts"] == []
