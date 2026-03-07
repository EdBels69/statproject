from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set


class RunState(str, Enum):
    INGEST = "ingest"
    PROFILE = "profile"
    CLEAN = "clean"
    DESIGN = "design"
    FREEZE = "freeze"
    COMPILE = "compile"
    EXECUTE = "execute"
    VERIFY = "verify"
    REPORT = "report"
    RELEASE = "release"


ALL_RUN_STATES: List[str] = [state.value for state in RunState]


ALLOWED_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.INGEST: {RunState.PROFILE},
    RunState.PROFILE: {RunState.CLEAN},
    RunState.CLEAN: {RunState.DESIGN},
    RunState.DESIGN: {RunState.CLEAN, RunState.FREEZE},
    RunState.FREEZE: {RunState.COMPILE},
    RunState.COMPILE: {RunState.EXECUTE},
    RunState.EXECUTE: {RunState.COMPILE, RunState.VERIFY},
    RunState.VERIFY: {RunState.COMPILE, RunState.REPORT},
    RunState.REPORT: {RunState.VERIFY, RunState.RELEASE},
    RunState.RELEASE: set(),
}


REQUIRED_ARTIFACTS: Dict[RunState, Set[str]] = {
    RunState.INGEST: {"source_raw", "source_meta"},
    RunState.PROFILE: {"profile"},
    RunState.CLEAN: {"cleaning_plan", "cleaning_log", "processed_dataset"},
    RunState.DESIGN: {"design"},
    RunState.FREEZE: {"analysis_set"},
    RunState.COMPILE: {"protocol"},
    RunState.EXECUTE: {"results"},
    RunState.VERIFY: {"verification"},
    RunState.REPORT: {"report_html"},
    RunState.RELEASE: {
        "reproducibility_manifest",
        "reproduce_script",
        "reproduce_payload",
        "protocol_resolved",
    },
}


@dataclass(frozen=True)
class Transition:
    from_state: RunState
    to_state: RunState
    changed_at: str
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "from": self.from_state.value,
            "to": self.to_state.value,
            "changed_at": self.changed_at,
        }
        if isinstance(self.reason, str) and self.reason.strip():
            payload["reason"] = self.reason.strip()
        return payload


class RunStateMachine:
    def __init__(
        self,
        *,
        initial_state: RunState | str = RunState.INGEST,
        transition_log: Optional[Iterable[Mapping[str, Any]]] = None,
    ) -> None:
        self._state = self._coerce_state(initial_state)
        self._log: List[Transition] = []
        if transition_log:
            for raw in transition_log:
                if not isinstance(raw, Mapping):
                    continue
                prev = raw.get("from")
                nxt = raw.get("to")
                changed = raw.get("changed_at")
                reason = raw.get("reason")
                try:
                    item = Transition(
                        from_state=self._coerce_state(prev),
                        to_state=self._coerce_state(nxt),
                        changed_at=str(changed),
                        reason=str(reason) if reason is not None else None,
                    )
                except Exception:
                    continue
                self._log.append(item)

    @staticmethod
    def _coerce_state(value: RunState | str | Any) -> RunState:
        if isinstance(value, RunState):
            return value
        text = str(value or "").strip().lower()
        if not text:
            raise ValueError("Run state is required")
        try:
            return RunState(text)
        except Exception as exc:
            raise ValueError(f"Unknown run state: {value}") from exc

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def state_value(self) -> str:
        return self._state.value

    @property
    def transitions(self) -> List[Dict[str, Any]]:
        return [item.as_dict() for item in self._log]

    def can_transition(self, to_state: RunState | str) -> bool:
        target = self._coerce_state(to_state)
        allowed = ALLOWED_TRANSITIONS.get(self._state, set())
        return target in allowed

    def transition(self, to_state: RunState | str, *, reason: Optional[str] = None) -> Transition:
        target = self._coerce_state(to_state)
        if not self.can_transition(target):
            raise ValueError(f"Forbidden transition: {self._state.value} -> {target.value}")
        item = Transition(
            from_state=self._state,
            to_state=target,
            changed_at=datetime.utcnow().isoformat() + "Z",
            reason=reason,
        )
        self._log.append(item)
        self._state = target
        return item

    def missing_required_artifacts(self, artifact_index: Mapping[str, Any]) -> List[str]:
        required = REQUIRED_ARTIFACTS.get(self._state, set())
        missing: List[str] = []
        for key in sorted(required):
            value = artifact_index.get(key) if isinstance(artifact_index, Mapping) else None
            if isinstance(value, str) and value.strip():
                continue
            if bool(value):
                continue
            missing.append(key)
        return missing

    def to_document(self, artifact_index: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        artifacts = dict(artifact_index) if isinstance(artifact_index, Mapping) else {}
        return {
            "schema": "clinimetria.run_state",
            "version": 1,
            "state": self._state.value,
            "allowed_next": [state.value for state in sorted(ALLOWED_TRANSITIONS.get(self._state, set()), key=lambda s: s.value)],
            "required_artifacts": sorted(REQUIRED_ARTIFACTS.get(self._state, set())),
            "missing_artifacts": self.missing_required_artifacts(artifacts),
            "artifacts": artifacts,
            "transitions": self.transitions,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }


def assert_transition_allowed(from_state: RunState | str, to_state: RunState | str) -> None:
    machine = RunStateMachine(initial_state=from_state)
    machine.transition(to_state)

