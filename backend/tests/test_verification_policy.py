from app.copilot.verification_policy import (
    attempt_verifier_reflection_repair,
    repair_run_payload_multiplicity,
    repair_run_payload_p_bounds,
)


def test_repair_run_payload_multiplicity_updates_steps():
    run_payload = {
        "results": {
            "s1": {"p_value": 0.01},
            "s2": {"p_value_raw": 0.04},
        }
    }

    res = repair_run_payload_multiplicity(run_payload, alpha=0.05, correction="holm")

    assert res.get("changed") is True
    assert int(res.get("n_steps") or 0) == 2
    assert set(res.get("steps") or []) == {"s1", "s2"}

    s1 = run_payload["results"]["s1"]
    s2 = run_payload["results"]["s2"]
    for item in [s1, s2]:
        assert item.get("multiplicity_correction") == "holm"
        assert isinstance(item.get("p_value_adj"), float)
        assert isinstance(item.get("significant_adj"), bool)
        trace = item.get("multiplicity_trace")
        assert isinstance(trace, dict)
        assert trace.get("method") == "holm"
        assert trace.get("scope") == "verification_repair"


def test_repair_run_payload_p_bounds_clamps_near_limits():
    run_payload = {
        "results": {
            "s1": {"p_value": -1e-13},
            "s2": {"p_value_adj": 1.0 + 5e-13},
            "s3": {"p_value": 0.2},
        }
    }

    res = repair_run_payload_p_bounds(run_payload, epsilon=1e-12)

    assert res.get("changed") is True
    assert int(res.get("n_steps") or 0) == 2
    assert set(res.get("steps") or []) == {"s1", "s2"}
    assert run_payload["results"]["s1"]["p_value"] == 0.0
    assert run_payload["results"]["s2"]["p_value_adj"] == 1.0
    assert run_payload["results"]["s3"]["p_value"] == 0.2


def test_attempt_verifier_reflection_repair_applies_multiplicity_fix():
    run_payload = {
        "results": {
            "s1": {"p_value": 0.02},
            "s2": {"p_value": 0.03},
        }
    }
    verification = {
        "status": "failed",
        "failures": [
            {
                "check": "multiplicity_trace_method",
                "step_id": "s1",
                "message": "Unsupported multiplicity method in trace: legacy",
            }
        ],
    }

    res = attempt_verifier_reflection_repair(
        run_payload,
        verification=verification,
        alpha=0.05,
        correction="fdr_bh",
    )

    assert res.get("applied") is True
    assert res.get("reason") == "multiplicity_trace_repaired"
    assert isinstance(run_payload["results"]["s1"].get("multiplicity_trace"), dict)


def test_attempt_verifier_reflection_repair_returns_no_repair_for_unhandled_failure():
    run_payload = {"results": {"s1": {"effect_size_ci_lower": 2.0, "effect_size_ci_upper": 1.0}}}
    verification = {
        "status": "failed",
        "failures": [
            {
                "check": "effect_ci_order",
                "step_id": "s1",
                "message": "effect_size_ci_lower >= effect_size_ci_upper",
            }
        ],
    }

    res = attempt_verifier_reflection_repair(
        run_payload,
        verification=verification,
        alpha=0.05,
        correction="fdr_bh",
    )

    assert res.get("applied") is False
    assert res.get("reason") == "no_deterministic_repair_available"
    assert res.get("checks") == ["effect_ci_order"]

