import math
import shutil
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import pytest

from app.stats.engine import run_analysis


Case = Tuple[str, pd.DataFrame, str, str, Dict]


def _build_cases() -> List[Case]:
    rng = np.random.default_rng(42)
    out: List[Case] = []

    # 1) Independent t-test
    n = 120
    df_t = pd.DataFrame(
        {
            "group": ["A"] * n + ["B"] * n,
            "value": np.concatenate([rng.normal(10.0, 1.8, n), rng.normal(12.0, 1.8, n)]),
        }
    )
    out.append(("t_test_ind", df_t, "value", "group", {}))
    out.append(("t_test_welch", df_t, "value", "group", {}))

    # 2) Mann-Whitney
    df_mw = pd.DataFrame(
        {
            "group": ["A"] * n + ["B"] * n,
            "value": np.concatenate([rng.lognormal(1.5, 0.45, n), rng.lognormal(1.8, 0.45, n)]),
        }
    )
    out.append(("mann_whitney", df_mw, "value", "group", {}))

    # 3) ANOVA / Kruskal
    df_a = pd.DataFrame(
        {
            "group": ["A"] * n + ["B"] * n + ["C"] * n,
            "value": np.concatenate(
                [rng.normal(8.0, 1.6, n), rng.normal(10.5, 1.6, n), rng.normal(12.8, 1.6, n)]
            ),
        }
    )
    out.append(("anova", df_a, "value", "group", {}))
    out.append(("kruskal", df_a, "value", "group", {}))

    # 4) Chi-square
    df_chi = pd.DataFrame(
        {
            "group": ["A"] * 120 + ["B"] * 120,
            "outcome": (["yes"] * 85 + ["no"] * 35) + (["yes"] * 58 + ["no"] * 62),
        }
    )
    out.append(("chi_square", df_chi, "outcome", "group", {}))

    # 5) Pearson / Spearman
    x = rng.normal(0, 1, 220)
    y = 0.82 * x + rng.normal(0, 0.35, 220)
    df_corr = pd.DataFrame({"x": x, "y": y})
    out.append(("pearson", df_corr, "x", "y", {}))
    out.append(("spearman", df_corr, "x", "y", {}))

    # 6) Linear regression
    x1 = rng.normal(0, 1, 260)
    x2 = rng.normal(0, 1, 260)
    y_lin = 2.0 + 0.95 * x1 - 0.55 * x2 + rng.normal(0, 0.45, 260)
    df_lin = pd.DataFrame({"target": y_lin, "x1": x1, "x2": x2})
    out.append(("linear_regression", df_lin, "target", "x1", {"predictors": ["x1", "x2"]}))

    # 7) Logistic regression
    lx1 = rng.normal(0, 1, 320)
    lx2 = rng.normal(0, 1, 320)
    logits = 0.9 * lx1 - 0.65 * lx2
    prob = 1.0 / (1.0 + np.exp(-logits))
    y_log = rng.binomial(1, prob, 320)
    if y_log.sum() < 10 or (len(y_log) - y_log.sum()) < 10:
        y_log[:160] = 0
        y_log[160:] = 1
    df_log = pd.DataFrame({"outcome": y_log, "x1": lx1, "x2": lx2})
    out.append(("logistic_regression", df_log, "outcome", "x1", {"predictors": ["x1", "x2"]}))

    return out


def _as_float(value):
    try:
        if value is None:
            return None
        f = float(value)
        if math.isfinite(f):
            return f
    except Exception:
        return None
    return None


def _assert_base_contract(method_id: str, result: Dict):
    assert isinstance(result, dict), f"{method_id}: result must be dict"
    assert "error" not in result, f"{method_id}: engine returned error: {result.get('error')}"
    assert "method" in result, f"{method_id}: missing 'method'"
    assert "significant" in result, f"{method_id}: missing 'significant'"

    p = _as_float(result.get("p_value"))
    if p is not None:
        assert 0.0 <= p <= 1.0, f"{method_id}: invalid p_value={p}"


def _run(method_id: str, df: pd.DataFrame, col_a: str, col_b: str, engine: str, kwargs: Dict):
    return run_analysis(
        df,
        method_id,
        col_a,
        col_b,
        alpha=0.05,
        engine=engine,
        **kwargs,
    )


def test_python_contract_top10_methods():
    for method_id, df, col_a, col_b, kwargs in _build_cases():
        result = _run(method_id, df, col_a, col_b, engine="python", kwargs=kwargs)
        _assert_base_contract(method_id, result)


def test_python_r_parity_top10_methods():
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available in PATH")

    cases = _build_cases()
    probe_method_id, probe_df, probe_a, probe_b, probe_kwargs = cases[0]
    probe = _run(probe_method_id, probe_df, probe_a, probe_b, engine="r", kwargs=probe_kwargs)
    if str(probe.get("engine", "")).strip().lower() != "r":
        pytest.skip("R engine is unavailable or fell back to Python")

    for method_id, df, col_a, col_b, kwargs in cases:
        py = _run(method_id, df, col_a, col_b, engine="python", kwargs=kwargs)
        r = _run(method_id, df, col_a, col_b, engine="r", kwargs=kwargs)

        _assert_base_contract(method_id, py)
        _assert_base_contract(method_id, r)
        assert str(r.get("engine", "")).strip().lower() == "r", f"{method_id}: expected R engine output"

        py_sig = bool(py.get("significant"))
        r_sig = bool(r.get("significant"))
        assert py_sig == r_sig, f"{method_id}: significance mismatch python={py_sig}, r={r_sig}"

        py_p = _as_float(py.get("p_value"))
        r_p = _as_float(r.get("p_value"))
        if py_p is not None and r_p is not None:
            # Parity tolerance: identical direction + bounded p-distance.
            assert abs(py_p - r_p) <= 0.2, f"{method_id}: p-value drift too large python={py_p}, r={r_p}"
