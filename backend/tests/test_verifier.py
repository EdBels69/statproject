from app.copilot.verifier import verify_run_payload


def test_verifier_passes_valid_payload():
    run_payload = {
        "results": {
            "s1": {
                "p_value": 0.03,
                "p_value_adj": 0.04,
                "significant_adj": True,
                "effect_size": 0.55,
                "effect_size_ci_lower": 0.20,
                "effect_size_ci_upper": 0.90,
                "multiplicity_trace": {
                    "method": "holm",
                    "n_total": 2,
                    "n_valid": 2,
                },
            }
        }
    }
    report = verify_run_payload(run_payload, alpha=0.05)
    assert report["status"] == "passed"
    assert int(report["summary"]["failed"]) == 0


def test_verifier_fails_on_invalid_p_value():
    run_payload = {"results": {"s1": {"p_value": 1.2}}}
    report = verify_run_payload(run_payload, alpha=0.05)
    assert report["status"] == "failed"
    assert any(item.get("check") == "p_value_bounds" for item in report["failures"])


def test_verifier_fails_on_non_finite_effect_size():
    run_payload = {"results": {"s1": {"effect_size": "NaN"}}}
    report = verify_run_payload(run_payload, alpha=0.05)
    assert report["status"] == "failed"
    assert any(item.get("check") == "effect_size_finite" for item in report["failures"])


def test_verifier_fails_when_multiple_pvalues_without_multiplicity():
    run_payload = {
        "results": {
            "s1": {"p_value": 0.01},
            "s2": {"p_value": 0.02},
        }
    }
    report = verify_run_payload(run_payload, alpha=0.05)
    assert report["status"] == "failed"
    assert any(item.get("check") == "multiplicity_correction_required" for item in report["failures"])


def test_verifier_passes_when_global_multiplicity_policy_present():
    run_payload = {
        "multiplicity_policy": {"correction": "holm"},
        "results": {
            "s1": {"p_value": 0.01},
            "s2": {"p_value": 0.02},
        },
    }
    report = verify_run_payload(run_payload, alpha=0.05)
    assert report["status"] == "passed"
    assert not any(item.get("check") == "multiplicity_correction_required" for item in report["failures"])
