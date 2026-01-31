import numpy as np
import pandas as pd

from app.stats.engine import run_analysis


def _build_regression_df(rows=240):
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "target": rng.normal(0, 1, rows),
        "x1": rng.normal(0, 1, rows),
        "x2": rng.normal(0, 1, rows),
        "group": rng.choice(["A", "B", "C"], size=rows)
    })


def _build_classification_df(rows=240):
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        "target": rng.choice(["yes", "no"], size=rows),
        "x1": rng.normal(0, 1, rows),
        "x2": rng.normal(0, 1, rows),
        "group": rng.choice(["A", "B", "C"], size=rows)
    })


def test_ml_regression_outputs():
    df = _build_regression_df()
    methods = ["random_forest", "gradient_boosting", "knn", "svm"]

    for method in methods:
        res = run_analysis(
            df,
            method,
            "target",
            "x1",
            predictors=["x1", "x2", "group"],
            random_state=42
        )
        assert "r_squared" in res
        assert "mae" in res
        assert "rmse" in res
        assert isinstance(res.get("r_squared"), float)
        assert res.get("mae") is None or isinstance(res.get("mae"), float)
        assert res.get("rmse") is None or isinstance(res.get("rmse"), float)


def test_ml_classification_outputs():
    df = _build_classification_df()
    methods = ["random_forest", "gradient_boosting", "knn", "svm"]

    for method in methods:
        res = run_analysis(
            df,
            method,
            "target",
            "x1",
            predictors=["x1", "x2", "group"],
            task="classification",
            random_state=42
        )
        assert "accuracy" in res
        assert 0.0 <= float(res.get("accuracy")) <= 1.0
        if res.get("f1") is not None:
            assert 0.0 <= float(res.get("f1")) <= 1.0
        if res.get("precision") is not None:
            assert 0.0 <= float(res.get("precision")) <= 1.0
        if res.get("recall") is not None:
            assert 0.0 <= float(res.get("recall")) <= 1.0
        roc = res.get("roc")
        assert isinstance(roc, dict)
        assert "auc" in roc
        assert roc.get("plot_data")
