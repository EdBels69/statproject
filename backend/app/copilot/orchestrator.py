from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from app.core.run_state_machine import ALLOWED_TRANSITIONS, REQUIRED_ARTIFACTS, RunState, RunStateMachine


class AgentRole(str, Enum):
    INGESTOR = "ingestor"
    CLEANER = "cleaner"
    PLANNER = "planner"
    EXECUTOR = "executor"
    VERIFIER = "verifier"
    REPORTER = "reporter"


ROLE_BY_STATE: Dict[RunState, AgentRole] = {
    RunState.INGEST: AgentRole.INGESTOR,
    RunState.PROFILE: AgentRole.INGESTOR,
    RunState.CLEAN: AgentRole.CLEANER,
    RunState.DESIGN: AgentRole.PLANNER,
    RunState.FREEZE: AgentRole.CLEANER,
    RunState.COMPILE: AgentRole.PLANNER,
    RunState.EXECUTE: AgentRole.EXECUTOR,
    RunState.VERIFY: AgentRole.VERIFIER,
    RunState.REPORT: AgentRole.REPORTER,
    RunState.RELEASE: AgentRole.REPORTER,
}


PIPELINE_ORDER: List[RunState] = [
    RunState.INGEST,
    RunState.PROFILE,
    RunState.CLEAN,
    RunState.DESIGN,
    RunState.FREEZE,
    RunState.COMPILE,
    RunState.EXECUTE,
    RunState.VERIFY,
    RunState.REPORT,
    RunState.RELEASE,
]

DEFAULT_SUCCESSOR: Dict[RunState, Optional[RunState]] = {
    state: (PIPELINE_ORDER[idx + 1] if idx + 1 < len(PIPELINE_ORDER) else None)
    for idx, state in enumerate(PIPELINE_ORDER)
}


@dataclass(frozen=True)
class AgentDecision:
    action: str
    reason: Optional[str] = None
    target_state: Optional[RunState] = None
    artifact_updates: Optional[Dict[str, Any]] = None

    @classmethod
    def advance(
        cls,
        *,
        target_state: Optional[RunState | str] = None,
        reason: Optional[str] = None,
        artifact_updates: Optional[Dict[str, Any]] = None,
    ) -> "AgentDecision":
        if isinstance(target_state, RunState):
            target = target_state
        elif target_state is not None:
            target = RunState(str(target_state).strip().lower())
        else:
            target = None
        return cls(
            action="advance",
            reason=reason,
            target_state=target,
            artifact_updates=dict(artifact_updates) if isinstance(artifact_updates, dict) else None,
        )

    @classmethod
    def retry(
        cls,
        *,
        reason: Optional[str] = None,
        artifact_updates: Optional[Dict[str, Any]] = None,
    ) -> "AgentDecision":
        return cls(
            action="retry",
            reason=reason,
            target_state=None,
            artifact_updates=dict(artifact_updates) if isinstance(artifact_updates, dict) else None,
        )

    @classmethod
    def reject(
        cls,
        *,
        target_state: RunState | str,
        reason: Optional[str] = None,
        artifact_updates: Optional[Dict[str, Any]] = None,
    ) -> "AgentDecision":
        if isinstance(target_state, RunState):
            target = target_state
        else:
            target = RunState(str(target_state).strip().lower())
        return cls(
            action="reject",
            reason=reason,
            target_state=target,
            artifact_updates=dict(artifact_updates) if isinstance(artifact_updates, dict) else None,
        )

    @classmethod
    def complete(cls, *, reason: Optional[str] = None) -> "AgentDecision":
        return cls(action="complete", reason=reason)

    @classmethod
    def from_any(cls, value: Any) -> "AgentDecision":
        if isinstance(value, AgentDecision):
            return value
        if isinstance(value, Mapping):
            action = str(value.get("action") or "").strip().lower() or "retry"
            reason = value.get("reason")
            target_state = value.get("target_state")
            updates = value.get("artifact_updates")
            if action == "advance":
                return cls.advance(target_state=target_state, reason=str(reason) if reason else None, artifact_updates=updates if isinstance(updates, dict) else None)
            if action == "reject":
                if target_state is None:
                    raise ValueError("reject decision requires target_state")
                return cls.reject(target_state=target_state, reason=str(reason) if reason else None, artifact_updates=updates if isinstance(updates, dict) else None)
            if action == "complete":
                return cls.complete(reason=str(reason) if reason else None)
            return cls.retry(reason=str(reason) if reason else None, artifact_updates=updates if isinstance(updates, dict) else None)
        raise ValueError("Unsupported decision payload")


Handler = Callable[[RunState, Mapping[str, Any], int], Union[AgentDecision, Mapping[str, Any]]]


class AgentOrchestrator:
    def __init__(
        self,
        *,
        initial_state: RunState | str = RunState.INGEST,
        max_rounds: int = 10,
        artifact_index: Optional[Dict[str, Any]] = None,
        role_handlers: Optional[Mapping[str, Handler]] = None,
        reflect_agent: Optional[Any] = None,
    ) -> None:
        self.machine = RunStateMachine(initial_state=initial_state)
        self.max_rounds = max(1, int(max_rounds))
        self.artifacts: Dict[str, Any] = dict(artifact_index) if isinstance(artifact_index, dict) else {}
        self.role_handlers: Dict[str, Handler] = dict(role_handlers) if isinstance(role_handlers, Mapping) else {}
        self.rounds_executed = 0
        self.events: List[Dict[str, Any]] = []
        self._reflect_agent = reflect_agent

    @staticmethod
    def _coerce_state(value: RunState | str) -> RunState:
        if isinstance(value, RunState):
            return value
        return RunState(str(value).strip().lower())

    def _resolve_handler(self, state: RunState) -> Optional[Handler]:
        role = ROLE_BY_STATE.get(state)
        keys = [
            state.value,
            str(role.value) if isinstance(role, AgentRole) else "",
        ]
        for key in keys:
            if key and key in self.role_handlers:
                return self.role_handlers[key]
        return None

    def _default_decision(self, state: RunState) -> AgentDecision:
        missing = self.machine.missing_required_artifacts(self.artifacts)
        if missing:
            return AgentDecision.retry(reason=f"missing artifacts: {', '.join(missing)}")

        target = DEFAULT_SUCCESSOR.get(state)
        if target is None:
            return AgentDecision.complete(reason="release state reached")

        allowed = ALLOWED_TRANSITIONS.get(state, set())
        if target in allowed:
            return AgentDecision.advance(target_state=target, reason=f"{state.value}_ok")

        if allowed:
            fallback = sorted(list(allowed), key=lambda s: s.value)[0]
            return AgentDecision.advance(target_state=fallback, reason=f"{state.value}_fallback")

        return AgentDecision.complete(reason=f"terminal state: {state.value}")

    def _apply_artifact_updates(self, updates: Optional[Dict[str, Any]]) -> None:
        if not isinstance(updates, dict):
            return
        for key, value in updates.items():
            if not isinstance(key, str) or not key.strip():
                continue
            norm_key = key.strip()
            if value is None:
                self.artifacts.pop(norm_key, None)
                continue
            self.artifacts[norm_key] = value

    def step(self) -> Dict[str, Any]:
        state = self.machine.state
        role = ROLE_BY_STATE.get(state)
        handler = self._resolve_handler(state)

        if handler is not None:
            raw_decision = handler(state, dict(self.artifacts), int(self.rounds_executed) + 1)
            decision = AgentDecision.from_any(raw_decision)
        else:
            decision = self._default_decision(state)

        self._apply_artifact_updates(decision.artifact_updates)

        action = str(decision.action or "").strip().lower() or "retry"
        next_state = self.machine.state_value
        transition_applied = False

        if action == "complete":
            pass
        elif action == "retry":
            pass
        else:
            if decision.target_state is None:
                decision = AgentDecision.advance(
                    target_state=DEFAULT_SUCCESSOR.get(state),
                    reason=decision.reason,
                )
            target = decision.target_state
            if target is None:
                action = "complete"
            else:
                if target not in ALLOWED_TRANSITIONS.get(state, set()):
                    raise ValueError(f"Forbidden transition: {state.value} -> {target.value}")
                self.machine.transition(target, reason=decision.reason)
                transition_applied = True
                next_state = self.machine.state_value

        event = {
            "round": int(self.rounds_executed) + 1,
            "state": state.value,
            "role": role.value if isinstance(role, AgentRole) else None,
            "action": action,
            "reason": decision.reason or "",
            "target_state": decision.target_state.value if isinstance(decision.target_state, RunState) else None,
            "next_state": next_state,
            "transition_applied": transition_applied,
            "missing_required_artifacts": self.machine.missing_required_artifacts(self.artifacts),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        self.events.append(event)
        self.rounds_executed += 1
        return event

    def run(self, *, until_state: RunState | str = RunState.RELEASE) -> Dict[str, Any]:
        target = self._coerce_state(until_state)
        while self.rounds_executed < self.max_rounds:
            if self.machine.state == target:
                break
            event = self.step()
            if event.get("action") == "complete":
                break

        status = "completed" if self.machine.state == target else "incomplete"
        return {
            "status": status,
            "state": self.machine.state_value,
            "target_state": target.value,
            "rounds_executed": int(self.rounds_executed),
            "max_rounds": int(self.max_rounds),
            "artifacts": dict(self.artifacts),
            "missing_required_artifacts": self.machine.missing_required_artifacts(self.artifacts),
            "events": list(self.events),
            "transitions": self.machine.transitions,
            "required_artifacts_by_state": {
                state.value: sorted(list(REQUIRED_ARTIFACTS.get(state, set())))
                for state in PIPELINE_ORDER
            },
        }

    def reflect_on_results(
        self,
        results: Dict[str, Dict[str, Any]],
        *,
        round_number: int = 1,
    ) -> AgentDecision:
        """
        Use the ReflectAgent to evaluate execution results and decide
        whether to advance to REPORT, retry EXECUTE, or revise COMPILE.

        If no reflect_agent was provided, defaults to advance.
        """
        if self._reflect_agent is None:
            return AgentDecision.advance(
                target_state=RunState.REPORT,
                reason="no reflect agent configured, auto-advancing",
            )

        try:
            from app.copilot.reflect_agent import ReflectDecision

            summary = self._reflect_agent.reflect_run(results)
            decision_str = summary.get("overall_decision", "accepted")

            if decision_str == "accepted":
                return AgentDecision.advance(
                    target_state=RunState.REPORT,
                    reason="reflection: all checks passed",
                    artifact_updates={"reflection_log": summary},
                )
            elif decision_str == "needs_revision" and round_number < self.max_rounds:
                return AgentDecision.reject(
                    target_state=RunState.COMPILE,
                    reason=f"reflection: needs revision ({summary.get('total_issues', 0)} issues)",
                    artifact_updates={"reflection_log": summary},
                )
            else:
                # accepted_with_flags or max rounds reached
                return AgentDecision.advance(
                    target_state=RunState.REPORT,
                    reason=f"reflection: {decision_str} ({summary.get('total_issues', 0)} issues flagged)",
                    artifact_updates={"reflection_log": summary},
                )
        except Exception as exc:
            return AgentDecision.advance(
                target_state=RunState.REPORT,
                reason=f"reflection error: {exc}, auto-advancing",
            )
