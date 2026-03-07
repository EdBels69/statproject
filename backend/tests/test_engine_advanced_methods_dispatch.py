import numpy as np
import pandas as pd

from app.stats.engine import run_analysis


def _base_numeric_df(n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(2026)
    x1 = rng.normal(0.0, 1.0, size=n)
    x2 = 0.6 * x1 + rng.normal(0.0, 0.8, size=n)
    x3 = rng.normal(0.0, 1.0, size=n)
    x4 = 0.4 * x2 + 0.3 * x3 + rng.normal(0.0, 0.9, size=n)
    group = np.where(np.arange(n) < (n // 2), "A", "B")
    outcome = 1.5 + 0.7 * x1 + (group == "B").astype(float) * 0.8 + rng.normal(0.0, 0.7, size=n)

    return pd.DataFrame(
        {
            "x1": x1,
            "x2": x2,
            "x3": x3,
            "x4": x4,
            "group": group,
            "outcome": outcome,
        }
    )


def test_ancova_dispatch_runs():
    df = _base_numeric_df()
    res = run_analysis(
        df,
        "ancova",
        "outcome",
        "group",
        alpha=0.05,
        covariates=["x1", "x2"],
    )
    assert res.get("method") == "ancova"
    assert isinstance(res.get("anova_table"), list)


def test_pca_dispatch_runs():
    df = _base_numeric_df()
    res = run_analysis(
        df,
        "pca",
        "x1",
        "x2",
        alpha=0.05,
        variables=["x1", "x2", "x3", "x4"],
        n_components=2,
    )
    assert res.get("method") == "pca"
    assert int(res.get("n_components") or 0) == 2
    assert isinstance(res.get("components"), list) and len(res["components"]) == 2


def test_efa_dispatch_runs():
    df = _base_numeric_df()
    res = run_analysis(
        df,
        "efa",
        "x1",
        "x2",
        alpha=0.05,
        variables=["x1", "x2", "x3", "x4"],
        n_factors=2,
    )
    assert res.get("method") == "efa"
    assert int(res.get("n_factors") or 0) == 2
    assert isinstance(res.get("factors"), list) and len(res["factors"]) == 2


def test_kmeans_dispatch_runs():
    df = _base_numeric_df()
    res = run_analysis(
        df,
        "kmeans",
        "x1",
        "x2",
        alpha=0.05,
        variables=["x1", "x2", "x3"],
        n_clusters=3,
        random_state=42,
    )
    assert res.get("method") == "kmeans"
    assert int(res.get("n_clusters") or 0) == 3
    assert isinstance(res.get("cluster_assignments"), list)


def test_hierarchical_dispatch_runs():
    df = _base_numeric_df()
    res = run_analysis(
        df,
        "hierarchical_clustering",
        "x1",
        "x2",
        alpha=0.05,
        variables=["x1", "x2", "x3"],
        n_clusters=3,
        linkage_method="ward",
    )
    assert res.get("method") == "hierarchical_clustering"
    assert int(res.get("n_clusters") or 0) >= 2
    dendrogram = res.get("dendrogram")
    assert isinstance(dendrogram, dict)
    assert isinstance(dendrogram.get("linkage_matrix"), list)


def test_misc_correlation_reliability_dispatch_runs():
    df = _base_numeric_df()
    df["binary_group"] = np.where(np.arange(len(df)) % 2 == 0, "No", "Yes")
    df["m1"] = df["outcome"] + np.random.default_rng(7).normal(0.0, 0.2, size=len(df))
    df["m2"] = df["outcome"] + np.random.default_rng(8).normal(0.0, 0.2, size=len(df))

    res_shapiro = run_analysis(df, "shapiro_wilk", "outcome", "group", alpha=0.05)
    assert res_shapiro.get("method") == "shapiro_wilk"

    res_point_biserial = run_analysis(
        df,
        "point_biserial",
        "outcome",
        "binary_group",
        alpha=0.05,
        outcome="outcome",
        group="binary_group",
    )
    assert res_point_biserial.get("method") == "point_biserial"

    res_partial = run_analysis(
        df,
        "partial_correlation",
        "x1",
        "x2",
        alpha=0.05,
        outcome="x1",
        group="x2",
        covariates=["x3"],
    )
    assert res_partial.get("method") == "partial_correlation"

    res_cronbach = run_analysis(
        df,
        "cronbach_alpha",
        "x1",
        "x2",
        alpha=0.05,
        variables=["x1", "x2", "x3", "x4"],
    )
    assert res_cronbach.get("method") == "cronbach_alpha"

    res_bland = run_analysis(df, "bland_altman", "m1", "m2", alpha=0.05)
    assert res_bland.get("method") == "bland_altman"
    assert isinstance(res_bland.get("agreement_interpretation"), dict)
    assert isinstance(res_bland.get("plot_reference_lines"), dict)
    assert res_bland.get("outside_loa_fraction") is not None


def test_categorical_agreement_dispatch_runs():
    rng = np.random.default_rng(99)
    n = 140
    before = rng.integers(0, 2, size=n)
    after = (before ^ (rng.random(n) < 0.25)).astype(int)
    cond1 = rng.integers(0, 2, size=n)
    cond2 = (cond1 ^ (rng.random(n) < 0.20)).astype(int)
    cond3 = (cond1 ^ (rng.random(n) < 0.30)).astype(int)

    rater_a = np.where(before == 1, "pos", "neg")
    # Keep agreement imperfect but above chance.
    flip = rng.random(n) < 0.15
    rater_b = np.where(np.where(flip, 1 - before, before) == 1, "pos", "neg")

    df = pd.DataFrame(
        {
            "before": np.where(before == 1, "yes", "no"),
            "after": np.where(after == 1, "yes", "no"),
            "c1": np.where(cond1 == 1, "yes", "no"),
            "c2": np.where(cond2 == 1, "yes", "no"),
            "c3": np.where(cond3 == 1, "yes", "no"),
            "rater_a": rater_a,
            "rater_b": rater_b,
        }
    )

    res_kappa = run_analysis(df, "cohens_kappa", "rater_a", "rater_b", alpha=0.05)
    assert res_kappa.get("method") == "cohens_kappa"

    res_mcnemar = run_analysis(
        df,
        "mcnemar",
        "before",
        "after",
        alpha=0.05,
        before="before",
        after="after",
    )
    assert res_mcnemar.get("method") == "mcnemar"

    res_cochran = run_analysis(
        df,
        "cochran_q",
        "c1",
        "c2",
        alpha=0.05,
        outcome_cols=["c1", "c2", "c3"],
    )
    assert res_cochran.get("method") == "cochran_q"


def test_icc_dispatch_runs():
    rng = np.random.default_rng(101)
    subjects = [f"s{i:02d}" for i in range(1, 26)]
    raters = ["r1", "r2", "r3"]
    rows = []
    for sid in subjects:
        latent = rng.normal(10.0, 2.0)
        for rater in raters:
            rows.append(
                {
                    "subject": sid,
                    "rater": rater,
                    "rating": latent + rng.normal(0.0, 0.7),
                }
            )
    df = pd.DataFrame(rows)

    res = run_analysis(
        df,
        "icc",
        "rating",
        "rater",
        alpha=0.05,
        subject_col="subject",
        rater_col="rater",
        icc_type="ICC2",
    )
    assert res.get("method") == "icc"
    assert res.get("icc_type") is not None


def test_bayesian_dispatch_runs():
    df = _base_numeric_df()
    df["group2"] = np.where(np.arange(len(df)) < (len(df) // 2), "A", "B")
    df["cat_a"] = np.where(df["x1"] > 0.0, "high", "low")
    df["cat_b"] = np.where(df["x2"] > 0.2, "yes", "no")

    res_one = run_analysis(
        df,
        "bayes_t_test_one",
        "x1",
        "",
        alpha=0.05,
        test_value=0.0,
    )
    assert res_one.get("method") == "bayes_t_test_one"
    assert isinstance(res_one.get("bayesian"), dict)
    assert res_one.get("bayesian", {}).get("bf10") is not None

    res_ind = run_analysis(
        df,
        "bayes_t_test_ind",
        "outcome",
        "group2",
        alpha=0.05,
    )
    assert res_ind.get("method") == "bayes_t_test_ind"
    assert isinstance(res_ind.get("bayesian"), dict)
    assert res_ind.get("bayes_decision") in {"supports_h1", "supports_h0", "inconclusive"}

    res_corr = run_analysis(
        df,
        "bayes_correlation",
        "x1",
        "x2",
        alpha=0.05,
        correlation_method="pearson",
    )
    assert res_corr.get("method") == "bayes_correlation"
    assert isinstance(res_corr.get("bayesian"), dict)
    assert res_corr.get("bayesian", {}).get("posterior_prob_h1") is not None

    res_anova = run_analysis(
        df,
        "bayes_anova",
        "outcome",
        "group2",
        alpha=0.05,
    )
    assert res_anova.get("method") == "bayes_anova"
    assert isinstance(res_anova.get("bayesian"), dict)
    assert res_anova.get("frequentist_method") == "anova"

    res_reg = run_analysis(
        df,
        "bayes_linear_regression",
        "outcome",
        "x1",
        alpha=0.05,
        predictors=["x1", "x2"],
    )
    assert res_reg.get("method") == "bayes_linear_regression"
    assert isinstance(res_reg.get("bayesian"), dict)
    assert res_reg.get("frequentist_method") == "linear_regression"

    res_chi = run_analysis(
        df,
        "bayes_chi_square",
        "cat_a",
        "cat_b",
        alpha=0.05,
    )
    assert res_chi.get("method") == "bayes_chi_square"
    assert isinstance(res_chi.get("bayesian"), dict)
    assert res_chi.get("frequentist_method") in {"chi_square", "fisher_exact"}


def test_time_series_dispatch_runs():
    n = 96
    rng = np.random.default_rng(123)
    t = np.arange(n)
    values = 0.08 * t + 1.5 * np.sin(2 * np.pi * t / 12) + rng.normal(0.0, 0.3, size=n)
    df = pd.DataFrame(
        {
            "time": pd.date_range("2024-01-01", periods=n, freq="D"),
            "value": values,
        }
    )

    res = run_analysis(
        df,
        "time_series_analysis",
        "value",
        "",
        alpha=0.05,
        time="time",
        seasonal_period=12,
        acf_lags=24,
        ljung_lags=12,
        forecast_horizon=8,
    )
    assert res.get("method") == "time_series_analysis"
    assert int(res.get("n_observations") or 0) == n
    assert isinstance(res.get("trend"), dict)
    assert isinstance(res.get("autocorrelation"), dict)
    assert isinstance(res.get("diagnostics"), dict)
    assert isinstance(res.get("diagnostics", {}).get("ljung_box"), dict)
    assert isinstance(res.get("plot_data"), list) and len(res["plot_data"]) == n
    forecast = res.get("forecast")
    assert isinstance(forecast, dict)
    assert int(forecast.get("horizon") or 0) == 8
    assert isinstance(forecast.get("points"), list) and len(forecast["points"]) == 8


def test_time_series_numeric_axis_not_coerced_to_epoch_dates():
    n = 60
    rng = np.random.default_rng(321)
    id_values = np.arange(1001, 1001 + n)
    signal = 15.0 + 0.03 * np.arange(n) + rng.normal(0.0, 0.25, size=n)
    df = pd.DataFrame({"ID": id_values, "crp": signal})

    res = run_analysis(
        df,
        "time_series_analysis",
        "crp",
        "",
        alpha=0.05,
        time="ID",
        forecast_horizon=5,
    )

    assert res.get("method") == "time_series_analysis"
    assert str(res.get("time_axis_kind")) == "numeric"

    plot_data = res.get("plot_data")
    assert isinstance(plot_data, list) and len(plot_data) == n
    first_x = plot_data[0].get("x")
    assert not (isinstance(first_x, str) and first_x.startswith("1970-"))

    forecast = res.get("forecast")
    assert isinstance(forecast, dict)
    points = forecast.get("points")
    assert isinstance(points, list) and len(points) == 5
    first_fx = points[0].get("x")
    assert not (isinstance(first_fx, str) and first_fx.startswith("1970-"))


def test_time_series_datetime_axis_warns_on_epoch_artifact_years():
    n = 48
    rng = np.random.default_rng(77)
    df = pd.DataFrame(
        {
            "time": pd.date_range("1970-01-05", periods=n, freq="D"),
            "value": 4.0 + 0.05 * np.arange(n) + rng.normal(0.0, 0.2, size=n),
        }
    )

    res = run_analysis(
        df,
        "time_series_analysis",
        "value",
        "",
        alpha=0.05,
        time="time",
        forecast_horizon=4,
    )

    assert res.get("method") == "time_series_analysis"
    assert str(res.get("time_axis_kind")) == "datetime"

    time_quality = res.get("time_quality")
    assert isinstance(time_quality, dict)
    assert str(time_quality.get("quality")) in {"warning", "caution"}
    flags = time_quality.get("flags") or []
    assert any(str(flag) == "epoch_artifact_risk" for flag in flags)

    warnings = res.get("warnings") or []
    assert any("1970-1985" in str(msg) or "epoch" in str(msg).lower() for msg in warnings)


def test_time_series_warnings_use_human_readable_messages():
    n = 24
    rng = np.random.default_rng(91)
    df = pd.DataFrame(
        {
            "time": pd.date_range("2025-01-01", periods=n, freq="D"),
            "value": 7.0 + 0.1 * np.arange(n) + rng.normal(0.0, 0.15, size=n),
        }
    )

    res = run_analysis(
        df,
        "time_series_analysis",
        "value",
        "",
        alpha=0.05,
        time="time",
        seasonal_period=20,
        forecast_horizon=3,
    )

    assert res.get("method") == "time_series_analysis"
    warnings = res.get("warnings") or []
    assert any("Seasonal decomposition skipped" in str(msg) for msg in warnings)
    assert not any(
        "seasonal_decomposition_skipped" in str(msg) or "forecast_fallback_linear" in str(msg)
        for msg in warnings
    )
