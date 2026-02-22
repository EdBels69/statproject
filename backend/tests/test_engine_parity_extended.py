import math
import shutil
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import pytest

from app.stats.engine import run_analysis


Case = Tuple[str, pd.DataFrame, str, str, Dict]


def _build_cases() -> List[Case]:
    rng = np.random.default_rng(123)
    out: List[Case] = []

    # 1) Welch ANOVA
    n = 90
    df_welch = pd.DataFrame(
        {
            "group": ["A"] * n + ["B"] * n + ["C"] * n,
            "value": np.concatenate(
                [
                    rng.normal(8.0, 1.0, n),
                    rng.normal(10.5, 2.5, n),
                    rng.normal(12.0, 4.0, n),
                ]
            ),
        }
    )
    out.append(("anova_welch", df_welch, "value", "group", {}))

    # 2) Fisher exact (2x2)
    df_fisher = pd.DataFrame(
        {
            "outcome": (["yes"] * 46 + ["no"] * 14) + (["yes"] * 24 + ["no"] * 36),
            "group": (["A"] * 60) + (["B"] * 60),
        }
    )
    out.append(("fisher_exact", df_fisher, "outcome", "group", {}))

    # 3) Survival KM with group comparison
    df_surv = pd.DataFrame(
        {
            "duration": np.concatenate([rng.exponential(10.0, 140), rng.exponential(6.5, 140)]),
            "event": rng.binomial(1, 0.72, 280),
            "group": ["A"] * 140 + ["B"] * 140,
        }
    )
    out.append(("survival_km", df_surv, "duration", "event", {"group_col": "group"}))

    # 4) RM-ANOVA (wide repeated measures)
    n_sub = 80
    subject = [f"s_{i:03d}" for i in range(n_sub)]
    grp = ["A"] * (n_sub // 2) + ["B"] * (n_sub - n_sub // 2)
    base = rng.normal(50, 8, n_sub)
    v1 = base + rng.normal(0, 1.2, n_sub)
    v2 = base + np.where(np.array(grp) == "B", 3.0, 1.0) + rng.normal(0, 1.2, n_sub)
    v3 = base + np.where(np.array(grp) == "B", 6.0, 2.0) + rng.normal(0, 1.2, n_sub)
    df_rm = pd.DataFrame({"subject": subject, "group": grp, "v1": v1, "v2": v2, "v3": v3})
    out.append(
        (
            "rm_anova",
            df_rm,
            "v1",
            "subject",
            {"outcome_cols": ["v1", "v2", "v3"], "subject_col": "subject"},
        )
    )

    # 5) Friedman (wide repeated measures)
    f1 = rng.normal(10.0, 1.0, n_sub)
    f2 = f1 + rng.normal(0.7, 0.8, n_sub)
    f3 = f2 + rng.normal(0.8, 0.8, n_sub)
    df_fried = pd.DataFrame({"f1": f1, "f2": f2, "f3": f3})
    out.append(("friedman", df_fried, "f1", "f2", {"outcome_cols": ["f1", "f2", "f3"]}))

    # 6) ROC analysis
    n_roc = 260
    y = rng.binomial(1, 0.5, n_roc)
    score = y * 0.75 + rng.normal(0, 0.35, n_roc)
    df_roc = pd.DataFrame({"score": score, "label": y})
    out.append(("roc_analysis", df_roc, "score", "label", {}))

    # 7) Two-way ANOVA
    n2 = 90
    g1 = np.array(["A"] * n2 + ["B"] * n2 + ["A"] * n2 + ["B"] * n2)
    g2 = np.array(["T1"] * (2 * n2) + ["T2"] * (2 * n2))
    base = np.where(g1 == "B", 3.0, 0.0) + np.where(g2 == "T2", 2.0, 0.0)
    interaction = np.where((g1 == "B") & (g2 == "T2"), 1.5, 0.0)
    value = 10.0 + base + interaction + rng.normal(0, 1.2, len(g1))
    df_2w = pd.DataFrame({"value": value, "group1": g1, "group2": g2})
    out.append(("anova_twoway", df_2w, "value", "group1", {"group1": "group1", "group2": "group2"}))

    # 8) Clustered correlation
    n_cc = 220
    z1 = rng.normal(0.0, 1.0, n_cc)
    z2 = 0.82 * z1 + rng.normal(0.0, 0.35, n_cc)
    z3 = 0.74 * z1 + rng.normal(0.0, 0.40, n_cc)
    w1 = rng.normal(0.0, 1.0, n_cc)
    w2 = 0.77 * w1 + rng.normal(0.0, 0.38, n_cc)
    w3 = 0.71 * w1 + rng.normal(0.0, 0.42, n_cc)
    df_cluster = pd.DataFrame(
        {
            "z1": z1,
            "z2": z2,
            "z3": z3,
            "w1": w1,
            "w2": w2,
            "w3": w3,
        }
    )
    out.append(
        (
            "clustered_correlation",
            df_cluster,
            "z1",
            "z2",
            {
                "variables": ["z1", "z2", "z3", "w1", "w2", "w3"],
                "method": "pearson",
                "linkage_method": "average",
                "n_clusters": 2,
                "show_p_values": True,
            },
        )
    )

    # 9) Mixed effects
    n_subjects = 24
    rows = []
    for sid in range(1, n_subjects + 1):
        grp = "A" if sid <= n_subjects // 2 else "B"
        for time in [1, 2, 3, 4]:
            baseline = 10.0 if grp == "A" else 11.0
            time_effect = 0.6 * time
            interaction_effect = 0.7 * time if grp == "B" else 0.0
            noise = rng.normal(0, 0.8)
            rows.append(
                {
                    "subject": f"s_{sid:03d}",
                    "time": time,
                    "group": grp,
                    "outcome": baseline + time_effect + interaction_effect + noise,
                }
            )
    df_mix = pd.DataFrame(rows)
    out.append(
        (
            "mixed_effects",
            df_mix,
            "outcome",
            "group",
            {"group_col": "group", "time_col": "time", "subject_col": "subject"},
        )
    )

    return out


def _as_float(value):
    try:
        if value is None:
            return None
        out = float(value)
        if math.isfinite(out):
            return out
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


def test_python_contract_extended_methods():
    for method_id, df, col_a, col_b, kwargs in _build_cases():
        result = _run(method_id, df, col_a, col_b, engine="python", kwargs=kwargs)
        _assert_base_contract(method_id, result)


def test_python_r_parity_extended_methods():
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

        assert bool(py.get("significant")) == bool(r.get("significant")), (
            f"{method_id}: significance mismatch python={py.get('significant')} r={r.get('significant')}"
        )

        py_p = _as_float(py.get("p_value"))
        r_p = _as_float(r.get("p_value"))
        if py_p is not None and r_p is not None:
            assert abs(py_p - r_p) <= 0.25, f"{method_id}: p-value drift too large python={py_p}, r={r_p}"

        if method_id == "roc_analysis":
            py_auc = _as_float(py.get("auc"))
            r_auc = _as_float(r.get("auc"))
            if py_auc is not None and r_auc is not None:
                assert abs(py_auc - r_auc) <= 0.1, f"roc_analysis: auc drift too large python={py_auc}, r={r_auc}"
