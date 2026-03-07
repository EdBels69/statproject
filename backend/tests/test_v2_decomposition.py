"""Tests for v2.py decomposition: re-exports and registry wiring."""

from __future__ import annotations

import pytest


class TestSchemas:
    """Verify schemas are importable from both locations."""

    def test_import_from_schemas(self) -> None:
        from app.api.schemas import (
            AnalysisPlanRequest,
            ExecuteProtocolRequest,
            MixedEffectsRequest,
        )

        req = ExecuteProtocolRequest(dataset_id="test", protocol=[])
        assert req.dataset_id == "test"
        assert req.alpha == 0.05

        plan = AnalysisPlanRequest(dataset_id="test", text="design")
        assert plan.text == "design"

        mixed = MixedEffectsRequest(
            dataset_id="test",
            outcome="y",
            time_col="time",
            group_col="group",
            subject_col="subject",
        )
        assert mixed.random_slope is False

    def test_reexport_from_v2(self) -> None:
        from app.api.v2 import ExecuteProtocolRequest

        req = ExecuteProtocolRequest(dataset_id="test", protocol=[])
        assert req.dataset_id == "test"


class TestHelpers:
    """Verify helper functions work from new location."""

    def test_canonical_method_id(self) -> None:
        from app.api.helpers import _canonical_method_id

        assert _canonical_method_id("welch_t_test") == "t_test_welch"
        assert _canonical_method_id("t_test_ind") == "t_test_ind"

    def test_to_int_or_none(self) -> None:
        from app.api.helpers import _to_int_or_none

        assert _to_int_or_none(42) == 42
        assert _to_int_or_none("10") == 10
        assert _to_int_or_none(None) is None
        assert _to_int_or_none("abc") is None

    def test_finite_float(self) -> None:
        from app.api.helpers import _finite_float

        assert _finite_float(3.14) == pytest.approx(3.14)
        assert _finite_float(float("nan")) is None
        assert _finite_float(None) is None

    def test_as_bool(self) -> None:
        from app.api.helpers import _as_bool

        assert _as_bool(True) is True
        assert _as_bool("yes") is True
        assert _as_bool(0) is False

    def test_reexport_from_v2(self) -> None:
        from app.api.v2 import _canonical_method_id

        assert _canonical_method_id("welch_t_test") == "t_test_welch"


class TestBuilders:
    """Verify builder functions are importable."""

    def test_build_environment_snapshot(self) -> None:
        from app.api.builders import _build_environment_snapshot

        snap = _build_environment_snapshot()
        assert isinstance(snap, dict)
        assert "python" in snap or "platform" in snap or len(snap) > 0

    def test_sha256_hex(self) -> None:
        from app.api.builders import _sha256_hex

        digest = _sha256_hex(b"hello")
        assert isinstance(digest, str)
        assert len(digest) == 64

    def test_reexport_from_v2(self) -> None:
        from app.api.v2 import _build_environment_snapshot

        snap = _build_environment_snapshot()
        assert isinstance(snap, dict)


class TestExecutorDispatch:
    """Verify executor registry."""

    def test_registry_contains_known_executors(self) -> None:
        from app.api.executor_dispatch import EXECUTOR_REGISTRY

        assert "paired_wide" in EXECUTOR_REGISTRY
        assert "bland_altman" in EXECUTOR_REGISTRY
        assert "responder_analysis" in EXECUTOR_REGISTRY

    def test_get_executor_loads(self) -> None:
        from app.api.executor_dispatch import get_executor

        fn = get_executor("paired_wide")
        assert fn is not None
        assert callable(fn)

    def test_get_executor_unknown_returns_none(self) -> None:
        from app.api.executor_dispatch import get_executor

        fn = get_executor("nonexistent_method_xyz")
        assert fn is None

    def test_is_engine_method(self) -> None:
        from app.api.executor_dispatch import is_engine_method

        assert is_engine_method("mann_whitney") is True
        assert is_engine_method("t_test_ind") is True
        assert is_engine_method("paired_wide") is False
