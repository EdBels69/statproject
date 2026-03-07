import warnings
import numpy as np
import pandas as pd

from app.stats.engine import run_analysis, check_normality_with_policy


def test_kendall_correlation_runs():
    rng = np.random.default_rng(42)
    x = np.arange(1, 101, dtype=float)
    noise = rng.normal(0.0, 1.0, size=100)
    y = x + noise
    df = pd.DataFrame({"x": x, "y": y})

    res = run_analysis(df, "kendall", "x", "y", alpha=0.05)

    assert res.get("method") == "kendall"
    assert isinstance(res.get("stat_value"), float)
    assert isinstance(res.get("p_value"), float)


def test_correlation_method_override_to_kendall():
    rng = np.random.default_rng(7)
    x = np.linspace(0, 10, 120)
    y = x**2 + rng.normal(0.0, 1.0, size=120)
    df = pd.DataFrame({"x": x, "y": y})

    res = run_analysis(df, "pearson", "x", "y", alpha=0.05, correlation_method="kendall")

    assert res.get("method") == "kendall"
    assert res.get("effect_size_name") == "tau"


def test_group_assumptions_respect_custom_policy():
    rng = np.random.default_rng(123)
    a = rng.lognormal(mean=0.0, sigma=1.0, size=80)
    b = rng.lognormal(mean=0.2, sigma=1.0, size=80)
    df = pd.DataFrame(
        {
            "value": np.concatenate([a, b]),
            "group": ["A"] * len(a) + ["B"] * len(b),
        }
    )

    res = run_analysis(
        df,
        "t_test_ind",
        "value",
        "group",
        alpha=0.05,
        normality_test="suite",
        normality_decision="majority",
        homogeneity_test="fligner",
    )

    assumptions = res.get("assumptions") if isinstance(res, dict) else {}
    normality = assumptions.get("normality") if isinstance(assumptions, dict) else {}
    homogeneity = assumptions.get("homogeneity") if isinstance(assumptions, dict) else {}

    assert isinstance(normality, dict) and normality
    for group_payload in normality.values():
        if not isinstance(group_payload, dict):
            continue
        assert "tests" in group_payload
        assert "selected_tests" in group_payload
        assert "decision_rule" in group_payload

    assert homogeneity.get("test") == "fligner"


def test_near_constant_normality_without_runtime_warning():
    s = pd.Series([3.0] * 40)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        out = check_normality_with_policy(
            s,
            normality_test="suite",
            alpha=0.05,
            decision_rule="majority",
        )

    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warnings
    assert out.get("passed") is False
    tests = out.get("tests") if isinstance(out, dict) else {}
    shapiro = tests.get("shapiro") if isinstance(tests, dict) else {}
    assert isinstance(shapiro, dict)
    assert shapiro.get("passed") is False


def test_paired_ttest_constant_data_without_runtime_warning():
    n = 30
    df = pd.DataFrame(
        {
            "value": [10.0] * n + [10.0] * n,
            "group": ["A"] * n + ["B"] * n,
        }
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        res = run_analysis(df, "t_test_rel", "value", "group", alpha=0.05)

    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warnings
    assert res.get("method") in {"t_test_rel", "wilcoxon", "mann_whitney"}
